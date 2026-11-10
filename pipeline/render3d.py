# 3D ANIMATOR: builds the clay-style set in Blender and renders each scene as frames.
# Usage: python3 render3d.py <script.json> all [scene ids...]         -> every frame (resumes if stopped)
#        python3 render3d.py <script.json> preview <id>:<t> [...]     -> single stills (t in seconds)
# Each scene in the script names a "visual"; the function with that name below poses everything for time t.
import bpy, json, math, os, sys, time, random

SCRIPT = json.load(open(sys.argv[1]))
TIMINGS = {t["id"]: t for t in json.load(open("out/timings.json"))}
FPS3D = 15                      # 3D frames per second (each shown twice in the 30 fps video)
RES = (540, 960)                # half of 1080x1920; compose.py upscales
OUT = os.path.abspath("out/3d")

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)          # smooth in and out
def snap(x): x = clamp(x); return 1 - (1 - x) ** 4              # fast start, soft stop (punchy camera)
def prog(t, a, b): return clamp((t - a) / (b - a))
def lerp(a, b, k): return tuple(x + (y - x) * k for x, y in zip(a, b))
def add(a, b): return tuple(x + y for x, y in zip(a, b))

# ---------------- render settings ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = 10; sc.cycles.use_adaptive_sampling = True; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4; sc.render.use_persistent_data = True
sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -1.0

def mat(name, rgb, rough=0.5, sss=0.0, emit=0.0, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss; b.inputs["Metallic"].default_value = metal
    b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = emit
    return m
def glow(m, v): m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = v
def alpha(m, v): m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = v

GROUPS = {}                     # name -> list of objects, so whole props can be shown/hidden
def reg(o, group):
    if group: GROUPS.setdefault(group, []).append(o)
    return o
def show(group, on=True):
    for o in GROUPS.get(group, []): o.hide_render = not on

def sphere(name, r, loc, m, scale=(1, 1, 1), parent=None, group=None, seg=40):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.object; o.name = name; o.scale = scale; bpy.ops.object.shade_smooth()
    o.data.materials.append(m); o.parent = parent; return reg(o, group)
def cyl(name, r, depth, loc, rot, m, parent=None, group=None, bevel=0.0, verts=40):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.object; o.name = name; bpy.ops.object.shade_smooth(); o.data.materials.append(m); o.parent = parent
    if bevel: b = o.modifiers.new("b", 'BEVEL'); b.width = bevel; b.segments = 3
    return reg(o, group)
def box(name, size, loc, m, parent=None, group=None, bevel=0.03, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size; o.data.materials.append(m); o.parent = parent
    if bevel: b = o.modifiers.new("b", 'BEVEL'); b.width = bevel; b.segments = 3
    return reg(o, group)
def torus(name, R, r, loc, rot, m, parent=None, group=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; bpy.ops.object.shade_smooth(); o.data.materials.append(m); o.parent = parent
    return reg(o, group)
def empty(loc=(0, 0, 0), parent=None, group=None):
    bpy.ops.object.empty_add(location=loc); o = bpy.context.object; o.parent = parent; return reg(o, group)
def tube(name, n, m, depth=0.035, parent=None, group=None):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = depth; cu.bevel_resolution = 4; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(n - 1)
    o = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(o)
    o.data.materials.append(m); o.parent = parent; return reg(o, group)

# ---------------- materials ----------------
SKIN = mat("skin", (0.85, 0.56, 0.42), 0.45, 0.25)
WHITE = mat("eyewhite", (0.95, 0.95, 0.95), 0.15)
DARK = mat("dark", (0.02, 0.02, 0.03), 0.2)
PHONES = mat("phones", (0.10, 0.12, 0.18), 0.35)
CUP_L = mat("cup_left", (0.10, 0.12, 0.18), 0.35)                  # can turn see-through for the cutaway
CUSHION = mat("cushion", (0.20, 0.22, 0.28), 0.8)
SHIRT = mat("shirt", (0.95, 0.55, 0.18), 0.7)
NOISE = mat("noise", (1.0, 0.30, 0.15), 0.4, emit=0.5)
ANTI = mat("anti", (0.10, 0.70, 0.95), 0.4, emit=0.5)
CALM = mat("calm", (0.95, 0.95, 0.95), 0.4, emit=0.8)
VOICEW = mat("voicewave", (1.0, 0.71, 0.28), 0.4, emit=0.6)
MICGLOW = mat("mic", (1.0, 0.71, 0.28), 0.3)
INMIC = mat("inmic", (0.10, 0.70, 0.95), 0.3)
RING = mat("ring", (1.0, 0.71, 0.28), 0.4, emit=0.9)
METAL = mat("metal", (0.78, 0.80, 0.84), 0.3, metal=0.6)
FANM = mat("fan", (0.30, 0.32, 0.36), 0.35, metal=0.5)
AIRM = mat("air", (0.92, 0.95, 1.0), 0.5, emit=0.3)
CHIPM = mat("chip", (0.08, 0.09, 0.11), 0.4)
GOLD = mat("gold", (1.0, 0.75, 0.3), 0.25, metal=1.0)
CHIPLED = mat("chipled", (0.10, 0.70, 0.95), 0.3, emit=1.0)
FUR = mat("fur", (0.62, 0.38, 0.20), 0.8, 0.1)
FUR2 = mat("fur2", (0.95, 0.88, 0.75), 0.8, 0.1)
BACK = mat("backdrop", (0.30, 0.42, 0.62), 0.9)

# ---------------- character (original design) ----------------
ROOT = empty(group="char")
HEAD = empty(parent=ROOT, group="char")
sphere("head", 1.0, (0, 0, 0), SKIN, (1, 1, 1.08), HEAD, "char")
EYES, PUPILS, BROWS = [], [], []
for s in (-1, 1):
    EYES.append(sphere("eye", 0.2, (0.33 * s, -0.86, 0.22), WHITE, parent=HEAD, group="char"))
    PUPILS.append(sphere("pupil", 0.095, (0.33 * s, -1.03, 0.22), DARK, parent=HEAD, group="char"))
    BROWS.append(sphere("brow", 0.13, (0.33 * s, -0.86, 0.52), DARK, (1.3, 0.5, 0.3), HEAD, "char"))
sphere("nose", 0.13, (0, -1.05, 0.0), SKIN, (1, 1, 1.1), HEAD, "char")
MOUTH = tube("mouth", 15, DARK, 0.04, HEAD, "char")
def set_mouth(curve, open_=0.0):            # curve > 0 smile, < 0 frown
    for i, p in enumerate(MOUTH.data.splines[0].points):
        x = -0.28 + 0.56 * i / 14
        z = -0.38 + curve * (x * x - 0.078) * 2.2 - open_ * 0.12 * math.sin(math.pi * i / 14)
        y = -math.sqrt(max(0.0, 1 - x * x - (z / 1.08) ** 2)) - 0.03
        p.co = (x, y, z, 1)
BAND = tube("band", 40, PHONES, 0.09, HEAD, "char")
for i, p in enumerate(BAND.data.splines[0].points):
    a = math.pi * i / 39
    p.co = (1.12 * math.cos(a), 0.05, 1.18 * math.sin(a) + 0.05, 1)
for s in (-1, 1):
    cyl("cup", 0.48, 0.32, (1.16 * s, 0.05, 0.0), (0, math.pi / 2, 0), CUP_L if s < 0 else PHONES, HEAD, "char", 0.08)
    torus("cushion", 0.42, 0.1, (1.0 * s, 0.05, 0.0), (0, math.pi / 2, 0), CUSHION, HEAD, "char")
MIC = sphere("mic", 0.07, (-1.33, -0.18, 0.18), MICGLOW, parent=HEAD, group="char")
INNER_MIC = sphere("inner_mic", 0.06, (-1.06, -0.22, -0.16), INMIC, parent=HEAD, group="inside")
sphere("body", 1.0, (0, 0.2, -2.0), SHIRT, (1.35, 0.8, 0.8), ROOT, "char")
cyl("neck", 0.32, 0.9, (0, 0.1, -1.15), (0, 0, 0), SKIN, ROOT, "char")
RINGS = [torus(f"ring{i}", 0.12, 0.014, (-1.36, -0.18, 0.18), (0, math.pi / 2, 0), RING, HEAD, "rings") for i in range(3)]

def face(squint=0.0, brow=0.0, smile=0.0, look=(0.0, 0.0), open_=0.0):
    for e, p, b, s in zip(EYES, PUPILS, BROWS, (-1, 1)):
        e.scale = (1, 1, 1 - 0.6 * squint); p.scale = (1, 1, 1 - 0.6 * squint)
        p.location = (0.33 * s + look[0], -1.03, 0.22 + look[1] * (1 - squint))
        b.location = (0.33 * s, -0.86, 0.52 - 0.08 * brow)
        b.rotation_euler = (0, 0.35 * brow * s, 0)             # brows tilt in when annoyed
    set_mouth(smile, open_)

# ---------------- jet engine (plane scene) ----------------
ENG = empty((-4.3, 1.4, 1.5), group="engine")
cyl("nacelle", 1.0, 2.6, (0, 0, 0), (0, math.pi / 2, 0), METAL, ENG, "engine", 0.05)
torus("lip", 1.0, 0.13, (1.3, 0, 0), (0, math.pi / 2, 0), METAL, ENG, "engine")
cyl("fandisk", 0.9, 0.05, (1.05, 0, 0), (0, math.pi / 2, 0), DARK, ENG, "engine")
FAN = empty((1.12, 0, 0), ENG, "engine")
for i in range(12):
    a = 2 * math.pi * i / 12
    box("blade", (0.04, 0.16, 0.8), (0, 0.45 * math.cos(a), 0.45 * math.sin(a)), FANM, FAN, "engine", 0.01, rot=(a, 0.35, 0))
sphere("spinner", 0.22, (0.08, 0, 0), METAL, (1.4, 1, 1), FAN, "engine")
box("pylon", (1.2, 0.3, 1.0), (0, 0, 1.2), METAL, ENG, "engine")
box("wing", (3.0, 9.0, 0.22), (-0.3, 3.0, 1.75), METAL, ENG, "engine", 0.08, rot=(0, 0, -0.25))

# ---------------- air molecules (air scene) ----------------
MOLS = []
for j in range(7):
    for i in range(15):
        bx, bz = -3.36 + i * 0.48, -0.9 + j * 0.42 + (0.21 if i % 2 else 0)
        o = sphere("mol", 0.11, (bx, -0.3, bz), AIRM, group="air", seg=16)
        MOLS.append((o, bx, bz))

# ---------------- chip (chip scene) ----------------
CHIP = empty((0, 0, 0.6), group="chip")
box("chipbody", (1.5, 0.3, 1.5), (0, 0, 0), CHIPM, CHIP, "chip", 0.05)
box("chiplabel", (0.9, 0.05, 0.12), (0, -0.16, 0.25), CHIPLED, CHIP, "chip", 0.01)
box("chipdot", (0.12, 0.05, 0.12), (-0.5, -0.16, -0.5), CHIPLED, CHIP, "chip", 0.01)
for s in (-1, 1):
    for k in range(6):
        z = -0.6 + k * 0.24
        box("pin", (0.28, 0.08, 0.08), (s * 0.85, 0, z), GOLD, CHIP, "chip", 0.01)
        box("pin", (0.08, 0.08, 0.28), (z, 0, s * 0.85), GOLD, CHIP, "chip", 0.01)

# ---------------- dog (limits scene, original design) ----------------
DOG = empty((-2.1, -0.7, -1.55), group="dog")
sphere("dbody", 0.7, (0, 0, 0), FUR, (1.35, 0.8, 0.8), DOG, "dog")
DHEAD = empty((0.85, 0, 0.55), DOG, "dog")
sphere("dhead", 0.5, (0, 0, 0), FUR, parent=DHEAD, group="dog")
sphere("dsnout", 0.26, (0.42, 0, -0.1), FUR2, (1.3, 1, 0.8), DHEAD, "dog")
sphere("dnose", 0.08, (0.74, 0, -0.03), DARK, parent=DHEAD, group="dog")
for s in (-1, 1):
    sphere("deye", 0.07, (0.3, 0.26 * s, 0.15), DARK, parent=DHEAD, group="dog")
    sphere("dear", 0.2, (-0.05, 0.36 * s, 0.32), FUR2, (0.6, 0.4, 1.3), DHEAD, "dog")
    for fx in (-0.55, 0.55):
        cyl("dleg", 0.13, 0.6, (fx, 0.3 * s, -0.55), (0, 0, 0), FUR, DOG, "dog")
sphere("dtail", 0.12, (-0.95, 0, 0.35), FUR, (1.8, 0.7, 0.7), DOG, "dog")

# ---------------- sound waves ----------------
N = 140
WAVES = [tube(f"wave{i}", N, NOISE, 0.045, group="waves") for i in range(5)]
def wave(i, p0, p1, amp, k, phase, m=NOISE, up=(0, 0, 1), jag=0.0, grow=1.0, taper=0.6, depth=0.045,
         loc=(0, 0, 0), rot=(0, 0, 0), sign=1, fade_end=None):
    """Draw wave number i from p0 to p1. grow < 1 = only the front part has arrived yet."""
    o = WAVES[i]; o.hide_render = grow <= 0.001
    o.data.materials[0] = m; o.data.bevel_depth = depth; o.location = loc; o.rotation_euler = rot
    L = math.dist(p0, p1); g = max(grow, 0.001)
    for n, p in enumerate(o.data.splines[0].points):
        u = g * n / (N - 1); s = u * L
        ph = k * s - phase
        d = math.sin(ph) + jag * (0.55 * math.sin(2.7 * ph + 1) + 0.35 * math.sin(5.3 * ph + 2))
        a = amp * clamp(s / taper) * clamp((g * L - s) / taper if grow < 1 else 1)
        if fade_end is not None:
            a *= clamp((fade_end - u) / 0.25); u = min(u, fade_end)
        pos = lerp(p0, p1, u)
        p.co = (pos[0] + up[0] * a * d * sign, pos[1] + up[1] * a * d * sign, pos[2] + up[2] * a * d * sign, 1)

# ---------------- set, lights, camera ----------------
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 8, 0), rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(BACK)
bpy.ops.object.light_add(type='AREA', location=(-4, -5, 5)); kl = bpy.context.object; kl.data.energy = 1500; kl.data.size = 5
kl.rotation_euler = (math.radians(50), 0, math.radians(-38))
bpy.ops.object.light_add(type='AREA', location=(5, -2, 2)); fl = bpy.context.object; fl.data.energy = 700; fl.data.size = 4
fl.rotation_euler = (math.radians(70), 0, math.radians(65))
bpy.ops.object.light_add(type='AREA', location=(0, 3, 4)); rl = bpy.context.object; rl.data.energy = 900; rl.data.size = 3
rl.rotation_euler = (math.radians(-40), 0, 0)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.55, 0.75, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.5
AIM = empty()
bpy.ops.object.camera_add(location=(0, -7, 0.3)); CAM = bpy.context.object; sc.camera = CAM
tc = CAM.constraints.new('TRACK_TO'); tc.target = AIM; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'

def camera(pos, aim, lens, shake=0.0, t=0.0, roll=0.0):
    if shake:
        pos = add(pos, (shake * math.sin(t * 37), 0, shake * math.sin(t * 29 + 1)))
    CAM.location = pos; AIM.location = aim; CAM.data.lens = lens
    CAM.rotation_euler = (0, 0, 0)
    CAM.constraints[0].influence = 1.0

def reset():
    """Every scene starts from the same neutral state, then shows what it needs."""
    for g in ("char", "engine", "air", "chip", "dog", "waves", "rings", "inside"): show(g, False)
    ROOT.location = (0, 0, 0); ROOT.rotation_euler = (0, 0, 0); HEAD.rotation_euler = (0, 0, 0)
    glow(MICGLOW, 0); glow(INMIC, 0); alpha(CUP_L, 1.0); MIC.scale = (1, 1, 1)
    for o in WAVES: o.hide_render = True
def bob(t, amt=1.0):
    HEAD.rotation_euler = (0.04 * amt * math.sin(t * 2.1), 0, 0.05 * amt * math.sin(t * 1.3))

# ---------------- scenes ----------------
def hook(t, d):
    reset(); show("char")
    k = snap(t / d)
    camera(lerp((0, -9.5, 1.2), (-0.6, -4.6, 0.3), k), (-0.15, 0, -0.2), 26, shake=0.03 * (1 - prog(t, 1.6, 2.2)), t=t)
    quiet = ease(prog(t, 1.7, 2.3))                            # headphones switch on halfway through
    for i, (sgn, ph) in enumerate([(-1, 0), (1, 0), (-1, 1.7), (1, 2.2)]):
        z = 0.25 if i < 2 else -0.15
        wave(i, (sgn * 5.0, -0.05, z), (sgn * 1.38, -0.05, z), 0.3 * (1 - quiet) + 0.001, 5, t * 13 + ph, jag=0.5,
             grow=snap(t / 0.6), depth=0.045)
    glow(MICGLOW, 4 * quiet)
    face(squint=0.75 * (1 - quiet), brow=1.0 - 1.3 * quiet, smile=-0.7 + 1.6 * quiet, open_=0.4 * (1 - quiet))
    HEAD.rotation_euler = (0, 0, 0.07 * math.sin(t * 24) * (1 - quiet))

def plane(t, d):
    reset(); show("char"); show("engine")
    FAN.rotation_euler = (t * 25, 0, 0)
    cut = t > d * 0.5                                           # two shots: wide, then close-up
    if not cut:
        k = ease(t / (d * 0.5))
        camera(lerp((3.2, -9.0, -0.4), (2.4, -8.0, 0.0), k), (-1.6, 0.3, 0.4), 24)
    else:
        k = ease(prog(t, d * 0.5, d))
        camera(lerp((-0.4, -4.4, 0.4), (-0.9, -3.6, 0.3), k), (-0.5, 0, 0.0), 30, shake=0.025, t=t)
    for i, dz in enumerate((0.35, 0.0, -0.35)):
        wave(i, (-3.0, 1.3, 1.5 + dz), (-1.36, 0.0, 0.1 + dz * 0.4), 0.22, 7, t * 16 + i * 1.3, jag=0.7,
             grow=snap(t / 0.7), depth=0.04)
    face(squint=0.7, brow=1.0, smile=-0.8, look=(-0.06, 0), open_=0.3 + 0.2 * math.sin(t * 9))
    HEAD.rotation_euler = (0, 0, 0.04 * math.sin(t * 21))

def air(t, d):
    reset(); show("air")
    k = ease(t / d)
    camera(lerp((-1.2, -8.2, 1.6), (1.2, -7.4, 0.6), k), lerp((-0.5, 0, 0.4), (0.5, 0, 0.0), k), 30)
    kk, wv, A = 1.6, 6.0, 0.17 * ease(t / 0.6)
    for o, bx, bz in MOLS:                                     # molecules bunch up and spread out
        ph = kk * bx - wv * t
        o.location = (bx + A * math.cos(ph), -0.3, bz)
        sq = math.sin(ph)                                      # +1 = squeezed (high pressure)
        o.scale = [1 + 0.35 * sq * ease(t / 0.6)] * 3
    wave(0, (-3.6, -0.3, -2.0), (3.6, -0.3, -2.0), 0.45 * ease(t / 0.6), kk, wv * t - math.pi / 2,
         m=VOICEW, depth=0.05, taper=0.3)

def mic(t, d):
    reset(); show("char"); show("rings")
    a = 0.25 + 0.65 * ease(t / d)                               # orbit around the left earcup
    c = (-1.2, -0.1, 0.12)
    camera(add(c, (-2.6 * math.cos(a), -2.6 * math.sin(a), 0.4)), c, 34)
    reach = snap(t / 1.2)
    wave(0, (-6.0, -0.18, 0.18), (-1.42, -0.18, 0.18), 0.12, 9, t * 12, jag=0.5, grow=reach, depth=0.025, taper=0.3)
    on = prog(t, 0.9, 1.3)
    glow(MICGLOW, on * (4 + 2 * math.sin(t * 14))); MIC.scale = [1 + 0.4 * on] * 3
    for i, r in enumerate(RINGS):                               # "recording" pulses
        ph = (t * 0.9 + i / 3) % 1
        r.hide_render = on < 1 or ph > 0.92
        r.scale = [1 + 2.2 * ph] * 3
    face(squint=0.3, brow=0.6, smile=-0.3, look=(-0.08, 0))

def chip(t, d):
    reset(); show("chip")
    k = ease(t / d)
    camera(lerp((-2.4, -7.0, 1.0), (2.2, -6.6, 0.8), k), lerp((-1.6, 0, 0.6), (1.6, 0, 0.6), k), 36)
    CHIP.scale = [1 + 0.06 * math.sin(t * 10) * prog(t, 0.8, 1.2)] * 3
    glow(CHIPLED, 1 + 4 * prog(t, 0.8, 1.2) * (0.6 + 0.4 * math.sin(t * 12)))
    wave(0, (-6.5, -0.05, 0.6), (-0.85, -0.05, 0.6), 0.4, 3, t * 6, grow=snap(t / 0.9), depth=0.05)
    out = snap(prog(t, 0.9, 1.7))
    wave(1, (0.85, -0.05, 0), (6.5, -0.05, 0), 0.4, 3, t * 6, grow=out, depth=0.05, loc=(0, 0, 1.25))
    turn = ease(prog(t, 1.9, 3.2))                              # the copy rotates 180 degrees = upside down
    wave(2, (0.85, -0.05, 0), (6.5, -0.05, 0), 0.4, 3, t * 6, m=ANTI, grow=out, depth=0.05,
         loc=(0, 0, -0.05), rot=(math.pi * turn, 0, 0))

def cancel(t, d):
    reset(); show("char")
    k = ease(t / d)
    camera(lerp((0, -8.6, 2.6), (0, -6.0, 0.6), k), lerp((0, 0, 2.2), (0, 0, 0.5), k), 28)
    merge = ease(prog(t, 0.2, 1.4))
    gone = ease(prog(t, 1.6, 2.6))
    zc, amp = 2.4, 0.5 * (1 - gone)
    wave(0, (-3.8, 0, 0), (3.8, 0, 0), amp + 0.0005, 2.4, t * 4, m=CALM if gone > 0.6 else NOISE, depth=0.05 + 0.03 * gone,
         loc=(0, 0, 3.1 + (zc - 3.1) * merge), taper=0.3)
    wave(1, (-3.8, 0, 0), (3.8, 0, 0), amp + 0.0005, 2.4, t * 4, m=ANTI, sign=-1, depth=0.05,
         loc=(0, -0.03, 1.7 + (zc - 1.7) * merge), taper=0.3)
    WAVES[1].hide_render = gone > 0.9
    glow(CALM, 0.8 + 6 * math.exp(-max(0, t - 2.5) * 3) * (gone > 0.6))   # flash when it goes flat
    relax = ease(prog(t, 1.8, 3.2))
    face(squint=0.4 * (1 - relax) + 0.3 * relax, brow=0.6 * (1 - relax) - 0.2 * relax, smile=-0.3 + 1.3 * relax)
    bob(t, 0.6)

def inside(t, d):
    reset(); show("char"); show("inside")
    alpha(CUP_L, 0.18)                                          # see-through earcup = cutaway
    k = ease(t / d)
    c = (-1.12, -0.12, -0.05)
    camera(lerp((-2.9, -2.4, 0.7), (-2.4, -1.5, 0.4), k), c, 36)
    left = 1 - ease(prog(t, 1.6, 2.7))
    wave(0, (-1.31, -0.22, -0.16), (-1.0, -0.22, -0.16), 0.03 * left + 0.0005, 45, t * 20, m=NOISE, jag=0.8,
         depth=0.012, taper=0.05)
    glow(INMIC, 2 + 3 * math.sin(t * 12) ** 2)
    face(squint=0.25, brow=-0.1, smile=0.6, look=(-0.08, 0))

def limits(t, d):
    reset(); show("char"); show("dog")
    ROOT.location = (1.5, 0.2, 0.15)
    camera((0.1, -9.0, -0.2), (-0.2, 0, -0.4), 26, shake=0.04 * sum(math.exp(-max(0, t - b - 0.35) * 8) * (t > b + 0.35) for b in (0.9, 2.6)), t=t)
    hit = 0.0
    for i, b in enumerate((0.9, 2.6)):                          # two barks
        u = prog(t, b, b + 0.35)
        DHEAD.rotation_euler = (0, -0.35 * math.sin(math.pi * prog(t, b - 0.1, b + 0.3)), 0) if b - 0.1 < t < b + 0.3 else DHEAD.rotation_euler
        if t > b:
            mouth = (DOG.location[0] + 0.85 + 0.75, DOG.location[1], DOG.location[2] + 0.5)
            ear = (1.5 - 1.38, 0.0, 0.2)
            wave(i * 2, mouth, ear, 0.18, 14, t * 30, jag=1.4, grow=u, depth=0.035, taper=0.15, fade_end=1.0)
            late = prog(t, b + 0.35, b + 0.9) * 0.45            # anti-noise starts late and never catches up
            wave(i * 2 + 1, ear, mouth, 0.18, 14, t * 30, m=ANTI, grow=late, depth=0.03, taper=0.1, sign=-1)
            hit = max(hit, math.exp(-max(0, t - b - 0.35) * 5) * (t > b + 0.35))
    DOG.location = (-2.1, -0.7, -1.55 + 0.06 * abs(math.sin(t * 6)))
    face(squint=0.8 * hit + 0.1, brow=1.0 * hit, smile=-0.8 * hit + 0.3 * (1 - hit), open_=0.5 * hit, look=(-0.1, -0.03))
    HEAD.rotation_euler = (0, 0, 0.12 * hit)

def outro(t, d):
    reset(); show("char")
    a = -0.45 + 0.6 * ease(t / d)
    camera((math.sin(a) * 6.2, -math.cos(a) * 6.2, 0.5), (0, 0, -0.4), 26)
    beat = 112 / 60
    HEAD.rotation_euler = (0.08 * abs(math.sin(math.pi * t * beat)), 0, 0.06 * math.sin(math.pi * t * beat / 2))
    face(squint=0.88, brow=-0.3, smile=1.1)
    wave(0, (-5.0, -0.05, 0.3), (-1.38, -0.05, 0.3), 0.22, 7, t * 14, jag=0.6, grow=0.999, fade_end=0.5)   # engine: fades out
    wave(1, (-5.0, -0.05, -0.15), (-1.38, -0.05, -0.15), 0.16, 9, t * 10, m=VOICEW, jag=0.3, grow=snap(prog(t, 0.6, 1.8)))

SCENES = {f.__name__: f for f in [hook, plane, air, mic, chip, cancel, inside, limits, outro]}

def render_frame(scene, t, path):
    SCENES[scene["visual"]](t, TIMINGS[scene["id"]]["duration"])
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    mode = sys.argv[2]
    by_id = {s["id"]: s for s in SCRIPT["scenes"]}
    if mode == "preview":
        os.makedirs(OUT, exist_ok=True)
        for spec in sys.argv[3:]:
            sid, t = spec.split(":")
            t0 = time.time(); render_frame(by_id[sid], float(t), f"{OUT}/preview_{sid}.png")
            print("preview", sid, round(time.time() - t0, 1), "s", flush=True)
    else:
        only = sys.argv[3:] or list(by_id)
        for sid in only:
            s, d = by_id[sid], TIMINGS[sid]["duration"]
            folder = f"{OUT}/{sid}"; os.makedirs(folder, exist_ok=True)
            n = round(d * FPS3D)
            for i in range(n):
                p = f"{folder}/f{i:04d}.png"
                if os.path.exists(p): continue                 # resume after an interruption
                render_frame(s, i / FPS3D, p + ".tmp.png"); os.replace(p + ".tmp.png", p)
            print("scene done", sid, n, "frames", flush=True)
