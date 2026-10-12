"""Feature TJSP — Acórdãos de 2º grau na Consulta de Jurisprudência do e-SAJ (CJSG)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tjsp",
    description="TJSP: busca de acórdãos de 2º grau (ementa e metadados) no e-SAJ CJSG",
    version="0.1.0",
    api_base="https://esaj.tjsp.jus.br/cjsg",
    requires_auth=False,
    tags=["judiciario", "jurisprudencia", "tjsp", "acordaos"],
)
