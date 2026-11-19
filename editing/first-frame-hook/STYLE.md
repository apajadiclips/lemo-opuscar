# First-frame hook · Hook frame pertama

**What it is:** the opening is built to stop the scroll. Frame 0 is already full: the subject is big, the promise or question is on screen, and the first sound is one of the loudest in the film.

## Invariants
- **Frame 0 is complete.** No fade from black, no logo, no slow build. Any frame grab of t = 0 must work as a thumbnail.
- **Subject fills ≥ 60 % of the frame** for the first 0.5–1 s (an extreme close-up or a punch-in), then pulls out to show context.
- **One line of text, ≤ 3 words per line**, readable at phone size (≥ 100 px on 1080 wide), placed clear of the subject. Hold it for its read time (letters ÷ 15 + 1.5 s).
- **Sound at 0.0:** an impact or sub drop. The groove starts on a beat after it (0.5–1.0 s), not with it.
- **Two punches in the first second** (zoom 1.0 → 1.15 with a decaying shake), on beats 0 and 1.
- The pull-out reveals what the video is about by 2–2.5 s.

## Build
- Camera zoom about the subject's centre: `screen = c + (p − c) · z`; punch z by beats, ease out (cubic) on the pull-out.
- Shake: `amp · e^(−(t mod beat) / 0.12)`, only during the punches.
- A ring or flash on the punch frames gives a second visual hit without a cut.

## Pitfalls
- Text under 100 px or more than one sentence: nobody reads it in the first second.
- Starting with the groove: the impact gets lost. Leave a gap of half a beat.
- A thumbnail-worthy frame that comes at 1.5 s instead of 0.
