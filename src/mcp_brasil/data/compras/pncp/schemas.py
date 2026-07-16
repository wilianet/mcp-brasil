"""Pydantic schemas for the Compras feature."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaginationInfo(BaseModel):
    """Metadados que deixam explícito o escopo efetivamente consultado."""

    pagina_inicial: int = 1
    paginas_consultadas: int = 1
    total_paginas: int | None = None
    total_registros_fonte: int | None = None
    pesquisa_completa: bool = False
    limite_paginas_atingido: bool = False


class Contratacao(BaseModel):
    """Contratação pública retornada pelo PNCP."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    ano: int | None = None
    numero_sequencial: int | None = None
    numero_controle_pncp: str | None = None
    objeto: str | None = None
    modalidade_id: int | None = None
    modalidade_nome: str | None = None
    situacao_id: int | None = None
    situacao_nome: str | None = None
    valor_estimado: float | None = None
    valor_homologado: float | None = None
    data_publicacao: str | None = None
    data_abertura: str | None = None
    uf: str | None = None
    municipio: str | None = None
    esfera: str | None = None
    link_pncp: str | None = None


class ContratacaoResultado(BaseModel):
    """Resultado paginado de busca de contratações."""

    total: int = 0
    contratacoes: list[Contratacao] = Field(default_factory=list)
    paginacao: PaginationInfo = Field(default_factory=PaginationInfo)


class Contrato(BaseModel):
    """Contrato público."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    numero_contrato: str | None = None
    objeto: str | None = None
    fornecedor_cnpj: str | None = None
    fornecedor_nome: str | None = None
    valor_inicial: float | None = None
    valor_final: float | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    data_publicacao: str | None = None
    situacao: str | None = None


class ContratoResultado(BaseModel):
    """Resultado paginado de busca de contratos."""

    total: int = 0
    contratos: list[Contrato] = Field(default_factory=list)
    paginacao: PaginationInfo = Field(default_factory=PaginationInfo)


class AtaRegistroPreco(BaseModel):
    """Ata de registro de preço."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    numero_ata: str | None = None
    objeto: str | None = None
    fornecedor_cnpj: str | None = None
    fornecedor_nome: str | None = None
    valor_total: float | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    situacao: str | None = None


class AtaResultado(BaseModel):
    """Resultado paginado de busca de atas."""

    total: int = 0
    atas: list[AtaRegistroPreco] = Field(default_factory=list)
    paginacao: PaginationInfo = Field(default_factory=PaginationInfo)


class Fornecedor(BaseModel):
    """Fornecedor de contratações públicas."""

    cnpj: str | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    municipio: str | None = None
    uf: str | None = None
    porte: str | None = None
    data_abertura: str | None = None


class FornecedorResultado(BaseModel):
    """Resultado paginado de busca de fornecedores."""

    total: int = 0
    fornecedores: list[Fornecedor] = Field(default_factory=list)


class OrgaoContratante(BaseModel):
    """Órgão contratante no PNCP."""

    cnpj: str | None = None
    razao_social: str | None = None
    esfera: str | None = None
    poder: str | None = None
    uf: str | None = None
    municipio: str | None = None


class OrgaoResultado(BaseModel):
    """Resultado paginado de busca de órgãos."""

    total: int = 0
    orgaos: list[OrgaoContratante] = Field(default_factory=list)


class ItemContratacao(BaseModel):
    """Item de uma contratação publicado na API de integração do PNCP."""

    numero_item: int | None = None
    descricao: str | None = None
    material_ou_servico: str | None = None
    material_ou_servico_nome: str | None = None
    quantidade: float | None = None
    unidade_medida: str | None = None
    valor_unitario_estimado: float | None = None
    valor_total: float | None = None
    orcamento_sigiloso: bool | None = None
    criterio_julgamento_nome: str | None = None
    situacao_nome: str | None = None
    tipo_beneficio_nome: str | None = None
    data_inclusao: str | None = None
    data_atualizacao: str | None = None
    tem_resultado: bool | None = None
    codigo_catalogo: str | None = None
    informacao_complementar: str | None = None


class DocumentoContratacao(BaseModel):
    """Metadados de documento ou anexo de uma contratação."""

    sequencial_documento: int | None = None
    titulo: str | None = None
    tipo_documento_id: int | None = None
    tipo_documento_nome: str | None = None
    tipo_documento_descricao: str | None = None
    url: str | None = None
    uri: str | None = None
    status_ativo: bool | None = None
    data_publicacao: str | None = None


class ResultadoItemContratacao(BaseModel):
    """Resultado homologado de um item de contratação."""

    numero_item: int | None = None
    sequencial_resultado: int | None = None
    fornecedor_documento: str | None = None
    fornecedor_nome: str | None = None
    tipo_pessoa: str | None = None
    quantidade_homologada: float | None = None
    valor_unitario_homologado: float | None = None
    valor_total_homologado: float | None = None
    percentual_desconto: float | None = None
    situacao_nome: str | None = None
    porte_fornecedor_nome: str | None = None
    data_resultado: str | None = None
    data_inclusao: str | None = None
    data_atualizacao: str | None = None


class ItensContratacaoResultado(BaseModel):
    total: int = 0
    itens: list[ItemContratacao] = Field(default_factory=list)


class DocumentosContratacaoResultado(BaseModel):
    total: int = 0
    documentos: list[DocumentoContratacao] = Field(default_factory=list)


class ResultadosItemContratacaoResultado(BaseModel):
    total: int = 0
    resultados: list[ResultadoItemContratacao] = Field(default_factory=list)


class ItemPca(BaseModel):
    """Item do Plano de Contratações Anual."""

    numero_item: int | None = None
    descricao: str | None = None
    quantidade_estimada: float | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None
    unidade_fornecimento: str | None = None
    categoria: str | None = None
    data_desejada: str | None = None


class Pca(BaseModel):
    """Plano de Contratações Anual."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    ano: int | None = None
    unidade_nome: str | None = None
    id_pca: str | None = None
    data_publicacao: str | None = None
    itens: list[ItemPca] = Field(default_factory=list)


class PcaResultado(BaseModel):
    """Resultado paginado de busca de PCAs."""

    total: int = 0
    pcas: list[Pca] = Field(default_factory=list)


class InstrumentoCobranca(BaseModel):
    """Instrumento de cobrança (nota fiscal) vinculado a contrato."""

    cnpj_orgao: str | None = None
    ano_contrato: int | None = None
    numero_instrumento: str | None = None
    tipo_nome: str | None = None
    data_emissao: str | None = None
    objeto_contrato: str | None = None
    fornecedor_nome: str | None = None
    fornecedor_cnpj: str | None = None
    valor_nf: str | None = None
    chave_nfe: str | None = None


class InstrumentoCobrancaResultado(BaseModel):
    """Resultado paginado de busca de instrumentos de cobrança."""

    total: int = 0
    instrumentos: list[InstrumentoCobranca] = Field(default_factory=list)
