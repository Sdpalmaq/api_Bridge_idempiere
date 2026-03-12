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
    ProgressComponent,
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
    Devuelve la estructura del Dashboard principal con el consumo real de la cuota.
    """
    # 1. Lógica de Negocio (MOCK: esto luego viene de BD)
    limite_docs = 50 if current_user.subscription_tier == "Básico" else 5000
    docs_usados = 45  # A punto de acabarse la cuota
    porcentaje = (docs_usados / limite_docs) * 100

    # 2. Definimos los componentes
    components_list = [
        HeaderComponent(
            type="header",
            title=f"Bienvenido a tu Empresa",
            subtitle=f"Plan {current_user.subscription_tier} activo",
        ),
        # NUEVO: Componente visual de cuotas
        ProgressComponent(
            type="progress",
            id="quota_progress",
            label="Documentos emitidos este mes",
            current_value=docs_usados,
            max_value=limite_docs,
            percentage=porcentaje,
            color_hex=(
                "#F44336" if porcentaje > 80 else "#4CAF50"
            ),  # Rojo si está en peligro
        ),
        ButtonComponent(
            type="button",
            label="Nueva Factura Electrónica",
            style="primary",
            action=UIAction(
                type="navigate",
                target="/api/v1/invoices/sdui/create",  # <-- Flutter llamará a este GET
            ),
        ),
    ]

    # Banner de Upgrade si está en plan Básico
    if current_user.subscription_tier == "Básico":
        components_list.append(
            BannerComponent(
                type="banner",
                label="Mejora a plan Pro para ver métricas avanzadas y facturar sin límites",
                color_hex="#E8EAF6",
                action=UIAction(type="modal", target="upgrade_plan"),
            )
        )

    return ScreenLayout(screen_name="Dashboard Principal", layout=components_list)
