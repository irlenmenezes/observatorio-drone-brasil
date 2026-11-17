# Histórico do método

A versão sobe quando muda uma regra de contagem, normalização ou recorte. Base nova não muda a versão.
Releases com um quarto número (ex.: 2026.11.1.1) trazem mudança de código, página ou rotina sem mudar o método.

## 2026.11.1.1 (17/11/2026) · método continua 2026.11.1
- Rotina passa de mensal para semanal (toda segunda). A ANAC atualiza o arquivo do SISANT várias vezes por mês; a rotina só publica quando a base é mais nova que a da página. As entradas e saídas continuam na janela fixa de cerca de 30 dias.
- Página: o título fica em até ~61 caracteres para o nome do Observatório não ser cortado no resultado de busca; pergunta frequente nova ("Qual o drone mais vendido do Brasil?"), respondida com o modelo mais cadastrado e o aviso de que o SISANT não registra venda; nome na trilha de navegação do JSON-LD; textos dizem "toda semana".

## 2026.11.1 (14/11/2026)
- Seção Agro, nova: drones agrícolas da ANAC cruzados com o registro de aviação agrícola do MAPA (SIPEAGRO, dados abertos) e com a área plantada da PAM 2025 do IBGE. Drone agrícola é o cadastro vigente com ramo agrícola ou de pulverização, ou com modelo de pulverizador declarado em outro ramo (2 kg ou mais). O casamento é drone a drone pelos 9 dígitos do número (PS no MAPA, PP na ANAC). Scripts novos: `obs_mapa_baixa.py`, `obs_agro.py`, `obs_agro_html.py`; referências fixas em `obs-agro-ref/`. O resultado entra no bloco `agro` do JSON da edição, com versão própria em `meta.versao_metodo_agro`.
- Privacidade na seção Agro: só agregados. Município com 1 ou 2 operadores (ou empresas) vira a faixa "1 a 2" e só aparece pelo nome com zero ou 3 ou mais. O CSV do MAPA, que tem e-mail, telefone e nome de pessoa física, nunca é publicado nem versionado; entra só o SHA-256 em `checksums.txt`. O script varre o JSON antes de gravar e a rotina varre a página antes de publicar.
- Onze checagens próprias da seção Agro; se uma falha, a página sai sem a seção, nunca com número errado.
- A pergunta "quantos drones agrícolas" passa a usar a regra da seção (ramo + modelo de pulverizador, só vigente). Antes contava só o ramo (14.210 na base de 01/11/2026), e a página ficaria com dois números para a mesma coisa.
- Snapshot do arquivo do MAPA a cada execução da rotina, porque ele não tem data por linha. A série do lado do MAPA começa em 14/11/2026.
- Rotina: a conferência depois de publicar lia o `dateModified` da página, que desde 02/11 é a data de processamento. Com base e processamento em dias diferentes, a rotina publicava e acusava falha. Agora lê o `version` do Dataset, que é a data da base. O backup do servidor não é mais sobrescrito quando a mesma base é reprocessada.
- Página (apresentação, sem mudar contagem): barra inferior no celular com quatro atalhos e o botão Explorar, que abre a lista de todas as seções, agora com as quatro seções agro (a barra entrou no código em 30/10); título e H1 em forma de pergunta, resposta direta no topo, perguntas frequentes geradas dos dados, JSON-LD com WebPage, Dataset, FAQPage e BreadcrumbList, e `sitemap.xml` gerado no build com a data real (02/11).
- As edições de 13/11 e 14/11/2026 já trazem o bloco `agro` (método agro 2026.11.1), mas o campo `versao_metodo` delas ainda diz 2026.10.1, porque a apuração do SISANT rodou antes da troca do rótulo. A contagem do SISANT não mudou entre as duas versões. A partir da próxima base, o campo sai como 2026.11.1.

## 2026.10.1 (30/10/2026)
- Entradas e saídas passam a usar janela fixa de cerca de 30 dias: a base atual contra a base arquivada de 28 a 32 dias antes (a mais próxima de 30, se não houver). Antes eram as duas últimas bases, com janelas de 12 a 28 dias que não se comparavam entre edições. A página mostra as datas e o número de dias; o JSON de movimento registra `janela_alvo_dias` e `janela_ajustada`. Seção renomeada para "O que entrou e o que saiu em N dias".

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
