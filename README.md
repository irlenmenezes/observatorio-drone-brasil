# Observatório do Drone no Brasil

Apuração aberta e reproduzível do cadastro nacional de drones (SISANT/ANAC), publicada em
**https://irlenmenezes.com.br/observatorio-drone-brasil/**.

Este repositório guarda o código que faz a apuração, os resultados consolidados de cada
edição e o checksum de cada arquivo de origem usado. Qualquer pessoa consegue baixar os
mesmos arquivos nas fontes oficiais, rodar os mesmos scripts e chegar aos mesmos números.

Desde 14/11/2026 o Observatório tem também uma seção Agro, que cruza os drones agrícolas da
ANAC com o registro de aviação agrícola do MAPA e com a área plantada do IBGE.

Edição corrente: **base ANAC de 14/11/2026, 193.411 registros, método 2026.11.1** (seção Agro
com o arquivo do MAPA de 08/11/2026 e a PAM 2025 do IBGE).

## Fontes

| Fonte | O que vem dela | Onde baixar |
|---|---|---|
| ANAC, SISANT | Cadastro de drones: código, validade, operador (CPF mascarado ou CNPJ), fabricante, modelo, peso, ramo declarado | https://sistemas.anac.gov.br/dadosabertos/Aeronaves/drones%20cadastrados/SISANT.csv |
| Receita Federal, via [Minha Receita](https://minhareceita.org) | UF, município e CNAE da sede de cada CNPJ (BrasilAPI como reserva) | consulta por CNPJ em `consulta_uf.py` |
| MAPA, SIPEAGRO (dados abertos) | Registro de aviação agrícola: estabelecimentos, situação do registro e números das aeronaves | https://dados.agricultura.gov.br/dataset/sipeagro |
| IBGE, PAM (SIDRA, tabela 5457) | Área plantada ou destinada à colheita por município, UF e Brasil, ano de 2025 | https://sidra.ibge.gov.br/tabela/5457 |

A lista de municípios vem da API de localidades do IBGE. Os arquivos do IBGE usados estão em
`obs-agro-ref/`, porque a PAM é anual e a seção usa sempre o mesmo ano até sair o próximo.

## O que é medido

O SISANT é um cadastro de **aeronaves**: cada linha é um drone registrado, com código,
validade, operador (CPF mascarado ou CNPJ), tipo de uso, fabricante, modelo, número de
série, peso máximo de decolagem e ramo de atividade declarado.

Cadastro permite concluir quantas aeronaves estão registradas, de que modelo, faixa de
peso, tipo de uso e ramo, e em nome de CPF ou de CNPJ. **Não** permite concluir quantas
pessoas têm drone, quanto cada marca vendeu, quantas horas cada modelo voa nem onde o drone
opera. Todos os rótulos do Observatório seguem essa distinção.

## Reproduzir a apuração

Python 3.11 ou mais novo. A apuração não tem dependências externas.

```bash
git clone https://github.com/irlenmenezes/observatorio-drone-brasil.git
cd observatorio-drone-brasil

# 1. baixe o arquivo oficial da ANAC (é público)
curl -o SISANT_new.csv "https://sistemas.anac.gov.br/dadosabertos/Aeronaves/drones%20cadastrados/SISANT.csv"

# 2. (opcional) UF das empresas: agrega os CNPJs e consulta os que faltam no cache
python apura_uf.py
python consulta_uf.py

# 3. apura, compara com a base de cerca de 30 dias antes (se houver snapshot) e gera a página
python obs_apura.py      # -> obs-drone.json (aborta se uma checagem de consistência falhar)
python obs_diff.py       # -> obs-diff.json (precisa de duas bases em snapshots/)
python obs_build.py      # -> site/index.html + site/dados/
```

Para incluir a seção Agro, rode antes do `obs_build.py`:

```bash
# baixa o CSV do MAPA com o Chrome instalado (pip install playwright) e guarda em snapshots/mapa/
python obs_mapa_baixa.py
# ou baixe o CSV à mão na página do SIPEAGRO e passe o caminho direto:
python obs_agro.py caminho/sipeagroaviacaoagricolaregistro.csv   # -> obs-agro.json
```

O `obs_build.py` só monta a seção Agro se o `obs-agro.json` for da mesma base ANAC da página.
Sem ele, a página sai completa, só que sem as seções agro.

`obs_rotina.py` encadeia tudo isso todo mês: baixa o CSV da ANAC e o do MAPA, guarda os
snapshots, apura, gera e publica. Se o download ou a apuração do MAPA falhar, a página sai
sem a seção Agro em vez de não sair. Sem o arquivo `obs_rotina.env` a rotina apura e gera a
página, mas não publica.

Para comparar duas bases, guarde cada CSV em `snapshots/SISANT_AAAA-MM-DD.csv` (a data vem
da primeira linha do arquivo). Os checksums em `checksums.txt` dizem exatamente quais
arquivos foram usados em cada edição, inclusive o do MAPA.

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

## Seção Agro: ANAC x MAPA x IBGE

A pergunta é simples: quantos drones agrícolas cadastrados na ANAC aparecem no registro de
aviação agrícola do MAPA, e onde estão as sedes de quem opera em relação a onde se planta.
Na base de 14/11/2026 são 14.628 drones agrícolas vigentes na ANAC, e 30,9% deles aparecem
num registro ativo do MAPA.

Como a conta é feita (`obs_agro.py`):

- **Drone agrícola** é o cadastro vigente com ramo agrícola ou de pulverização (a mesma
  classificação de ramo do resto do Observatório) ou com modelo de pulverizador (Agras, MG-1,
  XAG, EAVision e outros) declarado em outro ramo, com 2 kg ou mais e sem nome de drone de
  consumo. Deduplicado por código e dono.
- **O cruzamento é pelos 9 dígitos do número.** O MAPA grava o drone como PS seguido de 9
  dígitos; a ANAC lista o mesmo número com o prefixo PP. Os 9 dígitos não se repetem no
  SISANT, então o casamento é drone a drone. Quando os dois lados são empresa, o dono confere
  em 97% dos casos (mesma raiz de CNPJ).
- **Operador do MAPA** é o estabelecimento com registro ativo e pelo menos um drone na lista,
  sem as entidades que só dão curso.
- **Área plantada** é a variável 8331 da tabela 5457 da PAM (lavouras temporárias e
  permanentes), em hectares.
- **Onze checagens** antes de gravar: CPF + CNPJ somam a frota agrícola, ramo + modelo
  também, faixas de peso somam, as situações dos operadores fecham, a soma das UFs da PAM dá
  o Brasil, a frota agrícola não varia mais de 15% contra a edição anterior, entre outras. Se
  uma falha, o script não grava nada e a página sai sem a seção.

### Privacidade

O CSV do MAPA traz e-mail, telefone, nome de pessoa física e nome do responsável técnico.
Nada disso sai daqui:

- o CSV fica só na máquina de quem apura (`snapshots/mapa/`), não vai para o servidor nem
  para este repositório. Aqui só entra o SHA-256 dele, em `checksums.txt`;
- o JSON e a página têm só agregados: totais nacionais, por UF e por município;
- **município com 1 ou 2 operadores não aparece com o número**: a contagem vira a faixa
  "1 a 2". O nome do município só aparece com zero ou com 3 ou mais operadores. A mesma regra
  vale para a contagem de empresas da ANAC por município;
- antes de gravar, `obs_agro.py` varre o próprio JSON atrás de e-mail, telefone, CPF
  mascarado e de qualquer nome de pessoa física ou responsável técnico do arquivo do MAPA.
  Achou, não grava. Antes de publicar, a rotina varre a página e os JSON de novo atrás de
  e-mail e telefone; se achar, regera sem a seção Agro e, se ainda achar, não publica.

### Limites da seção Agro

1. **Operador do MAPA não é drone.** O registro é do estabelecimento; a lista de aeronaves
   dentro dele tem código fora do formato e drone repetido entre registros.
2. **Sede não é onde se opera.** UF e município da ANAC vêm do endereço do CNPJ na Receita;
   os do MAPA, do endereço do estabelecimento. Nenhum recorte diz onde mais se pulveriza.
   Prestador de serviço costuma ficar na cidade-polo e voar num raio grande.
3. **Pessoa física não tem UF na ANAC.** Mais da metade da frota agrícola está em CPF, então
   toda tabela por estado, do lado da ANAC, é só CNPJ.
4. **Fora do MAPA não é o mesmo que irregular.** A frota da ANAC inclui fabricante, revenda,
   estoque e empresa de pesquisa, que a Portaria MAPA 298/2021 dispensa do registro (art. 27).
   E frota cadastrada não é frota voando.
5. **O ramo é declarado pelo próprio operador.** Há drones de até 2 kg no ramo de
   pulverização; ficam na conta porque o ramo é a regra do Observatório, mas é ruído.
6. **Área plantada soma safra e safrinha.** O mesmo talhão de soja e milho conta duas vezes,
   e entram lavouras permanentes. Hectare por drone serve para comparar lugares, não mede
   capacidade.
7. **O arquivo do MAPA não tem data por linha.** Não dá para saber quando cada operador se
   registrou. A série do lado do MAPA sai das cópias guardadas a cada execução da rotina, a
   primeira de 14/11/2026.
8. **Endereço de CNPJ vem de espelho da Receita** (Minha Receita, competência 2026-10, mais as
   consultas mensais do Observatório para CNPJ novo).

## Arquivos

| Arquivo | O que é |
|---|---|
| `obs_apura.py` | Lê o CSV e gera `obs-drone.json` com todos os recortes. Versão do método e histórico ficam aqui. |
| `obs_diff.py` | Compara a base atual com a base arquivada de cerca de 30 dias antes, por `CODIGO_AERONAVE`. |
| `obs_build.py` | Gera a página estática (SVG inline, tabela por seção, JSON-LD com Dataset e perguntas frequentes, barra inferior no celular) e a pasta `dados/`. |
| `apura_uf.py`, `consulta_uf.py` | Agregam a frota por CNPJ e consultam a UF (minhareceita.org, BrasilAPI como reserva). |
| `obs_mapa_baixa.py` | Baixa o CSV de registro de aviação agrícola do MAPA e guarda um snapshot datado em `snapshots/mapa/` (fora do repositório). |
| `obs_agro.py` | Apura a seção Agro: regra do drone agrícola, cruzamento ANAC x MAPA, PAM, checagens e varredura de privacidade. Gera `obs-agro.json`. |
| `obs_agro_html.py` | Monta as seções agro da página a partir do `obs-agro.json`. |
| `obs_rotina.py` | Rotina mensal. |
| `cnpj-uf-cache.json` | UF, município e CNAE por CNPJ, da Receita Federal. Sem razão social. |
| `obs-agro-ref/` | Referências fixas da seção Agro: PAM 2025 do IBGE (Brasil, UF e município), metadados da tabela 5457, lista de municípios do IBGE e UF + código IBGE da sede de cada CNPJ (Receita, competência 2026-10, sem razão social). |
| `dados/observatorio-drone-brasil-AAAA-MM-DD.json` | Resultados consolidados de cada edição. A partir de 13/11/2026 trazem também o bloco `agro`. |
| `dados/movimento-A-a-B.json` | Entradas, renovações e saídas entre duas bases. |
| `checksums.txt` | SHA-256 dos arquivos da ANAC e do MAPA usados. |
| `obs-fonts/` | Big Shoulders Display, IBM Plex Mono, Inter e Source Serif 4 (esta última não é mais usada na página), licença OFL. |

Os JSONs em `dados/` são **consolidados e agregados**. Os arquivos brutos (o CSV da ANAC e o
do MAPA) não são redistribuídos aqui: os registros individuais ficam nas fontes oficiais.

## Versões

A versão do método (`VERSAO_METODO` em `obs_apura.py`) sobe quando muda uma regra de
contagem, normalização ou recorte, não quando entra uma base nova. Cada edição em `dados/`
guarda a data da base, a data de processamento e a versão com que foi apurada; o bloco
`agro` tem a sua em `meta.versao_metodo_agro`. O histórico está em [CHANGELOG.md](CHANGELOG.md).

## Licença e citação

Código sob [MIT](LICENSE). Dados consolidados em `dados/` sob
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br): use, cite e linke.
As fontes primárias são a ANAC, o MAPA e o IBGE (dados abertos).

> MENEZES, Irlen. Observatório do Drone no Brasil, base ANAC de 14/11/2026. Apuração sobre
> o SISANT. Disponível em: https://irlenmenezes.com.br/observatorio-drone-brasil/

Metadados para gerenciadores de referência em [CITATION.cff](CITATION.cff).

## Autor

Irlen Menezes, cientista de dados formado pela PUC Minas, com experiência em legislação e
regulação de drones no Brasil. Autor do blog de drones de https://irlenmenezes.com.br e das
ferramentas gratuitas para pilotos. Entrevista, pauta ou pedido de recorte:
https://irlenmenezes.com.br/contato/
