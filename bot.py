import os
import telebot
import requests
from io import BytesIO
import logging

# ================================
# CONFIGURAÇÃO DE LOGS
# ================================
logging.basicConfig(
    level=logging.DEBUG,  # INFO ou DEBUG
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# ================================
# VARIÁVEIS DE AMBIENTE
# ================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
EVO_API_URL = os.environ.get('EVO_API_URL')
EVO_API_KEY = os.environ.get('EVO_API_KEY')
EVO_INSTANCE_NAME = os.environ.get('EVO_INSTANCE_NAME')
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER')

# ================================
# INICIALIZA BOT (com threads desligadas)
# ================================
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

def disable_webhook():
    try:
        logger.info("Removendo webhook antes de iniciar polling...")
        bot.remove_webhook()
        logger.info("Webhook removido com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao remover webhook: {e}")

# ================================
# EVOLUTION API — FUNÇÕES COM LOG
# ================================

def check_evolution_status():
    url = f"{EVO_API_URL}/"
    headers = {'apikey': EVO_API_KEY}

    logger.info(f"Consultando status da Evolution API: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        logger.debug(f"Resposta bruta da API (status {response.status_code}): {response.text}")

        response.raise_for_status()
        data = response.json()

        if data.get("status") == 200:
            return f"✅ Evolution API Online!\nVersão: {data.get('version', 'N/A')}"

        return f"⚠️ API online, mas com status inesperado: {data}"

    except Exception as e:
        logger.error(f"Erro ao verificar Evolution API: {e}")
        return f"❌ Erro ao verificar Evolution API: {e}"


def get_qrcode_image():
    url = f"{EVO_API_URL}/instance/qrcode/{EVO_INSTANCE_NAME}"
    headers = {'apikey': EVO_API_KEY}

    logger.info(f"Solicitando QR Code da Evolution API: {url}?format=image")

    try:
        response = requests.get(url, headers=headers, params={'format': 'image'}, timeout=20)
        logger.debug(f"Headers recebidos: {response.headers}")
        content_type = response.headers.get("Content-Type", "")

        # Caso seja imagem
        if "image" in content_type:
            logger.info("QR Code recebido com sucesso (imagem).")
            return response.content, None

        # Caso venha JSON (instância conectada ou erro)
        try:
            data = response.json()
            logger.warning(f"API retornou JSON ao invés de imagem: {data}")

            if data.get("state") == "connected":
                return None, "⚠️ Instância já está conectada."

            return None, f"❌ Erro da API: {data.get('message')}"

        except:
            logger.error("Resposta não é imagem nem JSON válido.")
            return None, "❌ Resposta inválida da Evolution API."

    except Exception as e:
        logger.error(f"Erro ao buscar QR Code: {e}")
        return None, f"❌ Erro ao buscar QR Code: {e}"


def send_test_message(phone_number, message_text):
    url = f"{EVO_API_URL}/message/sendText/{EVO_INSTANCE_NAME}"
    headers = {'apikey': EVO_API_KEY, 'Content-Type': 'application/json'}
    payload = {
        "number": phone_number,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": message_text}
    }

    logger.info(f"Enviando mensagem para {phone_number}...")
    logger.debug(f"Payload enviado: {payload}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.debug(f"Resposta API (status {response.status_code}): {response.text}")

        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            logger.info(f"Mensagem enviada com sucesso! ID: {data.get('id')}")
            return f"✅ Mensagem enviada!\nID: `{data.get('id')}`"

        logger.warning(f"Falha no envio: {data}")
        return f"⚠️ Falha ao enviar mensagem: {data.get('message')}"

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return f"❌ Erro ao enviar mensagem: {e}"


# ================================
# HANDLERS DO TELEGRAM (com logs)
# ================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    logger.info(f"Comando /start recebido de {message.from_user.id}")
    bot.reply_to(message,
        "🤖 Bot Evolution API\n\n"
        "/status - Verificar API\n"
        "/qrcode - Obter QR Code\n"
        "/enviar - Enviar mensagem de teste"
    )


@bot.message_handler(commands=['status'])
def handle_status(message):
    logger.info("/status solicitado.")
    bot.send_message(message.chat.id, check_evolution_status(), parse_mode="Markdown")


@bot.message_handler(commands=['qrcode'])
def handle_qrcode(message):
    logger.info("/qrcode solicitado.")
    bot.send_message(message.chat.id, "⏳ Buscando QR Code...")

    image_data, error = get_qrcode_image()

    if error:
        logger.warning(f"Erro no QR Code: {error}")
        bot.send_message(message.chat.id, error, parse_mode="Markdown")
        return

    if image_data:
        logger.info("Enviando QR Code ao usuário.")
        photo = BytesIO(image_data)
        photo.name = "qrcode.png"
        bot.send_photo(message.chat.id, photo, caption="📲 Escaneie para conectar o WhatsApp!")


@bot.message_handler(commands=['enviar'])
def handle_send(message):
    logger.info("/enviar solicitado.")

    if not TEST_PHONE_NUMBER:
        logger.error("TEST_PHONE_NUMBER não configurado.")
        bot.reply_to(message, "⚠️ TEST_PHONE_NUMBER não configurado.")
        return

    res = send_test_message(TEST_PHONE_NUMBER, "Mensagem de teste via Evolution API.")
    bot.send_message(message.chat.id, res, parse_mode="Markdown")


# ================================
# LOOP PRINCIPAL DO BOT
# ================================
if __name__ == '__main__':
    logger.info("Iniciando bot do Telegram...")
    disable_webhook()

    try:
        bot.infinity_polling(
            timeout=45,
            long_polling_timeout=45,
            skip_pending=True
        )
    except Exception as e:
        logger.critical(f"Falha crítica no polling: {e}")
