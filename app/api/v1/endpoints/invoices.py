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
    summary="UI Catálogo de Productos Real",
    tags=["Facturación Móvil"],
)
async def get_invoice_lines_ui(
    invoice_id: int,
    bpartner_name: str = "Cliente",
    search_query: str = None,  # 👈 Flutter enviará esto cuando el usuario escriba
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Devuelve la pantalla de búsqueda y selección de productos reales desde iDempiere.
    """

    # 1. Llamada real a iDempiere a través del servicio
    productos_reales = await invoice_service.search_products(
        client_id=current_user.ad_client_id, query=search_query
    )

    # 2. Armamos la UI Base (Cabecera y Buscador)
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
            # NOTA: En Flutter, configurar este text_input para que al cambiar
            # recargue esta misma URL pasando ?search_query=lo_que_escribio
        ),
    ]

    # 3. Construimos la lista de productos dinámicamente
    if not productos_reales:
        from app.domain.sdui.components import (
            BannerComponent,
        )  # Asegúrate de importarlo arriba

        components.append(
            BannerComponent(
                type="banner",
                label="No se encontraron productos activos.",
                color_hex="#FFCDD2",  # Rojo clarito
                action=UIAction(type="modal", target="none"),
            )
        )
    else:
        for p in productos_reales:
            # Extraemos los datos reales. iDempiere puede devolver el ID en minúscula o con el nombre del modelo.
            prod_id = p.get("id") or p.get("M_Product_ID")
            nombre = p.get("Name", "Sin Nombre")
            codigo = p.get("Value", "S/N")

            # Nota: El precio idealmente viene de una tarifa (M_PriceList_Version),
            # pero para este MVP tomaremos un campo referencial o lo dejamos en "Agregar"
            precio = p.get("PriceStd", 0.0)

            components.append(
                ListItemComponent(
                    type="list_item",
                    id=f"prod_{prod_id}",
                    title=nombre,
                    subtitle=f"Cód: {codigo}",
                    value=f"${precio:.2f}",
                    action=UIAction(
                        type="api_call",
                        target=f"/api/v1/invoices/{invoice_id}/add-line",
                        params={"m_product_id": prod_id, "qty": 1},
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
    # 1. Procesamos la línea en el servicio
    result = await invoice_service.add_line_to_invoice(
        invoice_id=invoice_id,
        client_id=current_user.ad_client_id,
        org_id=current_user.ad_org_id,
        data=payload,
    )

    # 2. SDUI...
    return {
        "status": "success",
        # 👇 AQUÍ ARREGLAMOS EL ERROR: Quitamos product_name
        "message": f"Se agregaron {result['qty']} unidades a la factura.",
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
    summary="Emitir Factura al SRI (Con validación de Cuotas)",
    tags=["Facturación Móvil"],
)
async def complete_invoice_action(
    invoice_id: int, current_user: UserContext = Depends(get_current_user_context)
):
    """
    Paso final. Valida el Tier del usuario.
    Si tiene cuota -> Cambia estado a 'Completado' en iDempiere.
    Si NO tiene cuota -> Devuelve un Modal SDUI para hacer Upgrade.
    """

    # 1. 🛡️ GUARDIÁN DE CUOTAS (Lógica de Negocio)
    # Definimos los límites según el Tier (Esto luego vendrá de la BD)
    limite_docs = 50 if current_user.subscription_tier == "Básico" else 5000

    # MOCK: Simulamos que consultamos la BD y el usuario "Básico" ya hizo 50 facturas.
    # (Cambia este número a 10 para probar el "camino feliz" de nuevo)
    docs_consumidos_este_mes = 50

    if docs_consumidos_este_mes >= limite_docs:
        print(
            f"🚫 BLOQUEO: El usuario {current_user.user_id} agotó su plan {current_user.subscription_tier}."
        )

        # MAGIA SDUI: No lanzamos un error 500. Devolvemos una UI para venderle más.
        return {
            "status": "quota_exceeded",
            "message": "Has alcanzado el límite de tu plan.",
            "next_action": {
                "type": "modal",
                "target": "show_upgrade_plan",
                "params": {
                    "title": "¡Límite Alcanzado! 🚀",
                    "message": f"Tu plan {current_user.subscription_tier} te permite emitir {limite_docs} facturas/mes. Pásate al plan Pro para facturar sin límites.",
                    "button_label": "Ver Planes y Mejorar",
                    "upgrade_url": "/api/v1/tiers/sdui",  # Aquí lo mandaríamos a la pasarela de pago
                    "cancel_action": "dismiss",
                },
            },
        }

    # 2. Si tiene cuota libre, procedemos con el ERP
    print(
        f"✅ Cuota validada ({docs_consumidos_este_mes}/{limite_docs}). Procesando en iDempiere..."
    )
    result = await invoice_service.complete_invoice(invoice_id=invoice_id)

    # 3. Respuesta Exitosa SDUI
    return {
        "status": "success",
        "message": f"¡Factura {result['document_no']} emitida con éxito!",
        "data": result,
        "next_action": {
            "type": "navigate",
            "target": "/dashboard",
            "params": {"refresh_charts": True, "show_toast": "Factura enviada al SRI"},
        },
    }
