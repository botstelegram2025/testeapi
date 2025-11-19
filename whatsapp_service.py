import httpx
import logging
import os

log = logging.getLogger("whatsapp_service")

class WhatsAppService:
    def __init__(self):
        self.API_URL = os.getenv("WHATSAPP_API_URL")  # exemplo: https://meu-projeto.up.railway.app
        if self.API_URL.endswith("/"):
            self.API_URL = self.API_URL[:-1]

        log.info(f"WhatsApp API inicializada: {self.API_URL}")

    # =============================
    # INSTÂNCIAS
    # =============================

    async def create_instance(self, instance_name: str):
        """Cria uma nova instância Baileys"""
        url = f"{self.API_URL}/instance/create"
        data = {"instanceName": instance_name}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url, json=data)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao criar instância: {e}")
            return {"status": False, "error": str(e)}

    async def fetch_instances(self):
        """Retorna todas as instâncias ativas"""
        url = f"{self.API_URL}/instance/fetchInstances"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao listar instâncias: {e}")
            return {"status": False, "error": str(e)}

    # =============================
    # STATUS & QR CODE
    # =============================

    async def get_status(self, instance_name: str):
        """Obtém o estado da instância (open, close, connecting, etc.)"""
        url = f"{self.API_URL}/instance/status/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao obter status: {e}")
            return {"status": False, "state": "error", "error": str(e)}

    async def get_qr(self, instance_name: str):
        """Obtém o QR code atual da instância"""
        url = f"{self.API_URL}/instance/qr/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                data = resp.json()

                if data.get("status") and data.get("qr"):
                    return {"success": True, "qr": data["qr"]}

                return {"success": False, "qr": None}
        except Exception as e:
            log.error(f"Erro ao obter QR: {e}")
            return {"success": False, "error": str(e)}

    # =============================
    # CONTROLE DA SESSÃO
    # =============================

    async def reconnect(self, instance_name: str):
        """Força reconexão da instância"""
        url = f"{self.API_URL}/instance/restart/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao reconectar: {e}")
            return {"status": False, "error": str(e)}

    async def connect(self, instance_name: str):
        """Ativa a conexão da instância"""
        url = f"{self.API_URL}/instance/connect/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao conectar instância: {e}")
            return {"status": False, "error": str(e)}

    async def delete_instance(self, instance_name: str):
        """Remove uma instância"""
        url = f"{self.API_URL}/instance/delete/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.delete(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao deletar instância: {e}")
            return {"status": False, "error": str(e)}

    # =============================
    # ENVIO DE MENSAGENS
    # =============================

    async def send_text(self, instance_name: str, number: str, message: str):
        """Envia mensagem de texto"""
        url = f"{self.API_URL}/message/sendText"

        payload = {
            "instanceName": instance_name,
            "to": number,
            "message": message,
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url, json=payload)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao enviar mensagem: {e}")
            return {"status": False, "error": str(e)}

    # =============================
    # FUNÇÕES DE ALTO NÍVEL (para Telegram Bot)
    # =============================

    async def ensure_instance(self, instance_name: str):
        """Se a instância não existir → cria."""
        instances = await self.fetch_instances()

        if not instances.get("instances"):
            await self.create_instance(instance_name)
            return True

        if instance_name not in instances["instances"]:
            await self.create_instance(instance_name)
            return True

        return True

    async def get_connection_state(self, instance_name: str):
        """Retorna estado e tenta recuperar fallback"""
        status = await self.get_status(instance_name)

        if not status.get("status"):
            return {"connected": False, "state": "error"}

        state = status.get("state", "unknown")

        return {
            "connected": state == "open",
            "state": state
        }

    async def get_qr_auto(self, instance_name: str):
        """Se a sessão estiver desconectada → gera QR"""
        status = await self.get_connection_state(instance_name)

        if status["connected"]:
            return {"success": True, "connected": True, "qr": None}

        qr = await self.get_qr(instance_name)
        return {
            "success": True,
            "connected": False,
            "qr": qr.get("qr")
        }


# Instância global
whatsapp = WhatsAppService()
