#!/usr/bin/env python3
"""Draw a card for each upstream repo I've contributed to and splice the cards into README.md.

Edit CONTRIBUTIONS, then run `python3 scripts/cards.py`. Needs an authenticated gh CLI.
Rerun it to refresh star and fork counts.
"""
import base64
import json
import re
import subprocess
import urllib.request
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
USER = "Chaoqi31"
W = 416

CONTRIBUTIONS = [
    # repo, merged PR numbers, one-line summary under the repo name
    ("walkinglabs/hands-on-modern-rl", [37], "Open-source course on RL for LLMs and agents"),
]

THEMES = {
    "light": dict(bg="#ffffff", border="#d1d9e0", fg="#1f2328", muted="#59636e", accent="#0969da",
                  done="#8250df", add="#1a7f37", delete="#d1242f", ring="#1f232826"),
    "dark": dict(bg="#0d1117", border="#3d444d", fg="#f0f6fc", muted="#9198a1", accent="#4493f8",
                 done="#ab7df8", add="#3fb950", delete="#f85149", ring="#ffffff26"),
}

# Primer Octicons, 16px, MIT license.
MERGE = "M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .005V3.25Z"
STAR = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"
FORK = "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"


def fetch(repo, numbers):
    owner, name = repo.split("/")
    prs = "".join(
        f"pr{n}: pullRequest(number: {n}) {{ number title additions deletions mergedAt author {{ login }} }}"
        for n in numbers
    )
    query = (
        f'{{ repository(owner: "{owner}", name: "{name}") {{ stargazerCount forkCount '
        f"primaryLanguage {{ name color }} owner {{ __typename avatarUrl(size: 80) }} {prs} }} }}"
    )
    out = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], check=True, capture_output=True, text=True)
    data = json.loads(out.stdout)["data"]["repository"]
    for n in numbers:
        pr = data[f"pr{n}"]
        if not pr["mergedAt"] or pr["author"]["login"] != USER:
            raise SystemExit(f"{repo}#{n} is not a merged PR by {USER}")
    return data


def avatar(url):
    with urllib.request.urlopen(url) as r:
        return f"data:{r.headers.get_content_type()};base64,{base64.b64encode(r.read()).decode()}"


def short(n):
    return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k" if n >= 1000 else str(n)


def clip(text, limit=46):
    # ponytail: character count, not measured width. Titles near the limit may still touch the edge.
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def card(t, repo, data, numbers, summary, image):
    owner, name = repo.split("/")
    lang = data["primaryLanguage"] or {"name": "", "color": t["muted"]}
    corner = 4 if data["owner"]["__typename"] == "Organization" else 10
    h = 98 + 48 * len(numbers) + 10
    rows = ""
    for i, n in enumerate(numbers):
        pr, y = data[f"pr{n}"], 98 + 48 * i
        merged = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00")).strftime("%b %-d, %Y")
        rows += (
            f'<path transform="translate(16 {y + 13})" fill="{t["done"]}" d="{MERGE}"/>'
            f'<text x="40" y="{y + 26}" font-size="13" font-weight="600" fill="{t["fg"]}">{escape(clip(pr["title"]))}</text>'
            f'<text x="40" y="{y + 44}" font-size="12" fill="{t["muted"]}">#{n} merged on {merged}'
            f'<tspan dx="8" fill="{t["add"]}">+{pr["additions"]}</tspan>'
            f'<tspan dx="4" fill="{t["delete"]}">−{pr["deletions"]}</tspan></text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
        f'aria-label="{repo}, {len(numbers)} merged pull request{"s" if len(numbers) > 1 else ""}">'
        '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; }</style>'
        f'<defs><clipPath id="avatar"><rect x="16" y="16" width="20" height="20" rx="{corner}"/></clipPath></defs>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="6" fill="{t["bg"]}" stroke="{t["border"]}"/>'
        f'<image href="{image}" x="16" y="16" width="20" height="20" clip-path="url(#avatar)"/>'
        f'<rect x="16.5" y="16.5" width="19" height="19" rx="{corner - .5}" fill="none" stroke="{t["ring"]}"/>'
        f'<text x="44" y="31" font-size="14" fill="{t["accent"]}">{owner}/<tspan font-weight="600">{name}</tspan></text>'
        f'<text x="16" y="58" font-size="12" fill="{t["muted"]}">{escape(summary)}</text>'
        f'<circle cx="21" cy="78" r="5" fill="{lang["color"]}"/>'
        f'<text x="32" y="82" font-size="12" fill="{t["muted"]}">{lang["name"]}</text>'
        f'<path transform="translate(112 70)" fill="{t["muted"]}" d="{STAR}"/>'
        f'<text x="132" y="82" font-size="12" fill="{t["muted"]}">{short(data["stargazerCount"])}</text>'
        f'<path transform="translate(184 70)" fill="{t["muted"]}" d="{FORK}"/>'
        f'<text x="204" y="82" font-size="12" fill="{t["muted"]}">{short(data["forkCount"])}</text>'
        f'<path d="M1 98.5H{W - 1}" stroke="{t["border"]}"/>'
        f"{rows}</svg>\n"
    )


def main():
    links = []
    for repo, numbers, summary in CONTRIBUTIONS:
        data = fetch(repo, numbers)
        image = avatar(data["owner"]["avatarUrl"])
        slug = repo.replace("/", "-")
        for theme, t in THEMES.items():
            (ROOT / f"assets/contrib/{slug}-{theme}.svg").write_text(card(t, repo, data, numbers, summary, image))
        if len(numbers) == 1:
            href, alt = f"https://github.com/{repo}/pull/{numbers[0]}", f'{repo}: merged PR #{numbers[0]}, {data[f"pr{numbers[0]}"]["title"]}'
        else:
            href, alt = f"https://github.com/{repo}/pulls?q=is%3Apr+is%3Amerged+author%3A{USER}", f"{repo}: {len(numbers)} merged PRs"
        links.append(
            f'<a href="{href}"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/contrib/{slug}-dark.svg">'
            f'<img alt="{escape(alt)}" src="assets/contrib/{slug}-light.svg" width="{W}"></picture></a>'
        )
        print(repo, short(data["stargazerCount"]), "stars")
    block = "<!-- contributions:start -->\n" + "\n".join(links) + "\n<!-- contributions:end -->"
    text = README.read_text()
    README.write_text(re.sub(r"<!-- contributions:start -->.*?<!-- contributions:end -->", lambda _: block, text, flags=re.S))


if __name__ == "__main__":
    main()
