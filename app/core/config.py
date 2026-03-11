from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "API Bridge Ecuador"
    VERSION: str = "1.0.0"
    
    # Seguridad JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # iDempiere 12
    IDEMPIERE_API_URL: str
    IDEMPIERE_API_TOKEN: Optional[str] = None

    class Config:
        # Pydantic buscará el archivo .env en la raíz
        env_file = ".env"
        env_file_encoding = 'utf-8'

# Instanciamos la configuración para importarla en toda la app
settings = Settings()