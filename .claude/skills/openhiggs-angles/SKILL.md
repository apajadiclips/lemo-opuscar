---
name: openhiggs-angles
description: Make many camera angles of one photo (orbit, turnaround, coverage, up to 96 views) and optionally turn each into a short camera-move video clip, on the user's own ComfyUI server (Qwen-Image-Edit-2511 Multiple-Angles LoRA + LTX-2 camera-control LoRAs). Use when the user wants other angles of an image, a character or product turnaround, shot coverage from one still, "banyak angle", "tukar angle kamera", or a dolly / crane / orbit clip from a picture.
---

# OpenHiggs angles

One image in → many new camera views → (optional) one camera-move clip per view.
Everything runs on the user's ComfyUI through `scripts/openhiggs.py` (standard library; Pillow optional for the contact sheet).

## 1. Check the server once

- Server URL: `--server` or `$COMFY_URL` (default `http://127.0.0.1:8188`). If you can't reach it, ask the user for the URL. A cloud session can't reach the user's localhost: they need a public URL, or run the skill on their own machine.
- The models must already be on the server. File names are in `workflows/*.api.json`: `qwen_image_edit_2511_bf16`, `qwen-image-edit-2511-multiple-angles-lora`, `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16`, `qwen_2.5_vl_7b`, `qwen_image_vae`; and for moves `ltx-2-19b-dev-fp8`, `ltx-2-19b-distilled-lora-384`, `gemma_3_12B_it_fp4_mixed`, `ltx-2-spatial-upscaler-x2-1.0`, plus whichever `ltx-2-19b-lora-camera-control-*` LoRAs the moves need. If ComfyUI rejects the workflow, the script prints the node errors: tell the user which file is missing.

## 2. Pick the angles

`python3 scripts/openhiggs.py list` prints everything. The LoRA only understands its own vocabulary, so **always use these exact words**:

| Part | Values |
|---|---|
| azimuth | front view, front-right quarter view, right side view, back-right quarter view, back view, back-left quarter view, left side view, front-left quarter view |
| elevation | low-angle shot, eye-level shot, elevated shot, high-angle shot |
| distance | close-up, medium shot, wide shot |

Presets: `orbit8` (8 around, eye level), `turnaround` (front/right/back/left, wide: character or product sheet), `coverage` (8 shots for editing a scene), `heights` (4), `distances` (3), `full96` (every combination).
Map the user's wording to these yourself ("dari bawah" → low-angle shot, "sisi kiri" → left side view, "dekat" → close-up). Use repeatable `--angle "azimuth|elevation|distance"` for a custom list.

## 3. Run

```bash
S=.claude/skills/openhiggs-angles/scripts/openhiggs.py
python3 $S angles photo.jpg --preset orbit8 --out out/            # images + angles.json + contact.png
python3 $S angles photo.jpg --angle "back view|high-angle shot|wide shot" --quality full
python3 $S move out/angle_03_*.png --move jib-up --scene "rain starts falling"
python3 $S pipeline photo.jpg --preset turnaround --move orbit-left --out out/
```

- `--quality fast` (default) = Lightning, 4 steps: quick drafts. `full` = 40 steps, cfg 4: final frames, ~10× slower.
- One `--seed` is shared by every angle so the views stay consistent; it's written to `angles.json`.
- Moves: `dolly-in/out/left/right`, `jib-up/down`, `static` use their LoRA. `orbit-left/right` and `handheld` have no LoRA and rely on the prompt alone, so they are less reliable. `--scene` describes what happens in the shot; the script adds the camera phrase and the look. Default length 5 s at 24 fps, 1280×704 (`--seconds --fps --width --height`; frames are rounded to 8n+1).
- `full96` and `pipeline` queue many GPU jobs. Before starting more than ~12, tell the user the count and confirm.
- `--dry-run` writes the patched workflow JSON for every job without contacting a server, so you can check prompts or hand the user files to drop into ComfyUI.

## 4. Deliver

Show `contact.png` first, then the files the user asks for. Say which seed and quality were used, and offer to re-run any angle at `--quality full` or with a new seed.
