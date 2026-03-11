from fastapi import APIRouter, Depends
from app.core.security import get_current_user_context, UserContext
from app.domain.sdui.components import (
    ScreenLayout,
    HeaderComponent,
    TextInputComponent,
    InputValidation,
    SelectComponent,
    ButtonComponent,
    UIAction,
    ListItemComponent,
)
from app.domain.schemas.invoice import InvoiceHeaderCreate
from app.services.invoice_service import InvoiceService
from app.domain.schemas.invoice import InvoiceLineCreate


router = APIRouter()
# Instanciamos el servicio
invoice_service = InvoiceService()


@router.get(
    "/sdui/create", response_model=ScreenLayout, summary="UI para Crear Factura"
)
async def get_invoice_create_ui(
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Devuelve el formulario dinámico para crear una factura.
    Incluye validaciones nativas para Ecuador (Cédula/RUC).
    """

    # Expresiones regulares del SRI
    REGEX_RUC_CEDULA = r"^\d{10,13}$"  # Básico: de 10 a 13 números

    components = [
        HeaderComponent(
            type="header",
            title="Nueva Factura",
            subtitle="Complete los datos del cliente",
        ),
        # Selector de Tipo de Documento
        SelectComponent(
            type="select",
            id="doc_type",
            label="Tipo de Identificación",
            options=[
                {"label": "RUC", "value": "ruc"},
                {"label": "Cédula", "value": "cedula"},
                {"label": "Pasaporte", "value": "pasaporte"},
            ],
        ),
        # Input con validación Regex inyectada desde el Backend
        TextInputComponent(
            type="text_input",
            id="document_number",
            label="Número de Documento",
            placeholder="Ej: 1712345678001",
            keyboard_type="number",
            is_required=True,
            validation=InputValidation(
                regex=REGEX_RUC_CEDULA,
                error_message="El documento debe tener 10 o 13 dígitos numéricos.",
            ),
        ),
        TextInputComponent(
            type="text_input",
            id="client_name",
            label="Razón Social / Nombres",
            placeholder="Ingrese el nombre completo",
            keyboard_type="text",
            is_required=True,
        ),
        # Botón para enviar el formulario a nuestro BFF
        ButtonComponent(
            type="button",
            label="Continuar al Detalle",
            style="primary",
            action=UIAction(
                type="api_call",  # Ya no es 'navigate', ahora es llamar a una API
                target="/api/v1/invoices/draft",  # Aquí enviaremos los datos luego
                params={"action": "save_header"},
            ),
        ),
    ]

    return ScreenLayout(screen_name="Formulario Nueva Factura", layout=components)


@router.post(
    "/draft", summary="Guardar Cabecera y Validar Cliente", tags=["Facturación Móvil"]
)
async def create_invoice_draft(
    payload: InvoiceHeaderCreate,
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Recibe los datos del formulario móvil.
    Verifica en iDempiere si el C_BPartner existe (o lo crea) y genera un C_Invoice en borrador.
    """

    # Delegamos toda la lógica de negocio al servicio, pasándole el contexto del usuario
    result = await invoice_service.process_draft_header(
        client_id=current_user.ad_client_id,
        org_id=current_user.ad_org_id,
        user_id=current_user.user_id,
        data=payload,
    )

    # ---------------------------------------------------------
    # RESPUESTA SDUI: ¿Qué debe hacer Flutter ahora?
    # ---------------------------------------------------------
    # Al igual que le enviamos la UI, ahora le decimos a dónde navegar
    # (a la pantalla para agregar productos a esta nueva factura)
    return {
        "status": "success",
        "message": "Cabecera guardada correctamente.",
        "data": result,
        "next_action": {
            "type": "navigate",
            "target": f"/invoices/{result['invoice_id']}/lines",
            "params": {"bpartner_name": result["client_name"]},
        },
    }


@router.get(
    "/{invoice_id}/lines/sdui",
    response_model=ScreenLayout,
    summary="UI Catálogo de Productos",
    tags=["Facturación Móvil"],
)
async def get_invoice_lines_ui(
    invoice_id: int,
    bpartner_name: str = "Cliente",  # Lo recibimos opcionalmente desde Flutter para la UI
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Devuelve la pantalla de búsqueda y selección de productos para una factura específica.
    """

    # ⚠️ MOCK: En el futuro esto hará un SELECT a la tabla M_Product filtrando por ad_client_id
    productos_mock = [
        {
            "m_product_id": 2001,
            "name": "Licencia SRI Básica",
            "value": "SRI-01",
            "price": "$19.00",
        },
        {
            "m_product_id": 2002,
            "name": "Módulo POS Restaurante",
            "value": "POS-02",
            "price": "$45.00",
        },
        {
            "m_product_id": 2003,
            "name": "Consultoría Técnica",
            "value": "SRV-99",
            "price": "$150.00",
        },
    ]

    # Armamos la UI Base (Cabecera y Buscador)
    components = [
        HeaderComponent(
            type="header",
            title="Agregar Productos",
            subtitle=f"Factura #{invoice_id} - {bpartner_name}",
        ),
        TextInputComponent(
            type="text_input",
            id="search_query",
            label="Buscar en catálogo...",
            placeholder="Nombre o código del producto",
            keyboard_type="text",
            is_required=False,
        ),
    ]

    # Construimos la lista de productos dinámicamente
    for p in productos_mock:
        components.append(
            ListItemComponent(
                type="list_item",
                id=f"prod_{p['m_product_id']}",
                title=p["name"],
                subtitle=f"Cód: {p['value']}",
                value=p["price"],
                # Al tocar el producto, Flutter mandará un POST para agregarlo a la factura
                action=UIAction(
                    type="api_call",
                    target=f"/api/v1/invoices/{invoice_id}/add-line",
                    params={"m_product_id": p["m_product_id"], "qty": 1},
                ),
            )
        )

    return ScreenLayout(screen_name="Catálogo de Productos", layout=components)


@router.post(
    "/{invoice_id}/add-line",
    summary="Agregar Producto a Factura",
    tags=["Facturación Móvil"],
)
async def add_invoice_line(
    invoice_id: int,
    payload: InvoiceLineCreate,
    current_user: UserContext = Depends(get_current_user_context),
):
    # 1. Procesamos la línea en el servicio (¡AHORA SÍ REAL!)
    result = await invoice_service.add_line_to_invoice(
        invoice_id=invoice_id,
        client_id=current_user.ad_client_id,
        org_id=current_user.ad_org_id,  # 👈 ESTO ES VITAL PARA QUE NO FALLE
        data=payload,
    )

    # 2. SDUI...
    return {
        "status": "success",
        "message": f"Se agregó {result['qty']}x {result['product_name']}.",
        "data": result,
        "next_action": {
            "type": "modal",
            "target": "show_invoice_summary",
            "params": {
                "title": "Resumen de Factura",
                "grand_total": f"${result['invoice_grand_total']:.2f}",
                "button_label": "Emitir al SRI y Cobrar",
                "final_action_endpoint": f"/api/v1/invoices/{invoice_id}/complete",
            },
        },
    }


@router.post(
    "/{invoice_id}/complete",
    summary="Emitir Factura al SRI",
    tags=["Facturación Móvil"],
)
async def complete_invoice_action(
    invoice_id: int, current_user: UserContext = Depends(get_current_user_context)
):
    """
    Paso final. Cambia el estado de la factura a 'Completado'.
    Devuelve la orden al móvil para regresar al Dashboard.
    """
    # 1. Procesar en el ERP
    result = await invoice_service.complete_invoice(invoice_id=invoice_id)

    # 2. SDUI: ¿Qué hace Flutter después de cobrar?
    # Le decimos que lance un mensaje de éxito y lo mandamos de vuelta al Home.
    return {
        "status": "success",
        "message": f"¡Factura {result['document_no']} emitida con éxito!",
        "data": result,
        "next_action": {
            "type": "navigate",
            "target": "/dashboard",  # De vuelta a la pantalla principal
            "params": {
                "refresh_charts": True  # Le decimos a la app que recargue los gráficos
            },
        },
    }
