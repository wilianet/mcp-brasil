"""Tests for the PNCP HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.compras.pncp import client
from mcp_brasil.data.compras.pncp.constants import (
    ATAS_URL,
    CONTRATACAO_DETALHE_URL,
    CONTRATACOES_URL,
    CONTRATOS_URL,
    FORNECEDORES_URL,
    ORGAOS_URL,
)

# Common test dates (YYYYMMDD)
DATE_INI = "20240101"
DATE_FIM = "20240331"


# ---------------------------------------------------------------------------
# normalizar_data / validar_periodo
# ---------------------------------------------------------------------------


class TestNormalizarData:
    def test_yyyymmdd_passthrough(self) -> None:
        assert client.normalizar_data("20240315") == "20240315"

    def test_yyyy_mm_dd(self) -> None:
        assert client.normalizar_data("2024-03-15") == "20240315"

    def test_dd_mm_yyyy(self) -> None:
        assert client.normalizar_data("15/03/2024") == "20240315"

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Formato de data inválido"):
            client.normalizar_data("March 15, 2024")

    def test_whitespace_stripped(self) -> None:
        assert client.normalizar_data("  20240315  ") == "20240315"


class TestValidarPeriodo:
    def test_valid_period(self) -> None:
        client.validar_periodo("20240101", "20240331")  # 90 days

    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValueError, match="anterior"):
            client.validar_periodo("20240331", "20240101")

    def test_exceeds_max_range_raises(self) -> None:
        with pytest.raises(ValueError, match="excede o máximo"):
            client.validar_periodo("20240101", "20250201")  # >365 days


# ---------------------------------------------------------------------------
# buscar_contratacoes
# ---------------------------------------------------------------------------


class TestBuscarContratacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contratacoes(self) -> None:
        respx.get(CONTRATACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "data": [
                        {
                            "orgaoEntidade": {
                                "cnpj": "00394460000141",
                                "razaoSocial": "Ministério da Educação",
                                "ufSigla": "DF",
                                "municipioNome": "Brasília",
                                "esferaNome": "Federal",
                            },
                            "anoCompra": 2024,
                            "sequencialCompra": 1,
                            "numeroControlePNCP": "00394460000141-1-000001/2024",
                            "objetoCompra": "Aquisição de computadores",
                            "modalidadeId": 1,
                            "modalidadeNome": "Pregão eletrônico",
                            "situacaoCompraId": 1,
                            "situacaoCompraNome": "Publicada",
                            "valorTotalEstimado": 500000.0,
                            "valorTotalHomologado": 480000.0,
                            "dataPublicacaoPncp": "2024-03-15",
                            "dataAberturaProposta": "2024-04-01",
                            "linkPncp": "https://pncp.gov.br/app/editais/123",
                        }
                    ],
                },
            )
        )
        result = await client.buscar_contratacoes(
            data_inicial=DATE_INI, data_final=DATE_FIM, modalidade=6
        )
        assert result.total == 1
        assert len(result.contratacoes) == 1
        c = result.contratacoes[0]
        assert c.orgao_cnpj == "00394460000141"
        assert c.orgao_nome == "Ministério da Educação"
        assert c.objeto == "Aquisição de computadores"
        assert c.modalidade_id == 1
        assert c.valor_estimado == 500000.0
        assert c.valor_homologado == 480000.0
        assert c.uf == "DF"
        assert c.municipio == "Brasília"
        assert c.link_pncp == "https://pncp.gov.br/app/editais/123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(CONTRATACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={"totalRegistros": 0, "data": []},
            )
        )
        result = await client.buscar_contratacoes(
            data_inicial=DATE_INI, data_final=DATE_FIM, modalidade=6
        )
        assert result.total == 0
        assert result.contratacoes == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fallback_resultado_key(self) -> None:
        respx.get(CONTRATACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 1,
                    "resultado": [
                        {
                            "orgaoEntidade": {"cnpj": "11111111000100"},
                            "objetoCompra": "Teste fallback",
                        }
                    ],
                },
            )
        )
        result = await client.buscar_contratacoes(
            data_inicial=DATE_INI, data_final=DATE_FIM, modalidade=6
        )
        assert len(result.contratacoes) == 1
        assert result.contratacoes[0].objeto == "Teste fallback"

    @pytest.mark.asyncio
    @respx.mock
    async def test_client_side_text_filter(self) -> None:
        respx.get(CONTRATACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 2,
                    "data": [
                        {
                            "orgaoEntidade": {},
                            "objetoCompra": "Aquisição de computadores",
                        },
                        {
                            "orgaoEntidade": {},
                            "objetoCompra": "Serviço de limpeza",
                        },
                    ],
                },
            )
        )
        result = await client.buscar_contratacoes(
            data_inicial=DATE_INI,
            data_final=DATE_FIM,
            modalidade=6,
            texto="computadores",
        )
        assert result.total == 1
        assert result.contratacoes[0].objeto == "Aquisição de computadores"

    @pytest.mark.asyncio
    @respx.mock
    async def test_text_filter_scans_all_pages(self) -> None:
        route = respx.get(CONTRATACOES_URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "totalRegistros": 2,
                        "totalPaginas": 2,
                        "data": [{"orgaoEntidade": {}, "objetoCompra": "Serviço de limpeza"}],
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "totalRegistros": 2,
                        "totalPaginas": 2,
                        "data": [
                            {"orgaoEntidade": {}, "objetoCompra": "Aquisição de computadores"}
                        ],
                    },
                ),
            ]
        )

        result = await client.buscar_contratacoes(
            DATE_INI, DATE_FIM, 6, texto="computadores", tamanho=1
        )

        assert route.call_count == 2
        assert result.total == 1
        assert result.contratacoes[0].objeto == "Aquisição de computadores"
        assert result.paginacao.paginas_consultadas == 2
        assert result.paginacao.pesquisa_completa is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_text_filter_reports_page_limit(self) -> None:
        route = respx.get(CONTRATACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 3,
                    "totalPaginas": 3,
                    "data": [{"orgaoEntidade": {}, "objetoCompra": "Serviço de limpeza"}],
                },
            )
        )

        result = await client.buscar_contratacoes(
            DATE_INI, DATE_FIM, 6, texto="computadores", tamanho=1, max_paginas=1
        )

        assert route.call_count == 1
        assert result.total == 0
        assert result.paginacao.pesquisa_completa is False
        assert result.paginacao.limite_paginas_atingido is True


# ---------------------------------------------------------------------------
# buscar_contratos
# ---------------------------------------------------------------------------


class TestBuscarContratos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contratos(self) -> None:
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "data": [
                        {
                            "orgaoEntidade": {
                                "cnpj": "00394460000141",
                                "razaoSocial": "Ministério da Saúde",
                            },
                            "fornecedor": {
                                "cnpj": "12345678000199",
                                "razaoSocial": "Empresa Pharma LTDA",
                            },
                            "numeroContratoEmpenho": "2024/001",
                            "objetoContrato": "Fornecimento de medicamentos",
                            "valorInicial": 100000.0,
                            "valorFinal": 95000.0,
                            "dataVigenciaInicio": "2024-01-01",
                            "dataVigenciaFim": "2024-12-31",
                            "dataPublicacaoPncp": "2024-01-10",
                            "nomeStatus": "Vigente",
                        }
                    ],
                },
            )
        )
        result = await client.buscar_contratos(data_inicial=DATE_INI, data_final=DATE_FIM)
        assert result.total == 1
        assert len(result.contratos) == 1
        c = result.contratos[0]
        assert c.orgao_cnpj == "00394460000141"
        assert c.orgao_nome == "Ministério da Saúde"
        assert c.fornecedor_cnpj == "12345678000199"
        assert c.fornecedor_nome == "Empresa Pharma LTDA"
        assert c.numero_contrato == "2024/001"
        assert c.objeto == "Fornecimento de medicamentos"
        assert c.valor_inicial == 100000.0
        assert c.valor_final == 95000.0
        assert c.vigencia_inicio == "2024-01-01"
        assert c.vigencia_fim == "2024-12-31"
        assert c.situacao == "Vigente"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"totalRegistros": 0, "data": []},
            )
        )
        result = await client.buscar_contratos(data_inicial=DATE_INI, data_final=DATE_FIM)
        assert result.total == 0
        assert result.contratos == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fornecedor_cpfcnpj_fallback(self) -> None:
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "data": [
                        {
                            "orgaoEntidade": {},
                            "fornecedor": {
                                "cpfCnpj": "99988877000166",
                                "nomeRazaoSocial": "Fornecedor Alt",
                            },
                            "objetoContrato": "Teste fallback fornecedor",
                        }
                    ],
                },
            )
        )
        result = await client.buscar_contratos(data_inicial=DATE_INI, data_final=DATE_FIM)
        c = result.contratos[0]
        assert c.fornecedor_cnpj == "99988877000166"
        assert c.fornecedor_nome == "Fornecedor Alt"

    @pytest.mark.asyncio
    @respx.mock
    async def test_client_side_text_filter(self) -> None:
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 2,
                    "data": [
                        {
                            "orgaoEntidade": {},
                            "objetoContrato": "Fornecimento de medicamentos",
                        },
                        {
                            "orgaoEntidade": {},
                            "objetoContrato": "Serviço de TI",
                        },
                    ],
                },
            )
        )
        result = await client.buscar_contratos(
            data_inicial=DATE_INI,
            data_final=DATE_FIM,
            texto="medicamentos",
        )
        assert result.total == 1
        assert result.contratos[0].objeto == "Fornecimento de medicamentos"


# ---------------------------------------------------------------------------
# buscar_atas
# ---------------------------------------------------------------------------


class TestBuscarAtas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_atas(self) -> None:
        respx.get(ATAS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "data": [
                        {
                            "orgaoEntidade": {
                                "cnpj": "00394460000141",
                                "razaoSocial": "Universidade Federal",
                            },
                            "fornecedor": {
                                "cnpj": "98765432000155",
                                "razaoSocial": "Papelaria Central LTDA",
                            },
                            "numeroAtaRegistroPreco": "2024/010",
                            "objetoContrato": "Material de escritório",
                            "valorInicial": 250000.0,
                            "dataVigenciaInicio": "2024-06-01",
                            "dataVigenciaFim": "2025-05-31",
                            "nomeStatus": "Vigente",
                        }
                    ],
                },
            )
        )
        result = await client.buscar_atas(data_inicial=DATE_INI, data_final=DATE_FIM)
        assert result.total == 1
        assert len(result.atas) == 1
        a = result.atas[0]
        assert a.orgao_cnpj == "00394460000141"
        assert a.orgao_nome == "Universidade Federal"
        assert a.fornecedor_cnpj == "98765432000155"
        assert a.fornecedor_nome == "Papelaria Central LTDA"
        assert a.numero_ata == "2024/010"
        assert a.objeto == "Material de escritório"
        assert a.valor_total == 250000.0
        assert a.vigencia_inicio == "2024-06-01"
        assert a.vigencia_fim == "2025-05-31"
        assert a.situacao == "Vigente"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(ATAS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"totalRegistros": 0, "data": []},
            )
        )
        result = await client.buscar_atas(data_inicial=DATE_INI, data_final=DATE_FIM)
        assert result.total == 0
        assert result.atas == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_ata_fields_fallback(self) -> None:
        respx.get(ATAS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "data": [
                        {
                            "orgaoEntidade": {},
                            "fornecedor": {
                                "cpfCnpj": "11122233000144",
                                "nomeRazaoSocial": "Fornecedor Ata Alt",
                            },
                            "numeroAta": "ATA-001",
                            "objetoAta": "Objeto via campo ata",
                            "valorTotal": 300000.0,
                        }
                    ],
                },
            )
        )
        result = await client.buscar_atas(data_inicial=DATE_INI, data_final=DATE_FIM)
        a = result.atas[0]
        assert a.fornecedor_cnpj == "11122233000144"
        assert a.fornecedor_nome == "Fornecedor Ata Alt"
        assert a.numero_ata == "ATA-001"
        assert a.objeto == "Objeto via campo ata"
        assert a.valor_total == 300000.0


# ---------------------------------------------------------------------------
# consultar_fornecedor
# ---------------------------------------------------------------------------


class TestConsultarFornecedor:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_fornecedor(self) -> None:
        respx.get(FORNECEDORES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalRegistros": 1,
                    "data": [
                        {
                            "cnpj": "12345678000199",
                            "razaoSocial": "Empresa Teste LTDA",
                            "nomeFantasia": "Teste Corp",
                            "municipio": {"nome": "São Paulo"},
                            "uf": {"sigla": "SP"},
                            "porte": "Médio",
                            "dataAbertura": "2010-05-20",
                        }
                    ],
                },
            )
        )
        result = await client.consultar_fornecedor(cnpj="12345678000199")
        assert result.total == 1
        assert len(result.fornecedores) == 1
        f = result.fornecedores[0]
        assert f.cnpj == "12345678000199"
        assert f.razao_social == "Empresa Teste LTDA"
        assert f.nome_fantasia == "Teste Corp"
        assert f.municipio == "São Paulo"
        assert f.uf == "SP"
        assert f.porte == "Médio"
        assert f.data_abertura == "2010-05-20"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(FORNECEDORES_URL).mock(
            return_value=httpx.Response(
                200,
                json={"totalRegistros": 0, "data": []},
            )
        )
        result = await client.consultar_fornecedor(cnpj="00000000000000")
        assert result.total == 0
        assert result.fornecedores == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fornecedor_fields_fallback(self) -> None:
        respx.get(FORNECEDORES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 1,
                    "resultado": [
                        {
                            "cpfCnpj": "99988877000166",
                            "nomeRazaoSocial": "Fornecedor Alt",
                            "municipioNome": "Rio de Janeiro",
                            "ufSigla": "RJ",
                            "porteEmpresa": "Grande",
                        }
                    ],
                },
            )
        )
        result = await client.consultar_fornecedor(cnpj="99988877000166")
        f = result.fornecedores[0]
        assert f.cnpj == "99988877000166"
        assert f.razao_social == "Fornecedor Alt"
        assert f.municipio == "Rio de Janeiro"
        assert f.uf == "RJ"
        assert f.porte == "Grande"


# ---------------------------------------------------------------------------
# consultar_orgao
# ---------------------------------------------------------------------------


class TestConsultarOrgao:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_orgao_by_cnpj(self) -> None:
        cnpj = "00394460000141"
        respx.get(f"{ORGAOS_URL}/{cnpj}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "cnpj": cnpj,
                    "razaoSocial": "Ministério da Educação",
                    "esferaNome": "Federal",
                    "poderNome": "Executivo",
                    "ufSigla": "DF",
                    "municipioNome": "Brasília",
                },
            )
        )
        result = await client.consultar_orgao(cnpj=cnpj)
        assert result.total == 1
        assert len(result.orgaos) == 1
        o = result.orgaos[0]
        assert o.cnpj == cnpj
        assert o.razao_social == "Ministério da Educação"
        assert o.esfera == "Federal"
        assert o.poder == "Executivo"
        assert o.uf == "DF"
        assert o.municipio == "Brasília"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        cnpj = "99999999999999"
        respx.get(f"{ORGAOS_URL}/{cnpj}").mock(
            return_value=httpx.Response(200, json={}),
        )
        result = await client.consultar_orgao(cnpj=cnpj)
        assert result.total == 0
        assert result.orgaos == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_orgao_fields_fallback(self) -> None:
        cnpj = "11111111000100"
        respx.get(f"{ORGAOS_URL}/{cnpj}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "cnpj": cnpj,
                    "razaoSocial": "Prefeitura Municipal",
                    "esferaId": "Municipal",
                    "poderId": "Executivo",
                    "ufNome": "São Paulo",
                    "municipioNome": "Campinas",
                },
            )
        )
        result = await client.consultar_orgao(cnpj=cnpj)
        o = result.orgaos[0]
        assert o.cnpj == cnpj
        assert o.razao_social == "Prefeitura Municipal"
        assert o.esfera == "Municipal"
        assert o.poder == "Executivo"
        assert o.uf == "São Paulo"
        assert o.municipio == "Campinas"


class TestContratacaoComplementos:
    cnpj = "00394460000141"
    ano = 2024
    sequencial = 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_consultar_detalhe_uses_query_api(self) -> None:
        url = f"{CONTRATACAO_DETALHE_URL}/{self.cnpj}/compras/{self.ano}/{self.sequencial}"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "orgaoEntidade": {"cnpj": self.cnpj},
                    "anoCompra": self.ano,
                    "sequencialCompra": self.sequencial,
                    "objetoCompra": "Objeto detalhado",
                },
            )
        )

        result = await client.consultar_contratacao_detalhe(self.cnpj, self.ano, self.sequencial)

        assert result.objeto == "Objeto detalhado"

    @pytest.mark.asyncio
    @respx.mock
    async def test_listar_itens(self) -> None:
        url = f"{ORGAOS_URL}/{self.cnpj}/compras/{self.ano}/{self.sequencial}/itens"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "numeroItem": 1,
                        "descricao": "Computador portátil",
                        "quantidade": 10,
                        "unidadeMedida": "UN",
                        "valorUnitarioEstimado": 5000,
                        "valorTotal": 50000,
                        "temResultado": True,
                    }
                ],
            )
        )

        result = await client.listar_itens_contratacao(self.cnpj, self.ano, self.sequencial)

        assert result.total == 1
        assert result.itens[0].descricao == "Computador portátil"
        assert result.itens[0].valor_total == 50000

    @pytest.mark.asyncio
    @respx.mock
    async def test_listar_documentos(self) -> None:
        url = f"{ORGAOS_URL}/{self.cnpj}/compras/{self.ano}/{self.sequencial}/arquivos"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "sequencialDocumento": 1,
                        "titulo": "Edital",
                        "tipoDocumentoNome": "Edital",
                        "url": "https://pncp.gov.br/documento.pdf",
                        "statusAtivo": True,
                    }
                ],
            )
        )

        result = await client.listar_documentos_contratacao(self.cnpj, self.ano, self.sequencial)

        assert result.total == 1
        assert result.documentos[0].titulo == "Edital"
        assert result.documentos[0].url == "https://pncp.gov.br/documento.pdf"

    @pytest.mark.asyncio
    @respx.mock
    async def test_listar_resultados_item(self) -> None:
        url = f"{ORGAOS_URL}/{self.cnpj}/compras/{self.ano}/{self.sequencial}/itens/1/resultados"
        respx.get(url).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "numeroItem": 1,
                        "sequencialResultado": 1,
                        "niFornecedor": "11222333000181",
                        "nomeRazaoSocialFornecedor": "Fornecedor Teste",
                        "quantidadeHomologada": 10,
                        "valorTotalHomologado": 48000,
                        "situacaoCompraItemResultadoNome": "Homologado",
                    }
                ],
            )
        )

        result = await client.listar_resultados_item_contratacao(
            self.cnpj, self.ano, self.sequencial, 1
        )

        assert result.total == 1
        assert result.resultados[0].fornecedor_nome == "Fornecedor Teste"
        assert result.resultados[0].valor_total_homologado == 48000

    @pytest.mark.asyncio
    @respx.mock
    async def test_listar_resultados_item_accepts_no_content(self) -> None:
        url = f"{ORGAOS_URL}/{self.cnpj}/compras/{self.ano}/{self.sequencial}/itens/1/resultados"
        respx.get(url).mock(return_value=httpx.Response(204))

        result = await client.listar_resultados_item_contratacao(
            self.cnpj, self.ano, self.sequencial, 1
        )

        assert result.total == 0
        assert result.resultados == []
