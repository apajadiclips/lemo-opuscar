# Beat-sync · Potong ikut beat

**What it is:** cuts, landings and reveals are timed to the music grid, so the edit feels like part of the track.

## Invariants
- **The music grid comes first.** Choose the BPM, write the cue map, then animate. Every cut time is `t0 + n · beat` (or a half or quarter beat).
- **Cut on the kick**, never between beats. Accent cuts (a change of framing or colour) go on the downbeat of a bar.
- **Change something real at every cut:** framing (wide / low / top / close), colour field, or angle. Two cuts to the same framing read as a glitch.
- **Physical actions land on the beat too:** a bounce peaks at mid-beat and lands on the beat (`h = 1 − (2·phase − 1)²`).
- **No more than 6–8 consecutive cuts on every beat**, then hold for a bar. Cutting on every beat for long tires the eye.
- A 2–3-frame white flash (≤ 55 % alpha) on accent cuts; a short tick or click in the foley.

## Build
- One `timeline` (BPM, sections, hit list) shared by the picture, the score and the mixer. Export `window.EV` and let the mixer place sounds from it.
- Check: every cut time modulo the beat should be 0 ms.

## Pitfalls
- Cuts that drift by a frame or two: at 24 fps a beat at 120 BPM is exactly 12 frames, so prefer BPMs that divide well (120, 144, 96).
- Text that changes on every cut: keep labels on one plate across the cuts.
