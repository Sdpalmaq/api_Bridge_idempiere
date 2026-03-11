from fastapi import FastAPI, Depends
from app.core.config import settings
from app.core.security import get_current_user_context, UserContext
from app.domain.sdui.components import (
    ScreenLayout,
    HeaderComponent,
    ButtonComponent,
    WidgetComponent,
    BannerComponent,
    UIAction,
)
from app.api.v1.endpoints import auth, invoices

# IMPORTAMOS EL ROUTER DE AUTH
from app.api.v1.endpoints import auth

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BFF Middleware para iDempiere y Flutter - Facturación Electrónica SRI Ecuador",
)

# Registramos las rutas de autenticación
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])

app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["Facturación"])


@app.get("/", tags=["Sistema"])
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}


@app.get(
    "/api/v1/dashboard/sdui", response_model=ScreenLayout, tags=["Server-Driven UI"]
)
async def get_dashboard_ui(
    current_user: UserContext = Depends(get_current_user_context),
):
    """
    Devuelve la estructura de la pantalla Dashboard estandarizada con Pydantic.
    """

    # 1. Definimos los componentes base de forma segura
    components_list = [
        HeaderComponent(
            type="header",
            title=f"Bienvenido a tu Empresa",
            subtitle=f"Sucursal ID: {current_user.ad_org_id}",
        ),
        ButtonComponent(
            type="button",
            label="Nueva Factura Electrónica",
            style="primary",
            action=UIAction(
                type="navigate",
                target="/invoices/create",
                params={"client_id": current_user.ad_client_id},
            ),
        ),
    ]

    # 2. Lógica de Suscripciones (Tiers)
    if current_user.subscription_tier in ["Pro", "Empresarial"]:
        components_list.append(
            WidgetComponent(
                type="widget",
                id="bi_sales_chart",
                label="Gráfico de Ventas Mensuales",
                data_endpoint="/api/v1/reports/sales-chart",
            )
        )
    else:
        components_list.append(
            BannerComponent(
                type="banner",
                label="Mejora a plan Pro para ver métricas avanzadas",
                color_hex="#E8EAF6",
                action=UIAction(type="modal", target="upgrade_plan"),
            )
        )

    # 3. Retornamos el modelo validado
    return ScreenLayout(screen_name="Dashboard Principal", layout=components_list)
