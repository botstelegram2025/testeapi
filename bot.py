import os
import telebot
import requests
from io import BytesIO
import logging

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
EVO_API_URL = os.environ.get('WHATSAPP_API_URL')  # 🔥 usa API free
EVO_INSTANCE_NAME = os.environ.get('EVO_INSTANCE_NAME')
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER')

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

def disable_webhook():
    try:
        logger.info("Removendo webhook antes de iniciar polling...")
        bot.remove_webhook()
        logger.info("Webhook removido com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao remover webhook: {e}")

# ================================
# FUNÇÕES EVOLUTION API FREE
# ================================

def check_evolution_status():
    url = f"{EVO_API_URL}/health"
    logger.info(f"Verificando status da API: {url}")

    try:
        r = requests.get(url, timeout=10)
        return f"✅ API Online!\nResposta: {r.text}"
    except Exception as e:
        logger.error(f"Erro status: {e}")
        return f"❌ Erro ao verificar API: {e}"

def get_qrcode_image():
    url = f"{EVO_API_URL}/instance/qr/{EVO_INSTANCE_NAME}"
    logger.info(f"Buscando QR Code: {url}")

    try:
        r = requests.get(url, timeout=15)

        data = r.json()
        qr_text = data.get("qr")

        if not qr_text:
            return None, "QR não disponível. A instância ainda não gerou o QR."

        # Converte texto QR para imagem
        import qrcode
        img = qrcode.make(qr_text)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer.getvalue(), None

    except Exception as e:
        logger.error(f"Erro QR Code: {e}")
        return None, f"❌ Erro ao buscar QR Code: {e}"

def send_test_message(number, text):
    url = f"{EVO_API_URL}/message/sendText"
    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": number,
        "message": text
    }

    logger.info(f"Enviando mensagem para {number}: {text}")

    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()

        if data.get("status"):
            return "✅ Mensagem enviada com sucesso!"
        return f"⚠️ Falha: {data}"

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return f"❌ Erro ao enviar mensagem: {e}"

# ================================
# COMMANDS TELEGRAM
# ================================

@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.reply_to(message,
        "🤖 Bot WhatsApp Evolution FREE\n\n"
        "/status - Testar API\n"
        "/qrcode - Ver QR Code\n"
        "/enviar - Enviar mensagem teste\n"
        "/env - Ver variáveis carregadas"
    )

@bot.message_handler(commands=["env"])
def env(message):
    bot.send_message(
        message.chat.id,
        f"EVO_API_URL = {EVO_API_URL}\n"
        f"EVO_INSTANCE_NAME = {EVO_INSTANCE_NAME}\n"
        f"TEST_PHONE_NUMBER = {TEST_PHONE_NUMBER}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["status"])
def cmd_status(message):
    bot.send_message(message.chat.id, check_evolution_status())

@bot.message_handler(commands=["qrcode"])
def cmd_qrcode(message):
    bot.send_message(message.chat.id, "⏳ Gerando QR Code...")

    image, error = get_qrcode_image()

    if error:
        bot.send_message(message.chat.id, f"❌ {error}")
        return

    photo = BytesIO(image)
    photo.name = "qrcode.png"

    bot.send_photo(message.chat.id, photo, caption="📲 Escaneie o QR para conectar!")

@bot.message_handler(commands=["enviar"])
def cmd_enviar(message):
    if not TEST_PHONE_NUMBER:
        bot.reply_to(message, "⚠ TEST_PHONE_NUMBER não configurado.")
        return

    result = send_test_message(TEST_PHONE_NUMBER, "Mensagem de teste via Evolution FREE API")
    bot.send_message(message.chat.id, result)

# ================================
# INICIAR BOT
# ================================
if __name__ == "__main__":
    logger.info("Iniciando bot...")
    disable_webhook()
    bot.infinity_polling(timeout=50, long_polling_timeout=50, skip_pending=True)
