# 3D ANIMATOR: builds the clay-style set in Blender and renders each scene as frames.
# Usage: python3 render3d.py <script.json> all            -> every frame of every scene
#        python3 render3d.py <script.json> preview <id>:<t> [...] -> single stills (t in seconds)
import bpy, json, math, os, sys, time

SCRIPT = json.load(open(sys.argv[1]))
TIMINGS = {t["id"]: t for t in json.load(open("out/timings.json"))}
FPS3D = 15                      # 3D frames per second (upscaled + doubled to 30 fps later)
RES = (540, 960)                # half of 1080x1920; compose.py upscales
OUT = os.path.abspath("out/3d")

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)          # smooth in and out
def prog(t, a, b): return clamp((t - a) / (b - a))
def lerp(a, b, k): return tuple(x + (y - x) * k for x, y in zip(a, b))

# ---------------- set building ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = 10; sc.cycles.use_adaptive_sampling = True; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4; sc.render.use_persistent_data = True
sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -1.0

def mat(name, rgb, rough=0.5, sss=0.0, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = emit
    return m

def sphere(name, r, loc, m, scale=(1, 1, 1), parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
    o = bpy.context.object; o.name = name; o.scale = scale; bpy.ops.object.shade_smooth()
    o.data.materials.append(m); o.parent = parent; return o

SKIN = mat("skin", (0.85, 0.56, 0.42), 0.45, 0.25)
WHITE = mat("eyewhite", (0.95, 0.95, 0.95), 0.15)
DARK = mat("dark", (0.02, 0.02, 0.03), 0.2)
PHONES = mat("phones", (0.10, 0.12, 0.18), 0.35)
CUSHION = mat("cushion", (0.20, 0.22, 0.28), 0.8)
NOISE = mat("noise", (1.0, 0.30, 0.15), 0.4, emit=0.5)
ANTI = mat("anti", (0.10, 0.70, 0.95), 0.4, emit=0.5)
CALM = mat("calm", (0.95, 0.95, 0.95), 0.4, emit=0.8)
MICGLOW = mat("mic", (1.0, 0.71, 0.28), 0.3, emit=0.0)
BACK = mat("backdrop", (0.30, 0.42, 0.62), 0.9)

# character: everything parented to an empty so the head can bob
bpy.ops.object.empty_add(location=(0, 0, 0)); HEAD = bpy.context.object
sphere("head", 1.0, (0, 0, 0), SKIN, (1, 1, 1.08), HEAD)
EYES, PUPILS, BROWS = [], [], []
for s in (-1, 1):
    EYES.append(sphere("eye", 0.2, (0.33 * s, -0.86, 0.22), WHITE, parent=HEAD))
    PUPILS.append(sphere("pupil", 0.095, (0.33 * s, -1.03, 0.22), DARK, parent=HEAD))
    BROWS.append(sphere("brow", 0.13, (0.33 * s, -0.86, 0.52), DARK, (1.3, 0.5, 0.3), HEAD))
sphere("nose", 0.13, (0, -1.05, 0.0), SKIN, (1, 1, 1.1), HEAD)

def tube(name, n, m, depth=0.035, parent=None):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = depth; cu.bevel_resolution = 4; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(n - 1)
    o = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(o)
    o.data.materials.append(m); o.parent = parent; return o

MOUTH = tube("mouth", 15, DARK, 0.04, HEAD)
def set_mouth(curve):                      # curve > 0 smile, < 0 frown
    for i, p in enumerate(MOUTH.data.splines[0].points):
        x = -0.28 + 0.56 * i / 14
        z = -0.38 + curve * (x * x - 0.078) * 2.2
        y = -math.sqrt(max(0.0, 1 - x * x - (z / 1.08) ** 2)) - 0.03
        p.co = (x, y, z, 1)

# headphones: band (arc) + two cups with cushions + a mic dot on the left cup
BAND = tube("band", 40, PHONES, 0.09, HEAD)
for i, p in enumerate(BAND.data.splines[0].points):
    a = math.pi * i / 39
    p.co = (1.12 * math.cos(a), 0.05, 1.18 * math.sin(a) + 0.05, 1)
for s in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.48, depth=0.32, location=(1.16 * s, 0.05, 0.0), rotation=(0, math.pi / 2, 0), vertices=48)
    cup = bpy.context.object; bpy.ops.object.shade_smooth(); cup.data.materials.append(PHONES); cup.parent = HEAD
    bm = cup.modifiers.new("bevel", 'BEVEL'); bm.width = 0.08; bm.segments = 4
    bpy.ops.mesh.primitive_torus_add(major_radius=0.42, minor_radius=0.1, location=(1.0 * s, 0.05, 0.0), rotation=(0, math.pi / 2, 0))
    t = bpy.context.object; bpy.ops.object.shade_smooth(); t.data.materials.append(CUSHION); t.parent = HEAD
MIC = sphere("mic", 0.07, (-1.33, -0.18, 0.18), MICGLOW, parent=HEAD)

# body hint (shoulders) so it reads as a person
sphere("body", 1.0, (0, 0.2, -2.0), mat("shirt", (0.95, 0.55, 0.18), 0.7), (1.35, 0.8, 0.8))
bpy.ops.mesh.primitive_cylinder_add(radius=0.32, depth=0.9, location=(0, 0.1, -1.15), vertices=32)
bpy.context.object.data.materials.append(SKIN); bpy.ops.object.shade_smooth()

# sound waves
N = 120
WAVE_NOISE = tube("wave_noise", N, NOISE, 0.045)
WAVE_ANTI = tube("wave_anti", N, ANTI, 0.045)
WAVE_NOISE_R = tube("wave_noise_r", N, NOISE, 0.045)
def set_wave(o, x0, x1, z, amp, k, phase, y=0.0, sign=1, show=True, taper_end=None):
    o.hide_render = not show
    for i, p in enumerate(o.data.splines[0].points):
        x = x0 + (x1 - x0) * i / (N - 1)
        a = amp
        if taper_end is not None:          # wave fades as it approaches the ear
            a *= clamp((taper_end - abs(x)) / 0.6) if abs(x) > taper_end - 0.6 else 1
        p.co = (x, y, z + sign * a * math.sin(k * x - phase), 1)

# backdrop + lights + camera
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 6, 0), rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(BACK)
bpy.ops.object.light_add(type='AREA', location=(-4, -5, 5)); k = bpy.context.object; k.data.energy = 1500; k.data.size = 5
k.rotation_euler = (math.radians(50), 0, math.radians(-38))
bpy.ops.object.light_add(type='AREA', location=(5, -2, 2)); f = bpy.context.object; f.data.energy = 700; f.data.size = 4
f.rotation_euler = (math.radians(70), 0, math.radians(65))
bpy.ops.object.light_add(type='AREA', location=(0, 3, 4)); r = bpy.context.object; r.data.energy = 900; r.data.size = 3
r.rotation_euler = (math.radians(-40), 0, 0)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.55, 0.75, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.5
bpy.ops.object.empty_add(location=(0, 0, 0)); AIM = bpy.context.object
bpy.ops.object.camera_add(location=(0, -7, 0.3)); CAM = bpy.context.object; sc.camera = CAM
tc = CAM.constraints.new('TRACK_TO'); tc.target = AIM; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'

def camera(pos, aim, lens):
    CAM.location = pos; AIM.location = aim; CAM.data.lens = lens

def face(squint=0.0, brow=0.0, smile=0.0, look=(0.0, 0.0)):
    for e, p, b, s in zip(EYES, PUPILS, BROWS, (-1, 1)):
        e.scale = (1, 1, 1 - 0.55 * squint); p.scale = (1, 1, 1 - 0.55 * squint)
        p.location = (0.33 * s + look[0], -1.03, 0.22 + look[1] * (1 - squint))
        b.location = (0.33 * s, -0.86, 0.52 - 0.08 * brow)
        b.rotation_euler = (0, 0.35 * brow * s, 0)             # brows tilt in when annoyed
    set_mouth(smile)

# ---------------- scenes: pose everything for time t (s) in a scene lasting d ----------------
def hide_waves():
    for o in (WAVE_NOISE, WAVE_ANTI, WAVE_NOISE_R): o.hide_render = True
def bob(t, amt=1.0):
    HEAD.rotation_euler = (0.04 * amt * math.sin(t * 2.1), 0, 0.05 * amt * math.sin(t * 1.3))

def hook(t, d):
    k = ease(t / d)
    camera(lerp((0, -6.2, 0.6), (0, -5.0, 0.4), k), (0, 0, -0.35), 26)
    hide_waves()
    reach = ease(t / 1.2)
    set_wave(WAVE_NOISE, -4.5, -1.35, 0.15, 0.32, 5, t * 12, show=True, taper_end=4.5)
    set_wave(WAVE_NOISE_R, 1.35, 4.5, 0.15, 0.32, 5, -t * 12, show=True, taper_end=4.5)
    for o in (WAVE_NOISE, WAVE_NOISE_R):                       # waves slide in from the edges
        o.location = ((-1 if o is WAVE_NOISE else 1) * 3.2 * (1 - reach), 0, 0)
    face(squint=0.7 * ease(t / 0.8), brow=1.0, smile=-0.6, look=(0, 0))
    HEAD.rotation_euler = (0, 0, 0.06 * math.sin(t * 25) * ease(t / 0.5))   # annoyed shake

def waves(t, d):
    k = ease(t / d)
    camera(lerp((0.6, -9.0, 1.4), (-0.4, -8.4, 1.6), k), (0, 0, 0.9), 28)
    hide_waves()
    amp = 0.55 * ease(t / 0.8)
    set_wave(WAVE_NOISE, -4.0, 4.0, 2.55, amp, 2.2, t * 5)
    WAVE_NOISE.location = (0, 0, 0)
    face(squint=0.25, brow=0.5, smile=-0.2, look=(0, 0.06))
    bob(t)

def mic(t, d):
    k = ease(t / d)
    camera(lerp((-4.6, -3.0, 0.9), (-3.6, -2.2, 0.6), k), (-1.25, -0.1, 0.1), 32)
    hide_waves()
    reach = ease(t / 1.6)
    set_wave(WAVE_NOISE, -5.5, -1.42, 0.18, 0.22, 6, t * 10, y=-0.18, taper_end=5.5)
    WAVE_NOISE.location = (-3.0 * (1 - reach), 0, 0)
    MICGLOW.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = \
        reach * (3 + 2 * math.sin(t * 14))                    # mic lights up as it "hears"
    MIC.scale = [1 + 0.35 * reach] * 3
    face(squint=0.3, brow=0.6, smile=-0.3, look=(-0.08, 0))
    HEAD.rotation_euler = (0, 0, 0)

def flip(t, d):
    k = ease(t / d)
    camera(lerp((0, -8.8, 1.3), (0, -8.2, 1.5), k), (0, 0, 1.0), 28)
    hide_waves()
    MICGLOW.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 3
    set_wave(WAVE_NOISE, -3.6, 3.6, 3.0, 0.5, 2.4, t * 4)
    WAVE_NOISE.location = (0, 0, 0)
    # the copy appears below, then rotates 180 degrees around its length = upside down
    appear, turn = ease(t / 0.6), ease(prog(t, 0.9, 2.2))
    set_wave(WAVE_ANTI, -3.6, 3.6, 0.0, 0.5 * appear, 2.4, t * 4)
    WAVE_ANTI.location = (0, 0, 1.75); WAVE_ANTI.rotation_euler = (math.pi * turn, 0, 0)
    face(squint=0.2, brow=0.2, smile=0.0, look=(0, 0.08))
    bob(t)

def cancel(t, d):
    k = ease(t / d)
    camera(lerp((0, -8.2, 1.5), (0, -6.4, 0.9), k), (0, 0, 0.7 - 0.3 * k), 28)
    hide_waves()
    merge = ease(prog(t, 0.2, 1.6))
    gone = ease(prog(t, 1.5, 3.0))
    zc = 2.35
    amp = 0.5 * (1 - gone)
    set_wave(WAVE_NOISE, -3.6, 3.6, 0.0, amp, 2.4, t * 4)
    set_wave(WAVE_ANTI, -3.6, 3.6, 0.0, amp, 2.4, t * 4, sign=-1)
    WAVE_ANTI.rotation_euler = (0, 0, 0)
    WAVE_NOISE.location = (0, 0, 3.0 + (zc - 3.0) * merge)
    WAVE_ANTI.location = (0, -0.02, 1.75 + (zc - 1.75) * merge)
    if gone > 0.95:                                          # merged into one calm flat line
        WAVE_ANTI.hide_render = True
    WAVE_NOISE.data.materials[0] = CALM if gone > 0.5 else NOISE
    relax = ease(prog(t, 1.5, 3.2))
    face(squint=0.35 * (1 - relax), brow=0.5 * (1 - relax), smile=-0.2 + 1.0 * relax, look=(0, 0.04))
    bob(t, 0.6)

def outro(t, d):
    a = -0.35 + 0.5 * ease(t / d)
    camera((math.sin(a) * 5.6, -math.cos(a) * 5.6, 0.2), (0, 0, -0.55), 26)
    hide_waves()
    WAVE_NOISE.data.materials[0] = NOISE
    blink = 1.0 if (t % 2.6) < 0.12 else 0.0
    face(squint=max(0.35, blink), brow=-0.2, smile=1.0, look=(0, 0))
    HEAD.rotation_euler = (0.05 * math.sin(t * 1.2), 0, 0.1 * math.sin(t * 0.8))

SCENES = {f.__name__: f for f in [hook, waves, mic, flip, cancel, outro]}

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
