# CAPTION STYLE: shared by every renderer so all videos look the same.
import math, cairo

W, H = 1080, 1920
AMBER, WHITE, NAVY = (1.0, 0.71, 0.28), (0.96, 0.97, 0.99), (0.055, 0.086, 0.188)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def pop(x):
    x = clamp(x); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def text(c, s, x, y, size, rgb=WHITE, a=1.0, center=True, outline=0):
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(size)
    e = c.text_extents(s)
    c.move_to(x - (e.x_advance / 2 if center else 0), y); c.text_path(s)
    if outline:
        c.set_source_rgba(0, 0, 0, a); c.set_line_width(outline); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke_preserve()
    c.set_source_rgba(*rgb, a); c.fill()
    return e.x_advance

def chunks(sentence):
    out, cur = [], []
    for w in sentence.split():
        cur.append(w)
        if len(cur) == 3 or w[-1] in ",.?!": out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def timeline(sentence, speech):
    """Guess when each word is spoken: longer words take longer, pause after punctuation."""
    groups = chunks(sentence)
    flat = [w for g in groups for w in g]
    weights = [len(w.strip(",.?!")) + 2 for w in flat]
    pause = [0.25 if w[-1] in ",.?!" else 0 for w in flat]
    unit = (speech - sum(pause)) / sum(weights)
    t, times = 0.0, []
    for wgt, p in zip(weights, pause):
        times.append(t); t += wgt * unit + p
    res, i = [], 0
    for g in groups:
        res.append((g, times[i:i + len(g)])); i += len(g)
    return res

def draw(c, tl, t, y=1360):
    current = None
    for g, ts in tl:
        if t >= ts[0] - 0.05: current = (g, ts)
    if not current: return
    g, ts = current
    s = 0.85 + 0.15 * pop((t - ts[0]) / 0.18)
    c.save(); c.translate(W / 2, y); c.scale(s, s)
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(92)
    words = [w.upper() for w in g]
    widths = [c.text_extents(w + " ").x_advance for w in words]
    total = sum(widths)
    if total > 940: c.scale(940 / total, 940 / total)
    x = -total / 2 + c.text_extents(" ").x_advance / 2
    active = max(k for k in range(len(words)) if k == 0 or t >= ts[k])
    for k, (w, wd) in enumerate(zip(words, widths)):
        c.move_to(x, 0); c.text_path(w)
        c.set_source_rgb(0, 0, 0); c.set_line_width(16); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke_preserve()
        c.set_source_rgb(*(AMBER if k == active else WHITE)); c.fill()
        x += wd
    c.restore()

def logo(c, a, cx=W / 2 - 230, cy=1640):
    if a <= 0: return
    c.set_source_rgba(*AMBER, a); c.set_line_width(22); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx - 40, cy - 40); c.line_to(cx + 40, cy + 40); c.stroke()
    c.move_to(cx + 40, cy - 40); c.line_to(cx - 40, cy + 40); c.stroke()
    w = text(c, "xplain", cx + 85, cy + 30, 84, WHITE, a, center=False, outline=12)
    text(c, ".motion", cx + 85 + w, cy + 30, 84, AMBER, a, center=False, outline=12)
