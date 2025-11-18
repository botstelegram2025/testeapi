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
EVO_API_URL = os.environ.get('EVO_API_URL')
EVO_INSTANCE_NAME = os.environ.get('EVO_INSTANCE_NAME')
AUTHENTICATION_API_KEY = os.environ.get('AUTHENTICATION_API_KEY')  # 🔥 ADICIONADA
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
# FUNÇÕES EVOLUTION API
# ================================

def get_headers():
    """Retorna headers SOMENTE se a API KEY existir."""
    if AUTHENTICATION_API_KEY:
        return {"apikey": AUTHENTICATION_API_KEY}
    return {}  # API sem chave

def check_evolution_status():
    url = f"{EVO_API_URL}/"
    logger.info(f"Verificando status da Evolution API: {url}")

    try:
        r = requests.get(url, headers=get_headers(), timeout=10)
        logger.debug(f"Resposta API: {r.text}")
        data = r.json()
        return f"✅ Evolution API Online!\nVersão: {data.get('version')}"
    except Exception as e:
        logger.error(f"Erro ao verificar status: {e}")
        return f"❌ Erro ao verificar Evolution API: {e}"

def get_qrcode_image():
    url = f"{EVO_API_URL}/instance/qrcode/{EVO_INSTANCE_NAME}"
    logger.info(f"Buscando QR Code: {url}")

    try:
        r = requests.get(url, headers=get_headers(), timeout=20)
        logger.debug(f"Headers recebidos: {r.headers}")

        if "image" in r.headers.get("Content-Type", ""):
            return r.content, None

        data = r.json()
        logger.warning(f"QR retornou JSON: {data}")

        return None, data.get("message", "Erro inesperado ao gerar QR Code")

    except Exception as e:
        logger.error(f"Erro QR Code: {e}")
        return None, f"❌ Erro ao buscar QR Code: {e}"

def send_test_message(number, text):
    url = f"{EVO_API_URL}/message/sendText/{EVO_INSTANCE_NAME}"
    payload = {
        "number": number,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": text}
    }

    logger.info(f"Enviando mensagem para {number}")
    logger.debug(f"Payload: {payload}")

    try:
        r = requests.post(url, headers=get_headers(), json=payload, timeout=10)
        logger.debug(f"Resposta API: {r.text}")

        data = r.json()
        if data.get("status") == "success":
            return f"✅ Mensagem enviada! ID: {data.get('id')}"

        return f"⚠️ Falha: {data}"

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return f"❌ Erro ao enviar mensagem: {e}"

# ================================
# HANDLERS TELEGRAM
# ================================

@bot.message_handler(commands=["start", "help"])
def start(message):
    logger.info(f"/start de {message.from_user.id}")
    bot.reply_to(message,
        "🤖 Bot Evolution API\n\n"
        "/status - Verificar API\n"
        "/qrcode - Gerar QR\n"
        "/enviar - Enviar mensagem de teste\n"
        "/env - Ver variáveis carregadas"
    )

@bot.message_handler(commands=["env"])
def env(message):
    bot.send_message(
        message.chat.id,
        f"EVO_API_URL = {EVO_API_URL}\n"
        f"EVO_INSTANCE_NAME = {EVO_INSTANCE_NAME}\n"
        f"AUTHENTICATION_API_KEY = {'DEFINIDA' if AUTHENTICATION_API_KEY else 'VAZIA'}\n"
        f"TEST_PHONE_NUMBER = {TEST_PHONE_NUMBER}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["status"])
def cmd_status(message):
    bot.send_message(message.chat.id, check_evolution_status())

@bot.message_handler(commands=["qrcode"])
def cmd_qrcode(message):
    logger.info("/qrcode solicitado")
    bot.send_message(message.chat.id, "⏳ Buscando QR Code...")

    image, error = get_qrcode_image()
    if error:
        bot.send_message(message.chat.id, f"❌ {error}")
        return

    photo = BytesIO(image)
    photo.name = "qrcode.png"
    bot.send_photo(message.chat.id, photo, caption="📲 Escaneie para conectar seu WhatsApp!")

@bot.message_handler(commands=["enviar"])
def cmd_enviar(message):
    if not TEST_PHONE_NUMBER:
        bot.reply_to(message, "⚠️ TEST_PHONE_NUMBER não configurado.")
        return

    result = send_test_message(TEST_PHONE_NUMBER, "Mensagem de teste via Evolution API.")
    bot.send_message(message.chat.id, result)

# ================================
# INICIAR BOT
# ================================
if __name__ == "__main__":
    logger.info("Iniciando bot...")
    disable_webhook()

    try:
        bot.infinity_polling(
            timeout=50,
            long_polling_timeout=50,
            skip_pending=True
        )
    except Exception as e:
        logger.critical(f"Erro crítico no polling: {e}")
