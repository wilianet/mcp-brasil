# Operacao segura na Sipal

Este documento define a configuracao inicial aprovada para avaliar o `mcp-brasil`
na Sipal. O objetivo e manter o servidor local, sem porta de rede, sem dados
pessoais e com dependencias auditadas.

## Baseline aprovada

- Executar por `stdio`, dentro de uma venv exclusiva.
- Fixar o pacote em `mcp-brasil==0.14.0`.
- Manter `MCP_BRASIL_TOOL_SEARCH=bm25`.
- Nao habilitar `code_mode`, HTTP, Docker, OAuth ou datasets na avaliacao inicial.
- Nao configurar `ANTHROPIC_API_KEY` inicialmente.
- Nao liberar PII com `MCP_BRASIL_LGPD_ALLOW_PII`.
- Confirmar informacoes financeiras, juridicas, medicas ou comerciais na fonte oficial.

Snapshot revisado em 2026-07-16: commit
`7a7c49cdfc2398eb623a47c60e4b786a86213bdc`.

## 1. Preparar o ambiente isolado

Execute no PowerShell, na raiz deste repositorio:

```powershell
uv venv .venv

$meta = Invoke-RestMethod 'https://pypi.org/pypi/mcp-brasil/0.14.0/json'
$wheel = $meta.urls |
    Where-Object { $_.packagetype -eq 'bdist_wheel' } |
    Select-Object -First 1

Invoke-WebRequest -Uri $wheel.url -OutFile $wheel.filename

$esperado = 'f11126047aa51378d7d6ef3cf8ee50a95b2dd4414e6fa75ac95db7e1adc86e88'
$obtido = (Get-FileHash -Algorithm SHA256 $wheel.filename).Hash.ToLowerInvariant()
if ($obtido -ne $esperado) {
    throw "Hash do pacote invalido. Esperado: $esperado; obtido: $obtido"
}

uv pip install --python .venv\Scripts\python.exe $wheel.filename
```

Nao use `pip install -e .` ou `uv sync --frozen` antes de atualizar e auditar o
`uv.lock` do repositorio.

## 2. Auditar as dependencias instaladas

```powershell
uvx pip-audit --path .venv\Lib\site-packages --progress-spinner off
```

O resultado esperado e `No known vulnerabilities found`. Se houver qualquer
vulnerabilidade, nao conecte o servidor ao cliente MCP ate revisar ou atualizar
o pacote afetado.

Registre a arvore efetivamente instalada:

```powershell
uv pip freeze --python .venv\Scripts\python.exe
```

## 3. Configuracao inicial do cliente MCP

Use o Python da venv como comando do servidor:

```json
{
  "mcpServers": {
    "dados-publicos": {
      "command": "C:\\Users\\wilia\\OneDrive - Sipal Industria E Comercio Ltda\\ideias\\dados-publicos\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_brasil.server"],
      "env": {
        "MCP_BRASIL_TOOL_SEARCH": "bm25",
        "MCP_BRASIL_AUTH_MODE": "none",
        "MCP_BRASIL_DATASETS": "",
        "MCP_BRASIL_LGPD_ALLOW_PII": ""
      }
    }
  }
}
```

`MCP_BRASIL_AUTH_MODE=none` so e aceitavel nesse modo `stdio`, pois nao existe
porta de rede. Nao coloque chaves diretamente em arquivos versionados.

## 4. Segredos e dados

- Nao crie `.env` na raiz sem necessidade: o servidor carrega esse arquivo
  automaticamente.
- Quando uma fonte exigir chave, use uma credencial exclusiva, de menor
  privilegio e fornecida apenas pelo bloco `env` do cliente MCP ou por um cofre.
- Nunca use chaves pessoais ou de producao durante a avaliacao.
- Mantenha `ANTHROPIC_API_KEY` ausente. Quando configurada, as ferramentas de
  recomendacao e planejamento enviam consultas para a Anthropic.
- Datasets DuckDB podem ocupar gigabytes e conter dados pessoais. A ativacao
  exige avaliacao separada de LGPD, finalidade, retencao e controle de acesso.

## 5. HTTP e Docker

Nao execute o `docker-compose.yml` original na rede corporativa. Ele publica a
porta 8061 e o processo interno escuta em `0.0.0.0`; sem token, o MCP pode ficar
acessivel a outros equipamentos da rede.

Se HTTP se tornar necessario, os requisitos minimos sao:

- bind exclusivo em `127.0.0.1`;
- `MCP_BRASIL_AUTH_MODE=static`;
- token aleatorio exclusivo em `MCP_BRASIL_API_TOKEN`;
- firewall bloqueando acesso externo;
- nova auditoria do `uv.lock` e da imagem;
- nenhuma publicacao direta na internet.

## 6. Atualizacoes do upstream

Nao atualize o fork automaticamente. Primeiro inspecione as mudancas:

```powershell
git fetch upstream --tags
git log --oneline main..upstream/main
git diff --stat main..upstream/main
```

Antes de incorporar uma nova versao:

1. Revisar `pyproject.toml`, `uv.lock`, workflows, Docker e novos dominios externos.
2. Baixar o artefato publicado e verificar seu hash.
3. Recriar a venv do zero.
4. Executar `pip-audit` novamente.
5. Validar que PII, datasets, HTTP e `code_mode` continuam desabilitados.

## 7. Usos iniciais permitidos

- Indicadores de Bacen e IBGE.
- Pesquisa de compras publicas, PNCP e contratos.
- Informacoes cadastrais e territoriais publicas.
- Apoio a pesquisas de mercado e relatorios internos.

As respostas sao auxiliares. Para decisoes da Sipal, registre a URL, data da
consulta e confirme o dado diretamente na fonte primaria.
