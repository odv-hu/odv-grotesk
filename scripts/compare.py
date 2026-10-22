"""Glyph-by-glyph comparison sheet: odv Grotesk vs Akkurat Pro, as vector PDF.

    python3 scripts/compare.py ~/Library/Fonts preview/odv-vs-akkurat.pdf

Needs cairosvg and uharfbuzz on top of requirements.txt. Akkurat Pro is read from
the fonts folder at run time; nothing of it goes into the repo (the PDF is gitignored).
"""
import io
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import cairosvg
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from pypdf import PdfWriter, PdfReader

FONTS = Path(sys.argv[1])
OUT = Path(sys.argv[2])

W, H = 420, 297            # A3 landscape, mm
M = 12                     # margin
ODV_COL = '#111111'
AKK_COL = '#1f56c4'
GUIDE = '#c9c9c9'
LABEL_FONT = 'Inter, Helvetica, Arial, sans-serif'

# odv style -> nearest Akkurat Pro style by stem weight of n
PAIRS = [
    ('Regular', 'Regular'), ('Medium', 'Regular'), ('Bold', 'Bold'),
    ('Italic', 'Regular Italic'), ('MediumItalic', 'Regular Italic'), ('BoldItalic', 'Bold Italic'),
]

SAMPLES = [
    (14, 'Hamburgefonstiv HAMBURGEFONSTIV'),
    (14, 'Árvíztűrő tükörfúrógép ÁRVÍZTŰRŐ TÜKÖRFÚRÓGÉP'),
    (14, 'SSSsss Iiiijj äöüï ISO 10211 numerical model'),
    (9, 'Sokszor elvont, mégis szerkezetileg pontos: a hőhíd a szerkezet logikájából következik.'),
    (9, 'The fluxscape is a field, not a number: heat flows where the construction lets it.'),
    (9, '0123456789 (12,5 °C) [λ = 0,035 W/mK] € % § & @ * ? ! „idézet” «»'),
    (5.5, 'Sokszor elvont, mégis szerkezetileg pontos: a hőhíd a szerkezet logikájából következik.'),
    (5.5, 'The fluxscape is a field, not a number: heat flows where the construction lets it.'),
    (3.5, 'Sokszor elvont, mégis szerkezetileg pontos: a hőhíd a szerkezet logikájából következik. '
          'The fluxscape is a field, not a number.'),
]


class Face:
    def __init__(self, path, label):
        self.path, self.label = path, label
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt['head'].unitsPerEm
        os2 = self.tt['OS/2']
        self.xh, self.cap = os2.sxHeight / self.upm, os2.sCapHeight / self.upm
        self.hbfont = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self._d = {}

    def d(self, name):
        if name not in self._d:
            pen = SVGPathPen(self.gs)
            self.gs[name].draw(pen)
            self._d[name] = pen.getCommands()
        return self._d[name]

    def adv(self, name):
        return self.tt['hmtx'][name][0] / self.upm

    def stem(self):
        import sys as _s
        _s.path.insert(0, str(Path(__file__).resolve().parent))
        from draw import Font
        f = Font(self.path)
        return f.V / self.upm * 1000, f.H / self.upm * 1000


def glyph(face, name, x, y, em, color):
    """A glyph with its origin at (x, y) mm, em mm tall."""
    s = em / face.upm
    d = face.d(name)
    if not d:
        return ''
    return (f'<path transform="translate({x:.3f} {y:.3f}) scale({s:.6f} {-s:.6f})" '
            f'd="{d}" fill="{color}"/>')


def text(x, y, s, size, color='#666', anchor='start', weight='normal'):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{LABEL_FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(s)}</text>')


def line(x0, y0, x1, y1, color=GUIDE, w=0.1):
    return f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" stroke="{color}" stroke-width="{w}"/>'


def svg(groups):
    body = ''.join(f'<g id="{gid}">{"".join(items)}</g>' for gid, items in groups)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" '
            f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="white"/>{body}</svg>')


def header(title, sub, page):
    return [text(M, M + 2, title, 6, '#111', weight='bold'),
            text(M, M + 7.5, sub, 3.2),
            text(W - M, M + 2, f'{page}', 3.2, anchor='end')]


def setline(face, s, x, y, em, color):
    buf = hb.Buffer()
    buf.add_str(s)
    buf.guess_segment_properties()
    hb.shape(face.hbfont, buf, {'kern': True, 'liga': True})
    out = []
    order = face.tt.getGlyphOrder()
    k = em / face.upm
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        out.append(glyph(face, name, x + pos.x_offset * k, y - pos.y_offset * k, em, color))
        x += pos.x_advance * k
    return out, x


def text_page(odv, akk, page):
    g_odv, g_akk, g_lab = [], [], []
    g_lab += header(f'{odv.label}  vs  {akk.label}', 'text setting at equal point size — black: odv Grotesk, blue: Akkurat Pro', page)
    y = M + 22
    for size_mm, s in SAMPLES:
        for face, col, bucket, tag in ((odv, ODV_COL, g_odv, 'odv'), (akk, AKK_COL, g_akk, 'Akkurat')):
            y += size_mm * 1.05
            g_lab.append(text(M, y, tag, 2.4, col))
            items, _ = setline(face, s, M + 14, y, size_mm, col)
            bucket += items
        y += size_mm * 0.55
    # metrics table
    y += 4
    rows = [('', 'x-height', 'cap height', 'stem n (‰ em)', 'thin o (‰ em)')]
    for f in (odv, akk):
        v, h = f.stem()
        rows.append((f.label, f'{f.xh:.3f}', f'{f.cap:.3f}', f'{v:.0f}', f'{h:.0f}'))
    for r in rows:
        for i, c in enumerate(r):
            g_lab.append(text(M + 14 + i * 38, y, c, 3, '#333'))
        y += 5
    return svg([('labels', g_lab), (odv.label.replace(' ', '-'), g_odv), (akk.label.replace(' ', '-'), g_akk)])


def order_codepoints(odv, akk):
    cps = set(odv.cmap) | set(akk.cmap)
    cps = {c for c in cps if c > 0x20 and c not in (0xA0, 0xAD) and not (0xE000 <= c <= 0xF8FF)}
    first = [ord(c) for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789']
    rest = sorted(cps - set(first))
    return [c for c in first if c in cps] + rest


def grid_pages(odv, akk, start_page):
    em = 13.0                       # mm per em
    box = 1.08 * em                 # each glyph's column
    cw = 2 * box + 3                # cell width
    asc, desc = 0.80 * em, 0.26 * em
    ch = asc + desc + 6             # cell height incl. label
    cols = int((W - 2 * M) // cw)
    rows = int((H - 2 * M - 14) // ch)
    per = cols * rows
    cps = order_codepoints(odv, akk)
    pages = []
    for p0 in range(0, len(cps), per):
        page = start_page + len(pages)
        g_odv, g_akk, g_lab, g_guide = [], [], [], []
        g_lab += header(f'{odv.label}  vs  {akk.label}',
                        'glyphs at equal em — black: odv Grotesk, blue: Akkurat Pro; '
                        'guides: baseline, x-height and cap height of each font', page)
        for i, cp in enumerate(cps[p0:p0 + per]):
            r, c = divmod(i, cols)
            x0 = M + c * cw
            y0 = M + 14 + r * ch
            base = y0 + 4 + asc
            g_lab.append(text(x0, y0 + 2.6, f'{chr(cp)}  U+{cp:04X}', 2.2, '#888'))
            for k, (face, col, bucket) in enumerate(((odv, ODV_COL, g_odv), (akk, AKK_COL, g_akk))):
                bx = x0 + k * box
                g_guide.append(line(bx, base, bx + box - 1, base, '#aaa'))
                g_guide.append(line(bx, base - face.xh * em, bx + box - 1, base - face.xh * em))
                g_guide.append(line(bx, base - face.cap * em, bx + box - 1, base - face.cap * em))
                name = face.cmap.get(cp)
                if name is None:
                    g_lab.append(text(bx + (box - 1) / 2, base - 0.3 * em, '—', 2.4, '#bbb', 'middle'))
                    continue
                a = face.adv(name) * em
                gx = bx + (box - 1 - a) / 2      # centre the advance in the column
                bucket.append(glyph(face, name, gx, base, em, col))
        pages.append(svg([('guides', g_guide), ('labels', g_lab),
                          (odv.label.replace(' ', '-'), g_odv), (akk.label.replace(' ', '-'), g_akk)]))
    return pages


def cover(faces):
    g = header('odv Grotesk vs Akkurat Pro', 'complete glyph comparison, all styles', 1)
    y = M + 26
    g.append(text(M, y, 'Pairs, by nearest stem weight (stem of n, thousandths of the em):', 3.6, '#111'))
    y += 8
    for odv, akk in faces:
        v1, _ = odv.stem(); v2, _ = akk.stem()
        g.append(text(M + 4, y, f'{odv.label}  ({v1:.0f})   vs   {akk.label}  ({v2:.0f})', 3.6, '#333'))
        y += 6
    y += 4
    lines = [
        'Akkurat Pro Light has no odv counterpart (odv starts at Regular), so it is not paired.',
        'Each pair: one text-setting page, then every character either font maps, A–Z, a–z, 0–9 first,',
        'then by code point. A dash marks a character the font does not have.',
        'Glyphs are vector outlines (no fonts embedded); black = odv Grotesk, blue = Akkurat Pro.',
        'Both are drawn at the same em size, so differences in x-height and width are real.',
    ]
    for s in lines:
        g.append(text(M, y, s, 3.4, '#444')); y += 5.5
    return svg([('labels', g)])


def main():
    faces = []
    for o, a in PAIRS:
        odv = Face(FONTS / f'odvGrotesk-{o}.ttf', f'odv Grotesk {o}')
        akk = Face(FONTS / f'AkkuratPro {a}.otf', f'Akkurat Pro {a}')
        faces.append((odv, akk))
    pages = [cover(faces)]
    for odv, akk in faces:
        pages.append(text_page(odv, akk, len(pages) + 1))
        pages += grid_pages(odv, akk, len(pages) + 1)
    writer = PdfWriter()
    for s in pages:
        pdf = cairosvg.svg2pdf(bytestring=s.encode('utf-8'))
        writer.add_page(PdfReader(io.BytesIO(pdf)).pages[0])
    writer.add_metadata({'/Title': 'odv Grotesk vs Akkurat Pro'})
    with open(OUT, 'wb') as f:
        writer.write(f)
    print(len(pages), 'pages ->', OUT)


if __name__ == '__main__':
    main()
