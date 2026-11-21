#!/usr/bin/env python3
"""
Imagens que acompanham o Observatório para fora da página (20/11/2026):

  og/observatorio-drone-brasil-<base>.png   cartão 1200x630 de compartilhamento (og:image)
  selo.png                                  selo 320x100 (exportado em 2x) para outros sites embedarem

As duas saem dos mesmos números da página e são refeitas a cada build. O cartão leva a data
da base no nome, porque WhatsApp, LinkedIn e o CDN guardam imagem por URL: nome novo = imagem
nova. O selo tem URL fixa (é o que os outros sites colam), e o .htaccess da pasta dá a ele
cache curto para o número trocar junto com a base.

Precisa do Playwright com o Chrome instalado (o mesmo do obs_mapa_baixa.py). Sem ele, o build
segue e a página continua com as imagens da edição anterior.
"""
import html
import tempfile
from pathlib import Path

BASE = Path(__file__).parent
FONTES = BASE / "obs-fonts"
MARCA = BASE / "obs-irlen-mark.webp"


def _num(n):
    return f"{n:,}".replace(",", ".")


def _data_br(iso):
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def _css():
    f = lambda nome: (FONTES / nome).as_uri()
    return f"""
@font-face{{font-family:"Big Shoulders Display";src:url({f('big-shoulders-display-800.woff2')}) format("woff2");font-weight:700 900}}
@font-face{{font-family:"IBM Plex Mono";src:url({f('ibm-plex-mono-400.woff2')}) format("woff2");font-weight:400}}
@font-face{{font-family:"IBM Plex Mono";src:url({f('ibm-plex-mono-500.woff2')}) format("woff2");font-weight:500}}
@font-face{{font-family:"Inter";src:url({f('inter-latin.woff2')}) format("woff2");font-weight:100 900}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent}}
.k{{font-family:"IBM Plex Mono",monospace;font-weight:500;text-transform:uppercase;letter-spacing:.12em;color:#56606b}}
"""


def _barras(serie, w=330, h=190):
    """Emissões por mês (meses completos), pico em destaque. SVG puro, sem eixo: é ornamento com dado."""
    vals = [s["novos"] for s in serie]
    vmax = max(vals)
    n = len(vals)
    gap = 3
    bw = (w - gap * (n - 1)) / n
    pico = vals.index(vmax)
    rects = []
    for i, v in enumerate(vals):
        bh = max(2, v / vmax * (h - 4))
        cor = "#c2410c" if i == pico else "#1d5a8a"
        rects.append(f'<rect x="{i * (bw + gap):.1f}" y="{h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{cor}"/>')
    return (f'<svg width="{w}" height="{h + 2}" viewBox="0 0 {w} {h + 2}" xmlns="http://www.w3.org/2000/svg">'
            f'{"".join(rects)}<line x1="0" y1="{h + 1}" x2="{w}" y2="{h + 1}" stroke="#14181d" stroke-width="1.5"/></svg>')


def _rotulo_mes(m):
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    a, mm = m.split("-")
    return f"{meses[int(mm) - 1]}/{a[2:]}"


def _html_cartao(total, pf, pj, base, serie):
    pico = max(serie, key=lambda s: s["novos"])
    marca = f'<img src="{MARCA.as_uri()}" width="34" height="34" alt="">' if MARCA.exists() else ""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{_css()}
.card{{width:1200px;height:630px;background:#f2f4f2;color:#14181d;padding:46px 64px 40px;display:flex;flex-direction:column;
 font-family:Inter,sans-serif;border-top:10px solid #1d5a8a}}
.top{{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:16px;border-bottom:2px solid #14181d}}
.top .k{{font-size:21px}}
.mid{{flex:1;display:flex;justify-content:space-between;align-items:flex-end;gap:40px;padding:26px 0 24px}}
.q{{font-size:46px;font-weight:650;letter-spacing:-.02em;line-height:1.1}}
.n{{font-family:"Big Shoulders Display",sans-serif;font-weight:800;font-size:236px;line-height:.86;color:#1d5a8a;margin-top:18px;letter-spacing:-.005em}}
.u{{font-size:33px;font-weight:500;color:#14181d;margin-top:14px}}
.r{{display:flex;flex-direction:column;gap:12px;padding-bottom:8px}}
.r .k{{font-size:15px;letter-spacing:.08em}}
.r .k b{{color:#c2410c;font-weight:500}}
.bot{{display:flex;justify-content:space-between;align-items:center;padding-top:16px;border-top:1px solid #c3cbd1;
 font-family:"IBM Plex Mono",monospace;font-size:21px;color:#56606b}}
.site{{display:flex;align-items:center;gap:12px;color:#14181d;font-weight:500}}
.site img{{border-radius:50%}}
</style></head><body><div class="card">
 <div class="top"><span class="k">Observatório do Drone no Brasil</span><span class="k">Dados abertos · ANAC</span></div>
 <div class="mid">
  <div>
   <p class="q">Quantos drones tem no Brasil?</p>
   <p class="n">{_num(total)}</p>
   <p class="u">drones cadastrados na ANAC</p>
  </div>
  <div class="r">{_barras(serie)}
   <span class="k">Emissões por mês · <b>pico {_rotulo_mes(pico['mes'])}</b></span>
  </div>
 </div>
 <div class="bot"><span>Base de {_data_br(base)} · {_num(pf)} em CPF · {_num(pj)} em CNPJ</span>
  <span class="site">{marca}irlenmenezes.com.br</span></div>
</div></body></html>"""


def _html_selo(total, base):
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{_css()}
.selo{{width:320px;height:100px;background:#fff;border:1px solid #d7dde1;border-left:5px solid #1d5a8a;
 padding:11px 14px 10px;display:flex;flex-direction:column;justify-content:space-between}}
.selo .k{{font-size:10.5px;letter-spacing:.1em}}
.n{{font-family:"Big Shoulders Display",sans-serif;font-weight:800;font-size:44px;line-height:.9;color:#1d5a8a}}
.f{{font-family:"IBM Plex Mono",monospace;font-size:9.6px;color:#56606b;white-space:nowrap}}
.f b{{color:#14181d;font-weight:500}}
</style></head><body><div class="selo">
 <span class="k">Drones cadastrados no Brasil</span>
 <span class="n">{_num(total)}</span>
 <span class="f">ANAC, base de {_data_br(base)} · <b>Observatório do Drone</b></span>
</div></body></html>"""


def gera(destino: Path, total: int, pf: int, pj: int, base: str, serie: list) -> dict:
    """Gera cartão e selo em `destino`. Devolve {'og': caminho relativo, 'selo': caminho relativo}.
    Levanta exceção se o Playwright/Chrome não estiver disponível: quem chama decide o que fazer."""
    from playwright.sync_api import sync_playwright

    destino = Path(destino)
    (destino / "og").mkdir(parents=True, exist_ok=True)
    og_rel = f"og/observatorio-drone-brasil-{base}.png"
    trabalhos = [(_html_cartao(total, pf, pj, base, serie), ".card", destino / og_rel, 1),
                 (_html_selo(total, base), ".selo", destino / "selo.png", 2)]
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        try:
            for i, (doc, sel, saida, escala) in enumerate(trabalhos):
                arq = Path(tmp) / f"c{i}.html"
                arq.write_text(doc, encoding="utf-8")
                pg = b.new_page(viewport={"width": 1300, "height": 760}, device_scale_factor=escala)
                pg.goto(arq.as_uri(), wait_until="load")
                pg.evaluate("document.fonts.ready.then(() => true)")
                ok = pg.evaluate("document.fonts.check('800 40px \"Big Shoulders Display\"') && document.fonts.check('500 12px \"IBM Plex Mono\"')")
                if not ok:
                    raise RuntimeError(f"fonte local não carregou para {saida.name}")
                pg.locator(sel).screenshot(path=str(saida))
                pg.close()
        finally:
            b.close()
    return {"og": og_rel, "selo": "selo.png"}


if __name__ == "__main__":  # teste isolado: python obs_card.py
    import json
    d = json.loads((BASE / "obs-drone.json").read_text(encoding="utf-8"))
    r = d["resumo"]
    serie = [s for s in d["serie"] if not s.get("parcial")]
    print(gera(Path(tempfile.gettempdir()) / "obs-card-teste", r["total"], r["pf"], r["pj"], d["meta"]["data_base"], serie))
