#!/usr/bin/env python3
"""Gera o card SVG 'GitHub Stats' (tema Tokyo Night, estilo github-readme-stats)
somando estatísticas do usuário Diniz-Bruno e das Organizations Taverna-Web e Checkpoint-site.
Evita dependência de instâncias públicas do Vercel que sofrem rate-limit ou caem.
"""

import json
import math
import os
import urllib.parse
import urllib.request
from pathlib import Path

USERNAME = "Diniz-Bruno"
DISPLAY_NAME = "Bruno Diniz"
ORGS = ["Taverna-Web", "Checkpoint-site"]


def github_get(url: str, accept: str = "application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "User-Agent": "Diniz-Bruno-Profile-Stats",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_repos() -> list[dict]:
    repos = []
    seen = set()

    try:
        user_repos = github_get(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
        for r in user_repos:
            full_name = r.get("full_name")
            if full_name and full_name not in seen and not r.get("fork"):
                seen.add(full_name)
                repos.append(r)
    except Exception as exc:
        print(f"[warn] Falha ao buscar repos de {USERNAME}: {exc}")

    for org in ORGS:
        try:
            org_repos = github_get(f"https://api.github.com/orgs/{org}/repos?per_page=100")
            for r in org_repos:
                full_name = r.get("full_name")
                if full_name and full_name not in seen and not r.get("fork"):
                    seen.add(full_name)
                    repos.append(r)
        except Exception as exc:
            print(f"[warn] Falha ao buscar repos da org {org}: {exc}")

    return repos


def fetch_search_count(query: str, accept: str = "application/vnd.github+json") -> int | None:
    encoded = urllib.parse.quote(query)
    url = f"https://api.github.com/search/issues?q={encoded}&per_page=1"
    if "commits" in accept or query.startswith("commits:"):
        q_clean = query.removeprefix("commits:")
        encoded = urllib.parse.quote(q_clean)
        url = f"https://api.github.com/search/commits?q={encoded}&per_page=1"
    try:
        data = github_get(url, accept=accept)
        return int(data.get("total_count", 0))
    except Exception as exc:
        print(f"[warn] Falha na busca '{query}': {exc}")
        return None


def fetch_commits_from_contributors(repos: list[dict]) -> int:
    total = 0
    for repo in repos:
        full_name = repo.get("full_name")
        if not full_name:
            continue
        try:
            contributors = github_get(
                f"https://api.github.com/repos/{full_name}/contributors?per_page=100"
            )
            if isinstance(contributors, list):
                for c in contributors:
                    if str(c.get("login", "")).lower() == USERNAME.lower():
                        total += int(c.get("contributions", 0))
        except Exception as exc:
            print(f"[warn] Falha ao buscar contributors de {full_name}: {exc}")
    return total


def calculate_rank(commits: int, prs: int, issues: int, stars: int, followers: int) -> tuple[str, float]:
    """Calcula o rank e o progresso do anel baseado na fórmula do github-readme-stats."""
    def exp_cdf(x: float) -> float:
        return 1.0 - (2.0 ** -x)

    def log_normal_cdf(x: float) -> float:
        return x / (1.0 + x)

    commits_weight = 2.0
    prs_weight = 3.0
    issues_weight = 1.0
    stars_weight = 4.0
    followers_weight = 1.0
    total_weight = commits_weight + prs_weight + issues_weight + stars_weight + followers_weight

    score = (
        commits_weight * exp_cdf(commits / 250.0)
        + prs_weight * exp_cdf(prs / 50.0)
        + issues_weight * exp_cdf(issues / 25.0)
        + stars_weight * log_normal_cdf(stars / 50.0)
        + followers_weight * log_normal_cdf(followers / 10.0)
    ) / total_weight

    percentile = (1.0 - score) * 100.0

    thresholds = [
        (1.0, "S"),
        (12.5, "A+"),
        (25.0, "A"),
        (37.5, "A-"),
        (50.0, "B+"),
        (62.5, "B"),
        (75.0, "B-"),
        (87.5, "C+"),
        (100.0, "C"),
    ]
    level = "C"
    for limit, grade in thresholds:
        if percentile <= limit:
            level = grade
            break

    return level, max(15.0, min(100.0, 100.0 - percentile))


def fetch_stats() -> dict:
    followers = 0
    try:
        user_data = github_get(f"https://api.github.com/users/{USERNAME}")
        followers = int(user_data.get("followers", 0))
    except Exception as exc:
        print(f"[warn] Falha ao buscar perfil de {USERNAME}: {exc}")

    repos = fetch_repos()
    total_stars = sum(int(r.get("stargazers_count", 0)) for r in repos)
    total_repos = len(repos)

    commits_search = fetch_search_count(
        f"commits:author:{USERNAME}",
        accept="application/vnd.github.cloak-preview+json",
    )
    commits_contrib = fetch_commits_from_contributors(repos)
    total_commits = max(commits_search or 0, commits_contrib)

    total_prs = fetch_search_count(f"author:{USERNAME} type:pr") or 0
    total_issues = fetch_search_count(f"author:{USERNAME} type:issue") or 0

    rank, progress = calculate_rank(
        commits=total_commits,
        prs=total_prs,
        issues=total_issues,
        stars=total_stars,
        followers=followers,
    )

    return {
        "stars": total_stars,
        "commits": total_commits,
        "prs": total_prs,
        "issues": total_issues,
        "repos": total_repos,
        "rank": rank,
        "progress": progress,
    }


def render_svg(stats: dict) -> str:
    width = 450
    height = 195
    radius = 40
    circumference = 2 * math.pi * radius
    dashoffset = circumference * (1.0 - stats["progress"] / 100.0)

    rows = [
        (
            "Total Stars Earned:",
            stats["stars"],
            '<path fill-rule="evenodd" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25zm0 2.445L6.615 5.5a.75.75 0 01-.564.41l-3.097.45 2.24 2.184a.75.75 0 01.216.664l-.528 3.084 2.769-1.456a.75.75 0 01.698 0l2.77 1.456-.53-3.084a.75.75 0 01.216-.664l2.24-2.183-3.096-.45a.75.75 0 01-.564-.41L8 2.694v.001z"/>',
        ),
        (
            "Total Commits:",
            stats["commits"],
            '<path fill-rule="evenodd" d="M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z"/>',
        ),
        (
            "Total PRs:",
            stats["prs"],
            '<path fill-rule="evenodd" d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/>',
        ),
        (
            "Total Issues:",
            stats["issues"],
            '<path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9 3a1 1 0 11-2 0 1 1 0 012 0zm-.25-6.25a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0v-3.5z"/>',
        ),
        (
            "Contributed to (repos):",
            stats["repos"],
            '<path fill-rule="evenodd" d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z"/>',
        ),
    ]

    row_Nodes = []
    for idx, (label, val, icon_path) in enumerate(rows):
        y = idx * 25
        row_Nodes.append(
            f"""    <g transform="translate(25, {y})">
      <svg class="icon" viewBox="0 0 16 16" version="1.1" width="16" height="16">
        {icon_path}
      </svg>
      <text class="stat bold" x="25" y="12.5">{label}</text>
      <text class="stat bold" x="215" y="12.5" data-testid="stat-value">{val}</text>
    </g>"""
        )

    rows_svg = "\n".join(row_Nodes)

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="descId">
  <title id="titleId">{DISPLAY_NAME}'s GitHub Stats, Rank: {stats["rank"]}</title>
  <desc id="descId">Total Stars: {stats["stars"]}, Total Commits: {stats["commits"]}, Total PRs: {stats["prs"]}, Total Issues: {stats["issues"]}, Contributed to: {stats["repos"]}</desc>
  <style>
    .header {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #70a5fd;
    }}
    .stat {{
      font: 600 14px 'Segoe UI', Ubuntu, "Helvetica Neue", Sans-Serif;
      fill: #38bdae;
    }}
    .bold {{
      font-weight: 700;
    }}
    .rank-text {{
      font: 800 24px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #38bdae;
    }}
    .icon {{
      fill: #bf91f3;
    }}
    .rank-circle-rim {{
      stroke: #70a5fd;
      fill: none;
      stroke-width: 6;
      opacity: 0.2;
    }}
    .rank-circle {{
      stroke: #70a5fd;
      stroke-dasharray: {circumference:.2f};
      stroke-dashoffset: {dashoffset:.2f};
      fill: none;
      stroke-width: 6;
      stroke-linecap: round;
      opacity: 0.85;
      transform-origin: 0px 0px;
      transform: rotate(-90deg);
    }}
  </style>
  <rect data-testid="card-bg" x="0.5" y="0.5" rx="4.5" height="99%" stroke="#E4E2E2" width="{width - 1}" fill="#1a1b27" stroke-opacity="1"/>
  <g transform="translate(25, 35)">
    <text x="0" y="0" class="header" data-testid="header">{DISPLAY_NAME}'s GitHub Stats</text>
  </g>
  <g data-testid="main-card-body" transform="translate(0, 55)">
    <g data-testid="rank-circle" transform="translate(365, 55)">
      <circle class="rank-circle-rim" cx="0" cy="0" r="{radius}"/>
      <circle class="rank-circle" cx="0" cy="0" r="{radius}"/>
      <g class="rank-text">
        <text x="0" y="0" alignment-baseline="central" dominant-baseline="central" text-anchor="middle" data-testid="level-rank-icon">{stats["rank"]}</text>
      </g>
    </g>
{rows_svg}
  </g>
</svg>
"""


def main():
    stats = fetch_stats()
    if stats["repos"] == 0 and stats["commits"] == 0:
        raise RuntimeError("Nenhuma estatística retornada pela API do GitHub.")
    svg = render_svg(stats)
    out_path = Path(__file__).resolve().parent.parent / "assets" / "github-stats.svg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    print(f"SVG de GitHub Stats gerado com sucesso em {out_path}: {stats}")


if __name__ == "__main__":
    main()
