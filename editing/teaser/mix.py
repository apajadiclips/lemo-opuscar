"""Score + foley + mix for the teaser -> out/mix.wav. Reads events.json (window.EV) so sound and picture share one timeline."""
import json, os, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get("LIB", os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.join(LIB, "core", "audio"))
import sfx
from sfx import SR, t_, env_exp, lp, hp, bp, noise, norm, add

BPM, BEAT, DUR = 120, 0.5, 30.0
N = int(DUR * SR)
ev = json.load(open(os.path.join(HERE, "events.json")))["ev"]
rng = np.random.default_rng(3)

def st(): return np.zeros((N, 2))
def kick(v=1):
    d = .45; tt = t_(d); f = 48 + 110 * np.exp(-tt / .035)
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(d, .16) + hp(noise(d), 3000) * env_exp(d, .003) * .3) * v
def clap(v=1):
    d = .25; n = bp(noise(d), 900, 4000); e = env_exp(d, .05)
    for o in (.0, .011, .022): e = e + np.roll(env_exp(d, .004), int(o * SR)) * .7
    return norm(n * e) * v
def hat(v=1, d=.05): return norm(hp(noise(d), 7000) * env_exp(d, .012)) * v
def saw(f, d):
    tt = t_(d); return 2 * ((tt * f) % 1) - 1
def stab(freqs, d=.22, v=1):
    x = sum(saw(f, d) + saw(f * 1.006, d) for f in freqs); x = lp(x, 2600) * env_exp(d, .07)
    return norm(x) * v
def bass(f, d=.24, v=1):
    tt = t_(d); x = np.sin(2 * np.pi * f * tt) + .35 * np.sin(4 * np.pi * f * tt)
    return norm(x * np.minimum(1, tt / .005) * env_exp(d, .12)) * v
def sub_drop(d=1.0, v=1):
    tt = t_(d); f = 90 * np.exp(-tt * 1.6) + 30
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(d, .45)) * v
def boom(v=1):
    return norm(sub_drop(1.6) + lp(noise(1.6), 400) * env_exp(1.6, .3) * .6 + hp(noise(1.6), 2000) * env_exp(1.6, .02) * .4) * v
def swell(d=1.4, v=1):   # warm pad for the sun
    tt = t_(d); x = sum(np.sin(2 * np.pi * f * tt) for f in (220, 277.2, 329.6, 440))
    return norm(x * np.sin(np.pi * tt / d) ** 2) * v
def crackle(d):
    x = np.zeros(int(d * SR)); idx = rng.integers(0, len(x), int(d * 90)); x[idx] = rng.uniform(-1, 1, len(idx))
    return lp(hp(x, 900), 6000) * .9 + lp(noise(d), 300) * .03

# chords per bar (2 s): Am F C G
CH = [(220, 261.6, 329.6), (174.6, 220, 261.6), (196, 261.6, 329.6), (196, 246.9, 293.7)]
RT = [55, 43.65, 65.4, 49]

drums, music = st(), st()
for i in range(int(DUR / (BEAT / 2))):
    t = i * BEAT / 2
    beat_i, bar = i // 2, int(t // 2)
    on = (1.0 <= t < 24.3)                    # the groove runs from 1.0 s to the silence at 24.3
    if not on: continue
    if i % 2 == 0: add(drums, kick(), t, .95)
    if i % 2 == 1: add(drums, hat(), t, .22, .3)
    if t >= 5 and i % 4 == 2: add(drums, clap(), t, .5, -.1)
    if t >= 3 and i % 2 == 1: add(music, bass(RT[bar % 4]), t, .55)
    if t >= 5 and i % 2 == 1: add(music, stab(CH[bar % 4]), t, .22, (-.3, .3)[i % 4 == 1])
# title: kicks on every word, final hit
for e in ev:
    if e["type"] == "word": add(drums, kick(), e["t"], 1.0); add(music, stab(CH[0], .5), e["t"], .3)
    if e["type"] == "hit":
        add(drums, kick(), e["t"], 1.0); add(drums, sfx.crash(), e["t"], .45)
        add(music, stab(CH[0], 1.0) * env_exp(1.0, .4), e["t"], .4)

score = drums + music
# speed-ramp: blockwise low-pass + dip during the slow motion (near-silence 1), back on the slam at 13.0
def ramp_cut(t):
    if t < 11.3 or t >= 13.2: return None
    if t < 11.6: return 8000 * (1 - (t - 11.3) / .3) + 250
    if t < 12.9: return 250
    return 250 + 8000 * (t - 12.9) / .3
blk = 1200
for s in range(int(11.3 * SR), int(13.2 * SR), blk):
    fc = ramp_cut(s / SR)
    for c in (0, 1):
        seg = score[max(0, s - 4000):s + blk, c]
        score[s:s + blk, c] = lp(seg, fc)[-blk:] * (0.35 if fc < 1000 else 1)

fx = st()
for e in ev:
    t, ty = e["t"], e["type"]
    if ty == "impact": add(fx, boom(), t, 1.0); add(fx, sfx.crash(), t, .35)
    elif ty == "punch": add(fx, sfx.thump(f=60), t, .9); add(fx, hat(1, .12), t, .4)
    elif ty == "pullout": add(fx, sfx.whoosh(.9), t, .35)
    elif ty == "bounce": add(fx, sfx.thump(f=95), t, .36); add(fx, sfx.pop(), t, .11)
    elif ty == "cut": add(fx, sfx.click(1.4), t, .25)
    elif ty == "roll": add(fx, lp(noise(5.0), 500) * np.sin(np.pi * t_(5.0) / 5.0) * .5, t, .35)
    elif ty == "slow_in":
        for k in range(3): add(fx, sfx.heartbeat(), t + .1 + k * .45, .9)
        add(fx, sfx.whoosh(.5), t - .2, .3)
    elif ty == "slow_out": add(fx, kick(), t, .9); add(fx, sfx.whoosh(.35), t - .1, .5)
    elif ty == "whoosh": add(fx, sfx.whoosh(.45), t, .9, -.6); add(fx, sfx.thump(f=80), t + .3, .5)   # J-cut: sound leads the whip
    elif ty == "sun": add(fx, swell(1.5), t, .5); add(fx, sfx.thump(f=50), t, .5)
    elif ty == "vinyl": add(fx, crackle(1.8 + .7), t, .5); add(fx, sfx.click(.6), t, .4)   # L-cut: crackle runs into the silence
    elif ty == "stop":
        tt = t_(.6); f = 300 * (1 - tt / .6) + 20                                          # record stop
        add(fx, norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 - tt / .6)) , t, .25)
    elif ty == "boom": add(fx, boom(), t, 1.0)
    elif ty == "word": add(fx, sfx.thump(f=70), t, .5)

room = st(); r = lp(noise(DUR), 220) * .25 + hp(lp(noise(DUR), 3000), 800) * .02
room[:, 0] = r; room[:, 1] = np.roll(r, 900)

mix = score * .8 + fx * .9 + room * .5
# duck the score briefly under the big hits
duck = np.ones(N)
for e in ev:
    if e["type"] in ("impact", "boom"):
        s = int(e["t"] * SR); n = int(.6 * SR); duck[s:s + n] = np.minimum(duck[s:s + n], np.linspace(.5, 1, n)[:len(duck[s:s + n])])
mix = score * .8 * duck[:, None] + fx * .9 + room * .5
mix /= np.abs(mix).max() / .9
mix = np.stack([sfx.limit(mix[:, c], .95) for c in (0, 1)], 1)
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
with wave.open(os.path.join(HERE, "out", "mix.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
print("out/mix.wav", DUR, "s")
