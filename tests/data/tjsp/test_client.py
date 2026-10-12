"""Tests for the TJSP CJSG client (respx + HTML fixtures gravadas do portal)."""

import re
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from mcp_brasil.data.tjsp import client
from mcp_brasil.data.tjsp.constants import (
    CJSG_BASE_URL,
    CONSULTA_PATH,
    PAGINA_PATH,
    RESULTADO_PATH,
)
from mcp_brasil.exceptions import HttpClientError

FIXTURES = Path(__file__).parent / "fixtures"
URL_CONSULTA = f"{CJSG_BASE_URL}{CONSULTA_PATH}"
URL_RESULTADO = f"{CJSG_BASE_URL}{RESULTADO_PATH}"
URL_PAGINA = f"{CJSG_BASE_URL}{PAGINA_PATH}"
NUMERO_CNJ = r"^\d{7}-\d{2}\.\d{4}\.8\.26\.\d{4}$"


def _fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def _mock_fluxo(html_pagina: str) -> respx.Route:
    respx.get(URL_CONSULTA).mock(return_value=httpx.Response(200, text=""))
    respx.post(URL_RESULTADO).mock(return_value=httpx.Response(200, text=""))
    return respx.get(URL_PAGINA).mock(return_value=httpx.Response(200, text=html_pagina))


def _form_enviado() -> dict[str, list[str]]:
    corpo = respx.calls[1].request.content.decode()
    return parse_qs(corpo)


class TestParseResultados:
    """CA1: página com 20 acórdãos e todos os campos."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_pagina_com_20_acordaos(self) -> None:
        _mock_fluxo(_fixture("resultado_pagina1.html"))
        r = await client.buscar_acordaos("desvio produtivo do consumidor")
        assert r.total == 47675
        assert r.pagina == 1
        assert len(r.acordaos) == 20
        for a in r.acordaos:
            assert re.match(NUMERO_CNJ, a.numero_processo), a.numero_processo
            assert a.cd_acordao and a.cd_acordao.isdigit()
            assert a.relator and a.orgao_julgador and a.comarca
            assert a.data_julgamento and a.data_publicacao
            assert a.ementa and len(a.ementa) > 50
            assert a.url and a.cd_acordao in a.url

    @pytest.mark.asyncio
    @respx.mock
    async def test_campos_do_primeiro_acordao(self) -> None:
        _mock_fluxo(_fixture("resultado_pagina1.html"))
        a = (await client.buscar_acordaos("desvio produtivo do consumidor")).acordaos[0]
        assert a.numero_processo == "1058184-36.2023.8.26.0224"
        assert a.cd_acordao == "21046257"
        assert a.classe == "Apelação Cível"
        assert a.assunto == "Prestação de Serviços"
        assert a.relator == "Monte Serrat"
        assert a.orgao_julgador == "30ª Câmara de Direito Privado"
        assert a.ementa is not None
        assert a.ementa.startswith("Apelação")
        assert "Ação declaratória de inexistência de débito" in a.ementa
        assert "Recurso desprovido" in a.ementa

    @pytest.mark.asyncio
    @respx.mock
    async def test_sem_resultados_devolve_total_zero(self) -> None:
        """CA6: busca sem resultado não é falha."""
        _mock_fluxo(_fixture("resultado_vazio.html"))
        r = await client.buscar_acordaos("xyzzyquux987654")
        assert r.total == 0
        assert r.acordaos == []


class TestFormulario:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sessao_post_e_pagina(self) -> None:
        """CA2: GET da consulta, POST do formulário e GET da página N na mesma sessão."""
        rota = _mock_fluxo(_fixture("resultado_pagina1.html"))
        r = await client.buscar_acordaos("dano moral", pagina=2)
        assert r.pagina == 2
        assert [c.request.method for c in respx.calls] == ["GET", "POST", "GET"]
        assert rota.calls.last.request.url.params["pagina"] == "2"
        assert rota.calls.last.request.url.params["tipoDeDecisao"] == "A"
        form = _form_enviado()
        assert form["dados.buscaInteiroTeor"] == ["dano moral"]
        assert form["tipoDecisaoSelecionados"] == ["A"]
        assert form["dados.origensSelecionadas"] == ["T"]
        assert form["dados.ordenarPor"] == ["dtPublicacao"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_datas_de_julgamento(self) -> None:
        """CA3: datas vão no formulário."""
        _mock_fluxo(_fixture("resultado_pagina1.html"))
        await client.buscar_acordaos(
            "dano moral", data_julgamento_inicio="01/01/2025", data_julgamento_fim="31/01/2025"
        )
        form = _form_enviado()
        assert form["dados.dtJulgamentoInicio"] == ["01/01/2025"]
        assert form["dados.dtJulgamentoFim"] == ["31/01/2025"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_somente_ementa(self) -> None:
        """CA4: só-ementa usa dados.buscaEmenta e não o inteiro teor."""
        _mock_fluxo(_fixture("resultado_pagina1.html"))
        await client.buscar_acordaos("dano moral", somente_ementa=True)
        form = _form_enviado()
        assert form["dados.buscaEmenta"] == ["dano moral"]
        assert "dados.buscaInteiroTeor" not in form

    @pytest.mark.asyncio
    @respx.mock
    async def test_ordenar_por_relevancia(self) -> None:
        _mock_fluxo(_fixture("resultado_pagina1.html"))
        await client.buscar_acordaos("dano moral", ordenar_por="relevancia")
        assert _form_enviado()["dados.ordenarPor"] == ["relevancia"]


class TestErros:
    """CA5: falha da fonte vira HttpClientError, nunca lista vazia."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_status_5xx(self) -> None:
        respx.get(URL_CONSULTA).mock(return_value=httpx.Response(200, text=""))
        respx.post(URL_RESULTADO).mock(return_value=httpx.Response(503))
        with pytest.raises(HttpClientError):
            await client.buscar_acordaos("dano moral")

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout(self) -> None:
        respx.get(URL_CONSULTA).mock(return_value=httpx.Response(200, text=""))
        respx.post(URL_RESULTADO).mock(side_effect=httpx.ReadTimeout("lento"))
        with pytest.raises(HttpClientError):
            await client.buscar_acordaos("dano moral")

    @pytest.mark.asyncio
    @respx.mock
    async def test_html_sem_tabela(self) -> None:
        _mock_fluxo(_fixture("sem_tabela.html"))
        with pytest.raises(HttpClientError, match="sem a tabela"):
            await client.buscar_acordaos("dano moral")
