"""End-to-end tests for the TJSP feature via fastmcp.Client (CA7)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tjsp import FEATURE_META
from mcp_brasil.data.tjsp.schemas import AcordaoTJSP, ResultadoBuscaTJSP
from mcp_brasil.data.tjsp.server import mcp


def test_feature_meta() -> None:
    assert FEATURE_META.name == "tjsp"
    assert FEATURE_META.requires_auth is False


@pytest.mark.asyncio
async def test_tool_registrada_com_docstring() -> None:
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert "buscar_acordaos_tjsp" in tools
        assert "TJSP" in (tools["buscar_acordaos_tjsp"].description or "")
        props = tools["buscar_acordaos_tjsp"].inputSchema["properties"]
        assert {"query", "pagina", "somente_ementa", "ordenar_por"} <= set(props)


@pytest.mark.asyncio
async def test_resource_info() -> None:
    async with Client(mcp) as client:
        res = await client.read_resource("data://tjsp/info")
        data = json.loads(res[0].text)  # type: ignore[union-attr]
        assert data["tamanho_pagina"] == 20
        assert "relevancia" in data["filtros"]["ordenar_por"]


@pytest.mark.asyncio
async def test_tool_via_mcp_client() -> None:
    resultado = ResultadoBuscaTJSP(
        total=1,
        pagina=1,
        acordaos=[
            AcordaoTJSP(
                numero_processo="1000001-11.2025.8.26.0100",
                cd_acordao="21000001",
                relator="Relator Teste",
                ementa="Ementa de teste",
            )
        ],
    )
    with patch(
        "mcp_brasil.data.tjsp.tools.client.buscar_acordaos",
        new_callable=AsyncMock,
        return_value=resultado,
    ):
        async with Client(mcp) as client:
            result = await client.call_tool("buscar_acordaos_tjsp", {"query": "teste"})
    texto = result.content[0].text  # type: ignore[union-attr]
    assert "1000001-11.2025.8.26.0100" in texto
    assert "Ementa de teste" in texto
