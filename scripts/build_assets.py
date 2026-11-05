#!/usr/bin/env python3
"""
Builds every SVG in ../assets for the LeoL6 profile README.

The look mirrors leonardolees.com: warm near-black cards (#20201d) with a
#41403a border, the #fff672 accent bar under headings, #f0c465 nav gold and
the Red Hat Text / Red Hat Mono typefaces.

GitHub serves repo images with a CSP that blocks web fonts inside SVGs, so all
text is converted to vector outlines here. Edit the CONTENT section below and
re-run:

    pip install fonttools brotli uharfbuzz
    python3 scripts/build_assets.py
"""
import html
import io
import re
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
OUT = HERE.parent / "assets"

C = dict(
    bg="#141412", box="#20201d", inner="#1b1b19", border="#41403a",
    nav="#2e2e2a", accent="#fff672", gold="#f0c465", text="#dbdbdb",
    muted="#b8b8b8", label="#9b8f8f", white="#ffffff",
    light_text="#141412", light_bar="#e9c13a",
)

# --------------------------------------------------------------------------
# CONTENT — edit here
# --------------------------------------------------------------------------
HEADER = dict(
    hello="HELLO, I'M",
    name="Leonardo Lees",
    role="Software Developer",
    tagline=("Self-taught full-stack developer with a passion for systems "
             "architecture, security engineering & embedded software."),
    nav=["About", "Portfolio", "Talks"],
    terminal_title="leo@leonardolees.com",
    terminal=[
        [("$ ", "gold"), ("whoami", "text")],
        [("leo — full-stack & systems dev", "muted")],
        [("$ ", "gold"), ("cat focus.txt", "text")],
        [("embedded · rust · full-stack web", "muted")],
        [("$ ", "gold"), ("ls interests/", "text")],
        [("rf/  crypto/  hardware/  contracts/", "muted")],
        [("$ ", "gold")],
    ],
)

LINKS = [
    ("website", "globe", "leonardolees.com"),
    ("linkedin", "person", "LinkedIn"),
    ("x", "at", "@leo_f_lees"),
    ("email", "mail", "contact@leonardolees.com"),
]

HEADINGS = {
    "about": "About Me",
    "stack": "What I Work With",
    "projects": "Featured Projects",
    "talks": "Talks",
    "contact": "Get In Touch",
}

STACK_COLUMNS = [
    ("What I'm Good At", ["Embedded Development", "Rust Application Development",
                          "Full-Stack Web Development"]),
    ("Current Interests", ["RF Engineering", "Cryptography", "Hardware Development",
                           "Systems Architecture", "Smart Contracts"]),
    ("Off The Keyboard", ["Guitar", "Messing with circuits", "Cinematography",
                          "Three pugs"]),
]

TOOLBOX = [
    ("LANGUAGES", ["Rust", "C", "C++", "TypeScript", "JavaScript", "Python", "Java", "Lua"]),
    ("EMBEDDED & RF", ["ESP32", "ESP32-S3", "Arduino", "LoRa", "SPI / I2C", "M5Stack"]),
    ("CRYPTOGRAPHY", ["X25519", "XSalsa20-Poly1305", "BLAKE2b", "TweetNaCl", "Monocypher"]),
    ("WEB & APPS", ["React", "Vite", "FastAPI", "Leaflet", "WebSockets", "egui", "Swing", "MySQL"]),
]

PROJECTS = [
    dict(slug="carrier-pigeon", icon="radio", lang="C++ · JS",
         title="Carrier Pigeon",
         desc=("Decentralized, end-to-end encrypted messaging over LoRa on the "
               "ESP32. Runs as standalone handheld firmware or with a "
               "browser-based client."),
         tags=["ESP32-S3", "LoRa", "X25519", "AEAD"]),
    dict(slug="phisher", icon="hook", lang="C",
         title="Phisher",
         desc=("An evil captive portal for the ESP32 that shows how easily open "
               "Wi-Fi gets abused, with a live admin panel. Built for "
               "education and demos."),
         tags=["ESP32", "Captive Portal", "DNS", "WebSockets"]),
    dict(slug="triangle-gator", icon="triangle", lang="Rust",
         title="Triangle Gator",
         desc=("Desktop tool that trilaterates the physical location of Wi-Fi "
               "access points from signal strength. Built to support my "
               "ATLSECCON talk."),
         tags=["Rust", "egui", "nalgebra", "RF"]),
    dict(slug="sceptre", icon="cloud", lang="TypeScript · Python",
         title="Sceptre Weather Dashboard",
         desc=("Hour-by-hour forecasts built from 30 years of public NASA "
               "weather data, using weighted averages with anomaly awareness. "
               "NASA Space Apps 2025."),
         tags=["React", "FastAPI", "Leaflet", "NASA data"]),
    dict(slug="obj-renderer", icon="cube", lang="C++",
         title="Obj Renderer",
         desc=("A standalone .obj 3D renderer in under 1,700 lines of C++ with "
               "shaded and wireframe modes, using only rudimentary libraries."),
         tags=["C++", "Win32", "3D Graphics"]),
    dict(slug="roblox-admin-panel", icon="terminal", lang="Lua",
         title="Roblox Admin Panel",
         desc=("Co-developed in-game admin panel with a full command system "
               "and Discord webhook integration for logging."),
         tags=["Lua", "Roblox", "Webhooks"]),
]

TALKS = [
    dict(slug="atlseccon-2026", event="ATLSECCON 2026",
         title="“Carrier Pigeon”: Decentralized Communication with LoRa"),
    dict(slug="atlseccon-2025", event="ATLSECCON 2025",
         title="The Dangers of Public Wi-Fi"),
    dict(slug="bsides-halifax-2025", event="BSIDES HALIFAX 2025",
         title="“Carrier Pigeon”: Decentralized Communication with LoRa"),
    dict(slug="nasa-space-apps-2025", event="NASA SPACE APPS 2025",
         title="Sceptre Weather Dashboard"),
]


# --------------------------------------------------------------------------
# Text-to-outline engine
# --------------------------------------------------------------------------
class Font:
    def __init__(self, key, file):
        self.key = key
        tt = TTFont(FONTS / file)
        self.upem = tt["head"].unitsPerEm
        self.order = tt.getGlyphOrder()
        self.glyphset = tt.getGlyphSet()
        raw = TTFont(FONTS / file)
        raw.flavor = None
        buf = io.BytesIO()
        raw.save(buf)
        self.hb = hb.Font(hb.Face(buf.getvalue()))
        self._paths = {}

    def shape(self, s):
        b = hb.Buffer()
        b.add_str(s)
        b.guess_segment_properties()
        hb.shape(self.hb, b, {"kern": True, "liga": True})
        out, x = [], 0
        for info, pos in zip(b.glyph_infos, b.glyph_positions):
            name = self.order[info.codepoint]
            if name == ".notdef":
                raise ValueError(f"{self.key} has no glyph for a character in {s!r}")
            out.append((name, x + pos.x_offset, pos.y_offset))
            x += pos.x_advance
        return out, x

    def path(self, g):
        if g not in self._paths:
            pen = SVGPathPen(self.glyphset)
            self.glyphset[g].draw(pen)
            self._paths[g] = pen.getCommands()
        return self._paths[g]

    def width(self, s, size, ls=0.0):
        glyphs, adv = self.shape(s)
        return adv * size / self.upem + ls * max(len(glyphs) - 1, 0)


F = dict(
    r400=Font("t4", "red-hat-text-latin-400-normal.woff2"),
    r500=Font("t5", "red-hat-text-latin-500-normal.woff2"),
    r600=Font("t6", "red-hat-text-latin-600-normal.woff2"),
    m400=Font("m4", "red-hat-mono-latin-400-normal.woff2"),
    m500=Font("m5", "red-hat-mono-latin-500-normal.woff2"),
)


def wrap(s, font, size, maxw):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if font.width(trial, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class SVG:
    def __init__(self, w, h, label):
        self.w, self.h, self.label = w, h, label
        self.body, self.defs, self.css = [], {}, ""

    def add(self, s):
        self.body.append(s)

    def text(self, s, x, y, font, size, fill, anchor="start", ls=0.0, cls=None):
        glyphs, adv = font.shape(s)
        width = adv * size / font.upem + ls * max(len(glyphs) - 1, 0)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        k = size / font.upem
        lsu = ls / k
        uses = []
        for i, (g, gx, gy) in enumerate(glyphs):
            d = font.path(g)
            if not d:
                continue
            gid = f"{font.key}{re.sub(r'[^A-Za-z0-9_-]', '_', g)}"
            self.defs[gid] = d
            y_attr = f' y="{gy}"' if gy else ""
            uses.append(f'<use href="#{gid}" x="{gx + i * lsu:.0f}"{y_attr}/>')
        c = f' class="{cls}"' if cls else ""
        self.add(f'<g{c} fill="{fill}" transform="translate({x:.2f} {y:.2f}) '
                 f'scale({k:.5f} {-k:.5f})">{"".join(uses)}</g>')
        return width

    def save(self, path):
        defs = "".join(f'<path id="{k}" d="{v}"/>' for k, v in self.defs.items())
        css = f"<style>{self.css}</style>" if self.css else ""
        label = html.escape(self.label, quote=True)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
               f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" '
               f'aria-label="{label}"><title>{label}</title>{css}'
               f'<defs>{defs}</defs>{"".join(self.body)}</svg>\n')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")


# --------------------------------------------------------------------------
# Icons (24x24 grid, stroked)
# --------------------------------------------------------------------------
ICONS = {
    "radio": '<circle cx="12" cy="12" r="2" fill="{c}" stroke="none"/>'
             '<path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7'
             'M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8"/>',
    "hook": '<circle cx="15" cy="3.6" r="1.6"/>'
            '<path d="M15 5.2V14a5 5 0 0 1-10 0v-2l3 3"/>',
    "triangle": '<path d="M12 4L4 19h16z"/>'
                '<circle cx="12" cy="4" r="2" fill="{c}"/><circle cx="4" cy="19" r="2" fill="{c}"/>'
                '<circle cx="20" cy="19" r="2" fill="{c}"/><circle cx="12" cy="14" r="1.4" fill="{c}" stroke="none"/>',
    "cloud": '<path d="M7 15.5a3.8 3.8 0 0 1-.4-7.6 5.3 5.3 0 0 1 10.3-1 3.5 3.5 0 0 1 .6 8.6"/>'
             '<path d="M12.8 11.5l-2.3 4.2h3.2l-2.2 4.3"/>',
    "cube": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12L4 7.5M12 12v9"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/>'
                '<path d="M7.5 10l3 2.2-3 2.2M12.5 15h4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/>'
             '<path d="M3.5 9h17M3.5 15h17"/>',
    "person": '<circle cx="12" cy="8" r="3.6"/><path d="M4.8 20.5a7.2 7.2 0 0 1 14.4 0"/>',
    "at": '<circle cx="12" cy="12" r="3.6"/><path d="M15.6 9v4.2a2.4 2.4 0 0 0 4.8 0V12'
          'a8.4 8.4 0 1 0-3.3 6.7"/>',
    "mail": '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M4 7l8 6 8-6"/>',
    "arrow": '<path d="M7 17L17 7M9 7h8v8"/>',
}


def icon(name, x, y, size, color, sw=2.0):
    s = size / 24
    inner = ICONS[name].replace("{c}", color)
    return (f'<g transform="translate({x:.2f} {y:.2f}) scale({s:.4f})" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round">{inner}</g>')


def card(svg, x=1, y=1, w=None, h=None, rx=22, fill=C["box"]):
    w = (svg.w - 2) if w is None else w
    h = (svg.h - 2) if h is None else h
    svg.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{C["border"]}" stroke-width="1.2"/>')


def chip(svg, x, y, label, font, size, h, fg, bg, pad=12, dot=None, rx=8):
    tw = font.width(label, size)
    lead = 14 if dot else 0
    w = pad * 2 + tw + lead
    svg.add(f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="{h}" rx="{rx}" '
            f'fill="{bg}" stroke="{C["border"]}" stroke-width="1"/>')
    if dot:
        svg.add(f'<circle cx="{x + pad + 3.5:.2f}" cy="{y + h / 2}" r="3.5" fill="{dot}"/>')
    base = y + h / 2 + size * 0.36
    svg.text(label, x + pad + lead, base, font, size, fg)
    return w


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------
def build_header():
    W, H = 1000, 384
    s = SVG(W, H, f'{HEADER["name"]}, {HEADER["role"]}. {HEADER["tagline"]}')
    card(s, rx=24)

    # nav tab hanging from the top-right corner, like the site
    nf, nsz, gap, pad, th = F["r600"], 16, 28, 30, 54
    widths = [nf.width(n, nsz) for n in HEADER["nav"]]
    tw = sum(widths) + gap * (len(widths) - 1) + pad * 2
    tx = W - 1 - tw
    s.add(f'<path d="M{tx:.2f} 1H{W - 25}a24 24 0 0 1 24 24V{th}H{tx + 22:.2f}'
          f'a22 22 0 0 1-22-22z" fill="{C["nav"]}" stroke="{C["border"]}" stroke-width="1.2"/>')
    cx = tx + pad
    for i, (n, w) in enumerate(zip(HEADER["nav"], widths)):
        s.text(n, cx, 33, nf, nsz, C["gold"] if i == 0 else C["white"])
        cx += w + gap

    # left column
    x = 54
    s.text(HEADER["hello"], x, 112, F["r500"], 13.5, C["label"], ls=2.2)
    s.text(HEADER["name"], x, 176, F["r600"], 60, C["white"])
    s.add(f'<rect x="{x}" y="196" width="52" height="6" rx="3" fill="{C["accent"]}"/>')
    chip(s, x, 222, HEADER["role"], F["r500"], 15, 36, C["text"], C["nav"], pad=16, rx=10)
    ty = 300
    for line in wrap(HEADER["tagline"], F["r400"], 17.5, 440):
        s.text(line, x, ty, F["r400"], 17.5, C["muted"])
        ty += 27

    # terminal
    bx, by, bw, bh = 546, 88, 402, 250
    s.add(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="16" '
          f'fill="{C["inner"]}" stroke="{C["border"]}" stroke-width="1.2"/>')
    s.add(f'<path d="M{bx} {by + 36}H{bx + bw}" stroke="{C["border"]}" stroke-width="1.2"/>')
    for i, col in enumerate([C["border"], C["border"], C["accent"]]):
        s.add(f'<circle cx="{bx + 22 + i * 18}" cy="{by + 18}" r="5.5" fill="{col}"/>')
    s.text(HEADER["terminal_title"], bx + bw / 2, by + 23, F["m400"], 12.5, C["label"], anchor="middle")

    css = [".l{animation:in .35s ease-out backwards}",
           "@keyframes in{from{opacity:0}to{opacity:1}}",
           ".cur{animation:blink 1.1s steps(1) infinite}",
           "@keyframes blink{50%{opacity:0}}"]
    lx, ly, lh, fsz = bx + 24, by + 70, 25, 15
    for i, segs in enumerate(HEADER["terminal"]):
        css.append(f".l{i}{{animation-delay:{0.25 + i * 0.32:.2f}s}}")
        cx = lx
        for txt, col in segs:
            font = F["m500"] if col == "gold" else F["m400"]
            cx += s.text(txt, cx, ly, font, fsz, C[col], cls=f"l l{i}")
        if i == len(HEADER["terminal"]) - 1:
            s.add(f'<rect class="l l{i} cur" x="{cx:.2f}" y="{ly - 13}" width="9" '
                  f'height="17" rx="1.5" fill="{C["accent"]}"/>')
        ly += lh
    css.append("@media (prefers-reduced-motion:reduce){.l,.cur{animation:none}}")
    s.css = "".join(css)
    s.save(OUT / "header.svg")


def build_links():
    for slug, ic, label in LINKS:
        f, sz, h = F["r600"], 15, 40
        tw = f.width(label, sz)
        w = int(14 + 18 + 10 + tw + 16) + 2
        s = SVG(w, h + 2, label)
        s.add(f'<rect x="1" y="1" width="{w - 2}" height="{h}" rx="11" fill="{C["nav"]}" '
              f'stroke="{C["border"]}" stroke-width="1.2"/>')
        s.add(icon(ic, 14, 1 + (h - 18) / 2, 18, C["gold"], sw=2.0))
        s.text(label, 42, 1 + h / 2 + sz * 0.36, f, sz, C["gold"])
        s.save(OUT / "links" / f"{slug}.svg")


def build_headings():
    for slug, label in HEADINGS.items():
        f, sz = F["r600"], 30
        w = int(f.width(label, sz)) + 6
        for mode, fg, bar in [("dark", C["white"], C["accent"]),
                              ("light", C["light_text"], C["light_bar"])]:
            s = SVG(w, 56, label)
            s.text(label, 1, 33, f, sz, fg)
            s.add(f'<rect x="2" y="46" width="40" height="5" rx="2.5" fill="{bar}"/>')
            s.save(OUT / "headings" / f"{slug}-{mode}.svg")


def build_stack():
    W = 1000
    s = SVG(W, 10, "")
    body_start = len(s.body)
    col_x = [44, 364, 704]
    bottom = 0
    for (title, items), x in zip(STACK_COLUMNS, col_x):
        s.text(title, x, 62, F["r600"], 21, C["white"])
        s.add(f'<rect x="{x}" y="76" width="34" height="4.5" rx="2.25" fill="{C["accent"]}"/>')
        y = 114
        for it in items:
            s.text("-", x, y, F["r500"], 16, C["gold"])
            s.text(it, x + 16, y, F["r400"], 16.5, C["text"])
            y += 29
        bottom = max(bottom, y)
    div = bottom + 4
    s.add(f'<path d="M44 {div}H{W - 44}" stroke="{C["border"]}" stroke-width="1.2"/>')

    y = div + 34
    lab_x, chip_x0, chip_x1, ch, gap, rgap = 44, 226, W - 44, 32, 8, 10
    for label, items in TOOLBOX:
        s.text(label, lab_x, y + ch / 2 + 4.5, F["r500"], 12.5, C["label"], ls=1.8)
        cx = chip_x0
        for it in items:
            w = F["r500"].width(it, 14.5) + 24 + 14
            if cx + w > chip_x1:
                cx = chip_x0
                y += ch + rgap
            chip(s, cx, y, it, F["r500"], 14.5, ch, C["text"], C["inner"], dot=C["accent"])
            cx += w + gap
        y += ch + rgap + 8
    H = int(y + 22)
    s.h = H
    s.label = ("Good at: " + ", ".join(STACK_COLUMNS[0][1]) + ". Interests: "
               + ", ".join(STACK_COLUMNS[1][1]) + ". Toolbox: "
               + "; ".join(f"{l.title()}: {', '.join(i)}" for l, i in TOOLBOX) + ".")
    s.body.insert(body_start, f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="24" '
                              f'fill="{C["box"]}" stroke="{C["border"]}" stroke-width="1.2"/>')
    s.save(OUT / "stack.svg")


def build_projects():
    W, H = 480, 264
    for p in PROJECTS:
        s = SVG(W, H, f'{p["title"]} ({p["lang"]}): {p["desc"]}')
        card(s)
        s.add(f'<rect x="26" y="26" width="52" height="52" rx="14" fill="{C["inner"]}" '
              f'stroke="{C["border"]}" stroke-width="1.2"/>')
        s.add(icon(p["icon"], 37, 37, 30, C["accent"], sw=1.9))
        s.add(icon("arrow", W - 26 - 20, 30, 20, C["gold"], sw=2.2))
        lw = F["r500"].width(p["lang"], 14)
        lx = W - 26 - 20 - 14 - lw
        s.add(f'<circle cx="{lx - 11:.2f}" cy="{40 - 5}" r="4" fill="{C["accent"]}"/>')
        s.text(p["lang"], lx, 40, F["r500"], 14, C["muted"])
        s.text(p["title"], 26, 114, F["r600"], 24, C["white"])
        lines = wrap(p["desc"], F["r400"], 15.5, W - 52)
        assert len(lines) <= 3, f'{p["title"]} description is {len(lines)} lines'
        for i, line in enumerate(lines):
            s.text(line, 26, 143 + i * 22, F["r400"], 15.5, C["muted"])
        cx = 26
        for t in p["tags"]:
            cx += chip(s, cx, H - 26 - 30, t, F["m500"], 12.5, 30, C["gold"], C["nav"]) + 8
        assert cx < W - 20, f'{p["title"]} tags overflow'
        s.save(OUT / "projects" / f'{p["slug"]}.svg')


def build_talks():
    W, H = 480, 180
    for t in TALKS:
        s = SVG(W, H, f'{t["event"].title()} talk: {t["title"]}. Watch on YouTube.')
        card(s)
        s.text(t["event"], 26, 46, F["m500"], 13, C["gold"], ls=1.4)
        px, py = W - 26 - 21, 42
        s.add(f'<circle cx="{px}" cy="{py}" r="21" fill="{C["accent"]}"/>')
        s.add(f'<path d="M{px - 6} {py - 9}L{px + 9} {py}L{px - 6} {py + 9}z" fill="{C["bg"]}"/>')
        lines = wrap(t["title"], F["r600"], 21, W - 52 - 30)
        assert len(lines) <= 2, t["title"]
        for i, line in enumerate(lines):
            s.text(line, 26, 92 + i * 28, F["r600"], 21, C["white"])
        w = s.text("Watch on YouTube", 26, H - 30, F["r500"], 14, C["muted"])
        s.add(icon("arrow", 26 + w + 6, H - 30 - 13, 15, C["muted"], sw=2.2))
        s.save(OUT / "talks" / f'{t["slug"]}.svg')


if __name__ == "__main__":
    build_header()
    build_links()
    build_headings()
    build_stack()
    build_projects()
    build_talks()
    for f in sorted(OUT.rglob("*.svg")):
        print(f"{f.relative_to(OUT.parent)}  {f.stat().st_size / 1024:.1f} KB")
