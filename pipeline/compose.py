# EDITOR: puts the 3D frames, captions, logo and voice together into the final Short.
# Usage: python3 compose.py <script.json>   (after voice.py and render3d.py)
import json, os, subprocess, sys, cairo
import captions as cap

FPS = 30
script = json.load(open(sys.argv[1]))
timings = {t["id"]: t for t in json.load(open("out/timings.json"))}
scenes = script["scenes"]

surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, cap.W, cap.H)
c = cairo.Context(surf)

for idx, s in enumerate(scenes):
    tm = timings[s["id"]]
    folder = f"out/3d/{s['id']}"
    frames = sorted(f for f in os.listdir(folder) if f.endswith(".png") and ".tmp" not in f)
    n = round(tm["duration"] * FPS)
    tl = cap.timeline(s["text"], tm["speech"])
    last = idx == len(scenes) - 1
    tmp, final = f"out/comp_{s['id']}.tmp.mp4", f"out/comp_{s['id']}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                          "-s", f"{cap.W}x{cap.H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                          "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    cached, img = None, None
    for j in range(n):
        t = j / FPS
        f = frames[min(int(t * 15), len(frames) - 1)]          # 15 fps 3D -> each frame shown twice
        if f != cached:
            img = cairo.ImageSurface.create_from_png(f"{folder}/{f}"); cached = f
        c.save(); c.scale(cap.W / img.get_width(), cap.H / img.get_height())
        c.set_source_surface(img, 0, 0); c.get_source().set_filter(cairo.FILTER_GOOD); c.paint(); c.restore()
        cap.draw(c, tl, t)
        if last:
            cap.logo(c, cap.ease((t - tm["duration"] * 0.45) / 0.4))
        surf.flush(); p.stdin.write(surf.get_data())
    p.stdin.close()
    if p.wait() == 0: os.replace(tmp, final)
    print("composed", s["id"], flush=True)

with open("out/comp_list.txt", "w") as f:
    for s in scenes: f.write(f"file 'comp_{s['id']}.mp4'\n")
name = os.path.splitext(os.path.basename(sys.argv[1]))[0]
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "out/comp_list.txt",
                "-i", "out/narration.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                "-b:a", "192k", "-shortest", f"out/{name}.mp4"], check=True)
print(f"done: out/{name}.mp4")
