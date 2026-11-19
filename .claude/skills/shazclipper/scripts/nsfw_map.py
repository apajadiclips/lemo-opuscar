"""Map sexual/nudity content across a whole VOD: keyframes only (fast), NudeNet on each.
Usage: nsfw_map.py <vod.mp4> <out.json> [keyframe_dir]   ->  [{t (VOD seconds), classes, score}]
Keyframe file names are frame numbers at the stream's frame rate (-frame_pts), so t = name / fps."""
import json, os, subprocess, sys
KF = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(sys.argv[2])), "kf")
os.makedirs(KF, exist_ok=True)
from nudenet import NudeDetector
CL = {"FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", "BUTTOCKS_EXPOSED", "ANUS_EXPOSED"}
if not os.path.exists(KF + "/done"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-skip_frame", "nokey", "-i", sys.argv[1], "-vf", "scale=960:-2", "-fps_mode", "vfr",
                    "-frame_pts", "1", "-q:v", "4", KF + "/%08d.jpg"], check=True)
    open(KF + "/done", "w").close()
num, den = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", sys.argv[1]], capture_output=True, text=True).stdout.strip().split("/")
FPS = float(num) / float(den)
det = NudeDetector(); hits = []; fs = sorted(f for f in os.listdir(KF) if f.endswith(".jpg"))
for i, f in enumerate(fs):
    found = [d for d in det.detect(f"{KF}/{f}") if d["class"] in CL and d["score"] >= .45]
    if found: hits.append(dict(t=round(int(f[:-4]) / FPS, 2), classes=sorted({d["class"] for d in found}), score=round(max(d["score"] for d in found), 2)))
    if i % 500 == 0: print(f"{i}/{len(fs)}", flush=True)
json.dump(hits, open(sys.argv[2], "w"), indent=1); print("DONE", len(fs), "keyframes,", len(hits), "flagged", flush=True)
