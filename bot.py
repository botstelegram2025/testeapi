import os
import telebot
import requests
from io import BytesIO
import logging
import qrcode

# ================================
# CONFIGURAÇÃO DE LOGS
# ================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ================================
# VARIÁVEIS DE AMBIENTE
# ================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
EVO_API_URL = os.environ.get('WHATSAPP_API_URL')   # link da API Evolution Free
EVO_INSTANCE_NAME = os.environ.get('EVO_INSTANCE_NAME') or "defaultbot"
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER')

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

def disable_webhook():
    try:
        logger.info("Removendo webhook...")
        bot.remove_webhook()
        logger.info("Webhook removido.")
    except Exception as e:
        logger.error(f"Erro ao remover webhook: {e}")

# ==========================================
# FUNÇÕES DA EVOLUTION API FREE
# ==========================================

def api_get(path):
    url = f"{EVO_API_URL}{path}"
    logger.debug(f"[GET] {url}")
    return requests.get(url, timeout=15).json()

def api_post(path, payload=None, files=None):
    url = f"{EVO_API_URL}{path}"
    logger.debug(f"[POST] {url} | Payload: {payload}")
    return requests.post(url, json=payload, data=payload, files=files, timeout=20).json()

def check_evolution_status():
    try:
        data = api_get("/health")
        return f"✅ API Online!\n{data}"
    except Exception as e:
        return f"❌ Erro ao verificar API: {e}"

def get_qrcode_image():
    try:
        data = api_get(f"/instance/qr/{EVO_INSTANCE_NAME}")

        qr_text = data.get("qr")
        if not qr_text:
            return None, "QR ainda não disponível. A instância pode estar conectada ou carregando."

        img = qrcode.make(qr_text)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return buf.getvalue(), None

    except Exception as e:
        return None, f"❌ Erro ao gerar QR: {e}"

def send_text_message(number, text):
    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": number,
        "message": text
    }
    return api_post("/message/sendText", payload)

# ==========================================
# COMANDOS DO BOT
# ==========================================

@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.reply_to(message,
        "🤖 *Evolution API FREE Bot*\n\n"
        "/status - Verificar API\n"
        "/qrcode - QR Code da instância\n"
        "/enviar - Enviar mensagem texto\n"
        "/instancias - Listar instâncias\n"
        "/criar_instancia nome\n"
        "/connect - Reconectar instância\n"
        "/restart - Reiniciar instância\n"
        "/enviar_imagem\n"
        "/enviar_audio\n"
        "/enviar_doc\n"
        "/botao - Enviar botões interativos\n"
        "/env - Ver variáveis\n",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["env"])
def env(message):
    bot.send_message(
        message.chat.id,
        f"""
EVO_API_URL = {EVO_API_URL}
EVO_INSTANCE_NAME = {EVO_INSTANCE_NAME}
TEST_PHONE_NUMBER = {TEST_PHONE_NUMBER}
""",
        parse_mode="Markdown"
    )

# =====================================================
# STATUS
# =====================================================

@bot.message_handler(commands=["status"])
def cmd_status(message):
    bot.send_message(message.chat.id, check_evolution_status())

# =====================================================
# QR CODE
# =====================================================

@bot.message_handler(commands=["qrcode"])
def cmd_qrcode(message):
    bot.send_message(message.chat.id, "⏳ Gerando QR...")

    img, error = get_qrcode_image()

    if error:
        bot.send_message(message.chat.id, f"❌ {error}")
        return

    photo = BytesIO(img)
    photo.name = "qr.png"
    bot.send_photo(message.chat.id, photo, caption="📲 Escaneie para conectar!")

# =====================================================
# ENVIAR MENSAGEM SIMPLES
# =====================================================

@bot.message_handler(commands=["enviar"])
def cmd_enviar(message):
    if not TEST_PHONE_NUMBER:
        return bot.send_message(message.chat.id, "⚠ TEST_PHONE_NUMBER não configurado")

    r = send_text_message(TEST_PHONE_NUMBER, "Mensagem de teste via Evolution API Free")
    bot.send_message(message.chat.id, f"📨 {r}")

# =====================================================
# /instancias
# =====================================================

@bot.message_handler(commands=["instancias"])
def cmd_instancias(message):
    try:
        data = api_get("/instance/fetchInstances")

        if not data.get("instances"):
            bot.send_message(message.chat.id, "📭 Nenhuma instância criada.")
            return

        lista = "\n".join([f"➡️ {i}" for i in data["instances"]])
        bot.send_message(message.chat.id, f"📌 *Instâncias:*\n{lista}", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro: {e}")

# =====================================================
# /criar_instancia <nome>
# =====================================================

@bot.message_handler(commands=["criar_instancia"])
def cmd_criar_instancia(message):
    parts = message.text.split()

    if len(parts) < 2:
        return bot.reply_to(message, "⚠ Use: /criar_instancia nome")

    nome = parts[1]

    r = api_post("/instance/create", {"instanceName": nome})
    bot.send_message(message.chat.id, f"📌 {r}")

# =====================================================
# /connect
# =====================================================

@bot.message_handler(commands=["connect"])
def cmd_connect(message):
    r = api_post(f"/instance/connect/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔄 Conectando...\n{r}")

# =====================================================
# /restart
# =====================================================

@bot.message_handler(commands=["restart"])
def cmd_restart(message):
    r = api_post(f"/instance/restart/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔁 Reiniciando...\n{r}")

# =====================================================
# ENVIO DE MÍDIA (IMAGEM)
# =====================================================

@bot.message_handler(commands=["enviar_imagem"])
def cmd_enviar_imagem(message):
    bot.send_message(message.chat.id, "📸 Envie uma imagem agora...")

    @bot.message_handler(content_types=["photo"])
    def process_image(img_msg):
        file_id = img_msg.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        url = f"{EVO_API_URL}/message/sendMedia"
        files = {'file': ('image.jpg', downloaded, 'image/jpeg')}
        payload = {
            "instanceName": EVO_INSTANCE_NAME,
            "to": TEST_PHONE_NUMBER,
            "caption": "Imagem via Evolution API Free"
        }

        response = requests.post(url, data=payload, files=files)
        bot.send_message(message.chat.id, f"📨 {response.text}")

# =====================================================
# ENVIO DE ÁUDIO
# =====================================================

@bot.message_handler(commands=["enviar_audio"])
def cmd_enviar_audio(message):
    bot.send_message(message.chat.id, "🎤 Envie o áudio...")

    @bot.message_handler(content_types=["audio", "voice"])
    def process_audio(audio_msg):
        file_id = audio_msg.audio.file_id if audio_msg.audio else audio_msg.voice.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        url = f"{EVO_API_URL}/message/sendMedia"
        files = {'file': ('audio.ogg', downloaded, 'audio/ogg')}
        payload = {
            "instanceName": EVO_INSTANCE_NAME,
            "to": TEST_PHONE_NUMBER,
            "caption": "Áudio via Evolution API Free"
        }

        response = requests.post(url, data=payload, files=files)
        bot.send_message(message.chat.id, f"📨 {response.text}")

# =====================================================
# ENVIO DE DOCUMENTO
# =====================================================

@bot.message_handler(commands=["enviar_doc"])
def cmd_enviar_doc(message):
    bot.send_message(message.chat.id, "📄 Envie agora o arquivo...")

    @bot.message_handler(content_types=["document"])
    def process_doc(doc_msg):
        file_id = doc_msg.document.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        url = f"{EVO_API_URL}/message/sendMedia"
        files = {
            'file': (doc_msg.document.file_name, downloaded, doc_msg.document.mime_type)
        }
        payload = {
            "instanceName": EVO_INSTANCE_NAME,
            "to": TEST_PHONE_NUMBER,
            "caption": "Documento via Evolution API Free"
        }

        response = requests.post(url, data=payload, files=files)
        bot.send_message(message.chat.id, f"📨 {response.text}")

# =====================================================
# BOTÕES INTERATIVOS
# =====================================================

@bot.message_handler(commands=["botao"])
def cmd_botao(message):
    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": TEST_PHONE_NUMBER,
        "message": "Escolha uma opção:",
        "buttons": [
            {"id": "sim", "text": "Sim 👍"},
            {"id": "nao", "text": "Não 👎"}
        ]
    }

    r = api_post("/message/sendText", payload)
    bot.send_message(message.chat.id, f"📨 {r}")

# ==========================================
# INICIAR BOT
# ==========================================
if __name__ == "__main__":
    logger.info("Iniciando bot...")
    disable_webhook()
    bot.infinity_polling(timeout=50, long_polling_timeout=50, skip_pending=True)
