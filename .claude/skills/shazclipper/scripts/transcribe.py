"""Transcribe a long stream in 10-minute chunks (constant memory, progress, resumable).
Usage: transcribe.py <audio16k.wav> <out.jsonl> [--model small] [--lang id]
Make the wav first: ffmpeg -i vod.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio16k.wav
Set HF_HUB_DISABLE_XET=1 (the Xet download path needs an extra host). Lines: {t0, t1, text, lp}."""
import argparse, json, os, time, wave
import numpy as np
from faster_whisper import WhisperModel
ap = argparse.ArgumentParser(); ap.add_argument("wav"); ap.add_argument("out"); ap.add_argument("--model", default="small"); ap.add_argument("--lang", default="id")
ap.add_argument("--threads", type=int, default=3); a = ap.parse_args()
w = wave.open(a.wav); n = w.getnframes(); sr = w.getframerate(); assert sr == 16000, "need 16 kHz mono"
done = 0.0
if os.path.exists(a.out):                              # resume after the last full chunk
    rows = [json.loads(l) for l in open(a.out)]; done = (int(rows[-1]["t1"] // 600)) * 600 if rows else 0
    with open(a.out, "w") as f: f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows if r["t0"] < done)
m = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=a.threads)
out = open(a.out, "a"); t0 = time.time(); CH = 600
for start in range(int(done * sr), n, CH * sr):
    w.setpos(start); x = np.frombuffer(w.readframes(min(CH * sr, n - start)), dtype="<i2").astype(np.float32) / 32768
    segs, _ = m.transcribe(x, language=a.lang, vad_filter=True, beam_size=1, condition_on_previous_text=False)
    off = start / sr
    for s in segs: out.write(json.dumps(dict(t0=round(off + s.start, 2), t1=round(off + s.end, 2), text=s.text.strip(), lp=round(s.avg_logprob, 2)), ensure_ascii=False) + "\n")
    out.flush(); print(f"{(start / sr + CH) / 60:6.1f} / {n / sr / 60:.1f} min, {time.time() - t0:5.0f} s", flush=True)
print("DONE", flush=True)
