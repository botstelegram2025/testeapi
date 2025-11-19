#!/usr/bin/env python3
import os
import time
import logging
import requests
from io import BytesIO
import qrcode
import telebot
from telebot.apihelper import ApiTelegramException

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

# ======================================================
# LOCK NATIVO ANTI-409 (não usa filelock)
# ======================================================
LOCKFILE = "/tmp/polling.lock"

def acquire_lock():
    """Evita várias instâncias rodando ao mesmo tempo no Railway."""
    try:
        if os.path.exists(LOCKFILE):
            logger.warning("⚠ Outra instância detectada. Encerrando para evitar 409.")
            time.sleep(99999)
        with open(LOCKFILE, "w") as f:
            f.write("locked")
        logger.info("🔒 Lock adquirido — instância única garantida.")
    except:
        logger.error("❌ Não foi possível criar lock.")
        pass

def release_lock():
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)
        logger.info("🔓 Lock liberado.")

# ======================================================
# HTTP HELPERS
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
    except:
        return None, {"status": False, "error": "API offline ou erro de conexão"}

def api_post(path, payload=None, files=None):
    hdr = headers()
    try:
        if files:
            r = requests.post(EVO_API_URL + path, data=payload, files=files, headers=hdr)
        else:
            hdr["Content-Type"] = "application/json"
            r = requests.post(EVO_API_URL + path, json=payload, headers=hdr)
        return r.status_code, r.json()
    except:
        return None, {"status": False, "error": "Erro ao enviar dados"}

# ======================================================
# COMANDOS
# ======================================================
@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🤖 Evolution Free Bot\n\n"
        "/status\n"
        "/instancias\n"
        "/criar_instancia NOME\n"
        "/connect\n"
        "/restart\n"
        "/qrcode\n"
        "/enviar\n"
        "/enviar_imagem\n"
        "/enviar_audio\n"
        "/enviar_doc\n"
        "/botao\n"
        "/env"
    )

@bot.message_handler(commands=["env"])
def env(message):
    bot.send_message(
        message.chat.id,
        f"EVO_API_URL = {EVO_API_URL}\n"
        f"EVO_INSTANCE_NAME = {EVO_INSTANCE_NAME}\n"
        f"APIKEY SET = {bool(AUTHENTICATION_API_KEY)}\n"
        f"TEST_PHONE_NUMBER = {TEST_PHONE_NUMBER}"
    )

@bot.message_handler(commands=["status"])
def status(message):
    code, data = api_get("/health")
    bot.send_message(message.chat.id, f"🔍 {data}")

@bot.message_handler(commands=["instancias"])
def instancias(message):
    code, data = api_get("/instance/fetchInstances")
    if code == 200:
        lista = "\n".join(f"➡ {i}" for i in data.get("instances", []))
        if not lista:
            lista = "Nenhuma instância"
        bot.send_message(message.chat.id, lista)
    else:
        bot.send_message(message.chat.id, f"❌ {data}")

@bot.message_handler(commands=["criar_instancia"])
def criar(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "Use: /criar_instancia nome")
    nome = parts[1].strip()
    _, data = api_post("/instance/create", {"instanceName": nome})
    bot.send_message(message.chat.id, str(data))

@bot.message_handler(commands=["connect"])
def connect(message):
    _, data = api_post(f"/instance/connect/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, str(data))

@bot.message_handler(commands=["restart"])
def restart(message):
    _, data = api_post(f"/instance/restart/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, str(data))

@bot.message_handler(commands=["qrcode"])
def qr(message):
    bot.send_message(message.chat.id, "⏳ Gerando QR...")
    code, data = api_get(f"/instance/qr/{EVO_INSTANCE_NAME}")
    if code == 200 and data.get("qr"):
        img = qrcode.make(data["qr"])
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        bot.send_photo(message.chat.id, bio)
    else:
        bot.send_message(message.chat.id, "❌ QR não disponível.")

@bot.message_handler(commands=["enviar"])
def enviar(message):
    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": TEST_PHONE_NUMBER,
        "message": "Teste via EvolutionFree"
    }
    _, data = api_post("/message/sendText", payload)
    bot.send_message(message.chat.id, str(data))

# ======================================================
# POLLING COM ANTI-409
# ======================================================
def start_polling():
    acquire_lock()  # impede duplicação

    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=50, long_polling_timeout=50, skip_pending=True)

        except ApiTelegramException as e:
            if "409" in str(e):
                requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
                time.sleep(3)
            else:
                time.sleep(3)

        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    logger.info("🚀 Bot iniciado (Evolution-Free)")
    try:
        start_polling()
    finally:
        release_lock()
