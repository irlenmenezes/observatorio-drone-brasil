#!/usr/bin/env python3
"""
Consulta a UF de cada CNPJ operador de drone na base pública da Receita.

Retomável: grava o cache a cada lote, então pode ser interrompido e religado.
Usa minhareceita.org como principal e BrasilAPI como reserva.

Uso:  python consulta_uf.py [quantos]     (padrão: todos)
"""
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = Path(__file__).parent
ENTRADA = BASE / "cnpjs-frota.json"
CACHE = BASE / "cnpj-uf-cache.json"
LIMITE = int(sys.argv[1]) if len(sys.argv) > 1 else None

cnpjs = json.loads(ENTRADA.read_text(encoding="utf-8"))
if LIMITE:
    cnpjs = cnpjs[:LIMITE]

cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
lock = threading.Lock()
pendentes = [c for c in cnpjs if c["cnpj"] not in cache]
print(f"alvo: {len(cnpjs)} CNPJs | já no cache: {len(cnpjs) - len(pendentes)} | a consultar: {len(pendentes)}")

FONTES = [
    ("minhareceita", "https://minhareceita.org/{}", lambda d: (d.get("uf"), d.get("municipio"), d.get("cnae_fiscal_descricao"))),
    ("brasilapi", "https://brasilapi.com.br/api/cnpj/v1/{}", lambda d: (d.get("uf"), d.get("municipio"), d.get("cnae_fiscal_descricao"))),
]


def busca(item):
    cnpj = item["cnpj"]
    for nome, url, extrai in FONTES:
        for tentativa in range(3):
            try:
                req = Request(url.format(cnpj), headers={"User-Agent": "pesquisa-editorial/1.0"})
                with urlopen(req, timeout=25) as r:
                    dados = json.loads(r.read().decode("utf-8"))
                uf, municipio, cnae = extrai(dados)
                if uf:
                    return cnpj, {"uf": uf, "municipio": municipio, "cnae": cnae, "fonte": nome}
                break
            except HTTPError as e:
                if e.code in (429, 503):          # excesso de requisições
                    time.sleep(2 + tentativa * 3)
                    continue
                if e.code == 404:
                    return cnpj, {"uf": None, "erro": "404"}
                break
            except (URLError, TimeoutError, json.JSONDecodeError):
                time.sleep(1 + tentativa)
    return cnpj, {"uf": None, "erro": "sem resposta"}


t0 = time.time()
feitos = 0
with ThreadPoolExecutor(max_workers=6) as pool:
    for cnpj, resultado in pool.map(busca, pendentes):
        with lock:
            cache[cnpj] = resultado
            feitos += 1
            if feitos % 25 == 0:
                CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                taxa = feitos / (time.time() - t0)
                falta = (len(pendentes) - feitos) / taxa / 60 if taxa else 0
                ok = sum(1 for v in cache.values() if v.get("uf"))
                print(f"   {feitos}/{len(pendentes)}  {taxa:.1f}/s  faltam ~{falta:.0f} min  (com UF: {ok})", flush=True)

CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
ok = sum(1 for v in cache.values() if v.get("uf"))
print(f"\nfim: {len(cache)} no cache, {ok} com UF, {time.time()-t0:.0f}s")
