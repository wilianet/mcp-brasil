"""HTTP client for the PNCP API.

Endpoints (verified against OpenAPI spec at /v3/api-docs):
    - /contratacoes/publicacao  → buscar_contratacoes (requires dates + modalidade)
    - /contratos                → buscar_contratos (requires dates)
    - /atas                     → buscar_atas (requires dates)
    - /fornecedores             → consultar_fornecedor
    - /orgaos                   → consultar_orgao

IMPORTANT: The PNCP API has NO text search parameter (`q`).
All text filtering is done client-side after fetching results.
Date format for all endpoints: YYYYMMDD.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from math import ceil
from typing import Any

from mcp_brasil._shared.http_client import http_get
from mcp_brasil._shared.validators import normalize_cnpj

from .constants import (
    ATAS_ATUALIZACAO_URL,
    ATAS_URL,
    CONTRATACAO_DETALHE_URL,
    CONTRATACOES_ATUALIZACAO_URL,
    CONTRATACOES_PROPOSTA_URL,
    CONTRATACOES_URL,
    CONTRATOS_ATUALIZACAO_URL,
    CONTRATOS_URL,
    FORNECEDORES_URL,
    INSTRUMENTOS_COBRANCA_URL,
    MAX_DATE_RANGE_DAYS,
    ORGAOS_URL,
    PCA_URL,
)
from .schemas import (
    AtaRegistroPreco,
    AtaResultado,
    Contratacao,
    ContratacaoResultado,
    Contrato,
    ContratoResultado,
    DocumentoContratacao,
    DocumentosContratacaoResultado,
    Fornecedor,
    FornecedorResultado,
    InstrumentoCobranca,
    InstrumentoCobrancaResultado,
    ItemContratacao,
    ItemPca,
    ItensContratacaoResultado,
    OrgaoContratante,
    OrgaoResultado,
    PaginationInfo,
    Pca,
    PcaResultado,
    ResultadoItemContratacao,
    ResultadosItemContratacaoResultado,
)

_DATE_RE = re.compile(r"^\d{8}$")


def normalizar_data(data: str) -> str:
    """Normalize a date string to YYYYMMDD format.

    Accepts: YYYYMMDD, YYYY-MM-DD, DD/MM/YYYY.
    Raises ValueError for invalid formats.
    """
    cleaned = data.strip()

    # Already YYYYMMDD
    if _DATE_RE.match(cleaned):
        datetime.strptime(cleaned, "%Y%m%d")  # validate
        return cleaned

    # YYYY-MM-DD
    if len(cleaned) == 10 and cleaned[4] == "-":
        dt = datetime.strptime(cleaned, "%Y-%m-%d")
        return dt.strftime("%Y%m%d")

    # DD/MM/YYYY
    if len(cleaned) == 10 and cleaned[2] == "/":
        dt = datetime.strptime(cleaned, "%d/%m/%Y")
        return dt.strftime("%Y%m%d")

    msg = f"Formato de data inválido: '{data}'. Use YYYYMMDD, YYYY-MM-DD ou DD/MM/YYYY."
    raise ValueError(msg)


def validar_periodo(data_inicial: str, data_final: str) -> None:
    """Validate that the date range does not exceed MAX_DATE_RANGE_DAYS."""
    dt_ini = datetime.strptime(data_inicial, "%Y%m%d")
    dt_fim = datetime.strptime(data_final, "%Y%m%d")
    if dt_fim < dt_ini:
        msg = f"data_final ({data_final}) é anterior a data_inicial ({data_inicial})."
        raise ValueError(msg)
    diff = (dt_fim - dt_ini).days
    if diff > MAX_DATE_RANGE_DAYS:
        msg = (
            f"Período de {diff} dias excede o máximo de {MAX_DATE_RANGE_DAYS} dias. "
            f"Reduza o intervalo entre data_inicial e data_final."
        )
        raise ValueError(msg)


def _default_data_inicial() -> str:
    """Return 30 days ago in YYYYMMDD format (sensible default)."""
    return (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")


def _default_data_final() -> str:
    """Return today in YYYYMMDD format."""
    return datetime.now().strftime("%Y%m%d")


def _filtrar_por_texto(items: list[dict[str, Any]], texto: str | None) -> list[dict[str, Any]]:
    """Filter API results client-side by text match on relevant fields."""
    if not texto:
        return items
    termo = texto.lower()
    filtered = []
    for item in items:
        searchable = " ".join(
            str(v).lower()
            for v in [
                item.get("objetoCompra"),
                item.get("objetoContrato"),
                item.get("objetoAta"),
                item.get("objetoContratacao"),
                (item.get("orgaoEntidade") or {}).get("razaoSocial"),
                (item.get("fornecedor") or {}).get("razaoSocial"),
                (item.get("fornecedor") or {}).get("nomeRazaoSocial"),
                item.get("nomeRazaoSocialFornecedor"),
            ]
            if v
        )
        if termo in searchable:
            filtered.append(item)
    return filtered


def _extrair_pagina(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Extract records and pagination metadata from both PNCP response shapes."""
    raw_items = data.get("data", data.get("resultado", []))
    items = raw_items if isinstance(raw_items, list) else []
    total_registros = data.get("totalRegistros", data.get("count"))
    total_paginas = data.get("totalPaginas")
    return items, total_registros, total_paginas


async def _buscar_paginas_com_texto(
    url: str,
    params: dict[str, str],
    *,
    texto: str | None,
    pagina: int,
    tamanho: int,
    max_paginas: int,
) -> tuple[list[dict[str, Any]], PaginationInfo]:
    """Fetch enough API pages for a truthful client-side text search.

    The PNCP query API has no full-text parameter. When ``texto`` is present,
    this helper walks every available page (up to ``max_paginas``) before
    applying the local filter. Without text it preserves the original one-page
    behavior and exposes that scope in the returned metadata.
    """
    if pagina < 1:
        raise ValueError("pagina deve ser maior ou igual a 1.")
    if max_paginas < 1:
        raise ValueError("max_paginas deve ser maior ou igual a 1.")

    pagina_atual = pagina
    paginas_consultadas = 0
    acumulados: list[dict[str, Any]] = []
    total_registros: int | None = None
    total_paginas: int | None = None

    while True:
        page_params = {**params, "pagina": str(pagina_atual)}
        data: dict[str, Any] = await http_get(url, params=page_params)
        items, page_total, page_count = _extrair_pagina(data)
        acumulados.extend(items)
        paginas_consultadas += 1

        if isinstance(page_total, int):
            total_registros = page_total
        if isinstance(page_count, int):
            total_paginas = page_count
        elif total_paginas is None and total_registros is not None:
            total_paginas = max(1, ceil(total_registros / tamanho))

        if not texto:
            break
        if total_paginas is None or pagina_atual >= total_paginas:
            break
        if paginas_consultadas >= max_paginas:
            break
        pagina_atual += 1

    limite_atingido = bool(
        texto
        and total_paginas is not None
        and pagina_atual < total_paginas
        and paginas_consultadas >= max_paginas
    )
    pesquisa_completa = bool(
        total_paginas is not None
        and pagina == 1
        and pagina_atual >= total_paginas
        and not limite_atingido
    )
    paginacao = PaginationInfo(
        pagina_inicial=pagina,
        paginas_consultadas=paginas_consultadas,
        total_paginas=total_paginas,
        total_registros_fonte=total_registros,
        pesquisa_completa=pesquisa_completa,
        limite_paginas_atingido=limite_atingido,
    )
    return _filtrar_por_texto(acumulados, texto), paginacao


def _parse_contratacao(item: dict[str, Any]) -> Contratacao:
    """Parse a raw API response item into a Contratacao model."""
    orgao = item.get("orgaoEntidade", {}) or {}
    return Contratacao(
        orgao_cnpj=orgao.get("cnpj"),
        orgao_nome=orgao.get("razaoSocial"),
        ano=item.get("anoCompra"),
        numero_sequencial=item.get("sequencialCompra"),
        numero_controle_pncp=item.get("numeroControlePNCP"),
        objeto=item.get("objetoCompra"),
        modalidade_id=item.get("modalidadeId"),
        modalidade_nome=item.get("modalidadeNome"),
        situacao_id=item.get("situacaoCompraId"),
        situacao_nome=item.get("situacaoCompraNome"),
        valor_estimado=item.get("valorTotalEstimado"),
        valor_homologado=item.get("valorTotalHomologado"),
        data_publicacao=item.get("dataPublicacaoPncp"),
        data_abertura=item.get("dataAberturaProposta"),
        uf=orgao.get("ufSigla"),
        municipio=orgao.get("municipioNome"),
        esfera=orgao.get("esferaNome"),
        link_pncp=item.get("linkPncp"),
    )


def _parse_contrato(item: dict[str, Any]) -> Contrato:
    """Parse a raw API response item into a Contrato model."""
    orgao = item.get("orgaoEntidade", {}) or {}
    fornecedor = item.get("fornecedor", {}) or {}
    return Contrato(
        orgao_cnpj=orgao.get("cnpj"),
        orgao_nome=orgao.get("razaoSocial"),
        numero_contrato=item.get("numeroContratoEmpenho"),
        objeto=item.get("objetoContrato"),
        fornecedor_cnpj=fornecedor.get("cnpj") or fornecedor.get("cpfCnpj"),
        fornecedor_nome=fornecedor.get("razaoSocial") or fornecedor.get("nomeRazaoSocial"),
        valor_inicial=item.get("valorInicial"),
        valor_final=item.get("valorFinal"),
        vigencia_inicio=item.get("dataVigenciaInicio"),
        vigencia_fim=item.get("dataVigenciaFim"),
        data_publicacao=item.get("dataPublicacaoPncp"),
        situacao=item.get("nomeStatus"),
    )


def _parse_ata(item: dict[str, Any]) -> AtaRegistroPreco:
    """Parse a raw API response item into an AtaRegistroPreco model."""
    orgao = item.get("orgaoEntidade", {}) or {}
    fornecedor = item.get("fornecedor", {}) or {}
    return AtaRegistroPreco(
        orgao_cnpj=orgao.get("cnpj"),
        orgao_nome=orgao.get("razaoSocial"),
        numero_ata=item.get("numeroAta") or item.get("numeroAtaRegistroPreco"),
        objeto=(
            item.get("objetoAta") or item.get("objetoContrato") or item.get("objetoContratacao")
        ),
        fornecedor_cnpj=fornecedor.get("cnpj") or fornecedor.get("cpfCnpj"),
        fornecedor_nome=fornecedor.get("razaoSocial") or fornecedor.get("nomeRazaoSocial"),
        valor_total=item.get("valorTotal") or item.get("valorInicial"),
        vigencia_inicio=item.get("dataVigenciaInicio") or item.get("vigenciaInicio"),
        vigencia_fim=item.get("dataVigenciaFim") or item.get("vigenciaFim"),
        situacao=item.get("nomeStatus"),
    )


async def buscar_contratacoes(
    data_inicial: str,
    data_final: str,
    modalidade: int,
    *,
    texto: str | None = None,
    uf: str | None = None,
    cnpj_orgao: str | None = None,
    modo_disputa: int | None = None,
    pagina: int = 1,
    tamanho: int = 10,
    max_paginas: int = 100,
) -> ContratacaoResultado:
    """Search published procurement processes.

    Required by the API: dataInicial, dataFinal, codigoModalidadeContratacao.
    Text filtering is done client-side (API has no text search).
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "codigoModalidadeContratacao": str(modalidade),
        "pagina": str(pagina),
        "tamanhoPagina": str(min(tamanho, 50)),
    }
    if uf:
        params["uf"] = uf
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if modo_disputa:
        params["codigoModoDisputa"] = str(modo_disputa)

    items, paginacao = await _buscar_paginas_com_texto(
        CONTRATACOES_URL,
        params,
        texto=texto,
        pagina=pagina,
        tamanho=min(tamanho, 50),
        max_paginas=max_paginas,
    )

    contratacoes = [_parse_contratacao(item) for item in items]
    return ContratacaoResultado(
        total=len(contratacoes)
        if texto
        else (paginacao.total_registros_fonte or len(contratacoes)),
        contratacoes=contratacoes,
        paginacao=paginacao,
    )


async def buscar_contratos(
    data_inicial: str,
    data_final: str,
    *,
    texto: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
    max_paginas: int = 100,
) -> ContratoResultado:
    """Search public contracts.

    Required by the API: dataInicial, dataFinal.
    Text filtering is done client-side (API has no text search).
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(tamanho, 500)),
    }
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao

    items, paginacao = await _buscar_paginas_com_texto(
        CONTRATOS_URL,
        params,
        texto=texto,
        pagina=pagina,
        tamanho=min(tamanho, 500),
        max_paginas=max_paginas,
    )

    contratos = [_parse_contrato(item) for item in items]
    return ContratoResultado(
        total=len(contratos) if texto else (paginacao.total_registros_fonte or len(contratos)),
        contratos=contratos,
        paginacao=paginacao,
    )


async def buscar_atas(
    data_inicial: str,
    data_final: str,
    *,
    texto: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
    max_paginas: int = 100,
) -> AtaResultado:
    """Search price record minutes (atas de registro de preço).

    Required by the API: dataInicial, dataFinal.
    Filters by validity period (vigência), not publication date.
    Text filtering is done client-side (API has no text search).
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(tamanho, 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    items, paginacao = await _buscar_paginas_com_texto(
        ATAS_URL,
        params,
        texto=texto,
        pagina=pagina,
        tamanho=min(tamanho, 500),
        max_paginas=max_paginas,
    )

    atas = [_parse_ata(item) for item in items]
    return AtaResultado(
        total=len(atas) if texto else (paginacao.total_registros_fonte or len(atas)),
        atas=atas,
        paginacao=paginacao,
    )


def _parse_fornecedor(item: dict[str, Any]) -> Fornecedor:
    """Parse a raw API response item into a Fornecedor model."""
    return Fornecedor(
        cnpj=item.get("cnpj") or item.get("cpfCnpj"),
        razao_social=item.get("razaoSocial") or item.get("nomeRazaoSocial"),
        nome_fantasia=item.get("nomeFantasia"),
        municipio=(
            item.get("municipio", {}).get("nome")
            if isinstance(item.get("municipio"), dict)
            else item.get("municipioNome")
        ),
        uf=(
            item.get("uf", {}).get("sigla")
            if isinstance(item.get("uf"), dict)
            else item.get("ufSigla")
        ),
        porte=item.get("porte") or item.get("porteEmpresa"),
        data_abertura=item.get("dataAbertura"),
    )


_ESFERA_MAP: dict[str, str] = {"F": "Federal", "E": "Estadual", "M": "Municipal", "D": "Distrital"}
_PODER_MAP: dict[str, str] = {"E": "Executivo", "L": "Legislativo", "J": "Judiciário"}


def _parse_orgao(item: dict[str, Any]) -> OrgaoContratante:
    """Parse a raw API response item into an OrgaoContratante model."""
    esfera_id = item.get("esferaId") or ""
    poder_id = item.get("poderId") or ""
    return OrgaoContratante(
        cnpj=item.get("cnpj"),
        razao_social=item.get("razaoSocial"),
        esfera=item.get("esferaNome") or _ESFERA_MAP.get(esfera_id, esfera_id),
        poder=item.get("poderNome") or _PODER_MAP.get(poder_id, poder_id),
        uf=item.get("ufSigla") or item.get("ufNome"),
        municipio=item.get("municipioNome"),
    )


async def consultar_fornecedor(cnpj: str) -> FornecedorResultado:
    """Search supplier by CNPJ."""
    params: dict[str, str] = {"cnpj": cnpj}
    data: dict[str, Any] = await http_get(FORNECEDORES_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    fornecedores = [_parse_fornecedor(item) for item in items] if isinstance(items, list) else []
    return FornecedorResultado(
        total=data.get("totalRegistros", data.get("count", len(fornecedores))),
        fornecedores=fornecedores,
    )


async def consultar_orgao(cnpj: str) -> OrgaoResultado:
    """Fetch a contracting body by CNPJ.

    The PNCP API only supports lookup by exact CNPJ at /api/pncp/v1/orgaos/{cnpj}.
    Text search is not available in the API.
    """
    from mcp_brasil.exceptions import HttpClientError

    url = f"{ORGAOS_URL}/{cnpj}"
    try:
        data: dict[str, Any] = await http_get(url)
    except HttpClientError:
        return OrgaoResultado(total=0, orgaos=[])
    if isinstance(data, dict) and data.get("cnpj"):
        orgao = _parse_orgao(data)
        return OrgaoResultado(total=1, orgaos=[orgao])
    return OrgaoResultado(total=0, orgaos=[])


async def buscar_contratacoes_abertas(
    data_final: str,
    *,
    texto: str | None = None,
    modalidade: int | None = None,
    uf: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
    max_paginas: int = 100,
) -> ContratacaoResultado:
    """Search procurement processes with open proposal submission.

    API: GET /v1/contratacoes/proposta
    Required: dataFinal, pagina.
    """
    data_fim = normalizar_data(data_final)
    params: dict[str, str] = {
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 50)),
    }
    if modalidade:
        params["codigoModalidadeContratacao"] = str(modalidade)
    if uf:
        params["uf"] = uf
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    tamanho_efetivo = min(max(tamanho, 10), 50)
    items, paginacao = await _buscar_paginas_com_texto(
        CONTRATACOES_PROPOSTA_URL,
        params,
        texto=texto,
        pagina=pagina,
        tamanho=tamanho_efetivo,
        max_paginas=max_paginas,
    )
    contratacoes = [_parse_contratacao(item) for item in items]
    return ContratacaoResultado(
        total=len(contratacoes)
        if texto
        else (paginacao.total_registros_fonte or len(contratacoes)),
        contratacoes=contratacoes,
        paginacao=paginacao,
    )


async def buscar_contratacoes_atualizadas(
    data_inicial: str,
    data_final: str,
    modalidade: int,
    *,
    texto: str | None = None,
    uf: str | None = None,
    cnpj_orgao: str | None = None,
    modo_disputa: int | None = None,
    pagina: int = 1,
    tamanho: int = 10,
    max_paginas: int = 100,
) -> ContratacaoResultado:
    """Search procurement processes by global update date.

    API: GET /v1/contratacoes/atualizacao
    Required: dataInicial, dataFinal, codigoModalidadeContratacao, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "codigoModalidadeContratacao": str(modalidade),
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 50)),
    }
    if uf:
        params["uf"] = uf
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if modo_disputa:
        params["codigoModoDisputa"] = str(modo_disputa)

    tamanho_efetivo = min(max(tamanho, 10), 50)
    items, paginacao = await _buscar_paginas_com_texto(
        CONTRATACOES_ATUALIZACAO_URL,
        params,
        texto=texto,
        pagina=pagina,
        tamanho=tamanho_efetivo,
        max_paginas=max_paginas,
    )
    contratacoes = [_parse_contratacao(item) for item in items]
    return ContratacaoResultado(
        total=len(contratacoes)
        if texto
        else (paginacao.total_registros_fonte or len(contratacoes)),
        contratacoes=contratacoes,
        paginacao=paginacao,
    )


async def buscar_contratos_atualizados(
    data_inicial: str,
    data_final: str,
    *,
    texto: str | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
    max_paginas: int = 100,
) -> ContratoResultado:
    """Search contracts by global update date.

    API: GET /v1/contratos/atualizacao
    Required: dataInicial, dataFinal, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao

    tamanho_efetivo = min(max(tamanho, 10), 500)
    items, paginacao = await _buscar_paginas_com_texto(
        CONTRATOS_ATUALIZACAO_URL,
        params,
        texto=texto,
        pagina=pagina,
        tamanho=tamanho_efetivo,
        max_paginas=max_paginas,
    )
    contratos = [_parse_contrato(item) for item in items]
    return ContratoResultado(
        total=len(contratos) if texto else (paginacao.total_registros_fonte or len(contratos)),
        contratos=contratos,
        paginacao=paginacao,
    )


async def buscar_atas_atualizadas(
    data_inicial: str,
    data_final: str,
    *,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> AtaResultado:
    """Search price record minutes by global update date.

    API: GET /v1/atas/atualizacao
    Required: dataInicial, dataFinal, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    data: dict[str, Any] = await http_get(ATAS_ATUALIZACAO_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []

    atas: list[AtaRegistroPreco] = []
    for item in items:
        atas.append(
            AtaRegistroPreco(
                orgao_cnpj=item.get("cnpjOrgao"),
                orgao_nome=item.get("nomeOrgao"),
                numero_ata=item.get("numeroAtaRegistroPreco"),
                objeto=item.get("objetoContratacao"),
                vigencia_inicio=item.get("vigenciaInicio"),
                vigencia_fim=item.get("vigenciaFim"),
            )
        )
    return AtaResultado(
        total=data.get("totalRegistros", len(atas)),
        atas=atas,
    )


async def consultar_contratacao_detalhe(
    cnpj: str,
    ano: int,
    sequencial: int,
) -> Contratacao:
    """Fetch a specific procurement process detail.

    API: GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
    """
    url = f"{CONTRATACAO_DETALHE_URL}/{normalize_cnpj(cnpj)}/compras/{ano}/{sequencial}"
    data: dict[str, Any] = await http_get(url)
    return _parse_contratacao(data)


def _parse_item_contratacao(item: dict[str, Any]) -> ItemContratacao:
    """Parse an item returned by the PNCP integration API."""
    return ItemContratacao(
        numero_item=item.get("numeroItem"),
        descricao=item.get("descricao"),
        material_ou_servico=item.get("materialOuServico"),
        material_ou_servico_nome=item.get("materialOuServicoNome"),
        quantidade=item.get("quantidade"),
        unidade_medida=item.get("unidadeMedida"),
        valor_unitario_estimado=item.get("valorUnitarioEstimado"),
        valor_total=item.get("valorTotal"),
        orcamento_sigiloso=item.get("orcamentoSigiloso"),
        criterio_julgamento_nome=item.get("criterioJulgamentoNome"),
        situacao_nome=item.get("situacaoCompraItemNome"),
        tipo_beneficio_nome=item.get("tipoBeneficioNome"),
        data_inclusao=item.get("dataInclusao"),
        data_atualizacao=item.get("dataAtualizacao"),
        tem_resultado=item.get("temResultado"),
        codigo_catalogo=item.get("catalogoCodigoItem"),
        informacao_complementar=item.get("informacaoComplementar"),
    )


def _parse_documento_contratacao(item: dict[str, Any]) -> DocumentoContratacao:
    """Parse procurement document metadata returned by PNCP."""
    return DocumentoContratacao(
        sequencial_documento=item.get("sequencialDocumento"),
        titulo=item.get("titulo"),
        tipo_documento_id=item.get("tipoDocumentoId"),
        tipo_documento_nome=item.get("tipoDocumentoNome"),
        tipo_documento_descricao=item.get("tipoDocumentoDescricao"),
        url=item.get("url"),
        uri=item.get("uri"),
        status_ativo=item.get("statusAtivo"),
        data_publicacao=item.get("dataPublicacaoPncp"),
    )


def _parse_resultado_item(item: dict[str, Any]) -> ResultadoItemContratacao:
    """Parse a homologated item result returned by PNCP."""
    return ResultadoItemContratacao(
        numero_item=item.get("numeroItem"),
        sequencial_resultado=item.get("sequencialResultado"),
        fornecedor_documento=item.get("niFornecedor"),
        fornecedor_nome=item.get("nomeRazaoSocialFornecedor"),
        tipo_pessoa=item.get("tipoPessoa"),
        quantidade_homologada=item.get("quantidadeHomologada"),
        valor_unitario_homologado=item.get("valorUnitarioHomologado"),
        valor_total_homologado=item.get("valorTotalHomologado"),
        percentual_desconto=item.get("percentualDesconto"),
        situacao_nome=item.get("situacaoCompraItemResultadoNome"),
        porte_fornecedor_nome=item.get("porteFornecedorNome"),
        data_resultado=item.get("dataResultado"),
        data_inclusao=item.get("dataInclusao"),
        data_atualizacao=item.get("dataAtualizacao"),
    )


def _integration_items(data: Any) -> list[dict[str, Any]]:
    """Normalize list and wrapped-list responses from the integration API."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("data", data.get("resultado", []))
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


async def listar_itens_contratacao(
    cnpj: str,
    ano: int,
    sequencial: int,
) -> ItensContratacaoResultado:
    """List all items from a specific PNCP procurement process."""
    cnpj_normalizado = normalize_cnpj(cnpj)
    url = f"{ORGAOS_URL}/{cnpj_normalizado}/compras/{ano}/{sequencial}/itens"
    data: Any = await http_get(url)
    itens = [_parse_item_contratacao(item) for item in _integration_items(data)]
    return ItensContratacaoResultado(total=len(itens), itens=itens)


async def listar_documentos_contratacao(
    cnpj: str,
    ano: int,
    sequencial: int,
) -> DocumentosContratacaoResultado:
    """List documents and attachments from a specific procurement process."""
    cnpj_normalizado = normalize_cnpj(cnpj)
    url = f"{ORGAOS_URL}/{cnpj_normalizado}/compras/{ano}/{sequencial}/arquivos"
    data: Any = await http_get(url)
    documentos = [_parse_documento_contratacao(item) for item in _integration_items(data)]
    return DocumentosContratacaoResultado(total=len(documentos), documentos=documentos)


async def listar_resultados_item_contratacao(
    cnpj: str,
    ano: int,
    sequencial: int,
    numero_item: int,
) -> ResultadosItemContratacaoResultado:
    """List homologated results for one procurement item."""
    cnpj_normalizado = normalize_cnpj(cnpj)
    url = (
        f"{ORGAOS_URL}/{cnpj_normalizado}/compras/{ano}/{sequencial}"
        f"/itens/{numero_item}/resultados"
    )
    data: Any = await http_get(url)
    resultados = [_parse_resultado_item(item) for item in _integration_items(data)]
    return ResultadosItemContratacaoResultado(total=len(resultados), resultados=resultados)


def _parse_item_pca(item: dict[str, Any]) -> ItemPca:
    """Parse a PCA item from API response."""
    return ItemPca(
        numero_item=item.get("numeroItem"),
        descricao=item.get("descricaoItem"),
        quantidade_estimada=item.get("quantidadeEstimada"),
        valor_unitario=item.get("valorUnitario"),
        valor_total=item.get("valorTotal"),
        unidade_fornecimento=item.get("unidadeFornecimento"),
        categoria=item.get("categoriaItemPcaNome") or item.get("nomeClassificacaoCatalogo"),
        data_desejada=item.get("dataDesejada"),
    )


def _parse_pca(item: dict[str, Any]) -> Pca:
    """Parse a PCA from API response."""
    raw_itens = item.get("itens", [])
    return Pca(
        orgao_cnpj=item.get("orgaoEntidadeCnpj"),
        orgao_nome=item.get("orgaoEntidadeRazaoSocial"),
        ano=item.get("anoPca"),
        unidade_nome=item.get("nomeUnidade"),
        id_pca=item.get("idPcaPncp"),
        data_publicacao=item.get("dataPublicacaoPNCP"),
        itens=[_parse_item_pca(i) for i in raw_itens] if isinstance(raw_itens, list) else [],
    )


async def buscar_pca(
    ano: int,
    codigo_classificacao: str = "0",
    *,
    pagina: int = 1,
    tamanho: int = 10,
) -> PcaResultado:
    """Search Annual Procurement Plans (PCA) by year.

    API: GET /v1/pca/
    Required: anoPca, codigoClassificacaoSuperior, pagina.
    """
    params: dict[str, str] = {
        "anoPca": str(ano),
        "codigoClassificacaoSuperior": codigo_classificacao,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    data: dict[str, Any] = await http_get(PCA_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    pcas = [_parse_pca(item) for item in items]
    return PcaResultado(
        total=data.get("totalRegistros", len(pcas)),
        pcas=pcas,
    )


async def buscar_pca_atualizacao(
    data_inicio: str,
    data_fim: str,
    *,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> PcaResultado:
    """Search PCA by global update date.

    API: GET /v1/pca/atualizacao
    Required: dataInicio, dataFim, pagina.
    """
    dt_ini = normalizar_data(data_inicio)
    dt_fim = normalizar_data(data_fim)
    validar_periodo(dt_ini, dt_fim)

    params: dict[str, str] = {
        "dataInicio": dt_ini,
        "dataFim": dt_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao

    data: dict[str, Any] = await http_get(f"{PCA_URL}/atualizacao", params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    pcas = [_parse_pca(item) for item in items]
    return PcaResultado(
        total=data.get("totalRegistros", len(pcas)),
        pcas=pcas,
    )


async def buscar_pca_usuario(
    ano: int,
    id_usuario: int,
    *,
    cnpj_orgao: str | None = None,
    codigo_classificacao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> PcaResultado:
    """Search PCA items by year and user ID.

    API: GET /v1/pca/usuario
    Required: anoPca, idUsuario, pagina.
    """
    params: dict[str, str] = {
        "anoPca": str(ano),
        "idUsuario": str(id_usuario),
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 500)),
    }
    if cnpj_orgao:
        params["cnpj"] = cnpj_orgao
    if codigo_classificacao:
        params["codigoClassificacaoSuperior"] = codigo_classificacao

    data: dict[str, Any] = await http_get(f"{PCA_URL}/usuario", params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    pcas = [_parse_pca(item) for item in items]
    return PcaResultado(
        total=data.get("totalRegistros", len(pcas)),
        pcas=pcas,
    )


def _parse_instrumento_cobranca(item: dict[str, Any]) -> InstrumentoCobranca:
    """Parse an instrument of billing from API response."""
    contrato = item.get("recuperarContratoDTO", {}) or {}
    tipo = item.get("tipoInstrumentoCobranca", {}) or {}
    nfe = item.get("notaFiscalEletronica", {}) or {}
    return InstrumentoCobranca(
        cnpj_orgao=item.get("cnpj"),
        ano_contrato=contrato.get("anoContrato"),
        numero_instrumento=item.get("numeroInstrumentoCobranca"),
        tipo_nome=tipo.get("nome"),
        data_emissao=item.get("dataEmissaoDocumento"),
        objeto_contrato=contrato.get("objetoContrato"),
        fornecedor_nome=nfe.get("nomeEmitente") or contrato.get("nomeRazaoSocialFornecedor"),
        fornecedor_cnpj=nfe.get("niEmitente") or contrato.get("niFornecedor"),
        valor_nf=nfe.get("valorNotaFiscal"),
        chave_nfe=item.get("chaveNFe"),
    )


async def buscar_instrumentos_cobranca(
    data_inicial: str,
    data_final: str,
    *,
    tipo: int | None = None,
    cnpj_orgao: str | None = None,
    pagina: int = 1,
    tamanho: int = 10,
) -> InstrumentoCobrancaResultado:
    """Search billing instruments (invoices) by inclusion date.

    API: GET /v1/instrumentoscobranca/inclusao
    Required: dataInicial, dataFinal, pagina.
    """
    data_ini = normalizar_data(data_inicial)
    data_fim = normalizar_data(data_final)
    validar_periodo(data_ini, data_fim)

    params: dict[str, str] = {
        "dataInicial": data_ini,
        "dataFinal": data_fim,
        "pagina": str(pagina),
        "tamanhoPagina": str(min(max(tamanho, 10), 100)),
    }
    if tipo:
        params["tipoInstrumentoCobranca"] = str(tipo)
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao

    data: dict[str, Any] = await http_get(INSTRUMENTOS_COBRANCA_URL, params=params)
    items = data.get("data", data.get("resultado", []))
    if not isinstance(items, list):
        items = []
    instrumentos = [_parse_instrumento_cobranca(item) for item in items]
    return InstrumentoCobrancaResultado(
        total=data.get("totalRegistros", len(instrumentos)),
        instrumentos=instrumentos,
    )
