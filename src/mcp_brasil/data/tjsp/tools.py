"""Tool functions for the TJSP feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

import re

from mcp_brasil.exceptions import HttpClientError

from . import client
from .constants import DATA_FORMATO, ORDENAR_POR, PAGE_SIZE

_DATA_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_EMENTA_MAX = 500


def _ementa(texto: str | None) -> str:
    if not texto:
        return "—"
    return texto if len(texto) <= _EMENTA_MAX else texto[:_EMENTA_MAX] + "..."


async def buscar_acordaos_tjsp(
    query: str,
    pagina: int = 1,
    somente_ementa: bool = False,
    data_julgamento_inicio: str | None = None,
    data_julgamento_fim: str | None = None,
    ordenar_por: str = "publicacao",
) -> str:
    """Busca acórdãos de 2º grau do Tribunal de Justiça de São Paulo (TJSP).

    Consulta a Consulta de Jurisprudência do e-SAJ (CJSG) e devolve, por acórdão,
    número CNJ, classe/assunto, relator, comarca, órgão julgador, datas de
    julgamento e publicação e a ementa. 20 acórdãos por página.

    Use para: precedentes do TJSP em matéria cível, consumidor, empresarial,
    família e pública (apelação, agravo, embargos). Não use para: STF, STJ ou
    TST (use buscar_jurisprudencia_*), decisões monocráticas, nem para obter o
    inteiro teor em PDF (exige login no e-SAJ).

    Exemplos: query="desvio produtivo do consumidor";
    query="prescrição intercorrente", data_julgamento_inicio="01/01/2025",
    data_julgamento_fim="30/06/2025"; query="cobrança indevida", somente_ementa=True.

    Args:
        query: Termos de busca. Por padrão pesquisa no inteiro teor.
        pagina: Página de resultados (default: 1; 20 acórdãos por página).
        somente_ementa: Se True, pesquisa só nas ementas (menos resultados, mais precisos).
        data_julgamento_inicio: Data inicial do julgamento, dd/mm/aaaa (opcional).
        data_julgamento_fim: Data final do julgamento, dd/mm/aaaa (opcional).
        ordenar_por: "publicacao" (mais recente primeiro, default) ou "relevancia".

    Returns:
        Lista de acórdãos com ementa e metadados, total informado pelo portal e
        dica de paginação. Em falha da fonte, texto iniciado por "Fonte TJSP indisponível".
    """
    if ordenar_por not in ORDENAR_POR:
        return f"ordenar_por inválido: '{ordenar_por}'. Use: {', '.join(ORDENAR_POR)}."
    for nome, valor in (
        ("data_julgamento_inicio", data_julgamento_inicio),
        ("data_julgamento_fim", data_julgamento_fim),
    ):
        if valor and not _DATA_RE.match(valor):
            return f"{nome} inválida: '{valor}'. Use o formato {DATA_FORMATO}."
    if pagina < 1:
        return "pagina deve ser maior ou igual a 1."

    try:
        resultado = await client.buscar_acordaos(
            query,
            pagina=pagina,
            somente_ementa=somente_ementa,
            data_julgamento_inicio=data_julgamento_inicio,
            data_julgamento_fim=data_julgamento_fim,
            ordenar_por=ordenar_por,
        )
    except HttpClientError as exc:
        return f"Fonte TJSP indisponível: {exc}. Tente novamente mais tarde."

    if not resultado.acordaos:
        return (
            f"Nenhum acórdão encontrado no TJSP para '{query}' "
            f"(total informado pelo portal: {resultado.total})."
        )

    paginas = max(1, -(-resultado.total // PAGE_SIZE))
    lines = [
        f"**Acórdãos TJSP** — '{query}' (página {pagina} de {paginas}, "
        f"{resultado.total} acórdãos):\n"
    ]
    for i, a in enumerate(resultado.acordaos, 1):
        cd = f" (cdAcordao {a.cd_acordao})" if a.cd_acordao else ""
        lines.append(f"**{i}. {a.numero_processo}**{cd}")
        classe = " / ".join(p for p in (a.classe, a.assunto) if p)
        lines.append(f"   Classe/Assunto: {classe or '—'}")
        lines.append(
            f"   Relator(a): {a.relator or '—'} · Órgão: {a.orgao_julgador or '—'} · "
            f"Comarca: {a.comarca or '—'}"
        )
        lines.append(
            f"   Julgamento: {a.data_julgamento or '—'} · Publicação: {a.data_publicacao or '—'}"
        )
        lines.append(f"   Ementa: {_ementa(a.ementa)}")
        lines.append("")

    if pagina < paginas:
        lines.append(f"> Use `pagina={pagina + 1}` para ver mais resultados.")

    return "\n".join(lines)
