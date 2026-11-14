# -*- coding: utf-8 -*-
"""Baixa o CSV de registro de aviação agrícola do MAPA (SIPEAGRO, dados abertos) e guarda um
snapshot datado em snapshots/mapa/ (14/11/2026).

Por que snapshot: o arquivo do MAPA não tem data por linha. A única forma de ter série do lado
do MAPA é guardar uma cópia a cada execução da rotina, como já se faz com o SISANT.

Por que Playwright: o servidor do MAPA derruba conexão de curl e de urllib. O Chrome headless
comum (Chrome instalado, user-agent padrão, sem disfarce nenhum) baixa normalmente.

🚨 PRIVACIDADE: o CSV traz e-mail, telefone, nome de pessoa física e de responsável técnico.
Ele fica SÓ em snapshots/mapa/, que não sobe para o servidor nem para o repositório público.
Para a página e para o JSON vão apenas agregados (obs_agro.py).

Saída: snapshots/mapa/sipeagro_registro_AAAA-MM-DD.csv + .json (Last-Modified, tamanho, sha256).
Código de saída 0 = ok; outro valor = falhou (a rotina segue sem a seção Agro).
Uso:  python obs_mapa_baixa.py
"""
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).parent
DEST = HERE / "snapshots" / "mapa"
URL = ("https://dados.agricultura.gov.br/dataset/52a01565-72d6-410e-b21b-64035831a7be/resource/"
       "fac50de6-d4c4-4b47-bac9-5b144de448c9/download/sipeagroaviacaoagricolaregistro.csv")
# colunas que o obs_agro.py usa: se o MAPA mudar o layout, melhor falhar aqui do que apurar errado
COLUNAS = {"UNIDADE_DA_FEDERACAO", "MUNICIPIO", "NUMERO_REGISTRO_ESTABELECIMENTO",
           "STATUS_REGISTRO_ESTABELECIMENTO", "CPF_CNPJ", "ATIVIDADE", "ESPECIE", "NUMERO_REGISTRO_AERONAVE"}
MIN_BYTES = 1_000_000
MIN_LINHAS = 5_000


def baixa():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        try:
            ctx = b.new_context()
            resp = ctx.request.get(URL, timeout=180_000)
            return resp.status, resp.body(), resp.headers.get("last-modified")
        finally:
            b.close()


def valida(corpo):
    if len(corpo) < MIN_BYTES:
        return f"arquivo pequeno demais ({len(corpo)} bytes)"
    texto = corpo.decode("utf-8-sig", errors="replace")
    cab = set(texto.split("\n", 1)[0].strip().split(";"))
    faltam = COLUNAS - cab
    if faltam:
        return f"layout mudou, faltam colunas: {sorted(faltam)}"
    linhas = texto.count("\n")
    if linhas < MIN_LINHAS:
        return f"poucas linhas ({linhas})"
    return None


def main():
    erro = None
    for tentativa in (1, 2):
        try:
            status, corpo, lm = baixa()
            if status != 200:
                erro = f"HTTP {status}"
            else:
                erro = valida(corpo)
            if not erro:
                break
        except Exception as e:  # noqa
            erro = f"{type(e).__name__}: {e}"
        print(f"tentativa {tentativa} falhou: {erro}")
        time.sleep(20)
    if erro:
        print(f"FALHOU: {erro}")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    hoje = dt.date.today().isoformat()
    alvo = DEST / f"sipeagro_registro_{hoje}.csv"
    tmp = alvo.with_suffix(".tmp")
    tmp.write_bytes(corpo)
    tmp.replace(alvo)
    lm_iso = None
    if lm:
        try:
            lm_iso = dt.datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT").date().isoformat()
        except ValueError:
            lm_iso = lm
    carimbo = {"arquivo": alvo.name, "url": URL,
               "baixado_em": dt.datetime.now().replace(microsecond=0).isoformat(),
               "last_modified": lm_iso, "bytes": len(corpo),
               "sha256": hashlib.sha256(corpo).hexdigest()}
    alvo.with_suffix(".json").write_text(json.dumps(carimbo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"snapshot MAPA: {alvo.name} ({len(corpo):,} bytes, Last-Modified {lm_iso})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
