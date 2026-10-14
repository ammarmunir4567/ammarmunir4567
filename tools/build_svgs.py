"""Generate the animated hero and footer band SVGs for the GitHub profile README.

usage:
    python3 -m venv .venv && .venv/bin/pip install fonttools brotli
    curl -L -o Recursive.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/recursive/Recursive%5BCASL%2CCRSV%2CMONO%2Cslnt%2Cwght%5D.ttf"
    .venv/bin/python tools/build_svgs.py Recursive.ttf assets

Text used in the SVGs is subset from Recursive (SIL Open Font License) and embedded as woff2,
so the type renders inside GitHub's image proxy.
"""
import base64
import io
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

AXES = {
    "casual": dict(MONO=0, CASL=1, wght=800, slnt=0, CRSV=0.5),
    "sans": dict(MONO=0, CASL=0, wght=420, slnt=0, CRSV=0.5),
    "sansb": dict(MONO=0, CASL=0, wght=640, slnt=0, CRSV=0.5),
    "mono": dict(MONO=1, CASL=0, wght=420, slnt=0, CRSV=0.5),
    "monob": dict(MONO=1, CASL=0, wght=660, slnt=0, CRSV=0.5),
}

PALETTES = {
    "light": dict(
        bg="#F5F7FC", panel="#FFFFFF", rule="#D9E0F0", ink="#141A33", muted="#56607F",
        cobalt="#2342A6", turq="#0E7C7B", saffron="#B86E0A", mist="#C3CDE8", band="#2342A6",
        bandAccent="#0E7C7B", ring="#0E7C7B", peri="#7A8FD9", chip="#F5F7FC",
    ),
    "dark": dict(
        bg="#0F1430", panel="#161D42", rule="#2A3466", ink="#E8ECF8", muted="#9AA5CC",
        cobalt="#8FA8FF", turq="#3FD0C9", saffron="#F2B04A", mist="#3A4578", band="#5B7BEA",
        bandAccent="#3FD0C9", ring="#3FD0C9", peri="#5F74D8", chip="#1B2350",
    ),
}

_instances = {}


def instance(key):
    if key not in _instances:
        _instances[key] = instancer.instantiateVariableFont(TTFont(SRC), AXES[key], inplace=False)
    return _instances[key]


def advance(key, s, size):
    f = instance(key)
    cmap, hmtx = f.getBestCmap(), f["hmtx"]
    upm = f["head"].unitsPerEm
    return sum(hmtx[cmap.get(ord(c), cmap[ord("?")])][0] for c in s) * size / upm


def font_face(key, chars):
    raw = io.BytesIO()
    instance(key).save(raw)
    raw.seek(0)
    f = TTFont(raw)
    opts = subset.Options()
    opts.layout_features = ["kern", "liga", "calt"]
    opts.name_IDs = []
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(f)
    f.flavor = "woff2"
    out = io.BytesIO()
    f.save(out)
    b64 = base64.b64encode(out.getvalue()).decode()
    return f"@font-face{{font-family:'r-{key}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self):
        self.used = {}

    def text(self, x, y, s, font, size, fill, extra="", anchor=None):
        self.used.setdefault(font, set()).update(s)
        a = f' text-anchor="{anchor}"' if anchor else ""
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="r-{font},ui-sans-serif,system-ui,sans-serif" '
                f'font-size="{size}" fill="{fill}"{a} {extra}>{esc(s)}</text>')

    def spans(self, x, y, parts, font, size, extra=""):
        out = []
        for s, fill, f in parts:
            f = f or font
            self.used.setdefault(f, set()).update(s)
            out.append(f'<tspan font-family="r-{f},ui-monospace,monospace" fill="{fill}">{esc(s)}</tspan>')
        return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" xml:space="preserve" {extra}>{"".join(out)}</text>'

    def fonts_css(self):
        return "".join(font_face(k, v | {" "}) for k, v in self.used.items())


class Anim:
    """CSS keyframe helpers. Every element's resting style is its final frame, so
    reduced motion (animation: none) shows the finished trace."""

    def __init__(self, T):
        self.T, self.kfs, self.rules, self.n = T, [], [], 0

    def pct(self, t):
        return f"{max(0, min(t / self.T * 100, 100)):.3f}%"

    def _name(self, prefix):
        self.n += 1
        return f"{prefix}{self.n}"

    def _add(self, name, frames, base=""):
        self.kfs.append(f"@keyframes {name}{{{frames}}}")
        self.rules.append(f".{name}{{{base}animation:{name} {self.T}s linear infinite}}")
        return name

    def fade_in(self, t, dur=0.28):
        n = self._name("f")
        return self._add(n, f"0%,{self.pct(t)}{{opacity:0}}{self.pct(t + dur)},100%{{opacity:1}}")

    def window(self, t_on, t_off):
        """Visible only between t_on and t_off (stepped counters)."""
        n = self._name("w")
        return self._add(n, f"0%,{self.pct(t_on)}{{opacity:0}}{self.pct(t_on + 0.01)},{self.pct(t_off)}{{opacity:1}}"
                            f"{self.pct(t_off + 0.01)},100%{{opacity:0}}", "opacity:0;")

    def wipe(self, t0, t1, dist, axis="X", steps=None):
        n = self._name("x")
        tf = f"animation-timing-function:steps({steps},end);" if steps else ""
        return self._add(n, f"0%,{self.pct(t0)}{{transform:translate{axis}(0);{tf}}}"
                            f"{self.pct(t1)},100%{{transform:translate{axis}({dist:.1f}px)}}",
                         f"transform:translate{axis}({dist:.1f}px);")

    def draw(self, t0, t1):
        n = self._name("d")
        return self._add(n, f"0%,{self.pct(t0)}{{stroke-dashoffset:1}}{self.pct(t1)},100%{{stroke-dashoffset:0}}",
                         "stroke-dasharray:1;stroke-dashoffset:0;")

    def sweep(self, t0, t1, dist):
        """Move right across a span, then vanish (playhead)."""
        n = self._name("p")
        return self._add(n, f"0%,{self.pct(t0)}{{transform:translateX(0);opacity:1}}"
                            f"{self.pct(t1)}{{transform:translateX({dist:.1f}px);opacity:1}}"
                            f"{self.pct(t1 + 0.3)},100%{{transform:translateX({dist:.1f}px);opacity:0}}", "opacity:0;")


def reveal(c, x, y, w, h, t0, t1, axis="X", steps=None):
    """Panel-coloured cover over a region, slid away to reveal what is underneath."""
    cid = f"c{c.A.n + 1}"
    dist = w if axis == "X" else -h
    cls = c.A.wipe(t0, t1, dist, axis, steps)
    return (f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/></clipPath>'
            f'<g clip-path="url(#{cid})"><rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{c.cover}"/></g>')


class Ctx:
    def __init__(self, s, p, A, px, py, pw):
        self.s, self.p, self.A, self.px, self.py, self.pw = s, p, A, px, py, pw
        self.cover = p["panel"]


def ask_row(c, x_label, x_val, y, size, t0=0.7, t1=2.0):
    s, p, A = c.s, c.p, c.A
    q = "what does ammar build?"
    qw = advance("mono", q, size)
    out = [s.text(x_label, y, "ask", "monob", size, p["cobalt"]), s.text(x_val, y, q, "mono", size, p["ink"]),
           reveal(c, x_val - 1, y - size - 2, qw + 4, size + 9, t0, t1, steps=len(q))]
    hide = A._add("caret", f"0%,{A.pct(t1 + 0.3)}{{opacity:1}}{A.pct(t1 + 0.31)},100%{{opacity:0}}", "opacity:0;")
    A.kfs.append("@keyframes bl{0%,49%{opacity:1}50%,100%{opacity:0}}")
    A.rules.append(".bl{animation:bl 1s step-end infinite}")
    move = A.wipe(t0, t1, qw, steps=len(q))
    out.append(f'<g class="{hide}"><g class="{move}"><rect class="bl" x="{x_val + 1}" y="{y - size + 1}" '
               f'width="{size * 0.33:.1f}" height="{size + 3}" fill="{p["cobalt"]}"/></g></g>')
    return out


def stream(c, x, y, parts, size, t0, speed=420):
    """One line of answer text revealed left to right like streamed tokens. Returns (svg, end time)."""
    lw = sum(advance(f or "mono", txt, size) for txt, _, f in parts) + 6
    t1 = t0 + lw / speed
    return c.s.spans(x, y, parts, "mono", size) + reveal(c, x - 2, y - size - 3, lw, size + 10, t0, t1), t1


def sources_line(c, x, y, t):
    s, p = c.s, c.p
    parts = []
    for ref, name in (("[1]", "Arq Tech, lead engineer   "), ("[2]", "Turing, RLHF   "),
                      ("[3]", "INOVAQO, generative AI")):
        parts += [(ref + " ", p["saffron"], "monob"), (name, p["muted"], None)]
    return f'<g class="{c.A.fade_in(t)}">' + s.spans(x, y, parts, "mono", 12.5) + "</g>"


# ---------------------------------------------------------------- hero panel: context funnel

def context_funnel(c):
    s, p, A, px, py, pw = c.s, c.p, c.A, c.px, c.py, c.pw
    x0 = px + 28
    right = px + pw - 28
    size = 14.5
    row_y = py + 42
    out = ask_row(c, x0, x0 + 56, row_y, size)

    sources = [  # name, detail, kind colour, k tokens
        ("GitHub MCP", "38 repos", p["turq"], 22),
        ("Slack MCP", "1.2k threads", p["turq"], 14),
        ("AWS MCP", "640 resources", p["turq"], 18),
        ("Policy library", "212 documents", p["peri"], 48),
        ("CVE feed", "9.8k advisories", p["saffron"], 30),
        ("Questionnaires", "40 RFPs", p["peri"], 20),
        ("UI/UX snapshots", "web, ext, mobile", p["cobalt"], 12),
        ("Mem0 memory", "14 recalls", p["cobalt"], 6),
    ]
    top = row_y + 52
    chip_w, chip_h, gap = 292, 28, 8
    col_h = len(sources) * (chip_h + gap) - gap
    gx, gw = x0 + chip_w + 74, 54
    cap = 200
    head = top - 14
    out.append(f'<g class="{A.fade_in(2.2)}">'
               + s.text(x0, head, "Sources", "sansb", 12.5, p["muted"])
               + s.text(gx + gw / 2, head, "Context window", "sansb", 12.5, p["muted"], anchor="middle")
               + s.text(right, head, "Distilled", "sansb", 12.5, p["muted"], anchor="end") + "</g>")
    out.append(f'<rect x="{gx}" y="{top}" width="{gw}" height="{col_h}" rx="10" fill="{p["chip"]}" stroke="{p["rule"]}"/>')

    filled, t = 0, 2.4
    times = []
    c.cover = p["chip"]
    for i, (name, detail, col, tok) in enumerate(sources):
        y = top + i * (chip_h + gap)
        cy = y + chip_h / 2
        out.append(f'<g class="{A.fade_in(t)}">'
                   f'<rect x="{x0}" y="{y}" width="{chip_w}" height="{chip_h}" rx="8" fill="{p["chip"]}" stroke="{p["rule"]}"/>'
                   f'<circle cx="{x0 + 14}" cy="{cy}" r="4" fill="{col}"/>'
                   + s.text(x0 + 26, cy + 4.5, name, "sansb", 12.5, p["ink"])
                   + s.text(x0 + chip_w - 12, cy + 4, detail, "mono", 11.5, p["muted"], anchor="end") + "</g>")
        # flow line into the gauge
        seg_h = tok / cap * col_h
        tgt_y = top + col_h - (filled + tok / 2) / cap * col_h
        d = f"M{x0 + chip_w + 2} {cy}C{x0 + chip_w + 40} {cy} {gx - 36} {tgt_y:.1f} {gx - 2} {tgt_y:.1f}"
        out.append(f'<path class="{A.draw(t + 0.1, t + 0.45)}" pathLength="1" d="{d}" fill="none" stroke="{col}" '
                   f'stroke-width="1.4" opacity=".7"/>')
        sy = top + col_h - (filled + tok) / cap * col_h
        out.append(f'<rect x="{gx + 4}" y="{sy:.1f}" width="{gw - 8}" height="{seg_h - 1.5:.1f}" rx="3" fill="{col}"/>'
                   + reveal(c, gx + 3, sy - 0.5, gw - 6, seg_h + 0.5, t + 0.4, t + 0.7, axis="Y"))
        filled += tok
        times.append((t + 0.55, filled))
        t += 0.38
    c.cover = p["panel"]
    for k, (tt, tot) in enumerate(times):
        last = k == len(times) - 1
        cls = A.fade_in(tt, 0.01) if last else A.window(tt, times[k + 1][0])
        out.append(s.text(gx + gw / 2, top + col_h + 22, f"{tot}k tokens", "monob", 12.5, p["ink"], f'class="{cls}"',
                          anchor="middle"))

    # distillation stages
    dx0 = gx + gw + 56
    dw = right - dx0
    stages = [("2,400 chunks", "hybrid retrieval, one org only"), ("40", "reciprocal rank fusion"),
              ("12", "cross-encoder rerank"), ("✓ checks pass", "UI/UX and contradiction checks")]
    sh, sg = 56, (col_h - 4 * 56) / 3
    t += 0.3
    for i, (big, small) in enumerate(stages):
        y = top + i * (sh + sg)
        g = (f'<rect x="{dx0}" y="{y:.1f}" width="{dw}" height="{sh}" rx="10" fill="{p["chip"]}" stroke="{p["rule"]}"/>'
             + s.text(dx0 + 14, y + 25, big, "sansb", 17, p["ink"])
             + s.text(dx0 + 14, y + 44, small, "sans", 12, p["muted"]))
        if i == 0:
            g += f'<path d="M{gx + gw + 4} {y + sh / 2:.1f}H{dx0 - 6}" stroke="{p["muted"]}" stroke-width="1.4" marker-end="url(#ah)"/>'
        else:
            g += f'<path d="M{dx0 + 30} {y - sg + 2:.1f}V{y - 5:.1f}" stroke="{p["muted"]}" stroke-width="1.4" marker-end="url(#ah)"/>'
        out.append(f'<g class="{A.fade_in(t)}">{g}</g>')
        t += 0.45

    ans_y = top + col_h + 66
    out.append(s.text(x0, ans_y, "answer", "monob", size, p["turq"], f'class="{A.fade_in(t)}"'))
    vx = x0 + 76
    lines = [
        [("Agents that take in a lot of messy context, distill it, check", p["ink"], None)],
        [("their own work and cite every source ", p["ink"], None), ("[1][2][3]", p["saffron"], "monob")],
    ]
    ta = t + 0.2
    for j, parts in enumerate(lines):
        svg, ta = stream(c, vx, ans_y + j * 27, parts, size, ta)
        out.append(svg)
    src_y = ans_y + 27 * len(lines) + 6
    out.append(sources_line(c, vx, src_y, ta + 0.2))
    desc = ("An animated funnel answers what does ammar build. Eight sources flow into a context window that fills to "
            "170 thousand tokens: GitHub, Slack and AWS MCP servers, a policy library, a CVE feed, questionnaires, "
            "UI/UX snapshots of web, extension and mobile, and Mem0 memory. The context is distilled from 2,400 chunks "
            "to 40 with reciprocal rank fusion and 12 with a cross-encoder, UI/UX and contradiction checks pass, and "
            "the answer cites its sources.")
    return out, src_y + 26 - py, desc


# ---------------------------------------------------------------- shared hero frame

def tile_pattern(p):
    return (f'<pattern id="tile" width="36" height="26" patternUnits="userSpaceOnUse">'
            f'<g fill="{p["band"]}">'
            + "".join(f'<path transform="rotate({a} 18 13)" d="M18 12.2c-2.2-1.8-2.6-5.2 0-8.4 2.6 3.2 2.2 6.6 0 8.4z"/>'
                      for a in (0, 90, 180, 270))
            + f'</g><g fill="{p["bandAccent"]}"><circle cx="18" cy="13" r="1.7"/>'
            + "".join(f'<circle cx="{18 + dx}" cy="{13 + dy}" r="1"/>' for dx, dy in ((5, 5), (-5, 5), (5, -5), (-5, -5)))
            + '<path d="M0 9l4 4-4 4-4-4zM36 9l4 4-4 4-4-4z"/></g></pattern>')


def hero(theme, variant, T):
    p = PALETTES[theme]
    s = Svg()
    A = Anim(T)
    W, PAD = 880, 48
    els = []
    name_y = 100
    els.append(s.text(PAD, name_y, "Ammar Munir", "casual", 62, p["ink"], 'letter-spacing="-0.5"'))
    els.append(s.text(W - PAD, name_y - 26, "Lead engineer at Arq Tech", "sansb", 15.5, p["ink"], anchor="end"))
    els.append(s.text(W - PAD, name_y - 4, "Lahore, Pakistan", "sans", 15.5, p["muted"], anchor="end"))
    tagline = "I build agentic RAG and LLM systems that answer with their sources."
    ty = name_y + 40
    els.append(s.text(PAD, ty, tagline, "sans", 20, p["muted"]))
    px, py, pw = PAD, ty + 33, W - 2 * PAD
    c = Ctx(s, p, A, px, py, pw)
    dyn, ph, desc = variant(c)
    H = py + ph + PAD - 8
    A.kfs.append(f"@keyframes gf{{0%,{A.pct(T - 0.9)}{{opacity:1}}{A.pct(T - 0.35)},100%{{opacity:0}}}}")
    A.rules.append(f".gf{{animation:gf {T}s linear infinite}}")
    css = (s.fonts_css() + "".join(A.kfs) + "".join(A.rules)
           + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" viewBox="0 0 {W} {H:.0f}" role="img" aria-labelledby="t d">
<title id="t">Ammar Munir</title>
<desc id="d">Lead engineer at Arq Tech. {esc(desc)}</desc>
<style>{css}</style>
<defs>{tile_pattern(p)}<clipPath id="card"><rect width="{W}" height="{H:.0f}" rx="18"/></clipPath>
<marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{p["muted"]}"/></marker></defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{H:.0f}" fill="{p["bg"]}"/>
<rect width="{W}" height="26" fill="url(#tile)"/>
<rect y="26" width="{W}" height="1" fill="{p["rule"]}"/>
</g>
{"".join(els)}
<rect x="{px}" y="{py}" width="{pw}" height="{ph:.0f}" rx="14" fill="{p["panel"]}" stroke="{p["rule"]}"/>
<g class="gf">{"".join(dyn)}</g>
</svg>'''


def band(theme):
    p = PALETTES[theme]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="26" viewBox="0 0 880 26" aria-hidden="true">'
            f'<defs>{tile_pattern(p)}</defs><rect width="880" height="26" fill="url(#tile)"/></svg>')


for theme in PALETTES:
    (OUT / f"hero-{theme}.svg").write_text(hero(theme, context_funnel, 18.0))
    (OUT / f"band-{theme}.svg").write_text(band(theme))

for f in sorted(OUT.glob("*.svg")):
    print(f.name, f.stat().st_size)
