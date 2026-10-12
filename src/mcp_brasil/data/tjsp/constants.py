"""Constants for the TJSP feature (e-SAJ Consulta de Jurisprudência de 2º grau).

Zero imports from other project modules (ADR-001 rule #6).
"""

CJSG_BASE_URL = "https://esaj.tjsp.jus.br/cjsg"
CONSULTA_PATH = "/consultaCompleta.do"
RESULTADO_PATH = "/resultadoCompleta.do"
PAGINA_PATH = "/trocaDePagina.do"

# Link de inteiro teor; exige login no e-SAJ, por isso é só referência
ACORDAO_URL = "https://esaj.tjsp.jus.br/cjsg/getArquivo.do?cdAcordao={cd_acordao}&cdForo=0"

# Campos do formulário consultaCompletaForm (validados ao vivo em 12/10/2026)
CAMPO_BUSCA_INTEIRO_TEOR = "dados.buscaInteiroTeor"
CAMPO_BUSCA_EMENTA = "dados.buscaEmenta"
CAMPO_DT_JULGAMENTO_INICIO = "dados.dtJulgamentoInicio"
CAMPO_DT_JULGAMENTO_FIM = "dados.dtJulgamentoFim"
CAMPO_ORDENAR_POR = "dados.ordenarPor"
CAMPO_TIPO_DECISAO = "tipoDecisaoSelecionados"
CAMPO_ORIGENS = "dados.origensSelecionadas"

TIPO_DECISAO_ACORDAO = "A"
ORIGEM_SEGUNDO_GRAU = "T"

ORDENAR_POR = {
    "publicacao": "dtPublicacao",
    "relevancia": "relevancia",
}

# O portal devolve sempre 20 acórdãos por página; não aceita outro tamanho
PAGE_SIZE = 20

# Formato das datas aceito pelo formulário
DATA_FORMATO = "dd/mm/aaaa"
