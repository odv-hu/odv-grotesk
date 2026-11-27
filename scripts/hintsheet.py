"""Side-by-side sheet of small text with and without hints (#20).

    python3 scripts/hintsheet.py UNHINTED_DIR HINTED_DIR preview/hinting.png [UPSTREAM_DIR]

Each style at 12, 13, 15 and 16 px (9, 10, 11 and 12 pt on a 96 dpi screen): Schibsted
Grotesk as shipped (hinted, when UPSTREAM_DIR is given), odv Grotesk unhinted, odv Grotesk
hinted, each also enlarged 4x so the pixels can be judged. Rendered by FreeType with its
TrueType interpreter (v40, grayscale, no autohinter), the closest stand-in for Windows
here. It is not Windows: ClearType's subpixel rendering and GDI's full-pixel x hinting
differ, so the to-do of looking at the fonts on a Windows machine stays.
Needs freetype-py, uharfbuzz and Pillow (requirements-check.txt).
"""
import sys
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image, ImageDraw

STYLES = ['Regular', 'Medium', 'Bold', 'Italic', 'MediumItalic', 'BoldItalic']
SIZES = [12, 13, 15, 16]
TEXT = 'a c e i j p I s r n m u: iij . , ! ? 0123456789 αβγδ λ ΣΩ ∇∈ Hamburgefonstiv'
FLAGS = freetype.FT_LOAD_NO_AUTOHINT | freetype.FT_LOAD_TARGET_NORMAL | freetype.FT_LOAD_RENDER


def line(path, size, text=TEXT):
    """Text at size px, positions from HarfBuzz rounded to whole pixels, each glyph
    rasterised by FreeType with the font's own hints (if any)."""
    face = freetype.Face(str(path))
    face.set_pixel_sizes(0, size)
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    font.scale = (size * 64, size * 64)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    width = sum(p.x_advance for p in buf.glyph_positions) // 64 + 10
    img = Image.new('L', (width, int(size * 1.5)), 255)
    x, base = 4 * 64, int(size * 1.15)
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        face.load_glyph(info.codepoint, FLAGS)
        bm = face.glyph.bitmap
        if bm.width:
            g = Image.frombytes('L', (bm.width, bm.rows), bytes(bm.buffer))
            img.paste(0, (round(x / 64) + face.glyph.bitmap_left, base - face.glyph.bitmap_top), g)
        x += pos.x_advance
    return img


def sheet(unhinted, hinted, out, upstream=None):
    rows = []
    for style in STYLES:
        sources = []
        if upstream and (upstream / f'SchibstedGrotesk-{style}.ttf').exists():
            sources.append(('Schibsted Grotesk, hinted', upstream / f'SchibstedGrotesk-{style}.ttf'))
        sources += [('odv Grotesk, unhinted', unhinted / f'odvGrotesk-{style}.ttf'),
                    ('odv Grotesk, hinted', hinted / f'odvGrotesk-{style}.ttf')]
        for size in SIZES:
            for label, path in sources:
                img = line(path, size)
                big = img.crop((0, 0, min(img.width, 220), img.height)).resize(
                    (min(img.width, 220) * 4, img.height * 4), Image.NEAREST)
                rows.append((f'{style} {size} px: {label}', img, big))
    lw = 260
    width = lw + max(r[1].width for r in rows) + 20 + max(r[2].width for r in rows)
    height = sum(max(r[1].height, r[2].height) + 6 for r in rows)
    page = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(page)
    y = 0
    for label, img, big in rows:
        draw.text((4, y + 2), label, fill=110)
        page.paste(img, (lw, y))
        page.paste(big, (lw + max(r[1].width for r in rows) + 20, y))
        y += max(img.height, big.height) + 6
    out.parent.mkdir(parents=True, exist_ok=True)
    page.save(out)
    print(f'wrote {out}')


if __name__ == '__main__':
    if len(sys.argv) not in (4, 5):
        raise SystemExit(__doc__)
    sheet(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]) if len(sys.argv) == 5 else None)
