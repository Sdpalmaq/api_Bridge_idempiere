# app/services/quota_service.py
import json
import os
from datetime import datetime
from pathlib import Path

# Archivo temporal hasta tener PostgreSQL
QUOTA_FILE = Path("quota_data.json")


def _load_data() -> dict:
    if not QUOTA_FILE.exists():
        return {}
    with open(QUOTA_FILE, "r") as f:
        return json.load(f)


def _save_data(data: dict):
    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f, indent=2)


class QuotaService:

    # Límites por tier — luego vendrán de BD
    LIMITES = {
        "Básico": 50,
        "Starter": 300,
        "Growth": 1000,
        "Pro": 5000,
        "Unlimited": 999999,
    }

    def _clave(self, client_id: int) -> str:
        """Clave única por tenant por mes: '11_2026_03'"""
        now = datetime.utcnow()
        return f"{client_id}_{now.year}_{now.month:02d}"

    def get_consumo(self, client_id: int) -> int:
        """Cuántos documentos emitió este tenant este mes."""
        data = _load_data()
        return data.get(self._clave(client_id), 0)

    def get_limite(self, subscription_tier: str) -> int:
        """Límite del plan."""
        return self.LIMITES.get(subscription_tier, 50)

    def puede_emitir(
        self, client_id: int, subscription_tier: str
    ) -> tuple[bool, int, int]:
        """
        Verifica si el tenant puede emitir un documento más.
        Retorna: (puede_emitir, consumido, limite)
        """
        consumido = self.get_consumo(client_id)
        limite = self.get_limite(subscription_tier)
        return consumido < limite, consumido, limite

    def registrar_emision(self, client_id: int):
        """Suma 1 al contador del tenant en el mes actual."""
        data = _load_data()
        clave = self._clave(client_id)
        data[clave] = data.get(clave, 0) + 1
        _save_data(data)
        print(f"📊 Quota registrada: tenant {client_id} → {data[clave]} docs este mes")
