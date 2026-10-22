# odv Grotesk

Schibsted Grotesk extended with Greek and maths characters, for odv.hu and LaTeX.

[Schibsted Grotesk](https://github.com/schibsted/schibsted-grotesk) covers Latin but has only eight Greek letters (Δ Π Σ Ω α β μ π) and a partial set of maths symbols.
That is enough for a website, not for technical writing with ζ, χ, κ and ∇ in it.
odv Grotesk adds the missing characters in the same style and leaves everything else as it is.
It is an independent modified version under the Open Font License, not affiliated with Schibsted.

## What is added

| | |
|---|---|
| Greek capitals | Γ Θ Λ Ξ Φ Ψ, plus Α Β Ε Ζ Η Ι Κ Μ Ν Ο Ρ Τ Υ Χ (same shapes as the Latin letters) |
| Greek lowercase | γ δ ε ζ η θ ι κ λ ν ο ρ σ τ υ φ χ ψ ω, plus ϵ and ϕ (the symbol forms LaTeX uses for `\epsilon` and `\phi`) |
| Maths | ∇ ∈ ∀ ∃ ∓ ⋅ ∼ ⊥ |

Styles: Regular, Medium, Bold and their italics (Schibsted's static weights, not the variable font).
Still missing: ξ, ς and the rest of the maths symbols; they come when a text needs them.

## How it is made

The new glyphs are drawn by [`scripts/draw.py`](scripts/draw.py) from recipes rather than by hand:
κ is k cut at the x-height, ρ is the bowl of p with a stem, ∇ is Δ turned over, and letters with no Latin relative (ζ, λ, ψ, Ψ…) are stroked along a centre line.
Stem widths, heights and sidebearings are measured from each style of the font, so the same recipes produce every weight and the italic.
The result goes into `sources/<style>.ufo`, which opens in any font editor.
A glyph finished by hand goes into `sources/hand-edited.txt`, and the script leaves it alone from then on.

[`scripts/build.py`](scripts/build.py) downloads the pinned Schibsted Grotesk release, merges the glyphs from the UFOs, renames the family and writes:

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
