"""Tests for the TJSP tools (client mockado)."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_brasil.data.tjsp.schemas import AcordaoTJSP, ResultadoBuscaTJSP
from mcp_brasil.data.tjsp.tools import buscar_acordaos_tjsp
from mcp_brasil.exceptions import HttpClientError

ALVO = "mcp_brasil.data.tjsp.tools.client.buscar_acordaos"


def _acordao(i: int) -> AcordaoTJSP:
    return AcordaoTJSP(
        numero_processo=f"100000{i}-11.2025.8.26.0100",
        cd_acordao=str(21000000 + i),
        classe="Apelação Cível",
        assunto="Dano Moral",
        relator="Relator Teste",
        comarca="São Paulo",
        orgao_julgador="1ª Câmara de Direito Privado",
        data_julgamento="10/01/2025",
        data_publicacao="12/01/2025",
        ementa="Ementa " * 120,
    )


class TestFormatacao:
    @pytest.mark.asyncio
    async def test_lista_com_total_e_paginacao(self) -> None:
        resultado = ResultadoBuscaTJSP(total=47, pagina=1, acordaos=[_acordao(1), _acordao(2)])
        with patch(ALVO, new_callable=AsyncMock, return_value=resultado):
            texto = await buscar_acordaos_tjsp("dano moral")
        assert "página 1 de 3, 47 acórdãos" in texto
        assert "**1. 1000001-11.2025.8.26.0100** (cdAcordao 21000001)" in texto
        assert "Relator(a): Relator Teste" in texto
        assert "Classe/Assunto: Apelação Cível / Dano Moral" in texto
        assert "Julgamento: 10/01/2025 · Publicação: 12/01/2025" in texto
        assert "`pagina=2`" in texto

    @pytest.mark.asyncio
    async def test_ementa_truncada_em_500(self) -> None:
        resultado = ResultadoBuscaTJSP(total=1, pagina=1, acordaos=[_acordao(1)])
        with patch(ALVO, new_callable=AsyncMock, return_value=resultado):
            texto = await buscar_acordaos_tjsp("dano moral")
        linha = next(ln for ln in texto.splitlines() if ln.strip().startswith("Ementa:"))
        assert linha.endswith("...")
        assert len(linha) < 520
        assert "`pagina=2`" not in texto

    @pytest.mark.asyncio
    async def test_sem_resultados(self) -> None:
        """CA6."""
        vazio = ResultadoBuscaTJSP(total=0, pagina=1, acordaos=[])
        with patch(ALVO, new_callable=AsyncMock, return_value=vazio):
            texto = await buscar_acordaos_tjsp("xyzzy")
        assert texto.startswith("Nenhum acórdão encontrado")
        assert "total informado pelo portal: 0" in texto


class TestErroEValidacao:
    @pytest.mark.asyncio
    async def test_fonte_indisponivel(self) -> None:
        """CA5."""
        with patch(ALVO, new_callable=AsyncMock, side_effect=HttpClientError("TJSP CJSG: 503")):
            texto = await buscar_acordaos_tjsp("dano moral")
        assert texto.startswith("Fonte TJSP indisponível: TJSP CJSG: 503")

    @pytest.mark.asyncio
    async def test_data_invalida_nao_chama_client(self) -> None:
        with patch(ALVO, new_callable=AsyncMock) as mock:
            texto = await buscar_acordaos_tjsp("dano moral", data_julgamento_inicio="2025-01-01")
        assert "data_julgamento_inicio inválida" in texto
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_ordenar_por_invalido(self) -> None:
        with patch(ALVO, new_callable=AsyncMock) as mock:
            texto = await buscar_acordaos_tjsp("dano moral", ordenar_por="data")
        assert "ordenar_por inválido" in texto
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_pagina_invalida(self) -> None:
        with patch(ALVO, new_callable=AsyncMock) as mock:
            texto = await buscar_acordaos_tjsp("dano moral", pagina=0)
        assert "pagina deve ser" in texto
        mock.assert_not_called()
