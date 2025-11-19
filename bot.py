import os
import telebot
import requests
from io import BytesIO
import logging
import qrcode

# ================================
# LOGS
# ================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ================================
# VARIÁVEIS DE AMBIENTE
# ================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
EVO_API_URL = os.environ.get("EVO_API_URL")
EVO_INSTANCE_NAME = os.environ.get("EVO_INSTANCE_NAME") or "defaultbot"
TEST_PHONE_NUMBER = os.environ.get("TEST_PHONE_NUMBER")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)


# ================================
# FUNÇÕES AUXILIARES API
# ================================
def api_get(path):
    url = f"{EVO_API_URL}{path}"
    logger.debug(f"[GET] {url}")
    r = requests.get(url, timeout=20)
    return r.json()


def api_post(path, payload=None, files=None):
    url = f"{EVO_API_URL}{path}"
    logger.debug(f"[POST] {url} | Payload={payload}")
    if files:
        r = requests.post(url, data=payload, files=files, timeout=30)
    else:
        r = requests.post(url, json=payload, timeout=30)
    return r.json()


# ================================
# STATUS
# ================================
@bot.message_handler(commands=["status"])
def cmd_status(message):
    try:
        data = api_get("/health")
        bot.send_message(message.chat.id, f"✅ API Online!\n{data}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro ao consultar API: {e}")


# ================================
# QR CODE
# ================================
@bot.message_handler(commands=["qrcode"])
def cmd_qrcode(message):
    bot.send_message(message.chat.id, "⏳ Gerando QR...")

    try:
        data = api_get(f"/instance/qr/{EVO_INSTANCE_NAME}")
        qr_text = data.get("qr")

        if not qr_text:
            bot.send_message(message.chat.id, "❌ QR ainda não disponível.")
            return

        img = qrcode.make(qr_text)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buf.name = "qr.png"

        bot.send_photo(message.chat.id, buf, caption="📲 Escaneie para conectar!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro ao gerar QR: {e}")


# ================================
# ENVIAR TEXTO
# ================================
@bot.message_handler(commands=["enviar"])
def cmd_enviar(message):
    if not TEST_PHONE_NUMBER:
        bot.send_message(message.chat.id, "⚠ Configure TEST_PHONE_NUMBER.")
        return

    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": TEST_PHONE_NUMBER,
        "message": "Mensagem de teste via Evolution API Free"
    }

    r = api_post("/message/sendText", payload)
    bot.send_message(message.chat.id, f"📨 {r}")


# ================================
# LISTAR INSTÂNCIAS
# ================================
@bot.message_handler(commands=["instancias"])
def cmd_instancias(message):
    try:
        data = api_get("/instance/fetchInstances")
        insts = data.get("instances", [])

        if not insts:
            bot.send_message(message.chat.id, "📭 Nenhuma instância criada.")
            return

        texto = "\n".join([f"➡️ {i}" for i in insts])
        bot.send_message(message.chat.id, f"📌 *Instâncias:*\n{texto}", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro: {e}")


# ================================
# CRIAR INSTÂNCIA
# ================================
@bot.message_handler(commands=["criar_instancia"])
def cmd_criar_instancia(message):
    try:
        _, nome = message.text.split(maxsplit=1)
    except:
        bot.send_message(message.chat.id, "⚠ Use: /criar_instancia nome")
        return

    payload = {"instanceName": nome.strip()}
    logger.info(f"Criando instância: {payload}")

    r = api_post("/instance/create", payload)
    bot.send_message(message.chat.id, f"📌 Resultado:\n{r}")


# ================================
# CONNECT
# ================================
@bot.message_handler(commands=["connect"])
def cmd_connect(message):
    r = api_post(f"/instance/connect/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔄 Conectando...\n{r}")


# ================================
# RESTART
# ================================
@bot.message_handler(commands=["restart"])
def cmd_restart(message):
    r = api_post(f"/instance/restart/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔁 Reiniciando...\n{r}")


# ================================
# ENVIAR IMAGEM
# ================================
@bot.message_handler(commands=["enviar_imagem"])
def cmd_enviar_imagem(message):
    bot.send_message(message.chat.id, "📸 Envie a imagem agora...")

    @bot.message_handler(content_types=["photo"])
    def process_image(img_msg):
        file_id = img_msg.photo[-1].file_id
        info = bot.get_file(file_id)
        img = bot.download_file(info.file_path)

        files = {"file": ("image.jpg", img, "image/jpeg")}
        payload = {
            "instanceName": EVO_INSTANCE_NAME,
            "to": TEST_PHONE_NUMBER,
            "caption": "Imagem via Evolution API Free"
        }

        r = api_post("/message/sendMedia", payload, files)
        bot.send_message(message.chat.id, f"📨 {r}")


# ================================
# ENVIAR ÁUDIO
# ================================
@bot.message_handler(commands=["enviar_audio"])
def cmd_enviar_audio(message):
    bot.send_message(message.chat.id, "🎤 Envie o áudio...")

    @bot.message_handler(content_types=["audio", "voice"])
    def process_audio(audio_msg):
        file_id = audio_msg.audio.file_id if audio_msg.audio else audio_msg.voice.file_id
        info = bot.get_file(file_id)
        audio = bot.download_file(info.file_path)

        files = {"file": ("audio.ogg", audio, "audio/ogg")}
        payload = {
            "instanceName": EVO_INSTANCE_NAME,
            "to": TEST_PHONE_NUMBER,
            "caption": "Áudio via Evolution Free"
        }

        r = api_post("/message/sendMedia", payload, files)
        bot.send_message(message.chat.id, f"📨 {r}")


# ================================
# ENVIAR DOCUMENTO
# ================================
@bot.message_handler(commands=["enviar_doc"])
def cmd_enviar_doc(message):
    bot.send_message(message.chat.id, "📄 Envie o documento...")

    @bot.message_handler(content_types=["document"])
    def process_doc(doc_msg):
        file_id = doc_msg.document.file_id
        info = bot.get_file(file_id)
        doc = bot.download_file(info.file_path)

        files = {"file": (doc_msg.document.file_name, doc, doc_msg.document.mime_type)}
        payload = {
            "instanceName": EVO_INSTANCE_NAME,
            "to": TEST_PHONE_NUMBER,
            "caption": "Documento via Evolution"
        }

        r = api_post("/message/sendMedia", payload, files)
        bot.send_message(message.chat.id, f"📨 {r}")


# ================================
# BOTÕES INTERATIVOS
# ================================
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


# ================================
# INICIAR BOT
# ================================
def disable_webhook():
    try:
        bot.remove_webhook()
    except:
        pass


if __name__ == "__main__":
    disable_webhook()
    logger.info("🚀 Bot iniciado!")
    bot.infinity_polling(timeout=50, long_polling_timeout=50, skip_pending=True)
