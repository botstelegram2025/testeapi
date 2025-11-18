import os
import telebot
import requests
from io import BytesIO

# --- Configurações/Variáveis de Ambiente ---
# O token do seu bot, obtido no BotFather
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# A URL da sua Evolution API (ex: https://sua-api.com.br)
EVO_API_URL = os.environ.get('EVO_API_URL')
# A chave de API/Token de autenticação da Evolution
EVO_API_KEY = os.environ.get('EVO_API_KEY')
# O nome da instância que você criou na Evolution API
EVO_INSTANCE_NAME = os.environ.get('EVO_INSTANCE_NAME')
# O número de telefone de teste (no formato 55DDD9XXXXXXXX, sem + ou outros caracteres)
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER')

# Inicializa o bot
bot = telebot.TeleBot(BOT_TOKEN)

# --- Funções de API ---

def check_evolution_status():
    """Verifica se a Evolution API está online."""
    url = f"{EVO_API_URL}/"
    headers = {'apikey': EVO_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == 200:
            return f"✅ **Evolution API Online!**\nVersão: {data.get('version', 'N/A')}"
        else:
            return f"⚠️ **Evolution API Online, mas com status inesperado:**\n{data.get('message', 'Sem detalhes')}"
            
    except requests.exceptions.RequestException as e:
        return f"❌ **Erro de conexão com Evolution API:** {e}"
    except Exception as e:
        return f"❌ **Erro inesperado ao verificar Evolution API:** {e}"

def get_qrcode_image():
    """Solicita a imagem do QR Code para a instância na Evolution API."""
    url = f"{EVO_API_URL}/instance/qrcode/{EVO_INSTANCE_NAME}"
    headers = {'apikey': EVO_API_KEY}
    
    try:
        # Usa o parâmetro 'format=image' para receber a imagem diretamente
        response = requests.get(url, headers=headers, params={'format': 'image'}, timeout=20)
        
        # O endpoint de QR Code retorna 200 mesmo se já estiver conectado, mas pode não ter imagem.
        # Se o conteúdo for binário (imagem) e não JSON (erro ou status de conectado), prosseguimos.
        if 'image' in response.headers.get('Content-Type', ''):
            # Retorna o conteúdo binário da imagem
            return response.content, None 
        
        # Caso não seja uma imagem, tentamos ler como JSON para encontrar o status ou erro
        try:
            data = response.json()
            # Se a instância já estiver CONECTADA, a API retorna JSON.
            if data.get("state") == "connected":
                 return None, "⚠️ **A instância já está conectada.** Não é necessário gerar o QR Code novamente."
            # Se houver outro erro ou status no JSON
            return None, f"❌ **Erro da API Evolution:** {data.get('message', 'Resposta API sem imagem.')}"
        except requests.exceptions.JSONDecodeError:
            return None, "❌ **Erro:** Resposta da Evolution API não é uma imagem e nem um JSON válido."

    except requests.exceptions.RequestException as e:
        return None, f"❌ **Erro de conexão ao buscar QR Code:** {e}"
    except Exception as e:
        return None, f"❌ **Erro inesperado ao buscar QR Code:** {e}"

def send_test_message(phone_number, message_text):
    """Envia uma mensagem de texto simples via Evolution API."""
    url = f"{EVO_API_URL}/message/sendText/{EVO_INSTANCE_NAME}"
    headers = {
        'apikey': EVO_API_KEY,
        'Content-Type': 'application/json'
    }
    payload = {
        "number": phone_number,
        "options": {
            "delay": 1200,
            "presence": "composing",
        },
        "textMessage": {
            "text": message_text
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            return f"✅ **Mensagem enviada com sucesso!**\nDestinatário: `{phone_number}`\nID: `{data.get('id', 'N/A')}`"
        else:
            return f"⚠️ **Falha no envio da mensagem:**\nDetalhes: {data.get('message', 'Resposta API sem detalhes')}"
            
    except requests.exceptions.RequestException as e:
        return f"❌ **Erro de conexão ao enviar mensagem:** {e}"
    except Exception as e:
        return f"❌ **Erro inesperado ao enviar mensagem:** {e}"

# --- Manipuladores de Comandos do Telegram ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Manipula os comandos /start e /help."""
    welcome_text = (
        "🤖 Olá! Eu sou o Bot de Teste da Evolution API.\n\n"
        "Comandos disponíveis:\n"
        "/status - Verifica se a Evolution API está online.\n"
        "/qrcode - Solicita e envia o QR Code para conectar a instância.\n"
        "/enviar - Envia uma mensagem de teste para o número pré-configurado."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['status'])
def handle_status(message):
    """Manipula o comando /status."""
    bot.reply_to(message, "⚙️ Verificando o status da Evolution API...", parse_mode="Markdown")
    status_result = check_evolution_status()
    bot.send_message(message.chat.id, status_result, parse_mode="Markdown")
    
@bot.message_handler(commands=['qrcode'])
def handle_qrcode(message):
    """Manipula o comando /qrcode para gerar e enviar o QR Code."""
    
    bot.reply_to(message, "⏳ Solicitando o QR Code da Evolution API. Isso pode levar alguns segundos...", parse_mode="Markdown")
    
    image_data, error_message = get_qrcode_image()
    
    if error_message:
        # Envia a mensagem de erro (já formatada em Markdown)
        bot.send_message(message.chat.id, error_message, parse_mode="Markdown")
    elif image_data:
        try:
            # Converte o conteúdo binário para um arquivo em memória que o Telegram possa ler
            photo = BytesIO(image_data)
            photo.name = 'qrcode.png' # Nome do arquivo
            
            # Envia a foto
            bot.send_photo(
                chat_id=message.chat.id,
                photo=photo,
                caption="📲 **Escaneie este QR Code no seu WhatsApp** para conectar a instância."
            )
            bot.send_message(message.chat.id, "💡 Lembre-se: O QR Code tem um tempo de validade. Se não conectar, tente novamente.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ **Erro ao enviar a imagem no Telegram:** {e}")

@bot.message_handler(commands=['enviar'])
def handle_send(message):
    """Manipula o comando /enviar para mandar uma mensagem de teste."""
    
    if not TEST_PHONE_NUMBER:
        bot.reply_to(message, "❌ **Erro:** A variável de ambiente `TEST_PHONE_NUMBER` não está configurada.", parse_mode="Markdown")
        return

    test_message = "Teste de envio de mensagem via Bot Telegram e Evolution API."
    bot.reply_to(message, f"✉️ Tentando enviar a mensagem para `{TEST_PHONE_NUMBER}`...", parse_mode="Markdown")
    
    send_result = send_test_message(TEST_PHONE_NUMBER, test_message)
    bot.send_message(message.chat.id, send_result, parse_mode="Markdown")

# --- Loop Principal do Bot ---

if __name__ == '__main__':
    print("Bot do Telegram iniciando...")
    bot.infinity_polling()
