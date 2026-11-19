"""Make one @shazclipper clip from a stream VOD, driven by a spec JSON. See SKILL.md for the spec and the style rules.

  python make_clip.py spec.json            # full clip -> <work>/<name>.mp4
  python make_clip.py spec.json --stills 0.5 6 12   # review frames (+ *_safe.jpg with the safe-zone overlay)

Pipeline: enhanced frames per segment (nlmeans + CAS) -> voice only per segment (Demucs, no back sound) ->
Whisper word times on the clip's own voice -> plain subtitles + moment words in Titan One mint -> mix -> -14 LUFS."""
import json, math, os, re, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import shaz_style as S
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(LIB, "core", "audio")); import sfx
FPS, SFPS = 24, 30.0
# picture clean-up: strong (nlmeans) for low-res screen recordings, light and fast (hqdn3d) for 1080p+ VODs
ENH_LOW = "nlmeans=s=2:p=5:r=9,cas=strength=0.6,eq=contrast=1.05:saturation=1.1"
ENH_HD = "hqdn3d=1.5:1.5:6:6,cas=strength=0.5,eq=contrast=1.05:saturation=1.1"

SPEC = json.load(open(sys.argv[1])); WORK = os.path.abspath(SPEC.get("work", os.path.dirname(os.path.abspath(sys.argv[1]))))
NAME = SPEC["name"]; S.STREAMER = SPEC.get("streamer", S.STREAMER)
if SPEC.get("moment_words"): S.MOMENT_WORDS = S.MOMENT_WORDS + "|" + SPEC["moment_words"]
SEGS = SPEC["segments"]                       # [{src: [a, b], speed: 1, label: hook|clip|replay}]
for k, g in enumerate(SEGS): g["k"] = k; g["dur"] = (g["src"][1] - g["src"][0]) / g.get("speed", 1.0)
END = 3.4 if SPEC.get("end_card", True) else 0       # the "full video on the streamer's channel" card
def run(cmd, **kw): subprocess.run(cmd, check=True, **kw)

# ---------- 0. cover: a 1-s+ title frame with a voice saying the hook (edge-tts) ----------
COVER = SPEC.get("cover")                     # {lines: [...], say: "...", frame: vod_seconds, voice: "id-ID-ArdiNeural", rate: "+20%"}
COVER_DUR = 0.0
def cover_tts():
    os.makedirs(f"{WORK}/audio", exist_ok=True); mp3, wav_ = f"{WORK}/audio/cover_tts.mp3", f"{WORK}/audio/cover_tts.wav"
    if not os.path.exists(wav_):
        say = COVER.get("say") or " ".join(COVER.get("lines") or SPEC.get("hook", {}).get("lines", []))
        env = dict(os.environ, SSL_CERT_FILE=os.environ.get("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt"))
        cmd = [os.path.join(LIB, ".venv", "bin", "edge-tts"), "--voice", COVER.get("voice", "id-ID-ArdiNeural"), f"--rate={COVER.get('rate', '+0%')}", "--text", say, "--write-media", mp3]
        if os.environ.get("HTTPS_PROXY"): cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]   # aiohttp ignores the proxy env by itself
        run(cmd, env=env)
        trim = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"
        run(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-af", trim, "-ac", "2", "-ar", "48000", wav_])
    with wave.open(wav_) as w: return w.getnframes() / w.getframerate()
if COVER: COVER_DUR = max(COVER.get("min", 1.0), cover_tts() + .2)
DUR = COVER_DUR + sum(g["dur"] for g in SEGS) + END
o = COVER_DUR
for g in SEGS: g["o0"] = o; o += g["dur"]
SW, SH = SPEC.get("source_size", [1920, 1080])
ENHANCE = SPEC.get("enhance") or (ENH_HD if SH >= 1000 else ENH_LOW)
CAM = SPEC["cam"]                             # facecam box in source px [x0, y0, x1, y1]
GAME = SPEC.get("game", {})                   # crop width and centre keyframes (source time -> cx, cy)

def seg_at(t):
    for g in SEGS:
        if t < g["o0"] + g["dur"]: return g, (t - g["o0"])
    g = SEGS[-1]; return g, g["dur"] - 1e-3

# ---------- 1. enhanced frames per segment ----------
def prep_frames():
    if COVER and not os.path.exists(f"{WORK}/frames/cover.jpg"):
        os.makedirs(f"{WORK}/frames", exist_ok=True)
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(COVER.get("frame", SEGS[0]["src"][0])), "-i", SPEC["source"], "-frames:v", "1", "-vf", ENHANCE, "-q:v", "2", f"{WORK}/frames/cover.jpg"])
    for g in SEGS:
        d = f"{WORK}/frames/seg{g['k']:02d}"
        if os.path.isdir(d) and len(os.listdir(d)) >= int((g["src"][1] - g["src"][0]) * SFPS) - 2: continue
        os.makedirs(d, exist_ok=True); a, b = g["src"]
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", SPEC["source"], "-vf", f"fps={SFPS:g},{ENHANCE}", "-q:v", "2", f"{d}/%05d.jpg"])
@lru_cache(maxsize=24)
def frame_img(k, i):
    d = f"{WORK}/frames/seg{k:02d}"; n = len(os.listdir(d))
    return Image.open(f"{d}/{max(0, min(i, n - 1)) + 1:05d}.jpg").convert("RGB")
def src_img(g, lt):
    f = lt * g.get("speed", 1.0) * SFPS; i = int(f); kf = f - i
    a = frame_img(g["k"], i)
    return Image.blend(a, frame_img(g["k"], i + 1), kf) if kf > .05 and g.get("speed", 1.0) < 1 else a

# ---------- 1b. sexual-content check: NudeNet on the frames, plus manual "blur" ranges in the spec ----------
NSFW_CLASSES = {"FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", "BUTTOCKS_EXPOSED", "ANUS_EXPOSED"}
BLUR = []                                     # [(a, b)] in VOD seconds where the gameplay is blurred
def scan_nsfw():
    """Every 1/3 s of every segment (and the cover frame), flag exposed-nudity detections; blur +-0.8 s around them.
    Cached in nsfw.json. Manual ranges: "blur": [[a, b], ...] (VOD seconds) for anything the detector misses."""
    p = f"{WORK}/nsfw.json"
    if os.path.exists(p): hits = json.load(open(p))
    else:
        from nudenet import NudeDetector
        det = NudeDetector(); hits = []
        jobs = [(g["src"][0] + i / SFPS, f"{WORK}/frames/seg{g['k']:02d}/{i + 1:05d}.jpg") for g in SEGS for i in range(0, len(os.listdir(f"{WORK}/frames/seg{g['k']:02d}")), 10)]
        if COVER: jobs.append((COVER.get("frame", SEGS[0]["src"][0]), f"{WORK}/frames/cover.jpg"))
        for st, f in jobs:
            found = [d for d in det.detect(f) if d["class"] in NSFW_CLASSES and d["score"] >= SPEC.get("nsfw_threshold", .45)]
            if found: hits.append(dict(t=round(st, 2), classes=sorted({d["class"] for d in found}), score=round(max(d["score"] for d in found), 2)))
        json.dump(hits, open(p, "w"), indent=1)
    rng = sorted([(h["t"] - .8, h["t"] + .8) for h in hits] + [tuple(r) for r in SPEC.get("blur", [])])
    for a, b in rng:                          # merge overlaps
        if BLUR and a <= BLUR[-1][1]: BLUR[-1] = (BLUR[-1][0], max(BLUR[-1][1], b))
        else: BLUR.append((a, b))
    return hits
def blurred(st): return any(a <= st <= b for a, b in BLUR)

# ---------- 2. voice only, per segment ----------
def prep_voice():
    py = os.environ.get("DEMUCS_PY") or SPEC.get("demucs_py")
    for g in SEGS:
        raw, voc = f"{WORK}/audio/seg{g['k']:02d}.wav", f"{WORK}/audio/seg{g['k']:02d}_voice.wav"
        if os.path.exists(voc): continue
        os.makedirs(f"{WORK}/audio", exist_ok=True); a, b = g["src"]
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", SPEC["source"], "-vn", "-ac", "2", "-ar", "48000", raw])
        if py and SPEC.get("remove_back_sound", True): run([py, f"{HERE}/separate_voice.py", raw, voc])
        else: os.replace(raw, voc)
def read_wav(p):
    with wave.open(p) as w: return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, w.getnchannels()).astype(np.float64) / 32768
def build_voice(with_bg=False):
    """The clip's voice track: segments at speed 1 keep his voice; slowed replays are voiceless (a whoosh in the mix).
    with_bg: add the game's own sound (Demucs' other stems) quietly under the voice ("back_sound" level, default 0.18 = about -15 dB)."""
    buf = np.zeros((int(DUR * 48000), 2)); lvl = float(SPEC.get("back_sound", .18))
    for g in SEGS:
        if abs(g.get("speed", 1.0) - 1) > .01: continue
        v = read_wav(f"{WORK}/audio/seg{g['k']:02d}_voice.wav")
        bgp = f"{WORK}/audio/seg{g['k']:02d}_voice_bg.wav"
        if with_bg and lvl > 0 and os.path.exists(bgp):
            b = read_wav(bgp); n0 = min(len(v), len(b)); v = v[:n0] + b[:n0] * lvl
        s = int(g["o0"] * 48000); n = min(len(v), len(buf) - s)
        fade = np.ones(n); m = min(480, n // 2); fade[:m] = np.linspace(0, 1, m); fade[-m:] = np.linspace(1, 0, m)
        buf[s:s + n] += v[:n] * fade[:, None]
    return buf

# ---------- 3. words: Whisper on the clip's own voice ----------
def prep_words(voice):
    p = f"{WORK}/words.json"
    if os.path.exists(p): return json.load(open(p))
    from faster_whisper import WhisperModel
    mono = voice.mean(1); x = mono[::3].astype(np.float32)                    # 48 kHz -> 16 kHz
    m = WhisperModel(SPEC.get("whisper_model", os.environ.get("WHISPER_CLIP_MODEL", "large-v3-turbo")), device="cpu", compute_type="int8")
    segs, _ = m.transcribe(x, language=SPEC.get("lang", "id"), word_timestamps=True, beam_size=5)
    words = [dict(w=w.word.strip(), t0=round(w.start, 2), t1=round(w.end, 2)) for s in segs for w in s.words if w.word.strip()]
    words = [w for w in words if not re.fullmatch(r"\W*", w["w"])]
    json.dump(words, open(p, "w"), ensure_ascii=False, indent=1); return words
def chunks(words):
    """Phrases: split on punctuation or a pause > 0.35 s, merge pieces shorter than 0.5 s (max 5 words)."""
    out, cur = [], []
    for i, x in enumerate(words):
        cur.append(x); gap = words[i + 1]["t0"] - x["t1"] if i + 1 < len(words) else 9
        if re.search(r"[.,!?]$", x["w"]) or gap > .35: out.append(cur); cur = []
    if cur: out.append(cur)
    merged = []
    for c in out:
        if merged and merged[-1][-1]["t1"] - merged[-1][0]["t0"] < .5 and len(merged[-1]) + len(c) <= 5 and c[0]["t0"] - merged[-1][-1]["t1"] < .5: merged[-1] += c
        else: merged.append(c)
    for j, c in enumerate(merged):
        nxt = merged[j + 1][0]["t0"] if j + 1 < len(merged) else None
        c[0]["c0"] = c[0]["t0"]; c[0]["c1"] = nxt if nxt is not None and nxt - c[-1]["t1"] < .9 else c[-1]["t1"] + .6
    return merged

# ---------- 4. picture ----------
def keyed(st, key, default):
    kf = GAME.get(key)
    if not kf: return default
    if isinstance(kf, (int, float)): return kf
    for (t0, v0), (t1, v1) in zip(kf, kf[1:]):
        if t0 <= st <= t1: return S.lerp(v0, v1, S.eio(S.seg(st, t0, t1)))
    return kf[0][1] if st < kf[0][0] else kf[-1][1]
def lift_dark(im):
    """Night scenes: a gentle gamma lift when the picture is dark (mean luma < 70), stronger the darker it is."""
    m = np.asarray(im.convert("L").resize((96, 96))).mean()
    if m >= 70 or not SPEC.get("auto_brighten", True): return im
    g = S.lerp(.62, .9, S.clamp((m - 20) / 50, 0, 1))               # gamma < 1 brightens shadows more than highlights
    return im.point([int(255 * (i / 255) ** g) for i in range(256)] * 3)
def game_panel(img, st, zoom):
    w = keyed(st, "w", 720) / zoom; h = w * S.GAME_H / S.W
    cx = keyed(st, "cx", SW * .45); cy = keyed(st, "cy", SH * .5)
    y0 = S.clamp(cy - .45 * h, 0, SH - h); x0 = S.clamp(cx - w / 2, 0, SW - w)
    return lift_dark(S.panel(img, (x0, y0, x0 + w, y0 + h), S.W, S.GAME_H, 1.1))
_SR = None
def ai_upscale(im):
    """Real-ESRGAN realesr-general-x4v3 (ONNX, CPU): x4 super-resolution, one session per worker process."""
    global _SR
    if _SR is None:
        import onnxruntime as ort
        so = ort.SessionOptions(); so.intra_op_num_threads = int(os.environ.get("SR_THREADS", 1))
        _SR = ort.InferenceSession(os.path.join(os.path.dirname(HERE), "models", "realesr-general-x4v3.onnx"), so, providers=["CPUExecutionProvider"])
    x = np.asarray(im, dtype=np.float32).transpose(2, 0, 1)[None] / 255
    y = _SR.run(None, {"img": x})[0][0].clip(0, 1).transpose(1, 2, 0)
    return Image.fromarray((y * 255 + .5).astype(np.uint8))
def cam_panel(img, zoom):
    x0, y0, x1, y1 = CAM
    if SPEC.get("ai_face", True):            # AI on the facecam: the crop is upscaled ~3.3x, so this is where it shows
        up = ai_upscale(img.crop(tuple(int(v) for v in CAM))); k = up.width / (x1 - x0)
        cx, cy = up.width / 2, up.height / 2; hw, hh = up.width / 2 / zoom, up.height / 2 / zoom
        return S.panel(up, (cx - hw, cy - hh, cx + hw, cy + hh), S.W, S.CAM_H, 1.0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; hw, hh = (x1 - x0) / 2 / zoom, (y1 - y0) / 2 / zoom
    return S.panel(img, (cx - hw, cy - hh, cx + hw, cy + hh), S.W, S.CAM_H, 1.2)

WORDS, CH, BIG = [], [], []
def cover_frame(t):
    """The cover: frozen dramatic frame, slow push, the hook in big Titan One, a flash on frame 0."""
    img = Image.open(f"{WORK}/frames/cover.jpg").convert("RGB"); st = COVER.get("frame", SEGS[0]["src"][0])
    k = S.seg(t, 0, COVER_DUR)
    game = ImageEnhance.Brightness(game_panel(img, st, 1.12 + .08 * k)).enhance(.8)
    if blurred(st): game = game.filter(ImageFilter.GaussianBlur(45))
    base = S.compose(cam_panel(img, 1.1 + .05 * k), game).convert("RGBA")
    lines = COVER.get("lines") or SPEC.get("hook", {}).get("lines", [])
    for i, line in enumerate(lines):
        S.moment(base, line, S.GAME_Y + 200 + i * 140, 104 if i == 0 else 136, S.back(S.seg(t, .05 * i, .2 + .05 * i)), S.WHT if i == 0 else S.MINT)
    im = base.convert("RGB")
    if t < .1: im = Image.blend(im, Image.new("RGB", (S.W, S.H), S.WHT), .5 * (1 - t / .1))
    return im

def frame(n):
    t = n / FPS
    if t < COVER_DUR: return cover_frame(t)
    end = END and t >= DUR - END
    g, lt = seg_at(min(t, DUR - END - 1e-3)) if END else seg_at(t)
    if end: lt = g["dur"] - 1e-3
    st = g["src"][0] + lt * g.get("speed", 1.0); img = src_img(g, lt); lab = g.get("label", "clip")
    punch = 1 + .06 * math.exp(-lt / .15) + .06 * max([math.exp(-(t - e) / .15) for e in BIG if 0 <= t - e < 1] + [0])
    gz = punch * (S.lerp(1.25, 1.12, S.seg(lt, 0, g["dur"])) if lab == "hook" else S.lerp(1.05, 1.2, S.seg(lt, 0, g["dur"])) if lab == "replay" else 1)
    cam = cam_panel(img, 1.08 if lab in ("hook", "replay") else punch); game = game_panel(img, st, gz)
    if lab == "replay": game = ImageEnhance.Color(game).enhance(.6)
    if blurred(st): game = game.filter(ImageFilter.GaussianBlur(45))         # sexual content: the gameplay is blurred
    im = S.compose(cam, game); d = ImageDraw.Draw(im, "RGBA")
    if lab == "replay":
        for (x, y, sx, sy) in ((40, S.GAME_Y + 30, 1, 1), (S.W - 40, S.GAME_Y + 30, -1, 1), (40, S.H - 40, 1, -1), (S.W - 40, S.H - 40, -1, -1)):
            d.line([(x, y), (x + 80 * sx, y)], fill=S.RED, width=10); d.line([(x, y), (x, y + 80 * sy)], fill=S.RED, width=10)
        d.rounded_rectangle((S.SAFE[0] + 30, S.GAME_Y + 60, S.SAFE[0] + 360, S.GAME_Y + 126), 33, fill=(0, 0, 0, 170))
        if int(t * 2) % 2 == 0: d.ellipse((S.SAFE[0] + 52, S.GAME_Y + 80, S.SAFE[0] + 78, S.GAME_Y + 106), fill=S.RED)
        d.text((S.SAFE[0] + 94, S.GAME_Y + 93), f"REPLAY {g.get('speed', .5):g}×", font=S.F(34), fill=S.WHT, anchor="lm")
    if end: d.rectangle((0, S.GAME_Y, S.W, S.H), fill=(0, 0, 0, int(150 * S.seg(t, DUR - END, DUR - END + .4))))
    base = im.convert("RGBA")
    hook = SPEC.get("hook"); th = t - COVER_DUR
    in_hook = hook and 0 <= th < SPEC.get("hook_dur", 3.0)
    if in_hook:                                            # hook: Titan One mint, in the safe zone (lines only without a cover)
        for i, line in enumerate([] if COVER else hook["lines"]):
            S.moment(base, line, S.GAME_Y + 130 + i * 118, 90 if i == 0 else 120, S.back(S.seg(th, .1 * i, .25 + .1 * i)))
        if hook.get("cta"):
            d2 = ImageDraw.Draw(base); s = hook["cta"]; tw = d2.textlength(s, font=S.F(32)); y = S.SAFE[3] - 110 if COVER else S.GAME_Y + 100 + len(hook["lines"]) * 118 + 30   # with a cover the subtitles run at the top: the pill goes low
            d2.rounded_rectangle((S.SAFE_CX - tw / 2 - 26, y, S.SAFE_CX + tw / 2 + 26, y + 60), 30, fill=S.RED + (235,))
            d2.text((S.SAFE_CX, y + 30), s, font=S.F(32), fill=S.WHT, anchor="mm")
    for r in SPEC.get("reactions", []):                    # [{t0, t1, text}] in clip time: a moment line over the facecam
        if r["t0"] <= t < r["t1"]: S.moment(base, r["text"], S.DIV_Y - 80, r.get("size", 60))
    if end:                                              # end card: send viewers to the streamer's full video
        te = t - (DUR - END)
        S.moment(base, SPEC.get("end_line1", "NONTON FULL VIDEO"), S.GAME_Y + 170, 84, S.back(S.seg(te, .1, .35)), S.WHT)
        S.moment(base, SPEC.get("end_line2", "DI CHANNEL"), S.GAME_Y + 268, 96, S.back(S.seg(te, .2, .45)))
        if te > .45:                                     # just the channel handle under it
            handle = SPEC.get("streamer_handle", "@" + S.STREAMER.replace(" ", ""))
            S.subtitle_plain(base, handle, y=S.GAME_Y + 390, sz=58)
    elif not (in_hook and not COVER):
        for c in CH:
            if c[0]["c0"] <= t < c[0]["c1"]:
                if SPEC.get("subtitle_style", "plain") == "plain": S.subtitle_plain(base, " ".join(x["w"] for x in c))
                else: S.subtitle(base, t, " ".join(x["w"] for x in c), None, times=[x["t0"] for x in c], t_on=c[0]["t0"])   # "moments": mint words
    im = base.convert("RGB")
    for g2 in (SEGS if COVER else SEGS[1:]):
        if g2["o0"] <= t < g2["o0"] + .08: im = Image.blend(im, Image.new("RGB", (S.W, S.H), S.WHT), .3 * (1 - (t - g2["o0"]) / .08))
    return im

def mix(voice):
    buf = voice.copy()
    if COVER:                                              # the cover: a hit on frame 0 and the voice saying the hook
        sfx.add(buf, sfx.thump(f=55), 0.0, .55)
        tts = read_wav(f"{WORK}/audio/cover_tts.wav"); n = min(len(tts), len(buf) - 2400); buf[2400:2400 + n] += tts[:n] * 1.6
    for g in (SEGS if COVER else SEGS[1:]): sfx.add(buf, sfx.whoosh(.3), g["o0"] - .15, .3)
    for g in SEGS:
        if g.get("label") == "replay": sfx.add(buf, sfx.whoosh(.6), g["o0"] - .3, .4)
    for b in BIG: sfx.add(buf, sfx.thump(f=60), b, .3)
    if END: sfx.add(buf, sfx.thump(f=60), DUR - END, .4)
    buf /= np.abs(buf).max() / .9
    p = f"{WORK}/audio/mix.wav"
    with wave.open(p, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(buf, -1, 1) * 32767).astype("<i2").tobytes())
    return p

def master(video, wav, out):
    j = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(j[j.rindex("{"):j.rindex("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=192000,alimiter=limit=0.7:attack=1:release=60:level=false,aresample=48000")
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])

if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True); prep_frames()
    hits = scan_nsfw(); print(f"nsfw check: {len(hits)} flagged frames -> blur {[(round(a, 1), round(b, 1)) for a, b in BLUR]}")
    prep_voice()
    voice = build_voice()
    WORDS = prep_words(voice) if SPEC.get("subtitles", True) else []   # "subtitles": false skips Whisper and draws no subtitles
    fixes = {k.lower(): v for k, v in SPEC.get("fix_words", {}).items()}   # words Whisper mishears: {"menrobos": "menerobos"}
    for x in WORDS:
        core = re.sub(r"[^\w-]", "", x["w"]).lower()
        if core in fixes: x["w"] = x["w"].lower().replace(core, fixes[core])
    CH = chunks(WORDS)
    if SPEC.get("subtitle_style", "plain") == "plain":     # one line each: split long phrases by time, never wrap
        flat = []
        for c in CH:
            parts = S.one_line(c)
            for j, p in enumerate(parts):
                p[0]["c0"] = p[0]["t0"]
                p[0]["c1"] = parts[j + 1][0]["t0"] if j + 1 < len(parts) else c[0]["c1"]
                flat.append(p)
        CH = flat
    BIG = [x["t0"] for x in WORDS if S.is_moment(x["w"])]
    print(f"{NAME}: {DUR:.1f} s, {len(WORDS)} words, {len(CH)} subtitle phrases, moments at {[round(b, 1) for b in BIG]}")
    if "--stills" in sys.argv:
        os.makedirs(f"{WORK}/stills", exist_ok=True)
        for ts in sys.argv[sys.argv.index("--stills") + 1:]:
            im = frame(round(float(ts) * FPS)); im.save(f"{WORK}/stills/{NAME}_{ts}.jpg", quality=88); S.safe_overlay(im).save(f"{WORK}/stills/{NAME}_{ts}_safe.jpg", quality=80)
        sys.exit(0)
    vid = f"{WORK}/{NAME}_video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{S.W}x{S.H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "20", "-preset", "slow", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    with Pool(int(os.environ.get("WORKERS", 4))) as p:
        for im in p.imap(frame, range(int(DUR * FPS)), chunksize=6): ff.stdin.write(im.tobytes())
    ff.stdin.close(); ff.wait()
    master(vid, mix(build_voice(with_bg=True)), f"{WORK}/{NAME}.mp4"); os.remove(vid); print(f"{WORK}/{NAME}.mp4")
