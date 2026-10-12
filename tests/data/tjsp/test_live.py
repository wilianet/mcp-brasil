"""Testes de contrato contra o portal real do TJSP (opt-in).

Rode com: MCP_BRASIL_RUN_LIVE_TESTS=1 uv run pytest tests/data/tjsp/test_live.py -m live
"""

import os
import re
from datetime import datetime

import pytest

from mcp_brasil.data.tjsp import client

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("MCP_BRASIL_RUN_LIVE_TESTS") != "1",
        reason="set MCP_BRASIL_RUN_LIVE_TESTS=1 to call the real TJSP CJSG",
    ),
]

QUERY = "desvio produtivo do consumidor"
NUMERO_CNJ = re.compile(r"^\d{7}-\d{2}\.\d{4}\.8\.26\.\d{4}$")


@pytest.mark.asyncio
async def test_ca1_pagina_com_acordaos() -> None:
    r = await client.buscar_acordaos(QUERY)
    assert r.total > 0
    assert 1 <= len(r.acordaos) <= 20
    for a in r.acordaos:
        assert NUMERO_CNJ.match(a.numero_processo)
        assert a.relator and a.orgao_julgador and a.data_julgamento and a.ementa


@pytest.mark.asyncio
async def test_ca2_pagina_2_diferente() -> None:
    p1 = await client.buscar_acordaos(QUERY, pagina=1)
    p2 = await client.buscar_acordaos(QUERY, pagina=2)
    assert {a.numero_processo for a in p1.acordaos}.isdisjoint(
        {a.numero_processo for a in p2.acordaos}
    )


@pytest.mark.asyncio
async def test_ca3_janela_de_datas() -> None:
    r = await client.buscar_acordaos(
        QUERY, data_julgamento_inicio="01/01/2025", data_julgamento_fim="31/01/2025"
    )
    assert r.acordaos
    for a in r.acordaos:
        assert a.data_julgamento is not None
        d = datetime.strptime(a.data_julgamento, "%d/%m/%Y")
        assert datetime(2025, 1, 1) <= d <= datetime(2025, 1, 31)


@pytest.mark.asyncio
async def test_ca4_somente_ementa_tem_menos_resultados() -> None:
    tudo = await client.buscar_acordaos(QUERY)
    ementa = await client.buscar_acordaos(QUERY, somente_ementa=True)
    assert 0 < ementa.total <= tudo.total
