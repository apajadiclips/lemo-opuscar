# Editing styles · Gaya suntingan

A library of **editing** styles: how shots are cut, timed and joined, not how they look. Pair any of them with a visual style from [`styles/`](../styles/README.md) and with shots from the `openhiggs-angles` skill (many angles + camera moves from one image).

Each style has a `STYLE.md`: what it is, its invariants (timing, sound, framing), how to build it in code, and its pitfalls. Rules are written for 24 fps and 120 BPM unless the style says otherwise; convert with beat = 60 / BPM.

| # | Style | Gaya | In one line |
|---|---|---|---|
| 01 | [First-frame hook](first-frame-hook/STYLE.md) | Hook frame pertama | Frame 0 is already the most striking image; no fade-in |
| 02 | [Beat-sync](beat-sync/STYLE.md) | Potong ikut beat | Cuts and landings fall on the beat grid |
| 03 | [Speed ramp](speed-ramp/STYLE.md) | Laju-perlahan-laju | One moment is stretched inside a fast shot |
| 04 | [Whip-pan](whip-pan/STYLE.md) | Libas kamera | A fast pan's blur becomes the cut to a new scene |
| 05 | [Match cut](match-cut/STYLE.md) | Potongan sepadan | The same shape or motion carries across two worlds |

Demo: [`teaser/`](teaser/), a 30-second 9:16 teaser that runs all five on one hero (an orange ball). Build it with `sh editing/teaser/build.sh` after `setup.sh deps`.

The style names are common teaching labels. The references that inspired the list teach grammar only: no clip, shot, character or logo from them is used here.
