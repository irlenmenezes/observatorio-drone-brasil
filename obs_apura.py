#!/usr/bin/env python3
"""
Apura o Observatorio do Drone no Brasil a partir do SISANT bruto.

Gera obs-drone.json, que alimenta a pagina estatica. Roda de novo a cada base
nova da ANAC: baixa o CSV, aponta ORIGEM aqui e executa.

Decisoes de metodo (todas declaradas na pagina, para nao enganar leitor):
  * A data de cadastro NAO existe no arquivo. Ela e derivada de
    DATA_VALIDADE - 24 meses, e o script confere essa premissa antes de usar.
    Como renovar reemite a validade, a serie mede "cadastros novos OU
    renovados" no mes, nao apenas primeiros cadastros.
  * UF tambem nao existe no arquivo. Vem da Receita, via CNPJ, e por isso
    cobre so a fatia PJ da base. CPF vem mascarado e nao tem como resolver.
  * Frota bruta por UF engana: shows de drone de luz somam milhares de
    aeronaves em pouquissimos CNPJs. Por isso a metrica principal e EMPRESAS,
    e a frota aparece tambem sem os ramos de enxame.
"""
import csv
import collections
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).parent
ORIGEM = BASE / "SISANT_new.csv"
SAIDA = BASE / "obs-drone.json"
CACHE_UF = BASE / "cnpj-uf-cache.json"

VALIDADE_MESES = 24
PREFIXOS_ENXAME = ("aeropublicidade", "aerodemonstra")
# Versao do metodo: sobe quando muda regra de contagem, normalizacao ou recorte
# (nao quando entra base nova). Cada edicao publicada guarda a versao com que foi
# apurada, para que um numero citado hoje continue conferivel depois.
VERSAO_METODO = "2026.09.2"
HISTORICO_METODO = [
    ("2026.08.1", "primeira apuração pública: série por validade menos 24 meses, UF via Receita, ramos agrupados"),
    ("2026.09.1", "snapshot por base; modelos colapsados por família; códigos de modelo decifrados pela própria base"),
    ("2026.09.2", "comparação entre bases pelo código da aeronave; checagens de consistência antes de publicar; "
                  "rótulos revisados (aeronaves em nome de CPF, modelos mais cadastrados, UF da sede)"),
]


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def menos_meses(d: datetime.date, meses: int) -> datetime.date:
    ano, mes = divmod((d.year * 12 + d.month - 1) - meses, 12)
    mes += 1
    dia = min(d.day, [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1])
    return datetime.date(ano, mes, dia)


# ----------------------------------------------------------------- ramos
RAMOS = [
    ("Recreativo", ("recreativo", "lazer", "hobby", "recreacao", "recreio")),
    ("Agricola / pulverizacao", ("pulveriza", "aeroagric", "agricola", "agricultura", "insumo")),
    ("Cinema e fotografia", ("aerocinematografia", "aerofotografia", "filmagem", "fotografia",
                             "audiovisual", "cinematografia")),
    ("Aerolevantamento e topografia", ("aerolevantamento", "fotogrametria", "topografia",
                                       "aeroprospec", "mapeamento")),
    ("Seguranca publica e defesa civil", ("seguranca publica", "defesa civil", "policia",
                                          "bombeiro", "combate a incendio")),
    ("Inspecao tecnica", ("aeroinspe", "inspecao")),
    ("Show de luzes e publicidade", ("aeropublicidade", "aerodemonstra", "letreiro", "publicidade")),
    ("Fiscalizacao e orgaos estatais", ("fiscaliza", "entidades estatais", "orgaos de")),
    ("Treinamento", ("treinamento", "instrucao", "escola")),
    ("Transporte de carga", ("transporte de carga", "mercadoria", "entrega", "delivery")),
    ("Reportagem", ("aerorreportagem", "reportagem", "jornalismo")),
    ("Experimental", ("experimental", "pesquisa", "cientific")),
]


def classifica_ramo(bruto: str) -> str:
    r = sem_acento((bruto or "").strip().lower())
    if not r or r == "null":
        return "Nao informado"
    for rotulo, chaves in RAMOS:
        if any(k in r for k in chaves):
            return rotulo
    return "Outros"


# ---------------------------------------------------------------- modelos
FAMILIAS = ("MINI", "AIR", "MAVIC", "PHANTOM", "INSPIRE", "AVATA", "NEO", "FPV", "SPARK",
            "TELLO", "MATRICE", "AGRAS", "EVO", "LITO", "FLIP", "EBEE", "ANAFI", "T10",
            "T20", "T25", "T30", "T40", "T50", "P4", "M30", "M300", "M350", "M3")


def normaliza_modelo(bruto: str) -> str:
    m = sem_acento((bruto or "").strip().upper())
    m = re.sub(r"\(.*?\)", " ", m)                      # "( RC 2)", "(RC-N1)"
    m = re.sub(r"[^A-Z0-9 ]+", " ", m)                  # hifen, ponto, barra
    m = re.sub(r"\b(DJI|SZ|TECHNOLOGY|CO|LTD|DA JIANG|INNOVATIONS)\b", " ", m)
    # Espacamento: muita gente digita o modelo grudado. Sem isto, "Mini 4Pro Fly
    # More Combo Plus" (1.204 unidades) e "Mini4Pro" nao entram na familia e o
    # ranking subconta. Conferido em 05/08/2026: 1.393 aeronaves recuperadas so
    # no Mini 4 Pro. A remocao de acento acima ja resolve o caso inverso ("Pro").
    m = re.sub(r"\bMINI(\d)", r"MINI \1", m)
    m = re.sub(r"\bAIR(\d)", r"AIR \1", m)
    m = re.sub(r"\bNEO(\d)", r"NEO \1", m)
    m = re.sub(r"\bMAVIC(\d)", r"MAVIC \1", m)
    m = re.sub(r"(\d)PRO\b", r"\1 PRO", m)
    m = re.sub(r"\s+", " ", m).strip()
    # Agras cadastrado so pelo codigo: "T25", "T50". Sao 1.625 aeronaves que
    # ficariam fora da linha agricola. Conservador de proposito: so quando a
    # string INTEIRA e o codigo, para nao capturar modelo de outro fabricante.
    if re.fullmatch(r"T\s?(10|16|20|25|30|40|50|60|70|100)P?", m):
        m = "AGRAS " + m.replace(" ", "")
    return m


# O campo FABRICANTE e digitado a mao e vem sujo: "DJ I", "D JI", "SZ DJI TECHNOLOGY
# CO., LTD - 6500", razao social inteira, e ate o modelo no lugar da marca. Agrupar
# pela primeira palavra jogava 1.023 aeronaves da DJI num fabricante chamado "D".
MARCAS = (
    ("DJI", ("DJI", "DAJIANG", "SZDJI")),
    ("Xiaomi / FIMI", ("XIAOMI", "FIMI")),
    ("Autel", ("AUTEL",)),
    ("Parrot", ("PARROT", "ANAFI")),
    ("XAG", ("XAG",)),
    ("Damoda", ("DAMODA",)),
    ("Nova Sky Stories", ("NOVASKY",)),
    ("SMD Baltic", ("SMDBALTIC",)),
    ("Hubsan", ("HUBSAN",)),
    ("SJRC", ("SJRC",)),
    ("Eavision", ("EAVISION",)),
    ("senseFly", ("SENSEFLY", "EBEE")),
    ("Skydio", ("SKYDIO",)),
)


def normaliza_marca(bruto: str) -> str:
    compacto = re.sub(r"[^A-Z0-9]", "", bruto or "")
    if not compacto:
        return "Nao informado"
    for rotulo, chaves in MARCAS:
        if any(compacto.startswith(k) or k in compacto for k in chaves):
            return rotulo
    return (bruto.split()[0] if bruto.split() else "Nao informado").title()


def parece_codigo(m: str) -> bool:
    """Codigo interno tipo MT3PD, sem nome de familia reconhecivel."""
    if not m or " " in m:
        return not m or (len(m.split()) == 1 and False)
    return (not any(f in m for f in FAMILIAS)) and bool(re.fullmatch(r"[A-Z0-9]{3,9}", m))


# Contar rotulo exato fragmenta a mesma aeronave: "MAVIC 3", "MAVIC 3 CINE
# PREMIUM COMBO" e "MAVIC 3 FLY MORE" viram tres linhas e nenhuma mostra o
# tamanho real da familia. O ranking publicado precisa responder "qual drone o
# Brasil mais usa", entao colapsa para familia. Ordem: do mais especifico para o
# mais generico, senao "MINI 3 PRO" cairia dentro de "MINI 3".
FAMILIA_CANON = [
    "MINI 5 PRO", "MINI 4 PRO", "MINI 3 PRO", "MINI 4K", "MINI 2 SE", "MINI SE",
    "MINI 4", "MINI 3", "MINI 2", "MAVIC MINI", "MINI",
    "NEO 2", "NEO", "AVATA 2", "AVATA",
    "AIR 3S", "AIR 3", "AIR 2S", "MAVIC AIR 2", "MAVIC AIR", "AIR",
    "LITO X1", "LITO 1", "LITO", "FLIP",
    "MAVIC 4 PRO", "MAVIC 3 PRO", "MAVIC 3 CLASSIC", "MAVIC 3", "MAVIC 2 PRO",
    "MAVIC 2", "MAVIC PRO", "MAVIC",
    "PHANTOM 4", "PHANTOM 3", "PHANTOM", "SPARK", "TELLO",
    "AGRAS T100", "AGRAS T70", "AGRAS T50", "AGRAS T40", "AGRAS T30",
    "AGRAS T25", "AGRAS T20", "AGRAS T16", "AGRAS T10", "AGRAS",
    "MATRICE", "INSPIRE",
]


def familia_modelo(m: str) -> str:
    alvo = " " + m + " "
    for chave in FAMILIA_CANON:
        if alvo.startswith(" " + chave + " ") or (" " + chave + " ") in alvo:
            return chave
    return m


# ------------------------------------------------------------------ leitura
if not ORIGEM.exists():
    sys.exit(f"nao achei {ORIGEM}")

cabecalho = ORIGEM.open(encoding="utf-8-sig").readline().strip()
mdata = re.search(r"(\d{4})-(\d{2})-(\d{2})", cabecalho)
if not mdata:
    sys.exit(f"nao consegui ler a data do cabecalho: {cabecalho!r}")
DATA_BASE = datetime.date(*map(int, mdata.groups()))

total = pj = pf = 0
uso = collections.Counter()
prefixo = collections.Counter()
ramos = collections.Counter()
modelos = collections.Counter()
fabricantes = collections.Counter()
peso_faixa = collections.Counter()
cadastro_mes = collections.Counter()
vencimento_mes = collections.Counter()
vencidos = 0
frota_cnpj = collections.Counter()
nome_cnpj = {}
ramo_cnpj = collections.defaultdict(collections.Counter)
# evidencia para decifrar codigo de modelo usando a propria base
codigo_evidencia = collections.defaultdict(collections.Counter)
futuro = 0

with open(ORIGEM, encoding="utf-8-sig") as f:
    f.readline()
    for row in csv.DictReader(f, delimiter=";"):
        total += 1

        val = datetime.datetime.strptime(row["DATA_VALIDADE"].strip(), "%d/%m/%Y").date()
        cad = menos_meses(val, VALIDADE_MESES)
        if cad > DATA_BASE:
            futuro += 1
        cadastro_mes[f"{cad:%Y-%m}"] += 1
        if val < DATA_BASE:
            vencidos += 1
        else:
            vencimento_mes[f"{val:%Y-%m}"] += 1

        cod = (row["CODIGO_AERONAVE"] or "").strip().upper()
        prefixo[cod[:2] if cod[2:3] == "-" else "??"] += 1
        uso[(row["TIPO_USO"] or "").strip()] += 1
        ramos[classifica_ramo(row["RAMO_ATIVIDADE"])] += 1

        fab_bruto = sem_acento((row["FABRICANTE"] or "").strip().upper())
        mod = normaliza_modelo(row["MODELO"])
        fab_mod = normaliza_modelo(row["FABRICANTE"])
        if mod:
            modelos[mod] += 1
            if parece_codigo(mod) and fab_mod and not parece_codigo(fab_mod):
                codigo_evidencia[mod][fab_mod] += 1

        fabricantes[normaliza_marca(fab_bruto)] += 1

        p = float((row["PESO_MAXIMO_DECOLAGEM_KG"] or "0").replace(",", "."))
        peso_faixa["Ate 250 g" if p < 0.25 else "250 g a 2 kg" if p < 2
                   else "2 a 25 kg" if p < 25 else "Acima de 25 kg"] += 1

        doc = (row["CPF_CNPJ"] or "").strip()
        if doc.upper().startswith("CNPJ"):
            pj += 1
            dig = "".join(c for c in doc if c.isdigit())
            if len(dig) == 14:
                frota_cnpj[dig] += 1
                nome_cnpj.setdefault(dig, (row["OPERADOR"] or "").strip())
                ramo_cnpj[dig][(row["RAMO_ATIVIDADE"] or "").strip()] += 1
        else:
            pf += 1

# checagem da premissa dos 24 meses: nenhum cadastro pode cair no futuro
if futuro:
    sys.exit(f"ABORTADO: {futuro} cadastros derivados caem depois de {DATA_BASE}. "
             "A validade de 24 meses nao vale para essa base.")

# ------------------------------------------- decifra codigo de modelo pela base
# So aceita quando a propria base concorda: o codigo tem que aparecer com o mesmo
# nome legivel em ao menos 80% das linhas. E o nome tem que ser de modelo, nao de
# empresa, senao razao social entra no ranking de drone (aconteceu com EAVISION).
RAZAO_SOCIAL = ("TECHNOLOG", "ROBOTIC", "LTDA", "IMPORTACAO", "EXPORTACAO", "INDUSTRIA",
                "COMERCIO", "INNOVATION", "ELECTRONIC", "SCIENCE", "GROUP", "COMPANY")
apelidos = {}
for cod_mod, cands in codigo_evidencia.items():
    alvo, n = cands.most_common(1)[0]
    if any(w in alvo for w in RAZAO_SOCIAL) or len(alvo.split()) > 3:
        continue
    if n >= 20 and n / sum(cands.values()) >= 0.8:
        apelidos[cod_mod] = alvo
if apelidos:
    for cod_mod, alvo in apelidos.items():
        modelos[alvo] += modelos.pop(cod_mod, 0)

# colapso por familia (depois de decifrar os codigos, senao MT3PD ficaria de fora)
modelos_familia = collections.Counter()
for _m, _n in modelos.items():
    modelos_familia[familia_modelo(_m)] += _n

# -------------------------------------------------------------- concentracao
ordenado = frota_cnpj.most_common()
frota_pj_total = sum(frota_cnpj.values())
concentracao = []
acum = i = 0
for marco in (50, 100, 250, 500, 1000, 2000, 4000):
    if marco > len(ordenado):
        break
    while i < marco:
        acum += ordenado[i][1]
        i += 1
    concentracao.append({"top": marco, "aeronaves": acum, "share": round(acum / frota_pj_total, 4)})

# ---------------------------------------------------------------------- UF
cache = json.loads(CACHE_UF.read_text(encoding="utf-8")) if CACHE_UF.exists() else {}
empresas_uf = collections.Counter()
frota_uf = collections.Counter()
frota_uf_limpa = collections.Counter()
municipios = collections.Counter()
sem_uf = frota_sem_uf = 0

for cnpj, n in ordenado:
    info = cache.get(cnpj) or {}
    uf = info.get("uf")
    if not uf:
        sem_uf += 1
        frota_sem_uf += n
        continue
    ramo_principal = ramo_cnpj[cnpj].most_common(1)[0][0]
    empresas_uf[uf] += 1
    frota_uf[uf] += n
    if not sem_acento(ramo_principal.lower()).startswith(PREFIXOS_ENXAME):
        frota_uf_limpa[uf] += n
    mun = (info.get("municipio") or "").title()
    if mun:
        municipios[f"{mun}/{uf}"] += 1

# ------------------------------------------------------------------- serie
# A base guarda apenas cadastro VIGENTE. Como a validade e de 24 meses, qualquer
# mes anterior a (data_base - 24 meses) so contem os poucos vencidos que ainda
# nao sairam do arquivo: 95 registros em 4 anos. Publicar esse trecho sugeriria
# que o mercado nasceu em 2024, o que e falso. Entao a serie comeca na janela
# completa, e o mes corrente vai marcado como parcial (o mes ainda nao acabou).
inicio = f"{menos_meses(DATA_BASE, VALIDADE_MESES):%Y-%m}"
descartados = sum(n for m, n in cadastro_mes.items() if m < inicio)
mes_corrente = f"{DATA_BASE:%Y-%m}"
serie = []
acumulado = 0
for m in sorted(cadastro_mes):
    if m < inicio:
        continue
    acumulado += cadastro_mes[m]
    item = {"mes": m, "novos": cadastro_mes[m], "acumulado": acumulado}
    if m == mes_corrente:
        item["parcial"] = True
        item["dias"] = DATA_BASE.day
    serie.append(item)

top_operadores = [
    {"nome": nome_cnpj[c], "frota": n, "ramo": ramo_cnpj[c].most_common(1)[0][0],
     "uf": (cache.get(c) or {}).get("uf", "")}
    for c, n in ordenado[:20]
]

# ------------------------------------------------- checagens de consistencia
# Nada e publicado se os totais nao fecharem. Cada recorte precisa somar o total
# do arquivo; diferenca so pode vir de filtro documentado (a serie descarta os
# meses fora da janela, e o descarte e contado). Tambem compara com a edicao
# anterior: uma base que encolhe ou salta demais e sinal de arquivo quebrado.
checagens = [
    ("PF + PJ = total", pf + pj == total),
    ("faixas de peso somam o total", sum(peso_faixa.values()) == total),
    ("prefixos de matricula somam o total", sum(prefixo.values()) == total),
    ("ramos agrupados somam o total", sum(ramos.values()) == total),
    ("serie + descartados = total", sum(s["novos"] for s in serie) + descartados == total),
    ("vencimentos futuros + vencidos = total", sum(vencimento_mes.values()) + vencidos == total),
    ("frota PJ = registros com CNPJ valido", frota_pj_total <= pj),
    ("UF: resolvidos + sem resposta = CNPJs", sum(empresas_uf.values()) + sem_uf == len(frota_cnpj)),
    ("premissa dos 24 meses", futuro == 0),
]
if SAIDA.exists():
    anterior = json.loads(SAIDA.read_text(encoding="utf-8"))
    t_ant = anterior.get("resumo", {}).get("total", 0)
    if t_ant:
        checagens.append((f"variacao do total contra a edicao anterior ({t_ant}) dentro de 15%",
                          abs(total - t_ant) / t_ant <= 0.15))
falhas = [nome for nome, ok in checagens if not ok]
if falhas:
    sys.exit("ABORTADO, checagem de consistencia falhou:\n  - " + "\n  - ".join(falhas))
print(f"checagens de consistencia: {len(checagens)} OK")

saida = {
    "meta": {
        "fonte": "ANAC / SISANT",
        "fonte_url": "https://sistemas.anac.gov.br/dadosabertos/Aeronaves/drones%20cadastrados/SISANT.csv",
        "data_base": DATA_BASE.isoformat(),
        "processado_em": datetime.datetime.now().replace(microsecond=0).isoformat(),
        "versao_metodo": VERSAO_METODO,
        "historico_metodo": [{"versao": v, "mudanca": m} for v, m in HISTORICO_METODO],
        "registros": total,
        "validade_meses": VALIDADE_MESES,
        "licenca": "CC BY 4.0",
        "checagens": [nome for nome, _ in checagens],
        "conteudo": "Resultados consolidados e agregados apurados sobre o arquivo SISANT; "
                    "nao contem os registros individuais. O arquivo bruto esta em fonte_url.",
    },
    "resumo": {
        "total": total, "pf": pf, "pj": pj,
        "cnpjs": len(frota_cnpj), "vencidos": vencidos,
        "frota_pj": frota_pj_total,
    },
    "serie": serie,
    "serie_nota": {
        "inicio": inicio,
        "descartados": descartados,
        "explicacao": "A serie cobre so a janela de 24 meses porque o arquivo da ANAC "
                      "lista apenas cadastro vigente. Cada barra conta emissoes do mes, "
                      "somando primeiro cadastro e renovacao.",
    },
    "vencimentos": [{"mes": m, "qtd": vencimento_mes[m]} for m in sorted(vencimento_mes)],
    "uso": {"prefixo": dict(prefixo), "tipo": dict(uso)},
    "ramos": dict(ramos.most_common()),
    "modelos": [{"modelo": m, "qtd": n} for m, n in modelos_familia.most_common(30)],
    "fabricantes": [{"marca": m, "qtd": n} for m, n in fabricantes.most_common(12)],
    "peso": dict(peso_faixa),
    "concentracao": concentracao,
    "top_operadores": top_operadores,
    "uf": {
        "empresas": dict(empresas_uf), "frota": dict(frota_uf),
        "frota_sem_enxame": dict(frota_uf_limpa),
        "municipios": dict(municipios.most_common(30)),
        "cobertura": {
            "cnpjs_total": len(frota_cnpj), "cnpjs_com_uf": sum(empresas_uf.values()),
            "cnpjs_sem_uf": sem_uf, "frota_sem_uf": frota_sem_uf,
        },
    },
    "apelidos_decifrados": apelidos,
}
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"base ANAC de {DATA_BASE}  |  {total} registros")
print(f"PF {pf} ({pf/total:.1%})  PJ {pj} ({pj/total:.1%})  CNPJs {len(frota_cnpj)}  vencidos {vencidos}")
print(f"prefixos: {dict(prefixo)}")
print(f"UF: {sum(empresas_uf.values())} CNPJs resolvidos, {sem_uf} sem resposta ({frota_sem_uf} aeronaves)")
print(f"codigos de modelo decifrados pela propria base: {len(apelidos)} -> {list(apelidos.items())[:6]}")
print(f"serie: {serie[0]['mes']} a {serie[-1]['mes']} ({len(serie)} meses)")
print("\ntop 10 modelos:")
for it in saida["modelos"][:10]:
    print(f"   {it['qtd']:>7}  {it['modelo']}")
print("\nvencimentos dos proximos 6 meses:")
for it in saida["vencimentos"][:6]:
    print(f"   {it['mes']}  {it['qtd']:>6}")
print(f"\ngravado: {SAIDA.name}")
