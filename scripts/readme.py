#!/usr/bin/env python3
"""Print the profile README as a linocut, then write README.md and assets/.

Each picture is a carved black block: lines are cut away to show the paper, and red comes from a second block.
Every word is converted to glyph outlines, so the SVGs need no fonts at view time.
Fonts come from the Google Fonts subsetting API and are cached in .cache/fonts.
Merged pull requests come from GitHub search, so a rerun picks up new ones.
The starwave tile is drawn from the waves starwave published that day, so a rerun redraws it.
Needs: pip install fonttools uharfbuzz numpy, and an authenticated gh CLI.
"""
import hashlib
import json
import math
import re
import subprocess
import urllib.parse
import urllib.request
from collections import defaultdict
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

HEADLINE = ["Research engineer intern at Z.AI.", "M.S. student at Penn."]
PROJECTS = [
    dict(slug="argus", name="Argus", href="https://github.com/Chaoqi31/argus-truth-engine",
         blurb="Audits AI-generated content, claim by claim.", note="Best Technical Implementation, UCWS Singapore 2026"),
    dict(slug="nemotron", name="Nemotron Reasoning", href="https://github.com/Chaoqi31/nemotron-reasoning-lora",
         blurb="Single-epoch LoRA on Nemotron-3-Nano-30B-A3B.", note="Kaggle silver medal, 33rd of 4,182"),
    dict(slug="text2sql", name="text2sql-agent-rl", href="https://github.com/Chaoqi31/text2sql-agent-rl",
         blurb="An RL-trained agent that explores the database first.", note="+7.2 execution accuracy on BIRD dev"),
    dict(slug="saiddone", name="SaidDone", href="https://github.com/Chaoqi31/saiddone",
         blurb="Local-first voice dictation for macOS.", note="Free, private, offline by default"),
]
# One project gets a full-width tile; its picture is drawn from the data it publishes each day.
FEATURE = dict(slug="starwave", name="starwave", href="https://github.com/Chaoqi31/starwave",
               blurb="GitHub Trending shows the repos that are already famous. starwave shows the waves forming right now.",
               note="Updated daily, zero dependencies")
STARWAVE_DATA = "https://chaoqi31.github.io/starwave/latest.json"
LINKS = [
    ("website", "Website", "https://chaoqiluo.com/"),
    ("scholar", "Google Scholar", "https://scholar.google.com/citations?user=eOwS19sAAAAJ&hl=en"),
    ("linkedin", "LinkedIn", "https://www.linkedin.com/in/chaoqi-luo-4317bb2b7/"),
    ("email", "Email", "mailto:luo31@seas.upenn.edu"),
]
MERGED_QUERY = f"is:pr is:merged author:{USER} -user:{USER}"
MERGED_HREF = "https://github.com/search?" + urllib.parse.urlencode({"q": MERGED_QUERY, "type": "pullrequests"})

W, HALF, GUTTER = 846, 423, 22
# GitHub sets images on the text baseline, which leaves this much space under each row of tiles.
BASELINE_GAP = 6
PAPER, BLACK, RED = "#EEE5D1", "#1A1714", "#C4412B"
HATCH = "url(#hatch)"
LINK_INK = {"light": BLACK, "dark": PAPER}
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


def text_right(path, s, size, right, y, fill):
    return text(path, s, size, right - Line(path, s, size).width, y, fill)


def svg(w, h, label, body, defs="", style=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(w)}" height="{num(h)}" viewBox="0 0 {num(w)} {num(h)}" '
        f'role="img" aria-label="{escape(label)}"><defs>{defs}</defs>{f"<style>{style}</style>" if style else ""}{body}</svg>\n'
    )


def rough(fid, scale, freq, seed):
    """Nudge edges with low-frequency noise so machine-straight marks read as carved by hand."""
    return (
        f'<filter id="{fid}" x="-3%" y="-10%" width="106%" height="120%">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{seed}" result="n"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="n" scale="{scale}" xChannelSelector="R" yChannelSelector="G"/></filter>'
    )


DEFS = (
    rough("rough", 2.6, ".045", 9) + rough("block", 4, ".03", 21)
    # Paper tooth: sparse brown specks from fractal noise.
    + '<filter id="grain" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
    '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3" stitchTiles="stitch"/>'
    '<feColorMatrix values="0 0 0 0 .227 0 0 0 0 .165 0 0 0 0 .094 1.7 0 0 0 -.78"/>'
    '<feComponentTransfer><feFuncA type="linear" slope=".16"/></feComponentTransfer></filter>'
    '<pattern id="hatch" width="4.2" height="4.2" patternUnits="userSpaceOnUse" patternTransform="rotate(40)">'
    f'<rect width="4.2" height="4.2" fill="{PAPER}"/><rect width="4.2" height="1.5" fill="{BLACK}"/></pattern>'
)


def rect(x, y, w, h, fill, extra=""):
    return f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" fill="{fill}"{extra}/>'


def paper(x, y, w, h):
    return rect(x, y, w, h, PAPER) + rect(x, y, w, h, "#000", ' filter="url(#grain)"')


def block(x, y, w, h):
    return f'<g filter="url(#block)">{rect(x, y, w, h, BLACK)}</g>'


# ---------------------------------------------------------------- marks

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
    """A path whose curvature starts as noise and is pulled straight: a tangle that settles into a horizon."""
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


def sample(points, per=8):
    """Points along the open curve catmull() draws through `points`."""
    p = np.array(points, float)
    p = np.vstack([p[0], p, p[-1]])
    t = np.linspace(0, 1, per, endpoint=False)[:, None]
    out = []
    for i in range(1, len(p) - 2):
        c1, c2 = p[i] + (p[i + 1] - p[i - 1]) / 6, p[i + 1] - (p[i + 2] - p[i]) / 6
        out += list((1 - t) ** 3 * p[i] + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t ** 2 * c2 + t ** 3 * p[i + 1])
    return np.array(out + [p[-2]])


def cut(points, widths):
    """The outline of a gouge cut along `points`, as wide as `widths` at each point, so a cut can swell and taper."""
    d = np.gradient(points, axis=0)
    side = np.stack([-d[:, 1], d[:, 0]], 1) / np.hypot(d[:, 0], d[:, 1])[:, None] * (np.asarray(widths) / 2)[:, None]
    return polyline(np.vstack([points + side, (points - side)[::-1]])) + "Z"


def wobbly(points, amp, seed):
    p = np.array(points, float)
    n = len(p)
    p[:, 0] += amp * noise(n, seed, max(3, n // 8))
    p[:, 1] += amp * noise(n, seed + 50, max(3, n // 8))
    return p


def ellipse(cx, cy, rx, ry, n=48, a0=0.0, a1=2 * math.pi):
    return [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(a0, a1, n)]


def shape(points, fill, seed, amp=1.1, sharp=False):
    """A shape left standing on the block, rimmed in black."""
    p = wobbly(points, amp, seed)
    d = polyline(p) + "Z" if sharp else catmull(p, closed=True)
    return f'<path d="{d}" fill="{fill}" stroke="{BLACK}" stroke-width="2.8" stroke-linejoin="round"/>'


def line(points, seed, width, amp, color=PAPER, dotted=False):
    """Paper-colored by default: a line cut out of the black."""
    dash = ' stroke-dasharray="0.5 7"' if dotted else ""
    return (f'<path d="{catmull(wobbly(points, amp, seed))}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round"{dash}/>')


def dot(x, y, r, fill):
    return f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(r)}" fill="{fill}"/>'


def gouges(x0, y0, x1, y1, rows, seed):
    """Short tapered cuts along wavy rows, thinning out toward the middle where the subject sits."""
    rng = np.random.default_rng(seed)
    cuts = []
    for j in range(rows):
        yy = y0 + (j + .5) * (y1 - y0) / rows
        middle = 1 - abs(2 * (j + .5) / rows - 1)
        x = x0 + rng.uniform(0, 30)
        while x < x1:
            ln, w = rng.uniform(5, 18), rng.uniform(.6, 1.5)
            ang, y = rng.normal(0, .1) + .12 * math.cos(x / 50 + j), yy + 3.5 * math.sin(x / 45 + j * 1.7) + rng.normal(0, 1.5)
            ts = np.linspace(0, 1, 7)
            fx, fy = math.cos(ang) * ln, math.sin(ang) * ln
            nx, ny = -math.sin(ang), math.cos(ang)
            side = [(x + fx * t + nx * w * math.sin(math.pi * t), y + fy * t + ny * w * math.sin(math.pi * t)) for t in ts]
            back = [(x + fx * t - nx * w * math.sin(math.pi * t), y + fy * t - ny * w * math.sin(math.pi * t)) for t in ts[::-1]]
            cuts.append(polyline(side + back) + "Z")
            x += ln + rng.uniform(4, 30) * (1 + 2.2 * middle ** 2)
    return f'<path fill="{PAPER}" d="{"".join(cuts)}"/>'


# ---------------------------------------------------------------- pictures, one per project

def eye(cx, cy):
    """Argus, the watchman with a hundred eyes."""
    top = [(cx - 70 + 140 * s, cy - 44 * math.sin(math.pi * s)) for s in np.linspace(0, 1, 30)]
    bottom = [(cx + 70 - 140 * s, cy + 34 * math.sin(math.pi * s)) for s in np.linspace(0, 1, 30)][1:-1]
    out = shape(top + bottom, PAPER, 1) + shape(ellipse(cx + 4, cy - 3, 25, 25), RED, 2)
    out += dot(cx + 5, cy - 3, 10, BLACK) + dot(cx + 12, cy - 10, 3.6, PAPER)
    for i, s in enumerate(np.linspace(0.14, 0.86, 7)):
        x, y = cx - 70 + 140 * s, cy - 44 * math.sin(math.pi * s)
        ang = math.atan2(-(44 * math.pi * math.cos(math.pi * s)), 140) - math.pi / 2
        out += line([(x, y - 2), (x + 13 * math.cos(ang), y - 2 + 13 * math.sin(ang))], 10 + i, 2.8, 0.3)
    return out


def medal(cx, cy):
    """A silver medal hanging from crossed ribbons that run off the top of the block."""
    top, knot, disc = cy - 110, cy - 22, cy + 16
    out = shape([(cx - 58, top), (cx - 32, top), (cx + 12, knot), (cx - 10, knot + 6)], RED, 3)
    out += shape([(cx + 58, top), (cx + 32, top), (cx - 12, knot), (cx + 10, knot + 6)], HATCH, 4)
    out += shape(ellipse(cx, disc, 42, 42, 56), HATCH, 5) + shape(ellipse(cx, disc, 29, 29, 44), "none", 6)
    star = [(cx + (15 if i % 2 == 0 else 6.5) * math.sin(i * math.pi / 5), disc - (15 if i % 2 == 0 else 6.5) * math.cos(i * math.pi / 5)) for i in range(10)]
    return out + shape(star, BLACK, 7, amp=0.5, sharp=True)


def database(cx, cy):
    """A database, and the dotted trail of an agent poking around it before it answers."""
    rx, ry, top, bot = 50, 14, cy - 44, cy + 44
    body = [(cx - rx, top), (cx - rx, bot)] + [(cx - rx * math.cos(a), bot + ry * math.sin(a)) for a in np.linspace(0, math.pi, 30)] + [(cx + rx, top)]
    trail = [(cx - 150 + 8 * s + 30 * math.sin(s / 7), cy + 58 - 1.6 * s + 16 * math.sin(s / 5)) for s in np.linspace(0, 62, 60)]
    out = line(trail, 14, 3, 0.8, dotted=True) + shape(body, PAPER, 8) + shape(ellipse(cx, top, rx, ry, 40), RED, 9)
    for i, y in enumerate((cy - 15, cy + 14)):
        out += line([(cx - rx * math.cos(a), y + ry * math.sin(a)) for a in np.linspace(0, math.pi, 24)], 11 + i, 2.5, 0.5, BLACK)
    return out


def voice(cx, cy):
    """A voice waveform turning into a page of text."""
    out = ""
    for i, hgt in enumerate([10, 24, 46, 30, 62, 38, 22, 44, 16]):
        x = cx - 128 + 13 * i
        out += line([(x, cy - hgt / 2), (x, cy + hgt / 2)], 20 + i, 3.7, 0.4)
    out += line([(cx - 2, cy), (cx + 26, cy)], 31, 2.8, 0.3)
    out += line([(cx + 17, cy - 8), (cx + 27, cy), (cx + 17, cy + 8)], 32, 2.8, 0.3)
    out += shape([(cx + 44, cy - 42), (cx + 138, cy - 42), (cx + 138, cy + 42), (cx + 44, cy + 42)], PAPER, 33, amp=0.7)
    for i, (w, y) in enumerate(((70, -20), (58, -2), (40, 16))):
        out += line([(cx + 58, cy + y), (cx + 58 + w, cy + y)], 34 + i, 2.8, 0.5, BLACK)
    return out + line([(cx + 104, cy + 9), (cx + 104, cy + 24)], 38, 2.8, 0.2, BLACK)


DRAW = {"argus": eye, "nemotron": medal, "text2sql": database, "saiddone": voice}


def star(cx, cy, r, seed):
    points = [(cx + (r if i % 2 == 0 else r * .43) * math.sin(i * math.pi / 5),
               cy - (r if i % 2 == 0 else r * .43) * math.cos(i * math.pi / 5)) for i in range(10)]
    return f'<path d="{polyline(wobbly(points, r * .06, seed))}Z" fill="{RED}"/>'


def ridges(x0, x1, horizon, front, waves):
    """A sea of carved swells, one per wave, each shaped by its stars per day over the last 14 days.

    The wave starwave ranks first swells nearest, the rest recede toward the horizon.
    A swell's height is the log of its best day, and it is filled black so it hides the swells behind it.
    Its crest is cut wider where it stands higher and nested cuts follow it up, so a calm day stays one thin line.
    A red star hangs over the first wave's best day.
    """
    xs = np.linspace(x0 + 70, x1 - 40, len(waves[0]["daily"]))
    tallest = math.log1p(max(max(w["daily"]) for w in waves) or 1)
    out, crests = "", []
    for k in reversed(range(len(waves))):
        daily, depth = waves[k]["daily"], k / max(1, len(waves) - 1)
        peak, near = max(daily) or 1, 1 - .6 * depth
        base = horizon + (front - horizon) * (1 - depth) ** 1.3
        height = 110 * near * math.log1p(peak) / tallest
        crest = [(x0, base), (x0 + 36, base)] + [(x, base - height * v / peak) for x, v in zip(xs, daily)] + [(x1, base)]
        p = sample(wobbly(crest, .7, 80 + k))
        rise = np.clip((base - p[:, 1]) / height, 0, 1)
        ends = np.clip(30 * np.minimum(np.linspace(0, 1, len(p)), np.linspace(1, 0, len(p))), 0, 1)
        hand = lambda j: np.clip(1 + .25 * noise(len(p), 70 + 10 * k + j, 24), .6, 1.4)  # noqa: E731
        out += f'<path d="{polyline(p)}L{num(x1)} {num(base + 60)}L{num(x0)} {num(base + 60)}Z" fill="{BLACK}"/>'
        cuts = cut(p, ends * hand(0) * (1 + 2.6 * near * rise ** .6))
        for j in range(1, int(height / 22) + 1):
            cuts += cut(p + [0, 6 * near * j], near * hand(j) * 1.9 * np.clip((rise - .15 * j) / .4, 0, 1) ** .8)
        out += f'<path d="{cuts}" fill="{PAPER}"/>'
        crests.append(p)
    x = xs[int(np.argmax(waves[0]["daily"]))]
    return out + star(x, min(np.interp(x, p[:, 0], p[:, 1]) for p in crests) - 20, 11, 90)


def merges(x0, x1, y, prs, biggest, seed):
    """A trunk, and for each merged pull request a red branch that leaves it and comes back.

    Taller branches changed more lines. Branches narrow once a repository has too many to fit.
    """
    step = min(23.2, (x1 - x0 - 16) / len(prs))
    w = step * 19 / 23.2
    out = line([(x, y) for x in np.linspace(x0, x1, 60)], seed, 2.4, 0.5, BLACK)
    for k, pr in enumerate(prs):
        a = x0 + 8 + k * step
        rise = 5 + 13 * math.sqrt((pr["additions"] + pr["deletions"]) / biggest)
        out += line([(a + w * t, y - rise * math.sin(math.pi * t)) for t in np.linspace(0, 1, 12)], seed + 1 + k, 2.1, 0.25, RED)
        out += dot(a + w, y, 2.5, RED)
    return out


# ---------------------------------------------------------------- plates

REVEAL = (
    "@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
    "@keyframes fade{from{opacity:0}to{opacity:1}}"
    "@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
)


def opener(seed=33):
    """Noise, then one cut line that tangles and settles into a horizon, then the headline."""
    h = 430
    path = gesture(104, W - 44, 150, seed)
    sx, sy = path[0]
    rng = np.random.default_rng(seed)
    dots = "".join(
        f'<circle cx="{num(sx + dx)}" cy="{num(sy + dy)}" r="{num(r * 1.15)}"/>'
        for dx, dy, r in zip(rng.normal(0, 30, 70), rng.normal(0, 22, 70), rng.uniform(1, 2.3, 70))
    )
    body = paper(0, 0, W, h) + block(16, 16, W - 32, 268)
    body += f'<g filter="url(#rough)"><g class="dots">{gouges(24, 24, W - 24, 276, 16, 5)}</g><g class="dots" fill="{RED}">{dots}</g>'
    body += (f'<path class="pen" pathLength="1" d="{polyline(path)}" fill="none" stroke="{PAPER}" stroke-width="3.8" '
             'stroke-linecap="round" stroke-linejoin="round"/></g>')
    for i, s in enumerate(HEADLINE):
        body += text(DISPLAY, s, 36, 31, 344 + 45 * i, BLACK, -0.01, f"h{i}")
    style = REVEAL + (
        "@media (prefers-reduced-motion:no-preference){"
        ".dots{animation:fade 1s ease .1s both}"
        ".pen{stroke-dasharray:1;animation:draw 3.4s cubic-bezier(.45,.05,.3,1) .7s both}"
        ".h0{animation:rise 1.2s ease 3s both}.h1{animation:rise 1.2s ease 3.3s both}}"
    )
    return svg(W, h, " ".join(HEADLINE), body, DEFS, style)


def tile(p, i):
    """Tiles sit 50% wide with no whitespace between them, so each SVG carries its own half of the gutter."""
    ph, vgap = 300, (GUTTER - BASELINE_GAP) / 2
    x, y = (0 if i % 2 == 0 else GUTTER / 2), (0 if i < 2 else vgap)
    pw = HALF - GUTTER / 2
    bx, by, bw, bh = x + 16, y + 16, pw - 32, 166
    body = paper(x, y, pw, ph) + block(bx, by, bw, bh)
    body += (f'<g clip-path="url(#tile)" filter="url(#rough)">{gouges(bx, by, bx + bw, by + bh, 9, 30 + i)}'
             f'{DRAW[p["slug"]](x + pw / 2, y + 100)}</g>')
    body += text(DISPLAY, p["name"], 27, x + 32, y + 226, BLACK, -0.01)
    body += text(TEXT, p["blurb"], 14.5, x + 32, y + 252, BLACK)
    body += text(ITALIC, p["note"], 14, x + 32, y + ph - 22, RED)
    clip = f'<clipPath id="tile"><rect x="{num(bx)}" y="{num(by)}" width="{num(bw)}" height="{bh}"/></clipPath>'
    return svg(HALF, ph + vgap, f'{p["name"]}. {p["blurb"]} {p["note"]}.', body, clip + DEFS)


def feature(p, waves):
    """The full-width tile: the same block and caption as a tile, with the waves starwave found today as its picture."""
    ph, bx, by, bw, bh = 324, 16, 16, W - 32, 190
    body = paper(0, 0, W, ph) + block(bx, by, bw, bh)
    body += (f'<g clip-path="url(#tile)" filter="url(#rough)">{gouges(bx, by, bx + bw, by + 90, 5, 44)}'
             f'{ridges(bx + 8, bx + bw - 8, by + 88, by + bh - 18, waves)}</g>')
    body += text(DISPLAY, p["name"], 27, 32, by + bh + 44, BLACK, -0.01)
    body += text(TEXT, p["blurb"], 14.5, 32, by + bh + 70, BLACK)
    body += text(ITALIC, p["note"], 14, 32, ph - 22, RED)
    clip = f'<clipPath id="tile"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}"/></clipPath>'
    return svg(W, ph, f'{p["name"]}. {p["blurb"]} {p["note"]}.', body, clip + DEFS)


def short(n):
    """Star counts the way GitHub abbreviates them: 950, 4.5k, 76.8k, 109k."""
    return str(n) if n < 1000 else f"{n / 1000:.1f}k" if n < 100000 else f"{n / 1000:.0f}k"


def score(merged):
    """One row per repository, busiest first: its name, its stars, and a trunk with a branch per merged pull request."""
    total = sum(len(prs) for _, prs, _ in merged)
    biggest = max(pr["additions"] + pr["deletions"] for _, prs, _ in merged for pr in prs)
    body = paper(0, 0, W, 84 + 50 * len(merged))
    body += text(ITALIC, "Merged upstream", 15, 32, 44, BLACK) + text_right(ITALIC, f"{total} pull requests", 15, W - 32, 44, BLACK)
    for i, (repo, prs, stars) in enumerate(merged):
        y = 92 + 50 * i
        body += text(DISPLAY, repo, min(19, 19 * 312 / Line(DISPLAY, repo, 19).width), 32, y, BLACK)
        body += text(TEXT, f"{len(prs)} merged, {short(stars)} stars", 12.5, 32, y + 18, BLACK)
        body += f'<g filter="url(#rough)">{merges(352, W - 32, y + 2, prs, biggest, 60 + 7 * i)}</g>'
    return svg(W, 84 + 50 * len(merged), alt_merged(merged), body, DEFS)


def link(label, ink):
    w = Line(TEXT, label, 16).width + 20
    body = text(TEXT, label, 16, 10, 21, ink)
    body += line([(10 + (w - 20) * t, 27) for t in np.linspace(0, 1, 12)], len(label), 1.2, 0.5, RED)
    return svg(w, 36, label, body)


# ---------------------------------------------------------------- README

def fetch_merged():
    """My pull requests merged into other people's repositories, as (repo, prs, stars), busiest repository first."""
    query = (
        'query($endCursor: String) { search(query: "' + MERGED_QUERY + '", type: ISSUE, first: 100, after: $endCursor) {'
        " pageInfo { hasNextPage endCursor }"
        " nodes { ... on PullRequest { number additions deletions repository { nameWithOwner stargazerCount } } } } }"
    )
    out = subprocess.run(["gh", "api", "graphql", "--paginate", "-f", f"query={query}", "--jq", ".data.search.nodes[]"],
                         check=True, capture_output=True, text=True).stdout
    repos, stars = defaultdict(list), {}
    for pr in map(json.loads, out.splitlines()):
        repo = pr["repository"]["nameWithOwner"]
        repos[repo].append(pr)
        stars[repo] = pr["repository"]["stargazerCount"]
    rows = [(repo, sorted(prs, key=lambda pr: pr["number"]), stars[repo]) for repo, prs in repos.items()]
    return sorted(rows, key=lambda row: (-len(row[1]), -row[2]))


def fetch_waves():
    """The waves starwave ranks today, busiest first, with clusters it flags as coordinated left out."""
    with urllib.request.urlopen(STARWAVE_DATA) as r:
        waves = json.load(r)["waves"]
    return [w for w in waves if not w["flags"]][:6]


def alt_merged(merged):
    total = sum(len(prs) for _, prs, _ in merged)
    return f"Merged upstream, {total} pull requests: " + "; ".join(f"{repo}, {len(prs)}" for repo, prs, _ in merged)


def image(src, href, alt, width="100%"):
    return f'<a href="{href}"><img alt="{escape(alt)}" src="assets/{src}" width="{width}"></a>'


def themed(slug, href, alt):
    return (f'<a href="{href}"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/{slug}-dark.svg">'
            f'<img alt="{escape(alt)}" src="assets/{slug}-light.svg"></picture></a>')


def readme(merged):
    alt = lambda p: f'{p["name"]}. {p["blurb"]} {p["note"]}.'  # noqa: E731
    tiles = [image(f'work-{p["slug"]}.svg', p["href"], alt(p), "50%") for p in PROJECTS]
    blocks = [
        image("opener.svg", "https://chaoqiluo.com/", " ".join(HEADLINE)),
        # No whitespace between tiles: a space would push the second tile of each row onto its own line.
        tiles[0] + tiles[1] + "<br>" + tiles[2] + tiles[3],
        image(f'work-{FEATURE["slug"]}.svg', FEATURE["href"], alt(FEATURE)),
        image("merged.svg", MERGED_HREF, alt_merged(merged)),
        '<p align="center">' + " ".join(themed(f"link-{slug}", href, label) for slug, label, href in LINKS) + "</p>",
    ]
    return "\n\n".join(blocks) + "\n"


def main():
    merged, waves = fetch_merged(), fetch_waves()
    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("*.svg"):
        old.unlink()
    files = {"opener.svg": opener(), "merged.svg": score(merged), f'work-{FEATURE["slug"]}.svg': feature(FEATURE, waves)}
    files.update({f'work-{p["slug"]}.svg': tile(p, i) for i, p in enumerate(PROJECTS)})
    for slug, label, _ in LINKS:
        for theme, ink in LINK_INK.items():
            files[f"link-{slug}-{theme}.svg"] = link(label, ink)
    for name, content in files.items():
        (ASSETS / name).write_text(content)
    (ROOT / "README.md").write_text(readme(merged))
    print(f"{sum(len(prs) for _, prs, _ in merged)} merged PRs in {len(merged)} repos; "
          f"{len(files)} SVGs, {sum(len(c) for c in files.values()) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
