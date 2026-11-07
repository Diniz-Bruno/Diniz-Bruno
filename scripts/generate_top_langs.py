#!/usr/bin/env python3
"""Gera o card SVG 'Top Languages' (tema Tokyo Night) somando os repositórios
pessoais do usuário Diniz-Bruno e das Organizations Taverna-Web e Checkpoint-site.
"""

import json
import os
import urllib.request
from pathlib import Path

USERNAME = "Diniz-Bruno"
ORGS = ["Taverna-Web", "Checkpoint-site"]
EXCLUDED_LANGS = {"Jupyter Notebook", "Makefile", "HTML", "CSS", "Shell", "Dockerfile"}

LANG_COLORS = {
    "C#": "#178600",
    "C++": "#f34b7d",
    "TypeScript": "#3178c6",
    "Python": "#3572A5",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "SQL": "#e38c00",
    "PLpgSQL": "#336790",
    "TSQL": "#e38c00",
    "Go": "#00ADD8",
    "Rust": "#dea584",
}


def github_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Diniz-Bruno-Profile-Stats",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_language_bytes() -> dict[str, int]:
    totals: dict[str, int] = {}
    repos = []

    # 1. Repositórios do usuário
    user_repos = github_get(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
    repos.extend(r for r in user_repos if not r.get("fork"))

    # 2. Repositórios das Organizations
    for org in ORGS:
        try:
            org_repos = github_get(f"https://api.github.com/orgs/{org}/repos?per_page=100")
            repos.extend(r for r in org_repos if not r.get("fork"))
        except Exception as exc:
            print(f"[warn] Falha ao buscar org {org}: {exc}")

    seen = set()
    for repo in repos:
        full_name = repo.get("full_name")
        if not full_name or full_name in seen:
            continue
        seen.add(full_name)
        lang_url = repo.get("languages_url")
        if not lang_url:
            continue
        try:
            langs = github_get(lang_url)
            for lang, count in langs.items():
                if lang in EXCLUDED_LANGS:
                    continue
                totals[lang] = totals.get(lang, 0) + int(count)
        except Exception as exc:
            print(f"[warn] Falha ao buscar linguagens de {full_name}: {exc}")

    return totals


def render_svg(totals: dict[str, int], max_langs: int = 6) -> str:
    sorted_items = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:max_langs]
    total_bytes = sum(v for _, v in sorted_items) or 1

    # Layout dimensions matching github-readme-stats compact card (height=180em)
    width = 350
    rows = (len(sorted_items) + 1) // 2
    height = 195

    # Progress bar segments
    bar_width = 300
    bar_parts = []
    offset = 0.0
    for lang, count in sorted_items:
        pct = count / total_bytes
        seg_w = round(pct * bar_width, 2)
        color = LANG_COLORS.get(lang, "#70a5fd")
        bar_parts.append(
            f'<rect mask="url(#rect-mask)" data-testid="lang-progress" '
            f'x="{offset:.2f}" y="0" width="{seg_w + 0.5:.2f}" height="8" fill="{color}"/>'
        )
        offset += seg_w

    # Legend items (2 columns)
    legend_parts = []
    for idx, (lang, count) in enumerate(sorted_items):
        pct = (count / total_bytes) * 100
        color = LANG_COLORS.get(lang, "#70a5fd")
        col = idx % 2
        row = idx // 2
        x_pos = 0 if col == 0 else 150
        y_pos = row * 25
        legend_parts.append(
            f'<g transform="translate({x_pos}, {y_pos})">'
            f'<circle cx="5" cy="6" r="5" fill="{color}" />'
            f'<text data-testid="lang-name" x="15" y="10" class="lang-name">'
            f"{lang} ({pct:.2f}%)"
            f"</text>"
            f"</g>"
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="descId">
  <title id="titleId">My Programming Languages</title>
  <desc id="descId">Most used languages across personal and organization repositories</desc>
  <style>
    .header {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #70a5fd;
    }}
    .lang-name {{
      font: 400 12px 'Inter', 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #38bdae;
    }}
  </style>
  <rect data-testid="card-bg" x="0.5" y="0.5" rx="4.5" height="99%" stroke="#E4E2E2" width="{width - 1}" fill="#1a1b27" stroke-opacity="1"/>
  <g transform="translate(25, 35)">
    <text x="0" y="0" class="header" data-testid="header">My Programming Languages</text>
  </g>
  <g transform="translate(25, 55)">
    <mask id="rect-mask">
      <rect x="0" y="0" width="{bar_width}" height="8" fill="white" rx="5"/>
    </mask>
    {"".join(bar_parts)}
    <g transform="translate(0, 28)">
      {"".join(legend_parts)}
    </g>
  </g>
</svg>
"""


def main():
    totals = fetch_all_language_bytes()
    if not totals:
        raise RuntimeError("Nenhuma linguagem encontrada pela API.")
    svg = render_svg(totals)
    out_path = Path(__file__).resolve().parent.parent / "assets" / "top-langs.svg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    print(f"SVG gerado com sucesso em {out_path}: {totals}")


if __name__ == "__main__":
    main()
