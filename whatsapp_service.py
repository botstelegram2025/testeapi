import httpx
import logging
import os

log = logging.getLogger("whatsapp_service")

class WhatsAppService:
    def __init__(self):
        self.API_URL = os.getenv("WHATSAPP_API_URL")
        if self.API_URL.endswith("/"):
            self.API_URL = self.API_URL[:-1]

        log.info(f"WhatsApp API inicializada: {self.API_URL}")

    # =============================
    # INSTÂNCIAS
    # =============================

    async def create_instance(self, instance_name: str):
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
        url = f"{self.API_URL}/instance/fetchInstances"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao listar instâncias: {e}")
            return {"status": False, "error": str(e)}

    # =============================
    # QR CODE
    # =============================

    async def get_qr(self, instance_name: str):
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

    async def connect(self, instance_name: str):
        url = f"{self.API_URL}/instance/start/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao conectar instância: {e}")
            return {"status": False, "error": str(e)}

    async def reconnect(self, instance_name: str):
        url = f"{self.API_URL}/instance/reconnect/{instance_name}"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url)
                return resp.json()
        except Exception as e:
            log.error(f"Erro ao reconectar instância: {e}")
            return {"status": False, "error": str(e)}

    async def delete_instance(self, instance_name: str):
        """(opcional — seu servidor não tem essa rota ainda)"""
        url = f"{self.API_URL}/instance/delete/{instance_name}"
        return {"status": False, "error": "Not implemented in server"}

    # =============================
    # ENVIO DE MENSAGENS
    # =============================

    async def send_text(self, instance_name: str, number: str, message: str):
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

# Instância global
whatsapp = WhatsAppService()

