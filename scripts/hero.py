#!/usr/bin/env python3
"""Draw the README hero, assets/hero-{light,dark}.svg.

Straight flow lines carry a Gaussian cloud into the name, the way a rectified flow moves noise onto data.
Text is converted to glyph outlines, so the SVGs need no fonts at view time.
Fonts come from the Google Fonts subsetting API and are cached in .cache/fonts.
Needs: pip install fonttools uharfbuzz numpy pillow
"""
import hashlib
import re
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache/fonts"
W, H = 848, 355

NAME = "Chaoqi Luo"
NAME_ZH = "罗朝旗"
TAGLINE = "Building LLM agents at Z.AI. Speeding up video generation at Penn."

THEMES = {
    "light": dict(frame="#f6f8fa", border="#d1d9e0", ink="#1f2328", muted="#59636e", flow=(".05", ".16")),
    "dark": dict(frame="#151b23", border="#3d444d", ink="#f0f6fc", muted="#9198a1", flow=(".07", ".26")),
}


def font(family, text):
    """Download a TTF subset holding just `text`. Google serves TTF to a non-browser user agent."""
    path = CACHE / (hashlib.sha1(f"{family}|{text}".encode()).hexdigest()[:12] + ".ttf")
    if not path.exists():
        query = urllib.parse.urlencode({"family": family, "text": text})
        css = urllib.request.urlopen(f"https://fonts.googleapis.com/css2?{query}").read().decode()
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(re.search(r"url\((.+?)\)", css)[1]).read())
    return path


class Line:
    """One shaped run of text: glyph outlines placed by HarfBuzz, kerning included."""

    def __init__(self, font_path, text, size):
        face = hb.Face(hb.Blob.from_file_path(str(font_path)))
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(hb.Font(face), buf)
        self.font_path, self.text, self.size = font_path, text, size
        self.scale = size / face.upem
        tt = TTFont(font_path)
        self.glyphset, order = tt.getGlyphSet(), tt.getGlyphOrder()
        self.glyphs, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            self.glyphs.append((order[info.codepoint], info.cluster, x + pos.x_offset, pos.y_offset))
            x += pos.x_advance
        self.width = x * self.scale

    def path(self, x, y):
        pen = SVGPathPen(self.glyphset, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for name, _, gx, gy in self.glyphs:
            m = (self.scale, 0, 0, -self.scale, x + gx * self.scale, y - gy * self.scale)
            self.glyphset[name].draw(TransformPen(pen, m))
        return pen.getCommands()

    def mask(self, x, y, ss=4):
        """Rasterize the run at `ss`x supersampling, in the same place path(x, y) draws it."""
        img = Image.new("L", (W * ss, H * ss))
        draw = ImageDraw.Draw(img)
        pil = ImageFont.truetype(str(self.font_path), self.size * ss)
        for _, cluster, gx, _ in self.glyphs:
            draw.text(((x + gx * self.scale) * ss, y * ss), self.text[cluster], font=pil, fill=255, anchor="ls")
        return np.asarray(img) > 127


def hero(t, f, n=1400, seed=5):
    name, zh, tag = Line(f["name"], NAME, 72), Line(f["zh"], NAME_ZH, 28), Line(f["text"], TAGLINE, 17)
    nx, ny = W - 48 - zh.width - 18 - name.width, 170
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(name.mask(nx, ny))
    pick = rng.choice(len(xs), n, replace=False)
    target = np.stack([xs[pick], ys[pick]], 1) / 4 + rng.random((n, 2)) / 4
    source = rng.normal([100, 150], [26, 34], (n, 2))
    # Pairing both clouds in y order is the 1-D optimal transport coupling, so the lines barely cross.
    target, source = target[np.argsort(target[:, 1])], source[np.argsort(source[:, 1])]
    flow = "".join(f"M{a:.1f} {b:.1f}L{c:.1f} {d:.1f}" for (a, b), (c, d) in zip(source, target))
    dots = "".join(f"M{a:.1f} {b:.1f}h0" for a, b in source)
    lo, hi = t["flow"]
    lines = [(name, nx, ny, t["ink"]), (zh, nx + name.width + 18, ny, t["muted"]), (tag, nx + 3, 296, t["ink"])]
    text = "".join(f'<path fill="{color}" d="{line.path(x, y)}"/>' for line, x, y, color in lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{NAME} ({NAME_ZH}). {TAGLINE}"><defs>'
        f'<linearGradient id="fade" gradientUnits="userSpaceOnUse" x1="100" x2="{nx + name.width}" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{t["ink"]}" stop-opacity="{lo}"/>'
        f'<stop offset="1" stop-color="{t["ink"]}" stop-opacity="{hi}"/></linearGradient></defs>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["frame"]}" stroke="{t["border"]}"/>'
        f'<path d="{flow}" stroke="url(#fade)" stroke-width=".6" fill="none"/>'
        f'<path d="{dots}" stroke="{t["muted"]}" stroke-opacity=".7" stroke-width="1.5" stroke-linecap="round"/>'
        f"{text}</svg>\n"
    )


def main():
    f = {
        "name": font("Archivo:wdth,wght@125,600", NAME),
        "text": font("Archivo:wdth,wght@100,400", TAGLINE),
        "zh": font("Noto Serif SC:wght@500", NAME_ZH),
    }
    for theme, t in THEMES.items():
        out = ROOT / f"assets/hero-{theme}.svg"
        out.write_text(hero(t, f))
        print(out.relative_to(ROOT), f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
