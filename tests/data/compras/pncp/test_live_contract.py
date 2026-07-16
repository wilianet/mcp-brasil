"""Opt-in contract tests against the real public PNCP API.

Run explicitly with:
    MCP_BRASIL_RUN_LIVE_TESTS=1 uv run pytest -m live
"""

from __future__ import annotations

import os

import pytest

from mcp_brasil.data.compras.pncp import client

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("MCP_BRASIL_RUN_LIVE_TESTS") != "1",
        reason="set MCP_BRASIL_RUN_LIVE_TESTS=1 to call the real PNCP API",
    ),
]

SAMPLE_CNPJ = os.getenv("PNCP_LIVE_SAMPLE_CNPJ", "90836693000140")
SAMPLE_ANO = int(os.getenv("PNCP_LIVE_SAMPLE_ANO", "2025"))
SAMPLE_SEQUENCIAL = int(os.getenv("PNCP_LIVE_SAMPLE_SEQUENCIAL", "401"))
SAMPLE_ITEM = int(os.getenv("PNCP_LIVE_SAMPLE_ITEM", "1"))


@pytest.mark.asyncio
async def test_real_pncp_items_documents_and_results_contract() -> None:
    itens = await client.listar_itens_contratacao(SAMPLE_CNPJ, SAMPLE_ANO, SAMPLE_SEQUENCIAL)
    documentos = await client.listar_documentos_contratacao(
        SAMPLE_CNPJ, SAMPLE_ANO, SAMPLE_SEQUENCIAL
    )

    assert isinstance(itens.itens, list)
    assert isinstance(documentos.documentos, list)
    assert itens.itens, "sample procurement no longer exposes items"

    resultados = await client.listar_resultados_item_contratacao(
        SAMPLE_CNPJ,
        SAMPLE_ANO,
        SAMPLE_SEQUENCIAL,
        SAMPLE_ITEM,
    )
    assert isinstance(resultados.resultados, list)
