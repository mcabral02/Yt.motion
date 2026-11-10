# CAPTION STYLE: shared by every renderer so all videos look the same.
# Script marks: *word* = red (noise/problem), ~word~ = cyan (fix/anti-noise), ^word^ = amber (key idea).
import math, random, cairo

W, H = 1080, 1920
AMBER, WHITE, NAVY = (1.0, 0.71, 0.28), (0.96, 0.97, 0.99), (0.055, 0.086, 0.188)
RED, CYAN = (1.0, 0.36, 0.25), (0.30, 0.85, 1.0)
STYLE = {"*": RED, "~": CYAN, "^": AMBER}

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def pop(x):
    x = clamp(x); c = 2.2
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def text(c, s, x, y, size, rgb=WHITE, a=1.0, center=True, outline=0):
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(size)
    e = c.text_extents(s)
    c.move_to(x - (e.x_advance / 2 if center else 0), y); c.text_path(s)
    if outline:
        c.set_source_rgba(0, 0, 0, a); c.set_line_width(outline); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke_preserve()
    c.set_source_rgba(*rgb, a); c.fill()
    return e.x_advance

def parse(sentence):
    """-> list of (word as shown, color or None)."""
    out = []
    for tok in sentence.split():
        col = None
        for m, rgb in STYLE.items():
            if m in tok: col = rgb
        out.append((tok.replace("*", "").replace("~", "").replace("^", ""), col))
    return out

def timeline(sentence, speech):
    """Group words 1-2 at a time and guess when each is spoken (longer words take longer, pause after punctuation)."""
    words = parse(sentence)
    groups, cur = [], []
    for w in words:
        if w[1] and cur: groups.append(cur); cur = []        # a keyword always starts its own group
        cur.append(w)
        if len(cur) == 2 or w[0][-1] in ",.?!" or w[1]: groups.append(cur); cur = []
    if cur: groups.append(cur)
    flat = [w for g in groups for w in g]
    weights = [len(w[0].strip(",.?!")) + 2 for w in flat]
    pause = [0.25 if w[0][-1] in ",.?!" else 0 for w in flat]
    unit = (speech - sum(pause)) / sum(weights)
    t, times = 0.0, []
    for wgt, p in zip(weights, pause):
        times.append(t); t += wgt * unit + p
    res, i = [], 0
    for gi, g in enumerate(groups):
        res.append((g, times[i:i + len(g)], random.Random(gi * 31 + len(sentence)).uniform(-4, 4))); i += len(g)
    return res

def keyword_times(tl):
    return [ts[k] for g, ts, _ in tl for k, (w, col) in enumerate(g) if col]

def draw(c, tl, t, y=1330):
    current = None
    for g, ts, tilt in tl:
        if t >= ts[0] - 0.04: current = (g, ts, tilt)
    if not current: return
    g, ts, tilt = current
    age = t - ts[0]
    s = 0.35 + 0.65 * pop(age / 0.16)                        # pops in from small with overshoot
    rise = 40 * (1 - ease(age / 0.16))                       # and bounces up
    big = any(col for _, col in g)
    c.save(); c.translate(W / 2, y + rise); c.rotate(math.radians(tilt * (1 - ease(age / 0.3)) + (tilt * 0.4 if big else 0)))
    c.scale(s, s)
    size = 138 if big else 112
    if big: size *= 1 + 0.04 * math.sin(age * 18) * math.exp(-age * 3)   # keyword wobble
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(size)
    words = [w.upper() for w, _ in g]
    widths = [c.text_extents(w + " ").x_advance for w in words]
    total = sum(widths) - c.text_extents(" ").x_advance
    if total > 960: c.scale(960 / total, 960 / total)
    x = -total / 2
    active = max(k for k in range(len(words)) if k == 0 or t >= ts[k])
    for k, (w, wd) in enumerate(zip(words, widths)):
        col = g[k][1] or (AMBER if k == active and len(words) > 1 else WHITE)
        c.move_to(x + 6, 8); c.text_path(w); c.set_source_rgba(0, 0, 0, 0.45); c.fill()      # drop shadow
        c.move_to(x, 0); c.text_path(w)
        c.set_source_rgb(0, 0, 0); c.set_line_width(20); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke_preserve()
        c.set_source_rgb(*col); c.fill()
        x += wd
    c.restore()

def label(c, s, t, y=250):
    """Small pill tag at the top that slides in, e.g. 'ANTI-NOISE'."""
    if not s: return
    a = ease((t - 0.3) / 0.3)
    if a <= 0: return
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(52)
    w = c.text_extents(s).x_advance + 70
    x = (W - w) / 2 - 300 * (1 - a)
    c.set_source_rgba(*AMBER, 0.97 * a)
    c.new_sub_path(); r = 40
    c.arc(x + r, y + r, r, math.pi / 2, 3 * math.pi / 2); c.arc(x + w - r, y + r, r, -math.pi / 2, math.pi / 2)
    c.close_path(); c.fill()
    text(c, s, x + w / 2, y + 58, 52, NAVY, a)

def logo(c, a, cx=W / 2 - 230, cy=1640):
    if a <= 0: return
    c.set_source_rgba(*AMBER, a); c.set_line_width(22); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx - 40, cy - 40); c.line_to(cx + 40, cy + 40); c.stroke()
    c.move_to(cx + 40, cy - 40); c.line_to(cx - 40, cy + 40); c.stroke()
    w = text(c, "xplain", cx + 85, cy + 30, 84, WHITE, a, center=False, outline=12)
    text(c, ".motion", cx + 85 + w, cy + 30, 84, AMBER, a, center=False, outline=12)
