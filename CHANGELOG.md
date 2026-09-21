# Histórico do método

A versão sobe quando muda uma regra de contagem, normalização ou recorte. Base nova não muda a versão.

## 2026.09.2 (21/09/2026)
- Comparação entre bases pelo `CODIGO_AERONAVE` (`obs_diff.py`): código novo, renovação, saída, recadastro por número de série. Nova seção "O que entrou e o que saiu entre duas bases".
- Checagens de consistência antes de publicar (10 regras; qualquer falha aborta).
- Rótulos revisados para dizer o que foi contado: "aeronaves em nome de CPF", "modelos mais cadastrados no SISANT", "UF do endereço cadastral do CNPJ", "dados consolidados".
- Metadados de versão no JSON (`processado_em`, `versao_metodo`, `historico_metodo`, `checagens`, `licenca`) e edições datadas publicadas em `dados/`.
- JSON-LD Dataset com `distribution`, `version`, `isAccessibleForFree`, `measurementTechnique`.

## 2026.09.1 (20/09/2026)
- Snapshot de cada base guardado, para que a série histórica não dependa da memória do cadastro.
- Modelos colapsados por família; códigos internos de fábrica decifrados pela própria base (≥ 80% de concordância, alvo não pode ser razão social).
- Redesign editorial da página (fontes locais, tema escuro próprio, sem JavaScript).

## 2026.08.1 (05/08/2026)
- Primeira apuração pública: série mensal por `DATA_VALIDADE − 24 meses`, UF via CNPJ na Receita, ramos de atividade agrupados, curva de concentração da frota empresarial, prefixos PP/PR/PS.
