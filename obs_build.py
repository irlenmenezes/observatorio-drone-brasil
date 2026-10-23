#!/usr/bin/env python3
"""
Monta a pagina do Observatorio do Drone no Brasil a partir de obs-drone.json.

Tudo e renderizado no build, nao no navegador: os graficos saem como SVG inline e
cada recorte tem tabela HTML de verdade. Isso e proposital. Grafico desenhado por
JavaScript nao e lido por LLM e vira uma pagina vazia para quem cita. Aqui o numero
esta no codigo-fonte, entao Google, Perplexity e ChatGPT leem sem executar nada.

Uso:  python obs_build.py    ->  ../../observatorio-drone/index.html
"""
import json
import math
import os
import shutil
from pathlib import Path

BASE = Path(__file__).parent
DADOS = BASE / "obs-drone.json"
# Saida: OBS_DESTINO, senao a pasta irma "observatorio-drone" (layout de producao),
# senao ./site (layout de um clone do repositorio)
_padrao = BASE.parent / "observatorio-drone"
DESTINO = Path(os.environ.get("OBS_DESTINO") or (_padrao if _padrao.exists() else BASE / "site"))
CANONICA = "https://irlenmenezes.com.br/observatorio-drone-brasil/"
REPO = "https://github.com/irlenmenezes/observatorio-drone-brasil"  # codigo, edicoes e checksums

d = json.loads(DADOS.read_text(encoding="utf-8"))
META, RES = d["meta"], d["resumo"]
# comparacao entre as duas ultimas bases (obs_diff.py). Opcional: sem duas
# bases guardadas a secao "movimento" simplesmente nao entra.
DIFF_ARQ = BASE / "obs-diff.json"
DIFF = json.loads(DIFF_ARQ.read_text(encoding="utf-8")) if DIFF_ARQ.exists() else None
if DIFF and DIFF.get("base_atual") != META["data_base"]:
    DIFF = None  # diff velho nao pode descrever base nova
# edicoes anteriores guardadas (obs-drone-AAAA-MM-DD.json), para o arquivo de versoes
EDICOES = sorted(p.name[10:20] for p in BASE.glob("obs-drone-????-??-??.json")
                 if p.name[10:20] != META["data_base"])

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun",
            "jul", "ago", "set", "out", "nov", "dez"]


def num(n) -> str:
    return f"{n:,}".replace(",", ".")


def pct(x, casas=1) -> str:
    return f"{x * 100:.{casas}f}".replace(".", ",") + "%"


def rotulo_mes(m: str, curto=False) -> str:
    a, mes = m.split("-")
    return f"{MESES_PT[int(mes) - 1]}/{a[2:] if curto else a}"


def data_br(iso: str) -> str:
    a, m, dia = iso.split("-")
    return f"{dia}/{m}/{a}"


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# ----------------------------------------------------------------- graficos
def escala(vmax, divisoes=4):
    """Passo e topo em numero redondo. Sem isso o eixo sai com tick tipo 4.875."""
    bruto = vmax / divisoes
    exp = 10 ** math.floor(math.log10(bruto))
    passo = next(m * exp for m in (1, 2, 2.5, 5, 10) if bruto <= m * exp)
    topo = passo * divisoes
    while topo < vmax:
        topo += passo
    return passo, topo


def colunas(dados, chave_x, chave_y, destaque=None, alt_texto="", parciais=(), nota_parcial=""):
    """Grafico de colunas em SVG. dados = lista de dicts."""
    W, H, PAD_L, PAD_R, PAD_T, EIXO = 900, 300, 54, 14, 26, 38
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T
    vmax = max(x[chave_y] for x in dados)
    passo, topo = escala(vmax)
    banda = plot_w / len(dados)
    larg = min(24, banda - 6)
    r = 4

    partes = [f'<svg viewBox="0 0 {W} {H + EIXO}" role="img" aria-label="{esc(alt_texto)}" '
              f'class="ch">']
    # grade: hairline solida, um passo fora da superficie
    for i in range(int(round(topo / passo)) + 1):
        v = passo * i
        y = PAD_T + plot_h - (v / topo) * plot_h
        partes.append(f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}"/>')
        partes.append(f'<text class="tick" x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end">'
                      f'{num(int(v))}</text>')

    for i, item in enumerate(dados):
        v = item[chave_y]
        h = (v / topo) * plot_h
        x = PAD_L + i * banda + (banda - larg) / 2
        y = PAD_T + plot_h - h
        parcial = item[chave_x] in parciais
        # ênfase por opacidade, não por matiz novo: o pico se destaca sem inventar cor
        cls = ("bar parcial" if parcial else
               "bar destaque" if item[chave_x] == destaque else "bar")
        dica = (f'<title>{rotulo_mes(item[chave_x])}: {num(v)}'
                f'{" (mês incompleto)" if parcial else ""}</title>')
        # a area de hover cobre a banda inteira, nao so a barra fina
        alvo = (f'<rect class="hit" x="{PAD_L + i * banda:.1f}" y="{PAD_T}" '
                f'width="{banda:.1f}" height="{plot_h:.1f}"/>')
        if h < r:
            marca = (f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{larg:.1f}" '
                     f'height="{max(h, 1):.1f}"/>')
        else:
            marca = (f'<path class="{cls}" d="M{x:.1f} {PAD_T + plot_h:.1f} L{x:.1f} {y + r:.1f} '
                     f'Q{x:.1f} {y:.1f} {x + r:.1f} {y:.1f} L{x + larg - r:.1f} {y:.1f} '
                     f'Q{x + larg:.1f} {y:.1f} {x + larg:.1f} {y + r:.1f} '
                     f'L{x + larg:.1f} {PAD_T + plot_h:.1f} Z"/>')
        partes.append(f'<g class="col">{dica}{alvo}{marca}</g>')
        # rotulo direto so no pico: numero em toda barra vira ruido
        if item[chave_x] == destaque:
            partes.append(f'<text class="valor" x="{x + larg / 2:.1f}" y="{y - 7:.1f}" '
                          f'text-anchor="middle">{num(v)}</text>')
        # eixo x: rotula o suficiente para orientar, sem empilhar texto
        passo_rot = max(1, round(len(dados) / 9))
        if i % passo_rot == 0 or i == len(dados) - 1:
            partes.append(f'<text class="tick" x="{x + larg / 2:.1f}" y="{H + 18}" '
                          f'text-anchor="middle">{rotulo_mes(item[chave_x], True)}</text>')

    partes.append(f'<line class="eixo" x1="{PAD_L}" y1="{PAD_T + plot_h}" '
                  f'x2="{W - PAD_R}" y2="{PAD_T + plot_h}"/>')
    partes.append("</svg>")
    return "".join(partes)


def barras_h(itens, total_ref=None, cor="s1", limite=None, ranking=True, cores=None):
    """Barras horizontais em HTML: texto real, responsivo, sem clipping."""
    mostrados = itens[:limite] if limite else itens
    vmax = max(v for _, v in mostrados) or 1
    linhas = []
    for i, (rotulo, v) in enumerate(mostrados):
        share = f'<span class="sh">{pct(v / total_ref)}</span>' if total_ref else ""
        pos = f'<span class="bh-r">{i + 1:02d}</span>' if ranking else ""
        c = cores[i] if cores else cor
        # o atraso escalonado faz a lista "preencher" de cima para baixo
        atraso = f"--i:{min(i, 15)}"
        linhas.append(
            f'<div class="bh" style="{atraso}">'
            f'<div class="bh-l">{pos}<span>{esc(rotulo)}</span></div>'
            f'<div class="bh-t"><i class="{c}" style="--w:{v / vmax * 100:.2f}%"></i></div>'
            f'<div class="bh-v"><b>{num(v)}</b>{share}</div></div>')
    return '<div class="bhs">' + "".join(linhas) + "</div>"


def tabela(cabecalhos, linhas, resumo=None):
    ths = "".join(f"<th{' class=n' if i else ''}>{esc(c)}</th>" for i, c in enumerate(cabecalhos))
    trs = []
    for ln in linhas:
        tds = "".join(f"<td{' class=n' if i else ''}>{c}</td>" for i, c in enumerate(ln))
        trs.append(f"<tr>{tds}</tr>")
    cap = f"<caption>{esc(resumo)}</caption>" if resumo else ""
    return (f'<div class="tw"><table>{cap}<thead><tr>{ths}</tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table></div>')


_contador = [0]


def bloco(id_, titulo, chapeu, corpo, nota=None, tabela_html=None,
          rotulo_tab="Ver todos os dados", etiqueta=None):
    """Uma seção do relatório. A numeração editorial 01→10 dá sequência de leitura."""
    _contador[0] += 1
    n = (f'<div class="nota"><span class="nota-t">Como este número foi apurado</span>'
         f'<p>{nota}</p></div>') if nota else ""
    t = (f'<details><summary><span>{rotulo_tab}</span></summary>{tabela_html}</details>'
         ) if tabela_html else ""
    tag = f'<span class="sec-tag">{esc(etiqueta)}</span>' if etiqueta else ""
    return (f'<section id="{id_}" class="sec">'
            f'<div class="sec-h"><span class="sec-n">{_contador[0]:02d}</span>'
            f'<div class="sec-t"><h2>{titulo}</h2>{tag}<p class="chapeu">{chapeu}</p></div></div>'
            f'<div class="sec-c">{corpo}{n}{t}</div></section>')


# ------------------------------------------------------------------ conteudo
serie = d["serie"]
parciais = {s["mes"] for s in serie if s.get("parcial")}
completos = [s for s in serie if not s.get("parcial")]
pico = max(completos, key=lambda s: s["novos"])
primeiro = completos[0]
mes_parcial = next((s for s in serie if s.get("parcial")), None)
ritmo = mes_parcial["novos"] / mes_parcial["dias"] if mes_parcial else 0

venc = d["vencimentos"]
venc12 = venc[:12]
venc_pico = max(venc12, key=lambda v: v["qtd"])
soma12 = sum(v["qtd"] for v in venc12)

uf_emp = sorted(d["uf"]["empresas"].items(), key=lambda x: -x[1])
uf_frota = d["uf"]["frota"]
uf_limpa = d["uf"]["frota_sem_enxame"]
total_emp = sum(d["uf"]["empresas"].values())

modelos = d["modelos"]
fabs = d["fabricantes"]
ramos = list(d["ramos"].items())
peso = d["peso"]
ORDEM_PESO = ["Ate 250 g", "250 g a 2 kg", "2 a 25 kg", "Acima de 25 kg"]
ROTULO_PESO = {"Ate 250 g": "Até 250 g", "250 g a 2 kg": "250 g a 2 kg",
               "2 a 25 kg": "2 a 25 kg", "Acima de 25 kg": "Acima de 25 kg"}
prefixo = d["uso"]["prefixo"]
conc = d["concentracao"]

T = RES["total"]
dji = next(f for f in fabs if f["marca"] == "DJI")
sub250 = peso["Ate 250 g"]
recreativo = prefixo.get("PR", 0)
nao_recreativo = prefixo.get("PP", 0)
avancado = prefixo.get("PS", 0)

# ---------------------------------------------------------- curva de concentracao
def curva():
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 900, 300, 58, 20, 22, 40
    pw, ph = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    pontos = [(0, 0)] + [(c["top"] / conc[-1]["top"], c["share"]) for c in conc]
    coords = [(PAD_L + x * pw, PAD_T + ph - y * ph) for x, y in pontos]
    dpath = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    partes = [f'<svg viewBox="0 0 {W} {H}" role="img" class="ch" '
              f'aria-label="Curva de concentração da frota empresarial">']
    for i in range(5):
        y = PAD_T + ph - (i / 4) * ph
        partes.append(f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}"/>')
        partes.append(f'<text class="tick" x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end">{i * 25}%</text>')
    partes.append(f'<path class="area" d="{dpath} L{coords[-1][0]:.1f} {PAD_T + ph} L{PAD_L} {PAD_T + ph} Z"/>')
    partes.append(f'<path class="linha" d="{dpath}"/>')
    for (x, y), c in zip(coords[1:], conc):
        partes.append(f'<circle class="pt" cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
        partes.append(f'<title>top {num(c["top"])} empresas: {pct(c["share"])} da frota</title>')
    for idx in (0, len(conc) - 1):
        x, y = coords[idx + 1]
        # afasta o rotulo da propria curva: colado, ele lê como parte da linha
        dx = 14 if idx == 0 else -11
        dy = 20 if idx == 0 else -15  # o primeiro ponto fica no joelho da curva: rotulo abaixo, senao a linha corta
        partes.append(f'<text class="valor" x="{x + dx:.1f}" y="{y + dy:.1f}" '
                      f'text-anchor="{"start" if idx == 0 else "end"}">{pct(conc[idx]["share"])}</text>')
        partes.append(f'<text class="tick" x="{x:.1f}" y="{PAD_T + ph + 20:.1f}" '
                      f'text-anchor="{"start" if idx == 0 else "end"}">top {num(conc[idx]["top"])}</text>')
    partes.append(f'<line class="eixo" x1="{PAD_L}" y1="{PAD_T + ph}" x2="{W - PAD_R}" y2="{PAD_T + ph}"/>')
    partes.append("</svg>")
    return "".join(partes)


# ------------------------------------------------------------------- secoes
secoes = []

secoes.append(bloco(
    "crescimento",
    "Quantos drones entram no cadastro por mês",
    f"O cadastro brasileiro saiu de {num(primeiro['novos'])} emissões em "
    f"{rotulo_mes(primeiro['mes'])} para {num(pico['novos'])} em {rotulo_mes(pico['mes'])}, "
    f"o maior volume da série. São {pct(pico['novos'] / primeiro['novos'] - 1, 0)} de aumento "
    f"em {len(completos)} meses.",
    # o mes corrente fica fora do grafico: 4 dias ao lado de meses fechados
    # desenharia um despencar que nao aconteceu. O numero vai no texto e na tabela.
    colunas(completos, "mes", "novos", destaque=pico["mes"],
            alt_texto=f"Emissões de cadastro por mês, de {rotulo_mes(completos[0]['mes'])} a "
                      f"{rotulo_mes(completos[-1]['mes'])}, com pico de {num(pico['novos'])}"),
    nota="A ANAC não publica a data do cadastro, só a validade. Como a validade é de 24 meses, "
         "a data de emissão é a validade menos 24 meses, e o script confere essa premissa antes "
         "de usar. Cada barra conta <strong>emissões</strong>: primeiro cadastro e renovação "
         f"entram juntos. A série começa em {rotulo_mes(serie[0]['mes'])} porque o arquivo lista "
         "apenas cadastro vigente, então mês mais antigo que isso apareceria vazio por construção, "
         f"não por falta de mercado. O gráfico vai até o último mês fechado: "
         f"{rotulo_mes(mes_parcial['mes'])} tem {num(mes_parcial['novos'])} emissões em "
         f"{mes_parcial['dias']} dias, ritmo de {num(round(ritmo))} por dia, e entra só na tabela "
         "para não desenhar uma queda que não existe.",
    tabela_html=tabela(
        ["Mês", "Emissões", "Acumulado no período"],
        [[rotulo_mes(s["mes"]) + (" (parcial)" if s.get("parcial") else ""),
          num(s["novos"]), num(s["acumulado"])] for s in serie],
        f"Emissões de cadastro SISANT por mês. Fonte: ANAC, base de {data_br(META['data_base'])}."),
    etiqueta="Série de 24 meses"
))

if DIFF:
    # A diferenca de totais entre duas bases e um SALDO e esconde tres movimentos.
    # Comparando codigo a codigo da para separar: codigo novo, renovacao e saida.
    dias = DIFF["dias"]
    saldo = DIFF["saldo"]
    novos_cod, renov, saidas = DIFF["codigos_novos"], DIFF["renovacoes"], DIFF["saidas"]
    recad = DIFF["recadastros_mesma_serie"]
    de, ate = data_br(DIFF["base_anterior"]), data_br(DIFF["base_atual"])
    sub250_novos = DIFF["novos_por_peso"].get("Ate 250 g", 0)
    mov = [("Códigos novos no arquivo", novos_cod, "s1"),
           ("Renovações (mesmo código, validade nova)", renov, "s3"),
           ("Saídas (código que sumiu do arquivo)", saidas, "s2")]
    vmax = max(v for _, v, _ in mov)
    mov_html = '<div class="bhs">' + "".join(
        f'<div class="bh" style="--i:{i}"><div class="bh-l"><span>{esc(r)}</span></div>'
        f'<div class="bh-t"><i class="{c}" style="--w:{v / vmax * 100:.2f}%"></i></div>'
        f'<div class="bh-v"><b>{num(v)}</b><span class="sh">{num(round(v / dias))}/dia</span></div></div>'
        for i, (r, v, c) in enumerate(mov)) + "</div>"
    secoes.append(bloco(
        "movimento",
        "O que entrou e o que saiu entre duas bases",
        f"Entre {de} e {ate} o arquivo cresceu {num(saldo)} registros, mas esse número é um saldo. "
        f"Entraram {num(novos_cod)} códigos novos e saíram {num(saidas)}; outros {num(renov)} "
        f"cadastros foram renovados. Todo dia entram cerca de {num(round(novos_cod / dias))} "
        f"aeronaves e saem {num(round(saidas / dias))}.",
        mov_html,
        nota=f"Comparação código a código (CODIGO_AERONAVE) entre os dois arquivos guardados, de "
             f"{de} e {ate}, {dias} dias. <strong>Código novo</strong> é o que não existia no arquivo "
             f"anterior; <strong>renovação</strong> é o mesmo código com validade adiantada; "
             f"<strong>saída</strong> é o código que estava e não está mais. Das saídas, "
             f"{num(DIFF['saidas_ja_vencidas'])} tinham validade até {ate} (venceram) e "
             f"{num(DIFF['saidas_antes_do_prazo'])} saíram antes do prazo (cancelamento ou transferência; "
             f"o arquivo não diz qual). Código novo não é sempre drone novo: {num(recad)} dos códigos novos "
             f"têm o mesmo número de série de um código que saiu, isto é, a mesma aeronave voltou com "
             f"código diferente ({num(DIFF['recadastros_mesmo_dono'])} com o mesmo dono, o resto trocou "
             f"de dono). Descontados esses, são {num(DIFF['aeronaves_novas'])} aeronaves novas no arquivo. "
             f"Dos códigos novos, {num(sub250_novos)} ({pct(sub250_novos / novos_cod)}) pesam até 250 g e "
             f"{num(DIFF['novos_pf'])} ({pct(DIFF['novos_pf'] / novos_cod)}) estão em nome de pessoa física. "
             f"Os {num(DIFF['linhas_atual'] - DIFF['codigos_atual'])} códigos repetidos do arquivo contam uma vez aqui.",
        tabela_html=tabela(
            ["Movimento", "Registros", "Por dia"],
            [["Códigos novos", num(novos_cod), num(round(novos_cod / dias))],
             ["… dos quais recadastro da mesma aeronave", num(recad), num(round(recad / dias))],
             ["… aeronaves novas no arquivo", num(DIFF["aeronaves_novas"]), num(round(DIFF["aeronaves_novas"] / dias))],
             ["Renovações", num(renov), num(round(renov / dias))],
             ["Saídas", num(saidas), num(round(saidas / dias))],
             ["… já vencidas na data da base", num(DIFF["saidas_ja_vencidas"]), ""],
             ["… antes do prazo", num(DIFF["saidas_antes_do_prazo"]), ""],
             ["Saldo (códigos únicos)", f"{saldo:+,}".replace(",", "."), num(round(saldo / dias))]],
            f"Movimento do cadastro entre as bases de {de} e {ate}. Fonte: ANAC, dois arquivos SISANT "
            f"comparados pelo código da aeronave."),
        rotulo_tab="Ver a decomposição completa",
        etiqueta=f"{dias} dias, duas bases"
    ))

secoes.append(bloco(
    "vencimentos",
    "A onda de vencimentos que ninguém avisa",
    f"Cadastro do SISANT vale 24 meses e a ANAC não manda lembrete. Nos próximos 12 meses "
    f"vencem {num(soma12)} cadastros, com pico de {num(venc_pico['qtd'])} em "
    f"{rotulo_mes(venc_pico['mes'])}. Voar com cadastro vencido é o mesmo que voar sem cadastro.",
    colunas(venc12, "mes", "qtd", destaque=venc_pico["mes"],
            alt_texto=f"Cadastros que vencem em cada um dos próximos 12 meses, com pico de "
                      f"{num(venc_pico['qtd'])} em {rotulo_mes(venc_pico['mes'])}"),
    nota=f"Contagem direta do campo DATA_VALIDADE, sem inferência nenhuma. Os {num(RES['vencidos'])} "
         "registros já vencidos na data da base ficam de fora. O gráfico mostra os 12 meses "
         "seguintes, que é a janela em que dá para agir; a tabela abaixo traz os 24. A onda "
         "reproduz, dois anos depois, o próprio ritmo de cadastro do gráfico anterior, então "
         "ela tende a crescer junto com o boom.",
    tabela_html=tabela(
        ["Mês", "Cadastros que vencem"],
        [[rotulo_mes(v["mes"]), num(v["qtd"])] for v in venc],
        f"Vencimentos de cadastro SISANT por mês. Fonte: ANAC, base de {data_br(META['data_base'])}."),
    etiqueta="Prazo correndo"
))

GRADE = {"RR": (3, 0), "AP": (5, 0), "AM": (2, 1), "PA": (4, 1), "MA": (5, 1), "CE": (6, 1), "RN": (7, 1),
         "AC": (1, 2), "RO": (2, 2), "MT": (3, 2), "TO": (4, 2), "PI": (5, 2), "PE": (6, 2), "PB": (7, 2),
         "MS": (3, 3), "GO": (4, 3), "BA": (5, 3), "SE": (6, 3), "AL": (7, 3),
         "DF": (4, 4), "MG": (5, 4), "ES": (6, 4), "SP": (4, 5), "RJ": (5, 5),
         "PR": (4, 6), "SC": (4, 7), "RS": (4, 8)}
REGIAO = {"N": ("Norte", "var(--r-n)", ["AC", "AM", "AP", "PA", "RO", "RR", "TO"]),
          "NE": ("Nordeste", "var(--r-ne)", ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]),
          "CO": ("Centro-Oeste", "var(--r-co)", ["DF", "GO", "MS", "MT"]),
          "SE": ("Sudeste", "var(--r-se)", ["ES", "MG", "RJ", "SP"]),
          "S": ("Sul", "var(--r-s)", ["PR", "RS", "SC"])}
UF_REG = {u: k for k, (_, _, us) in REGIAO.items() for u in us}
uf_emp_map = dict(d["uf"]["empresas"])


def mapa_uf():
    """Mapa em grade (cada estado um quadrado): cor = regiao, intensidade = empresas. Sem geometria externa."""
    vmax = max(v for k, v in uf_emp_map.items() if k in GRADE)
    T_, S_ = 62, 56
    tiles = []
    for uf, (c, r) in GRADE.items():
        n = uf_emp_map.get(uf, 0)
        a = 0.28 + 0.72 * math.sqrt(n / vmax)
        cor = REGIAO[UF_REG[uf]][1]
        txt = "var(--ink)" if a < 0.62 else "#fff"
        x, y = c * T_, r * T_
        tiles.append(f'<g class="ut"><title>{uf}: {num(n)} empresas</title>'
                     f'<rect x="{x}" y="{y}" width="{S_}" height="{S_}" rx="4" fill="{cor}" fill-opacity="{a:.2f}"/>'
                     f'<text x="{x + S_ / 2}" y="{y + 25}" text-anchor="middle" font-size="13" font-weight="500" fill="{txt}">{uf}</text>'
                     f'<text x="{x + S_ / 2}" y="{y + 43}" text-anchor="middle" font-size="12" fill="{txt}">{num(n)}</text></g>')
    svg = (f'<svg viewBox="0 0 {8 * T_} {9 * T_ - 6}" role="img" aria-label="Mapa em grade do Brasil com o número de empresas com drone por estado">'
           + "".join(tiles) + '</svg>')
    reg = []
    for k, (nome, cor, us) in REGIAO.items():
        tot = sum(uf_emp_map.get(u, 0) for u in us)
        reg.append((tot, f'<li style="--c:{cor}"><span class="rn">{num(tot)}</span><div><b>{nome}</b>'
                         f'<span>{" · ".join(us)}</span></div></li>'))
    reg_html = "".join(h for _, h in sorted(reg, reverse=True))
    ex = uf_emp_map.get("EX", 0)
    return (f'<div class="mapa"><div>{svg}</div><div><ul class="reg">{reg_html}</ul>'
            f'<p class="mapa-nota">Empresas por região, pela sede do CNPJ. Cor = região; quanto mais forte, mais empresas. '
            f'Sede no exterior: {num(ex)}.</p></div></div>')


cob = d["uf"]["cobertura"]
secoes.append(bloco(
    "estados",
    "Onde as empresas de drone têm sede",
    f"{esc(uf_emp[0][0])} concentra {num(uf_emp[0][1])} das {num(total_emp)} empresas com drone "
    f"cadastrado ({pct(uf_emp[0][1] / total_emp)}), seguido por {esc(uf_emp[1][0])} "
    f"({num(uf_emp[1][1])}) e {esc(uf_emp[2][0])} ({num(uf_emp[2][1])}). O recorte é pela UF "
    f"do endereço cadastral do CNPJ, não por onde o drone voa.",
    mapa_uf() + barras_h([(uf, n) for uf, n in uf_emp], total_ref=total_emp, limite=12),
    nota="O arquivo da ANAC não traz estado nem município. A localização aqui vem do CNPJ "
         f"consultado na base da Receita, então cobre a fatia empresarial: {num(RES['pj'])} "
         f"registros de {num(T)} ({pct(RES['pj'] / T)}), em {num(cob['cnpjs_com_uf'])} CNPJs "
         f"resolvidos de {num(cob['cnpjs_total'])}. CPF vem mascarado no arquivo e não há como "
         "localizar. <strong>Isto mede o mercado empresarial, não a frota total.</strong> "
         "A coluna de frota sem shows de luz existe porque um único espetáculo de drones "
         "registra mais de mil aeronaves em um CNPJ só e distorceria o ranking.",
    tabela_html=tabela(
        ["UF", "Empresas", "% das empresas", "Frota", "Frota sem shows de luz"],
        [[uf, num(n), pct(n / total_emp), num(uf_frota.get(uf, 0)), num(uf_limpa.get(uf, 0))]
         for uf, n in uf_emp],
        f"Empresas com drone cadastrado pela UF do endereço cadastral do CNPJ. Fonte: ANAC cruzado "
        f"com Receita Federal, base de {data_br(META['data_base'])}. EX = sede no exterior."),
    etiqueta="Recorte empresarial"
))

secoes.append(bloco(
    "modelos",
    "Os modelos mais cadastrados no SISANT",
    f"O {esc(modelos[0]['modelo'].title())} lidera com {num(modelos[0]['qtd'])} unidades. "
    f"Os dez modelos mais registrados somam {num(sum(m['qtd'] for m in modelos[:10]))} aeronaves, "
    f"{pct(sum(m['qtd'] for m in modelos[:10]) / T)} de tudo que está cadastrado. Cadastro mede "
    f"frota registrada, não venda do mês nem horas voadas.",
    barras_h([(m["modelo"].title(), m["qtd"]) for m in modelos], total_ref=T, limite=15),
    nota="O campo MODELO é digitado à mão e o mesmo drone aparece com várias grafias. O Mini 4 Pro, "
         "por exemplo, vinha escrito de três formas diferentes. As grafias são unificadas antes de "
         "contar, senão o pódio sai errado. Códigos internos de fábrica só são traduzidos quando a "
         "própria base concorda, em pelo menos 80% das linhas, sobre qual modelo é.",
    tabela_html=tabela(
        ["Modelo", "Unidades", "% da base"],
        [[m["modelo"].title(), num(m["qtd"]), pct(m["qtd"] / T, 2)] for m in modelos],
        f"Modelos mais registrados no SISANT. Fonte: ANAC, base de {data_br(META['data_base'])}."),
    etiqueta="Dado exclusivo"
))

secoes.append(bloco(
    "fabricantes",
    "A dependência de um fabricante só",
    f"A DJI responde por {num(dji['qtd'])} das {num(T)} aeronaves cadastradas, "
    f"{pct(dji['qtd'] / T)} do total. A segunda colocada tem "
    f"{pct(fabs[1]['qtd'] / T)}.",
    barras_h([(f["marca"], f["qtd"]) for f in fabs], total_ref=T, limite=8),
    nota="O campo FABRICANTE também é livre e vem sujo, com razão social inteira, marca escrita "
         "errada e até o modelo no lugar da marca. As variações são agrupadas por marca antes de "
         "contar. Sem isso, mais de mil aeronaves da DJI apareciam sob um fabricante chamado “D”.",
    etiqueta="Concentração de marca"
))

secoes.append(bloco(
    "atividade",
    "Para que o brasileiro usa drone",
    f"Uso recreativo é o maior grupo isolado, com {num(ramos[0][1])} registros "
    f"({pct(ramos[0][1] / T)}), mas a soma de todos os usos profissionais é maior: "
    f"{num(T - ramos[0][1])} aeronaves, {pct((T - ramos[0][1]) / T)} da base.",
    barras_h([(r, n) for r, n in ramos], total_ref=T, limite=10),
    tabela_html=tabela(
        ["Ramo de atividade", "Aeronaves", "% da base"],
        [[r, num(n), pct(n / T, 2)] for r, n in ramos],
        f"Ramo de atividade declarado no cadastro. Fonte: ANAC, base de {data_br(META['data_base'])}. "
        f"Os mais de 2 mil rótulos livres do arquivo foram agrupados em categorias."),
    etiqueta="2.030 rótulos agrupados"
))

leg = [("Não recreativo (PP)", nao_recreativo, "s1"),
       ("Recreativo (PR)", recreativo, "s2"),
       ("Operação avançada (PS)", avancado, "s3")]
segmentos = "".join(
    f'<i class="{c}" style="width:{v / T * 100:.2f}%" title="{esc(r)}: {num(v)}"></i>'
    for r, v, c in leg)
legenda = "".join(f'<span class="lg"><i class="{c}"></i>{esc(r)} <b>{num(v)}</b> '
                  f'<span class="sh">{pct(v / T)}</span></span>' for r, v, c in leg)
secoes.append(bloco(
    "uso",
    "Recreativo ou profissional, pela letra do cadastro",
    f"A própria matrícula entrega a classificação. {pct(nao_recreativo / T)} das aeronaves "
    f"têm prefixo PP, de uso não recreativo. O prefixo PS, de operação avançada, é a fatia "
    f"minúscula que enfrenta requisito regulatório mais pesado.",
    f'<div class="pilha">{segmentos}</div><div class="lgs">{legenda}</div>',
    nota="<strong>PR é recreativo e PP é não recreativo.</strong> O macete de que “PP é de "
         "particular” circula muito e está errado. PS identifica operação avançada e casa "
         f"exatamente com os {num(avancado)} registros de tipo de uso avançado no arquivo.",
    etiqueta="Pela matrícula"
))

peso_cores = ["o1", "o2", "o3", "o4"]
secoes.append(bloco(
    "peso",
    "O peso da frota e o fim da isenção",
    f"{num(sub250)} aeronaves pesam até 250 g, {pct(sub250 / T)} do cadastro. Esse grupo já foi "
    f"dispensado de cadastro e não é mais: desde 1º de julho de 2026 todo drone precisa de "
    f"registro, independente do peso.",
    # faixa de peso é dimensão ORDENADA, então rampa ordinal (claro→escuro) e
    # sem numeração de ranking: a ordem aqui é o peso, não o tamanho da barra
    barras_h([(ROTULO_PESO[k], peso[k]) for k in ORDEM_PESO], total_ref=T,
             ranking=False, cores=peso_cores),
    nota="Faixas montadas sobre o peso máximo de decolagem declarado. A faixa acima de 25 kg é "
         "quase toda drone agrícola de pulverização, que puxa a média para cima e responde por "
         "boa parte da frota profissional pesada.",
    etiqueta="Regra nova de 2026"
))

top_ops = d["top_operadores"][:10]
secoes.append(bloco(
    "concentracao",
    "A frota empresarial é muito concentrada",
    f"As 50 maiores empresas detêm {pct(conc[0]['share'])} de toda a frota empresarial. "
    f"Metade da frota está em menos de 500 CNPJs, de um universo de {num(RES['cnpjs'])}.",
    curva(),
    nota="Frota grande não é sinônimo de mercado grande. Os maiores operadores da lista são "
         "empresas de show de drone de luz, onde um único espetáculo usa mais de mil aeronaves "
         "com uma equipe pequena. Por isso a métrica de mercado por estado conta empresas, "
         "não aeronaves.",
    tabela_html=tabela(
        ["Recorte", "Aeronaves", "% da frota empresarial"],
        [[f"As {num(c['top'])} maiores empresas", num(c["aeronaves"]), pct(c["share"])]
         for c in conc],
        f"Concentração da frota empresarial. Fonte: ANAC, base de {data_br(META['data_base'])}."
    ) + tabela(
        ["Operador", "Frota", "UF", "Ramo declarado"],
        [[esc(o["nome"]), num(o["frota"]), o["uf"] or "—", esc(o["ramo"])] for o in top_ops],
        f"Dez maiores frotas empresariais. EX = sede no exterior."),
    rotulo_tab="Ver a tabela e os dez maiores operadores",
    etiqueta="Frota PJ"
))

# --------------------------------------------------------------------- HTML
# O hero traz UMA figura heroica (o total). Os tiles trazem o resto, sem repetir
# esse numero: dashboard que repete o mesmo valor duas vezes desperdica o topo.
# Rotulo diz exatamente o que foi contado: o arquivo tem CPF mascarado, entao
# "pessoa fisica" e contagem de AERONAVES em nome de CPF, nao de pessoas distintas.
# O ritmo diario, quando ha duas bases, separa codigo novo de renovacao.
if DIFF:
    tile_ritmo = ("Códigos novos por dia", num(round(DIFF["codigos_novos"] / DIFF["dias"])),
                  f"entre {data_br(DIFF['base_anterior'])} e {data_br(DIFF['base_atual'])}")
else:
    tile_ritmo = ("Emissões por dia", num(round(ritmo)),
                  f"1º cadastro + renovação, {rotulo_mes(mes_parcial['mes'])}")
tiles = [
    ("Aeronaves em nome de CPF", num(RES["pf"]), pct(RES["pf"] / T) + " de toda a base"),
    ("Empresas com drone", num(RES["cnpjs"]), f"{num(RES['pj'])} aeronaves no CNPJ"),
    tile_ritmo,
    ("Participação da DJI", pct(dji["qtd"] / T), f"{num(dji['qtd'])} aeronaves"),
]
tiles_html = "".join(
    f'<div class="tile" style="--i:{i}"><span class="tl">{l}</span>'
    f'<strong class="tv">{v}</strong><span class="td">{s}</span></div>'
    for i, (l, v, s) in enumerate(tiles))

INDICE = [("crescimento", "Crescimento")] + ([("movimento", "Entradas e saídas")] if DIFF else []) + [
          ("vencimentos", "Vencimentos"),
          ("estados", "Por estado"), ("modelos", "Modelos"), ("fabricantes", "Fabricantes"),
          ("atividade", "Atividade"), ("uso", "Recreativo x profissional"),
          ("peso", "Peso"), ("concentracao", "Concentração"), ("metodologia", "Metodologia"),
          ("dados", "Dados e citação")]
indice = "".join(f'<a href="#{i}">{t}</a>' for i, t in INDICE)
N_RECORTES = len(secoes)
POR_EXTENSO = {9: "Nove", 10: "Dez", 11: "Onze", 12: "Doze"}
JSON_ATUAL = f"dados/observatorio-drone-brasil-{META['data_base']}.json"

jsonld = json.dumps({
    "@context": "https://schema.org",
    "@type": "Dataset",
    "name": "Observatório do Drone no Brasil",
    "description": f"Panorama do cadastro de drones no Brasil apurado sobre o arquivo público "
                   f"SISANT da ANAC: {num(T)} aeronaves, evolução mensal, vencimentos, "
                   f"distribuição por estado, modelos, fabricantes e ramo de atividade. "
                   f"Base de {data_br(META['data_base'])}.",
    "url": CANONICA,
    "keywords": ["drone", "SISANT", "ANAC", "cadastro de drone", "Brasil", "RPAS"],
    "temporalCoverage": f"{serie[0]['mes']}/{serie[-1]['mes']}",
    "spatialCoverage": {"@type": "Place", "name": "Brasil"},
    "dateModified": META["data_base"],
    "version": META["data_base"],
    "isAccessibleForFree": True,
    "sameAs": [REPO],
    "citation": f"MENEZES, Irlen. Observatório do Drone no Brasil, base ANAC de {data_br(META['data_base'])}. "
                f"Apuração sobre o SISANT. {CANONICA}",
    "measurementTechnique": "Contagem direta sobre o arquivo público SISANT (ANAC), com normalização "
                            "de fabricante, modelo e ramo de atividade; data de emissão derivada da "
                            "validade menos 24 meses; UF obtida pelo CNPJ na Receita Federal.",
    # DataDownload: sem isso o Google Dataset Search lista o conjunto sem "baixar".
    "distribution": [
        {"@type": "DataDownload", "encodingFormat": "application/json",
         "name": f"Dados consolidados, base de {data_br(META['data_base'])}",
         "contentUrl": CANONICA + JSON_ATUAL},
        {"@type": "DataDownload", "encodingFormat": "application/json",
         "name": "Dados consolidados, edição corrente",
         "contentUrl": CANONICA + "observatorio-drone-brasil.json"},
    ],
    # O Google valida o isBasedOn como um Dataset COMPLETO e independente, entao ele
    # precisa dos campos obrigatorios por conta propria. Sem "description" da erro
    # critico na inspecao de URL (flagado em 07/08/2026). O "creator" tambem precisa
    # ser Organization: GovernmentOrganization e subtipo valido em schema.org, mas o
    # validador do Google reclama do tipo. "license" fica de fora de proposito: e
    # campo opcional e eu nao tenho a licenca da ANAC confirmada na fonte.
    "isBasedOn": {"@type": "Dataset", "name": "SISANT - Sistema de Aeronaves Não Tripuladas",
                  "description": "Base pública de cadastro de aeronaves não tripuladas mantida "
                                 "pela ANAC e publicada em dados abertos, com atualização diária "
                                 "e histórico mensal. Traz código do cadastro, validade, operador, "
                                 "tipo de uso, fabricante, modelo, peso máximo de decolagem e ramo "
                                 "de atividade de cada drone registrado no Brasil.",
                  "creator": {"@type": "Organization",
                              "name": "Agência Nacional de Aviação Civil (ANAC)",
                              "url": "https://www.gov.br/anac/"},
                  "url": "https://sistemas.anac.gov.br/dadosabertos/"},
    "creator": {"@type": "Person", "name": "Irlen Menezes",
                "url": "https://irlenmenezes.com.br/",
                "jobTitle": "Cientista de dados",
                "alumniOf": {"@type": "CollegeOrUniversity", "name": "PUC Minas"},
                "knowsAbout": ["Legislação e regulação de drones no Brasil", "RBAC 100", "ICA 100-40", "SISANT"],
                "sameAs": ["https://www.linkedin.com/in/irlenmenezes", "https://x.com/vinnaum"]},
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "variableMeasured": [
        {"@type": "PropertyValue", "name": "Aeronaves cadastradas", "value": T},
        {"@type": "PropertyValue", "name": "Aeronaves em nome de pessoa física (CPF)", "value": RES["pf"]},
        {"@type": "PropertyValue", "name": "Empresas com drone cadastrado", "value": RES["cnpjs"]},
        {"@type": "PropertyValue", "name": "Participação da DJI na frota",
         "value": round(dji["qtd"] / T * 100, 1), "unitText": "%"},
    ],
}, ensure_ascii=False, indent=1)

titulo = f"Observatório do Drone no Brasil: {num(T)} aeronaves cadastradas"
descricao = (f"Os números do drone no Brasil apurados direto do arquivo da ANAC: {num(T)} "
             f"aeronaves cadastradas, {num(RES['cnpjs'])} empresas, crescimento mês a mês, onda de "
             f"vencimentos, sede das empresas por estado e modelos mais cadastrados. Metodologia "
             f"aberta e dados consolidados para baixar.")

# CSS fora da f-string: chave dupla em folha deste tamanho é fonte garantida de bug.
# Folha editorial (20/09/2026). A anterior (premium navy/amarelo) esta em obs_build.py.bak-20260920-premium.
CSS = """
/* Observatório do Drone: folha editorial (20/09/2026).
   Direção: jornalismo de dados impresso, não dashboard. Papel, serifa nos títulos,
   mono nos números e rótulos, uma tinta e um acento. Nada de gradiente, vidro,
   sombra colorida ou ornamento. Fontes locais (fonts/). */
@font-face{font-family:"Big Shoulders Display";src:url(fonts/big-shoulders-display-800.woff2) format("woff2");font-weight:700 900;font-display:swap}
@font-face{font-family:"IBM Plex Mono";src:url(fonts/ibm-plex-mono-400.woff2) format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"IBM Plex Mono";src:url(fonts/ibm-plex-mono-500.woff2) format("woff2");font-weight:500;font-display:swap}
@font-face{font-family:"Inter";src:url(fonts/inter-latin.woff2) format("woff2");font-weight:100 900;font-display:swap}
:root{
 --papel:#f2f4f2; --sup:#ffffff; --sup2:#e8ece9;
 --ink:#14181d; --ink2:#56606b; --mudo:#7a848e;
 --borda:#d7dde1; --fio:#c3cbd1; --grade:#dfe5e8; --eixo:#9aa5ad;
 --tinta:#1d5a8a; --acento:#c2410c; --verde:#15803d; --hi:#d9961a;
 --s1:#1d5a8a; --s2:#c2410c; --s3:#15803d;
 --o1:#cfe0ee; --o2:#8fb4d1; --o3:#4f86b0; --o4:#1d5a8a;
 --linkc:#1d5a8a;
 --r-n:#4d8c3e; --r-ne:#7f5500; --r-co:#a584dc; --r-se:#8e3a6e; --r-s:#008caa;
 --cond:"Big Shoulders Display","Barlow Condensed","Arial Narrow","Roboto Condensed",Impact,sans-serif;
 --serif:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;
 --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
 --sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;
 color-scheme:light;
}
@media (prefers-color-scheme:dark){ :root:where(:not([data-theme=light])){__ESCURO__} }
:root[data-theme=dark]{__ESCURO__}

*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:70px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--papel);color:var(--ink);
 font:400 17px/1.65 var(--sans);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.wrap{width:min(1080px,100% - 40px);margin-inline:auto}
a{color:var(--linkc);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--fio)}
a:hover{text-decoration-color:currentColor}
.k{font-family:var(--mono);font-size:12px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:var(--ink2)}

/* ---------------------------------------------------------------- hero */
.hero{padding:56px 0 0}
.hero-top{display:flex;justify-content:space-between;gap:24px;align-items:baseline;flex-wrap:wrap;
 padding-bottom:18px;border-bottom:1px solid var(--ink)}
.hero-top .marca{font-family:var(--serif);font-weight:800;font-size:19px;letter-spacing:-.02em}
.atualiza{margin:0;padding:9px 0;border-bottom:1px solid var(--grade);font-family:var(--mono);font-size:12px;color:var(--ink2)}
.atualiza b{color:var(--ink);font-weight:500}
.tema{margin-left:12px;border:1px solid var(--fio);background:transparent;color:var(--ink);border-radius:999px;padding:4px 12px;font:500 11.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;cursor:pointer}
.tema:hover{border-color:var(--ink)}
.hero-g{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr);gap:48px;align-items:end;
 padding:40px 0 34px;border-bottom:1px solid var(--fio)}
h1{font-family:var(--serif);font-weight:800;font-size:clamp(34px,4.6vw,56px);line-height:1.04;
 letter-spacing:-.03em;margin:18px 0 0;max-width:17ch}
.sub{margin:22px 0 0;font-size:clamp(16px,1.5vw,19px);line-height:1.55;color:var(--ink2);max-width:54ch;
 font-family:var(--serif);font-weight:400}
.fonte{margin:22px 0 0;font-size:13.5px;color:var(--ink2);line-height:1.6;max-width:60ch}
.fonte.autor{margin-top:8px}
.figura{border-left:1px solid var(--fio);padding-left:28px}
.figura .fl{display:block}
.figura .fv{display:block;font-family:var(--cond);font-weight:800;font-size:clamp(64px,8.4vw,112px);
 line-height:.9;letter-spacing:-.01em;margin:6px 0 10px;font-variant-numeric:tabular-nums}
.figura .fd{font-size:14.5px;color:var(--ink2);line-height:1.55;margin:0}
.fdelta{display:inline-block;margin-top:14px;font-family:var(--mono);font-size:12.5px;color:var(--acento);
 border-bottom:1px solid var(--acento);padding-bottom:2px}

/* --------------------------------------------------------------- figuras */
.tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin-top:0;
 border-bottom:1px solid var(--fio)}
.tile{padding:16px 22px 18px 0;border-top:2px solid var(--ink);border-right:0;margin-right:22px}
.tile:last-child{margin-right:0}
.tile .tl{display:block;font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink2)}
.tile .tv{display:block;font-family:var(--cond);font-size:64px;font-weight:800;letter-spacing:0;
 line-height:1;margin:6px 0 6px;color:var(--ink);font-variant-numeric:tabular-nums}
.tile .td{font-size:13px;color:var(--mudo)}

/* ----------------------------------------------------------- índice fixo */
.idx{position:sticky;top:0;z-index:30;background:var(--papel);border-bottom:1px solid var(--fio);padding:0}
.idx-in{display:flex;gap:26px;overflow-x:auto;scrollbar-width:none}
.idx-in::-webkit-scrollbar{display:none}
.idx{padding:10px 0}
.idx-in{gap:6px}
.idx a{white-space:nowrap;font:600 13px var(--serif);color:var(--ink2);text-decoration:none;padding:7px 14px;border-radius:999px;border:1px solid transparent}
.idx a:hover{color:var(--ink);border-color:var(--fio)}
.idx a.on{background:var(--ink);color:var(--papel)}

/* -------------------------------------------------------------- seções */
main{padding-top:8px}
.sec{padding:48px 0 38px;border-bottom:1px solid var(--fio)}
.sec-h{display:grid;grid-template-columns:64px 1fr;gap:20px;margin-bottom:28px}
.sec-n{font-family:var(--mono);font-size:13px;color:var(--acento);padding-top:14px;font-variant-numeric:tabular-nums}
h2{font-family:var(--serif);font-size:clamp(26px,3.2vw,38px);font-weight:800;letter-spacing:-.025em;line-height:1.1;margin:0}
.sec-tag{display:inline-block;margin-top:12px;font-family:var(--mono);font-size:11px;letter-spacing:.1em;
 text-transform:uppercase;color:var(--ink2)}
.chapeu{margin:16px 0 0;font-size:17.5px;line-height:1.6;color:var(--ink);max-width:62ch;font-family:var(--serif)}
.sec-c{padding-left:84px}

/* ------------------------------------------------------ nota de método */
.nota{margin:26px 0 0;padding:14px 0 0;border-top:1px solid var(--grade);max-width:72ch}
.nota-t{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink2);margin-bottom:8px}
.nota p{margin:0;font-size:14px;line-height:1.65;color:var(--ink2)}
.nota strong{color:var(--ink);font-weight:600}

/* ------------------------------------------------------ barras e gráficos */
.chw{overflow-x:auto;margin:0 -6px;padding:0 6px}
svg.ch{display:block;width:100%;min-width:640px;height:auto;overflow:visible;font-family:var(--mono)}
.grid{stroke:var(--grade);stroke-width:1;stroke-dasharray:2 4}
.eixo{stroke:var(--eixo);stroke-width:1}
.tick{fill:var(--mudo);font-size:11px;font-family:var(--mono);font-variant-numeric:tabular-nums}
.valor{fill:var(--ink);font-size:12.5px;font-weight:500;font-family:var(--mono)}
.bar{fill:var(--tinta);opacity:.9}
.bar.destaque{fill:var(--hi);opacity:1}
.bar.parcial{fill:none;stroke:var(--tinta);stroke-width:1.2;stroke-dasharray:3 3;opacity:.8}
.col:hover .bar{opacity:1}
.hit{fill:transparent}
.col:hover .hit{fill:var(--ink);opacity:.05}
.linha{fill:none;stroke:var(--tinta);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.area{fill:var(--tinta);opacity:.06}
.pt{fill:var(--papel);stroke:var(--tinta);stroke-width:2}
.bhs{display:flex;flex-direction:column;gap:9px}
.bh{display:grid;grid-template-columns:minmax(118px,200px) 1fr minmax(118px,auto);gap:16px;align-items:center}
.bh-l{display:flex;align-items:baseline;gap:9px;font-size:14.5px;color:var(--ink);overflow-wrap:anywhere}
.bh-r{font-family:var(--mono);font-size:11px;color:var(--mudo);font-variant-numeric:tabular-nums;flex:none}
.bh-t{background:transparent;border:0;border-left:1px solid var(--eixo);height:16px;overflow:hidden}
.bh-t i{display:block;height:100%;width:var(--w);min-width:2px}
.bh-v{display:flex;gap:8px;justify-content:flex-end;align-items:baseline;font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums}
.bh-v b{font-weight:500;color:var(--ink)}
.sh{color:var(--mudo);font-weight:400;font-size:12px}
i.s1{background:var(--s1)} i.s2{background:var(--s2)} i.s3{background:var(--s3)}
i.o1{background:var(--o1)} i.o2{background:var(--o2)} i.o3{background:var(--o3)} i.o4{background:var(--o4)}
.pilha{display:flex;height:34px;overflow:hidden;gap:2px;background:transparent}
.pilha i{display:block;height:100%}
.lgs{display:flex;flex-wrap:wrap;gap:8px 26px;margin-top:14px}
.lg{display:flex;align-items:center;gap:8px;font-size:13.5px;color:var(--ink2)}
.lg i{width:10px;height:10px;flex:none}
.lg b{color:var(--ink);font-family:var(--mono);font-variant-numeric:tabular-nums;font-weight:500}

/* -------------------------------------------------------------- tabelas */
details{margin:22px 0 0;border-top:1px solid var(--grade)}
summary{cursor:pointer;font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;
 color:var(--ink2);padding:13px 0;list-style:none;display:flex;align-items:center;gap:9px}
summary::-webkit-details-marker{display:none}
summary::before{content:"";width:6px;height:6px;flex:none;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;
 transform:rotate(-45deg);transition:transform .2s}
details[open] summary::before{transform:rotate(45deg)}
summary:hover{color:var(--ink)}
.tw{overflow-x:auto}
.tw+.tw{margin-top:18px}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:440px}
caption{caption-side:bottom;text-align:left;padding:10px 0;font-size:12.5px;color:var(--mudo);line-height:1.55}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--grade)}
th{font-family:var(--mono);font-weight:500;color:var(--ink2);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
 border-bottom:1px solid var(--ink);background:transparent}
td.n,th.n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:var(--sup2)}

/* --------------------------------------------------------- metodologia */
#metodologia ol{margin:0;padding-left:22px}
#metodologia li{margin-bottom:13px;color:var(--ink2);line-height:1.66}
#metodologia li::marker{color:var(--acento);font-family:var(--mono)}
#metodologia strong{color:var(--ink);font-weight:600}
/* ------------------------------------------------ dados, versoes, citacao */
.dados-g{display:grid;grid-template-columns:1.2fr 1fr;gap:34px 48px}
.dados-g h3{font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink2);font-weight:500;margin:0 0 10px}
.dados-g h3+ul+h3{margin-top:22px}
.ficha{display:grid;grid-template-columns:max-content 1fr;gap:8px 18px;margin:0;font-size:14.5px;line-height:1.55}
.ficha dt{font-family:var(--mono);font-size:12px;color:var(--mudo);padding-top:2px}
.ficha dd{margin:0;color:var(--ink)}
.ficha a,.edicoes a,.citar a{color:var(--linkc);text-decoration:underline;text-decoration-color:var(--fio);text-underline-offset:3px}
.edicoes{list-style:none;margin:0;padding:0;font-size:14.5px;line-height:1.6}
.edicoes li{padding:5px 0;border-top:1px solid var(--grade)}
.edicoes li:first-child{border-top:0;padding-top:0}
.edicoes .k{font-family:var(--mono);font-size:12px;color:var(--acento);margin-right:8px}
@media(max-width:760px){.dados-g{grid-template-columns:1fr}}
.citar{margin-top:26px;padding:20px 0 0;border-top:1px solid var(--ink);font-size:14px;line-height:1.65;color:var(--ink2);max-width:72ch}
.citar b{color:var(--ink)}
.citar code{display:block;margin-top:10px;padding:12px 14px;border-left:2px solid var(--acento);background:var(--sup2);color:var(--ink);
 font-family:var(--mono);font-size:12.5px;line-height:1.65;overflow-wrap:anywhere}
footer{margin-top:0;padding:34px 0 60px;font-size:13.5px;color:var(--ink2)}
footer p{margin:0 0 6px}

/* ------------------------------------------------------------- mapa em grade */
.mapa{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:36px;align-items:start;margin:4px 0 30px}
.mapa svg{width:100%;height:auto;display:block}
.mapa .ut text{font-family:var(--mono);pointer-events:none}
.mapa .ut rect{stroke:var(--papel);stroke-width:2}
.reg{margin:0;padding:0;list-style:none}
.reg li{display:grid;grid-template-columns:minmax(96px,max-content) 1fr;gap:6px 18px;align-items:center;padding:12px 0;border-top:1px solid var(--grade)}
.reg li:first-child{border-top:2px solid var(--ink)}
.reg .rn{font-family:var(--cond);font-weight:800;font-size:44px;line-height:1;color:var(--c);white-space:nowrap}
.reg li>div{min-width:0}
.reg b{display:block;font-size:15px}
.reg span{font-family:var(--mono);font-size:11px;color:var(--ink2);letter-spacing:.04em}
.mapa-nota{font-family:var(--mono);font-size:11.5px;color:var(--mudo);margin:10px 0 0}
@media(max-width:760px){.mapa{grid-template-columns:1fr}.reg li{grid-template-columns:1fr;gap:2px}.reg .rn{font-size:40px}.ficha{grid-template-columns:1fr;gap:2px}.ficha dd{overflow-wrap:anywhere;margin-bottom:10px}}
/* ---------------------------------------------------------------- movimento */
@keyframes preenche{from{width:0}to{width:var(--w)}}
@media (prefers-reduced-motion:no-preference){
 .bh-t i{animation:preenche .7s cubic-bezier(.22,.7,.25,1) both;animation-delay:calc(var(--i,0)*40ms)}
}
@media (prefers-reduced-motion:reduce){
 *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}
}

/* ---------------------------------------------------------------- mobile */
@media(max-width:900px){ .hero-g{grid-template-columns:1fr;gap:26px} .figura{border-left:0;padding-left:0;border-top:1px solid var(--fio);padding-top:22px} .tiles{grid-template-columns:repeat(2,minmax(0,1fr))} .tile:nth-child(2){border-right:0} .tile:nth-child(3){padding-left:0;border-top:1px solid var(--grade)} .tile:nth-child(4){border-top:1px solid var(--grade)} }
@media(max-width:700px){
 .wrap{width:min(1080px,100% - 32px)}
 .hero{padding:34px 0 0}
 .sec{padding:38px 0 30px}
 .sec-h{grid-template-columns:1fr;gap:6px;margin-bottom:20px}
 .sec-n{padding-top:0}
 .sec-c{padding-left:0}
 .bh{grid-template-columns:1fr;gap:5px}
 .bh-v{justify-content:flex-start}
 .chapeu{font-size:17px}
 .tile .tv{font-size:32px}
}
@media print{.idx,details,footer{display:none}}
"""

ESCURO = ("--papel:#0f1317;--sup:#161b20;--sup2:#1d242b;"
          "--ink:#eef1f3;--ink2:#a9b3bc;--mudo:#7d8791;"
          "--borda:#2a323a;--fio:#37414a;--grade:#222a31;--eixo:#56626c;"
          "--tinta:#7fb3dc;--acento:#f08a52;--verde:#5fc27f;--hi:#e8ae3c;"
          "--s1:#7fb3dc;--s2:#f08a52;--s3:#5fc27f;"
          "--o1:#27394a;--o2:#3f6788;--o3:#6aa0cc;--o4:#b5d4ec;"
          "--linkc:#9ccbf0;color-scheme:dark;")
CSS = CSS.replace("__ESCURO__", ESCURO)

JS = """<script>
(function(){var r=document.documentElement,b=document.getElementById("tema");
try{var t=localStorage.getItem("obs-tema");if(t)r.setAttribute("data-theme",t)}catch(e){}
if(b)b.addEventListener("click",function(){var dk=r.getAttribute("data-theme")==="dark"||(!r.getAttribute("data-theme")&&matchMedia("(prefers-color-scheme:dark)").matches);var n=dk?"light":"dark";r.setAttribute("data-theme",n);try{localStorage.setItem("obs-tema",n)}catch(e){}});
var links=[].slice.call(document.querySelectorAll(".idx a")),secs=links.map(function(a){return document.querySelector(a.getAttribute("href"))});
if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){links.forEach(function(a){a.classList.toggle("on",a.getAttribute("href")==="#"+e.target.id)})}})},{rootMargin:"-30% 0px -60% 0px"});secs.forEach(function(s){s&&io.observe(s)})}
})();
</script>"""

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{esc(descricao)}">
<link rel="canonical" href="{CANONICA}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descricao)}">
<meta property="og:url" content="{CANONICA}">
<meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#f2f4f2">
<script type="application/ld+json">{jsonld}</script>
<style>{CSS}</style>
</head>
<body>

<header class="hero">
 <div class="wrap">
  <div class="hero-top">
   <span class="marca">Observatório do Drone no Brasil</span>
   <span><span class="k">Dados abertos</span><button class="tema" id="tema" type="button" aria-label="Alternar tema claro e escuro">Tema</button></span>
  </div>
  <p class="atualiza">Dados oficiais da ANAC, base de <b>{data_br(META['data_base'])}</b> · apurado em <b>{data_br(META['processado_em'][:10])}</b> · <a href="#metodologia">como apuramos</a></p>
  <div class="hero-g">
   <div>
    <span class="k">Relatório de cadastro · SISANT</span>
    <h1>Quantos drones existem no Brasil, contados um a um</h1>
    <p class="sub">O retrato do cadastro nacional apurado linha a linha sobre o arquivo
     público da ANAC. {POR_EXTENSO.get(N_RECORTES, N_RECORTES)} recortes, cada um com o método
     declarado embaixo do gráfico, e os dados consolidados para baixar e conferir.</p>
    <p class="fonte">Fonte primária:
     <a href="https://www.gov.br/anac/pt-br/assuntos/regulados/aeronaves/drones" rel="noopener">SISANT / ANAC</a>,
     {num(META['registros'])} registros. Localização por estado cruzada com a Receita Federal.</p>
    <p class="fonte autor">Apuração de <a href="https://irlenmenezes.com.br/sobre/" rel="author">Irlen Menezes</a>,
     cientista de dados formado pela PUC Minas, com experiência em legislação e regulação de drones no Brasil.</p>
   </div>
   <div class="figura">
    <span class="fl k">Aeronaves cadastradas</span>
    <strong class="fv">{num(T)}</strong>
    <p class="fd">{num(RES['pf'])} em nome de pessoa física e {num(RES['pj'])} em CNPJ,
     distribuídas entre {num(RES['cnpjs'])} empresas.</p>
    <span class="fdelta">Pico: {num(pico['novos'])} emissões em {rotulo_mes(pico['mes'])}</span>
   </div>
  </div>
 </div>
</header>

<div class="wrap"><div class="tiles">{tiles_html}</div></div>

<nav class="idx" aria-label="Seções do relatório">
 <div class="wrap idx-in">{indice}</div>
</nav>

<main class="wrap">
 {"".join(secoes)}

 <section id="metodologia" class="sec">
  <div class="sec-h"><span class="sec-n">{N_RECORTES + 1:02d}</span><div class="sec-t">
   <h2>Como estes números foram apurados</h2>
   <span class="sec-tag">Transparência</span>
   <p class="chapeu">Nada aqui vem de estimativa de mercado ou de release. Tudo sai do arquivo
    público da ANAC, processado por script. O que é medido e o que é derivado está separado.</p>
  </div></div>
  <div class="sec-c">
  <ol>
   <li><strong>Fonte.</strong> Arquivo SISANT da ANAC, base de {data_br(META['data_base'])},
    com {num(META['registros'])} registros. O arquivo traz código da aeronave, validade,
    operador, CPF ou CNPJ, tipo de uso, fabricante, modelo, número de série, peso máximo de
    decolagem e ramo de atividade. É um cadastro de <strong>aeronaves</strong>: cada linha é um
    drone registrado, não uma pessoa, uma venda nem um voo.</li>
   <li><strong>O que cadastro permite e não permite concluir.</strong> Permite: quantas aeronaves
    estão registradas, de que modelo, faixa de peso, tipo de uso e ramo declarado, e em nome de
    CPF ou de CNPJ. Não permite: quantas pessoas têm drone (o CPF vem mascarado e uma pessoa pode
    ter vários), quanto cada marca vendeu no mês, quantas horas cada modelo voa, nem onde o drone
    opera. Quando um recorte aqui diz "mais cadastrado", é isso que ele mede.</li>
   <li><strong>O que o arquivo não traz.</strong> Não existe data de cadastro, nem estado, nem
    município. A data de emissão é derivada da validade menos 24 meses, premissa conferida pelo
    script antes de qualquer cálculo. O estado vem do CNPJ consultado na Receita e por isso só
    cobre a parcela empresarial: {pct(RES['pj'] / T)} dos registros.</li>
   <li><strong>Emissão, primeiro cadastro e renovação.</strong> A série mensal conta
    <em>emissões</em>: primeiro cadastro e renovação entram juntos, porque uma base sozinha não
    os separa. A separação só é possível comparando dois arquivos guardados, código a código, e é
    o que a seção de entradas e saídas faz. Um arquivo novo também muda o passado: cadastros
    cancelados somem da série, por isso cada base fica guardada como snapshot.</li>
   <li><strong>Campos livres são limpos antes de contar.</strong> Fabricante, modelo e ramo de
    atividade são digitados à mão e o arquivo tem mais de 2 mil rótulos diferentes de ramo e
    mais de 3 mil de fabricante. Grafias do mesmo item são unificadas, senão qualquer ranking
    sai errado.</li>
   <li><strong>Frota não é mercado.</strong> Shows de drone de luz registram mais de mil
    aeronaves em um único CNPJ. Onde isso distorce a leitura, a métrica principal é o número de
    empresas e a frota aparece à parte, também sem os ramos de espetáculo.</li>
   <li><strong>Recorte da série.</strong> O arquivo lista apenas cadastro vigente. Como a
    validade é de 24 meses, qualquer mês anterior a {rotulo_mes(serie[0]['mes'])} contém só os
    {num(RES['vencidos'])} vencidos que ainda não saíram do arquivo. Publicar esse trecho
    sugeriria que o mercado nasceu em 2024, então a série começa onde a janela é completa.</li>
   <li><strong>Atualização e checagem.</strong> A apuração é um script que roda de novo a cada base
    nova publicada pela ANAC, todo mês. Antes de publicar, ele confere {len(META.get('checagens', []))}
    consistências: cada recorte tem de somar o total do arquivo (diferença só por filtro documentado,
    como a janela da série), a premissa dos 24 meses tem de valer e o total não pode variar mais de
    15% contra a edição anterior. Se uma falha, nada sobe. Os números desta página valem para
    {data_br(META['data_base'])}.</li>
   <li><strong>Quem apura.</strong> Irlen Menezes, cientista de dados formado pela PUC Minas, com
    experiência em legislação e regulação de drones no Brasil. Autor do blog de drones de
    <a href="https://irlenmenezes.com.br/">irlenmenezes.com.br</a> e das ferramentas gratuitas para pilotos.</li>
  </ol>
  </div>
 </section>

 <section id="dados" class="sec">
  <div class="sec-h"><span class="sec-n">{N_RECORTES + 2:02d}</span><div class="sec-t">
   <h2>Dados, versões e citação</h2>
   <span class="sec-tag">Imprensa e pesquisa</span>
   <p class="chapeu">Os dados consolidados ficam públicos, sem cadastro, e cada edição fica
    guardada. Um número citado hoje continua conferível quando a base seguinte sair.</p>
  </div></div>
  <div class="sec-c">
   <div class="dados-g">
    <div>
     <h3>Esta edição</h3>
     <dl class="ficha">
      <dt>Base ANAC</dt><dd>{data_br(META['data_base'])} · {num(META['registros'])} registros</dd>
      <dt>Processada em</dt><dd>{data_br(META['processado_em'][:10])}</dd>
      <dt>Método</dt><dd>versão {META.get('versao_metodo', '—')}</dd>
      <dt>Código</dt><dd><a href="{REPO}" rel="noopener">github.com/irlenmenezes/observatorio-drone-brasil</a>: scripts, edições e checksum dos arquivos da ANAC, para reproduzir a apuração</dd>
      <dt>Licença</dt><dd><a href="https://creativecommons.org/licenses/by/4.0/deed.pt-br" rel="license noopener">CC BY 4.0</a>: use, cite e linke</dd>
      <dt>Baixar</dt><dd><a href="{JSON_ATUAL}">dados consolidados desta edição (JSON)</a> ·
       <a href="observatorio-drone-brasil.json">edição corrente</a> ·
       <a href="{META.get('fonte_url', 'https://sistemas.anac.gov.br/dadosabertos/')}" rel="noopener">arquivo bruto na ANAC (CSV)</a></dd>
     </dl>
    </div>
    <div>
     <h3>Edições anteriores</h3>
     <ul class="edicoes">{"".join(f'<li><a href="dados/observatorio-drone-brasil-{e}.json">base de {data_br(e)}</a></li>' for e in reversed(EDICOES)) or "<li>Esta é a primeira edição guardada.</li>"}</ul>
     <h3>Mudanças de método</h3>
     <ul class="edicoes">{"".join(f'<li><span class="k">{h["versao"]}</span> {esc(h["mudanca"])}</li>' for h in reversed(META.get("historico_metodo", [])))}</ul>
    </div>
   </div>
   <div class="citar"><b>Pode usar estes dados</b> em reportagem, trabalho acadêmico ou conteúdo,
    com crédito e link. O JSON traz resultados consolidados e agregados; os registros individuais
    estão no arquivo da ANAC. Sugestão de citação:
    <code>MENEZES, Irlen. Observatório do Drone no Brasil, base ANAC de {data_br(META['data_base'])}.
Apuração sobre o SISANT. Disponível em: {CANONICA}</code>
    Para entrevista, pauta ou pedido de recorte que não está aqui:
    <a href="https://irlenmenezes.com.br/contato/">fale comigo</a>.</div>
  </div>
 </section>
</main>

<footer>
 <div class="wrap">
  <p>Apuração independente sobre dados abertos da ANAC ·
   <a href="https://irlenmenezes.com.br/">irlenmenezes.com.br</a></p>
  <p style="margin:8px 0 0;opacity:.72">Base de {data_br(META['data_base'])} ·
   {num(META['registros'])} registros · método {META.get('versao_metodo', '')} · dados consolidados em
   <a href="observatorio-drone-brasil.json">JSON</a></p>
 </div>
</footer>
{JS}
</body>
</html>
"""

# embrulha os SVG num container que rola no celular, sem a pagina rolar junto
html = html.replace('<svg viewBox', '<div class="chw"><svg viewBox').replace('</svg>', '</svg></div>')

DESTINO.mkdir(parents=True, exist_ok=True)
(DESTINO / "index.html").write_text(html, encoding="utf-8")
shutil.copy(DADOS, DESTINO / "observatorio-drone-brasil.json")

# arquivo de edicoes: uma copia datada por base, mais o diff entre bases, em dados/.
# A edicao corrente tambem fica guardada localmente como obs-drone-<data>.json.
(DESTINO / "dados").mkdir(exist_ok=True)
shutil.copy(DADOS, BASE / f"obs-drone-{META['data_base']}.json")
for e in sorted(set(EDICOES) | {META["data_base"]}):
    shutil.copy(BASE / f"obs-drone-{e}.json", DESTINO / "dados" / f"observatorio-drone-brasil-{e}.json")
if DIFF:
    shutil.copy(DIFF_ARQ, DESTINO / "dados" / f"movimento-{DIFF['base_anterior']}-a-{DIFF['base_atual']}.json")

# fontes locais (20/09/2026)
(DESTINO / "fonts").mkdir(exist_ok=True)
for f in (BASE / "obs-fonts").glob("*.woff2"):
    shutil.copy(f, DESTINO / "fonts" / f.name)

# vídeo de fundo do hero: arquivos continuam publicados, mas a página não os carrega mais
for v in ("hero-airspace.webm", "hero-airspace.mp4"):
    origem = BASE / "hero-video" / v
    if origem.exists():
        shutil.copy(origem, DESTINO / v)

# O servidor não conhece .webm e entregava como text/plain; com o type declarado
# no <source>, o Chrome descarta a fonte e cai sempre no MP4, que é 47% maior.
# .htaccess local: só vale nesta pasta, não encosta no da raiz (que tem o bloco
# NEXTJS_TO_SUBDOMAIN_REDIRECTS e é sensível).
# ⚠️ AddType sozinho NÃO funciona neste servidor (testado 05/08: continuou
# text/plain). Só o ForceType do FilesMatch pegou.
(DESTINO / ".htaccess").write_text(
    "# MIME que faltava no servidor: sem isto o WebM/AV1 sai como text/plain e o\n"
    "# navegador descarta a fonte, caindo sempre no MP4 (47% maior).\n"
    "<IfModule mod_mime.c>\n"
    "AddType video/webm .webm\n"
    "AddType video/mp4 .mp4\n"
    "</IfModule>\n"
    '<FilesMatch "\\.webm$">\n'
    "ForceType video/webm\n"
    "</FilesMatch>\n", encoding="utf-8", newline="\n")  # LF: no Windows o padrão vira CRLF

kb = len(html.encode("utf-8")) / 1024
print(f"gerado: {DESTINO / 'index.html'}  ({kb:.1f} KB)")
print(f"secoes: {len(secoes) + 1}   tabelas: {html.count('<table>')}   graficos: {html.count('<svg')}")
print(f"json publicado junto: observatorio-drone-brasil.json")
