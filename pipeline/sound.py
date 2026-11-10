# SOUND DESIGNER: makes original background music + sound effects in code (no copyright issues),
# then mixes them under the narration. Music automatically ducks (gets quieter) while the voice talks.
import numpy as np, soundfile as sf

SR = 24000
rng = np.random.default_rng(7)

def env(n, attack=0.005, release=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / release)

def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)): acc = (1 - a) * x[i] + a * acc; y[i] = acc
    return y

def note_hz(n): return 440 * 2 ** ((n - 69) / 12)

# ---------- music: upbeat, curious, 112 BPM ----------
def music(seconds, bpm=112):
    beat = 60 / bpm; n = int(seconds * SR); out = np.zeros(n + SR)
    def put(sig, t):
        i = int(t * SR)
        if i < 0 or i >= len(out): return      # sound would start outside the track: skip it
        j = min(len(out), i + len(sig)); out[i:j] += sig[:j - i]
    kick_t = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-kick_t * 30)) * kick_t) * np.exp(-kick_t * 12)
    clap = lowpass(rng.standard_normal(int(0.15 * SR)), 3000) * env(int(0.15 * SR), 0.001, 0.05) * 0.6
    hat = (rng.standard_normal(int(0.05 * SR)) - lowpass(rng.standard_normal(int(0.05 * SR)), 6000)) * env(int(0.05 * SR), 0.001, 0.012) * 0.25
    chords = [(57, [69, 72, 76]), (53, [69, 72, 77]), (48, [67, 72, 76]), (55, [67, 71, 74])]   # Am F C G
    bars = int(seconds / (4 * beat)) + 1
    for b in range(bars):
        root, tones = chords[b % 4]; t0 = b * 4 * beat
        for k in range(4):
            put(kick * 0.9, t0 + k * beat)
            if k % 2: put(clap, t0 + k * beat)
        for k in range(8): put(hat, t0 + k * beat / 2 + beat / 4)
        bl = int(beat * 0.9 * SR); bt = np.arange(bl) / SR
        for k in (0, 1.5, 2, 3):                                     # bouncy bass
            put(np.tanh(2 * np.sin(2 * np.pi * note_hz(root - 12) * bt)) * env(bl, 0.005, 0.25) * 0.35, t0 + k * beat)
        pl = int(beat / 2 * SR); pt = np.arange(pl) / SR
        for k in range(8):                                           # plucky arpeggio
            f = note_hz(tones[[0, 1, 2, 1][k % 4]] + (12 if k >= 4 else 0))
            sig = (np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt)) * env(pl, 0.002, 0.09) * 0.16
            put(sig, t0 + k * beat / 2)
    return out[:n]

# ---------- sound effects ----------
def whoosh(d=0.45):
    n = int(d * SR); x = rng.standard_normal(n)
    shape = np.sin(np.linspace(0, np.pi, n)) ** 2
    lo, hi = lowpass(x, 600), lowpass(x, 5000)
    k = np.linspace(0, 1, n)
    return (lo * (1 - k) + hi * k) * shape * 0.5

def pop():
    n = int(0.09 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * (900 - 500 * t / 0.09) * t) * env(n, 0.001, 0.03) * 0.35

def impact():
    n = int(0.6 * SR); t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (40 + 60 * np.exp(-t * 18)) * t) * np.exp(-t * 6)
    return (boom + lowpass(rng.standard_normal(n), 1500) * np.exp(-t * 20) * 0.6) * 0.8

def ding():
    n = int(0.9 * SR); t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * t) * a for f, a in [(1318, 0.5), (1975, 0.3), (2637, 0.15)]) * np.exp(-t * 4) * 0.35

def mix(voice_path, out_path, events, length):
    """events: list of (time_s, name). Voice on top, music ducked under it, effects on cuts."""
    voice, sr = sf.read(voice_path)
    if voice.ndim > 1: voice = voice.mean(1)
    assert sr == SR, sr
    n = int(length * SR)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    m = music(length)
    # ducking: follow the voice loudness, push music down while it talks
    win = int(0.15 * SR)
    loud = np.sqrt(np.convolve(voice ** 2, np.ones(win) / win, mode="same"))
    duck = 1 - 0.55 * np.clip(loud / 0.05, 0, 1)
    fx = np.zeros(n); lib = {"whoosh": whoosh(), "pop": pop(), "impact": impact(), "ding": ding()}
    for t, name in events:
        s = lib[name]; i = int(t * SR); j = min(n, i + len(s))
        if i < n: fx[i:j] += s[:j - i]
    fade = np.minimum(1, (n - np.arange(n)) / (1.0 * SR))             # music fades out in the last second
    out = voice * 1.0 + m * 0.22 * duck * fade + fx * 0.7
    out /= max(1.0, np.abs(out).max() / 0.97)
    sf.write(out_path, out, SR)
