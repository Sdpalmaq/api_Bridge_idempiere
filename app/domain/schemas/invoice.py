# app/domain/schemas/invoice.py
from pydantic import BaseModel, Field, constr


class InvoiceHeaderCreate(BaseModel):
    """
    Este modelo debe coincidir EXACTAMENTE con los 'id' de los componentes
    de texto y selectores que enviamos en el JSON SDUI.
    """

    doc_type: str = Field(..., description="Tipo de documento (ruc, cedula, pasaporte)")
    document_number: str = Field(
        ..., description="Número de identificación del cliente"
    )
    client_name: str = Field(..., description="Razón social o nombres completos")

    # Podríamos agregar validaciones extra en el backend como doble seguridad,
    # aunque Flutter ya haya validado el Regex en el móvil.



class InvoiceLineCreate(BaseModel):
    m_product_id: int = Field(..., description="ID interno del producto en iDempiere")
    qty: float = Field(default=1.0, description="Cantidad a facturar")
