#!/usr/bin/env python3
"""
Rota CNPJ: descobre em que estado está a frota profissional de drone.

O SISANT não traz UF nem município (só operador, CPF/CNPJ, uso, fabricante,
modelo, peso, ramo e validade). Como o CPF vem mascarado, o único caminho é
pela pessoa jurídica: agregamos a frota por CNPJ e consultamos a UF de cada um
na base pública da Receita.

Etapa 1 (este passo): agrega e mostra a curva de concentração, para decidir
quantos CNPJs precisam ser consultados para cobrir a maior parte da frota PJ.
"""
import csv
import collections
import datetime
import json
from pathlib import Path

BASE = Path(__file__).parent
CSV = BASE / "SISANT_new.csv"  # (20/09/2026) mesma origem do obs_apura.py
HOJE = datetime.date(2026, 8, 2)

frota = collections.Counter()      # cnpj -> nº de aeronaves
nome = {}                          # cnpj -> razão social (a do maior registro)
ramos = collections.defaultdict(collections.Counter)
uso_pj = collections.Counter()
total = pj = pf = 0

with open(CSV, encoding="utf-8-sig") as f:
    f.readline()
    for row in csv.DictReader(f, delimiter=";"):
        total += 1
        doc = (row["CPF_CNPJ"] or "").strip()
        if not doc.upper().startswith("CNPJ"):
            pf += 1
            continue
        pj += 1
        digitos = "".join(c for c in doc if c.isdigit())
        if len(digitos) != 14:
            continue
        frota[digitos] += 1
        nome.setdefault(digitos, (row["OPERADOR"] or "").strip())
        ramos[digitos][(row["RAMO_ATIVIDADE"] or "").strip()] += 1
        uso_pj[(row["TIPO_USO"] or "").strip()] += 1

print(f"registros: {total}   PJ: {pj} ({pj/total:.1%})   PF: {pf}")
print(f"CNPJs distintos: {len(frota)}")
print()

ordenado = frota.most_common()
acum = 0
marcos = [50, 100, 250, 500, 1000, 2000, 4000, len(ordenado)]
print("curva de concentração da frota PJ:")
i = 0
for m in marcos:
    while i < m and i < len(ordenado):
        acum += ordenado[i][1]
        i += 1
    print(f"   top {m:>6} CNPJs = {acum:>6} aeronaves ({acum/pj:.1%} da frota PJ)")

print()
print("os 15 maiores operadores:")
for cnpj, n in ordenado[:15]:
    ramo = ramos[cnpj].most_common(1)[0][0][:38]
    print(f"   {n:>5}  {nome[cnpj][:44]:<44} {ramo}")

destino = BASE / "cnpjs-frota.json"
destino.write_text(
    json.dumps(
        [
            {"cnpj": c, "frota": n, "nome": nome[c], "ramo": ramos[c].most_common(1)[0][0]}
            for c, n in ordenado
        ],
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
print(f"\ngravado: {destino.name} ({len(ordenado)} CNPJs)")
