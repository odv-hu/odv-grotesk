"""TrueType hinting for odv Grotesk with ttfautohint (#20).

    python3 scripts/build.py --hint                  # build with hinted .ttf files
    python3 scripts/hint.py fonts/ttf/*.ttf -o out/  # hint already built fonts

0.3.2 removed the hints from every style (#6): Schibsted's hints only fitted its untouched
glyphs, and hinted and unhinted letters side by side looked worse than none. Hinting the
finished font in one pass gives every glyph, Schibsted's, the reshaped ones and the Greek,
hints from the same analysis. macOS ignores hints, as do high-DPI screens, print and PDF;
they matter on Windows at standard resolution.

The options are the same for all six styles, so Medium and Bold stay in step with Regular.
Only the .ttf files get hints: Windows browsers use only the vertical ones, and the
webfonts are larger with them (decision pending in #20).
"""
import argparse
import io
from pathlib import Path

from fontTools.ttLib import TTFont

# ttfautohint's defaults, written out so a change is deliberate and applies to every style.
OPTIONS = dict(
    hinting_range_min=8,          # ppem from which hinting starts
    hinting_range_max=50,         # ppem up to which it is applied
    hinting_limit=200,            # above this ppem, no hinting at all
    increase_x_height=14,         # round the x-height up at small sizes, up to this ppem
    default_script='latn',
    fallback_script='none',
    # stem widths: -1 natural, 0 quantized, 1 strong, for grayscale, GDI ClearType and
    # DirectWrite ClearType rendering
    gray_stem_width_mode=0,
    gdi_cleartype_stem_width_mode=1,
    dw_cleartype_stem_width_mode=0,
    windows_compatibility=False,
    no_info=True,                 # keep our version string free of ttfautohint's note
)


def hint(tt):
    """A hinted copy of a TTFont (the input is left unhinted)."""
    from ttfautohint import ttfautohint
    raw = io.BytesIO()
    tt.save(raw)
    return TTFont(io.BytesIO(ttfautohint(in_buffer=raw.getvalue(), **OPTIONS)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('fonts', nargs='+', type=Path)
    ap.add_argument('-o', '--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for path in a.fonts:
        hint(TTFont(path)).save(a.out / path.name)
        print(f'hinted {path.name} -> {a.out / path.name}')
