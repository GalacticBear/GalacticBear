from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def github_graphql(query: str, variables: dict) -> dict:
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise SystemExit(
            "GITHUB_TOKEN is not set. "
            "Set it locally with: $env:GITHUB_TOKEN = gh auth token"
        )

    payload = json.dumps(
        {
            "query": query,
            "variables": variables,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "GalacticBear-profile-generator",
        },
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        result = json.load(response)

    if "errors" in result:
        raise RuntimeError(json.dumps(result["errors"], indent=2))

    return result["data"]


def get_contributions(login: str) -> dict:
    today = date.today()
    from_date = today - timedelta(days=364)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(
          from: $from
          to: $to
        ) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    data = github_graphql(
        query,
        {
            "login": login,
            "from": f"{from_date.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
        },
    )

    user = data.get("user")

    if not user:
        raise RuntimeError(f"GitHub user '{login}' was not found.")

    calendar = user["contributionsCollection"]["contributionCalendar"]

    days = []

    for week in calendar["weeks"]:
        for contribution_day in week["contributionDays"]:
            days.append(
                {
                    "date": contribution_day["date"],
                    "count": contribution_day["contributionCount"],
                }
            )

    return {
        "total": calendar["totalContributions"],
        "days": days,
    }


def calculate_streaks(days: list[dict]) -> tuple[int, int]:
    counts = {
        item["date"]: item["count"]
        for item in days
    }

    ordered_dates = sorted(counts)

    current_streak = 0
    longest_streak = 0
    running = 0

    for day in ordered_dates:
        if counts[day] > 0:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

    today = date.today()

    check_day = today

    while check_day.isoformat() in counts and counts[check_day.isoformat()] > 0:
        current_streak += 1
        check_day -= timedelta(days=1)

    return current_streak, longest_streak


def get_languages(login: str) -> list[tuple[str, int]]:
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(
          first: 100
          ownerAffiliations: OWNER
          privacy: PUBLIC
          isFork: false
        ) {
          nodes {
            languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                }
              }
            }
          }
        }
      }
    }
    """

    data = github_graphql(
        query,
        {
            "login": login,
        },
    )

    totals = Counter()

    for repository in data["user"]["repositories"]["nodes"]:
        if not repository:
            continue

        for edge in repository["languages"]["edges"]:
            language = edge["node"]["name"]
            size = edge["size"]
            totals[language] += size

    return totals.most_common(8)


def svg_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def write_svg(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_stats_svg(total: int, days: list[dict], output: Path) -> None:
    weekly = []

    for i in range(0, len(days), 7):
        weekly.append(
            sum(item["count"] for item in days[i:i + 7])
        )

    width = 760
    height = 230

    if weekly:
        max_value = max(weekly) or 1

        points = []

        for i, value in enumerate(weekly):
            x = 30 + (i / max(len(weekly) - 1, 1)) * 700
            y = 175 - (value / max_value) * 100
            points.append(f"{x:.1f},{y:.1f}")

        polyline = " ".join(points)
    else:
        polyline = "30,175 730,175"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
width="{width}" height="{height}" viewBox="0 0 {width} {height}"
role="img" aria-label="GitHub contribution statistics">

<rect x="0" y="0" width="{width}" height="{height}" rx="14"
fill="#0d1117" stroke="#30363d"/>

<text x="30" y="42"
font-family="monospace" font-size="16"
fill="#8b949e">GITHUB ACTIVITY</text>

<text x="30" y="92"
font-family="monospace" font-size="42"
font-weight="700"
fill="#f0f6fc">{total:,}</text>

<text x="30" y="118"
font-family="monospace" font-size="14"
fill="#8b949e">contributions in the last year</text>

<polyline
points="{polyline}"
fill="none"
stroke="#58a6ff"
stroke-width="3"
stroke-linejoin="round"
stroke-linecap="round"/>

</svg>
"""

    write_svg(output, svg)


def generate_streak_svg(
    current: int,
    longest: int,
    output: Path,
) -> None:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
width="760" height="180" viewBox="0 0 760 180"
role="img" aria-label="GitHub contribution streak statistics">

<rect x="0" y="0" width="760" height="180" rx="14"
fill="#0d1117" stroke="#30363d"/>

<text x="30" y="40"
font-family="monospace" font-size="16"
fill="#8b949e">CONTRIBUTION STREAKS</text>

<text x="30" y="105"
font-family="monospace" font-size="38"
font-weight="700"
fill="#f0f6fc">{current}</text>

<text x="30" y="132"
font-family="monospace" font-size="14"
fill="#8b949e">current streak</text>

<text x="390" y="105"
font-family="monospace" font-size="38"
font-weight="700"
fill="#f0f6fc">{longest}</text>

<text x="390" y="132"
font-family="monospace" font-size="14"
fill="#8b949e">longest streak</text>

</svg>
"""

    write_svg(output, svg)


def generate_languages_svg(
    languages: list[tuple[str, int]],
    output: Path,
) -> None:
    total = sum(size for _, size in languages) or 1

    rows = []

    for index, (language, size) in enumerate(languages):
        percentage = size / total * 100
        y = 58 + index * 42

        rows.append(
            f"""
            <text x="30" y="{y}"
            font-family="monospace"
            font-size="14"
            fill="#f0f6fc">{svg_escape(language)}</text>

            <rect x="180" y="{y - 13}"
            width="440" height="12" rx="6"
            fill="#21262d"/>

            <rect x="180" y="{y - 13}"
            width="{440 * percentage / 100:.1f}" height="12" rx="6"
            fill="#58a6ff"/>

            <text x="650" y="{y}"
            font-family="monospace"
            font-size="13"
            fill="#8b949e">{percentage:.1f}%</text>
            """
        )

    height = max(100, 75 + len(languages) * 42)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
width="760" height="{height}" viewBox="0 0 760 {height}"
role="img" aria-label="Programming languages used in public repositories">

<rect x="0" y="0" width="760" height="{height}" rx="14"
fill="#0d1117" stroke="#30363d"/>

<text x="30" y="30"
font-family="monospace" font-size="16"
fill="#8b949e">PUBLIC REPOSITORY LANGUAGES</text>

{"".join(rows)}

</svg>
"""

    write_svg(output, svg)


def generate_contributions_svg(
    days: list[dict],
    output: Path,
) -> None:
    width = 760
    height = 180

    ordered = sorted(days, key=lambda item: item["date"])

    cells = []

    for index, item in enumerate(ordered):
        x = 30 + (index % 52) * 13
        y = 48 + (index // 52) * 13

        count = item["count"]

        if count == 0:
            opacity = 0.08
        elif count <= 2:
            opacity = 0.30
        elif count <= 5:
            opacity = 0.55
        elif count <= 10:
            opacity = 0.75
        else:
            opacity = 1.0

        cells.append(
            f'<rect x="{x}" y="{y}" width="10" height="10" '
            f'rx="2" fill="#58a6ff" opacity="{opacity}" '
            f'data-date="{item["date"]}" data-count="{count}"/>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
width="{width}" height="{height}" viewBox="0 0 {width} {height}"
role="img" aria-label="GitHub contribution activity over the last year">

<rect x="0" y="0" width="{width}" height="{height}" rx="14"
fill="#0d1117" stroke="#30363d"/>

<text x="30" y="30"
font-family="monospace" font-size="16"
fill="#8b949e">CONTRIBUTION MAP · LAST 365 DAYS</text>

{"".join(cells)}

</svg>
"""

    write_svg(output, svg)


def generate_all_stats(assets_dir: Path) -> None:
    login = os.environ.get("GH_LOGIN")

    if not login:
        raise SystemExit(
            "GH_LOGIN is not set. "
            "Set it locally with: $env:GH_LOGIN = 'GalacticBear'"
        )

    contribution_data = get_contributions(login)

    total = contribution_data["total"]
    days = contribution_data["days"]

    current_streak, longest_streak = calculate_streaks(days)

    languages = get_languages(login)

    generate_stats_svg(
        total,
        days,
        assets_dir / "stats.svg",
    )

    generate_streak_svg(
        current_streak,
        longest_streak,
        assets_dir / "streak.svg",
    )

    generate_languages_svg(
        languages,
        assets_dir / "languages.svg",
    )

    generate_contributions_svg(
        days,
        assets_dir / "contributions.svg",
    )


if __name__ == "__main__":
    generate_all_stats(ROOT / "assets")