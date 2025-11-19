#!/usr/bin/env python3
import os
import time
import logging
import requests
from io import BytesIO
import qrcode
import telebot
from telebot.apihelper import ApiTelegramException

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("evo-bot")

# -----------------------
# Environment / Config
# -----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
EVO_API_URL = os.getenv("EVO_API_URL")          # <-- must be set
AUTHENTICATION_API_KEY = os.getenv("AUTHENTICATION_API_KEY")
EVO_INSTANCE_NAME = os.getenv("EVO_INSTANCE_NAME") or "defaultbot"
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER")

if not BOT_TOKEN:
    logger.critical("BOT_TOKEN not set. Exiting.")
    raise SystemExit("BOT_TOKEN not set")

if not EVO_API_URL:
    logger.critical("EVO_API_URL not set. Exiting.")
    raise SystemExit("EVO_API_URL not set")

if not AUTHENTICATION_API_KEY:
    logger.warning("AUTHENTICATION_API_KEY not set. Protected routes will likely return Unauthorized.")

# ensure base url doesn't end with slash
EVO_API_URL = EVO_API_URL.rstrip("/")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# awaiting actions per chat (simple state machine)
# values: None or "image"|"audio"|"document"
awaiting_action = {}

# -----------------------
# Helper: API requests with apikey header
# -----------------------
def get_headers():
    headers = {}
    if AUTHENTICATION_API_KEY:
        headers["apikey"] = AUTHENTICATION_API_KEY
    return headers

def api_get(path):
    url = f"{EVO_API_URL}{path}"
    logger.debug(f"[GET] {url}")
    try:
        r = requests.get(url, headers=get_headers(), timeout=20)
        # attempt json or error
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"status": False, "text": r.text}
    except Exception as e:
        logger.exception("api_get error")
        return None, {"status": False, "error": str(e)}

def api_post(path, payload=None, files=None):
    url = f"{EVO_API_URL}{path}"
    logger.debug(f"[POST] {url} | payload keys: {list(payload.keys()) if payload else None} | files: {bool(files)}")
    try:
        headers = get_headers()
        if files:
            # files is dict for requests.files, payload in data
            r = requests.post(url, data=payload, files=files, headers=headers, timeout=60)
        else:
            headers["Content-Type"] = "application/json"
            r = requests.post(url, json=payload, headers=headers, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"status": False, "text": r.text}
    except Exception as e:
        logger.exception("api_post error")
        return None, {"status": False, "error": str(e)}

# -----------------------
# Bot Commands
# -----------------------
@bot.message_handler(commands=["start","help"])
def cmd_start(message):
    txt = (
        "🤖 Evolution API FREE Bot\n\n"
        "/status - Verificar API\n"
        "/qrcode - Gerar QR da instância\n"
        "/enviar - Enviar texto teste\n"
        "/instancias - Listar instâncias\n"
        "/criar_instancia <nome> - Criar instância\n"
        "/connect - Iniciar/Conectar instância\n"
        "/restart - Reiniciar instância\n"
        "/enviar_imagem - Enviar imagem (faça upload após o comando)\n"
        "/enviar_audio - Enviar áudio (faça upload após o comando)\n"
        "/enviar_doc - Enviar documento (faça upload após o comando)\n"
        "/botao - Enviar botões interativos\n"
        "/env - Mostrar variáveis do bot (seguras)"
    )
    bot.send_message(message.chat.id, txt)

@bot.message_handler(commands=["env"])
def cmd_env(message):
    safe = (
        f"EVO_API_URL = {EVO_API_URL}\n"
        f"EVO_INSTANCE_NAME = {EVO_INSTANCE_NAME}\n"
        f"AUTHENTICATION_API_KEY = {'SET' if AUTHENTICATION_API_KEY else 'NOT SET'}\n"
        f"TEST_PHONE_NUMBER = {TEST_PHONE_NUMBER}"
    )
    bot.send_message(message.chat.id, safe)

@bot.message_handler(commands=["status"])
def cmd_status(message):
    code, data = api_get("/health")
    if code == 200:
        bot.send_message(message.chat.id, f"✅ API Online!\n{data}")
    elif code is None:
        bot.send_message(message.chat.id, f"❌ Erro: {data.get('error')}")
    else:
        bot.send_message(message.chat.id, f"⚠ Resposta: {data}")

@bot.message_handler(commands=["instancias"])
def cmd_instancias(message):
    code, data = api_get("/instance/fetchInstances")
    if code == 200 and isinstance(data, dict) and data.get("instances") is not None:
        insts = data.get("instances", [])
        if not insts:
            bot.send_message(message.chat.id, "📭 Nenhuma instância criada.")
            return
        texto = "\n".join(f"➡️ {i}" for i in insts)
        bot.send_message(message.chat.id, f"📌 Instâncias:\n{texto}")
    else:
        bot.send_message(message.chat.id, f"❌ Erro ao listar instâncias: {data}")

@bot.message_handler(commands=["criar_instancia"])
def cmd_criar_instancia(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "⚠ Use: /criar_instancia nome_da_instancia")
        return
    nome = parts[1].strip()
    payload = {"instanceName": nome}
    code, data = api_post("/instance/create", payload)
    bot.send_message(message.chat.id, f"📌 Resultado:\n{data}")

@bot.message_handler(commands=["connect"])
def cmd_connect(message):
    # uses EVO_INSTANCE_NAME env var
    code, data = api_post(f"/instance/connect/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔄 Connect -> {data}")

@bot.message_handler(commands=["restart"])
def cmd_restart(message):
    code, data = api_post(f"/instance/restart/{EVO_INSTANCE_NAME}")
    bot.send_message(message.chat.id, f"🔁 Restart -> {data}")

@bot.message_handler(commands=["qrcode"])
def cmd_qrcode(message):
    bot.send_message(message.chat.id, "⏳ Gerando QR...")
    code, data = api_get(f"/instance/qr/{EVO_INSTANCE_NAME}")
    if code == 200 and data.get("qr"):
        qr_text = data.get("qr")
        img = qrcode.make(qr_text)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buf.name = "qrcode.png"
        bot.send_photo(message.chat.id, buf, caption="📲 Escaneie para conectar!")
    elif code == 404:
        bot.send_message(message.chat.id, "❌ QR ainda não disponível. A instância pode estar desconectada ou carregando.")
    else:
        bot.send_message(message.chat.id, f"❌ Erro ao obter QR: {data}")

@bot.message_handler(commands=["enviar"])
def cmd_enviar(message):
    if not TEST_PHONE_NUMBER:
        bot.send_message(message.chat.id, "⚠ TEST_PHONE_NUMBER não configurado")
        return
    payload = {"instanceName": EVO_INSTANCE_NAME, "to": TEST_PHONE_NUMBER, "message": "Mensagem de teste via Evolution API Free"}
    code, data = api_post("/message/sendText", payload)
    bot.send_message(message.chat.id, f"📨 Resultado: {data}")

# -----------------------
# Media upload flow using awaiting_action dict (no nested handlers)
# -----------------------
@bot.message_handler(commands=["enviar_imagem"])
def cmd_enviar_imagem(message):
    awaiting_action[message.chat.id] = "image"
    bot.send_message(message.chat.id, "📸 Envie a imagem agora (como foto).")

@bot.message_handler(commands=["enviar_audio"])
def cmd_enviar_audio_cmd(message):
    awaiting_action[message.chat.id] = "audio"
    bot.send_message(message.chat.id, "🎤 Envie o áudio agora (voice ou audio).")

@bot.message_handler(commands=["enviar_doc"])
def cmd_enviar_doc_cmd(message):
    awaiting_action[message.chat.id] = "document"
    bot.send_message(message.chat.id, "📄 Envie o documento agora (file).")

@bot.message_handler(content_types=["photo","audio","voice","document"])
def handle_media(message):
    action = awaiting_action.get(message.chat.id)
    if not action:
        # nothing expected, ignore or inform
        return

    # Reset awaiting action immediately to avoid double processing
    awaiting_action.pop(message.chat.id, None)

    try:
        if action == "image" and message.content_type == "photo":
            file_id = message.photo[-1].file_id
            handle_file_and_send(message, file_id, filename="image.jpg", mime="image/jpeg")
        elif action == "audio" and message.content_type in ("audio","voice"):
            # prefer audio then voice
            if message.content_type == "audio":
                file_id = message.audio.file_id
                original_name = getattr(message.audio, "file_name", "audio.ogg")
                mime = getattr(message.audio, "mime_type", "audio/ogg")
            else:
                file_id = message.voice.file_id
                original_name = "voice.ogg"
                mime = "audio/ogg"
            handle_file_and_send(message, file_id, filename=original_name, mime=mime)
        elif action == "document" and message.content_type == "document":
            file_id = message.document.file_id
            original_name = message.document.file_name or "file"
            mime = message.document.mime_type or "application/octet-stream"
            handle_file_and_send(message, file_id, filename=original_name, mime=mime)
        else:
            bot.send_message(message.chat.id, "❌ Tipo de arquivo inesperado. Por favor envie o tipo correto.")
    except Exception as e:
        logger.exception("Erro processando mídia")
        bot.send_message(message.chat.id, f"❌ Erro ao processar arquivo: {e}")

def handle_file_and_send(message, file_id, filename="file", mime="application/octet-stream"):
    # download file from Telegram
    f_info = bot.get_file(file_id)
    downloaded = bot.download_file(f_info.file_path)
    # prepare multipart
    payload = {"instanceName": EVO_INSTANCE_NAME, "to": TEST_PHONE_NUMBER, "caption": f"Enviado via bot ({filename})"}
    files = {"file": (filename, downloaded, mime)}
    code, data = api_post("/message/sendMedia", payload, files=files)
    bot.send_message(message.chat.id, f"📨 Resultado: {data}")

# -----------------------
# Buttons (interactive)
# -----------------------
@bot.message_handler(commands=["botao"])
def cmd_botao(message):
    if not TEST_PHONE_NUMBER:
        bot.send_message(message.chat.id, "⚠ TEST_PHONE_NUMBER não configurado")
        return
    payload = {
        "instanceName": EVO_INSTANCE_NAME,
        "to": TEST_PHONE_NUMBER,
        "message": "Escolha uma opção:",
        "buttons": [
            {"id": "sim", "text": "Sim 👍"},
            {"id": "nao", "text": "Não 👎"}
        ]
    }
    code, data = api_post("/message/sendText", payload)
    bot.send_message(message.chat.id, f"📨 Resultado: {data}")

# -----------------------
# Robust polling with anti-409 handling
# -----------------------
def start_polling():
    backoff = 1
    while True:
        try:
            logger.info("Starting polling...")
            # ensure webhook removed
            try:
                bot.remove_webhook()
            except Exception:
                pass
            bot.infinity_polling(timeout=50, long_polling_timeout=50, skip_pending=True)
        except ApiTelegramException as e:
            # handle 409 - attempt to delete webhook and retry
            msg = str(e)
            logger.error(f"Polling exception: {msg}")
            if "409" in msg or "Conflict" in msg:
                # call deleteWebhook to clear server-side handlers
                try:
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                    requests.get(url, timeout=10)
                    logger.info("deleteWebhook called to clear conflicts.")
                except Exception as ex:
                    logger.exception("Failed to call deleteWebhook")
                # wait and retry
                time.sleep(backoff)
                backoff = min(60, backoff * 2)
                continue
            else:
                # unexpected telegram api error
                time.sleep(backoff)
                backoff = min(60, backoff * 2)
                continue
        except Exception as e:
            logger.exception("Unexpected polling error")
            time.sleep(backoff)
            backoff = min(60, backoff * 2)
            continue

if __name__ == "__main__":
    logger.info("Booting bot...")
    try:
        start_polling()
    except KeyboardInterrupt:
        logger.info("Stopping (KeyboardInterrupt)")
