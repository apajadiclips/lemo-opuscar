"""Keep the streamer's voice, drop the game sound / music ("back sound"): Demucs htdemucs vocals + a soft gate.
Runs in the Demucs venv (see SKILL.md): $DEMUCS_PY separate_voice.py <in.wav> <voice.wav> [--gate -42]"""
import argparse
import numpy as np, soundfile as sf, torch
import torchaudio.functional as AF
from demucs.pretrained import get_model
from demucs.apply import apply_model
from scipy.ndimage import uniform_filter1d, maximum_filter1d
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--gate", type=float, default=-42); a = ap.parse_args()
m = get_model("htdemucs"); m.eval()
x, sr = sf.read(a.inp, always_2d=True)
if x.shape[1] == 1: x = np.repeat(x, 2, 1)
t = torch.tensor(x.T, dtype=torch.float32); t44 = AF.resample(t, sr, m.samplerate)
ref = t44.mean(0); mu, sd = ref.mean(), ref.std() + 1e-8
with torch.no_grad(): out = apply_model(m, ((t44 - mu) / sd)[None], device="cpu", shifts=1, overlap=.25)[0] * sd + mu
v = AF.resample(out[m.sources.index("vocals")], m.samplerate, sr).numpy().T
# soft gate: between phrases, pull the leftover bleed down ~16 dB
env = np.sqrt(uniform_filter1d((v ** 2).mean(1), int(.03 * sr)))
open_ = maximum_filter1d((20 * np.log10(env + 1e-9) > a.gate).astype(float), int(.15 * sr))
v *= uniform_filter1d(np.where(open_ > 0, 1.0, .16), int(.04 * sr))[:, None]
sf.write(a.out, v, sr)
bg = AF.resample(sum(out[i] for i, n in enumerate(m.sources) if n != "vocals"), m.samplerate, sr).numpy().T
sf.write(a.out.replace(".wav", "_bg.wav"), bg, sr)            # the game's own sound, mixed back in quietly by make_clip
db = lambda s: 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9)
print(f"voice {db(v):.1f} dB, removed {db(x - v[:len(x)]):.1f} dB of other sound -> {a.out}")
