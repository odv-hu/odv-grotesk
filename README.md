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
| Greek lowercase | γ δ ε ζ η θ ι κ λ ν ξ ο ρ σ ς τ υ φ χ ψ ω, plus ϵ and ϕ (the symbol forms LaTeX uses for `\epsilon` and `\phi`) |
| Greek accents | ά έ ή ί ό ύ ώ ϊ ϋ ΐ ΰ, Ά Έ Ή Ί Ό Ύ Ώ Ϊ Ϋ, ΄ ΅ (monotonic); combining accents sit on every Greek letter |
| Maths | ∇ ∈ ∉ ∀ ∃ ∓ ⋅ ∼ ⊥ ∩ ∪ ⊂ ⊃ ⊆ ⊇ ∧ ∨ ⇒ ⇔ ∝ ∥ ∠ △ |

Styles: Regular, Medium, Bold and their italics (Schibsted's static weights, not the variable font).
Still missing: the rest of the maths symbols; they come when a text needs them.

## What is changed

| | |
|---|---|
| I | no serifs: a plain stem, spaced like the stem of H |
| e | the end of the lower stroke is cut level, so the opening is a horizontal slot |
| a | the top of the bowl runs flat out from the stem and turns down in a corner whose curvature eases in from the flat and out into the bowl, with no point where the bend starts; the terminal at the top is cut level at the height of its tip (upright styles; the italic a is single-storey and unchanged) |
| c | both terminals cut level |
| s | both terminals cut level at the height of their inner corners, like e and c |
| i j | square dot, top level with the top of l, overhanging the stem by the same amount on each side in every weight (so relatively less in heavier weights); it is the same glyph as the dot accent and the dieresis, so ä ö ü ż İ turn square too |
| i j | stems a touch heavier than n's (4.5%), so they don't read thin next to round letters; i and j match |
| p | counter moved right so stem and bowl are equally thick, which widens the join |
| f t (italics) | the upright f and t slanted, instead of the cursive forms |
| . , ! ? | square dots, the size of i's, and a comma with a square head and a straight tail leaning left, cut level; : ; … · ŀ and the quotes ‘ ’ “ ” ‚ „ are made of them and follow |
| contrast | Medium and Bold (and their italics) have thinner verticals, so horizontals no longer look thin next to the stems: thin to thick is 0.87 in every weight, about what Schibsted drew its own Italic with. The tops and bottoms of rounds run into short smooth curves instead of the point the thinning would leave |
| z E F T Z L H | in Medium and Bold the straight bars back to Schibsted's proportion to the thinned stem (about 0.85), so these letters are not darker than the rest |
| kerning | round lowercase pairs (o b p before o d c e q) are no longer kerned apart, and z is pulled half as close to o c e s, so `pod` and `poz` sit evenly |
| curves | Schibsted's own small kinks straightened and curvature steps between quadratic pieces evened out, in every glyph; smooth points stay smooth when rounded to whole units |

Accented forms (Í, é, ą, ç…), IJ, the fi ligatures and Greek Ι are built from these glyphs and follow them.
The changes are recipes in [`scripts/modify.py`](scripts/modify.py), applied to each style at build time.

## Download

Built fonts are on the [Releases page](https://github.com/odv-hu/odv-grotesk/releases), one release per version: `odvGrotesk-*.woff2` for the web, `odvGrotesk-*.ttf` for macOS and LuaLaTeX, `odvMath-Regular.otf` / `.woff2` (the maths font, below), or a zip with all of them and their licences.
They are not kept in git.

To release a version: set `VERSION` in `scripts/build.py`, add its entry to `FONTLOG.txt`, commit, then push the tag `v<version>`.
[`.github/workflows/release.yml`](.github/workflows/release.yml) builds every style from the committed UFOs and publishes the release with the FONTLOG entry as notes.
It never replaces an existing release.

## How it is made

The new glyphs are drawn by [`scripts/draw.py`](scripts/draw.py) from recipes rather than by hand:
κ is k cut at the x-height, ρ is the bowl of p with a stem, ∇ is Δ turned over, ⇒ is → with the shaft doubled, and letters with no Latin relative (ζ, λ, ψ, Ψ…) are stroked along a centre line.
Stem widths, heights and sidebearings are measured from each style of the font, so the same recipes produce every weight and the italic.
The result goes into `sources/<style>.ufo`, which opens in any font editor.
A glyph finished by hand goes into `sources/hand-edited.txt`, and the script leaves it alone from then on.

The Greek letters are kerned like Latin letters with the same sides: [`scripts/kern.py`](scripts/kern.py) puts Τ in T's kerning classes, Λ in A's, Γ in E's on the left and T's on the right, and so on, so `ΓΑΤΑ` sits like `AVATAR`.

Accented Greek is built by [`scripts/accents.py`](scripts/accents.py): every Greek letter gets a top anchor (the Latin twin's, or centred over the top of the drawn glyph), so combining accents land on it, and the monotonic letters ά…ώ, Ά…Ώ are composites of the letter and the font's own acute and dieresis. On the capitals the tonos stands to the left; in ΐ ΰ the dots spread to let the acute stand between them.

[`scripts/build.py`](scripts/build.py) downloads the pinned Schibsted Grotesk release, merges the glyphs from the UFOs, adds the Greek kerning, renames the family and writes:

- `fonts/ttf/odvGrotesk-*.ttf` for macOS and LuaLaTeX,
- `fonts/webfonts/odvGrotesk-*.woff2` for the website.

```sh
pip install -r requirements.txt
python3 scripts/build.py              # draw + build all styles
python3 scripts/build.py --no-draw    # build from the UFOs as they are (after hand edits)
python3 scripts/build.py Regular      # one style
```

## odv Math

The equations go with odv Grotesk in Computer Modern. **odv Math** is New Computer Modern Math Book enlarged to 112 %, the size at which odv-latex sets it next to the grotesk, so Keynote and odv.hu (where it can be MathML's `math` font) get the same size from the same file at its nominal size. [`scripts/odvmath.py`](scripts/odvmath.py) downloads the pinned New Computer Modern and changes only `unitsPerEm` (1000 → 893): the outlines, metrics and `MATH` table are New Computer Modern's. It is renamed and keeps its own licence, the GUST Font License; `GUST-FONT-LICENSE.txt` and `README-odvMath.txt` come with it in the release.

## Maths in LaTeX

odv Grotesk is a text font, not a maths font: it has no maths spacing, italic correction or script sizes, so equations stay in Computer Modern.
[odv-latex](https://github.com/odv-hu/odv-latex) (`odv.sty`) sets text in odv Grotesk and maths in Computer Modern enlarged to 112 %: odv Math when it is installed, New Computer Modern Book otherwise.
The Greek letters here are for running text, Keynote and the website.
[`preview/preview.tex`](preview/preview.tex) shows the glyphs, and equations in odv Math as `odv.sty` sets them.

## Licence

SIL Open Font License 1.1, see [OFL.txt](OFL.txt); changes are logged in [FONTLOG.txt](FONTLOG.txt).
The original design is © 2023 The Schibsted-Grotesk Project Authors.
odv Math is under the GUST Font License, as New Computer Modern (© Antonis Tsolomitis, after Computer Modern by Donald E. Knuth) is.
