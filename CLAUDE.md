# xplain.motion — project instructions for Claude

Animated educational YouTube Shorts channel (also TikTok / Instagram Reels), produced by Claude Code.
The owner is learning to code through this project: explain what you do in plain words, one concept at a time.

## Channel decisions
- Name / handle: **xplain.motion** (display name "Xplain Motion")
- Niche: one umbrella, "how things work", aimed at teens/adults (not kids)
  - ~70% How it works: everyday tech, the human body, machines, science. Lean toward tech topics (better pay, bridges to AI later)
  - ~30% What if: science-based what-ifs, still explained (fact-checked)
  - Not now: interactive stories (entertainment, kid-skewing, lowest pay). AI explainers come later as part of "how it works"
  - Vary the format inside the style (different openings, camera moves, pacing) so uploads are not one repeated template
- Format: ~30 s vertical (1080x1920), question in the first second, end right after the answer
- Style target: 3D animation in the Zack D. Films style (soft lighting, rounded clay-like characters, close-ups). One consistent style, voice and caption look across the channel.
- Narrator: Kokoro voice `am_liam`, speed 1.1. Never clone a real person's voice.
- Captions: big bold uppercase, 1-3 words at a time, active word highlighted in amber (#FFB547) with black outline

## Pipeline (run from `pipeline/`)
1. `bash ../setup.sh` once per fresh workspace (installs tools, downloads the voice model)
2. Writer: create `script.json` (title, voice, speed, scenes with id / visual / text)
3. Voice: `python3 voice.py [script.json]` -> out/narration.wav + out/timings.json
4. 3D previews: `python3 render3d.py scripts/X.json preview hook:2.0 cancel:1.2` -> out/3d/preview_*.png; look before rendering
5. 3D render (run in background, ~1 h): `python3 render3d.py scripts/X.json all` -> out/3d/<scene>/f0000.png ... (resumes if stopped)
6. Compose: `python3 compose.py scripts/X.json` -> out/X.mp4 (captions, logo, voice)

Scripts live in `pipeline/scripts/`. `render3d.py` holds the 3D set (character, headphones, waves) and one function per scene visual;
new topics add new scene functions/props. `captions.py` is the shared caption + logo style. `render.py` is the old 2D renderer.
3D speed in the cloud workspace (2 CPU cores): Cycles ~12 s/frame at 540x960 with 10 samples + denoise
-> render 3D at half size, 15 fps, upscale to 1080x1920. A 30 s Short is ~1.5 h, so 3D renders run as overnight scheduled tasks.

## Network notes
- Package installs and GitHub downloads work. YouTube, TikTok and Microsoft TTS are blocked from the workspace.
- Do not commit `pipeline/models/` or `pipeline/out/` (large / generated).
