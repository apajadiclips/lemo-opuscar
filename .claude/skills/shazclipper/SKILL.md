---
name: shazclipper
description: Cut a streamer's VOD (a Google Drive link or an uploaded video) into vertical 9:16 clips in the @shazclipper house style - facecam on top, gameplay full below, a "▶ streamer | S @shazclipper" bar, plain Indonesian subtitles from the streamer's own voice, important moments in Titan One light green, all text in the TikTok/Reels/Shorts safe zone, no back sound (voice only), enhanced picture. Use whenever the user asks for clips, "klip", "clipper", "shazclipper", highlight cuts, or sends a stream/VOD link to clip, even without naming the style.
---

# @shazclipper clips

The user runs the clipper channel **@shazclipper** (Malaysian; talks Malay, reads Indonesian). Streams so far: **Windah Basudara** (Indonesian, GTA VI), via his official clipper programme. Talk to the user in the language they write in (usually Malay).

## The style (fixed: keep every rule)

| Part | Rule |
|---|---|
| Frame | 1080×1920, 24 fps. Facecam 0–760, divider 760–836, gameplay 836–1920 full to the bottom (no blurred bands, no letterbox) |
| Divider | black bar, light-green top line; left `▶ <Streamer name>` (red ▶), right `S @shazclipper` (mint circle "S"). **The channel appears once, only here**: no bottom watermark, no second badge |
| Subtitles | **plain, ONE line**: Inter ExtraBold, white, black outline, same size, **no colour emphasis**, **Indonesian only** (the streamer's own words, from Whisper word times). A long phrase is split by time into balanced single lines (`one_line()`), never wrapped to two lines. (The old mint-word style stays available as `"subtitle_style": "moments"`.) |
| Moments | Titan One (mint, 150,255,160) is only for the **cover, hook, reaction lines and end card**, never inside subtitles. Moment words (`MOMENT_WORDS` in `scripts/shaz_style.py`, extend with `moment_words`) still get a small camera punch and a hit sound, no colour |
| Safe zone | **text only** must sit inside x 60–940, y 210–1470 (centred on x 500). Pictures may run under the app UI. Check with the `*_safe.jpg` stills |
| Sound | **no back sound**: voice only (Demucs vocals + soft gate), plus small hits on moment words and whooshes on cuts. No music |
| Picture | enhanced source frames: `hqdn3d` + CAS + light grade for 1080p VODs (fast); `nlmeans` + CAS for low-res screen recordings (slow, ~2 fps). `make_clip.py` picks by source height; override with `"enhance"` in the spec |
| Cover | **every clip opens with a ~1 s cover**: a frozen dramatic frame, the hook in big Titan One (first line white, second mint), a flash and a hit on frame 0, and a **voice saying the hook** (edge-tts, default `id-ID-ArdiNeural` at normal speed `+0%`: the user found +20% too fast). Its length follows the voice (≥ 1.0 s). It doubles as the TikTok thumbnail |
| Shape | cover → hook (3 s, his own payoff line, `TONTON SAMPAI HABIS` pill low in the safe zone) → build-up → moment → optional slow replay (`REPLAY 0.5×`, red corners) → end card `MAU LAGI?` + `FOLLOW @shazclipper` |
| Length | **61–75 s** (TikTok Creator Rewards needs > 60 s; also fine for Reels/Shorts). A 30–45 s Shorts cut is optional |
| Loudness | −14 LUFS, true peak ≤ −1.5 dB |
| Sexual content | **always blurred**: `make_clip.py` runs NudeNet (bundled model, offline) on every 1/3 s of the clip and the cover frame, and blurs the gameplay ±0.8 s around any exposed-nudity detection (`nsfw.json`). Add `"blur": [[a, b], …]` (VOD seconds) for anything it misses: kissing/sex scenes without nudity are not detected, so check suggestive scenes by eye. Never use a flagged frame as a cover. For a whole VOD, map it once: `scripts/nsfw_map.py <vod.mp4> ana/nsfw_map.json` (keyframes + NudeNet, ~27 ms/frame), and keep clips and covers away from flagged scenes |

Don'ts the user already rejected: two-line subtitles, green/mint words inside subtitles, Malay subtitle lines, bilingual lines, a second @shazclipper badge or a bottom watermark, background music or ambience, a gameplay band with a blurred bottom, Matcha Squishy (personal-use only).

## Setup (once per session)

Work in `films/<name>/` (git-ignored). Run from the library root.

```sh
sh plugin/skills/lemo-opuscar/scripts/setup.sh deps                     # .venv with numpy/scipy/Pillow
uv pip install --quiet --python .venv/bin/python faster-whisper edge-tts nudenet   # speech-to-text, cover voice, nudity check
# Demucs (voice separation) in its own venv, CPU torch:
uv venv --quiet --python 3.12 /tmp/demucs-venv
uv pip install --quiet --python /tmp/demucs-venv/bin/python --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple torch torchaudio
uv pip install --quiet --python /tmp/demucs-venv/bin/python demucs soundfile scipy
export DEMUCS_PY=/tmp/demucs-venv/bin/python HF_HUB_DISABLE_XET=1
```

Network: the `lemo-opuscar` environment allows drive.google.com, drive.usercontent.google.com, huggingface.co (+ cdn-lfs.hf.co, us.aws.cdn.hf.co), download.pytorch.org, dl.fbaipublicfiles.com, speech.platform.bing.com (edge-tts; `make_clip.py` passes `--proxy $HTTPS_PROXY` because aiohttp ignores the proxy env). If a download is refused by the proxy, ask for that host with the environment tools (one host at a time, with the reason).

## Workflow

1. **Get the VOD.** `sh .claude/skills/shazclipper/scripts/fetch_drive.sh "<drive link>" films/<name>/src/vod.mp4` (the link must be "Anyone with the link"). Probe it (`ffprobe`); a 4-h 1080p VOD is ~6 GB, check `df -h` first.
2. **Audio + transcript** (background; ~10 min of audio per 2 min of CPU with `small`):
   ```sh
   ffmpeg -v error -i src/vod.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le ana/audio16k.wav
   nohup .venv/bin/python .claude/skills/shazclipper/scripts/transcribe.py ana/audio16k.wav ana/transcript.jsonl > ana/transcribe.log 2>&1 &
   ```
   Give the user the transcript as `.txt` (`[h:mm:ss]` lines) and `.srt` if they ask.
3. **Find moments:** `.venv/bin/python .claude/skills/shazclipper/scripts/find_moments.py ana/audio16k.wav ana/transcript.jsonl ana/moments.json` (loudness above his running level + reaction words + talk). Then **look**: thumbnails every few seconds around each candidate and the transcript ±45 s. A clip needs a clear setup and payoff; skip pure cutscenes and menus.
4. **Find the layout** once per VOD: grid a frame, read the facecam box (aspect ≈ 1.42 for the 1080×760 panel), the minimap and HUD. Windah's GTA VI VOD: facecam `[1555, 784, 1885, 1016]`, minimap bottom-left (x < 335, y > 880). Keep the game crop clear of both.
5. **Spec per clip** (`films/<name>/clipNN/spec.json`):
   ```json
   {"name": "clip01_masuk-kantor-polisi", "source": ".../vod.mp4", "source_size": [1920, 1080],
    "streamer": "Windah Basudara", "lang": "id", "cam": [1555, 784, 1885, 1016],
    "game": {"w": 720, "cx": [[5376, 760], [5400, 900]], "cy": 620},
    "segments": [{"src": [5393, 5396], "speed": 1, "label": "hook"},
                 {"src": [5376, 5440], "speed": 1, "label": "clip"},
                 {"src": [5420, 5423], "speed": 0.5, "label": "replay"}],
    "cover": {"lines": ["NYUSUP KE", "KANTOR POLISI?!"], "say": "Nyusup ke kantor polisi?!", "frame": 5424, "voice": "id-ID-ArdiNeural", "rate": "+0%"},
    "hook": {"lines": ["NYUSUP KE", "KANTOR POLISI?!"], "cta": "TONTON SAMPAI HABIS"},
    "reactions": [{"t0": 40, "t1": 43, "text": "MUKANYA SANTAI BANGET…"}],
    "moment_words": "polisi|menerobos", "fix_words": {"menrobos": "menerobos"}, "end_card": true}
   ```
   `game.w` = crop width in source px (smaller = closer; ~980 for a 1080p VOD shows the character whole, 720 is a close-up); `cx`/`cy` = numbers or keyframes `[[source_time, value], …]` following the character, who should sit ~45 % down the panel. Segment times are VOD seconds. Replays are voiceless (a whoosh instead). `fix_words` corrects words Whisper mishears (check `words.json`). `cover.frame` = the VOD second to freeze (pick the most dramatic frame); `cover.say` = the sentence the voice reads (keep it ≤ 6 words so it fits ~1 s); other voices: `id-ID-GadisNeural` (female), `ms-MY-OsmanNeural` / `ms-MY-YasminNeural` (Malay). Delete `words.json` after adding or changing the cover (the timeline shifts).
6. **Covers first, for approval.** The user approves covers before any full render:
   ```sh
   .venv/bin/python .claude/skills/shazclipper/scripts/cover_preview.py films/<name>/clip0{2,3,4}/spec.json --sheet films/<name>/covers.jpg
   ```
   Send the sheet plus each `<name>_cover.mp4` (the cover with its voice). Keep `cover.say` short and without commas: a comma adds a pause (~0.4 s) and a cover over ~1.8 s feels slow. Match the voice to the cover text.
7. **Review stills, then render** (several clips: `sh .claude/skills/shazclipper/scripts/run_batch.sh films/<name>/clip02 films/<name>/clip03 …`, which frees each clip's frame cache after it renders):
   ```sh
   .venv/bin/python .claude/skills/shazclipper/scripts/make_clip.py films/<name>/clip01/spec.json --stills 1 10 30 60
   .venv/bin/python .claude/skills/shazclipper/scripts/make_clip.py films/<name>/clip01/spec.json
   ```
   Check the `_safe.jpg` stills: every text inside the green box, the subject not covered, the hook readable. The first run caches frames, voice and words under the clip folder; delete `words.json` after changing segments.
8. **Deliver** `films/<name>/clipNN/<name>.mp4` with SendUserFile, one line per clip: what happens, length, loudness. Remind once: clips follow the streamer's clipper-programme terms; credit stays in the bar.

## Monetisation notes (check the live rules; they change)

TikTok Creator Rewards: videos > 1 min, 10K followers, 100K views/30 days; most sources say Malaysia is not eligible yet. YouTube Shorts YPP: 1K subs + 10M Shorts views/90 days (rising on 1 Feb 2027). Facebook Content Monetization: invite-only. Reused-content rules are the main risk for clips: the edit (hook, layout, subtitles, moments, replay) is what makes a clip transformative.
