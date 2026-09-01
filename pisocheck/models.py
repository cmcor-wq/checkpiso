"""Modelos de datos compartidos entre fuentes, motor de puntuación e informes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AddressData:
    raw: str
    lat: float
    lng: float
    municipio: str
    provincia: str | None = None
    distrito: str | None = None
    barrio: str | None = None
    ref_catastral: str | None = None
    superficie_construida: float | None = None
    superficie_habitable: float | None = None
    habitaciones: int | None = None
    banios: int | None = None
    anio_construccion: int | None = None
    plantas_edificio: int | None = None
    ascensor: bool | None = None
    coef_participacion: float | None = None
    cert_energetica_estimada: str | None = None


@dataclass
class FactorResult:
    factor_id: str
    score: float
    label: str
    valor_raw: Any
    descripcion: str
    fuente: str
    alerta: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    datos_adicionales: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # La alerta se puede pasar explícitamente, pero por defecto se deriva
        # del umbral estándar del proyecto (score < 4 → alerta).
        if self.score < 4:
            self.alerta = True


@dataclass
class ReportData:
    address: AddressData
    factores: list[FactorResult]
    generado_en: datetime = field(default_factory=datetime.utcnow)
    version: str = "0.1"

    @property
    def score_global(self) -> float:
        if not self.factores:
            return 0.0
        return round(sum(f.score for f in self.factores) / len(self.factores), 2)

    @property
    def alertas(self) -> list[FactorResult]:
        return sorted((f for f in self.factores if f.alerta), key=lambda f: f.score)

    def get_factor(self, factor_id: str) -> FactorResult | None:
        for f in self.factores:
            if f.factor_id == factor_id:
                return f
        return None
