#!/usr/bin/env python3
"""OpenHiggs angles: many camera angles from one image, plus an optional camera move.

Drives a ComfyUI server over its HTTP API with the two bundled workflows:
  workflows/angle.api.json  Qwen-Image-Edit-2511 + Multiple-Angles LoRA (one new view per run)
  workflows/move.api.json   LTX-2 19B image-to-video + camera-control LoRA (one clip per run)

Standard library only (Pillow is optional, for the contact sheet).

  python3 openhiggs.py list
  python3 openhiggs.py angles photo.jpg --preset orbit8 --out out/
  python3 openhiggs.py angles photo.jpg --angle "front-left quarter view|low-angle shot|close-up"
  python3 openhiggs.py move out/angle_03.png --move dolly-in --scene "she turns to the window"
  python3 openhiggs.py pipeline photo.jpg --preset turnaround --move orbit-left --out out/

Server: --server or $COMFY_URL (default http://127.0.0.1:8188).
--dry-run writes the patched workflow JSON for every job and contacts no server.
"""
import argparse, copy, itertools, json, os, random, sys, time, uuid
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.join(HERE, "..", "workflows")

# Vocabulary the Multiple-Angles LoRA was trained on: "<sks> <azimuth> <elevation> <distance>"
AZIMUTHS = ["front view", "front-right quarter view", "right side view", "back-right quarter view",
            "back view", "back-left quarter view", "left side view", "front-left quarter view"]
ELEVATIONS = ["low-angle shot", "eye-level shot", "elevated shot", "high-angle shot"]
DISTANCES = ["close-up", "medium shot", "wide shot"]

PRESETS = {
    "orbit8":     [(a, "eye-level shot", "medium shot") for a in AZIMUTHS],
    "turnaround": [(a, "eye-level shot", "wide shot") for a in
                   ["front view", "right side view", "back view", "left side view"]],
    "coverage":   [("front view", "eye-level shot", "wide shot"),
                   ("front view", "eye-level shot", "medium shot"),
                   ("front view", "eye-level shot", "close-up"),
                   ("front-left quarter view", "low-angle shot", "medium shot"),
                   ("front-right quarter view", "elevated shot", "medium shot"),
                   ("right side view", "eye-level shot", "close-up"),
                   ("back-left quarter view", "eye-level shot", "medium shot"),
                   ("front view", "high-angle shot", "wide shot")],
    "heights":    [("front view", e, "medium shot") for e in ELEVATIONS],
    "distances":  [("front view", "eye-level shot", d) for d in DISTANCES],
    "full96":     list(itertools.product(AZIMUTHS, ELEVATIONS, DISTANCES)),
}

# LTX-2 camera-control LoRAs. None = no LoRA for this move: strength 0, the prompt alone moves the camera.
MOVES = {
    "dolly-in":    ("ltx-2-19b-lora-camera-control-dolly-in.safetensors",
                    "The camera dollies in toward the subject, ending on a close-up."),
    "dolly-out":   ("ltx-2-19b-lora-camera-control-dolly-out.safetensors",
                    "The camera dollies out, revealing the surroundings."),
    "dolly-left":  ("ltx-2-19b-lora-camera-control-dolly-left.safetensors",
                    "The camera tracks smoothly to the left."),
    "dolly-right": ("ltx-2-19b-lora-camera-control-dolly-right.safetensors",
                    "The camera tracks smoothly to the right."),
    "jib-up":      ("ltx-2-19b-lora-camera-control-jib-up.safetensors",
                    "The camera cranes up, rising above the subject."),
    "jib-down":    ("ltx-2-19b-lora-camera-control-jib-down.safetensors",
                    "The camera cranes down to the subject's eye level."),
    "static":      ("ltx-2-19b-lora-camera-control-static.safetensors",
                    "The camera is locked off, completely still."),
    "orbit-left":  (None, "The camera orbits slowly around the subject to the left, keeping it centred."),
    "orbit-right": (None, "The camera orbits slowly around the subject to the right, keeping it centred."),
    "handheld":    (None, "Handheld camera, gentle natural sway, following the subject."),
}
DEFAULT_SCENE = "the subject holds the moment, subtle natural motion"
LOOK = "35mm lens, natural perspective. cinematic, film still quality"


def load_wf(name):
    with open(os.path.join(WF_DIR, name)) as f:
        return json.load(f)


def angle_prompt(az, el, dist):
    for v, allowed, what in ((az, AZIMUTHS, "azimuth"), (el, ELEVATIONS, "elevation"), (dist, DISTANCES, "distance")):
        if v not in allowed:
            sys.exit(f"unknown {what} '{v}'. Choose from: {', '.join(allowed)}")
    return f"<sks> {az} {el} {dist}"


def parse_angle(s):
    parts = [p.strip() for p in s.split("|")]
    if len(parts) != 3:
        sys.exit(f"--angle must be 'azimuth|elevation|distance', got '{s}'")
    return tuple(parts)


def patch_angle(image_name, az, el, dist, seed, quality, prefix):
    wf = load_wf("angle.api.json")
    wf["1"]["inputs"]["image"] = image_name
    wf["10"]["inputs"]["prompt"] = angle_prompt(az, el, dist)
    wf["15"]["inputs"]["seed"] = seed
    if quality == "full":  # as the workflow's own note says: Lightning off, 40 steps, cfg 4
        wf["7"]["inputs"]["strength_model"] = 0
        wf["15"]["inputs"].update(steps=40, cfg=4)
    wf["17"]["inputs"]["filename_prefix"] = prefix
    return wf


def patch_move(image_name, move, scene, seed, seconds, fps, width, height, prefix, negative=None):
    if move not in MOVES:
        sys.exit(f"unknown move '{move}'. Choose from: {', '.join(MOVES)}")
    lora, phrase = MOVES[move]
    wf = load_wf("move.api.json")
    wf["1"]["inputs"]["image"] = image_name
    wf["2"]["inputs"]["resize_type.width"] = width
    wf["2"]["inputs"]["resize_type.height"] = height
    if lora:
        wf["11"]["inputs"]["lora_name"] = lora
        wf["11"]["inputs"]["strength_model"] = 1
    else:
        wf["11"]["inputs"]["strength_model"] = 0
    wf["20"]["inputs"]["text"] = f"{scene.rstrip('. ')}. {phrase} {LOOK}"
    if negative:
        wf["21"]["inputs"]["text"] = negative
    wf["22"]["inputs"]["value"] = fps
    frames = round(seconds * fps / 8) * 8 + 1  # LTX needs 8n+1 frames
    wf["24"]["inputs"]["value"] = max(frames, 9)
    wf["34"]["inputs"]["noise_seed"] = seed
    wf["53"]["inputs"]["filename_prefix"] = prefix
    return wf


class Comfy:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def _req(self, path, data=None, headers=None):
        req = urllib.request.Request(self.url + path, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            sys.exit(f"ComfyUI {path} -> HTTP {e.code}: {e.read().decode(errors='replace')[:2000]}")
        except urllib.error.URLError as e:
            sys.exit(f"cannot reach ComfyUI at {self.url}: {e.reason}. Set --server or COMFY_URL.")

    def upload(self, path):
        boundary = uuid.uuid4().hex
        name = f"openhiggs_{uuid.uuid4().hex[:8]}_{os.path.basename(path)}"
        with open(path, "rb") as f:
            blob = f.read()
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + blob + \
               f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
        res = json.loads(self._req("/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
        return (res.get("subfolder") + "/" if res.get("subfolder") else "") + res["name"]

    def queue(self, wf):
        body = json.dumps({"prompt": wf, "client_id": self.client_id}).encode()
        res = json.loads(self._req("/prompt", body, {"Content-Type": "application/json"}))
        if res.get("node_errors"):
            sys.exit(f"ComfyUI rejected the workflow: {json.dumps(res['node_errors'])[:2000]}")
        return res["prompt_id"]

    def wait(self, pid, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            h = json.loads(self._req(f"/history/{pid}")).get(pid)
            if h:
                st = h.get("status", {})
                if st.get("status_str") == "error":
                    msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                    sys.exit(f"job {pid} failed: {json.dumps(msgs)[:2000]}")
                if st.get("completed", True):
                    return h["outputs"]
            time.sleep(2)
        sys.exit(f"job {pid} timed out after {timeout}s")

    def fetch_outputs(self, outputs, dest_stem):
        saved = []
        for node in outputs.values():
            for key in ("images", "videos", "gifs", "video"):
                for i, item in enumerate(node.get(key, []) or []):
                    if not isinstance(item, dict) or item.get("type") == "temp":
                        continue
                    q = urllib.parse.urlencode({k: item.get(k, "") for k in ("filename", "subfolder", "type")})
                    ext = os.path.splitext(item["filename"])[1]
                    dest = f"{dest_stem}{'' if i == 0 else f'_{i}'}{ext}"
                    with open(dest, "wb") as f:
                        f.write(self._req(f"/view?{q}"))
                    saved.append(dest)
        return saved


def slug(az, el, dist):
    return "_".join(x.replace(" view", "").replace(" shot", "").replace(" ", "-") for x in (az, el, dist))


def contact_sheet(paths, labels, dest):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    thumbs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        im.thumbnail((384, 384))
        thumbs.append(im)
    if not thumbs:
        return None
    cols = min(4, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cw, ch = 384, max(t.height for t in thumbs) + 24
    sheet = Image.new("RGB", (cols * cw, rows * ch), (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    for i, (t, lab) in enumerate(zip(thumbs, labels)):
        x, y = (i % cols) * cw, (i // cols) * ch
        sheet.paste(t, (x + (cw - t.width) // 2, y))
        d.text((x + 6, y + ch - 20), lab, fill=(230, 230, 230))
    sheet.save(dest)
    return dest


def run_angles(a, comfy):
    if a.angle:
        angles = [parse_angle(s) for s in a.angle]
    else:
        angles = PRESETS[a.preset]
    os.makedirs(a.out, exist_ok=True)
    seed = a.seed if a.seed is not None else random.randrange(2**31)
    image_name = "input.png" if a.dry_run else comfy.upload(a.image)
    results, manifest = [], []
    for i, (az, el, dist) in enumerate(angles, 1):
        stem = os.path.join(a.out, f"angle_{i:02d}_{slug(az, el, dist)}")
        wf = patch_angle(image_name, az, el, dist, seed, a.quality, f"openhiggs/angle_{i:02d}")
        entry = {"index": i, "azimuth": az, "elevation": el, "distance": dist,
                 "prompt": angle_prompt(az, el, dist), "seed": seed}
        if a.dry_run:
            with open(stem + ".api.json", "w") as f:
                json.dump(wf, f, indent=2)
            entry["workflow"] = stem + ".api.json"
            print(f"[{i}/{len(angles)}] dry-run {entry['prompt']}")
        else:
            print(f"[{i}/{len(angles)}] {entry['prompt']} ...", flush=True)
            files = comfy.fetch_outputs(comfy.wait(comfy.queue(wf), a.timeout), stem)
            entry["files"] = files
            results += [(f, f"{i:02d} {az} / {el} / {dist}") for f in files if not f.endswith(".json")]
            print("   ->", ", ".join(files))
        manifest.append(entry)
    with open(os.path.join(a.out, "angles.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    if results:
        sheet = contact_sheet([r[0] for r in results], [r[1] for r in results], os.path.join(a.out, "contact.png"))
        if sheet:
            print("contact sheet:", sheet)
    return [r[0] for r in results]


def run_move(a, comfy, image):
    os.makedirs(a.out, exist_ok=True)
    seed = a.seed if a.seed is not None else random.randrange(2**31)
    image_name = "input.png" if a.dry_run else comfy.upload(image)
    stem = os.path.join(a.out, f"move_{a.move}_{os.path.splitext(os.path.basename(image))[0]}")
    wf = patch_move(image_name, a.move, a.scene, seed, a.seconds, a.fps, a.width, a.height,
                    f"openhiggs/move_{a.move}", a.negative)
    if a.dry_run:
        with open(stem + ".api.json", "w") as f:
            json.dump(wf, f, indent=2)
        print(f"dry-run move {a.move}: {wf['20']['inputs']['text']}  ({wf['24']['inputs']['value']} frames)")
        return
    print(f"move {a.move} from {image} ...", flush=True)
    print("   ->", ", ".join(comfy.fetch_outputs(comfy.wait(comfy.queue(wf), a.timeout), stem)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--server", default=os.environ.get("COMFY_URL", "http://127.0.0.1:8188"))
    p.add_argument("--dry-run", action="store_true", help="write patched workflows, contact no server")
    p.add_argument("--timeout", type=int, default=1800, help="seconds to wait per job")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show presets, angle vocabulary and moves")

    def angle_args(sp):
        sp.add_argument("image")
        sp.add_argument("--preset", default="orbit8", choices=PRESETS)
        sp.add_argument("--angle", action="append", help="'azimuth|elevation|distance'; repeatable, overrides --preset")
        sp.add_argument("--quality", default="fast", choices=["fast", "full"], help="fast = Lightning 4 steps")

    def move_args(sp, needs_image):
        if needs_image:
            sp.add_argument("image")
        sp.add_argument("--move", default="dolly-in", choices=MOVES)
        sp.add_argument("--scene", default=DEFAULT_SCENE, help="what happens in the shot")
        sp.add_argument("--negative", help="override the negative prompt")
        sp.add_argument("--seconds", type=float, default=5)
        sp.add_argument("--fps", type=int, default=24)
        sp.add_argument("--width", type=int, default=1280)
        sp.add_argument("--height", type=int, default=704)

    for name, fn in (("angles", lambda s: angle_args(s)), ("move", lambda s: move_args(s, True)),
                     ("pipeline", lambda s: (angle_args(s), move_args(s, False)))):
        sp = sub.add_parser(name)
        fn(sp)
        sp.add_argument("--out", default="openhiggs_out")
        sp.add_argument("--seed", type=int)
    a = p.parse_args()

    if a.cmd == "list":
        print("Presets:")
        for k, v in PRESETS.items():
            print(f"  {k:<11} {len(v):>3} angles")
        print("Azimuth:  ", " | ".join(AZIMUTHS))
        print("Elevation:", " | ".join(ELEVATIONS))
        print("Distance: ", " | ".join(DISTANCES))
        print("Moves:    ", " | ".join(f"{k}{'' if v[0] else '*'}" for k, v in MOVES.items()), "(* prompt-only)")
        return
    comfy = None if a.dry_run else Comfy(a.server)
    if a.cmd == "angles":
        run_angles(a, comfy)
    elif a.cmd == "move":
        run_move(a, comfy, a.image)
    else:
        frames = run_angles(a, comfy)
        if a.dry_run:
            run_move(a, comfy, a.image)
        for f in frames:
            run_move(a, comfy, f)


if __name__ == "__main__":
    main()
