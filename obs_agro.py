# -*- coding: utf-8 -*-
"""Seção Agro do Observatório (14/11/2026): ANAC/SISANT x MAPA/SIPEAGRO x IBGE/PAM.

Lê a base corrente da ANAC (SISANT_new.csv), o snapshot mais recente do MAPA
(snapshots/mapa/sipeagro_registro_*.csv, baixado por obs_mapa_baixa.py) e a área plantada do
IBGE (obs-agro-ref/). Grava obs-agro.json, que o obs_build.py lê, e uma cópia datada
obs-agro-<base ANAC>.json para o arquivo de edições.

Regras (as mesmas da checagem de viabilidade em agro-viab/VIABILIDADE.md):
  * Drone agrícola = ramo agrícola pela classifica_ramo do Observatório OU modelo de
    pulverizador (Agras, MG-1, XAG, EAVision...) declarado em outro ramo, com 2 kg ou mais
    e sem nome de drone de consumo. Só cadastro vigente, deduplicado por código + dono.
  * Casamento ANAC x MAPA pelos 9 dígitos do número: o MAPA grava PS + 9 dígitos e a ANAC
    lista o mesmo número com PP. Os 9 dígitos não se repetem no SISANT.
  * Operador do MAPA = estabelecimento com registro ativo e ao menos um drone, sem as
    entidades que só dão curso.

🚨 PRIVACIDADE: o CSV do MAPA traz e-mail, telefone e nome de pessoa física. Este script só
grava AGREGADOS: totais nacionais, por UF e por município com corte mínimo (contagem de
operador ou de empresa entre 1 e 2 vira a faixa "1 a 2"; município só aparece nominalmente
com 0 ou 3+). Antes de gravar, varre o JSON atrás de e-mail, telefone, CPF mascarado e de
qualquer nome de pessoa física ou responsável técnico do arquivo. Achou, não grava.

Código de saída: 0 = ok; 2 = falta insumo; 3 = checagem falhou (nada gravado).
Uso:  python obs_agro.py [caminho_do_csv_do_mapa]
"""
import ast
import collections
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).parent
SISANT = HERE / "SISANT_new.csv"
SNAP = HERE / "snapshots"
SNAP_MAPA = SNAP / "mapa"
REF = HERE / "obs-agro-ref"
SAIDA = HERE / "obs-agro.json"
CACHE_SERIE = HERE / "obs-agro-serie-cache.json"   # agregados por snapshot (local, evita reler tudo)

VERSAO_METODO_AGRO = "2026.11.1"
CORTE_MIN = 3        # abaixo disso (e acima de zero) a contagem por município vira faixa
PAM_ANO = 2025
PAM_ATUALIZADO = "2026-10-23"
URL_MAPA = "https://dados.agricultura.gov.br/dataset/sipeagro"
URL_PAM = "https://sidra.ibge.gov.br/tabela/5457"
URL_PORTARIA = "https://www.in.gov.br/web/dou/-/portaria-n-298-de-22-de-setembro-de-2021-347221930"


def sai(cod, msg):
    print(msg)
    sys.exit(cod)


# --------------------------------------------- regras do Observatório (sem rodar obs_apura.py)
# obs_apura.py executa tudo no nível do módulo; importar direto reescreveria obs-drone.json.
# Então extraio só funções e constantes pela árvore sintática.
_src = (HERE / "obs_apura.py").read_text(encoding="utf-8")
_keep = []
for _n in ast.parse(_src).body:
    if isinstance(_n, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
        _keep.append(_n)
    elif isinstance(_n, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in _n.targets):
        if not any(t.id in ("BASE", "ORIGEM", "SAIDA", "CACHE_UF", "DATA_BASE") for t in _n.targets):
            _keep.append(_n)
_ns = {}
exec(compile(ast.Module(body=_keep, type_ignores=[]), "obs_apura.py", "exec"), _ns)
sem_acento = _ns["sem_acento"]
classifica_ramo = _ns["classifica_ramo"]
normaliza_modelo = _ns["normaliza_modelo"]
normaliza_marca = _ns["normaliza_marca"]
familia_modelo = _ns["familia_modelo"]

PULV = re.compile(r"AGRAS|\bMG ?1|\bT ?(10|16|20|25|30|40|50|55|60|70|100)\s?P?\b|XAG|\bP ?(20|40|60|100|150)\b|\bV ?(40|50)\b|\bXP ?20|"
                  r"EAVISION|\bEA ?-? ?(20|30|60|2021)|TOPXGUN|\bFP ?(300|500|600)|JOYANCE|3WWDZ|\bKING ?100|\bGT ?40|\bX ?800|XFLY|X-FLY|"
                  r"GTEEX|HYLIO|PELICAN|\bMG ?50|\bU ?(60|70|75)\b|PYKA|HUIDA|\bHD ?540")
NAO_PULV = re.compile(r"SNAPTAIN|\bMINI\b|PHANTOM|MAVIC|\bAIR ?\d|AVATA|\bNEO\b|TELLO|SPARK")
SIS_PAT = re.compile(r"^P[PRS]\d{9}$")
RAB = re.compile(r"^P[PRSTU][A-Z]{3}$")
dig = lambda s: re.sub(r"\D", "", s or "")
norm_cod = lambda a: re.sub(r"[^A-Z0-9]", "", (a or "").upper())
num9 = lambda c: c[2:] if SIS_PAT.match(c) else None


def peso(r):
    try:
        return float((r["PESO_MAXIMO_DECOLAGEM_KG"] or "0").replace(",", "."))
    except ValueError:
        return 0.0


def eh_cnpj(r):
    return (r["CPF_CNPJ"] or "").strip().upper().startswith("CNPJ")


def classe_agro(r):
    """'ramo' = declarou o ramo agrícola; 'modelo' = pulverizador declarado em outro ramo; None = fora."""
    if classifica_ramo(r["RAMO_ATIVIDADE"]) == "Agricola / pulverizacao":
        return "ramo"
    txt = sem_acento(((r["FABRICANTE"] or "") + " | " + (r["MODELO"] or "")).upper())
    if PULV.search(txt) and not NAO_PULV.search(txt) and peso(r) >= 2:
        return "modelo"
    return None


def data_cabecalho(caminho):
    with open(caminho, encoding="utf-8-sig", errors="replace") as f:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", f.readline())
    return dt.date(*map(int, m.groups())) if m else None


def le_sisant(caminho, data_base):
    """Cadastros distintos por código + dono; vigentes = validade a partir da data da base."""
    with open(caminho, encoding="utf-8-sig", errors="replace") as f:
        primeira = f.readline()
        if "CODIGO_AERONAVE" in primeira:
            f.seek(0)
        vistos = {}
        for r in csv.DictReader(f, delimiter=";"):
            vistos.setdefault(((r["CODIGO_AERONAVE"] or "").strip().upper(), (r["CPF_CNPJ"] or "").strip()), r)
    todos = list(vistos.values())
    vig = []
    for r in todos:
        try:
            if dt.datetime.strptime(r["DATA_VALIDADE"].strip(), "%d/%m/%Y").date() >= data_base:
                vig.append(r)
        except ValueError:
            pass
    return todos, vig


def faixa(n):
    """Corte mínimo de privacidade: 1 ou 2 vira texto; 0 e 3+ ficam como número."""
    return n if n == 0 or n >= CORTE_MIN else f"1 a {CORTE_MIN - 1}"


# ------------------------------------------------------------------ IBGE (referência fixa)
def chave_nome(s):
    s = sem_acento((s or "").upper()).replace("D'", "D").replace("'", "").replace("-", " ")
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\s+", " ", s)).strip()


MUN = json.loads((REF / "ibge_municipios.json").read_text(encoding="utf-8"))
UF_DE_COD, COD_DE_NOME, NOME_DE_COD = {}, {}, {}
for _m in MUN:
    _uf = (_m["microrregiao"]["mesorregiao"]["UF"]["sigla"] if _m.get("microrregiao")
           else _m["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"])
    UF_DE_COD[_m["id"]] = _uf
    NOME_DE_COD[_m["id"]] = (_m["nome"], _uf)
    COD_DE_NOME[(_uf, chave_nome(_m["nome"]))] = _m["id"]
APELIDO_MUN = {("SP", "MOJI MIRIM"): ("SP", "MOGI MIRIM"), ("SP", "EMBU"): ("SP", "EMBU DAS ARTES"),
               ("TO", "SAO VALERIO DA NATIVIDADE"): ("TO", "SAO VALERIO"), ("MT", "POXOREO"): ("MT", "POXOREU"),
               ("MG", "SAO TOME DAS LETRAS"): ("MG", "SAO THOME DAS LETRAS")}


def cod_mun(uf, nome):
    k = (uf, chave_nome(nome))
    return COD_DE_NOME.get(APELIDO_MUN.get(k, k))


SIG = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
       "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
       "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}


def le_pam(nivel):
    d = json.loads((REF / f"pam{PAM_ANO}_area_{nivel}.json").read_text(encoding="utf-8"))
    out = {}
    for s in d[0]["resultados"][0]["series"]:
        v = s["serie"][str(PAM_ANO)]
        out[s["localidade"]["id"]] = int(v) if v.isdigit() else 0
    return out


# ------------------------------------------------------------------ MAPA
def le_mapa(caminho):
    """Estabelecimentos do arquivo do MAPA. Devolve também os valores pessoais do arquivo,
    só para a varredura de privacidade (nunca são gravados)."""
    linhas = list(csv.DictReader(open(caminho, encoding="utf-8-sig", errors="replace"), delimiter=";"))
    especie = collections.defaultdict(collections.Counter)
    for r in linhas:
        especie[norm_cod(r["NUMERO_REGISTRO_AERONAVE"])][r["ESPECIE"]] += 1

    def eh_drone(a):
        if SIS_PAT.match(a):
            return True
        if RAB.match(a):
            return False
        return especie[a].most_common(1)[0][0] == "Remotamente Pilotada"

    pessoais = set()
    est = {}
    for r in linhas:
        for campo in ("EMAIL", "TELEFONE", "NOME_RESPONSAVEL_TECNICO"):
            v = (r.get(campo) or "").strip()
            if len(v) >= 6:
                pessoais.add(v.upper())
        if (r.get("CPF_CNPJ") or "").startswith("***"):
            for campo in ("RAZAO_SOCIAL", "NOME_FANTASIA"):
                v = (r.get(campo) or "").strip()
                if len(v) >= 6:
                    pessoais.add(v.upper())
        k = r["NUMERO_REGISTRO_ESTABELECIMENTO"]
        e = est.setdefault(k, {"doc": r["CPF_CNPJ"], "status": set(), "ativ": set(),
                               "loc": collections.Counter(), "aer": set()})
        e["status"].add(r["STATUS_REGISTRO_ESTABELECIMENTO"])
        e["ativ"].add(r["ATIVIDADE"])
        e["loc"][(r["UNIDADE_DA_FEDERACAO"], r["MUNICIPIO"])] += 1
        a = norm_cod(r["NUMERO_REGISTRO_AERONAVE"])
        if a:
            e["aer"].add(a)
    for e in est.values():
        e["ativo"] = "Ativo" in e["status"]
        e["drones"] = {a for a in e["aer"] if eh_drone(a)}
        e["avioes"] = {a for a in e["aer"] if RAB.match(a)}
        e["so_ensino"] = e["ativ"] == {"ENTIDADES DE ENSINO"}
        (uf, mun), _ = e["loc"].most_common(1)[0]
        e["uf"], e["mun"] = uf, cod_mun(uf, mun)
        e["pj"] = not (e["doc"] or "").startswith("***")
        e["cnpj"] = dig(e["doc"]) if e["pj"] else None
    return linhas, est, pessoais


def resumo_mapa(est):
    op = [e for e in est.values() if e["ativo"] and e["drones"] and not e["so_ensino"]]
    listados = set().union(*[e["drones"] for e in est.values() if e["ativo"] and e["drones"]])
    return {"operadores": len(op), "operadores_pj": sum(1 for e in op if e["pj"]),
            "operadores_pf": sum(1 for e in op if not e["pj"]), "drones_listados": len(listados)}


# --------------------------------------------------------------- privacidade
PADROES = [("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")), ("telefone/documento", re.compile(r"\d{8,}")),
           ("CPF mascarado", re.compile(r"\*{3}")), ("telefone", re.compile(r"\(\d{2}\)\s*\d"))]


def strings(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from strings(v)
    elif isinstance(o, str):
        yield o


def varre_privacidade(obj, pessoais):
    """Lista de problemas; vazia = pode publicar."""
    probs = []
    for s in strings(obj):
        for nome, pad in PADROES:
            if nome == "telefone/documento" and s.startswith("http"):
                continue  # número dentro de URL de fonte oficial
            if pad.search(s):
                probs.append(f"{nome} em {s[:60]!r}")
        if s.upper().strip() in pessoais:
            probs.append(f"valor pessoal do arquivo do MAPA: {s[:20]!r}...")
    return probs


# --------------------------------------------------------------- série (cache local)
def serie_anac(base_atual, agro_atual, pf_atual):
    """Frota agrícola em cada snapshot guardado do SISANT. Diferença entre bases é SALDO."""
    cache = json.loads(CACHE_SERIE.read_text(encoding="utf-8")) if CACHE_SERIE.exists() else {}
    anac = cache.setdefault("anac", {})
    for p in sorted(SNAP.glob("SISANT_*.csv")):
        d = p.stem.split("_")[1]
        if d >= base_atual.isoformat():
            continue
        chave = f"{d}|{p.stat().st_size}|{VERSAO_METODO_AGRO}"
        if anac.get(d, {}).get("chave") != chave:
            _, vig = le_sisant(p, dt.date.fromisoformat(d))
            ag = [r for r in vig if classe_agro(r)]
            anac[d] = {"chave": chave, "agro": len(ag), "agro_pf": sum(1 for r in ag if not eh_cnpj(r))}
            print(f"  serie ANAC: {d} -> {len(ag)}")
    CACHE_SERIE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    out = [{"base": d, "drones_agricolas": v["agro"], "em_cpf": v["agro_pf"]} for d, v in sorted(anac.items())
           if d < base_atual.isoformat() and (SNAP / f"SISANT_{d}.csv").exists()]
    out.append({"base": base_atual.isoformat(), "drones_agricolas": agro_atual, "em_cpf": pf_atual})
    return out


def serie_mapa(snap_atual, resumo_atual):
    cache = json.loads(CACHE_SERIE.read_text(encoding="utf-8")) if CACHE_SERIE.exists() else {}
    mp = cache.setdefault("mapa", {})
    for p in sorted(SNAP_MAPA.glob("sipeagro_registro_*.csv")):
        d = p.stem.rsplit("_", 1)[1]
        chave = f"{d}|{p.stat().st_size}"
        if p == snap_atual:
            mp[d] = dict(resumo_atual, chave=chave)
        elif mp.get(d, {}).get("chave") != chave:
            _, est, _ = le_mapa(p)
            mp[d] = dict(resumo_mapa(est), chave=chave)
    CACHE_SERIE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    out = []
    for d, v in sorted(mp.items()):
        if not (SNAP_MAPA / f"sipeagro_registro_{d}.csv").exists():
            continue
        carimbo = SNAP_MAPA / f"sipeagro_registro_{d}.json"
        lm = json.loads(carimbo.read_text(encoding="utf-8")).get("last_modified") if carimbo.exists() else None
        out.append({"baixado_em": d, "arquivo_mapa_de": lm, **{k: v[k] for k in
                    ("operadores", "operadores_pj", "operadores_pf", "drones_listados")}})
    return out


# ====================================================================== principal
def main():
    if not SISANT.exists():
        sai(2, f"falta {SISANT.name}")
    data_base = data_cabecalho(SISANT)
    if not data_base:
        sai(2, "não li a data do cabeçalho do SISANT")
    if len(sys.argv) > 1:
        mapa_csv = Path(sys.argv[1])
    else:
        snaps = sorted(SNAP_MAPA.glob("sipeagro_registro_*.csv"))
        if not snaps:
            sai(2, "nenhum snapshot do MAPA em snapshots/mapa/")
        mapa_csv = snaps[-1]
    carimbo_arq = mapa_csv.with_suffix(".json")
    carimbo = json.loads(carimbo_arq.read_text(encoding="utf-8")) if carimbo_arq.exists() else {}
    print(f"ANAC {data_base} | MAPA {mapa_csv.name} (arquivo de {carimbo.get('last_modified')})")

    # ---------------------------------------------------------------- ANAC
    todos, vig = le_sisant(SISANT, data_base)
    agro = []
    for r in vig:
        c = classe_agro(r)
        if c:
            r = dict(r)
            r["_classe"] = c
            agro.append(r)
    pj = [r for r in agro if eh_cnpj(r)]
    pf = [r for r in agro if not eh_cnpj(r)]

    receita = json.loads((REF / "cnpj_sede_receita_2026-10.json").read_text(encoding="utf-8"))["cnpj"]
    cache_uf = json.loads((HERE / "cnpj-uf-cache.json").read_text(encoding="utf-8"))

    def sede(c):
        v = receita.get(c)
        if v and v[0]:
            return v[0], (v[1] or None)
        v = cache_uf.get(c) or {}
        if v.get("uf"):
            return v["uf"], cod_mun(v["uf"], v.get("municipio", ""))
        return None, None

    agro_uf = collections.Counter()
    cnpjs_uf = collections.defaultdict(set)
    agro_mun_cnpjs = collections.defaultdict(set)
    cnpjs_agro = collections.Counter()
    pj_sem_uf = 0
    for r in pj:
        c = dig(r["CPF_CNPJ"])
        cnpjs_agro[c] += 1
        uf, cm = sede(c)
        r["_uf"] = uf
        if not uf:
            pj_sem_uf += 1
            continue
        agro_uf[uf] += 1
        cnpjs_uf[uf].add(c)
        if cm:
            agro_mun_cnpjs[cm].add(c)

    pesos = collections.Counter("ate_2kg" if peso(r) < 2 else "de_2_a_25kg" if peso(r) < 25 else "25kg_ou_mais" for r in agro)
    marcas = collections.Counter(normaliza_marca(sem_acento((r["FABRICANTE"] or "").strip().upper())) for r in agro)
    familias = collections.Counter(familia_modelo(normaliza_modelo(r["MODELO"])) for r in agro)

    # ---------------------------------------------------------------- MAPA
    _, est, pessoais = le_mapa(mapa_csv)
    op_todos = {k: e for k, e in est.items() if e["ativo"] and e["drones"]}          # inclui escolas
    op = {k: e for k, e in op_todos.items() if not e["so_ensino"]}
    drones_mapa = set().union(*[e["drones"] for e in op_todos.values()]) if op_todos else set()
    drones_sis = {a for a in drones_mapa if SIS_PAT.match(a)}
    repetidos = collections.Counter(a for e in op_todos.values() for a in e["drones"])
    tam = sorted(len(e["drones"]) for e in op.values())
    mapa_num = {num9(a) for a in drones_sis}

    vig_num = {num9(norm_cod(r["CODIGO_AERONAVE"])) for r in vig} - {None}
    todos_num = {num9(norm_cod(r["CODIGO_AERONAVE"])) for r in todos} - {None}
    cod_todos = {norm_cod(r["CODIGO_AERONAVE"]) for r in todos}
    classes_op = collections.Counter()
    for e in op.values():
        validos = [a for a in e["drones"] if SIS_PAT.match(a)]
        if any(a[2:] in vig_num for a in validos):
            classes_op["com_drone_vigente_na_anac"] += 1
        elif validos:
            classes_op["so_numeros_nao_vigentes"] += 1
        else:
            classes_op["so_codigo_sem_formato"] += 1

    # conferência do dono: drone do MAPA vigente na ANAC, os dois lados empresa
    dono = {num9(norm_cod(r["CODIGO_AERONAVE"])): dig(r["CPF_CNPJ"]) for r in vig if eh_cnpj(r)}
    mesmo = outro = 0
    for e in op.values():
        if not e["pj"]:
            continue
        for a in e["drones"]:
            n = num9(a)
            if n and n in dono:
                if dono[n][:8] == e["cnpj"][:8]:
                    mesmo += 1
                else:
                    outro += 1

    # ---------------------------------------------------------------- cruzamento
    no_mapa = [r for r in agro if num9(norm_cod(r["CODIGO_AERONAVE"])) in mapa_num]
    raiz_mapa = {e["cnpj"][:8] for e in est.values() if e["ativo"] and e["pj"] and e["cnpj"]}
    pj_no_mapa_uf = collections.Counter(r["_uf"] for r in pj if r.get("_uf") and num9(norm_cod(r["CODIGO_AERONAVE"])) in mapa_num)

    # ---------------------------------------------------------------- PAM e tabelas
    pam_br = le_pam("N1")["1"]
    pam_uf = {SIG[k]: v for k, v in le_pam("N3").items()}
    pam_mun = {int(k): v for k, v in le_pam("N6").items()}

    op_uf = collections.Counter(e["uf"] for e in op.values())
    dr_uf = collections.Counter()
    for e in op.values():
        dr_uf[e["uf"]] += len(e["drones"])
    op_mun = collections.Counter(e["mun"] for e in op.values() if e["mun"])
    dr_mun = collections.Counter()
    for e in op.values():
        if e["mun"]:
            dr_mun[e["mun"]] += len(e["drones"])

    tab_uf = []
    for uf in sorted(pam_uf, key=lambda u: -pam_uf[u]):
        a, dpj, om, dm = pam_uf[uf], agro_uf.get(uf, 0), op_uf.get(uf, 0), dr_uf.get(uf, 0)
        tab_uf.append({
            "uf": uf, "area_plantada_ha": a,
            "drones_agricolas_anac_cnpj": dpj, "cnpjs_agricolas_anac": len(cnpjs_uf.get(uf, ())),
            "drones_cnpj_com_numero_no_mapa": pj_no_mapa_uf.get(uf, 0),
            "pct_cnpj_com_numero_no_mapa": round(100 * pj_no_mapa_uf.get(uf, 0) / dpj, 1) if dpj else None,
            "operadores_mapa": faixa(om), "drones_listados_mapa": dm if om == 0 or om >= CORTE_MIN else None,
            "ha_por_drone_mapa": round(a / dm) if dm and om >= CORTE_MIN else None,
            "ha_por_drone_anac_cnpj": round(a / dpj) if dpj else None,
        })

    linhas_mun = []
    for cm, a in pam_mun.items():
        linhas_mun.append((cm, a, op_mun.get(cm, 0), dr_mun.get(cm, 0), len(agro_mun_cnpjs.get(cm, ()))))
    linhas_mun.sort(key=lambda x: -x[1])
    com_area = [l for l in linhas_mun if l[1] > 0]

    def nome(cm):
        n, uf = NOME_DE_COD.get(cm, (str(cm), UF_DE_COD.get(cm, "")))
        return n, uf

    sem_op_uf = collections.defaultdict(lambda: [0, 0, 0])   # municípios, sem operador, área sem operador
    for cm, a, om, _, _ in linhas_mun:
        uf = UF_DE_COD.get(cm)
        if not uf:
            continue
        sem_op_uf[uf][0] += 1
        if not om:
            sem_op_uf[uf][1] += 1
            sem_op_uf[uf][2] += a
    uf_mais = max(sem_op_uf, key=lambda u: sem_op_uf[u][2])
    maiores_sem = []
    for cm, a, om, _, ncn in com_area:
        if om:
            continue
        n, uf = nome(cm)
        maiores_sem.append({"municipio": n, "uf": uf, "area_plantada_ha": a, "empresas_drone_agricola_anac_sede": faixa(ncn)})
        if len(maiores_sem) == 15:
            break
    polos = []
    for cm, om in op_mun.most_common():
        if om < CORTE_MIN or len(polos) == 10:
            break
        n, uf = nome(cm)
        polos.append({"municipio": n, "uf": uf, "operadores_mapa": om, "drones_listados_mapa": dr_mun[cm],
                      "area_plantada_ha": pam_mun.get(cm, 0)})
    densos = [(pam_mun.get(cm, 0), cm, om) for cm, om in op_mun.items() if om >= 10]
    exemplo = None
    if densos:
        a, cm, om = min(densos)
        n, uf = nome(cm)
        exemplo = {"municipio": n, "uf": uf, "operadores_mapa": om, "area_plantada_ha": a}

    T = len(agro)
    res = {
        "meta": {
            "titulo": "Seção Agro: drones agrícolas na ANAC x registro de aviação agrícola do MAPA x área plantada do IBGE",
            "base_anac": data_base.isoformat(),
            "mapa_arquivo_de": carimbo.get("last_modified"),
            "mapa_baixado_em": (carimbo.get("baixado_em") or "")[:10] or None,
            "pam_ano": PAM_ANO, "pam_atualizado_ibge": PAM_ATUALIZADO,
            "processado_em": dt.datetime.now().replace(microsecond=0).isoformat(),
            "versao_metodo_agro": VERSAO_METODO_AGRO,
            "fontes": {"anac": "https://sistemas.anac.gov.br/dadosabertos/Aeronaves/drones%20cadastrados/SISANT.csv",
                       "mapa": URL_MAPA, "ibge_pam": URL_PAM, "portaria_mapa_298_2021": URL_PORTARIA},
            "privacidade": f"Só agregados. O arquivo do MAPA traz e-mail, telefone e nome de pessoa física; nada disso "
                           f"é publicado. Contagem por município entre 1 e {CORTE_MIN - 1} aparece como faixa.",
            "corte_minimo_municipio": CORTE_MIN,
        },
        "frota_anac": {
            "vigentes": len(vig), "drones_agricolas": T,
            "pelo_ramo": sum(1 for r in agro if r["_classe"] == "ramo"),
            "pelo_modelo": sum(1 for r in agro if r["_classe"] == "modelo"),
            "em_cpf": len(pf), "em_cnpj": len(pj), "cnpjs": len(cnpjs_agro), "cnpj_sem_uf": pj_sem_uf,
            "peso": dict(pesos), "ramo_ate_2kg": sum(1 for r in agro if r["_classe"] == "ramo" and peso(r) < 2),
            "marcas": [{"marca": m, "drones": n} for m, n in marcas.most_common(6)],
            "agras": sum(n for k, n in familias.items() if k.startswith("AGRAS")),
        },
        "mapa": {
            "estabelecimentos": len(est), "ativos": sum(1 for e in est.values() if e["ativo"]),
            "cancelados": sum(1 for e in est.values() if not e["ativo"]),
            "ativos_so_aviao": sum(1 for e in est.values() if e["ativo"] and e["avioes"] and not e["drones"]),
            "operadores_drone": len(op), "operadores_pj": sum(1 for e in op.values() if e["pj"]),
            "operadores_pf": sum(1 for e in op.values() if not e["pj"]),
            "escolas_so_ensino": len(op_todos) - len(op),
            "operadores_drone_e_aviao": sum(1 for e in op.values() if e["avioes"]),
            "drones_listados": len(drones_mapa), "drones_codigo_formato_sisant": len(drones_sis),
            "drones_codigo_sem_formato": len(drones_mapa) - len(drones_sis),
            "drones_em_mais_de_um_registro": sum(1 for v in repetidos.values() if v > 1),
            "drones_por_operador_mediana": tam[len(tam) // 2] if tam else 0,
            "drones_por_operador": dict(collections.Counter("1" if n == 1 else "2 a 3" if n <= 3 else "4 a 9" if n <= 9 else "10 ou mais" for n in tam)),
            "operadores_por_situacao_na_anac": dict(classes_op),
            "numeros_fora_do_sisant_atual": len(mapa_num - todos_num),
            "soma_drones_por_uf": sum(dr_uf.values()),
        },
        "cruzamento": {
            "drones_agricolas_com_numero_no_mapa": len(no_mapa),
            "em_cnpj_com_numero_no_mapa": sum(1 for r in no_mapa if eh_cnpj(r)),
            "em_cpf_com_numero_no_mapa": sum(1 for r in no_mapa if not eh_cnpj(r)),
            "pelo_ramo_no_mapa": sum(1 for r in no_mapa if r["_classe"] == "ramo"),
            "pelo_modelo_no_mapa": sum(1 for r in no_mapa if r["_classe"] == "modelo"),
            "cnpjs_agricolas_com_registro_no_mapa_raiz": sum(1 for c in cnpjs_agro if c[:8] in raiz_mapa),
            "numeros_mapa_achados_codigo_identico": sum(1 for a in drones_sis if a in cod_todos),
            "numeros_mapa_achados_pelos_9_digitos": len(mapa_num & todos_num),
            "dono_mesma_raiz_cnpj": mesmo, "dono_outro_cnpj": outro,
        },
        "uf": tab_uf,
        "municipios": {
            "area_brasil_ha": pam_br,
            "municipios_com_operador_mapa": sum(1 for l in linhas_mun if l[2]),
            "top100_sem_operador_mapa": sum(1 for l in com_area[:100] if not l[2]),
            "top300_sem_operador_mapa": sum(1 for l in com_area[:300] if not l[2]),
            "area_top100_ha": sum(l[1] for l in com_area[:100]),
            "area_em_municipios_sem_operador_ha": sum(l[1] for l in linhas_mun if not l[2]),
            "uf_destaque_sem_operador": {"uf": uf_mais, "municipios": sem_op_uf[uf_mais][0],
                                         "sem_operador": sem_op_uf[uf_mais][1], "area_sem_operador_ha": sem_op_uf[uf_mais][2]},
            "sem_operador_por_uf": {u: {"municipios": v[0], "sem_operador": v[1], "area_sem_operador_ha": v[2]}
                                    for u, v in sorted(sem_op_uf.items())},
            "maiores_sem_operador_mapa": maiores_sem,
            "polos_operadores_mapa": polos,
            "exemplo_sede": exemplo,
            "operadores_com_municipio_ibge": sum(1 for e in op.values() if e["mun"]),
        },
    }
    res["series"] = {"anac": serie_anac(data_base, T, len(pf)),
                     "mapa": serie_mapa(mapa_csv, resumo_mapa(est))}

    # ---------------------------------------------------------------- checagens
    m, x, f = res["mapa"], res["cruzamento"], res["frota_anac"]
    ant = json.loads(SAIDA.read_text(encoding="utf-8")) if SAIDA.exists() else None
    checagens = [
        ("CPF + CNPJ = frota agrícola", f["em_cpf"] + f["em_cnpj"] == T),
        ("ramo + modelo = frota agrícola", f["pelo_ramo"] + f["pelo_modelo"] == T),
        ("faixas de peso somam a frota", sum(pesos.values()) == T),
        ("no MAPA: CPF + CNPJ = total", x["em_cpf_com_numero_no_mapa"] + x["em_cnpj_com_numero_no_mapa"] == x["drones_agricolas_com_numero_no_mapa"]),
        ("CNPJ por UF + sem UF = drones em CNPJ", sum(agro_uf.values()) + pj_sem_uf == len(pj)),
        ("operadores PJ + PF = operadores", m["operadores_pj"] + m["operadores_pf"] == m["operadores_drone"]),
        ("situações na ANAC somam os operadores", sum(classes_op.values()) == m["operadores_drone"]),
        ("arquivo do MAPA com volume plausível (500+ operadores)", m["operadores_drone"] >= 500),
        ("PAM: soma das UFs = Brasil", sum(pam_uf.values()) == pam_br),
    ]
    if ant and ant.get("frota_anac", {}).get("drones_agricolas"):
        t0 = ant["frota_anac"]["drones_agricolas"]
        checagens.append((f"frota agrícola dentro de 15% da edição anterior ({t0})", abs(T - t0) / t0 <= 0.15))
        o0 = ant.get("mapa", {}).get("operadores_drone")
        if o0:
            checagens.append((f"operadores do MAPA dentro de 30% da edição anterior ({o0})", abs(m["operadores_drone"] - o0) / o0 <= 0.30))
    res["meta"]["checagens"] = [n for n, _ in checagens]
    falhas = [n for n, ok in checagens if not ok]
    probs = varre_privacidade(res, pessoais)
    if probs:
        falhas.append("PRIVACIDADE: " + "; ".join(probs[:5]))
    if falhas:
        sai(3, "ABORTADO, nada gravado:\n  - " + "\n  - ".join(falhas))

    txt = json.dumps(res, ensure_ascii=False, indent=1)
    SAIDA.write_text(txt, encoding="utf-8")
    (HERE / f"obs-agro-{data_base.isoformat()}.json").write_text(txt, encoding="utf-8")
    print(f"checagens: {len(checagens)} OK; privacidade: OK")
    print(f"frota agrícola ANAC {T:,} | com número no MAPA {x['drones_agricolas_com_numero_no_mapa']:,} "
          f"({100 * x['drones_agricolas_com_numero_no_mapa'] / T:.1f}%) | CNPJ "
          f"{100 * x['em_cnpj_com_numero_no_mapa'] / len(pj):.1f}% | CPF {100 * x['em_cpf_com_numero_no_mapa'] / len(pf):.1f}%")
    print(f"MAPA: {m['operadores_drone']:,} operadores, {m['drones_listados']:,} drones listados; situação na ANAC {dict(classes_op)}")
    print(f"municípios: top100 sem operador {res['municipios']['top100_sem_operador_mapa']}, top300 {res['municipios']['top300_sem_operador_mapa']}")
    print("gravado: obs-agro.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
