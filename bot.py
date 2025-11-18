import os
import telebot
import requests
from io import BytesIO

# --- Configurações ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
EVO_API_URL = os.environ.get('EVO_API_URL')
EVO_API_KEY = os.environ.get('EVO_API_KEY')
EVO_INSTANCE_NAME = os.environ.get('EVO_INSTANCE_NAME')
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER')

# IMPORTANTE: desativa o parse threading para evitar instâncias duplicadas
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# --- Função para evitar erro 409 ---
def disable_webhook():
    """Remove qualquer webhook antes de iniciar polling."""
    try:
        bot.remove_webhook()
        print("Webhook removido com sucesso.")
    except Exception as e:
        print("Não foi possível remover webhook:", e)

# --- Funções Evolution API ---
def check_evolution_status():
    url = f"{EVO_API_URL}/"
    headers = {'apikey': EVO_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == 200:
            return f"✅ Evolution API Online!\nVersão: {data.get('version', 'N/A')}"
        else:
            return f"⚠️ Status inesperado:\n{data.get('message')}"
    except Exception as e:
        return f"❌ Erro ao verificar API: {e}"

def get_qrcode_image():
    url = f"{EVO_API_URL}/instance/qrcode/{EVO_INSTANCE_NAME}"
    headers = {'apikey': EVO_API_KEY}

    try:
        response = requests.get(url, headers=headers, params={'format':'image'}, timeout=20)

        if 'image' in response.headers.get('Content-Type', ''):
            return response.content, None

        try:
            data = response.json()
            if data.get("state") == "connected":
                return None, "⚠️ Instância já conectada."
            return None, f"❌ Erro da API: {data.get('message')}"
        except:
            return None, "❌ Resposta inválida da Evolution API."

    except Exception as e:
        return None, f"❌ Erro ao buscar QR Code: {e}"

def send_test_message(phone_number, message_text):
    url = f"{EVO_API_URL}/message/sendText/{EVO_INSTANCE_NAME}"
    headers = {'apikey': EVO_API_KEY, 'Content-Type': 'application/json'}
    payload = {
        "number": phone_number,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": message_text}
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()

        if data.get("status") == "success":
            return f"✅ Mensagem enviada!\nID: `{data.get('id')}`"
        return f"⚠️ Falha: {data.get('message')}"
    
    except Exception as e:
        return f"❌ Erro ao enviar: {e}"

# --- Comandos do Bot ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message,
        "🤖 Bot Evolution API\n\n"
        "/status - Verificar API\n"
        "/qrcode - Obter QR Code\n"
        "/enviar - Enviar mensagem de teste"
    )

@bot.message_handler(commands=['status'])
def handle_status(message):
    bot.reply_to(message, check_evolution_status(), parse_mode="Markdown")

@bot.message_handler(commands=['qrcode'])
def handle_qrcode(message):
    bot.send_message(message.chat.id, "⏳ Buscando QR Code...")
    image_data, error = get_qrcode_image()

    if error:
        bot.send_message(message.chat.id, error, parse_mode="Markdown")
        return

    if image_data:
        photo = BytesIO(image_data)
        photo.name = "qrcode.png"
        bot.send_photo(message.chat.id, photo, caption="📲 Escaneie para conectar o WhatsApp!")

@bot.message_handler(commands=['enviar'])
def handle_send(message):
    if not TEST_PHONE_NUMBER:
        bot.reply_to(message, "⚠️ TEST_PHONE_NUMBER não configurado.")
        return

    res = send_test_message(TEST_PHONE_NUMBER, "Mensagem de teste via Evolution API.")
    bot.send_message(message.chat.id, res, parse_mode="Markdown")

# --- Inicialização ---
if __name__ == '__main__':
    print("Bot do Telegram iniciando...")

    disable_webhook()  # 🔥 MUITO IMPORTANTE

    # Polling sem múltiplas instâncias
    bot.infinity_polling(
        timeout=45,
        long_polling_timeout=45,
        skip_pending=True
    )
