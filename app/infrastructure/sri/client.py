# app/infrastructure/sri/client.py
import httpx
from fastapi import HTTPException, status


class SRIClient:
    """
    Cliente para consultar el RUC/Cédula directamente al SRI Ecuador.
    No requiere autenticación — es el servicio público de consulta.
    """

    def __init__(self):
        self.base_url = (
            "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest"
        )
        self.timeout = 10.0

    async def consultar_ruc(self, ruc: str) -> dict | None:
        """
        Consulta el RUC al SRI y devuelve los datos del contribuyente.
        Retorna None si el RUC no existe o no está activo.
        """
        # El SRI tiene dos endpoints según el tipo de documento
        if len(ruc) == 13:
            endpoint = (
                f"/ContibuYente/existeBuscarContribuyentePorNumeroRuc?numRuc={ruc}"
            )
        elif len(ruc) == 10:
            endpoint = (
                f"/ContibuYente/existeBuscarContribuyentePorNumeroRuc?numRuc={ruc}"
            )
        else:
            return None

        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=self.timeout)

                if response.status_code == 200:
                    data = response.json()
                    # El SRI devuelve null si no encuentra el RUC
                    if not data:
                        return None
                    return self._normalizar(data)
                return None

            except httpx.RequestError:
                # Si el SRI no responde, no bloqueamos la facturación
                # simplemente devolvemos None y el usuario escribe el nombre
                return None

    def _normalizar(self, data: dict) -> dict:
        """
        El SRI devuelve campos con nombres poco intuitivos.
        Los normalizamos a algo legible.
        """
        # Para RUC de persona jurídica (empresa)
        razon_social = (
            data.get("razonSocial")
            or data.get("nombreComercial")
            or
            # Para cédula (persona natural): nombre + apellido
            f"{data.get('nombreCompleto', '')}".strip()
        )

        return {
            "ruc": data.get("numRuc", ""),
            "razon_social": razon_social,
            "tipo_contribuyente": data.get("tipoContribuyente", ""),
            "estado": data.get("estadoContribuyenteRuc", ""),
            "activo": data.get("estadoContribuyenteRuc") == "ACTIVO",
        }
