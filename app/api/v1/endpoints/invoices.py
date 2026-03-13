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
    BannerComponent,
)
from app.domain.schemas.invoice import InvoiceHeaderCreate, InvoiceLineCreate
from app.services.invoice_service import InvoiceService
from app.services.quota_service import QuotaService

router = APIRouter()
invoice_service = InvoiceService()
quota_service = QuotaService()  # junto a invoice_service = InvoiceService()


def extract(val, default=""):
    """iDempiere devuelve campos referencia como dicts {'id': 'CO', 'identifier': 'Completado'}"""
    if isinstance(val, dict):
        return val.get("id", default)
    return val if val is not None else default


@router.get(
    "/sdui/list",
    response_model=ScreenLayout,
    summary="UI Listado de Facturas",
    tags=["Facturación Móvil"],
)
async def get_invoice_list_ui(
    current_user: UserContext = Depends(get_current_user_context),
):
    facturas = await invoice_service.get_invoice_list(
        client_id=current_user.ad_client_id,
        org_id=current_user.ad_org_id,
    )

    components = [
        HeaderComponent(
            type="header",
            title="Mis Facturas",
            subtitle=f"{len(facturas)} documentos encontrados",
        ),
    ]

    if not facturas:
        components.append(
            BannerComponent(
                type="banner",
                label=f"Subtotal: ${total_lines:.2f}   |   IVA: ${iva:.2f}   |   Total: ${grand_total:.2f}",
                color_hex="#1565C0",  # Azul oscuro
                action=UIAction(type="modal", target="none"),
            ),
        )
    else:
        for f in facturas:
            invoice_id = f.get("id") or f.get("C_Invoice_ID")
            doc_no = f.get("DocumentNo", "Borrador")
            date_str = str(f.get("DateInvoiced", ""))[:10]
            doc_status = str(extract(f.get("DocStatus"), "DR"))
            grand_total = float(extract(f.get("GrandTotal"), 0.0))

            status_label = {
                "CO": "✅ Autorizada",
                "DR": "📝 Borrador",
                "VO": "❌ Anulada",
                "RE": "🔄 Reversada",
            }.get(doc_status, f"⚪ {doc_status}")

            components.append(
                ListItemComponent(
                    type="list_item",
                    id=f"inv_{invoice_id}",
                    title=f"Factura {doc_no}",
                    subtitle=f"{status_label}  •  {date_str}",
                    value=f"${grand_total:.2f}",
                    action=UIAction(
                        type="navigate",
                        target=f"/api/v1/invoices/{invoice_id}/sdui/detail",
                        params={"invoice_id": invoice_id},
                    ),
                )
            )

    components.append(
        ButtonComponent(
            type="button",
            label="+ Nueva Factura",
            style="primary",
            action=UIAction(
                type="navigate",
                target="/api/v1/invoices/sdui/create",
            ),
        )
    )

    return ScreenLayout(screen_name="Historial de Facturas", layout=components)


@router.get(
    "/sdui/create",
    response_model=ScreenLayout,
    summary="UI para Crear Factura",
)
async def get_invoice_create_ui(
    current_user: UserContext = Depends(get_current_user_context),
):
    REGEX_RUC_CEDULA = r"^\d{10,13}$"

    components = [
        HeaderComponent(
            type="header",
            title="Nueva Factura",
            subtitle="Complete los datos del cliente",
        ),
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
        ButtonComponent(
            type="button",
            label="Continuar al Detalle",
            style="primary",
            action=UIAction(
                type="api_call",
                target="/api/v1/invoices/draft",
                params={"action": "save_header"},
            ),
        ),
    ]

    return ScreenLayout(screen_name="Formulario Nueva Factura", layout=components)


@router.post(
    "/draft",
    summary="Guardar Cabecera y Validar Cliente",
    tags=["Facturación Móvil"],
)
async def create_invoice_draft(
    payload: InvoiceHeaderCreate,
    current_user: UserContext = Depends(get_current_user_context),
):
    result = await invoice_service.process_draft_header(
        client_id=current_user.ad_client_id,
        org_id=current_user.ad_org_id,
        user_id=current_user.user_id,
        data=payload,
    )

    return {
        "status": "success",
        "message": "Cabecera guardada correctamente.",
        "data": result,
        "next_action": {
            "type": "navigate",
            "target": f"/api/v1/invoices/{result['invoice_id']}/lines/sdui",
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
    bpartner_name: str = "Cliente",
    search_query: str = None,
    current_user: UserContext = Depends(get_current_user_context),
):
    productos_reales = await invoice_service.search_products(
        client_id=current_user.ad_client_id, query=search_query
    )

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

    if not productos_reales:
        components.append(
            BannerComponent(
                type="banner",
                label="No se encontraron productos activos.",
                color_hex="#FFCDD2",
                action=UIAction(type="modal", target="none"),
            )
        )
    else:
        for p in productos_reales:
            prod_id = p.get("id") or p.get("M_Product_ID")
            nombre = str(extract(p.get("Name"), "Sin Nombre"))
            codigo = str(extract(p.get("Value"), "S/N"))
            precio = float(extract(p.get("PriceStd"), 0.0))

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
    result = await invoice_service.add_line_to_invoice(
        invoice_id=invoice_id,
        client_id=current_user.ad_client_id,
        org_id=current_user.ad_org_id,
        data=payload,
    )

    return {
        "status": "success",
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
    summary="Emitir Factura al SRI",
    tags=["Facturación Móvil"],
)
async def complete_invoice_action(
    invoice_id: int,
    current_user: UserContext = Depends(get_current_user_context),
):
    # 1. Verificar quota REAL
    puede, consumido, limite = quota_service.puede_emitir(
        client_id=current_user.ad_client_id,
        subscription_tier=current_user.subscription_tier,
    )

    if not puede:
        print(
            f"🚫 BLOQUEO: tenant {current_user.ad_client_id} agotó quota ({consumido}/{limite})"
        )
        return {
            "status": "quota_exceeded",
            "message": "Has alcanzado el límite de tu plan.",
            "next_action": {
                "type": "modal",
                "target": "show_upgrade_plan",
                "params": {
                    "title": "¡Límite Alcanzado! 🚀",
                    "message": f"Tu plan {current_user.subscription_tier} permite {limite} facturas/mes. Llevas {consumido}.",
                    "button_label": "Ver Planes y Mejorar",
                    "upgrade_url": "/api/v1/tiers/sdui",
                    "cancel_action": "dismiss",
                },
            },
        }

    # 2. Emitir en iDempiere
    print(f"✅ Quota OK ({consumido}/{limite}). Procesando en iDempiere...")
    result = await invoice_service.complete_invoice(invoice_id=invoice_id)

    # 3. Registrar la emisión SOLO si iDempiere tuvo éxito
    quota_service.registrar_emision(client_id=current_user.ad_client_id)

    return {
        "status": "success",
        "message": f"¡Factura {result['document_no']} emitida con éxito!",
        "data": result,
        "next_action": {
            "type": "modal",
            "target": "invoice_done",
            "params": {
                "title": "¡Factura Emitida! ✅",
                "message": f"Factura {result['document_no']} enviada al SRI. Quedan {limite - consumido - 1} docs este mes.",
                "button_label": "Volver al Inicio",
                "navigate_after": "/dashboard",
            },
        },
    }


# app/api/v1/endpoints/invoices.py


@router.get(
    "/{invoice_id}/sdui/detail",
    response_model=ScreenLayout,
    summary="UI Detalle de Factura",
    tags=["Facturación Móvil"],
)
async def get_invoice_detail_ui(
    invoice_id: int,
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Muestra la cabecera y líneas de una factura específica.
    """
    data = await invoice_service.get_invoice_detail(invoice_id=invoice_id)
    header = data["header"]
    lines = data["lines"]

    # Extraemos campos de la cabecera
    doc_no = str(extract(header.get("DocumentNo"), "S/N"))
    date_str = str(header.get("DateInvoiced", ""))[:10]
    doc_status = str(extract(header.get("DocStatus"), "DR"))
    grand_total = float(extract(header.get("GrandTotal"), 0.0))
    total_lines = float(extract(header.get("TotalLines"), 0.0))

    status_label = {
        "CO": "✅ Autorizada",
        "DR": "📝 Borrador",
        "VO": "❌ Anulada",
        "RE": "🔄 Reversada",
    }.get(doc_status, f"⚪ {doc_status}")

    # Calculamos IVA desde los totales
    iva = grand_total - total_lines

    components = [
        HeaderComponent(
            type="header",
            title=f"Factura {doc_no}",
            subtitle=f"{status_label}  •  {date_str}",
        ),
        # Resumen financiero como banner
        BannerComponent(
            type="banner",
            label=f"Subtotal: ${total_lines:.2f}   |   IVA: ${iva:.2f}   |   Total: ${grand_total:.2f}",
            color_hex="#1565C0",  # Azul oscuro
            action=UIAction(type="modal", target="none"),
        ),
        # Cabecera de la sección de líneas
        HeaderComponent(
            type="header",
            title="Productos facturados",
            subtitle=f"{len(lines)} línea(s)",
        ),
    ]

    if not lines:
        components.append(
            BannerComponent(
                type="banner",
                label="Esta factura no tiene líneas de detalle.",
                color_hex="#FFF9C4",
                action=UIAction(type="modal", target="none"),
            )
        )
    else:
        for line in lines:
            # Extraemos datos de cada línea
            # Extraer nombre limpio del producto
            producto_raw = line.get("M_Product_ID")
            if isinstance(producto_raw, dict):
                identifier = producto_raw.get("identifier", "Producto")
                # iDempiere formato: "Screw_#6-32 x 3/8..." → separar por _ y tomar desde el segundo
                partes = identifier.split("_", 1)
                nombre = partes[1] if len(partes) > 1 else partes[0]
            else:
                nombre = "Producto sin nombre"

            # Para líneas de descripción pura (sin producto)
            if not producto_raw:
                nombre = line.get("Description", "Línea de descripción")

            qty = float(extract(line.get("QtyInvoiced"), 0.0))
            precio = float(extract(line.get("PriceActual"), 0.0))
            subtotal = float(extract(line.get("LineNetAmt"), 0.0))

            components.append(
                ListItemComponent(
                    type="list_item",
                    id=f"line_{line.get('id') or line.get('C_InvoiceLine_ID')}",
                    title=nombre,
                    subtitle=f"Cant: {qty:.0f}  •  Precio: ${precio:.2f}",
                    value=f"${subtotal:.2f}",
                    action=UIAction(
                        type="modal",
                        target="none",
                        params={},
                    ),
                )
            )

    # Botón de volver al listado
    components.append(
        ButtonComponent(
            type="button",
            label="← Volver al Listado",
            style="secondary",
            action=UIAction(
                type="navigate",
                target="/api/v1/invoices/sdui/list",
            ),
        )
    )

    # Solo mostrar "Emitir" si está en borrador
    if doc_status == "DR":
        components.append(
            ButtonComponent(
                type="button",
                label="Emitir al SRI",
                style="primary",
                action=UIAction(
                    type="api_call",
                    target=f"/api/v1/invoices/{invoice_id}/complete",
                    params={},
                ),
            )
        )

    return ScreenLayout(screen_name=f"Detalle Factura {doc_no}", layout=components)
