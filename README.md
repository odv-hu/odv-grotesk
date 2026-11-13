# odv Grotesk

Schibsted Grotesk extended with Greek and maths characters, for odv.hu and LaTeX.

[Schibsted Grotesk](https://github.com/schibsted/schibsted-grotesk) covers Latin but has only eight Greek letters (Δ Π Σ Ω α β μ π) and a partial set of maths symbols.
That is enough for a website, not for technical writing with ζ, χ, κ and ∇ in it.
odv Grotesk adds the missing characters in the same style, and reshapes a few letters (below); everything else is as it was.
It is an independent modified version under the Open Font License, not affiliated with Schibsted.

## What is added

| | |
|---|---|
| Greek capitals | Γ Θ Λ Ξ Φ Ψ, plus Α Β Ε Ζ Η Ι Κ Μ Ν Ο Ρ Τ Υ Χ (same shapes as the Latin letters) |
| Greek lowercase | γ δ ε ζ η θ ι κ λ ν ο ρ σ τ υ φ χ ψ ω, plus ϵ and ϕ (the symbol forms LaTeX uses for `\epsilon` and `\phi`) |
| Maths | ∇ ∈ ∀ ∃ ∓ ⋅ ∼ ⊥ |

Styles: Regular, Medium, Bold and their italics (Schibsted's static weights, not the variable font).
Still missing: ξ, ς and the rest of the maths symbols; they come when a text needs them.

## What is changed

| | |
|---|---|
| I | no serifs: a plain stem, spaced like the stem of H |
| e | the end of the lower stroke is cut level, so the opening is a horizontal slot |
| a | the top of the bowl runs flat out from the stem and turns down in a tighter corner (upright styles; the italic a is single-storey and unchanged) |
| c | both terminals cut level |
| i j | square dot, top level with the top of l, a little wider than the stem (relatively less in heavier weights); it is the same glyph as the dot accent and the dieresis, so ä ö ü ż İ turn square too |
| i | stem a touch heavier than n's, so it doesn't read thin next to round letters |
| p | counter moved right so stem and bowl are equally thick, which widens the join |
| f t (italics) | the upright f and t slanted, instead of the cursive forms |
| contrast | Medium and Bold (and their italics) have thinner verticals, so horizontals no longer look thin next to the stems; Bold now matches Akkurat Pro Bold in stem weight and contrast |

Accented forms (Í, é, ą, ç…), IJ, the fi ligatures and Greek Ι are built from these glyphs and follow them.
The changes are recipes in [`scripts/modify.py`](scripts/modify.py), applied to each style at build time.

## Download

Built fonts are on the [Releases page](https://github.com/odv-hu/odv-grotesk/releases), one release per version: `odvGrotesk-*.woff2` for the web, `odvGrotesk-*.ttf` for macOS and LuaLaTeX, or a zip with both.
They are not kept in git.

To release a version: set `VERSION` in `scripts/build.py`, add its entry to `FONTLOG.txt`, commit, then push the tag `v<version>`.
[`.github/workflows/release.yml`](.github/workflows/release.yml) builds every style from the committed UFOs and publishes the release with the FONTLOG entry as notes.
It never replaces an existing release.

## How it is made

The new glyphs are drawn by [`scripts/draw.py`](scripts/draw.py) from recipes rather than by hand:
κ is k cut at the x-height, ρ is the bowl of p with a stem, ∇ is Δ turned over, and letters with no Latin relative (ζ, λ, ψ, Ψ…) are stroked along a centre line.
Stem widths, heights and sidebearings are measured from each style of the font, so the same recipes produce every weight and the italic.
The result goes into `sources/<style>.ufo`, which opens in any font editor.
A glyph finished by hand goes into `sources/hand-edited.txt`, and the script leaves it alone from then on.

The Greek letters are kerned like Latin letters with the same sides: [`scripts/kern.py`](scripts/kern.py) puts Τ in T's kerning classes, Λ in A's, Γ in E's on the left and T's on the right, and so on, so `ΓΑΤΑ` sits like `AVATAR`.

[`scripts/build.py`](scripts/build.py) downloads the pinned Schibsted Grotesk release, merges the glyphs from the UFOs, adds the Greek kerning, renames the family and writes:

- `fonts/ttf/odvGrotesk-*.ttf` for macOS and LuaLaTeX,
- `fonts/webfonts/odvGrotesk-*.woff2` for the website.

```sh
pip install -r requirements.txt
python3 scripts/build.py              # draw + build all styles
python3 scripts/build.py --no-draw    # build from the UFOs as they are (after hand edits)
python3 scripts/build.py Regular      # one style
```

## Maths in LaTeX

odv Grotesk is a text font, not a maths font: it has no maths spacing, italic correction or script sizes, so equations stay in Computer Modern.
[odv-latex](https://github.com/odv-hu/odv-latex) (`odv.sty`) sets text in odv Grotesk and maths in Computer Modern enlarged to 112 %.
The Greek letters here are for running text, Keynote and the website.
[`preview/preview.tex`](preview/preview.tex) shows the glyphs; its equations still use an earlier experiment (Fira Math with odv Grotesk letters) that was dropped.

## Licence

SIL Open Font License 1.1, see [OFL.txt](OFL.txt); changes are logged in [FONTLOG.txt](FONTLOG.txt).
The original design is © 2023 The Schibsted-Grotesk Project Authors.
