# -*- coding: utf-8 -*-
"""Rotina mensal do Observatório do Drone (20/09/2026).

Baixa a base SISANT da ANAC, e SÓ SE a data da base for mais nova que a publicada:
guarda snapshot, resolve UF dos CNPJs novos, apura, gera a página, publica no servidor,
purga o cache e avisa o IndexNow. Grava tudo em obs_rotina.log e um resumo em obs_rotina_ultimo.txt.

Uso manual:  python obs_rotina.py            (respeita a checagem de data)
             python obs_rotina.py --forcar   (reprocessa mesmo sem base nova)
Agendada no Windows (Task Scheduler): tarefa "Observatorio Drone mensal", dia 1, 09:00, roda se perdeu o horário.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).parent
LOG = HERE / "obs_rotina.log"
RESUMO = HERE / "obs_rotina_ultimo.txt"
CSV = HERE / "SISANT_new.csv"
SNAP = HERE / "snapshots"
URL_CSV = "https://sistemas.anac.gov.br/dadosabertos/Aeronaves/drones%20cadastrados/SISANT.csv"
URL_PAGINA = "https://irlenmenezes.com.br/observatorio-drone-brasil/"
FORCAR = "--forcar" in sys.argv

# Onde a pagina e gerada: a mesma regra do obs_build.py
_padrao = HERE.parent / "observatorio-drone"
SAIDA = Path(os.environ.get("OBS_DESTINO") or (_padrao if _padrao.exists() else HERE / "site"))


def le_env(caminho):
    """CHAVE=valor por linha, sem depender de pacote. Linhas com # sao comentario."""
    env = {}
    if caminho.exists():
        for ln in caminho.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# Credenciais e caminho do servidor ficam FORA do codigo, em obs_rotina.env (ignorado pelo git):
#   SSH_HOST=usuario@servidor   SSH_PORT=22   SSH_KEY=~/.ssh/id_ed25519
#   REMOTO=caminho/no/servidor/observatorio-drone-brasil   INDEXNOW_KEY=...
# Sem esse arquivo a rotina apura e gera a pagina, mas nao publica.
ENV = le_env(HERE / "obs_rotina.env")
SSH = ENV.get("SSH_BIN", r"C:\Program Files\Git\usr\bin\ssh.exe")
TAR = ENV.get("TAR_BIN", r"C:\Program Files\Git\usr\bin\tar.exe")
KEY = str(Path(ENV.get("SSH_KEY", "~/.ssh/id_ed25519")).expanduser())
HOST = ENV.get("SSH_HOST")
PORTA = ENV.get("SSH_PORT", "22")
REMOTO = ENV.get("REMOTO")
INDEXNOW_KEY = ENV.get("INDEXNOW_KEY")


def log(msg):
    linha = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(linha, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def run(cmd, **kw):
    log("$ " + (cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.stdout.strip():
        log(r.stdout.strip()[-1500:])
    if r.returncode != 0:
        log("ERRO rc=%s %s" % (r.returncode, r.stderr.strip()[-800:]))
        raise RuntimeError(f"falhou: {cmd}")
    return r.stdout


def data_da_base(caminho):
    with open(caminho, encoding="utf-8-sig", errors="replace") as f:
        primeira = f.readline().strip()
    # "Atualizado em: 2026-09-20"
    return primeira.split(":")[-1].strip()


def base_publicada():
    try:
        html = urllib.request.urlopen(URL_PAGINA, timeout=30).read().decode("utf-8", "replace")
        i = html.find('"dateModified": "')
        return html[i + 17:i + 27] if i >= 0 else None
    except Exception as e:  # noqa
        log(f"aviso: nao li a pagina publicada ({e})")
        return None


def main():
    log("=== inicio da rotina ===")
    # 1. baixa a base
    tmp = HERE / "SISANT_baixado.csv"
    urllib.request.urlretrieve(URL_CSV, tmp)
    nova = data_da_base(tmp)
    atual = base_publicada()
    log(f"base baixada: {nova} | publicada: {atual}")
    if not FORCAR and atual and nova <= atual:
        log("nada a fazer: a base publicada ja e a mais recente")
        RESUMO.write_text(f"{dt.datetime.now():%d/%m/%Y %H:%M}: sem base nova (ANAC {nova}, publicada {atual}).\n", encoding="utf-8")
        tmp.unlink(missing_ok=True)
        return 0
    shutil.move(str(tmp), str(CSV))
    SNAP.mkdir(exist_ok=True)
    shutil.copy(CSV, SNAP / f"SISANT_{nova}.csv")
    log(f"snapshot guardado: snapshots/SISANT_{nova}.csv")

    # 2. UF das empresas novas (retomavel) e apuracao
    py = sys.executable
    run([py, str(HERE / "apura_uf.py")])
    run([py, str(HERE / "consulta_uf.py")])
    out = run([py, str(HERE / "obs_apura.py")])       # aborta sozinho se uma checagem de consistencia falhar
    run([py, str(HERE / "obs_diff.py")])              # entradas, renovacoes e saidas contra o snapshot anterior
    run([py, str(HERE / "obs_build.py")])
    idx = SAIDA / "index.html"
    if nova.split("-")[2] + "/" + nova.split("-")[1] + "/" + nova.split("-")[0] not in idx.read_text(encoding="utf-8"):
        raise RuntimeError("a pagina gerada nao traz a data da base nova")

    # 3. publica (uma sessao SSH: tar pelo stdin), purga e avisa
    if not (HOST and REMOTO):
        log("sem obs_rotina.env: pagina gerada localmente, publicacao pulada")
        RESUMO.write_text(f"{dt.datetime.now():%d/%m/%Y %H:%M}: base {nova} apurada e gerada em {SAIDA} (sem publicar).\n", encoding="utf-8")
        return 0
    # dados/ leva a edicao datada e o diff: cada base publicada fica conferivel depois
    tarcmd = [TAR, "-C", str(SAIDA), "-cf", "-", "index.html", "observatorio-drone-brasil.json", "sitemap.xml", "dados"]
    remoto = (f"set -e; cd {REMOTO} && cp index.html ~/observatorio-index.bak_{nova.replace('-', '')} && tar -xf - "
              f"&& cd .. && wp litespeed-purge all | tail -1")
    log("publicando...")
    p1 = subprocess.Popen(tarcmd, stdout=subprocess.PIPE)
    p2 = subprocess.run([SSH, "-p", PORTA, "-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=30", "-o", "LogLevel=ERROR", HOST, remoto],
                        stdin=p1.stdout, capture_output=True, text=True, encoding="utf-8", errors="replace")
    p1.stdout.close(); p1.wait()
    log((p2.stdout or p2.stderr).strip()[-300:])
    if p2.returncode != 0:
        raise RuntimeError("publicacao falhou (ssh)")
    time.sleep(5)
    vivo = base_publicada()
    if vivo != nova:
        raise RuntimeError(f"a pagina no ar mostra {vivo}, esperado {nova}")
    if INDEXNOW_KEY:
        body = json.dumps({"host": "irlenmenezes.com.br", "key": INDEXNOW_KEY,
                           "keyLocation": f"https://irlenmenezes.com.br/{INDEXNOW_KEY}.txt", "urlList": [URL_PAGINA]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            code = urllib.request.urlopen(req, timeout=30).status
        except Exception as e:  # noqa
            code = f"erro {e}"
        log(f"indexnow: {code}")
    resumo = f"{dt.datetime.now():%d/%m/%Y %H:%M}: publicada a base ANAC de {nova} (antes: {atual}).\n" + (out.strip()[-600:] if out else "")
    RESUMO.write_text(resumo + "\n", encoding="utf-8")
    log("=== fim: OK ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa
        log(f"=== fim: FALHOU: {e} ===")
        RESUMO.write_text(f"{dt.datetime.now():%d/%m/%Y %H:%M}: FALHOU: {e}\n", encoding="utf-8")
        sys.exit(1)
