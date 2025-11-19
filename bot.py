#!/usr/bin/env python3
import os
import time
import logging
import requests
from io import BytesIO
import qrcode
import telebot
from telebot.apihelper import ApiTelegramException
from filelock import FileLock

# ======================================================
# LOGS
# ======================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("EvolutionFreeBot")

# ======================================================
# VARIÁVEIS
# ======================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
EVO_API_URL = os.getenv("EVO_API_URL")
AUTHENTICATION_API_KEY = os.getenv("AUTHENTICATION_API_KEY")
EVO_INSTANCE_NAME = os.getenv("EVO_INSTANCE_NAME") or "instanciaPadrao"
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER")

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN não configurado")

if not EVO_API_URL:
    raise SystemExit("❌ EVO_API_URL não configurado")

EVO_API_URL = EVO_API_URL.rstrip("/")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# lock para impedir DUPLO POLLING = causa 409
LOCKFILE = "/tmp/bot_polling.lock"

awaiting_action = {}

# ======================================================
# FUNÇÕES HTTP
# ======================================================
def headers():
    h = {}
    if AUTHENTICATION_API_KEY:
        h["apikey"] = AUTHENTICATION_API_KEY
    return h

def api_get(path):
    try:
        r = requests.get(EVO_API_URL + path, headers=headers(), timeout=20)
        return r.status_code, r.json()
    except Exception as e:
        return None, {"status": False, "error": str(e)}

def api_post(path, payload=None, files=None):
    try:
        hdr = headers()
        if files:
            r = requests.post(EVO_API_URL + path, data=payload, files=files, headers=hdr, timeout=60)
        else:
            hdr["Content-Type"] = "application/json"
            r = requests.post(EVO_API_URL + path, json=payload, headers=hdr, timeout=30)
        return r.status_code, r.json()
    except Exception as e:
        return None, {"status": False, "error": str(e)}

# ======================================================
# COMANDOS DO BOT
# ======================================================
@bot.message_handler(commands=["start", "help"])
def start(message):
    txt = (
        "🤖 *Evolution Free Bot*\n\n"
        "/status - Ver API\n"
        "/instancias - Listar instâncias\n"
        "/criar_instancia NOME\n"
        "/connect - Conectar instância\n"
        "/restart - Reiniciar instância\n"
        "/qrcode - QR Code\n"
        "/enviar - Enviar texto\n"
        "/enviar_imagem\n"
        "/enviar_audio\n"
        "/enviar_doc\n"
        "/botao - Botões interativos\n"
        "/env - Variáveis"
    )
    bot.send_message(message.chat.id, txt, parse_mode="Markdown")

@bot.message_handler(commands=["env"])
def cmd_env(message):
    bot.send_message(
        message.chat.id,
        f"EVO_API_URL = {EVO_API_URL}\n"
        f"EVO_INSTANCE_NAME = {EVO_INSTANCE_NAME}\n"
        f"AUTHENTICATION_API_KEY = {'SET' if AUTHENTICATION_API_KEY else 'NOT SET'}\n"
        f"TEST_PHONE_NUMBER = {TEST_PHONE_NUMBER}"
    )

@bot.message_handler(commands=["status"])
def cmd_status(message):
    code, data = api_get("/health")
    if code == 200:
        bot.send_message(message.chat.id, f"✅ API Online\n{data}")
    else:
        bot.send_message(message.chat.id, f"❌ Erro: {data}")

@bot.message_handler(commands=["instancias"])
def cmd_instancias(message):
    code, data = api_get("/instance/fetchInstances")
    if code == 200:
        insts = data.get("instances", [])
        if not insts:
            bot.send_message(message.chat.id, "📭 Nenhuma instância criada.")
            return
        lista = "\n".join(f"➡ {i}" for i in insts)
        bot.send_message(message.chat.id, f"📌 Instâncias:\n{lista}")
    else:
        bot.send_message(message.chat.id, f"❌ {data}")

@bot.message_handler(commands=["criar_instancia"])
def criar(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "⚠ Use: /criar_instancia nome")
        return
    nome = parts[1].strip()
    _, data = api_post("/instance/create", {"instanceName": nome})
    bot.send_message(message.chat.id, f"📌 {data}")

@bot.message_handler(commands=["connect"])
def connect(message):
    _, data = api_post(f"/instance/connect/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔄 Connect:\n{data}")

@bot.message_handler(commands=["restart"])
def restart(message):
    _, data = api_post(f"/instance/restart/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔁 Restart:\n{data}")

@bot.message_handler(commands=["qrcode"])
def qrcode_cmd(message):
    bot.send_message(message.chat.id, "⏳ Gerando QR...")
    code, data = api_get(f"/instance/qr/{EVO_INSTANCE_NAME}")

    if code != 200 or not data.get("qr"):
        bot.send_message(message.chat.id, "❌ QR não disponível.")
        return

    img = qrcode.make(data["qr"])
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    bot.send_photo(message.chat.id, bio, caption="📲 Escaneie!")

@bot.message_handler(commands=["enviar"])
def enviar(message):
    if not TEST_PHONE_NUMBER:
        bot.send_message(message.chat.id, "⚠ TEST_PHONE_NUMBER não configurado")
        return

    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": TEST_PHONE_NUMBER,
        "message": "Mensagem de teste via Evolution Free"
    }
    _, data = api_post("/message/sendText", payload)
    bot.send_message(message.chat.id, f"📨 {data}")

# ======================================================
# TRATAMENTO DE MÍDIA
# ======================================================
@bot.message_handler(commands=["enviar_imagem"])
def enviar_imagem(message):
    awaiting_action[message.chat.id] = "image"
    bot.send_message(message.chat.id, "📸 Envie a imagem agora.")

@bot.message_handler(commands=["enviar_audio"])
def enviar_audio(message):
    awaiting_action[message.chat.id] = "audio"
    bot.send_message(message.chat.id, "🎤 Envie o áudio agora.")

@bot.message_handler(commands=["enviar_doc"])
def enviar_doc(message):
    awaiting_action[message.chat.id] = "doc"
    bot.send_message(message.chat.id, "📄 Envie o documento agora.")

@bot.message_handler(content_types=["photo", "audio", "voice", "document"])
def process_file(message):
    action = awaiting_action.pop(message.chat.id, None)
    if not action:
        return

    info = bot.get_file(
        message.photo[-1].file_id if message.content_type == "photo"
        else message.document.file_id if message.content_type == "document"
        else message.audio.file_id if message.content_type == "audio"
        else message.voice.file_id
    )
    binfile = bot.download_file(info.file_path)

    files = {"file": ("file", binfile)}
    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": TEST_PHONE_NUMBER,
        "caption": "Arquivo via bot"
    }
    _, data = api_post("/message/sendMedia", payload, files)
    bot.send_message(message.chat.id, f"📨 {data}")

# ======================================================
# ANTI-409 POLLING
# ======================================================
def start_polling():
    with FileLock(LOCKFILE):
        logger.info("🔥 Polling iniciado sem duplicação (anti-409).")

        while True:
            try:
                # sempre remover webhook
                try:
                    bot.remove_webhook()
                except:
                    pass

                bot.infinity_polling(timeout=50, long_polling_timeout=50, skip_pending=True)

            except ApiTelegramException as e:
                if "409" in str(e):
                    logger.warning("⚠ 409 detectado. Removendo webhook e reiniciando...")
                    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
                    time.sleep(2)
                else:
                    logger.error(f"Erro Telegram: {e}")
                time.sleep(3)

            except Exception as e:
                logger.error(f"Erro geral: {e}")
                time.sleep(3)

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    logger.info("🚀 Iniciando bot Evolution Free...")
    start_polling()
