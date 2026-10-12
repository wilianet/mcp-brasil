"""HTTP client for the TJSP e-SAJ Consulta de Jurisprudência (CJSG).

Fluxo do portal, em uma única sessão (cookie JSESSIONID):
    GET  /cjsg/consultaCompleta.do           → abre a sessão
    POST /cjsg/resultadoCompleta.do          → registra a consulta na sessão
    GET  /cjsg/trocaDePagina.do?pagina=N     → página N de resultados (20 por página)

Rules (ADR-001):
    - client.py NEVER formats for LLM — returns Pydantic models
    - erro de fonte (rede, status, HTML inesperado) vira HttpClientError
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup, Tag

from mcp_brasil._shared.http_client import create_client
from mcp_brasil.exceptions import HttpClientError

from .constants import (
    ACORDAO_URL,
    CAMPO_BUSCA_EMENTA,
    CAMPO_BUSCA_INTEIRO_TEOR,
    CAMPO_DT_JULGAMENTO_FIM,
    CAMPO_DT_JULGAMENTO_INICIO,
    CAMPO_ORDENAR_POR,
    CAMPO_ORIGENS,
    CAMPO_TIPO_DECISAO,
    CJSG_BASE_URL,
    CONSULTA_PATH,
    ORDENAR_POR,
    ORIGEM_SEGUNDO_GRAU,
    PAGINA_PATH,
    RESULTADO_PATH,
    TIPO_DECISAO_ACORDAO,
)
from .schemas import AcordaoTJSP, ResultadoBuscaTJSP

logger = logging.getLogger(__name__)

_TOTAL_INPUT_ID = "totalResultadoAbaRetornoFiltro-A"
_ROTULOS = {
    "Classe/Assunto": "classe_assunto",
    "Relator(a)": "relator",
    "Comarca": "comarca",
    "Órgão julgador": "orgao_julgador",
    "Data do julgamento": "data_julgamento",
    "Data de publicação": "data_publicacao",
    "Ementa": "ementa",
}


def _build_form(
    query: str,
    somente_ementa: bool,
    data_julgamento_inicio: str | None,
    data_julgamento_fim: str | None,
    ordenar_por: str,
) -> dict[str, str]:
    form = {
        CAMPO_BUSCA_EMENTA if somente_ementa else CAMPO_BUSCA_INTEIRO_TEOR: query,
        CAMPO_TIPO_DECISAO: TIPO_DECISAO_ACORDAO,
        CAMPO_ORIGENS: ORIGEM_SEGUNDO_GRAU,
        CAMPO_ORDENAR_POR: ORDENAR_POR[ordenar_por],
    }
    if data_julgamento_inicio:
        form[CAMPO_DT_JULGAMENTO_INICIO] = data_julgamento_inicio
    if data_julgamento_fim:
        form[CAMPO_DT_JULGAMENTO_FIM] = data_julgamento_fim
    return form


async def buscar_acordaos(
    query: str,
    pagina: int = 1,
    somente_ementa: bool = False,
    data_julgamento_inicio: str | None = None,
    data_julgamento_fim: str | None = None,
    ordenar_por: str = "publicacao",
) -> ResultadoBuscaTJSP:
    """Search acórdãos in the CJSG and return one page of parsed results.

    Raises:
        HttpClientError: rede, timeout, status >= 400 ou HTML sem a tabela de resultados.
    """
    form = _build_form(
        query, somente_ementa, data_julgamento_inicio, data_julgamento_fim, ordenar_por
    )
    try:
        async with create_client(
            base_url=CJSG_BASE_URL, headers={"Accept": "text/html,application/xhtml+xml"}
        ) as client:
            await client.get(CONSULTA_PATH)
            resp = await client.post(RESULTADO_PATH, data=form)
            resp.raise_for_status()
            resp = await client.get(
                PAGINA_PATH, params={"tipoDeDecisao": TIPO_DECISAO_ACORDAO, "pagina": pagina}
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HttpClientError(f"TJSP CJSG: {type(exc).__name__}: {exc}") from exc

    return _parse_resultados(resp.text, pagina)


def _parse_resultados(html: str, pagina: int) -> ResultadoBuscaTJSP:
    """Parse a results page. HTML sem o contador de resultados é tratado como falha da fonte."""
    soup = BeautifulSoup(html, "lxml")
    total_input = soup.find("input", id=_TOTAL_INPUT_ID)
    if not isinstance(total_input, Tag):
        logger.warning("TJSP CJSG: HTML sem a tabela de resultados (%d bytes)", len(html))
        raise HttpClientError("TJSP CJSG: resposta sem a tabela de resultados (layout mudou?)")
    total = int(str(total_input.get("value") or "0"))
    acordaos = [
        a
        for tr in soup.find_all("tr", class_="fundocinza1")
        if isinstance(tr, Tag) and (a := _parse_acordao(tr)) is not None
    ]
    return ResultadoBuscaTJSP(total=total, pagina=pagina, acordaos=acordaos)


def _texto(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def _parse_acordao(tr: Tag) -> AcordaoTJSP | None:
    link = tr.find("a", class_="downloadEmenta")
    if not isinstance(link, Tag):
        return None
    numero = _texto(link)
    cd_acordao = link.get("cdacordao")
    campos: dict[str, str] = {}
    for strong in tr.find_all("strong"):
        if not isinstance(strong, Tag) or not isinstance(strong.parent, Tag):
            continue
        rotulo = _texto(strong).rstrip(":")
        chave = _ROTULOS.get(rotulo)
        if chave is None or chave in campos:
            continue
        valor = _texto(strong.parent)
        campos[chave] = (
            valor[len(_texto(strong)) :].strip() if valor.startswith(_texto(strong)) else valor
        )

    # O portal repete a ementa resumida e a completa; o div "sem formatação" tem a íntegra limpa
    sem_formatacao = tr.find("div", class_="mensagemSemFormatacao")
    if isinstance(sem_formatacao, Tag) and _texto(sem_formatacao):
        campos["ementa"] = _texto(sem_formatacao)

    classe, assunto = None, None
    if "classe_assunto" in campos:
        partes = campos["classe_assunto"].split("/", 1)
        classe = partes[0].strip() or None
        assunto = partes[1].strip() if len(partes) > 1 else None

    return AcordaoTJSP(
        numero_processo=numero,
        cd_acordao=str(cd_acordao) if cd_acordao else None,
        classe=classe,
        assunto=assunto,
        relator=campos.get("relator"),
        comarca=campos.get("comarca"),
        orgao_julgador=campos.get("orgao_julgador"),
        data_julgamento=campos.get("data_julgamento"),
        data_publicacao=campos.get("data_publicacao"),
        ementa=campos.get("ementa"),
        url=ACORDAO_URL.format(cd_acordao=cd_acordao) if cd_acordao else None,
    )
