# Speed ramp · Laju-perlahan-laju

**What it is:** playback speed changes inside one shot: fast → slow motion → fast, to stretch one moment.

## Invariants
- **One stretched moment per ramp.** The slow part sits on the most important instant (contact, peak, eye contact).
- **Speed curve:** fast (2–4×) → ease down in 0.2–0.4 s → slow (0.1–0.25×) for 1–1.5 s → ease up in 0.2–0.4 s → fast. Never a linear ramp.
- **Position is the integral of speed**, not time × speed: `x(t) = ∫ speed(u) du`. Otherwise the subject jumps when the speed changes.
- **Sound follows the speed:** music low-passed (≈ 250 Hz) and dipped during the slow part, a heartbeat or breath, and a hit when the speed comes back. This is one of the film's near-silences.
- **Motion cues show the speed:** streaks and trails scale with speed; dust or particles hang in the air when slow.
- Optional grade during the slow part: a cool overlay and letterbox bars, gone when speed returns.

## Build
- `speed(t)` as a piecewise function with eased transitions; integrate numerically with a fixed step (1/480 s) from the start of the shot, so any frame renders alone.
- Show the speed (a 3× / 0.1× readout) only in teaching demos.

## Pitfalls
- Ramping on a moment that isn't interesting.
- Music that keeps going at full volume through the slow motion: the ramp loses its weight.
