# app/api/v1/endpoints/sri.py
from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_user_context, UserContext
from app.infrastructure.sri.client import SRIClient

router = APIRouter()
sri_client = SRIClient()


@router.get("/consultar-ruc", summary="Consultar RUC/Cédula al SRI")
async def consultar_ruc(
    ruc: str = Query(..., description="RUC o cédula a consultar"),
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Consulta el RUC al SRI Ecuador y devuelve el nombre del contribuyente.
    Flutter llama a este endpoint cuando el usuario termina de escribir el RUC.
    """
    print(f"🏛️ Consultando RUC {ruc} al SRI...")

    resultado = await sri_client.consultar_ruc(ruc)

    if not resultado:
        return {
            "encontrado": False,
            "mensaje": "RUC no encontrado en el SRI o servicio no disponible",
            "datos": None,
        }

    if not resultado["activo"]:
        return {
            "encontrado": True,
            "activo": False,
            "mensaje": f"RUC encontrado pero estado: {resultado['estado']}",
            "datos": resultado,
        }

    print(f"✅ RUC encontrado: {resultado['razon_social']}")
    return {
        "encontrado": True,
        "activo": True,
        "mensaje": "Contribuyente activo",
        "datos": resultado,
    }
