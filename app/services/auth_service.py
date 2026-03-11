from datetime import datetime, timedelta
import jwt
from app.core.config import settings
from app.infrastructure.idempiere.client import IDempiereClient


class AuthService:
    def __init__(self):
        # Inyectamos el cliente de iDempiere
        self.idempiere_client = IDempiereClient()

    async def authenticate_user_and_create_token(
        self, username: str, password: str
    ) -> str:
        """
        1. Valida con iDempiere.
        2. Determina el Tier de Suscripción de la empresa.
        3. Empaqueta todo en un JWT y lo devuelve.
        """
        # 1. Llamada a la capa de Infraestructura
        idempiere_response = await self.idempiere_client.login(username, password)

        # 2. Lógica de Negocio: Obtener el Tier de suscripción
        # En el futuro, esto consultará nuestra BD del BFF o una tabla en iDempiere
        # Por ahora, simulamos que la empresa 1000000 tiene plan "Pro"
        client_id = idempiere_response["clientId"]
        tier = "Pro" if client_id == 1000000 else "Básico"

        # 3. Armar el payload para nuestro JWT (El UserContext que ya conocemos)
        payload = {
            "sub": username,
            "user_id": idempiere_response["userId"],
            "ad_client_id": client_id,
            "ad_org_id": idempiere_response["orgId"],
            "role": idempiere_response["roleName"],
            "subscription_tier": tier,
            "exp": datetime.utcnow()
            + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        }

        # 4. Firmar el token
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return token
