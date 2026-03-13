from app.domain.schemas.invoice import InvoiceHeaderCreate, InvoiceLineCreate
from app.infrastructure.idempiere.client import IDempiereClient


class InvoiceService:
    def __init__(self):
        self.idempiere_client = IDempiereClient()

    async def process_draft_header(
        self, client_id: int, org_id: int, user_id: int, data: InvoiceHeaderCreate
    ) -> dict:

        print(f"🔍 Consultando a iDempiere: ¿Existe el RUC {data.document_number}?")

        # 1. BUSCAR ANTES DE CREAR
        bpartner_id = await self.idempiere_client.get_bpartner_by_ruc(
            ruc=data.document_number
        )

        if bpartner_id:
            print(
                f"✅ ¡Cliente encontrado! C_BPartner_ID: {bpartner_id}. Reutilizando registro."
            )
        else:
            print(
                f"⚠️ Cliente nuevo. Creando C_BPartner con RUC {data.document_number}..."
            )
            bpartner_id = await self.idempiere_client.create_bpartner(
                ruc=data.document_number,
                name=data.client_name,
                ad_client_id=client_id,
                ad_org_id=org_id,
            )

        # 2. Gestión de la Dirección (Location)
        # Nota arquitectónica: Para ser puristas, aquí también deberíamos buscar
        # si el bpartner_id ya tiene una dirección atada (C_BPartner_Location).
        # Para no bloquear el MVP, generamos una por defecto si falla.
        print(f"Generando/Asignando Dirección...")
        location_id = await self.idempiere_client.create_location(ad_org_id=org_id)
        bp_location_id = await self.idempiere_client.create_bpartner_location(
            c_bpartner_id=bpartner_id, c_location_id=location_id, ad_org_id=org_id
        )

        # 3. Creación del Borrador de Factura
        print(f"Generando Factura (Draft) para BPartner {bpartner_id}...")
        invoice_id = await self.idempiere_client.create_invoice_header(
            c_bpartner_id=bpartner_id,
            c_bpartner_location_id=bp_location_id,
            ad_client_id=client_id,
            ad_org_id=org_id,
        )

        return {
            "invoice_id": invoice_id,
            "bpartner_id": bpartner_id,
            "client_name": data.client_name,
            "status": "Draft",
        }

    # 👇 AQUÍ QUITAMOS EL MOCK Y PONEMOS LA CONEXIÓN REAL
    async def add_line_to_invoice(
        self, invoice_id: int, client_id: int, org_id: int, data: InvoiceLineCreate
    ) -> dict:
        print(
            f"➕ Insertando Producto {data.m_product_id} x {data.qty} en Factura {invoice_id}"
        )

        # 1. Insertamos la línea (iDempiere calculará el IVA por debajo)
        idempiere_line_response = await self.idempiere_client.create_invoice_line(
            c_invoice_id=invoice_id,
            m_product_id=data.m_product_id,
            qty=data.qty,
            ad_client_id=client_id,
            ad_org_id=org_id,
        )

        # 2. Consultamos la cabecera actualizada para obtener el Total Real (GrandTotal)
        updated_invoice = await self.idempiere_client.get_invoice(
            c_invoice_id=invoice_id
        )

        # Extraemos los totales con seguridad
        line_id = idempiere_line_response.get("id") or idempiere_line_response.get(
            "C_InvoiceLine_ID"
        )
        grand_total = updated_invoice.get("GrandTotal", 0.0)
        total_lines = updated_invoice.get("TotalLines", 0.0)  # Subtotal sin impuestos

        return {
            "invoice_line_id": line_id,
            "product_id": data.m_product_id,
            "qty": data.qty,
            "subtotal": total_lines,
            "invoice_grand_total": grand_total,  # Este es el que le importa al cliente
        }

    async def complete_invoice(self, invoice_id: int) -> dict:
        print(f"Enviando orden de Completar (CO) para Factura {invoice_id}...")
        response = await self.idempiere_client.complete_invoice(c_invoice_id=invoice_id)

        doc_status = response.get("DocStatus", "Unknown")
        document_no = response.get("DocumentNo", "Borrador")

        return {
            "invoice_id": invoice_id,
            "document_no": document_no,
            "status": doc_status,
        }

    async def search_products(self, client_id: int, query: str = None) -> list:
        """Obtiene y formatea los productos para el SDUI"""
        print(f"📦 Consultando catálogo para tenant {client_id} | Búsqueda: '{query}'")
        return await self.idempiere_client.get_products(
            ad_client_id=client_id, search_query=query
        )

    async def get_invoice_list(self, client_id: int, org_id: int) -> list:
        """Obtiene y formatea las facturas para el SDUI."""
        print(f"📋 Consultando facturas del tenant {client_id}...")
        return await self.idempiere_client.get_invoices(
            ad_client_id=client_id,
            ad_org_id=org_id,
        )

    async def get_invoice_detail(self, invoice_id: int) -> dict:
        """Obtiene cabecera + líneas de una factura."""
        print(f"🔍 Consultando detalle de factura {invoice_id}...")
        cabecera = await self.idempiere_client.get_invoice(c_invoice_id=invoice_id)
        lineas = await self.idempiere_client.get_invoice_lines(c_invoice_id=invoice_id)

        # 👇 Agrega esto temporalmente
        print(f"📋 Cabecera: {cabecera}")
        print(f"📋 Líneas encontradas: {len(lineas)}")
        for l in lineas:
            print(f"   → Línea: {l}")

        return {"header": cabecera, "lines": lineas}
