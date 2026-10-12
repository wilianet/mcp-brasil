"""Local embedded SQLite database with FTS5 for Jurisprudência.

Provides high-speed, offline-first search for:
- Súmulas Vinculantes (STF)
- Súmulas Tradicionais (STF e STJ)
- Temas de Repercussão Geral (STF) com teses fixadas e leading cases

Solves upstream WAF/Cloudflare blocks by serving authoritative verbetes locally.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from .schemas import RepercussaoGeral, Sumula

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent / "data"
_DB_PATH = _DATA_DIR / "jurisprudencia.db"

_COLUNAS_SUMULAS = (
    "s.tribunal, s.numero, s.vinculante, s.enunciado, s.ramo, s.situacao, s.data_aprovacao"
)
# Consulta que é só um número, opcionalmente precedido de "súmula", "súmula vinculante" ou "sv"
_NUMERO_QUERY = re.compile(
    r"^\s*(?:s[uú]mula(?:\s+vinculante)?|sv)?\s*(?:n[º°o.]?\s*)?(\d+)\s*$", re.IGNORECASE
)

_COLUNAS_RG = (
    "numero_tema, titulo, descricao, relator, leading_case, situacao, data_reconhecimento, tese"
)


def _clean_fts_query(query: str) -> str:
    """Sanitize query string for SQLite FTS5 MATCH syntax."""
    terms = re.findall(r"\w+", query, re.UNICODE)
    if not terms:
        return ""
    # Search each term with prefix matching (e.g. termo*)
    return " ".join(f'"{t}"*' for t in terms)


def get_connection() -> sqlite3.Connection:
    """Return an SQLite connection, initializing database if needed."""
    init_needed = not _DB_PATH.exists()
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    if init_needed:
        _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables and FTS5 indexes, and seed initial data."""
    logger.info("Inicializando banco local SQLite de jurisprudência em %s", _DB_PATH)
    cursor = conn.cursor()

    # 1. Súmulas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sumulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tribunal TEXT NOT NULL,
            numero INTEGER,
            vinculante INTEGER NOT NULL DEFAULT 0,
            enunciado TEXT NOT NULL,
            ramo TEXT,
            situacao TEXT,
            data_aprovacao TEXT,
            url TEXT
        );
    """)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS sumulas_fts USING fts5(
            enunciado,
            content='sumulas',
            content_rowid='id'
        );
    """)

    # 2. Repercussão Geral
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repercussao_geral (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_tema INTEGER NOT NULL,
            titulo TEXT,
            descricao TEXT,
            relator TEXT,
            leading_case TEXT,
            situacao TEXT,
            data_reconhecimento TEXT,
            tese TEXT,
            url TEXT
        );
    """)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS repercussao_fts USING fts5(
            titulo,
            tese,
            descricao,
            content='repercussao_geral',
            content_rowid='id'
        );
    """)

    conn.commit()
    _seed_data(conn)


def _seed_data(conn: sqlite3.Connection) -> None:
    """Seed data from JSON files in data/ directory."""
    cursor = conn.cursor()

    sql_ins_sumula = """
        INSERT INTO sumulas (
            tribunal, numero, vinculante, enunciado, ramo, situacao, data_aprovacao, url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    # 1. Súmulas Vinculantes
    sv_file = _DATA_DIR / "sumulas_vinculantes.json"
    if sv_file.exists():
        try:
            with open(sv_file, encoding="utf-8") as f:
                sv_data = json.load(f)
            sumulas_dict = sv_data.get("sumulas", {})
            for item in sumulas_dict.values():
                cursor.execute(
                    sql_ins_sumula,
                    (
                        "STF",
                        item.get("numero"),
                        1,
                        item.get("enunciado", ""),
                        item.get("ramo") or item.get("area"),
                        item.get("status"),
                        item.get("data"),
                        item.get("url"),
                    ),
                )
                row_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO sumulas_fts(rowid, enunciado) VALUES (?, ?)",
                    (row_id, item.get("enunciado", "")),
                )
        except Exception as e:
            logger.warning("Erro ao carregar sumulas_vinculantes.json: %s", e)

    # 2. Súmulas STF
    stf_file = _DATA_DIR / "sumulas_stf.json"
    if stf_file.exists():
        try:
            with open(stf_file, encoding="utf-8") as f:
                stf_data = json.load(f)
            sumulas_dict = stf_data.get("sumulas", {})
            for item in sumulas_dict.values():
                cursor.execute(
                    sql_ins_sumula,
                    (
                        "STF",
                        item.get("numero"),
                        0,
                        item.get("enunciado", ""),
                        item.get("area") or item.get("ramo"),
                        item.get("status"),
                        item.get("data"),
                        item.get("url"),
                    ),
                )
                row_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO sumulas_fts(rowid, enunciado) VALUES (?, ?)",
                    (row_id, item.get("enunciado", "")),
                )
        except Exception as e:
            logger.warning("Erro ao carregar sumulas_stf.json: %s", e)

    # 3. Súmulas STJ
    stj_file = _DATA_DIR / "sumulas_stj.json"
    if stj_file.exists():
        try:
            with open(stj_file, encoding="utf-8") as f:
                stj_data = json.load(f)
            sumulas_dict = stj_data.get("sumulas", {})
            for item in sumulas_dict.values():
                cursor.execute(
                    sql_ins_sumula,
                    (
                        "STJ",
                        item.get("numero"),
                        0,
                        item.get("enunciado", ""),
                        item.get("area") or item.get("tema"),
                        item.get("status"),
                        item.get("data"),
                        item.get("url"),
                    ),
                )
                row_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO sumulas_fts(rowid, enunciado) VALUES (?, ?)",
                    (row_id, item.get("enunciado", "")),
                )
        except Exception as e:
            logger.warning("Erro ao carregar sumulas_stj.json: %s", e)

    # 4. Temas Repercussão Geral STF
    rg_file = _DATA_DIR / "temas_rg_stf.json"
    if rg_file.exists():
        try:
            with open(rg_file, encoding="utf-8") as f:
                rg_data = json.load(f)
            temas_dict = rg_data.get("temas", {})
            for item in temas_dict.values():
                cursor.execute(
                    """
                    INSERT INTO repercussao_geral (
                        numero_tema, titulo, descricao, relator, leading_case,
                        situacao, data_reconhecimento, tese, url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.get("numero"),
                        item.get("titulo"),
                        item.get("descricao"),
                        item.get("relator"),
                        item.get("leadingCase"),
                        item.get("situacao"),
                        item.get("dataJulgamento") or item.get("dataTese"),
                        item.get("tese"),
                        item.get("paginaTema")
                        or (
                            item.get("links", {}).get("paginaTema")
                            if isinstance(item.get("links"), dict)
                            else None
                        ),
                    ),
                )
                row_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO repercussao_fts(rowid, titulo, tese, descricao)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        item.get("titulo") or "",
                        item.get("tese") or "",
                        item.get("descricao") or "",
                    ),
                )
        except Exception as e:
            logger.warning("Erro ao carregar temas_rg_stf.json: %s", e)

    conn.commit()
    logger.info("Seed de jurisprudência concluído com sucesso.")


def buscar_sumulas_local(
    query: str | None = None,
    tribunal: str | None = "stf",
    vinculante: bool | None = None,
    limit: int = 20,
) -> list[Sumula]:
    """Busca súmulas no banco SQLite local com suporte a FTS5 e filtros."""
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()

        conditions: list[str] = []
        params: list[Any] = []

        if tribunal:
            conditions.append("s.tribunal = ?")
            params.append(tribunal.upper())

        if vinculante is not None:
            conditions.append("s.vinculante = ?")
            params.append(1 if vinculante else 0)

        numero_match = None
        if query:
            m = _NUMERO_QUERY.match(query)
            if m:
                numero_match = int(m.group(1))

        if numero_match is not None:
            conditions.append("s.numero = ?")
            params.append(numero_match)
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            sql = f"""
                SELECT {_COLUNAS_SUMULAS}
                FROM sumulas s
                {where_clause}
                ORDER BY s.vinculante DESC, s.numero ASC
                LIMIT ?
            """
            params.append(limit)
            cursor.execute(sql, params)
        elif query:
            fts_query = _clean_fts_query(query)
            if fts_query:
                conditions.append("sumulas_fts MATCH ?")
                params.append(fts_query)
                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                sql = f"""
                    SELECT {_COLUNAS_SUMULAS}
                    FROM sumulas s
                    JOIN sumulas_fts ON s.id = sumulas_fts.rowid
                    {where_clause}
                    ORDER BY s.vinculante DESC, bm25(sumulas_fts)
                    LIMIT ?
                """
                params.append(limit)
                try:
                    cursor.execute(sql, params)
                except sqlite3.OperationalError:
                    # Fallback para LIKE simples se a query FTS for inválida
                    params.pop()  # remove limit
                    params.pop()  # remove fts_query
                    conditions.pop()
                    conditions.append("s.enunciado LIKE ?")
                    params.append(f"%{query}%")
                    where_clause = " WHERE " + " AND ".join(conditions)
                    sql = f"""
                        SELECT {_COLUNAS_SUMULAS}
                        FROM sumulas s
                        {where_clause}
                        ORDER BY s.vinculante DESC, s.numero ASC
                        LIMIT ?
                    """
                    params.append(limit)
                    cursor.execute(sql, params)
            else:
                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                sql = f"""
                    SELECT {_COLUNAS_SUMULAS}
                    FROM sumulas s
                    {where_clause}
                    ORDER BY s.vinculante DESC, s.numero ASC
                    LIMIT ?
                """
                params.append(limit)
                cursor.execute(sql, params)
        else:
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            sql = f"""
                SELECT {_COLUNAS_SUMULAS}
                FROM sumulas s
                {where_clause}
                ORDER BY s.vinculante DESC, s.numero ASC
                LIMIT ?
            """
            params.append(limit)
            cursor.execute(sql, params)

        rows = cursor.fetchall()
        return [
            Sumula(
                tribunal=r["tribunal"],
                numero=r["numero"],
                enunciado=r["enunciado"],
                referencia_legislativa=r["ramo"],
                situacao=r["situacao"],
                data_aprovacao=r["data_aprovacao"],
                vinculante=bool(r["vinculante"]),
            )
            for r in rows
        ]


def buscar_repercussao_geral_local(
    query: str | None = None,
    tema: int | None = None,
    limit: int = 15,
) -> list[RepercussaoGeral]:
    """Busca temas de repercussão geral no banco SQLite local."""
    with contextlib.closing(get_connection()) as conn:
        cursor = conn.cursor()

        if tema is not None:
            cursor.execute(
                f"""
                SELECT {_COLUNAS_RG}
                FROM repercussao_geral
                WHERE numero_tema = ?
                LIMIT ?
                """,
                (tema, limit),
            )
        elif query:
            fts_query = _clean_fts_query(query)
            if fts_query:
                sql = f"""
                    SELECT {", ".join("r." + c.strip() for c in _COLUNAS_RG.split(","))}
                    FROM repercussao_geral r
                    JOIN repercussao_fts ON r.id = repercussao_fts.rowid
                    WHERE repercussao_fts MATCH ?
                    ORDER BY bm25(repercussao_fts)
                    LIMIT ?
                """
                try:
                    cursor.execute(sql, (fts_query, limit))
                except sqlite3.OperationalError:
                    cursor.execute(
                        f"""
                        SELECT {_COLUNAS_RG}
                        FROM repercussao_geral
                        WHERE titulo LIKE ? OR tese LIKE ? OR descricao LIKE ?
                        LIMIT ?
                        """,
                        (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                    )
            else:
                cursor.execute(
                    f"""
                    SELECT {_COLUNAS_RG}
                    FROM repercussao_geral
                    ORDER BY numero_tema DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
        else:
            cursor.execute(
                f"""
                SELECT {_COLUNAS_RG}
                FROM repercussao_geral
                ORDER BY numero_tema DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        return [
            RepercussaoGeral(
                numero_tema=r["numero_tema"],
                titulo=r["titulo"],
                descricao=r["descricao"],
                relator=r["relator"],
                leading_case=r["leading_case"],
                situacao=r["situacao"],
                data_reconhecimento=r["data_reconhecimento"],
                tese=r["tese"],
            )
            for r in rows
        ]
