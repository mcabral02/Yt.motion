# ANIMATION + CAPTION AGENT: draws every scene, burns in captions, renders the Short.
import json, math, random, subprocess, os, sys, cairo

W, H, FPS = 1080, 1920, 30
NAVY, NAVY2 = (0.055, 0.086, 0.188), (0.086, 0.137, 0.27)
CYAN, AMBER, WHITE = (0.31, 0.84, 0.91), (1.0, 0.71, 0.28), (0.96, 0.97, 0.99)
CORAL = (1.0, 0.48, 0.35)

script = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "script.json"))
timings = {t["id"]: t for t in json.load(open("out/timings.json"))}

# ---------- small helpers ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3              # fast start, soft stop
def pop(x):                                                       # overshoot "pop" 0->1
    x = clamp(x); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
def prog(t, a, b): return clamp((t - a) / (b - a))

def circle(c, x, y, r, rgb, a=1.0):
    if r <= 0: return
    c.set_source_rgba(*rgb, a); c.arc(x, y, r, 0, 2 * math.pi); c.fill()

def background(c, top=NAVY, bottom=NAVY2):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *top); g.add_color_stop_rgb(1, *bottom)
    c.set_source(g); c.paint()
    c.set_source_rgba(1, 1, 1, 0.045)                             # brand dot grid
    for gx in range(30, W, 60):
        for gy in range(30, H, 60):
            c.arc(gx, gy, 2.2, 0, 2 * math.pi); c.fill()

STARS = [(random.Random(i).uniform(0, W), random.Random(i * 7 + 1).uniform(0, 1150),
          random.Random(i * 13 + 2).uniform(1.5, 4.5)) for i in range(140)]
def stars(c, t, a=1.0):
    for i, (x, y, r) in enumerate(STARS):
        tw = 0.55 + 0.45 * math.sin(t * 2.5 + i)
        circle(c, x, y, r, WHITE, a * tw)

def earth(c, x, y, r, t=0.0):
    c.save()
    circle(c, x, y, r * 1.12, CYAN, 0.12)                         # atmosphere glow
    c.arc(x, y, r, 0, 2 * math.pi); c.clip()
    circle(c, x, y, r, (0.16, 0.42, 0.85))
    c.set_source_rgb(0.30, 0.74, 0.45)                            # drifting continents
    for (dx, dy, rr) in [(-0.35, -0.25, 0.38), (0.25, 0.3, 0.3), (0.45, -0.35, 0.22), (-0.1, 0.55, 0.2)]:
        ox = ((dx + t * 0.06 + 1.5) % 3.0 - 1.5) * r
        c.arc(x + ox, y + dy * r, rr * r, 0, 2 * math.pi); c.fill()
    g = cairo.RadialGradient(x - r * 0.4, y - r * 0.4, r * 0.1, x, y, r * 1.05)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.18); g.add_color_stop_rgba(0.6, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0.1, 0.45)
    c.set_source(g); c.paint()
    c.restore()

def moon(c, x, y, r, a=1.0):
    if r <= 0: return
    circle(c, x, y, r * 1.35, WHITE, 0.10 * a)
    circle(c, x, y, r, (0.80, 0.82, 0.88), a)
    for (dx, dy, rr) in [(-0.3, -0.2, 0.22), (0.3, 0.25, 0.16), (0.15, -0.4, 0.12), (-0.2, 0.45, 0.1)]:
        circle(c, x + dx * r, y + dy * r, rr * r, (0.62, 0.65, 0.74), a)

def sun(c, x, y, r, t):
    g = cairo.RadialGradient(x, y, r * 0.5, x, y, r * 2.2)
    g.add_color_stop_rgba(0, *AMBER, 0.55); g.add_color_stop_rgba(1, *AMBER, 0)
    c.set_source(g); c.arc(x, y, r * 2.2, 0, 2 * math.pi); c.fill()
    circle(c, x, y, r * (1 + 0.02 * math.sin(t * 4)), (1.0, 0.82, 0.38))

def text(c, s, x, y, size, rgb=WHITE, a=1.0, weight=cairo.FONT_WEIGHT_BOLD, center=True):
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, weight); c.set_font_size(size)
    e = c.text_extents(s)
    c.move_to(x - (e.x_advance / 2 if center else 0), y)
    c.set_source_rgba(*rgb, a); c.show_text(s)
    return e.x_advance

def tag(c, label, t):
    a = ease(t / 0.4)
    c.set_font_size(40); c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    w = c.text_extents(label).x_advance + 56
    x, y = (W - w) / 2, 190
    c.set_source_rgba(*AMBER, 0.95 * a)
    c.new_sub_path(); rr = 34
    c.arc(x + rr, y + rr, rr, math.pi / 2, 3 * math.pi / 2); c.arc(x + w - rr, y + rr, rr, -math.pi / 2, math.pi / 2)
    c.close_path(); c.fill()
    text(c, label, W / 2, y + 48, 40, NAVY, a)

# ---------- scenes: each draws frame at time t (seconds) of duration d ----------
def moon_vanish(c, t, d):
    background(c); stars(c, t, 0.6)
    s = pop(t / 0.5)
    earth(c, W / 2, 820, 230 * s, t)
    ang = -0.5 + t * 0.9
    vanish = prog(t, d * 0.55, d * 0.8)
    mx, my = W / 2 + math.cos(ang) * 400, 820 + math.sin(ang) * 140
    moon(c, mx, my, 80 * s * (1 - ease(vanish)) * (1 + 0.3 * math.sin(vanish * math.pi)))
    if 0 < vanish < 1:                                            # poof ring + sparks
        circle(c, mx, my, 40 + 260 * vanish, WHITE, 0.0)
        c.set_source_rgba(*WHITE, 0.8 * (1 - vanish)); c.set_line_width(8)
        c.arc(mx, my, 40 + 200 * ease(vanish), 0, 2 * math.pi); c.stroke()
        for k in range(10):
            a2 = k * 2 * math.pi / 10
            circle(c, mx + math.cos(a2) * 230 * ease(vanish), my + math.sin(a2) * 230 * ease(vanish), 9 * (1 - vanish), AMBER)

def dark_sky(c, t, d):
    fade = ease(prog(t, d * 0.2, d * 0.55))
    background(c, top=tuple(v * (1 - 0.6 * fade) for v in NAVY), bottom=tuple(v * (1 - 0.6 * fade) for v in NAVY2))
    stars(c, t, 0.35 + 0.65 * fade)                               # no moon = brighter stars
    g = cairo.RadialGradient(780, 430, 60, 780, 430, 520)         # moonlight glow
    g.add_color_stop_rgba(0, 0.9, 0.93, 1, 0.35 * (1 - fade)); g.add_color_stop_rgba(1, 0.9, 0.93, 1, 0)
    c.set_source(g); c.paint()
    moon(c, 780, 430, 110, 1 - fade)
    for i, (col, base, amp) in enumerate([((0.10, 0.16, 0.30), 1000, 70), ((0.06, 0.10, 0.20), 1060, 50)]):
        k = 1 - 0.55 * fade
        c.set_source_rgb(*(v * k for v in col)); c.move_to(0, H)
        for x in range(0, W + 20, 20):
            c.line_to(x, base + amp * math.sin(x / 170 + i * 2))
        c.line_to(W, H); c.close_path(); c.fill()

def tides(c, t, d):
    background(c)
    shrink = ease(prog(t, d * 0.2, d * 0.65))
    ex, ey, r = W / 2 - 60, 760, 210
    moon(c, 120, ey, 70, 1 - shrink)
    sun(c, W + 10, ey, 120, t)
    bulge = 1 + 0.42 * (1 - shrink) + 0.18 * shrink               # ocean stretch
    c.save(); c.translate(ex, ey); c.scale(bulge, 1 / bulge ** 0.25)
    c.arc(0, 0, r * 1.08, 0, 2 * math.pi); c.restore()
    c.set_source_rgba(*CYAN, 0.45); c.fill()
    earth(c, ex, ey, r, t)
    # tide meter
    bx, by, bh = 160, 1030, 46
    text(c, "TIDE HEIGHT", bx, by - 18, 34, WHITE, 0.8, center=False)
    c.set_source_rgba(1, 1, 1, 0.12); c.rectangle(bx, by, 760, bh); c.fill()
    frac = 1 - 0.55 * shrink
    c.set_source_rgb(*CYAN); c.rectangle(bx, by, 760 * frac * ease(t / 0.6), bh); c.fill()
    text(c, f"{round(frac * 100)}%", bx + 760, by - 18, 34, CYAN, 1, center=False) if False else \
        text(c, f"{round(frac * 100)}%", bx + 700, by - 18, 34, CYAN)

def coral(c, t, d):
    background(c, top=(0.03, 0.18, 0.32), bottom=(0.02, 0.08, 0.16))
    lost = ease(prog(t, d * 0.35, d * 0.6))
    c.set_source_rgba(1, 1, 1, 0.06)                              # light rays
    for i in range(5):
        x = 120 + i * 220 + 30 * math.sin(t + i)
        c.move_to(x, 0); c.line_to(x + 120, 0); c.line_to(x + 260, 1150); c.line_to(x + 140, 1150); c.close_path(); c.fill()
    moon(c, W / 2, 330, 70, 1 - lost)
    if lost > 0.3: text(c, "?", W / 2, 370, 130, AMBER, ease((lost - 0.3) / 0.5))
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    def branch(x, y, ang, length, depth):
        if depth == 0: return
        sway = 0.06 * math.sin(t * 1.8 + x / 90)
        x2, y2 = x + math.cos(ang + sway) * length, y + math.sin(ang + sway) * length
        c.set_line_width(4 + depth * 5); c.set_source_rgb(*CORAL)
        c.move_to(x, y); c.line_to(x2, y2); c.stroke()
        branch(x2, y2, ang - 0.45, length * 0.72, depth - 1); branch(x2, y2, ang + 0.4, length * 0.72, depth - 1)
    for i, bx in enumerate([180, 420, 660, 900]):
        branch(bx, 1130, -math.pi / 2, 120 + 25 * (i % 2), 4)
    for i in range(60):                                           # spawning: synced, then scattered
        rng = random.Random(i)
        bx = [180, 420, 660, 900][i % 4] + rng.uniform(-90, 90)
        phase = (t * 0.35 + rng.uniform(0, 1) * lost) % 1
        y = 1050 - phase * 650
        a = (1 - phase) * (1 - 0.75 * lost * rng.random())
        circle(c, bx + 25 * math.sin(phase * 6 + i), y, 7, (1, 0.9, 0.85), a)
    c.set_source_rgb(0.04, 0.09, 0.15); c.rectangle(0, 1120, W, H); c.fill()

def tilt(c, t, d):
    background(c); stars(c, t, 0.4)
    ex, ey, r = W / 2, 800, 230
    grow = ease(prog(t, d * 0.15, d * 0.7))
    deg = 23.4 + (8 + 40 * grow) * math.sin(t * 2.2) * grow
    sun(c, -40, ey, 110, t)
    c.save(); c.translate(ex, ey); c.rotate(math.radians(deg))
    c.set_source_rgba(*WHITE, 0.85); c.set_line_width(7); c.set_dash([24, 16])
    c.move_to(0, -r - 120); c.line_to(0, r + 120); c.stroke(); c.set_dash([])
    c.restore()
    earth(c, ex, ey, r, t)
    c.save(); c.translate(ex, ey); c.rotate(math.radians(deg))      # day/night shadow on right
    c.arc(0, 0, r, 0, 2 * math.pi); c.clip(); c.restore()
    c.save(); c.arc(ex, ey, r, 0, 2 * math.pi); c.clip()
    c.set_source_rgba(0, 0, 0.05, 0.45); c.rectangle(ex + r * 0.15, ey - r, r, 2 * r); c.fill(); c.restore()
    col = AMBER if abs(deg - 23.4) > 12 else CYAN
    text(c, f"TILT {abs(deg):.0f}°", W / 2, 1150, 64, col)

def outro(c, t, d):
    background(c); stars(c, t, 0.6)
    ex, ey = W / 2, 760
    earth(c, ex, ey, 200, t)
    back = pop(t / 0.6)
    ang = 2.6 + t * 0.8
    c.set_source_rgba(*WHITE, 0.15); c.set_line_width(3)
    c.save(); c.translate(ex, ey); c.scale(1, 0.35); c.arc(0, 0, 380, 0, 2 * math.pi); c.restore(); c.stroke()
    moon(c, ex + math.cos(ang) * 380, ey + math.sin(ang) * 133, 70 * back)
    a = ease(prog(t, d * 0.55, d * 0.75))                        # logo card
    cx, cy = W / 2 - 230, 1100
    c.set_source_rgba(*AMBER, a); c.set_line_width(22); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx - 40, cy - 40); c.line_to(cx + 40, cy + 40); c.stroke()      # "X" mark
    c.move_to(cx + 40, cy - 40); c.line_to(cx - 40, cy + 40); c.stroke()
    w = text(c, "xplain", cx + 85, cy + 26, 84, WHITE, a, center=False)
    text(c, ".motion", cx + 85 + w, cy + 26, 84, AMBER, a, center=False)

SCENES = {f.__name__: f for f in [moon_vanish, dark_sky, tides, coral, tilt, outro]}

# ---------- captions ----------
def chunks(sentence):
    words, out, cur = sentence.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) == 3 or w[-1] in ",.?!": out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def caption_timeline(text_, speech):
    groups = chunks(text_)
    flat = [w for g in groups for w in g]
    weights = [len(w.strip(",.?!")) + 2 for w in flat]
    pause = [0.25 if w[-1] in ",.?!" else 0 for w in flat]          # breath after punctuation
    unit = (speech - sum(pause)) / sum(weights)
    t, times = 0.0, []
    for wgt, p in zip(weights, pause):
        times.append((t, t + wgt * unit)); t += wgt * unit + p
    res, i = [], 0
    for g in groups:
        res.append((g, times[i:i + len(g)])); i += len(g)
    return res

def draw_caption(c, tl, t):
    current = None
    for g, ts in tl:
        if t >= ts[0][0] - 0.05: current = (g, ts)
    if not current: return
    g, ts = current
    since = t - ts[0][0]
    s = 0.85 + 0.15 * pop(since / 0.18)
    size = 92
    c.save(); c.translate(W / 2, 1360); c.scale(s, s)
    c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(size)
    words = [w.upper() for w in g]
    widths = [c.text_extents(w + " ").x_advance for w in words]
    total = sum(widths)
    if total > 940:                                               # shrink long lines to fit the screen
        c.scale(940 / total, 940 / total)
    x = -total / 2 + c.text_extents(" ").x_advance / 2
    starts = [a for a, _ in ts] + [1e9]
    active = max(k for k in range(len(words)) if k == 0 or t >= starts[k])
    for k, (w, wd) in enumerate(zip(words, widths)):
        c.move_to(x, 0); c.text_path(w)
        c.set_source_rgb(0, 0, 0); c.set_line_width(16); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke_preserve()
        c.set_source_rgb(*(AMBER if k == active else WHITE)); c.fill()
        x += wd
    c.restore()

# ---------- render ----------
def render_scene(scene, only_frame=None):
    tm = timings[scene["id"]]
    d, n = tm["duration"], round(tm["duration"] * FPS)
    tl = caption_timeline(scene["text"], tm["speech"])
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    label = "WHAT IF?" if script["scenes"].index(scene) < len(script["scenes"]) - 1 else "WHAT IF?"
    def frame(i):
        t = i / FPS
        c.save(); SCENES[scene["visual"]](c, t, d); c.restore()
        tag(c, label, tm["start"] + t)
        draw_caption(c, tl, t)
        surf.flush()
    if only_frame is not None:
        frame(only_frame); surf.write_to_png(f"out/preview_{scene['id']}.png"); return
    tmp, final = f"out/scene_{scene['id']}.tmp.mp4", f"out/scene_{scene['id']}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "18", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for i in range(n):
        frame(i); p.stdin.write(surf.get_data())
    p.stdin.close()
    if p.wait() == 0: os.replace(tmp, final)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "preview":                                         # one still per scene, busiest moment
        for s in script["scenes"]:
            render_scene(s, only_frame=round(timings[s["id"]]["duration"] * FPS * 0.6))
    else:
        for s in script["scenes"]: render_scene(s); print("rendered", s["id"], flush=True)
        with open("out/list.txt", "w") as f:
            for s in script["scenes"]: f.write(f"file 'scene_{s['id']}.mp4'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "out/list.txt",
                        "-i", "out/narration.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", "out/short.mp4"], check=True)
        print("done: out/short.mp4")
