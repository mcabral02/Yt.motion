# xplain.motion — project instructions for Claude

Animated educational YouTube Shorts channel (also TikTok / Instagram Reels), produced by Claude Code.
The owner is learning to code through this project: explain what you do in plain words, one concept at a time.

## Channel decisions
- Name / handle: **xplain.motion** (display name "Xplain Motion")
- Topics: how things work, what-ifs, interactive "you choose" stories; tech/AI later
- Format: ~30 s vertical (1080x1920), question in the first second, end right after the answer
- Style target: 3D animation in the Zack D. Films style (soft lighting, rounded clay-like characters, close-ups). One consistent style, voice and caption look across the channel.
- Narrator: Kokoro voice `am_liam`, speed 1.1. Never clone a real person's voice.
- Captions: big bold uppercase, 1-3 words at a time, active word highlighted in amber (#FFB547) with black outline

## Pipeline (run from `pipeline/`)
1. `bash ../setup.sh` once per fresh workspace (installs tools, downloads the voice model)
2. Writer: create `script.json` (title, voice, speed, scenes with id / visual / text)
3. Voice: `python3 voice.py [script.json]` -> out/narration.wav + out/timings.json
4. Preview stills: `python3 render.py preview [script.json]` -> look at them before a full render
5. Render: `python3 render.py all [script.json]` -> out/short.mp4

`render.py` is the current 2D (cairo) renderer. `test3d.py` is the Blender 3D test.
3D speed in the cloud workspace (2 CPU cores): Cycles ~12 s/frame at 540x960 with 10 samples + denoise
-> render 3D at half size, 15 fps, upscale to 1080x1920. A 30 s Short is ~1.5 h, so 3D renders run as overnight scheduled tasks.

## Network notes
- Package installs and GitHub downloads work. YouTube, TikTok and Microsoft TTS are blocked from the workspace.
- Do not commit `pipeline/models/` or `pipeline/out/` (large / generated).
