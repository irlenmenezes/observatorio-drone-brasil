# Observatório do Drone no Brasil

Apuração aberta e reproduzível do cadastro nacional de drones (SISANT/ANAC), publicada em
**https://irlenmenezes.com.br/observatorio-drone-brasil/**.

Este repositório guarda o código que faz a apuração, os resultados consolidados de cada
edição e o checksum de cada arquivo da ANAC usado. Qualquer pessoa consegue baixar o mesmo
arquivo na ANAC, rodar os mesmos scripts e chegar aos mesmos números.

Edição corrente: **base ANAC de 20/09/2026, 186.016 registros, método 2026.09.2.**

## O que é medido

O SISANT é um cadastro de **aeronaves**: cada linha é um drone registrado, com código,
validade, operador (CPF mascarado ou CNPJ), tipo de uso, fabricante, modelo, número de
série, peso máximo de decolagem e ramo de atividade declarado.

Cadastro permite concluir quantas aeronaves estão registradas, de que modelo, faixa de
peso, tipo de uso e ramo, e em nome de CPF ou de CNPJ. **Não** permite concluir quantas
pessoas têm drone, quanto cada marca vendeu, quantas horas cada modelo voa nem onde o drone
opera. Todos os rótulos do Observatório seguem essa distinção.

## Reproduzir a apuração

Python 3.11 ou mais novo, sem dependências externas.

```bash
git clone https://github.com/irlenmenezes/observatorio-drone-brasil.git
cd observatorio-drone-brasil

# 1. baixe o arquivo oficial da ANAC (é público)
curl -o SISANT_new.csv "https://sistemas.anac.gov.br/dadosabertos/Aeronaves/drones%20cadastrados/SISANT.csv"

# 2. (opcional) UF das empresas: agrega os CNPJs e consulta os que faltam no cache
python apura_uf.py
python consulta_uf.py

# 3. apura, compara com a base anterior (se houver snapshot) e gera a página
python obs_apura.py      # -> obs-drone.json (aborta se uma checagem de consistência falhar)
python obs_diff.py       # -> obs-diff.json (precisa de duas bases em snapshots/)
python obs_build.py      # -> site/index.html + site/dados/
```

`obs_rotina.py` encadeia tudo isso todo mês (baixa o CSV, guarda snapshot, apura, gera,
publica). Sem o arquivo `obs_rotina.env` ela apura e gera a página, mas não publica.

Para comparar duas bases, guarde cada CSV em `snapshots/SISANT_AAAA-MM-DD.csv` (a data vem
da primeira linha do arquivo). Os checksums em `checksums.txt` dizem exatamente quais
arquivos foram usados em cada edição.

## Decisões de método

Todas declaradas na página, embaixo de cada gráfico. As que mais mudam o resultado:

- **Data de cadastro não existe no arquivo.** É derivada de `DATA_VALIDADE − 24 meses`. O
  script confere a premissa antes de usar e aborta se algum cadastro cair no futuro.
- **A série mensal conta emissões**, primeiro cadastro e renovação somados, porque uma base
  sozinha não os separa. A separação vem de `obs_diff.py`, comparando dois arquivos código a
  código: código novo, renovação (mesmo código, validade adiantada) e saída.
- **Diferença de totais entre duas bases é saldo, nunca "cadastros novos".** Entre 04/08 e
  20/09/2026 o saldo foi +8.385, mas entraram 14.988 códigos e saíram 6.603.
- **UF vem do CNPJ consultado na Receita** e cobre só a parcela empresarial; o CPF vem
  mascarado. O recorte por estado é a UF do endereço cadastral, não onde o drone voa.
- **Frota não é mercado.** Shows de drone de luz registram mais de mil aeronaves em um CNPJ.
  A métrica de mercado por estado conta empresas; a frota aparece à parte.
- **Campos livres são limpos antes de contar.** Fabricante, modelo e ramo têm milhares de
  grafias. Modelos são colapsados por família; códigos internos de fábrica só são traduzidos
  quando a própria base concorda em pelo menos 80% das linhas.
- **Checagens antes de publicar.** Cada recorte tem de somar o total do arquivo (diferença
  só por filtro documentado), a premissa dos 24 meses tem de valer e o total não pode variar
  mais de 15% contra a edição anterior. Se uma falha, nada sobe.

## Arquivos

| Arquivo | O que é |
|---|---|
| `obs_apura.py` | Lê o CSV e gera `obs-drone.json` com todos os recortes. Versão do método e histórico ficam aqui. |
| `obs_diff.py` | Compara os dois últimos snapshots por `CODIGO_AERONAVE`. |
| `obs_build.py` | Gera a página estática (SVG inline, tabela por seção, JSON-LD Dataset) e a pasta `dados/`. |
| `apura_uf.py`, `consulta_uf.py` | Agregam a frota por CNPJ e consultam a UF (minhareceita.org, BrasilAPI como reserva). |
| `obs_rotina.py` | Rotina mensal. |
| `cnpj-uf-cache.json` | UF, município e CNAE por CNPJ, da Receita Federal. Sem razão social. |
| `dados/observatorio-drone-brasil-AAAA-MM-DD.json` | Resultados consolidados de cada edição. |
| `dados/movimento-A-a-B.json` | Entradas, renovações e saídas entre duas bases. |
| `checksums.txt` | SHA-256 dos arquivos da ANAC usados. |
| `obs-fonts/` | Source Serif 4, IBM Plex Mono e Inter, licença OFL. |

Os JSONs em `dados/` são **consolidados e agregados**; os registros individuais estão no
arquivo da ANAC. Os arquivos brutos não são redistribuídos aqui.

## Versões

A versão do método (`VERSAO_METODO` em `obs_apura.py`) sobe quando muda uma regra de
contagem, normalização ou recorte, não quando entra uma base nova. Cada edição em `dados/`
guarda a data da base, a data de processamento e a versão com que foi apurada. O histórico
está em [CHANGELOG.md](CHANGELOG.md).

## Licença e citação

Código sob [MIT](LICENSE). Dados consolidados em `dados/` sob
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br): use, cite e linke.
A fonte primária é a ANAC (dados abertos).

> MENEZES, Irlen. Observatório do Drone no Brasil, base ANAC de 20/09/2026. Apuração sobre
> o SISANT. Disponível em: https://irlenmenezes.com.br/observatorio-drone-brasil/

Metadados para gerenciadores de referência em [CITATION.cff](CITATION.cff).

## Autor

Irlen Menezes, cientista de dados formado pela PUC Minas, com experiência em legislação e
regulação de drones no Brasil. Autor do blog de drones de https://irlenmenezes.com.br e das
ferramentas gratuitas para pilotos. Entrevista, pauta ou pedido de recorte:
https://irlenmenezes.com.br/contato/
