import httpx
from fastapi import HTTPException, status
from app.core.config import settings


class IDempiereClient:
    """
    Cliente HTTP Asíncrono para comunicarse con los Web Services REST de iDempiere 12.
    """

    def __init__(self):
        self.base_url = settings.IDEMPIERE_API_URL
        # iDempiere espera autenticación en los headers
        self.headers = {
            "Authorization": f"Bearer {settings.IDEMPIERE_API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.timeout = 15.0

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """Método privado genérico para hacer peticiones POST a iDempiere"""
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.headers, timeout=self.timeout
                )
                response.raise_for_status()  # Lanza error si iDempiere devuelve 400 o 500
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"Error de iDempiere: {e.response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Rechazado por el ERP: {e.response.text}",
                )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No se pudo conectar con el servidor de iDempiere.",
                )

                # -----------------------------------------------------------------

                # Añade este método justo debajo de _post:

    async def _put(self, endpoint: str, payload: dict) -> dict:
        """Método privado para actualizar registros existentes en iDempiere"""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            try:
                # Usamos client.put en lugar de post
                response = await client.put(
                    url, json=payload, headers=self.headers, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"Error de iDempiere: {e.response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error ERP: {e.response.text}",
                )
            except httpx.RequestError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Error de conexión.",
                )

    # MÉTODOS DE AUTENTICACIÓN
    # -----------------------------------------------------------------
    async def login(self, username: str, password: str) -> dict:
        """
        Devuelve el contexto del usuario.
        Mantenemos este mock temporalmente para no bloquear la prueba de las facturas.
        """
        if username == "admin_empresa" and password == "sri2026":
            return {
                "token": "idempiere_native_token_xyz",
                "userId": 100,  # AD_User_ID
                # ⚠️ MUY IMPORTANTE PARA TU PRUEBA REAL:
                # Cambia este 1000000 por el AD_Client_ID real de la empresa en tu iDempiere
                "clientId": 11,
                # Cambia este 0 por el AD_Org_ID real si tu iDempiere lo exige
                "orgId": 11,
                "roleId": 102,
                "roleName": "Admin",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales rechazadas por iDempiere.",
            )

    # -----------------------------------------------------------------
    # MÉTODOS DE NEGOCIO (Mapeo DTO -> iDempiere)
    # -----------------------------------------------------------------

    async def create_bpartner(
        self, ruc: str, name: str, ad_client_id: int, ad_org_id: int
    ) -> int:
        """Paso 1: Crea el Cliente (Omitimos Value y AD_Client_ID por seguridad)"""
        payload = {"TaxID": ruc, "Name": name, "IsCustomer": "Y"}
        response = await self._post("/models/c_bpartner", payload)
        return response.get("id") or response.get("C_BPartner_ID")

    async def create_location(self, ad_org_id: int) -> int:
        """Paso 2: Crea la dirección física (C_Location)"""
        payload = {
            "AD_Org_ID": ad_org_id,
            "Address1": "Dirección no provista",
            "City": "Ecuador",
            "C_Country_ID": 170,  # ID estándar para Ecuador
        }
        response = await self._post("/models/c_location", payload)
        return response.get("id") or response.get("C_Location_ID")

    async def create_bpartner_location(
        self, c_bpartner_id: int, c_location_id: int, ad_org_id: int
    ) -> int:
        """Paso 3: Une el Cliente con la Dirección física"""
        payload = {
            "AD_Org_ID": ad_org_id,
            "C_BPartner_ID": c_bpartner_id,
            "C_Location_ID": c_location_id,
            "Name": "Dirección Matriz",
        }
        response = await self._post("/models/c_bpartner_location", payload)
        return response.get("id") or response.get("C_BPartner_Location_ID")

    async def create_invoice_header(
        self,
        c_bpartner_id: int,
        c_bpartner_location_id: int,
        ad_client_id: int,
        ad_org_id: int,
    ) -> int:
        """Paso 4: Crea la cabecera de la factura en borrador"""
        payload = {
            "AD_Org_ID": ad_org_id,
            "C_BPartner_ID": c_bpartner_id,
            "C_BPartner_Location_ID": c_bpartner_location_id,
            # ⚠️ CAMBIA ESTE ID POR EL DE TU FACTURA SRI:
            "C_DocTypeTarget_ID": 116,
            "IsSOTrx": "Y",
            "DocStatus": "DR",
        }
        response = await self._post("/models/c_invoice", payload)
        return response.get("id") or response.get("C_Invoice_ID")

    async def create_invoice_line(
        self,
        c_invoice_id: int,
        m_product_id: int,
        qty: float,
        ad_client_id: int,
        ad_org_id: int,
    ) -> dict:
        """Paso 5: Inserta una Línea de Factura"""
        payload = {
            "AD_Org_ID": ad_org_id,
            "C_Invoice_ID": c_invoice_id,
            "M_Product_ID": m_product_id,
            "QtyEntered": qty,
            "QtyInvoiced": qty,
        }
        response = await self._post("/models/c_invoiceline", payload)
        return response

    async def complete_invoice(self, c_invoice_id: int) -> dict:
        """
        Ejecuta la acción de Completar (CO) en la factura.
        Al hacer esto, iDempiere dispara la Facturación Electrónica al SRI.
        """
        payload = {
            "doc-action": "CO"
        }
        # En la API de iDempiere, actualizamos apuntando al ID en la URL
        response = await self._put(f"/models/c_invoice/{c_invoice_id}", payload)
        return response
