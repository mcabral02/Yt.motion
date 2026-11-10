# VOICE AGENT: reads a script, records each scene's line, saves timings.
# Script options: "voice" (name, or "a+b" to mix two voices 50/50), "speed", "pitch" (semitones, + = younger/brighter).
# Keyword marks (*word*, ~word~, ^word^) are for captions only and are removed before speaking.
import json, re, subprocess, sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

PAD = 0.2  # seconds of breathing room after each line (short = punchier pace)

def clean(text): return re.sub(r"[*~^]", "", text)

def load_voice(k, name):
    if "+" in name:
        a, b = name.split("+")
        return 0.5 * k.get_voice_style(a) + 0.5 * k.get_voice_style(b)
    return name

def finish(wav_in, wav_out, pitch):
    """Pitch shift (keeps the speed) + compression so the voice sounds punchy and loud."""
    chain = []
    if pitch: chain.append(f"rubberband=pitch={2 ** (pitch / 12):.4f}:formant=preserved")
    chain += ["acompressor=threshold=-18dB:ratio=3:attack=5:release=60:makeup=4", "alimiter=limit=0.95"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_in, "-af", ",".join(chain), wav_out], check=True)

if __name__ == "__main__":
    script = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "script.json"))
    k = Kokoro("models/kokoro.onnx", "models/voices.bin")
    voice = load_voice(k, script["voice"])
    clips, timings, t = [], [], 0.0
    for s in script["scenes"]:
        audio, sr = k.create(clean(s["text"]), voice=voice, speed=s.get("speed", script["speed"]), lang="en-us")
        if s.get("pitch"):                        # per-scene tone: higher = excited, lower = serious
            sf.write("out/_clip.wav", audio, sr)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "out/_clip.wav", "-af",
                            f"rubberband=pitch={2 ** (s['pitch'] / 12):.4f}:formant=preserved", "out/_clip2.wav"], check=True)
            audio, sr = sf.read("out/_clip2.wav", dtype="float32")
        speech = len(audio) / sr
        audio = np.concatenate([audio, np.zeros(int(PAD * sr), dtype=audio.dtype)])
        clips.append(audio)
        timings.append({"id": s["id"], "start": t, "speech": speech, "duration": len(audio) / sr})
        t += len(audio) / sr
    sf.write("out/narration_raw.wav", np.concatenate(clips), sr)
    finish("out/narration_raw.wav", "out/narration.wav", script.get("pitch", 0))
    json.dump(timings, open("out/timings.json", "w"), indent=1)
    print(f"total {t:.1f}s", [(x["id"], round(x["duration"], 2)) for x in timings])
