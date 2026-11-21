# -*- coding: utf-8 -*-
"""Seção Agro do Observatório (14/11/2026): monta o HTML a partir de obs-agro.json.

Chamado pelo obs_build.py só quando existe obs-agro.json da mesma base ANAC da página.
Segue o design da página (seções numeradas, barras em HTML, tabela real em <details>,
nota de método embaixo) e não usa JavaScript.
Tudo o que entra aqui já é agregado: obs_agro.py varre o JSON atrás de dado pessoal antes
de gravar, e contagem por município entre 1 e 2 já chega como faixa ("1 a 2").
"""

UF_NOME = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
           "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
           "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
           "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
           "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
           "SE": "Sergipe", "TO": "Tocantins"}
POR_EXT = {2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez"}

INDICE = [("agro", "Agro"), ("agro-operadores", "Agro: operadores"),
          ("agro-estados", "Agro por estado"), ("agro-municipios", "Agro por município")]

CSS = """
/* ---------------------------------------------------- seção agro (14/11/2026) */
.sec .tiles.ag-t{margin:0 0 30px;border-bottom:0}
.sec .ag-t .tile .tv{font-size:46px}
.bh-t.duo{display:flex}
.bh-t.duo i{flex:none}
i.g1{background:var(--eixo)} i.hi{background:var(--hi)}
.tw.fixa1 th:first-child,.tw.fixa1 td:first-child{position:sticky;left:0;z-index:1;background:var(--papel)}
.tw.fixa1 tbody tr:hover td:first-child{background:var(--sup2)}
.tw-cap{margin:8px 0 0;font-size:12.5px;color:var(--mudo);line-height:1.55;max-width:72ch}
caption.vh{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.tw-cap+.tw{margin-top:20px}
.agro-lim ol{margin:0;padding-left:20px}
.agro-lim li{margin:0 0 9px;font-size:14px;line-height:1.65;color:var(--ink2)}
.agro-lim li::marker{color:var(--acento);font-family:var(--mono);font-size:12px}
.agro-lim li strong{color:var(--ink);font-weight:600}
@media(max-width:700px){
 .sec .ag-t .tile .tv{font-size:30px}
 .tw table{font-size:12.5px}
 .tw th,.tw td{padding:8px 9px}
}
"""


def monta(AG, h):
    """AG = conteúdo de obs-agro.json; h = funções do obs_build (num, pct, esc, data_br, bloco, barras_h).
    Devolve um dict com as seções e os pedaços que entram em outras partes da página."""
    num, pct, esc, data_br, bloco, barras_h = (h[k] for k in ("num", "pct", "esc", "data_br", "bloco", "barras_h"))
    M, F, X, MAPA, MUN = AG["meta"], AG["frota_anac"], AG["cruzamento"], AG["mapa"], AG["municipios"]

    def p1(v):  # percentual que já vem em 0-100
        return f"{v:.1f}".replace(".", ",") + "%"

    def mi(v):  # milhões com uma casa
        return f"{v / 1e6:.1f}".replace(".", ",")

    def milhar(v):  # milhares com uma casa
        return f"{v / 1e3:.1f}".replace(".", ",")

    def cel(v):  # célula de tabela: número, faixa de privacidade ou ausência
        if v is None:
            return "n/d"
        return num(v) if isinstance(v, int) else esc(str(v))

    _ntab = [0]

    def tab(cab, linhas, resumo, fixa=True):
        # a legenda fica FORA da caixa que rola: no celular a tabela larga rola de lado e a
        # <caption> rolaria junto, cortada. aria-describedby mantém o vínculo com a tabela.
        _ntab[0] += 1
        cid = f"ag-cap-{_ntab[0]}"
        ths = "".join(f"<th{' class=n' if i else ''}>{esc(c)}</th>" for i, c in enumerate(cab))
        trs = "".join("<tr>" + "".join(f"<td{' class=n' if i else ''}>{c}</td>" for i, c in enumerate(ln)) + "</tr>"
                      for ln in linhas)
        # 20/11/2026: <caption> invisível dá o título "oficial" da tabela (leitor de tela e robô de IA
        # leem como título); a legenda visível continua fora da rolagem, escondida do leitor de tela
        # para não ler o mesmo texto duas vezes.
        return (f'<div class="tw{" fixa1" if fixa else ""}"><table>'
                f'<caption class="vh">{esc(resumo)}</caption>'
                f'<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>'
                f'<p class="tw-cap" id="{cid}" aria-hidden="true">{esc(resumo)}</p>')

    db = data_br(M["base_anac"])
    dm = data_br(M["mapa_arquivo_de"]) if M.get("mapa_arquivo_de") else "data não informada"
    dbx = data_br(M["mapa_baixado_em"]) if M.get("mapa_baixado_em") else ""
    T, pf, pj = F["drones_agricolas"], F["em_cpf"], F["em_cnpj"]
    no, no_pj, no_pf = X["drones_agricolas_com_numero_no_mapa"], X["em_cnpj_com_numero_no_mapa"], X["em_cpf_com_numero_no_mapa"]
    op, op_pj, op_pf = MAPA["operadores_drone"], MAPA["operadores_pj"], MAPA["operadores_pf"]
    listados = MAPA["drones_listados"]
    fonte_cap = (f"Fontes: ANAC/SISANT, base de {db}; MAPA/SIPEAGRO, registro de aviação agrícola, arquivo de {dm}. "
                 f"Apuração: Irlen Menezes.")
    secoes = []

    # --------------------------------------------------------- 1. frota x registro
    tiles = [("Drones agrícolas na ANAC", num(T), f"cadastro vigente em {db}"),
             ("Com número no MAPA", pct(no / T), f"{num(no)} drones"),
             ("Operadores no MAPA", num(op), f"{num(op_pj)} empresas e {num(op_pf)} pessoas físicas"),
             ("Drones listados no MAPA", num(listados), f"em registros ativos, arquivo de {dm}")]
    tiles_html = '<div class="tiles ag-t">' + "".join(
        f'<div class="tile" style="--i:{i}"><span class="tl">{l}</span><strong class="tv">{v}</strong>'
        f'<span class="td">{s}</span></div>' for i, (l, v, s) in enumerate(tiles)) + "</div>"
    linhas_duo = [("Em nome de empresa (CNPJ)", no_pj, pj), ("Em nome de pessoa física (CPF)", no_pf, pf),
                  ("Toda a frota agrícola", no, T)]
    duo = '<div class="bhs">' + "".join(
        f'<div class="bh" style="--i:{i}"><div class="bh-l"><span>{esc(r)}</span></div>'
        f'<div class="bh-t duo"><i class="s1" style="--w:{a / b * 100:.2f}%"></i>'
        f'<i class="o2" style="--w:{(b - a) / b * 100:.2f}%"></i></div>'
        f'<div class="bh-v"><b>{pct(a / b)}</b><span class="sh">{num(a)} de {num(b)}</span></div></div>'
        for i, (r, a, b) in enumerate(linhas_duo)) + "</div>"
    legenda = ('<div class="lgs"><span class="lg"><i class="s1"></i>Com número num registro ativo do MAPA</span>'
               '<span class="lg"><i class="o2"></i>Sem número no MAPA</span></div>')
    mesmo, outro = X["dono_mesma_raiz_cnpj"], X["dono_outro_cnpj"]
    titulo1 = f"{'Só ' if no / T < 0.5 else ''}{pct(no / T)} dos drones agrícolas da ANAC aparecem no registro do MAPA"
    serie = AG["series"]["anac"]
    t_serie = tab(["Base da ANAC", "Drones agrícolas", "Em CPF", "% em CPF"],
                  [[data_br(s["base"]), num(s["drones_agricolas"]), num(s["em_cpf"]), pct(s["em_cpf"] / s["drones_agricolas"])]
                   for s in serie],
                  "Frota agrícola com cadastro vigente em cada base da ANAC guardada pelo Observatório, mesma regra. "
                  "Diferença entre duas bases é saldo (entradas menos saídas), não quantidade de drones novos.")
    sm = AG["series"]["mapa"]
    t_mapa = tab(["Baixado em", "Arquivo do MAPA de", "Operadores", "Drones listados"],
                 [[data_br(s["baixado_em"]), data_br(s["arquivo_mapa_de"]) if s.get("arquivo_mapa_de") else "sem data",
                   num(s["operadores"]), num(s["drones_listados"])] for s in sm],
                 "Registro de aviação agrícola do MAPA em cada cópia guardada. O arquivo não tem data por linha, "
                 "então a série do lado do MAPA começou a ser montada em 14/11/2026.") if len(sm) >= 2 else ""
    secoes.append(bloco(
        "agro", titulo1,
        f"A ANAC tem {num(T)} drones agrícolas com cadastro vigente. Pelo número da aeronave, {num(no)} aparecem em "
        f"algum registro ativo de aviação agrícola do MAPA, que a Portaria 298/2021 exige de quem faz aplicação com "
        f"drone. Em nome de empresa a fatia é de {pct(no_pj / pj)}. Em nome de pessoa física, cai para {pct(no_pf / pf)}. "
        f'A conta completa, drone a drone e estado por estado, está <a href="https://irlenmenezes.com.br/drones-agricolas-anac-registro-mapa-sipeagro-cruzamento-2026/">no post sobre o cruzamento ANAC x MAPA</a>.',
        tiles_html + duo + legenda,
        nota=f"Drone agrícola aqui é quem declarou o ramo de pulverização no SISANT ({num(F['pelo_ramo'])}) mais quem "
             f"cadastrou modelo de pulverizador (Agras, XAG, EAVision e parecidos) em outro ramo, com 2 kg ou mais "
             f"({num(F['pelo_modelo'])}). Só entra cadastro vigente na base de {db}. O MAPA grava o drone como PS "
             f"seguido de 9 dígitos e a ANAC lista o mesmo número com PP, então o cruzamento é pelo número: pelo "
             f"código idêntico só {num(X['numeros_mapa_achados_codigo_identico'])} batem, pelos 9 dígitos são "
             f"{num(X['numeros_mapa_achados_pelos_9_digitos'])}. Esses dígitos não se repetem no SISANT e, quando os "
             f"dois lados são empresa, a raiz do CNPJ do dono confere em {pct(mesmo / (mesmo + outro), 0)} dos casos "
             f"(o resto parece drone arrendado ou de terceiro, que a Portaria permite). <strong>Estar fora do MAPA não "
             f"quer dizer estar irregular</strong>: na frota da ANAC também há fabricante, revenda, estoque e drone de "
             f"pesquisa, que a Portaria dispensa do registro (art. 27). Os limites completos estão no "
             f'<a href="#agro-metodo">fim da seção agro</a>.',
        tabela_html=tab(["Recorte", "Drones agrícolas na ANAC", "Com número no MAPA", "% no MAPA"],
                        [["Toda a frota agrícola", num(T), num(no), pct(no / T)],
                         ["Em nome de empresa (CNPJ)", num(pj), num(no_pj), pct(no_pj / pj)],
                         ["Em nome de pessoa física (CPF)", num(pf), num(no_pf), pct(no_pf / pf)],
                         ["Pelo ramo declarado", num(F["pelo_ramo"]), num(X["pelo_ramo_no_mapa"]), pct(X["pelo_ramo_no_mapa"] / F["pelo_ramo"])],
                         ["Por modelo de pulverizador", num(F["pelo_modelo"]), num(X["pelo_modelo_no_mapa"]),
                          pct(X["pelo_modelo_no_mapa"] / F["pelo_modelo"]) if F["pelo_modelo"] else "n/d"]],
                        f"Drones agrícolas com cadastro vigente na ANAC cujo número aparece num registro ativo do MAPA. "
                        f"{fonte_cap}") + t_serie + t_mapa,
        rotulo_tab="Ver a tabela e a frota em cada base",
        etiqueta="Agro · ANAC x MAPA"))

    # --------------------------------------------------------- 2. operadores do MAPA
    sit = MAPA["operadores_por_situacao_na_anac"]
    ok, nv, inv = sit.get("com_drone_vigente_na_anac", 0), sit.get("so_numeros_nao_vigentes", 0), sit.get("so_codigo_sem_formato", 0)
    share = (nv + inv) / op
    k = round(1 / share) if share else 0
    if k in POR_EXT and abs(1 / share - k) / k <= 0.12:
        titulo2 = f"Um em cada {POR_EXT[k]} operadores do MAPA não tem drone que dê para achar vigente na ANAC"
    else:
        titulo2 = f"{pct(share)} dos operadores do MAPA não têm drone que dê para achar vigente na ANAC"
    itens = [("Ao menos um drone vigente na ANAC", ok), ("Só números que não estão vigentes na ANAC", nv),
             ("Só código fora do formato, sem como conferir", inv)]
    dist = MAPA["drones_por_operador"]
    secoes.append(bloco(
        "agro-operadores", titulo2,
        f"O MAPA tem {num(op)} operadores de drone com registro ativo, que listam {num(listados)} drones. "
        f"{num(ok)} deles têm ao menos um drone com cadastro vigente na ANAC. Outros {num(nv)} só listam números que "
        f"não estão vigentes no SISANT, e {num(inv)} só têm código digitado fora do formato, que não dá para conferir.",
        barras_h(itens, total_ref=op, ranking=False, cores=["s1", "s2", "g1"]),
        nota=f"A Portaria 298 pede que o drone esteja regular na ANAC para entrar no registro do MAPA (art. 4º, III). "
             f"Só que o registro é do estabelecimento, e a lista de aeronaves dentro dele é digitada: "
             f"{num(MAPA['drones_codigo_sem_formato'])} códigos não seguem o formato do SISANT (nome do modelo ou zeros "
             f"no lugar do número) e {num(MAPA['drones_em_mais_de_um_registro'])} drones aparecem em mais de um "
             f"registro, o que a Portaria permite (art. 21, § 2º). Dos números no formato certo, "
             f"{num(MAPA['numeros_fora_do_sisant_atual'])} não estão no arquivo atual da ANAC: venceram, foram "
             f"cancelados ou foram digitados errado. Os {num(MAPA['escolas_so_ensino'])} estabelecimentos que só dão "
             f"curso ficaram fora da conta de operadores; os drones deles entram no total listado. A maioria dos "
             f"operadores tem um drone só ({num(dist.get('1', 0))}) e {num(dist.get('10 ou mais', 0))} têm 10 ou mais.",
        tabela_html=tab(["Situação na ANAC", "Operadores do MAPA", "% dos operadores"],
                        [[esc(r), num(v), pct(v / op)] for r, v in itens] + [["Total", num(op), "100,0%"]],
                        f"Operadores de drone com registro ativo no MAPA, pela situação dos drones que eles listam no "
                        f"cadastro da ANAC. {fonte_cap}")
        + tab(["O registro do MAPA em números", "Quantidade"],
              [["Estabelecimentos no arquivo", num(MAPA["estabelecimentos"])],
               ["… com registro ativo", num(MAPA["ativos"])],
               ["… cancelados", num(MAPA["cancelados"])],
               ["Ativos que só têm avião", num(MAPA["ativos_so_aviao"])],
               ["Operadores de drone (sem escolas)", num(op)],
               ["… empresas", num(op_pj)],
               ["… pessoas físicas", num(op_pf)],
               ["… com drone e avião", num(MAPA["operadores_drone_e_aviao"])],
               ["Escolas que só dão curso", num(MAPA["escolas_so_ensino"])],
               ["Drones listados em registro ativo (com escolas)", num(listados)],
               ["… com número no formato do SISANT", num(MAPA["drones_codigo_formato_sisant"])],
               ["… com código fora do formato", num(MAPA["drones_codigo_sem_formato"])],
               ["Drone presente em mais de um registro", num(MAPA["drones_em_mais_de_um_registro"])],
               ["Mediana de drones por operador", num(MAPA["drones_por_operador_mediana"])],
               ["Operadores com 1 drone", num(dist.get("1", 0))],
               ["… com 2 a 3", num(dist.get("2 a 3", 0))],
               ["… com 4 a 9", num(dist.get("4 a 9", 0))],
               ["… com 10 ou mais", num(dist.get("10 ou mais", 0))]],
              f"Registro de aviação agrícola do MAPA (SIPEAGRO), arquivo de {dm}, baixado em {dbx}. "
              f"Só contagens; o arquivo traz dados de contato que não são publicados aqui."),
        rotulo_tab="Ver as tabelas do registro do MAPA",
        etiqueta="Agro · o caminho inverso"))

    # --------------------------------------------------------- 3. por estado
    U = AG["uf"]
    top12 = sorted(U, key=lambda r: -r["drones_agricolas_anac_cnpj"])[:12]
    top12 = sorted([r for r in top12 if r["pct_cnpj_com_numero_no_mapa"] is not None],
                   key=lambda r: -r["pct_cnpj_com_numero_no_mapa"])
    mx, mn = top12[0], top12[-1]
    barras_uf = '<div class="bhs">' + "".join(
        f'<div class="bh" style="--i:{i}"><div class="bh-l"><span class="bh-r">{i + 1:02d}</span>'
        f'<span>{UF_NOME.get(r["uf"], r["uf"])}</span></div>'
        f'<div class="bh-t"><i class="{"hi" if r in (mx, mn) else "s1"}" style="--w:{r["pct_cnpj_com_numero_no_mapa"]:.2f}%"></i></div>'
        f'<div class="bh-v"><b>{p1(r["pct_cnpj_com_numero_no_mapa"])}</b>'
        f'<span class="sh">{num(r["drones_cnpj_com_numero_no_mapa"])} de {num(r["drones_agricolas_anac_cnpj"])}</span></div></div>'
        for i, r in enumerate(top12)) + "</div>"
    maior_area = max(U, key=lambda r: r["area_plantada_ha"])
    maior_pj = max(U, key=lambda r: r["drones_agricolas_anac_cnpj"])
    frase_area = ""
    if isinstance(maior_area["operadores_mapa"], int) and maior_area.get("ha_por_drone_mapa"):
        frase_area = (f" {UF_NOME[maior_area['uf']]} planta {mi(maior_area['area_plantada_ha'])} milhões de hectares e tem "
                      f"{num(maior_area['operadores_mapa'])} operadores no MAPA, com {num(maior_area['drones_listados_mapa'])} "
                      f"drones listados: um para cada {milhar(maior_area['ha_por_drone_mapa'])} mil hectares.")
    if maior_pj["uf"] != maior_area["uf"]:
        frase_area += (f" {UF_NOME[maior_pj['uf']]} tem a maior frota agrícola em CNPJ "
                       f"({num(maior_pj['drones_agricolas_anac_cnpj'])} drones) e planta "
                       f"{pct(maior_pj['area_plantada_ha'] / maior_area['area_plantada_ha'], 0)} da área de "
                       f"{UF_NOME[maior_area['uf']]}. Parte disso é sede: empresa registrada lá que voa em outros estados.")
    secoes.append(bloco(
        "agro-estados",
        f"{UF_NOME[mx['uf']]} tem {p1(mx['pct_cnpj_com_numero_no_mapa'])} da frota agrícola empresarial no MAPA; "
        f"{UF_NOME[mn['uf']]}, {p1(mn['pct_cnpj_com_numero_no_mapa'])}",
        f"Entre os 12 estados com mais drones agrícolas em nome de empresa, a fatia com número no MAPA vai de "
        f"{p1(mn['pct_cnpj_com_numero_no_mapa'])} ({UF_NOME[mn['uf']]}) a {p1(mx['pct_cnpj_com_numero_no_mapa'])} "
        f"({UF_NOME[mx['uf']]}).{frase_area}",
        barras_uf,
        nota=f"Por estado só dá para olhar empresa: drone em nome de CPF não tem UF no SISANT, e isso é "
             f"{pct(pf / T, 0)} da frota agrícola. A UF da ANAC é a da sede do CNPJ na Receita Federal; a do MAPA é o "
             f"endereço cadastrado do estabelecimento. Nenhuma das duas diz onde o drone aplica. O gráfico usa escala "
             f"de 0 a 100% e mostra os 12 estados com mais drones agrícolas em CNPJ; nos menores, poucas dezenas de "
             f"drones mexem muito no percentual, e eles ficam na tabela. A soma de drones do MAPA por estado "
             f"({num(MAPA['soma_drones_por_uf'])}) passa do total ({num(listados)}) porque o mesmo drone pode estar em "
             f"dois registros. A área plantada é a da PAM {M['pam_ano']} do IBGE, que soma safra e safrinha e inclui "
             f"lavoura permanente: hectare por drone serve para comparar estados, não mede capacidade de aplicação. "
             f"{num(F['cnpj_sem_uf'])} drones em CNPJ ficaram sem UF porque a Receita não respondeu.",
        tabela_html=tab(["UF", f"Área plantada {M['pam_ano']} (mil ha)", "Drones agrícolas em CNPJ (ANAC)",
                         "% com número no MAPA", "Operadores no MAPA", "Drones listados no MAPA", "Hectares por drone do MAPA"],
                        [[r["uf"], num(round(r["area_plantada_ha"] / 1000)), num(r["drones_agricolas_anac_cnpj"]),
                          p1(r["pct_cnpj_com_numero_no_mapa"]) if r["pct_cnpj_com_numero_no_mapa"] is not None else "n/d",
                          cel(r["operadores_mapa"]), cel(r["drones_listados_mapa"]), cel(r["ha_por_drone_mapa"])]
                         for r in U],
                        f"Estados em ordem de área plantada. ANAC: só drones em CNPJ, UF da sede na Receita. MAPA: UF do "
                        f"estabelecimento. IBGE: PAM {M['pam_ano']}, área plantada ou destinada à colheita. {fonte_cap}",
                        fixa=True),
        rotulo_tab="Ver os 27 estados",
        etiqueta="Agro · recorte empresarial"))

    # --------------------------------------------------------- 4. municípios
    ud = MUN["uf_destaque_sem_operador"]
    ms = MUN["maiores_sem_operador_mapa"]
    ex = MUN.get("exemplo_sede")
    top = ms[0]
    barras_mun = barras_h([(f"{m['municipio']} ({m['uf']})", m["area_plantada_ha"]) for m in ms], limite=12)
    frase_ex = (f" Sede não é onde se opera: {esc(ex['municipio'])} ({ex['uf']}) tem {num(ex['operadores_mapa'])} "
                f"operadores do MAPA com sede e {num(ex['area_plantada_ha'])} hectares plantados. Prestador de serviço "
                f"costuma ficar na cidade-polo e voar num raio grande.") if ex else ""
    limites = [
        ("Operador do MAPA não é drone.",
         f"O registro é do estabelecimento; a lista de aeronaves dentro dele tem código fora do formato "
         f"({num(MAPA['drones_codigo_sem_formato'])}) e drone repetido entre registros ({num(MAPA['drones_em_mais_de_um_registro'])})."),
        ("Sede não é onde opera.",
         "UF e município da ANAC vêm do endereço do CNPJ na Receita; os do MAPA, do endereço cadastrado do "
         "estabelecimento. Nenhum recorte desta seção diz onde mais se pulveriza."),
        ("Pessoa física não tem UF na ANAC.",
         f"São {pct(pf / T, 0)} da frota agrícola. Toda tabela por estado, do lado da ANAC, é só CNPJ."),
        ("Fora do MAPA não é o mesmo que irregular.",
         "A frota da ANAC inclui fabricante, revenda, estoque e empresa de pesquisa, que a Portaria 298 dispensa do "
         "registro (art. 27). E frota cadastrada não é frota voando."),
        ("O ramo é declarado pelo próprio operador.",
         f"{num(F['ramo_ate_2kg'])} drones de até 2 kg estão no ramo de pulverização. Ficam na conta porque o ramo é a "
         f"regra do Observatório, mas é ruído."),
        ("Área plantada soma safra e safrinha.",
         "O mesmo talhão de soja e milho conta duas vezes, e entram lavouras permanentes. Hectare por drone serve para "
         "comparar lugares, não mede capacidade."),
        ("O arquivo do MAPA não tem data por linha.",
         "Não dá para saber quando cada operador se registrou. A série do lado do MAPA sai das cópias que o "
         "Observatório guarda a cada atualização, a primeira de 14/11/2026."),
        ("Endereço de CNPJ vem de espelho da Receita",
         "(Minha Receita, competência 2026-10, mais as consultas mensais do Observatório para CNPJ novo)."),
        ("Datas das três bases.",
         f"ANAC/SISANT: base de {db}. MAPA/SIPEAGRO, registro de aviação agrícola: arquivo de {dm}, baixado em {dbx}. "
         f"IBGE/PAM: área plantada ou destinada à colheita de {M['pam_ano']} (tabela 5457), atualizada pelo IBGE em "
         f"{data_br(M['pam_atualizado_ibge'])}."),
    ]
    lim_html = ('<div class="nota agro-lim" id="agro-metodo"><span class="nota-t">Limites do cruzamento agro e datas das '
                'bases</span><ol>' + "".join(f"<li><strong>{t}</strong> {c}</li>" for t, c in limites) + "</ol></div>")
    s4 = bloco(
        "agro-municipios",
        f"{num(MUN['top100_sem_operador_mapa'])} dos 100 municípios que mais plantam não têm operador de drone do MAPA com sede",
        f"Nos 300 que mais plantam, são {num(MUN['top300_sem_operador_mapa'])}. O maior deles é {esc(top['municipio'])} "
        f"({top['uf']}), com {num(top['area_plantada_ha'])} hectares. Em {UF_NOME.get(ud['uf'], ud['uf'])}, "
        f"{num(ud['sem_operador'])} dos {num(ud['municipios'])} municípios não têm operador do MAPA sediado, e eles somam "
        f"{mi(ud['area_sem_operador_ha'])} milhões de hectares plantados. É um retrato de onde ficam as sedes, não de "
        f"onde se pulveriza. As sedes das empresas de pulverização, cidade por cidade, estão "
        f'<a href="https://irlenmenezes.com.br/onde-estao-cnpjs-de-pulverizacao-com-drone-mapa-por-municipio-sisant-2026/">no mapa do cadastro por município</a>.',
        barras_mun,
        nota=f"Cada operador do MAPA foi ligado ao código IBGE do município pelo endereço cadastrado "
             f"({num(MUN['operadores_com_municipio_ibge'])} de {num(op)} casaram; o resto é distrito ou grafia que não "
             f"bate com a lista do IBGE) e cruzado com a área plantada da PAM {M['pam_ano']}.{frase_ex} Para não expor "
             f"quem opera sozinho, contagem de 1 ou 2 aparece como faixa, e um município só aparece pelo nome com zero ou "
             f"com 3 operadores ou mais. A coluna de empresas da ANAC segue a mesma regra.",
        tabela_html=tab(["Município", "UF", f"Área plantada {M['pam_ano']} (ha)", "Empresas com drone agrícola na ANAC sediadas"],
                        [[esc(m["municipio"]), m["uf"], num(m["area_plantada_ha"]),
                          cel(m["empresas_drone_agricola_anac_sede"])] for m in ms],
                        f"Os {len(ms)} municípios com mais área plantada sem nenhum operador do MAPA com sede. "
                        f"Contagem de 1 ou 2 empresas aparece como faixa. {fonte_cap} IBGE: PAM {M['pam_ano']}.", fixa=True)
        + tab(["Município", "UF", "Operadores do MAPA com sede", "Drones listados", f"Área plantada {M['pam_ano']} (ha)"],
              [[esc(p["municipio"]), p["uf"], num(p["operadores_mapa"]), num(p["drones_listados_mapa"]),
                num(p["area_plantada_ha"])] for p in MUN["polos_operadores_mapa"]],
              "Polos: os municípios com mais operadores do MAPA sediados. Muita sede e pouca lavoura é sinal de prestador "
              "que atende a região.", fixa=True)
        + tab(["UF", "Municípios", "Sem operador do MAPA com sede", "Área plantada nesses municípios (mil ha)"],
              [[u, num(v["municipios"]), num(v["sem_operador"]), num(round(v["area_sem_operador_ha"] / 1000))]
               for u, v in sorted(MUN["sem_operador_por_uf"].items(), key=lambda kv: -kv[1]["area_sem_operador_ha"])],
              f"Municípios sem operador do MAPA sediado, por estado, em ordem de área plantada sem operador. "
              f"IBGE: PAM {M['pam_ano']}.", fixa=True),
        rotulo_tab="Ver as tabelas de municípios",
        etiqueta="Agro · sede x lavoura")
    s4 = s4[:-len("</div></section>")] + lim_html + "</div></section>"
    secoes.append(s4)

    # --------------------------------------------------------- pedaços para o resto da página
    faq_agro = (f"{num(T)} drones agrícolas têm cadastro vigente na ANAC, na base de {db}: {num(F['pelo_ramo'])} declaram "
                f"o ramo de pulverização e {num(F['pelo_modelo'])} são modelos de pulverizador cadastrados em outro ramo. "
                f"{'Só ' if no / T < 0.5 else ''}{pct(no / T)} deles aparecem no registro de aviação agrícola do MAPA. Números maiores que circulam "
                f"na imprensa, como 35 mil, são estimativas de mercado e não saem de nenhum cadastro.")
    faq_mapa = ("Quantos drones agrícolas estão registrados no MAPA?",
                f"O registro de aviação agrícola do MAPA (SIPEAGRO) lista {num(listados)} drones em {num(op)} operadores "
                f"com registro ativo, sendo {num(op_pj)} empresas e {num(op_pf)} pessoas físicas, no arquivo de {dm}. "
                f"Cruzando pelo número da aeronave, {num(no)} dos {num(T)} drones agrícolas com cadastro vigente na ANAC "
                f"aparecem no MAPA ({pct(no / T)}): {pct(no_pj / pj)} dos que estão em nome de empresa e "
                f"{pct(no_pf / pf)} dos que estão em nome de pessoa física.")
    metodo_li = ('<li><strong>Seção agro.</strong> Os drones agrícolas do SISANT são cruzados, pelo número da '
                 'aeronave, com o arquivo de registro de aviação agrícola do MAPA (SIPEAGRO, dados abertos) e com a '
                 'área plantada da PAM do IBGE. O arquivo do MAPA traz e-mail, telefone e nome de pessoa física: nada '
                 'disso é publicado, só agregados, e contagem de 1 ou 2 por município vira faixa. O arquivo do MAPA é '
                 'guardado a cada atualização para formar série. Regras e limites estão no '
                 '<a href="#agro-metodo">fim da seção agro</a>.</li>')
    ficha = (f'<dt>Base MAPA</dt><dd>registro de aviação agrícola (SIPEAGRO), arquivo de {dm}, baixado em {dbx}</dd>'
             f'<dt>Base IBGE</dt><dd>PAM {M["pam_ano"]}, área plantada ou destinada à colheita (tabela 5457)</dd>')
    return {
        "secoes": secoes, "indice": INDICE, "css": CSS, "faq_agro": faq_agro, "faq_mapa": faq_mapa,
        "metodo_li": metodo_li, "ficha": ficha,
        "fonte": " Seção agro cruzada com o registro de aviação agrícola do MAPA e a área plantada do IBGE.",
        "ds_desc": " Inclui o cruzamento dos drones agrícolas com o registro de aviação agrícola do MAPA (SIPEAGRO) "
                   "e com a área plantada do IBGE (PAM).",
        "ds_vars": [
            {"@type": "PropertyValue", "name": "Drones agrícolas com cadastro vigente na ANAC", "value": T},
            {"@type": "PropertyValue", "name": "Drones agrícolas da ANAC com número no registro do MAPA",
             "value": round(no / T * 100, 1), "unitText": "%"},
            {"@type": "PropertyValue", "name": "Operadores de drone com registro ativo no MAPA", "value": op},
        ],
        "ds_base": [
            {"@type": "Dataset", "name": "SIPEAGRO: registro de aviação agrícola",
             "description": "Arquivo de dados abertos do Ministério da Agricultura e Pecuária com os estabelecimentos "
                            "registrados para aviação agrícola, a atividade, a situação do registro e as aeronaves, "
                            "tripuladas e remotamente pilotadas, vinculadas a cada um.",
             "creator": {"@type": "Organization", "name": "Ministério da Agricultura e Pecuária (MAPA)",
                         "url": "https://www.gov.br/agricultura/"},
             "url": "https://dados.agricultura.gov.br/dataset/sipeagro"},
            {"@type": "Dataset", "name": "Produção Agrícola Municipal (PAM), tabela 5457",
             "description": "Pesquisa anual do IBGE com área plantada ou destinada à colheita, área colhida, "
                            "quantidade produzida e valor da produção das lavouras, por município.",
             "creator": {"@type": "Organization", "name": "Instituto Brasileiro de Geografia e Estatística (IBGE)",
                         "url": "https://www.ibge.gov.br/"},
             "url": "https://sidra.ibge.gov.br/tabela/5457"},
        ],
        "keywords": ["drone agrícola", "MAPA", "SIPEAGRO", "aviação agrícola", "pulverização"],
    }
