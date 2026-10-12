"""Unit tests for the embedded SQLite jurisprudence database."""

import sqlite3

import pytest

from mcp_brasil.data.jurisprudencia import db
from mcp_brasil.data.jurisprudencia.db import (
    buscar_repercussao_geral_local,
    buscar_sumulas_local,
)


class TestLocalJurisprudenciaDB:
    def test_buscar_sumula_vinculante_por_numero(self) -> None:
        results = buscar_sumulas_local(query="11", tribunal="stf", vinculante=True)
        assert len(results) >= 1
        s11 = results[0]
        assert s11.numero == 11
        assert s11.vinculante is True
        assert "algemas" in s11.enunciado.lower()

    def test_buscar_sumula_vinculante_por_texto(self) -> None:
        results = buscar_sumulas_local(query="algemas", tribunal="stf")
        assert len(results) >= 1
        assert any(s.numero == 11 and s.vinculante for s in results)

    def test_buscar_sumulas_stj(self) -> None:
        results = buscar_sumulas_local(query="dano moral", tribunal="stj")
        assert len(results) >= 1
        assert all(s.tribunal == "STJ" for s in results)

    def test_buscar_repercussao_geral_por_tema(self) -> None:
        results = buscar_repercussao_geral_local(tema=810)
        assert len(results) == 1
        t810 = results[0]
        assert t810.numero_tema == 810
        assert "Fazenda Pública" in t810.titulo
        assert t810.tese is not None

    def test_buscar_repercussao_geral_por_texto(self) -> None:
        results = buscar_repercussao_geral_local(query="ICMS base calculo PIS")
        assert len(results) >= 1
        # Tema 69 (Tese do Século)
        temas = [r.numero_tema for r in results]
        assert 69 in temas

    def test_busca_por_numero_aceita_prefixo(self) -> None:
        for query in ("Súmula Vinculante 11", "sv 11", "súmula nº 11", " 11 "):
            results = buscar_sumulas_local(query=query, tribunal="stf")
            assert results, query
            assert results[0].numero == 11, query

    def test_texto_com_sv_e_digito_nao_vira_busca_por_numero(self) -> None:
        # "desvio" contém "sv"; antes, "desvio de finalidade 1" virava busca pela Súmula 1
        results = buscar_sumulas_local(query="desvio de finalidade 1", tribunal="stf")
        assert all("desvio" in s.enunciado.lower() for s in results)

    def test_fecha_conexao_apos_busca(self, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = db.get_connection()
        monkeypatch.setattr(db, "get_connection", lambda: conn)
        buscar_sumulas_local(query="algemas", tribunal="stf")
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
