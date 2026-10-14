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
import json
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
        bandAccent="#0E7C7B", ring="#0E7C7B", peri="#7A8FD9", chip="#F5F7FC", hubText="#FFFFFF",
    ),
    "dark": dict(
        bg="#0F1430", panel="#161D42", rule="#2A3466", ink="#E8ECF8", muted="#9AA5CC",
        cobalt="#8FA8FF", turq="#3FD0C9", saffron="#F2B04A", mist="#3A4578", band="#5B7BEA",
        bandAccent="#3FD0C9", ring="#3FD0C9", peri="#5F74D8", chip="#1B2350", hubText="#0F1430",
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


def ask_row(c, x_label, x_val, y, size, t0=0.7, t1=None, label="ask", query="what does ammar build?"):
    s, p, A = c.s, c.p, c.A
    q = query
    t1 = t1 or t0 + len(q) * 0.028
    qw = advance("mono", q, size)
    out = [s.text(x_label, y, label, "monob", size, p["cobalt"]), s.text(x_val, y, q, "mono", size, p["ink"]),
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


# ---------------------------------------------------------------- shared node helpers

def box(c, x, y, w, h, title, sub, tfont="sansb", tsize=13.5, sfont="mono", ssize=11.5, sub_cls=None, dim=False):
    s, p = c.s, c.p
    dash = ' stroke-dasharray="4 4"' if dim else ""
    op = ' opacity=".45"' if dim else ""
    sc = f' class="{sub_cls}"' if sub_cls else ""
    return (f'<g{op}><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="10" fill="{p["chip"]}" stroke="{p["rule"]}"{dash}/>'
            + s.text(x + 13, y + h / 2 - 3, title, tfont, tsize, p["ink"])
            + f"<g{sc}>" + s.text(x + 13, y + h / 2 + 14, sub, sfont, ssize, p["muted"]) + "</g></g>")


def light_up(c, x, y, w, h, t):
    """Accent outline and a done dot that appear when a node finishes."""
    p, A = c.p, c.A
    return (f'<g class="{A.fade_in(t, 0.2)}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="10" fill="none" '
            f'stroke="{p["turq"]}" stroke-width="1.8"/><circle cx="{x + w - 12:.1f}" cy="{y + 12:.1f}" r="3.5" fill="{p["turq"]}"/></g>')


def edge(c, d, t=None, dashed=False, arrow=True):
    """Static faint edge, plus an accent copy that draws itself at time t."""
    p, A = c.p, c.A
    mk = ' marker-end="url(#ah)"' if arrow else ""
    da = ' stroke-dasharray="4 4"' if dashed else ""
    out = f'<path d="{d}" fill="none" stroke="{p["rule"]}" stroke-width="1.5"{da}{mk}/>'
    if t is not None:
        out += (f'<path class="{A.draw(t, t + 0.35)}" pathLength="1" d="{d}" fill="none" stroke="{p["turq"]}" '
                f'stroke-width="2"/>')
    return out


def result_block(c, x0, y, lines, stats, t, size=14.5):
    s, p, A = c.s, c.p, c.A
    out = [s.text(x0, y, "result", "monob", size, p["turq"], f'class="{A.fade_in(t)}"')]
    vx = x0 + 76
    ta = t + 0.2
    for j, txt in enumerate(lines):
        svg, ta = stream(c, vx, y + j * 27, [(txt, p["ink"], None)], size, ta)
        out.append(svg)
    sy = y + 27 * len(lines) + 4
    out.append(s.text(vx, sy, stats, "mono", 12.5, p["muted"], f'class="{A.fade_in(ta + 0.2)}"'))
    return out, sy


# ---------------------------------------------------------------- hero panel: agent hub

def hub_panel(c):
    s, p, A, px, py, pw = c.s, c.p, c.A, c.px, c.py, c.pw
    x0, right = px + 28, px + pw - 28
    size = 14.5
    row_y = py + 42
    out = ask_row(c, x0, x0 + 56, row_y, size, query="research 3 competitors, update the CRM and draft a pricing brief")
    c.cover = p["chip"]

    gt = row_y + 30
    nw, nh = 200, 52
    rows = [gt, gt + 84, gt + 168]
    lx, rx = x0, right - nw
    hcx = px + pw / 2
    hw, hh = 176, 66
    hcy = rows[1] + nh / 2
    hl, hr, ht, hb = hcx - hw / 2, hcx + hw / 2, hcy - hh / 2, hcy + hh / 2

    nodes = [  # title, result, x, y, side
        ("Workflow", "plan → research → draft", hcx - nw / 2, rows[0], "top"),
        ("Subagents", "3 researchers, parallel", lx, rows[0], "left"),
        ("Web search", "42 sources read", lx, rows[1], "left"),
        ("MCP tools", "hubspot, notion, slack", rx, rows[0], "right"),
        ("RAG", "past deals + sales docs", lx, rows[2], "left"),
        ("Memory", "account history, Mem0", rx, rows[1], "right"),
        ("Code", "pricing model in Python", rx, rows[2], "right"),
        ("Human review", "approved in Slack", hcx - nw / 2, rows[2], "bottom"),
    ]
    t = 2.5
    edges, boxes = [], []
    for title, res, x, y, side in nodes:
        ncy = y + nh / 2
        if side == "left":
            d = f"M{hl - 2:.1f} {hcy + (ncy - hcy) * 0.3:.1f}L{x + nw + 4:.1f} {ncy:.1f}"
        elif side == "right":
            d = f"M{hr + 2:.1f} {hcy + (ncy - hcy) * 0.3:.1f}L{x - 4:.1f} {ncy:.1f}"
        elif side == "top":
            d = f"M{hcx:.1f} {ht - 2:.1f}L{hcx:.1f} {y + nh + 4:.1f}"
        else:
            d = f"M{hcx:.1f} {hb + 2:.1f}L{hcx:.1f} {y - 4:.1f}"
        edges.append(edge(c, d, t))
        boxes.append(box(c, x, y, nw, nh, title, res, sub_cls=A.fade_in(t + 0.35)) + light_up(c, x, y, nw, nh, t + 0.3))
        t += 0.6
    out += edges + boxes

    # the agent itself
    A.kfs.append("@keyframes hp{0%,100%{opacity:.15}50%{opacity:.7}}")
    A.rules.append(".hp{animation:hp 1.6s ease-in-out infinite}")
    out.append(f'<rect class="hp" x="{hl - 5:.1f}" y="{ht - 5:.1f}" width="{hw + 10}" height="{hh + 10}" rx="17" fill="none" '
               f'stroke="{p["cobalt"]}" stroke-width="1.5"/>')
    out.append(f'<rect x="{hl:.1f}" y="{ht:.1f}" width="{hw}" height="{hh}" rx="14" fill="{p["cobalt"]}"/>')
    out.append(s.text(hcx, hcy - 2, "Agent", "sansb", 16, p["hubText"], anchor="middle"))
    out.append(s.text(hcx, hcy + 17, "Claude Agent SDK", "mono", 11.5, p["hubText"], anchor="middle"))

    c.cover = p["panel"]
    blk, sy = result_block(c, x0, rows[2] + nh + 44,
                           ["Pricing brief drafted from 42 cited sources, 3 CRM deals",
                            "updated, summary posted to Slack after one approval."],
                           "3 subagents, 57 tool calls, hooks on every write", t + 0.2)
    out += blk
    desc = ("An animated agent built on the Claude Agent SDK takes the task research 3 competitors, update the CRM "
            "and draft a pricing brief. It plans the workflow, runs 3 research subagents in parallel, reads 42 web "
            "sources, uses RAG over past deals and sales docs, calls MCP tools for HubSpot, Notion and Slack, recalls "
            "account history from Mem0 memory, builds a pricing model in Python and gets human approval in Slack.")
    return out, sy + 26 - py, desc


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
    tagline = "I build AI agents, workflows, integrations and RAG that run in production."
    assert advance("sans", tagline, 20) < W - 2 * PAD
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


# ---------------------------------------------------------------- toolbox

ICONS = json.loads(Path(__file__).with_name("icons.json").read_text())
AWS = "#FF9900"

# (group title, accent, [(category, [(tool, simple-icons slug or monogram letters, optional monogram colour)])])
TOOLBOX = [
    ("AI systems", "turq", [
        ("Agents and orchestration", [("Claude Agent SDK", "claude"), ("LangGraph", "langgraph"), ("LangChain", "langchain"), ("LlamaIndex", "LI"),
                                      ("MCP", "modelcontextprotocol"), ("Composio", "C"), ("Mem0", "M0")]),
        ("Retrieval and documents", [("Pinecone", "P"), ("pgvector", "postgresql"), ("Cohere", "C"),
                                     ("Sentence Transformers", "huggingface"), ("Docling", "D"), ("PyMuPDF", "Mu")]),
        ("Models and inference", [("OpenAI", "O"), ("Anthropic", "anthropic"), ("Gemini", "googlegemini"), ("Groq", "G"),
                                  ("LLaMA", "meta"), ("Whisper", "W"), ("Hugging Face", "huggingface"),
                                  ("PyTorch", "pytorch")]),
    ]),
    ("Platform engineering", "cobalt", [
        ("Backend and data", [("FastAPI", "fastapi"), ("Django", "django"), ("Celery", "celery"), ("RabbitMQ", "rabbitmq"),
                              ("Redis", "redis"), ("PostgreSQL", "postgresql"), ("SQLAlchemy", "sqlalchemy"),
                              ("MongoDB", "mongodb"), ("Pydantic", "pydantic")]),
        ("Frontend and apps", [("React", "react"), ("Next.js", "nextdotjs"), ("Tailwind CSS", "tailwindcss"),
                               ("shadcn/ui", "shadcnui"), ("TanStack Query", "reactquery"), ("React Native", "react"),
                               ("Expo", "expo"), ("Chrome extensions", "googlechrome"), ("Tauri", "tauri")]),
        ("Cloud and DevOps", [("AWS ECS", "ECS", AWS), ("AWS Lambda", "λ", AWS), ("Amazon S3", "S3", AWS),
                              ("Amazon RDS", "RDS", AWS), ("Terraform", "terraform"), ("Docker", "docker"),
                              ("GitHub Actions", "githubactions"), ("Vercel", "vercel")]),
        ("Quality and observability", [("LangSmith", "LS"), ("Sentry", "sentry"), ("CloudWatch", "CW", AWS),
                                       ("Pytest", "pytest"), ("Playwright", "PW"), ("Vitest", "vitest"), ("Ruff", "ruff")]),
        ("Languages", [("Python", "python"), ("TypeScript", "typescript"), ("JavaScript", "javascript"),
                       ("Rust", "rust"), ("C++", "cplusplus")]),
    ]),
]


def luminance(hex_):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def toolbox(theme):
    p = PALETTES[theme]
    s = Svg()
    W, PAD = 880, 36
    label_w = 218
    cx0, cx1 = PAD + label_w, W - PAD
    chip_h, gap, icon = 32, 8, 16
    els = []
    y = PAD - 4
    alt = []
    for g, (title, accent, cats) in enumerate(TOOLBOX):
        if g:
            y += 18
        y += 26
        els.append(s.text(PAD, y, title, "casual", 25, p["ink"]))
        els.append(f'<rect x="{PAD + advance("casual", title, 25) + 14:.1f}" y="{y - 8}" '
                   f'width="{W - PAD - advance("casual", title, 25) - 14 - PAD:.1f}" height="1.5" fill="{p[accent]}" opacity=".55"/>')
        y += 18
        for k, (cat, tools) in enumerate(cats):
            if k:
                els.append(f'<line x1="{PAD}" y1="{y + 7}" x2="{W - PAD}" y2="{y + 7}" stroke="{p["rule"]}"/>')
                y += 14
            top = y
            els.append(f'<rect x="{PAD}" y="{top + 8}" width="3.5" height="16" rx="1.75" fill="{p[accent]}"/>')
            els.append(s.text(PAD + 14, top + 21, cat, "sansb", 14, p["ink"]))
            x, row = cx0, top
            for tool in tools:
                name, ref = tool[0], tool[1]
                tw = advance("sans", name, 13.5)
                w = 10 + icon + 8 + tw + 12
                if x + w > cx1:
                    x, row = cx0, row + chip_h + gap
                els.append(f'<rect x="{x:.1f}" y="{row}" width="{w:.1f}" height="{chip_h}" rx="9" fill="{p["panel"]}" stroke="{p["rule"]}"/>')
                ix, iy = x + 10, row + (chip_h - icon) / 2
                if ref in ICONS:
                    col = ICONS[ref]["hex"]
                    if contrast(col, p["panel"]) < 2.2:
                        col = p["ink"]
                    els.append(f'<path transform="translate({ix:.1f} {iy:.1f}) scale({icon / 24})" d="{ICONS[ref]["path"]}" fill="{col}"/>')
                else:
                    bg = tool[2] if len(tool) > 2 else p[accent]
                    fg = "#FFFFFF" if contrast("#FFFFFF", bg) >= contrast("#0F1430", bg) else "#0F1430"
                    fs = {1: 10, 2: 8, 3: 6.2}[len(ref)]
                    els.append(f'<rect x="{ix:.1f}" y="{iy:.1f}" width="{icon}" height="{icon}" rx="4" fill="{bg}"/>')
                    els.append(s.text(ix + icon / 2, iy + icon / 2 + fs * 0.36, ref, "monob", fs, fg, anchor="middle"))
                els.append(s.text(x + 10 + icon + 8, row + chip_h / 2 + 4.6, name, "sans", 13.5, p["ink"]))
                x += w + gap
            y = row + chip_h + 8
            alt.append(f"{cat}: {', '.join(t[0] for t in tools)}.")
    H = y + PAD - 12
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Toolbox</title>
<desc id="d">{esc(" ".join(alt))}</desc>
<style>{s.fonts_css()}</style>
<rect width="{W}" height="{H}" rx="18" fill="{p["bg"]}"/>
{"".join(els)}
</svg>''', " ".join(alt)


def band(theme):
    p = PALETTES[theme]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="26" viewBox="0 0 880 26" aria-hidden="true">'
            f'<defs>{tile_pattern(p)}</defs><rect width="880" height="26" fill="url(#tile)"/></svg>')


for theme in PALETTES:
    (OUT / f"hero-{theme}.svg").write_text(hero(theme, hub_panel, 18.0))
    (OUT / f"band-{theme}.svg").write_text(band(theme))
    svg, alt = toolbox(theme)
    (OUT / f"toolbox-{theme}.svg").write_text(svg)

for f in sorted(OUT.glob("*.svg")):
    print(f.name, f.stat().st_size)
