#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara duas bases SISANT guardadas em snapshots/ pelo CODIGO_AERONAVE.

Separa o que a diferenca de totais esconde: primeiro cadastro (codigo que nao existia),
renovacao (mesmo codigo, validade adiantada), saida (codigo que sumiu: vencido, cancelado
ou transferido) e o saldo liquido. Sem isso, "X mil novos" e so um saldo.

Uso:  python obs_diff.py                     -> compara as duas bases mais recentes
      python obs_diff.py 2026-08-04 2026-09-20
Grava obs-diff.json (lido pelo obs_build.py) e imprime o resumo.
"""
import collections
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).parent
SNAP = HERE / "snapshots"
SAIDA = HERE / "obs-diff.json"


def le(caminho):
    """{codigo: (validade, peso_kg, numero_serie, doc)}; linhas = total de linhas do arquivo."""
    regs, linhas = {}, 0
    with open(caminho, encoding="utf-8-sig", errors="replace") as f:
        primeira = f.readline()
        if "CODIGO_AERONAVE" in primeira:  # snapshot sem linha de carimbo
            f.seek(0)
        for r in csv.DictReader(f, delimiter=";"):
            linhas += 1
            cod = (r.get("CODIGO_AERONAVE") or "").strip().upper()
            if not cod:
                continue
            val = (r.get("DATA_VALIDADE") or "").strip()
            try:
                p = float((r.get("PESO_MAXIMO_DECOLAGEM_KG") or "0").replace(",", "."))
            except ValueError:
                p = 0.0
            regs[cod] = (val, p, (r.get("NUMERO_SERIE") or "").strip().upper(),
                         (r.get("CPF_CNPJ") or "").strip())
    return regs, linhas


def faixa(p):
    return "Ate 250 g" if p < 0.25 else "250 g a 2 kg" if p < 2 else "2 a 25 kg" if p < 25 else "Acima de 25 kg"


def main():
    bases = sorted(SNAP.glob("SISANT_*.csv"))
    if len(sys.argv) == 3:
        a, b = (SNAP / f"SISANT_{sys.argv[1]}.csv", SNAP / f"SISANT_{sys.argv[2]}.csv")
    elif len(bases) >= 2:
        a, b = bases[-2], bases[-1]
    else:
        print("preciso de duas bases em snapshots/; nada a comparar")
        return 0
    da, db = a.stem.split("_")[1], b.stem.split("_")[1]
    dias = (dt.date.fromisoformat(db) - dt.date.fromisoformat(da)).days
    (A, linhas_a), (B, linhas_b) = le(a), le(b)
    ca, cb = set(A), set(B)
    novos = cb - ca
    sairam = ca - cb
    comuns = ca & cb
    renovados = {c for c in comuns if A[c][0] != B[c][0]}
    # das saidas, quantas ja estavam vencidas ou vencendo ate a data da base nova
    lim = dt.date.fromisoformat(db)
    saida_vencida = 0
    for c in sairam:
        try:
            if dt.datetime.strptime(A[c][0], "%d/%m/%Y").date() <= lim:
                saida_vencida += 1
        except ValueError:
            pass
    # codigo novo nem sempre e drone novo: o mesmo numero de serie pode sair com um
    # codigo e voltar com outro (troca de tipo de uso PR<->PP, ou transferencia de dono)
    serie_saiu = collections.defaultdict(list)
    for c in sairam:
        if len(A[c][2]) >= 6:
            serie_saiu[A[c][2]].append(c)
    recad = [c for c in novos if B[c][2] in serie_saiu]
    recad_mesmo_dono = sum(1 for c in recad if any(A[x][3] == B[c][3] for x in serie_saiu[B[c][2]]))
    peso_novos = collections.Counter(faixa(B[c][1]) for c in novos)
    pf_novos = sum(1 for c in novos if not B[c][3].upper().startswith("CNPJ"))
    saida = {
        "base_anterior": da, "base_atual": db, "dias": dias,
        "linhas_anterior": linhas_a, "linhas_atual": linhas_b,
        "codigos_anterior": len(A), "codigos_atual": len(B),
        "saldo": len(B) - len(A),
        "codigos_novos": len(novos),
        "recadastros_mesma_serie": len(recad),
        "recadastros_mesmo_dono": recad_mesmo_dono,
        "aeronaves_novas": len(novos) - len(recad),
        "renovacoes": len(renovados),
        "saidas": len(sairam),
        "saidas_ja_vencidas": saida_vencida,
        "saidas_antes_do_prazo": len(sairam) - saida_vencida,
        "novos_por_dia": round(len(novos) / dias, 1) if dias else None,
        "renovacoes_por_dia": round(len(renovados) / dias, 1) if dias else None,
        "novos_pf": pf_novos,
        "novos_por_peso": dict(peso_novos),
        "metodo": "Comparacao pelo CODIGO_AERONAVE entre dois snapshots do arquivo SISANT. "
                  "Codigo novo = ausente na base anterior. Renovacao = mesmo codigo com "
                  "DATA_VALIDADE diferente. Saida = codigo presente antes e ausente agora (vencido, "
                  "cancelado ou transferido; o arquivo nao diz qual). Recadastro = codigo novo cujo "
                  "NUMERO_SERIE e o mesmo de um codigo que saiu. Codigos repetidos no arquivo contam uma vez.",
    }
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{da} -> {db} ({dias} dias): {len(A)} -> {len(B)} codigos  saldo {saida['saldo']:+}"
          f"  (linhas {linhas_a} -> {linhas_b})")
    print(f"  codigos novos       {len(novos)}  ({saida['novos_por_dia']}/dia; PF {pf_novos}; "
          f"recadastros de serie que saiu: {len(recad)}, {recad_mesmo_dono} com o mesmo dono)")
    print(f"  renovacoes          {len(renovados)}  ({saida['renovacoes_por_dia']}/dia)")
    print(f"  saidas              {len(sairam)}  (ja vencidas ate {db}: {saida_vencida}; antes do prazo: {len(sairam) - saida_vencida})")
    print(f"  novos por peso      {dict(peso_novos)}")
    print(f"gravado: {SAIDA.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
