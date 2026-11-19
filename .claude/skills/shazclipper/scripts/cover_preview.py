"""Preview only the cover of one or more clips, for the user to approve before the full render.
Usage: cover_preview.py spec1.json [spec2.json ...] [--sheet out.jpg]
Per spec: <work>/<name>_cover.jpg (the cover at ~0.6 s) and <work>/<name>_cover.mp4 (the whole cover with its voice).
--sheet also lays all covers side by side in one image."""
import importlib.util, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
sheet = sys.argv[sys.argv.index("--sheet") + 1] if "--sheet" in sys.argv else None
if sheet in args: args.remove(sheet)
outs = []
for spec in args:
    sys.argv = [os.path.join(HERE, "make_clip.py"), spec]
    m = importlib.util.spec_from_file_location(f"mc_{len(outs)}", sys.argv[0]); mc = importlib.util.module_from_spec(m); m.loader.exec_module(mc)
    assert mc.COVER, f"{spec}: no cover block"
    os.makedirs(f"{mc.WORK}/frames", exist_ok=True)
    if not os.path.exists(f"{mc.WORK}/frames/cover.jpg"):
        mc.run(["ffmpeg", "-v", "error", "-y", "-ss", str(mc.COVER["frame"]), "-i", mc.SPEC["source"], "-frames:v", "1", "-vf", mc.ENHANCE, "-q:v", "2", f"{mc.WORK}/frames/cover.jpg"])
    still = mc.cover_frame(min(.6, mc.COVER_DUR * .6)); jpg = f"{mc.WORK}/{mc.NAME}_cover.jpg"; still.save(jpg, quality=90)
    # the cover as a short video with its voice and the frame-0 hit
    vid, wav, mp4 = f"{mc.WORK}/cover_v.mp4", f"{mc.WORK}/audio/cover_mix.wav", f"{mc.WORK}/{mc.NAME}_cover.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{mc.S.W}x{mc.S.H}", "-r", str(mc.FPS), "-i", "-",
                           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    for n in range(int((mc.COVER_DUR + .4) * mc.FPS)): ff.stdin.write(mc.cover_frame(min(n / mc.FPS, mc.COVER_DUR - 1e-3)).tobytes())
    ff.stdin.close(); ff.wait()
    buf = np.zeros((int((mc.COVER_DUR + .4) * 48000), 2)); mc.sfx.add(buf, mc.sfx.thump(f=55), 0.0, .55)
    tts = mc.read_wav(f"{mc.WORK}/audio/cover_tts.wav"); n = min(len(tts), len(buf) - 2400); buf[2400:2400 + n] += tts[:n] * 1.6
    buf /= np.abs(buf).max() / .9
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(buf, -1, 1) * 32767).astype("<i2").tobytes())
    mc.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", wav, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5", "-c:a", "aac", "-b:a", "192k", "-shortest", mp4]); os.remove(vid)
    say = mc.COVER.get("say") or " ".join(mc.COVER.get("lines", []))
    print(f"{mc.NAME}: cover {mc.COVER_DUR:.2f} s, voice '{say}' -> {jpg}, {mp4}")
    outs.append((jpg, mc.NAME, say, mc.COVER_DUR))
if sheet and outs:
    th = [Image.open(j).resize((360, 640)) for j, *_ in outs]
    S = Image.new("RGB", (len(th) * 375 + 15, 790), (18, 18, 22)); d = ImageDraw.Draw(S)
    f1 = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf", 24); f2 = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 19)
    for i, (im, (_, name, say, dur)) in enumerate(zip(th, outs)):
        x = 15 + i * 375; S.paste(im, (x, 20))
        d.text((x, 674), f"{name.split('_')[0].upper()}  ·  {dur:.1f} s", font=f1, fill=(150, 255, 160))
        line, y = "Suara: ", 708                            # wrap the voice line to the thumbnail width
        for wd in f'"{say}"'.split():
            if d.textlength(line + wd, font=f2) > 350: d.text((x, y), line, font=f2, fill=(225, 225, 230)); line, y = "", y + 24
            line += wd + " "
        d.text((x, y), line, font=f2, fill=(225, 225, 230))
    S.save(sheet, quality=90); print("sheet:", sheet)
