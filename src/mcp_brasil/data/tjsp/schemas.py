"""Pydantic models for the TJSP feature."""

from __future__ import annotations

from pydantic import BaseModel


class AcordaoTJSP(BaseModel):
    """Acórdão de 2º grau do TJSP, como listado na Consulta de Jurisprudência (CJSG)."""

    numero_processo: str
    cd_acordao: str | None = None
    classe: str | None = None
    assunto: str | None = None
    relator: str | None = None
    comarca: str | None = None
    orgao_julgador: str | None = None
    data_julgamento: str | None = None
    data_publicacao: str | None = None
    ementa: str | None = None
    url: str | None = None


class ResultadoBuscaTJSP(BaseModel):
    """Uma página de resultados da CJSG."""

    total: int
    pagina: int
    acordaos: list[AcordaoTJSP]
