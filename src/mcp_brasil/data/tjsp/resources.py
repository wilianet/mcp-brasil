"""Resources for the TJSP feature."""

from __future__ import annotations

import json

from .constants import CJSG_BASE_URL, DATA_FORMATO, ORDENAR_POR, PAGE_SIZE


def info_tjsp() -> str:
    """Informações sobre a fonte, os filtros suportados e as limitações."""
    data = {
        "nome": "Consulta de Jurisprudência do TJSP (e-SAJ CJSG)",
        "url_base": CJSG_BASE_URL,
        "cobertura": "Acórdãos de 2º grau do Tribunal de Justiça de São Paulo",
        "autenticacao": "Nenhuma para ementa e metadados; inteiro teor (PDF) exige login no e-SAJ",
        "tamanho_pagina": PAGE_SIZE,
        "filtros": {
            "query": "termos de busca no inteiro teor (padrão) ou só na ementa (somente_ementa)",
            "data_julgamento_inicio/fim": f"formato {DATA_FORMATO}",
            "ordenar_por": sorted(ORDENAR_POR),
        },
        "nao_suportado": [
            "filtro por relator, classe, assunto, seção ou comarca (exigem códigos do portal)",
            "decisões monocráticas e homologações",
            "download do inteiro teor",
        ],
        "erro": "Falha da fonte retorna texto iniciado por 'Fonte TJSP indisponível'",
    }
    return json.dumps(data, ensure_ascii=False)
