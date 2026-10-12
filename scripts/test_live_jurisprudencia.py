"""Script de teste ao vivo para validação das APIs de Jurisprudência e do servidor FastMCP."""

import asyncio
import time

from fastmcp import Client

from mcp_brasil.data.jurisprudencia.client import (
    buscar_repercussao_geral,
    buscar_stf,
    buscar_stj,
    buscar_sumulas_stf,
    buscar_tst,
)
from mcp_brasil.data.jurisprudencia.server import mcp


async def testar_stf():
    print("\n" + "=" * 60)
    print("1. TESTANDO STF (buscar_jurisprudencia_stf)...")
    start = time.time()
    try:
        results = await buscar_stf("dano moral", pagina=1, tamanho=2)
        elapsed = time.time() - start
        print(f"-> Retornou {len(results)} acórdãos em {elapsed:.2f}s")
        for i, res in enumerate(results, 1):
            print(
                f"   [{i}] Processo: {res.classe} {res.numero_processo} | Relator: {res.relator}"
            )
            print(f"       Julgamento: {res.data_julgamento} | Órgão: {res.orgao_julgador}")
            print(f"       Ementa resumida: {(res.ementa or '')[:160]}...")
            print(f"       URL: {res.url}")
        return len(results) > 0
    except Exception as e:
        print(f"-> Erro no STF: {e}")
        return False


async def testar_stj():
    print("\n" + "=" * 60)
    print("2. TESTANDO STJ (buscar_jurisprudencia_stj)...")
    start = time.time()
    try:
        results = await buscar_stj("dano moral", pagina=1, tamanho=2)
        elapsed = time.time() - start
        print(f"-> Retornou {len(results)} acórdãos em {elapsed:.2f}s")
        for i, res in enumerate(results, 1):
            print(
                f"   [{i}] Processo: {res.classe} {res.numero_processo} | Relator: {res.relator}"
            )
            print(f"       Julgamento: {res.data_julgamento} | Órgão: {res.orgao_julgador}")
            print(f"       Ementa resumida: {(res.ementa or '')[:160]}...")
            print(f"       URL: {res.url}")
        return len(results) > 0
    except Exception as e:
        print(f"-> Erro no STJ: {e}")
        return False


async def testar_tst():
    print("\n" + "=" * 60)
    print("3. TESTANDO TST (buscar_jurisprudencia_tst)...")
    start = time.time()
    try:
        results = await buscar_tst("horas extras", pagina=1, tamanho=2)
        elapsed = time.time() - start
        print(f"-> Retornou {len(results)} acórdãos em {elapsed:.2f}s")
        for i, res in enumerate(results, 1):
            print(
                f"   [{i}] Processo: {res.classe} {res.numero_processo} | Relator: {res.relator}"
            )
            print(f"       Julgamento: {res.data_julgamento} | Órgão: {res.orgao_julgador}")
            print(f"       Ementa resumida: {(res.ementa or '')[:160]}...")
            print(f"       URL: {res.url}")
        return len(results) > 0
    except Exception as e:
        print(f"-> Erro no TST: {e}")
        return False


async def testar_sumulas_stf():
    print("\n" + "=" * 60)
    print("4. TESTANDO SÚMULAS VINCULANTES / STF (buscar_sumulas_stf)...")
    start = time.time()
    try:
        results = await buscar_sumulas_stf("vinculante")
        elapsed = time.time() - start
        print(f"-> Retornou {len(results)} súmulas em {elapsed:.2f}s")
        for i, res in enumerate(results[:3], 1):
            vinc_str = f"Vinculante: {res.vinculante}"
            print(f"   [{i}] Súmula nº {res.numero} ({vinc_str}) | Situação: {res.situacao}")
            print(f"       Enunciado: {(res.enunciado or '')[:180]}...")
        return len(results) > 0
    except Exception as e:
        print(f"-> Erro nas Súmulas STF: {e}")
        return False


async def testar_repercussao_geral():
    print("\n" + "=" * 60)
    print("5. TESTANDO REPERCUSSÃO GERAL (buscar_repercussao_geral)...")
    start = time.time()
    try:
        results = await buscar_repercussao_geral(tema=810)
        elapsed = time.time() - start
        print(f"-> Retornou {len(results)} temas em {elapsed:.2f}s")
        for i, res in enumerate(results[:2], 1):
            print(f"   [{i}] Tema nº {res.numero_tema} | Leading Case: {res.leading_case}")
            print(f"       Título: {res.titulo}")
            print(f"       Tese: {(res.tese or '')[:200]}...")
        return len(results) > 0
    except Exception as e:
        print(f"-> Erro na Repercussão Geral: {e}")
        return False


async def testar_mcp_client_e2e():
    print("\n" + "=" * 60)
    print("6. TESTANDO EXECUÇÃO VIA FASTMCP CLIENT (PROTOCOLO MCP NATIVO)...")
    start = time.time()
    try:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            print(f"-> Conectado ao servidor MCP com {len(tools)} ferramentas registradas:")
            for t in tools:
                print(f"   - {t.name}: {t.description[:70]}...")

            print("\n   Chamando tool 'buscar_sumulas' via protocolo MCP...")
            call_res = await client.call_tool(
                "buscar_sumulas", {"tribunal": "stf", "query": "vinculante"}
            )
            elapsed = time.time() - start
            print(f"-> Resposta recebida via MCP em {elapsed:.2f}s:")
            print("   Conteúdo (primeiros 300 caracteres):")
            print(f"   {str(call_res.data)[:300]}...")
            return True
    except Exception as e:
        print(f"-> Erro no FastMCP Client: {e}")
        return False


async def main():
    print("=" * 60)
    print("INICIANDO BATERIA DE TESTES DE INTEGRAÇÃO REAL: MCP JURISPRUDÊNCIA")
    print("=" * 60)

    sucessos = {}
    sucessos["STF"] = await testar_stf()
    sucessos["STJ"] = await testar_stj()
    sucessos["TST"] = await testar_tst()
    sucessos["Súmulas STF"] = await testar_sumulas_stf()
    sucessos["Repercussão Geral STF"] = await testar_repercussao_geral()
    sucessos["Protocolo FastMCP Client"] = await testar_mcp_client_e2e()

    print("\n" + "=" * 60)
    print("RELATÓRIO CONSOLIDADO DE VALIDAÇÃO:")
    print("=" * 60)
    for k, v in sucessos.items():
        status = "✅ PASSOU" if v else "⚠️ REQUER ATENÇÃO / RETORNO VAZIO"
        print(f"{k:30} : {status}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
