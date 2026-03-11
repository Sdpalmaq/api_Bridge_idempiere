from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.services.auth_service import AuthService

router = APIRouter()

# Instanciamos el servicio (En el futuro usaremos inyección de dependencias avanzada)
auth_service = AuthService()


@router.post("/login", summary="Obtener Token JWT desde iDempiere")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Toma las credenciales, llama al servicio de autenticación y devuelve el JWT.
    """
    # Toda la lógica compleja y llamadas a iDempiere suceden dentro de esta línea
    token = await auth_service.authenticate_user_and_create_token(
        username=form_data.username, password=form_data.password
    )

    return {"access_token": token, "token_type": "bearer"}
