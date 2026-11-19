# Match cut · Potongan sepadan

**What it is:** a cut between two different worlds that share a shape, motion or idea, placed in the same spot on screen.

## Invariants
- **Same position, same size, same silhouette** across the cut: the matched shape sits on identical screen coordinates (±2 %).
- **Everything else changes:** colour, texture, setting, scale of the world. The more different the worlds, the stronger the match.
- **Hold each world ≥ 1.5 s** so the viewer recognises it before the next cut.
- **Cut on a beat**, with a sound change that tells the worlds apart (a bounce → a warm pad → vinyl crackle). Letting one world's sound run over into the next (L-cut) binds them.
- A chain of 2–3 matches, then a release: the shape shrinks, stops or turns into the next section.
- At most one short flash on the cut (≤ 2 frames): the match should carry it, not the flash.

## Build
- Define the matched shape once (centre, radius) and draw every world around it.
- A slow push across the chain (1.00 → 1.04) keeps it alive without moving the match.

## Pitfalls
- The shape moves a little between worlds: the match reads as a mistake.
- Worlds that look alike: then it's just a cut.
