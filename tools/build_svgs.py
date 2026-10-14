"""Generate the animated hero and career timeline SVGs for the GitHub profile README.

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
        bandAccent="#0E7C7B", ring="#0E7C7B", onCobalt="#FFFFFF", turqTint="#E3F4F3",
    ),
    "dark": dict(
        bg="#0F1430", panel="#161D42", rule="#2A3466", ink="#E8ECF8", muted="#9AA5CC",
        cobalt="#8FA8FF", turq="#3FD0C9", saffron="#F2B04A", mist="#3A4578", band="#5B7BEA",
        bandAccent="#3FD0C9", ring="#3FD0C9", onCobalt="#0F1430", turqTint="#123A4A",
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


def has_glyph(key, ch):
    return ord(ch) in instance(key).getBestCmap()


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
        self.css = []

    def text(self, x, y, s, font, size, fill, extra="", anchor=None):
        self.used.setdefault(font, set()).update(s)
        a = f' text-anchor="{anchor}"' if anchor else ""
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="r-{font},ui-sans-serif,system-ui,sans-serif" '
                f'font-size="{size}" fill="{fill}"{a} {extra}>{esc(s)}</text>')

    def spans(self, x, y, parts, font, size, extra=""):
        """parts: list of (string, fill, font_override_or_None)."""
        out = []
        for s, fill, f in parts:
            f = f or font
            self.used.setdefault(f, set()).update(s)
            out.append(f'<tspan font-family="r-{f},ui-monospace,monospace" fill="{fill}">{esc(s)}</tspan>')
        return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" xml:space="preserve" {extra}>{"".join(out)}</text>'

    def fonts_css(self):
        return "".join(font_face(k, v | {" "}) for k, v in self.used.items())


# ---------------------------------------------------------------- hero

def tile_pattern(p):
    """Lahore blue-pottery flower tile, repeated along an edge."""
    return (f'<pattern id="tile" width="36" height="26" patternUnits="userSpaceOnUse">'
            f'<g fill="{p["band"]}">'
            + "".join(f'<path transform="rotate({a} 18 13)" d="M18 12.2c-2.2-1.8-2.6-5.2 0-8.4 2.6 3.2 2.2 6.6 0 8.4z"/>'
                      for a in (0, 90, 180, 270))
            + f'</g><g fill="{p["bandAccent"]}"><circle cx="18" cy="13" r="1.7"/>'
            + "".join(f'<circle cx="{18 + dx}" cy="{13 + dy}" r="1"/>' for dx, dy in ((5, 5), (-5, 5), (5, -5), (-5, -5)))
            + '<path d="M0 9l4 4-4 4-4-4zM36 9l4 4-4 4-4-4z"/></g></pattern>')



T = 16.0  # seconds per loop


def pct(t):
    return f"{min(t / T * 100, 100):.3f}%"


def hero(theme):
    p = PALETTES[theme]
    s = Svg()
    W, PAD = 880, 48
    els, kfs, rules = [], [], []

    def fade_in(name, t, dur=0.28):
        kfs.append(f"@keyframes {name}{{0%,{pct(t)}{{opacity:0}}{pct(t + dur)},100%{{opacity:1}}}}")
        rules.append(f".{name}{{animation:{name} {T}s linear infinite}}")
        return name

    def wipe(name, t0, t1, width, steps=None):
        tf = f"animation-timing-function:steps({steps},end);" if steps else ""
        kfs.append(f"@keyframes {name}{{0%,{pct(t0)}{{transform:translateX(0);{tf}}}"
                   f"{pct(t1)},100%{{transform:translateX({width:.1f}px)}}}}")
        rules.append(f".{name}{{transform:translateX({width:.1f}px);animation:{name} {T}s linear infinite}}")
        return name

    # header: name, role and place, one-line tagline
    name_y = 100
    els.append(s.text(PAD, name_y, "Ammar Munir", "casual", 62, p["ink"], 'letter-spacing="-0.5"'))
    els.append(s.text(W - PAD, name_y - 26, "Lead engineer at Arq Tech", "sansb", 15.5, p["ink"], anchor="end"))
    els.append(s.text(W - PAD, name_y - 4, "Lahore, Pakistan", "sans", 15.5, p["muted"], anchor="end"))
    tagline = "I build agentic RAG and LLM systems that answer with their sources."
    assert advance("sans", tagline, 20) < W - 2 * PAD
    ty = name_y + 40
    els.append(s.text(PAD, ty, tagline, "sans", 20, p["muted"]))
    ty += 27

    # trace panel
    px, py = PAD, ty + 6
    pw = W - 2 * PAD
    ix = px + 28           # dot column
    lx = ix + 20           # label column
    vx = lx + 96           # value column
    lh = 30
    mono = 15.5
    cw = advance("mono", "M", mono)
    row_y = py + 44

    dyn = []  # everything inside the looping, fading group

    # ask row with typing
    query = "what does ammar build?"
    qw = advance("mono", query, mono)
    dyn.append(s.text(lx, row_y, "ask", "monob", mono, p["cobalt"]))
    dyn.append(s.text(vx, row_y, query, "mono", mono, p["ink"]))
    dyn.append(f'<clipPath id="cq"><rect x="{vx - 1}" y="{row_y - 17}" width="{qw + 4:.1f}" height="24"/></clipPath>')
    dyn.append(f'<g clip-path="url(#cq)"><rect class="{wipe("tq", 0.7, 2.0, qw + 4, steps=len(query))}" '
               f'x="{vx - 1}" y="{row_y - 17}" width="{qw + 4:.1f}" height="24" fill="{p["panel"]}"/></g>')
    kfs.append(f"@keyframes ch{{0%,{pct(2.3)}{{opacity:1}}{pct(2.31)},100%{{opacity:0}}}}")
    rules.append(f".ch{{opacity:0;animation:ch {T}s linear infinite}}")
    kfs.append("@keyframes bl{0%,49%{opacity:1}50%,100%{opacity:0}}")
    rules.append(".bl{animation:bl 1s step-end infinite}")
    dyn.append(f'<g class="ch"><g class="{wipe("tc", 0.7, 2.0, qw, steps=len(query))}">'
               f'<rect class="bl" x="{vx + 1}" y="{row_y - 15}" width="{cw * 0.55:.1f}" height="19" fill="{p["cobalt"]}"/></g></g>')

    steps = [
        ("route", "agentic_rag"),
        ("expand", "3 sub-queries"),
        ("retrieve", "dense + sparse search, scoped to one organization"),
        ("fuse", "reciprocal rank fusion"),
        ("rerank", "cross-encoder"),
    ]
    t = 2.4
    for i, (label, value) in enumerate(steps):
        y = row_y + lh * (i + 1)
        row = fade_in(f"r{i}", t)
        done = fade_in(f"d{i}", t + 0.42, 0.12)
        kfs.append(f"@keyframes p{i}{{0%,{pct(t)}{{opacity:0}}{pct(t + 0.05)}{{opacity:1}}"
                   f"{pct(t + 0.2)}{{opacity:.35}}{pct(t + 0.35)}{{opacity:1}}100%{{opacity:1}}}}")
        rules.append(f".p{i}{{animation:p{i} {T}s linear infinite}}")
        dyn.append(f'<g class="{row}">'
                   f'<circle class="p{i}" cx="{ix + 5}" cy="{y - 5}" r="5" fill="none" stroke="{p["ring"]}" stroke-width="1.6"/>'
                   f'<circle class="{done}" cx="{ix + 5}" cy="{y - 5}" r="3" fill="{p["ring"]}"/>'
                   + s.text(lx, y, label, "mono", mono, p["muted"])
                   + s.text(vx, y, value, "mono", mono, p["ink"]) + "</g>")
        t += 0.5

    # divider
    dy = row_y + lh * (len(steps) + 1) - 10
    dyn.append(f'<line class="{fade_in("dv", t)}" x1="{lx}" y1="{dy}" x2="{px + pw - 28}" y2="{dy}" '
               f'stroke="{p["rule"]}" stroke-dasharray="3 5"/>')

    # streamed answer
    ans_y = dy + 34
    dyn.append(s.text(lx, ans_y, "answer", "monob", mono, p["turq"], f'class="{fade_in("al", t + 0.1)}"'))
    answer = [
        [("Agentic RAG and LLM systems, from prototype to production:", p["ink"], None)],
        [("hybrid retrieval, reranking, memory and cited answers ", p["ink"], None),
         ("[1][2][3]", p["saffron"], "monob")],
    ]
    t_ans = t + 0.3
    for j, parts in enumerate(answer):
        y = ans_y + j * lh
        lw = sum(advance(f or "mono", txt, mono) for txt, _, f in parts) + 6
        dur = lw / 400  # ~token streaming speed
        dyn.append(s.spans(vx, y, parts, "mono", mono))
        dyn.append(f'<clipPath id="ca{j}"><rect x="{vx - 2}" y="{y - 18}" width="{lw:.1f}" height="25"/></clipPath>')
        dyn.append(f'<g clip-path="url(#ca{j})"><rect class="{wipe(f"wa{j}", t_ans, t_ans + dur, lw)}" '
                   f'x="{vx - 2}" y="{y - 18}" width="{lw:.1f}" height="25" fill="{p["panel"]}"/></g>')
        t_ans += dur

    # sources
    src_y = ans_y + lh * len(answer) + 14
    dash = "–" if has_glyph("mono", "–") else "-"
    sources = [
        ("[1]", f"Arq Tech, lead engineer on an AI compliance platform, 2025{dash}now"),
        ("[2]", "Turing, LLM post-training data and RLHF evaluation, 2023"),
        ("[3]", f"INOVAQO, generative AI projects end to end, 2024{dash}25"),
    ]
    t_src = t_ans + 0.2
    for k, (ref, txt) in enumerate(sources):
        y = src_y + k * 25
        dyn.append(f'<g class="{fade_in(f"s{k}", t_src + k * 0.22)}">'
                   + s.text(vx, y, ref, "monob", 13.5, p["saffron"])
                   + s.text(vx + advance("monob", ref + " ", 13.5), y, txt, "mono", 13.5, p["muted"]) + "</g>")

    ph = src_y + 25 * (len(sources) - 1) + 30 - py
    H = py + ph + PAD - 8

    kfs.append(f"@keyframes gf{{0%,{pct(T - 0.9)}{{opacity:1}}{pct(T - 0.35)},100%{{opacity:0}}}}")
    rules.append(f".gf{{animation:gf {T}s linear infinite}}")

    # Lahore blue-pottery band across the top edge
    band = tile_pattern(p)

    css = (s.fonts_css() + "".join(kfs) + "".join(rules)
           + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" viewBox="0 0 {W} {H:.0f}" role="img" aria-labelledby="t d">
<title id="t">Ammar Munir</title>
<desc id="d">Lead engineer at Arq Tech. An animated agent trace answers the question what does ammar build: it routes the question, expands it into sub-queries, runs dense and sparse retrieval fused with reciprocal rank fusion, reranks with a cross-encoder, and answers with citations to Arq Tech, Turing and INOVAQO.</desc>
<style>{css}</style>
<defs>{band}<clipPath id="card"><rect width="{W}" height="{H:.0f}" rx="18"/></clipPath></defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{H:.0f}" fill="{p["bg"]}"/>
<rect width="{W}" height="26" fill="url(#tile)"/>
<rect y="26" width="{W}" height="1" fill="{p["rule"]}"/>
</g>
{"".join(els)}
<rect x="{px}" y="{py}" width="{pw}" height="{ph:.0f}" rx="14" fill="{p["panel"]}" stroke="{p["rule"]}"/>
<g class="gf">{"".join(dyn)}</g>
</svg>'''


# ---------------------------------------------------------------- timeline

def timeline(theme):
    p = PALETTES[theme]
    s = Svg()
    W, x0, x1 = 880, 56, 824
    months = 48  # Jan 2023 .. Dec 2026

    def mx(i):
        return x0 + i / months * (x1 - x0)

    roles = [  # start index, end index, company, role, is_ai
        (0, 6, "Turing", "LLM post-training and RLHF evaluation", True),
        (6, 11, "FAST-NU", "Teaching assistant", False),
        (17, 23, "Ginkgo Retail", "Backend, 30% faster APIs", False),
        (23, 35, "INOVAQO", "Generative AI engineer", True),
        (35, 45.5, "Arq Tech", "Lead engineer, US remote", True),
    ]
    els = []
    lg_y = 22
    lx = x0
    for label, kind in [("LLM and generative AI work", "ai"), ("Software engineering and teaching", "se"),
                        ("Education", "ed")]:
        if kind == "ed":
            els.append(f'<rect x="{lx}" y="{lg_y - 7}" width="18" height="4" rx="2" fill="{p["turq"]}"/>')
        else:
            els.append(f'<rect x="{lx}" y="{lg_y - 11}" width="18" height="12" rx="3" '
                       f'fill="{p["cobalt"] if kind == "ai" else p["mist"]}"/>')
        els.append(s.text(lx + 26, lg_y, label, "sans", 13, p["muted"]))
        lx += 26 + advance("sans", label, 13) + 28

    bar_y, bar_h = 104, 24
    for a, b, company, role, ai in roles:
        xa, xb = mx(a) + 1.5, mx(b) - 1.5
        fill = p["cobalt"] if ai else p["mist"]
        els.append(f'<rect x="{xa:.1f}" y="{bar_y}" width="{xb - xa:.1f}" height="{bar_h}" rx="6" fill="{fill}"/>')
        if ai:
            els.append(f'<line x1="{xa:.1f}" y1="{bar_y}" x2="{xa:.1f}" y2="{bar_y - 46}" stroke="{p["rule"]}"/>')
            els.append(s.text(xa + 8, bar_y - 30, company, "sansb", 15, p["ink"]))
            els.append(s.text(xa + 8, bar_y - 12, role, "sans", 12.5, p["muted"]))
        else:
            els.append(f'<line x1="{xa:.1f}" y1="{bar_y + bar_h}" x2="{xa:.1f}" y2="{bar_y + bar_h + 46}" stroke="{p["rule"]}"/>')
            els.append(s.text(xa + 8, bar_y + bar_h + 22, company, "sansb", 15, p["ink"]))
            els.append(s.text(xa + 8, bar_y + bar_h + 40, role, "sans", 12.5, p["muted"]))

    # now marker
    nx = mx(45.5) - 1.5
    els.append(f'<circle class="pulse" cx="{nx:.1f}" cy="{bar_y + bar_h / 2}" r="7" fill="none" stroke="{p["saffron"]}" stroke-width="2"/>')
    els.append(f'<circle cx="{nx:.1f}" cy="{bar_y + bar_h / 2}" r="4.5" fill="{p["saffron"]}"/>')
    els.append(s.text(nx + 14, bar_y + bar_h / 2 + 4.5, "now", "sansb", 13, p["saffron"]))

    # axis
    ay = 194
    els.append(f'<line x1="{x0}" y1="{ay}" x2="{x1}" y2="{ay}" stroke="{p["rule"]}" stroke-width="1.5"/>')
    for i, yr in enumerate(["2023", "2024", "2025", "2026"]):
        x = mx(i * 12)
        els.append(f'<line x1="{x:.1f}" y1="{ay - 5}" x2="{x:.1f}" y2="{ay + 5}" stroke="{p["muted"]}" stroke-width="1.5"/>')
        els.append(s.text(x + 6, ay + 20, yr, "sansb", 13, p["muted"]))

    # education, running in from 2020
    ey = 236
    xe = mx(18)
    els.append(f'<rect x="{x0 - 40}" y="{ey}" width="{xe - x0 + 40:.1f}" height="5" rx="2.5" fill="url(#edfade)"/>')
    els.append(s.text(x0, ey + 24, "BS Computer Science, FAST-NU Lahore, 2020 to 2024", "sans", 12.5, p["muted"]))

    H = ey + 36
    css = (s.fonts_css()
           + "@keyframes pulse{0%{r:5;opacity:.9}70%,100%{r:13;opacity:0}}"
           + ".pulse{animation:pulse 2.4s ease-out infinite}"
           + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Career timeline</title>
<desc id="d">Turing, LLM post-training and RLHF evaluation, January to June 2023. FAST-NU teaching assistant, July to November 2023. Ginkgo Retail, June to November 2024. INOVAQO, generative AI engineer, December 2024 to November 2025. Arq Tech, lead engineer, December 2025 to now. BS Computer Science at FAST-NU Lahore, 2020 to 2024.</desc>
<style>{css}</style>
<defs><linearGradient id="edfade" x1="0" x2="1"><stop offset="0" stop-color="{p["turq"]}" stop-opacity="0"/><stop offset=".12" stop-color="{p["turq"]}"/></linearGradient></defs>
{"".join(els)}
</svg>'''


# ---------------------------------------------------------------- Ask Arq architecture

def architecture(theme):
    p = PALETTES[theme]
    s = Svg()
    W = 880
    els = []

    def node(x, y, w, h, title, sub=None, kind="step"):
        if kind == "io":
            els.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{p["cobalt"]}"/>')
            tc, sc = p["onCobalt"], p["onCobalt"]
        elif kind == "mem":
            els.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{p["turqTint"]}" stroke="{p["turq"]}" stroke-width="1.5"/>')
            tc, sc = p["ink"], p["muted"]
        else:
            els.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{p["panel"]}" stroke="{p["cobalt"]}" stroke-width="1.5"/>')
            tc, sc = p["ink"], p["muted"]
        cx = x + w / 2
        if sub:
            els.append(s.text(cx, y + h / 2 - 3, title, "sansb", 14.5, tc, anchor="middle"))
            els.append(s.text(cx, y + h / 2 + 15, sub, "sans", 12.5, sc, anchor="middle"))
        else:
            els.append(s.text(cx, y + h / 2 + 5, title, "sansb", 14.5, tc, anchor="middle"))
        return dict(l=x, r=x + w, t=y, b=y + h, cx=cx, cy=y + h / 2)

    def arrow(d, both=False):
        start = ' marker-start="url(#ah)"' if both else ""
        els.append(f'<path d="{d}" fill="none" stroke="{p["muted"]}" stroke-width="1.5"{start} marker-end="url(#ah)"/>')

    # row 1: question, router, agent, memory
    h1, y1 = 56, 14
    q = node(16, y1, 126, h1, "Question", kind="io")
    r = node(194, y1, 140, h1, "LLM router")
    a = node(386, y1, 176, h1, "ReAct agent", "about 13 tools")
    m = node(632, y1, 190, h1, "Mem0", "persistent memory", kind="mem")
    arrow(f"M{q['r'] + 2} {q['cy']}H{r['l'] - 4}")
    arrow(f"M{r['r'] + 2} {r['cy']}H{a['l'] - 4}")
    arrow(f"M{a['r'] + 6} {a['cy']}H{m['l'] - 6}", both=True)

    # row 2: expansion, then the retrieval box, then the answer
    box_t, box_b, box_l, box_r = 128, 318, 188, 712
    els.append(f'<rect x="{box_l}" y="{box_t}" width="{box_r - box_l}" height="{box_b - box_t}" rx="14" '
               f'fill="none" stroke="{p["turq"]}" stroke-width="1.5" stroke-dasharray="5 5"/>')
    els.append(s.text(box_l + 18, box_t + 26, "Hybrid retrieval, isolated per organization", "sansb", 13, p["turq"]))
    h2 = 52
    mid = 242
    x_ = node(16, mid - h2 / 2, 140, h2, "Multi-query", "expansion")
    d = node(214, mid - 36 - 22, 132, 44, "Dense search")
    sp = node(214, mid + 36 - 22, 132, 44, "Sparse search")
    f = node(392, mid - h2 / 2, 136, h2, "Reciprocal", "rank fusion")
    c = node(560, mid - h2 / 2, 130, h2, "Cross-encoder", "rerank")
    ans = node(738, mid - h2 / 2, 126, h2, "Cited answer", kind="io")

    # agent hands the query to retrieval
    arrow(f"M{a['cx']} {a['b'] + 2}V96H{x_['cx']}V{x_['t'] - 4}")
    split = x_["r"] + 26
    for n in (d, sp):
        arrow(f"M{x_['r'] + 2} {x_['cy']}H{split}V{n['cy']}H{n['l'] - 4}")
    join = d["r"] + 22
    for n in (d, sp):
        arrow(f"M{n['r'] + 2} {n['cy']}H{join}V{f['cy']}H{f['l'] - 4}")
    arrow(f"M{f['r'] + 2} {f['cy']}H{c['l'] - 4}")
    arrow(f"M{c['r'] + 2} {c['cy']}H{ans['l'] - 4}")

    H = box_b + 8
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Ask Arq architecture</title>
<desc id="d">A question goes to an LLM router, then a ReAct agent with about 13 tools that reads and writes Mem0 persistent memory. The agent expands the question into multiple queries. Hybrid retrieval, isolated per organization, runs dense and sparse search, fuses the results with reciprocal rank fusion and reranks them with a cross-encoder, producing a cited answer.</desc>
<style>{s.fonts_css()}</style>
<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{p["muted"]}"/></marker></defs>
{"".join(els)}
</svg>'''


def band(theme):
    p = PALETTES[theme]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="26" viewBox="0 0 880 26" aria-hidden="true">'
            f'<defs>{tile_pattern(p)}</defs><rect width="880" height="26" fill="url(#tile)"/></svg>')


for theme in PALETTES:
    (OUT / f"band-{theme}.svg").write_text(band(theme))
    (OUT / f"ask-arq-{theme}.svg").write_text(architecture(theme))
    (OUT / f"hero-{theme}.svg").write_text(hero(theme))
    (OUT / f"timeline-{theme}.svg").write_text(timeline(theme))

for f in sorted(OUT.glob("*.svg")):
    print(f.name, f.stat().st_size)
