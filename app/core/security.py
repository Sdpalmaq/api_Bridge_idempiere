from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from app.core.config import settings

security_scheme = HTTPBearer()


class UserContext(BaseModel):
    user_id: int
    ad_client_id: int
    ad_org_id: int
    role: str
    subscription_tier: str


async def get_current_user_context(
    token: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> UserContext:
    try:
        # Usamos el SECRET_KEY que viene validado del .env
        payload = jwt.decode(
            token.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        return UserContext(
            user_id=payload.get("user_id"),
            ad_client_id=payload.get("ad_client_id"),
            ad_org_id=payload.get("ad_org_id"),
            role=payload.get("role"),
            subscription_tier=payload.get("subscription_tier"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
