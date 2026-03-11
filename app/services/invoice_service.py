from app.domain.schemas.invoice import InvoiceHeaderCreate, InvoiceLineCreate
from app.infrastructure.idempiere.client import IDempiereClient


class InvoiceService:
    def __init__(self):
        self.idempiere_client = IDempiereClient()

    async def process_draft_header(
        self, client_id: int, org_id: int, user_id: int, data: InvoiceHeaderCreate
    ) -> dict:
        print(f"Creando C_BPartner con RUC {data.document_number}...")
        bpartner_id = await self.idempiere_client.create_bpartner(
            ruc=data.document_number,
            name=data.client_name,
            ad_client_id=client_id,
            ad_org_id=org_id,
        )

        print(f"Cliente {bpartner_id} creado. Generando Dirección...")
        location_id = await self.idempiere_client.create_location(ad_org_id=org_id)
        bp_location_id = await self.idempiere_client.create_bpartner_location(
            c_bpartner_id=bpartner_id, c_location_id=location_id, ad_org_id=org_id
        )

        print(f"Dirección {bp_location_id} creada. Generando Factura (Draft)...")
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
            f"Enviando a iDempiere: Producto {data.m_product_id} x {data.qty} a Factura {invoice_id}"
        )

        # 1. Llamada HTTP real
        idempiere_line_response = await self.idempiere_client.create_invoice_line(
            c_invoice_id=invoice_id,
            m_product_id=data.m_product_id,
            qty=data.qty,
            ad_client_id=client_id,
            ad_org_id=org_id,
        )

        # 2. Extraemos los cálculos matemáticos y de impuestos que hizo iDempiere
        line_id = idempiere_line_response.get("id") or idempiere_line_response.get(
            "C_InvoiceLine_ID"
        )
        line_net_amt = idempiere_line_response.get("LineNetAmt", 0)
        tax_amt = idempiere_line_response.get("TaxAmt", 0)
        line_total_amt = line_net_amt + tax_amt

        return {
            "invoice_line_id": line_id,
            "product_name": f"Producto ID {data.m_product_id}",
            "qty": data.qty,
            "line_net_amt": line_net_amt,
            "tax_amt": tax_amt,
            "line_total_amt": line_total_amt,
            "invoice_grand_total": line_total_amt,
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
