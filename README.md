<div align="center">

<img src="docs/media/reel-studio.gif" alt="Reel Studio · DropAudio CCS" width="100%" />

# Reel Studio · DropAudio CCS

**From phone footage to a finished CapCut draft, with AI running on my own machine.**

I record. The app transcribes the audio, looks at every take, decides which ones are usable,
writes the script and assembles a 1080×1920 draft in CapCut — ready to export.

**A reel that took me ~2 hours to cut by hand now takes ~15 minutes, and most of that is unattended.**

[Watch the MP4](docs/media/reel-studio-motion.mp4) · [Léeme en español](README.es.md) · [Full project history](reel-studio-capcut-2026-10.md) · [Project context docs (ES)](docs/contexto/README.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Local AI](https://img.shields.io/badge/AI-local%20via%20Ollama-000000?style=flat-square)
![Desktop](https://img.shields.io/badge/Desktop-pywebview%20%2B%20PyInstaller-4B8BBE?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-39ff88?style=flat-square)

</div>

---

## The problem

I run [DropAudio CCS](https://dropaudioccs.com), an audio e-commerce store. Every reel meant the same
two hours: scrub through everything I shot on the phone, find the takes where I don't stumble over my
words, write the script, drop it all into CapCut and line up the text. The editing was never the hard
part — **finding the usable takes was**, and no tool does that for you.

So the app watches the footage instead of me.

## How it works

| Step | What it does | With what |
|---|---|---|
| **1 · Analyze** | Transcribes the speech, describes one frame every N seconds, and scores each take (usable / hooks the viewer). Writes `analisis.json` and resumes where it left off if interrupted. | faster-whisper `small` · a vision model via Ollama |
| **2 · Write the script** | Builds the "here's how you buy" narrative: hook → 5 steps → CTA. Moves cuts that land in the middle of a sentence. | a text model via Ollama, or a rule-based fallback with no model at all |
| **3 · Build in CapCut** | 1080×1920 draft with clips, brand hook, step chips, CTA, original music and the narration as text on a dedicated `voz` track. | pyCapCut · Pillow · `gen_music.py` |

**On "local":** transcription and frame analysis run entirely on this machine through
[Ollama](https://ollama.com) — the footage never leaves it. The script step defaults to a cloud-hosted
model tag, also through Ollama; point it at a local model and the whole pipeline is offline.

## Engineering notes

The interesting parts aren't the AI calls — they're what happens when things go wrong, because a
10-minute analysis that dies at minute 9 and starts over is worse than no tool at all.

- **Resumable analysis.** Progress is written to `analisis.json` as it goes; a crash or a closed laptop
  costs the current file, not the run.
- **Frames are deduplicated before any model sees them.** Each frame is reduced to a 24×24 grayscale
  thumbnail and compared to the last one — static shots skip the vision model entirely. This is where
  most of the speed came from, not from a bigger GPU.
- **Nothing is allowed to hang.** Every model call has an explicit timeout with visible progress
  (characters generated, seconds elapsed), and the script step falls back to a rule-based writer when
  the model fails, so the run always produces a draft.
- **Models disagree about their own options.** Long "thinking" is disabled via `think: false`, and when
  a model rejects that option the call is retried without it instead of failing.
- **The UI is a local web app in a native window.** pywebview + a server bound to `127.0.0.1` only,
  packaged into a single `.exe` with PyInstaller — no browser, no port exposed, no install ritual.
- **Boring real-world glue:** HEIC → JPG conversion (CapCut and vision models don't reliably read HEIC),
  font fetching, brand overlays generated as PNGs.

## Install and run

Requirements: Windows, Python 3.10+, [Ollama](https://ollama.com) running, `ffmpeg` on PATH, and the
CapCut desktop app (closed while a draft is being created).

```powershell
git clone https://github.com/GuanYixuan/pyCapCut ..\pyCapCut
pip install -e ..\pyCapCut
pip install -r requirements.txt
```

Then double-click **`Reel_Studio.bat`** (or run `pythonw ReelStudio.pyw`).
To build a standalone executable: `Crear_exe.bat` → `dist\ReelStudio\ReelStudio.exe`.

### Narration voice inside CapCut

1. Open the draft (restart CapCut if it was open).
2. Select the text clips on the `voz` track (click the first, Shift + click the last).
3. Text to speech → pick the voice → Generate.

## Project structure

| File | Purpose |
|---|---|
| `ReelStudio.pyw` | Desktop app (pywebview, native window with WebView2) |
| `Reel_Studio.bat` | Launches the app with no console window |
| `studio_web.py` | Local server (127.0.0.1 only) between the UI and the engine |
| `studio.html` | Interface (black/gold, Space Grotesk + Plus Jakarta Sans) |
| `reel_studio.py` | Engine: analyze, script, assemble in CapCut, brand PNGs, HEIC→JPG |
| `reel_capcut.py` | Command-line version (`analizar` / `elegir` / `armar`) |
| `gen_music.py` | Royalty-free synthesized soundtrack (128 BPM) |
| `make_overlays.py`, `overlays/` | Brand text and backgrounds as PNG/JPG |
| `readme-motion/` | HyperFrames project behind the video at the top of this README |
| `reel-studio-capcut-2026-10.md` | Decisions, how the pipeline evolved, lessons and open items |

Raw footage (`Videos Dropaudioccs/`) stays out of the repository.

## Regenerating the README video

```bash
cd readme-motion
npx hyperframes check
npx hyperframes render --quality delivery --output renders/reel-studio-motion.mp4
ffmpeg -i renders/reel-studio-motion.mp4 -vf "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" ../docs/media/reel-studio.gif
```

## What the footage taught me

- In talking-head video, **the transcript rules**: without it the AI picks pretty shots and cuts
  sentences in half.
- No silent filler photos; if a photo goes in, it needs a slow zoom and a voice over it.
- What works: face to camera at the start, POV of the delivery ride, and "the customer tries it first,
  pays after".
- Always export 1080p, 30 fps.
- Privacy: from sales screenshots only the products are used — never customer names or phone numbers.

## Scope and credits

This is an internal tool I built for my own store, published as-is — not a product or a service I
offer. It builds on [pyCapCut](https://github.com/GuanYixuan/pyCapCut) to write CapCut's draft format,
which is not a public API: it may break when CapCut changes. Not affiliated with or endorsed by CapCut.

## License

MIT © Daniel Alejandro Silva Rojas — see [LICENSE](LICENSE).
Portfolio: [my-resume-landing.vercel.app](https://my-resume-landing.vercel.app/) · [LinkedIn](https://www.linkedin.com/in/daniel-alejandro-silva-rojas/)
