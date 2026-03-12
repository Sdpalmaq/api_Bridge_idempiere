from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal


# ---------------------------------------------------------
# 1. Acciones (¿Qué pasa al tocar un componente en Flutter?)
# ---------------------------------------------------------
class UIAction(BaseModel):
    type: Literal["navigate", "api_call", "modal"] = Field(
        ..., description="Tipo de acción a ejecutar"
    )
    target: str = Field(..., description="Ruta de navegación o endpoint a llamar")
    params: Optional[dict] = Field(default=None, description="Parámetros adicionales")


# ---------------------------------------------------------
# 2. Componentes Base Visuales
# ---------------------------------------------------------
class HeaderComponent(BaseModel):
    type: Literal["header"]
    title: str
    subtitle: Optional[str] = None


class ButtonComponent(BaseModel):
    type: Literal["button"]
    label: str
    action: UIAction
    style: Literal["primary", "secondary", "danger"] = "primary"


class WidgetComponent(BaseModel):
    type: Literal["widget"]
    id: str
    label: str
    data_endpoint: Optional[str] = None


class BannerComponent(BaseModel):
    type: Literal["banner"]
    label: str
    action: UIAction
    color_hex: str = "#FFD700"


class ProgressComponent(BaseModel):
    type: Literal["progress"]
    id: str = Field(..., description="ID único del componente de progreso")
    label: str = Field(
        ..., description="Texto a mostrar encima de la barra (ej: Documentos usados)"
    )
    current_value: float = Field(..., description="Valor actual consumido")
    max_value: float = Field(..., description="Valor máximo permitido (límite)")
    percentage: float = Field(..., description="Porcentaje calculado (0 a 100)")
    color_hex: str = Field(
        default="#4CAF50",
        description="Color de la barra (ej: verde normal, rojo si es peligroso)",
    )


# ---------------------------------------------------------
# 3. Componentes de Formulario (Nuevos)
# ---------------------------------------------------------
class InputValidation(BaseModel):
    regex: str = Field(..., description="Expresión regular para validar en Flutter")
    error_message: str = Field(..., description="Mensaje a mostrar si la regex falla")


class TextInputComponent(BaseModel):
    type: Literal["text_input"]
    id: str = Field(
        ...,
        description="El nombre del campo que Flutter nos enviará de vuelta (ej. 'ruc')",
    )
    label: str
    placeholder: Optional[str] = None
    keyboard_type: Literal["text", "number", "email", "phone"] = "text"
    is_required: bool = True
    validation: Optional[InputValidation] = None


class SelectComponent(BaseModel):
    type: Literal["select"]
    id: str
    label: str
    options: List[dict] = Field(
        ..., description="Lista de {'label': '...', 'value': '...'}"
    )


# ---------------------------------------------------------
# 6. Componentes de Listas / Catálogos (NUEVO)
# ---------------------------------------------------------
class ListItemComponent(BaseModel):
    type: Literal["list_item"]
    id: str = Field(..., description="ID único del item (ej. M_Product_ID)")
    title: str = Field(..., description="Nombre del producto")
    subtitle: Optional[str] = Field(None, description="Código o descripción corta")
    value: str = Field(..., description="Precio o cantidad a mostrar a la derecha")
    action: UIAction = Field(
        ..., description="Qué pasa al tocar este producto (ej. agregarlo)"
    )


# ---------------------------------------------------------
# 4. Tipado Polimórfico (¡SIEMPRE DESPUÉS DE DECLARAR LAS CLASES!)
# ---------------------------------------------------------
AnyComponent = Union[
    HeaderComponent,
    ButtonComponent,
    WidgetComponent,
    BannerComponent,
    TextInputComponent,
    SelectComponent,
    ListItemComponent,
    ProgressComponent,  # <-- No olvidar añadirlo aquí también
]


# ---------------------------------------------------------
# 5. El Contenedor Final: La Pantalla
# ---------------------------------------------------------
class ScreenLayout(BaseModel):
    screen_name: str = Field(..., description="Nombre interno de la pantalla")
    layout: List[AnyComponent] = Field(
        ..., description="Lista ordenada de componentes a renderizar"
    )
