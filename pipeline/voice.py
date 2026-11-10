# VOICE AGENT: reads script.json, makes one voice clip per scene, saves timings.
import json, sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

script = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "script.json"))
k = Kokoro("models/kokoro.onnx", "models/voices.bin")
PAD = 0.35  # seconds of breathing room after each line

clips, timings, t = [], [], 0.0
for s in script["scenes"]:
    audio, sr = k.create(s["text"], voice=script["voice"], speed=script["speed"], lang="en-us")
    speech = len(audio) / sr
    audio = np.concatenate([audio, np.zeros(int(PAD * sr), dtype=audio.dtype)])
    clips.append(audio)
    timings.append({"id": s["id"], "start": t, "speech": speech, "duration": len(audio) / sr})
    t += len(audio) / sr

sf.write("out/narration.wav", np.concatenate(clips), sr)
json.dump(timings, open("out/timings.json", "w"), indent=1)
print(f"total {t:.1f}s", [(x["id"], round(x["duration"], 2)) for x in timings])
