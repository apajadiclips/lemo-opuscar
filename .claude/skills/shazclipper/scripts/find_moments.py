"""Rank clip moments in a stream: loudness above his own running level + reaction words + how much he talks.
Usage: find_moments.py <audio16k.wav> <transcript.jsonl> <out.json> [--top 40]
Writes candidates [{t, a, b, score, loud, react, talk, text}] (t = the moment; a..b = a 45-s window around it)."""
import argparse, json, re, wave
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.ndimage import median_filter, uniform_filter1d
ap = argparse.ArgumentParser(); ap.add_argument("wav"); ap.add_argument("transcript"); ap.add_argument("out"); ap.add_argument("--top", type=int, default=40); a = ap.parse_args()
REACT = (r"anjir|anjing|anjay|astaga|astagfirullah|ya ?allah|gila|wkwk|haha|waduh|aduh|buset|bangsat|kampret|mampus|mati|bjir|njir|"
         r"woi|woy|lho|loh|apaan|serius|gak mungkin|tolong|lari|kabur|polisi|bunuh|rampok|maling|curi|ledak|tabrak|"
         r"alamak|aduhai|weh|wey|mak aih|celaka|bodoh|gilo|haih")                      # Indonesian + Malay
w = wave.open(a.wav); n = w.getnframes(); sr = w.getframerate(); hop = sr // 2; vals = []
sos = butter(4, [250, 3500], "band", fs=sr, output="sos")                         # the voice band
for s in range(0, n, sr * 600):
    w.setpos(s); x = sosfilt(sos, np.frombuffer(w.readframes(min(sr * 600, n - s)), dtype="<i2").astype(np.float32) / 32768)
    vals += [np.sqrt((x[i:i + hop] ** 2).mean()) for i in range(0, len(x) - hop + 1, hop)]
db = 20 * np.log10(np.array(vals) + 1e-9); T = np.arange(len(db)) * .5
EX = uniform_filter1d(db - median_filter(db, size=121), 4)                        # louder than his last minute
SEGS = [json.loads(l) for l in open(a.transcript)]
def seg_in(x, y): return [s for s in SEGS if s["t1"] > x and s["t0"] < y]
cands = []
for c in np.arange(60, T[-1] - 30, 5.0):
    x, y = c - 35, c + 10; m = (T >= c - 3) & (T <= c + 3); loud = float(EX[m].max()) if m.any() else 0
    ss = seg_in(x, y); text = " ".join(s["text"] for s in ss).lower()
    react = len(re.findall(REACT, text)); talk = sum(min(s["t1"], y) - max(s["t0"], x) for s in ss) / (y - x)
    cands.append(dict(t=float(c), a=float(x), b=float(y), loud=round(loud, 1), react=react, talk=round(talk, 2), score=round(loud + react * 2.5 + talk * 6, 1)))
cands.sort(key=lambda k: -k["score"]); picks = []
for k in cands:
    if all(abs(k["t"] - p["t"]) > 90 for p in picks): picks.append(k)
    if len(picks) >= a.top: break
picks.sort(key=lambda k: -k["score"])
for p in picks: p["text"] = " / ".join(s["text"] for s in seg_in(p["a"], p["b"]))
json.dump(picks, open(a.out, "w"), ensure_ascii=False, indent=1)
fmt = lambda t: f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}"
for i, p in enumerate(picks, 1): print(f"#{i:02d} {fmt(p['t'])} score {p['score']:5.1f}  {p['text'][:160]}")
