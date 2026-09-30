#!/usr/bin/env python3
"""Draw the profile README in ink on colored paper, then write README.md and assets/.

Every word is converted to glyph outlines, so the SVGs need no fonts at view time.
Fonts come from the Google Fonts subsetting API and are cached in .cache/fonts.
Merged pull requests are checked with the gh CLI, so the page can only list merged work of mine.
Needs: pip install fonttools uharfbuzz numpy, and an authenticated gh CLI.
"""
import hashlib
import json
import math
import re
import subprocess
import urllib.parse
import urllib.request
from functools import lru_cache
from html import escape
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache/fonts"
ASSETS = ROOT / "assets"
USER = "Chaoqi31"

HEADLINE = ["Building LLM agents at Z.AI.", "Making video generation faster at Penn."]
PROJECTS = [
    dict(slug="argus", name="Argus", color="#CBCADB", href="https://github.com/Chaoqi31/argus-truth-engine",
         blurb="Audits AI-generated content, claim by claim.", note="Best Technical Implementation, UCWS Singapore 2026"),
    dict(slug="nemotron", name="Nemotron Reasoning", color="#D4A27F", href="https://github.com/Chaoqi31/nemotron-reasoning-lora",
         blurb="Single-epoch LoRA on Nemotron-3-Nano-30B-A3B.", note="Kaggle silver medal, 33rd of 4,182"),
    dict(slug="text2sql", name="text2sql-agent-rl", color="#BCD1CA", href="https://github.com/Chaoqi31/text2sql-agent-rl",
         blurb="An RL-trained agent that explores the database first.", note="+7.2 execution accuracy on BIRD dev"),
    dict(slug="saiddone", name="SaidDone", color="#E3DACC", href="https://github.com/Chaoqi31/saiddone",
         blurb="Local-first voice dictation for macOS.", note="Free, private, offline by default"),
]
CONTRIBUTIONS = [("walkinglabs/hands-on-modern-rl", [37])]
LINKS = [
    ("website", "Website", "https://chaoqiluo.com/"),
    ("scholar", "Google Scholar", "https://scholar.google.com/citations?user=eOwS19sAAAAJ&hl=en"),
    ("linkedin", "LinkedIn", "https://www.linkedin.com/in/chaoqi-luo-4317bb2b7/"),
    ("email", "Email", "mailto:luo31@seas.upenn.edu"),
]

W, HALF, GUTTER = 846, 423, 22
# GitHub sets images on the text baseline, which leaves this much space under each row of tiles.
BASELINE_GAP = 6
INK, IVORY, CLAY, OAT = "#141413", "#FAF9F5", "#D97757", "#E3DACC"
LINK_INK = {"light": ("#141413", "#8F897E"), "dark": ("#EEEAE1", "#77716A")}
LATIN = "".join(chr(c) for c in range(32, 127)) + "×–—’‘“”…é"


def font(family, text):
    """Download a TTF subset holding just `text`. Google serves TTF to a non-browser user agent."""
    path = CACHE / (hashlib.sha1(f"{family}|{text}".encode()).hexdigest()[:12] + ".ttf")
    if not path.exists():
        query = urllib.parse.urlencode({"family": family, "text": text})
        css = urllib.request.urlopen(f"https://fonts.googleapis.com/css2?{query}").read().decode()
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(re.search(r"url\((.+?)\)", css)[1]).read())
    return path


DISPLAY = font("Newsreader:opsz,wght@72,300", LATIN)
TEXT = font("Newsreader:opsz,wght@16,400", LATIN)
ITALIC = font("Newsreader:ital,opsz,wght@1,16,400", LATIN)


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


@lru_cache(None)
def face(path):
    tt = TTFont(path)
    return hb.Font(hb.Face(hb.Blob.from_file_path(str(path)))), tt.getGlyphSet(), tt.getGlyphOrder(), tt["head"].unitsPerEm


class Line:
    """One shaped run of text: glyph outlines placed by HarfBuzz, kerning included."""

    def __init__(self, path, s, size, tracking=0.0):
        hbfont, self.glyphset, order, upem = face(path)
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(hbfont, buf)
        self.scale = size / upem
        self.glyphs, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            self.glyphs.append((order[info.codepoint], x + pos.x_offset, pos.y_offset))
            x += pos.x_advance + tracking * upem
        self.width = (x - tracking * upem) * self.scale

    def path(self, x, y):
        pen = SVGPathPen(self.glyphset, ntos=num)
        for name, gx, gy in self.glyphs:
            m = (self.scale, 0, 0, -self.scale, x + gx * self.scale, y - gy * self.scale)
            self.glyphset[name].draw(TransformPen(pen, m))
        return pen.getCommands()


def text(path, s, size, x, y, fill, tracking=0.0, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<path{c} fill="{fill}" d="{Line(path, s, size, tracking).path(x, y)}"/>'


def svg(w, h, label, body, defs="", style=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(w)}" height="{num(h)}" viewBox="0 0 {num(w)} {num(h)}" '
        f'role="img" aria-label="{escape(label)}"><defs>{defs}</defs>{f"<style>{style}</style>" if style else ""}{body}</svg>\n'
    )


def grain(rgb, alpha):
    """Paper tooth: sparse specks of `rgb` from fractal noise."""
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return (
        '<filter id="grain" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
        '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3" stitchTiles="stitch"/>'
        f'<feColorMatrix values="0 0 0 0 {r:.3f} 0 0 0 0 {g:.3f} 0 0 0 0 {b:.3f} 1.7 0 0 0 -.78"/>'
        f'<feComponentTransfer><feFuncA type="linear" slope="{alpha}"/></feComponentTransfer></filter>'
    )


def rough(scale):
    """Nudge edges with low-frequency noise so machine-straight strokes read as drawn by hand."""
    return (
        '<filter id="rough" x="-2%" y="-10%" width="104%" height="120%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".045" numOctaves="2" seed="9" result="n"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="n" scale="{scale}" xChannelSelector="R" yChannelSelector="G"/></filter>'
    )


def plate(x, y, w, h, color):
    return f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" fill="{color}"/><rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" filter="url(#grain)"/>'


# ---------------------------------------------------------------- pen

def noise(n, seed, knots):
    """Smooth 1-D noise: `knots` random values, eased between."""
    k = np.random.default_rng(seed).normal(0, 1, knots + 3)
    t = np.linspace(0, knots, n)
    i = np.floor(t).astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    return k[i] * (1 - f) + k[i + 1] * f


def smoothstep(a, b, u):
    v = np.clip((u - a) / (b - a), 0, 1)
    return v * v * (3 - 2 * v)


def gesture(x0, x1, y_end, seed, n=2600):
    """A pen path whose curvature starts as noise and is pulled straight: a tangle that settles into a horizon."""
    u = np.linspace(0, 1, n)
    curl = 0.06 * noise(n, seed, 48) * (1 - smoothstep(0.3, 0.86, u))
    pull = 0.0008 + 0.022 * smoothstep(0.4, 0.92, u)
    heading, x, y = 0.0, [0.0], [0.0]
    for i in range(1, n):
        heading += curl[i] - pull[i] * heading
        x.append(x[-1] + math.cos(heading))
        y.append(y[-1] + math.sin(heading))
    x, y = np.array(x), np.array(y)
    s = (x1 - x0) / (x[-1] - x[0])
    return list(zip(x0 + (x - x[0]) * s, y_end + (y - y[-1]) * s))


def polyline(points):
    return "M" + "L".join(f"{num(a)} {num(b)}" for a, b in points)


def catmull(points, closed=False):
    p = np.array(points)
    p = np.vstack([p[-1], p, p[0], p[1]]) if closed else np.vstack([p[0], p, p[-1]])
    d = f"M{num(p[1][0])} {num(p[1][1])}"
    for i in range(1, len(p) - 2):
        c1 = p[i] + (p[i + 1] - p[i - 1]) / 6
        c2 = p[i + 1] - (p[i + 2] - p[i]) / 6
        d += f"C{num(c1[0])} {num(c1[1])} {num(c2[0])} {num(c2[1])} {num(p[i + 1][0])} {num(p[i + 1][1])}"
    return d + ("Z" if closed else "")


def wobbly(points, amp, seed):
    p = np.array(points, float)
    n = len(p)
    p[:, 0] += amp * noise(n, seed, max(3, n // 8))
    p[:, 1] += amp * noise(n, seed + 50, max(3, n // 8))
    return p


def ellipse(cx, cy, rx, ry, n=48, a0=0.0, a1=2 * math.pi):
    return [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(a0, a1, n)]


def shape(points, seed, fill="none", width=2.6, amp=0.9):
    return (f'<path d="{catmull(wobbly(points, amp, seed), closed=True)}" fill="{fill}" stroke="{INK}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def stroke(points, seed, width=2.6, amp=0.7, color=INK, extra=""):
    return (f'<path d="{catmull(wobbly(points, amp, seed))}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round"{extra}/>')


# ---------------------------------------------------------------- drawings, one per project

def draw_eye(cx, cy):
    """Argus, the watchman with a hundred eyes."""
    top = [(cx - 70 + 140 * s, cy - 44 * math.sin(math.pi * s)) for s in np.linspace(0, 1, 30)]
    bottom = [(cx + 70 - 140 * s, cy + 34 * math.sin(math.pi * s)) for s in np.linspace(0, 1, 30)][1:-1]
    out = shape(top + bottom, 1, IVORY)
    out += shape(ellipse(cx + 4, cy - 3, 25, 25), 2, "#9C8FB8")
    out += f'<circle cx="{cx + 5}" cy="{cy - 3}" r="10" fill="{INK}"/><circle cx="{cx + 12}" cy="{cy - 10}" r="3.6" fill="{IVORY}"/>'
    for i, s in enumerate(np.linspace(0.14, 0.86, 7)):
        x, y = cx - 70 + 140 * s, cy - 44 * math.sin(math.pi * s)
        ang = math.atan2(-(44 * math.pi * math.cos(math.pi * s)), 140) - math.pi / 2
        out += stroke([(x, y - 2), (x + 13 * math.cos(ang), y - 2 + 13 * math.sin(ang))], 10 + i, 2.4, 0.3)
    return out


def draw_medal(cx, cy):
    """A silver medal hanging from crossed ribbons that run off the top of the tile."""
    top, knot, disc = cy - 110, cy - 22, cy + 16
    out = shape([(cx - 58, top), (cx - 32, top), (cx + 12, knot), (cx - 10, knot + 6)], 3, "#F3E6D0")
    out += shape([(cx + 58, top), (cx + 32, top), (cx - 12, knot), (cx + 10, knot + 6)], 4, IVORY)
    out += shape(ellipse(cx, disc, 42, 42, 56), 5, "#E6E4DF")
    out += shape(ellipse(cx, disc, 29, 29, 44), 6)
    star = [(cx + (15 if i % 2 == 0 else 6.5) * math.sin(i * math.pi / 5), disc - (15 if i % 2 == 0 else 6.5) * math.cos(i * math.pi / 5)) for i in range(10)]
    out += f'<path d="{polyline(wobbly(star, 0.5, 7))}Z" fill="{INK}" stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>'
    return out


def draw_database(cx, cy):
    """A database, and the dotted trail of an agent poking around it before answering."""
    rx, ry, top, bot = 50, 14, cy - 44, cy + 44
    body = [(cx - rx, top), (cx - rx, bot)] + [(cx - rx * math.cos(a), bot + ry * math.sin(a)) for a in np.linspace(0, math.pi, 30)] + [(cx + rx, top)]
    out = shape(body, 8, IVORY)
    out += shape(ellipse(cx, top, rx, ry, 40), 9, "#E4EFEA")
    for i, y in enumerate((cy - 15, cy + 14)):
        out += stroke([(cx - rx * math.cos(a), y + ry * math.sin(a)) for a in np.linspace(0, math.pi, 24)], 11 + i, 2.2, 0.5)
    trail = [(cx - 150 + 8 * s + 30 * math.sin(s / 7), cy + 58 - 1.6 * s + 16 * math.sin(s / 5)) for s in np.linspace(0, 62, 60)]
    return out + stroke(trail, 14, 2.6, 0.8, extra=' stroke-dasharray="0.5 7"')


def draw_voice(cx, cy):
    """A voice waveform turning into a page of text."""
    out = ""
    for i, hgt in enumerate([10, 24, 46, 30, 62, 38, 22, 44, 16]):
        x = cx - 128 + 13 * i
        out += stroke([(x, cy - hgt / 2), (x, cy + hgt / 2)], 20 + i, 3.2, 0.4)
    out += stroke([(cx - 2, cy), (cx + 26, cy)], 31, 2.4, 0.3)
    out += stroke([(cx + 17, cy - 8), (cx + 27, cy), (cx + 17, cy + 8)], 32, 2.4, 0.3)
    out += shape([(cx + 44, cy - 42), (cx + 138, cy - 42), (cx + 138, cy + 42), (cx + 44, cy + 42)], 33, IVORY, amp=0.7)
    for i, (w, y) in enumerate(((70, -20), (58, -2), (40, 16))):
        out += stroke([(cx + 58, cy + y), (cx + 58 + w, cy + y)], 34 + i, 2.4, 0.5)
    return out + stroke([(cx + 104, cy + 9), (cx + 104, cy + 24)], 38, 2.4, 0.2)


def draw_merge(x0, x1, y):
    """Two hand-drawn branches, the lower one the upstream trunk, joining at a merge commit."""
    length = x1 - x0
    s = np.linspace(0, 1, 60)
    lift = smoothstep(0.12, 0.36, s) * (1 - smoothstep(0.62, 0.86, s))
    out = stroke([(x0 + length * t, y) for t in s], 40, 2.4, 0.6)
    out += stroke([(x0 + length * t, y - 30 * l) for t, l in zip(s, lift)], 41, 2.4, 0.6)
    for i, (t, dy, fill) in enumerate(((0.06, 0, IVORY), (0.48, -30, IVORY), (0.9, 0, INK), (0.3, 0, IVORY))):
        out += shape(ellipse(x0 + length * t, y + dy, 6, 6, 18), 42 + i, fill, 2.2, 0.3)
    return out


DRAW = {"argus": draw_eye, "nemotron": draw_medal, "text2sql": draw_database, "saiddone": draw_voice}


# ---------------------------------------------------------------- plates

REVEAL = (
    "@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
    "@keyframes fade{from{opacity:0}to{opacity:1}}"
    "@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
)


def opener(seed=33):
    """Noise dots, then one pen line that tangles and settles into a horizon, then the headline."""
    h = 404
    line = gesture(104, W - 44, 150, seed)
    sx, sy = line[0]
    rng = np.random.default_rng(seed)
    dots = "".join(
        f'<circle cx="{num(sx + dx)}" cy="{num(sy + dy)}" r="{num(r)}"/>'
        for dx, dy, r in zip(rng.normal(0, 30, 70), rng.normal(0, 22, 70), rng.uniform(1, 2.3, 70))
    )
    body = plate(0, 0, W, h, CLAY) + f'<g class="dots" fill="{INK}">{dots}</g>'
    body += (f'<g filter="url(#rough)"><path class="pen" pathLength="1" d="{polyline(line)}" fill="none" stroke="{INK}" '
             'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g>')
    for i, s in enumerate(HEADLINE):
        body += text(DISPLAY, s, 36, 31, 318 + 45 * i, INK, -0.01, f"h{i}")
    style = REVEAL + (
        "@media (prefers-reduced-motion:no-preference){"
        ".dots{animation:fade 1s ease .1s both}"
        ".pen{stroke-dasharray:1;animation:draw 3.4s cubic-bezier(.45,.05,.3,1) .7s both}"
        ".h0{animation:rise 1.2s ease 3s both}.h1{animation:rise 1.2s ease 3.3s both}}"
    )
    return svg(W, h, " ".join(HEADLINE), body, rough(1.1) + grain("#3A1E10", ".22"), style)


def tile(p, i):
    """Tiles sit 50% wide with no whitespace between them, so each SVG carries its own half of the gutter."""
    ph, vgap = 290, (GUTTER - BASELINE_GAP) / 2
    x, y = (0 if i % 2 == 0 else GUTTER / 2), (0 if i < 2 else vgap)
    pw = HALF - GUTTER / 2
    body = plate(x, y, pw, ph, p["color"])
    body += f'<g clip-path="url(#tile)" filter="url(#rough)">{DRAW[p["slug"]](x + pw / 2, y + 96)}</g>'
    body += text(DISPLAY, p["name"], 27, x + 32, y + 214, INK, -0.01)
    body += text(TEXT, p["blurb"], 14.5, x + 32, y + 240, INK)
    body += text(ITALIC, p["note"], 14, x + 32, y + ph - 22, INK)
    clip = f'<clipPath id="tile"><rect x="{num(x)}" y="{num(y)}" width="{num(pw)}" height="{ph}"/></clipPath>'
    return svg(HALF, ph + vgap, f'{p["name"]}. {p["blurb"]} {p["note"]}.', body, clip + rough(2) + grain("#2A2018", ".12"))


def merged_plate(merged):
    rows = 56 * len(merged)
    h = 76 + rows
    body = plate(0, 0, W, h, OAT) + text(ITALIC, "Merged upstream", 15, 32, 44, INK)
    for i, (repo, prs) in enumerate(merged):
        y = 80 + 56 * i
        body += text(DISPLAY, repo, 21, 32, y, INK)
        detail = f'#{prs[0]["number"]}  {prs[0]["title"]}' if len(prs) == 1 else f"{len(prs)} merged pull requests"
        body += text(TEXT, detail, 14.5, 32, y + 24, INK)
    body += f'<g filter="url(#rough)">{draw_merge(W - 280, W - 44, 30 + h / 2)}</g>'
    return svg(W, h, alt_merged(merged), body, rough(1.4) + grain("#2A2018", ".12"))


def link(label, ink, rule):
    w = Line(TEXT, label, 16).width + 20
    body = text(TEXT, label, 16, 10, 21, ink)
    body += stroke([(10 + (w - 20) * t, 27) for t in np.linspace(0, 1, 12)], len(label), 1.2, 0.5, rule)
    return svg(w, 36, label, body)


# ---------------------------------------------------------------- README

def fetch_merged():
    """Titles of the listed pull requests, after checking each one is merged and mine."""
    merged = []
    for repo, numbers in CONTRIBUTIONS:
        owner, name = repo.split("/")
        fields = "".join(f"pr{n}: pullRequest(number: {n}) {{ number title mergedAt author {{ login }} }}" for n in numbers)
        query = f'{{ repository(owner: "{owner}", name: "{name}") {{ {fields} }} }}'
        out = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], check=True, capture_output=True, text=True)
        prs = list(json.loads(out.stdout)["data"]["repository"].values())
        for pr in prs:
            if not pr["mergedAt"] or pr["author"]["login"] != USER:
                raise SystemExit(f'{repo}#{pr["number"]} is not a merged PR by {USER}')
        merged.append((repo, prs))
    return merged


def alt_merged(merged):
    return "Merged upstream: " + "; ".join(f"{repo} " + ", ".join(f'#{p["number"]} {p["title"]}' for p in prs) for repo, prs in merged)


def image(src, href, alt, width="100%"):
    return f'<a href="{href}"><img alt="{escape(alt)}" src="assets/{src}" width="{width}"></a>'


def themed(slug, href, alt):
    return (f'<a href="{href}"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/{slug}-dark.svg">'
            f'<img alt="{escape(alt)}" src="assets/{slug}-light.svg"></picture></a>')


def readme(merged):
    repo, prs = merged[0]
    if len(merged) == 1 and len(prs) == 1:
        merged_href = f'https://github.com/{repo}/pull/{prs[0]["number"]}'
    else:
        merged_href = f"https://github.com/search?q=is%3Apr+is%3Amerged+author%3A{USER}&type=pullrequests"
    tiles = [image(f'work-{p["slug"]}.svg', p["href"], f'{p["name"]}. {p["blurb"]} {p["note"]}.', "50%") for p in PROJECTS]
    blocks = [
        image("opener.svg", "https://chaoqiluo.com/", " ".join(HEADLINE)),
        # No whitespace between tiles: a space would push the second tile of each row onto its own line.
        tiles[0] + tiles[1] + "<br>" + tiles[2] + tiles[3],
        image("merged.svg", merged_href, alt_merged(merged)),
        '<p align="center">' + " ".join(themed(f"link-{slug}", href, label) for slug, label, href in LINKS) + "</p>",
    ]
    return "\n\n".join(blocks) + "\n"


def main():
    merged = fetch_merged()
    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("*.svg"):
        old.unlink()
    files = {"opener.svg": opener(), "merged.svg": merged_plate(merged)}
    files.update({f'work-{p["slug"]}.svg': tile(p, i) for i, p in enumerate(PROJECTS)})
    for slug, label, _ in LINKS:
        for theme, (ink, rule) in LINK_INK.items():
            files[f"link-{slug}-{theme}.svg"] = link(label, ink, rule)
    for name, content in files.items():
        (ASSETS / name).write_text(content)
    (ROOT / "README.md").write_text(readme(merged))
    print(f"{len(files)} SVGs, {sum(len(c) for c in files.values()) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
