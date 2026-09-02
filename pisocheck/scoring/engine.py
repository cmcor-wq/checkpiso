"""Orquesta las funciones de scoring/factors.py sobre los datos ya obtenidos.

No hace llamadas de red: recibe `raw_data`, un dict {factor_id: datos_crudos}
ya recopilado por quien orquesta las fuentes (más adelante, main.py). Un
factor cuyo dato no está en `raw_data` (o vale None) simplemente no entra en
el informe — así la media global solo cuenta los factores disponibles,
como pide la spec §4.
"""

from __future__ import annotations

from pisocheck.models import AddressData, FactorResult, ReportData
from pisocheck.scoring.factors import FACTOR_FUENTES, FACTOR_SCORERS, label_from_score


def build_report(address: AddressData, raw_data: dict) -> ReportData:
    factores: list[FactorResult] = []

    for factor_id, scorer in FACTOR_SCORERS.items():
        raw = raw_data.get(factor_id)
        if raw is None:
            continue

        score, descripcion, datos_adicionales = scorer(raw)
        factores.append(
            FactorResult(
                factor_id=factor_id,
                score=score,
                label=label_from_score(score),
                valor_raw=raw,
                descripcion=descripcion,
                fuente=FACTOR_FUENTES[factor_id],
                datos_adicionales=datos_adicionales,
            )
        )

    return ReportData(address=address, factores=factores)
