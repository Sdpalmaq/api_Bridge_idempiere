from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware  # 👈 nuevo import
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
from app.api.v1.endpoints import auth, invoices, sri  # 👈 agrega sri
from app.services.quota_service import QuotaService  # 👈 nuevo import


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BFF Middleware para iDempiere y Flutter - Facturación Electrónica SRI Ecuador",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 👈 asterisco simple, permite todo en desarrollo
    allow_credentials=False,  # 👈 debe ser False cuando allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registramos las rutas de autenticación
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])

app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["Facturación"])

app.include_router(sri.router, prefix="/api/v1/sri", tags=["SRI Ecuador"])


@app.get("/", tags=["Sistema"])
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}


quota_service = QuotaService()


@app.get(
    "/api/v1/dashboard/sdui", response_model=ScreenLayout, tags=["Server-Driven UI"]
)
async def get_dashboard_ui(
    current_user: UserContext = Depends(get_current_user_context),
):
    # Quota REAL desde QuotaService
    consumido = quota_service.get_consumo(current_user.ad_client_id)
    limite = quota_service.get_limite(current_user.subscription_tier)
    porcentaje = (consumido / limite) * 100

    components_list = [
        HeaderComponent(
            type="header",
            title="Bienvenido a tu Empresa",
            subtitle=f"Plan {current_user.subscription_tier} activo",
        ),
        ProgressComponent(
            type="progress",
            id="quota_progress",
            label="Documentos emitidos este mes",
            current_value=consumido,
            max_value=limite,
            percentage=porcentaje,
            color_hex="#F44336" if porcentaje > 80 else "#4CAF50",
        ),
        ButtonComponent(
            type="button",
            label="Nueva Factura Electrónica",
            style="primary",
            action=UIAction(
                type="navigate",
                target="/api/v1/invoices/sdui/create",
            ),
        ),
        ButtonComponent(
            type="button",
            label="Ver Mis Facturas",
            style="secondary",
            action=UIAction(
                type="navigate",
                target="/api/v1/invoices/sdui/list",
            ),
        ),
    ]

    if current_user.subscription_tier == "Básico":
        components_list.append(
            BannerComponent(
                type="banner",
                label="Mejora a plan Pro para facturar sin límites",
                color_hex="#E8EAF6",
                action=UIAction(type="modal", target="upgrade_plan"),
            )
        )

    return ScreenLayout(screen_name="Dashboard Principal", layout=components_list)
