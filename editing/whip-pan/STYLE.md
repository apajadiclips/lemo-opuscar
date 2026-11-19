# Whip-pan · Libas kamera

**What it is:** the camera pans so fast that the image smears, and the smear hides the change to a new place or time.

## Invariants
- **Pan duration 0.25–0.35 s**, eased in and out (`eio`). The new scene is centred and still when the pan ends.
- **Real motion blur:** average 6–10 sub-frames over a 1/48 s shutter along the pan. No blur filter on a still frame.
- **The sound leads the picture (J-cut):** the whoosh starts 0.1–0.2 s before the pan, with a low thump as it lands.
- **Same direction** for consecutive whips, so the world reads as one continuous space.
- **Each destination is different at a glance** (colour field and layout), with the subject in the same screen position, so the eye stays put.
- The landing falls on a beat.

## Build
- Lay the scenes side by side on one strip (`ox = i · W − camX`); `camX(t)` is a sum of eased steps.
- Blur: `for k in 0..7: alpha = 1/(k+1); draw(camX(t − shutter · k/7))`; this gives the running average.

## Pitfalls
- Blank frames or a gap between the scenes in the middle of the pan.
- A whoosh that starts on the cut instead of before it.
