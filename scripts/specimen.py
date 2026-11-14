"""Glyph overview for the README: preview/glyphs.svg, drawn from the built fonts.

    python3 scripts/build.py && python3 scripts/specimen.py

Every glyph is an outline (no font is embedded or needed to view it), defined
once and placed with <use>, so the file stays small. Light and dark colours
follow the reader's colour scheme, as on GitHub. Needs uharfbuzz on top of
requirements.txt, for the kerned headings.
"""
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / 'fonts' / 'ttf'
OUT = ROOT / 'preview' / 'glyphs.svg'

COLS = 13
CELL_W, CELL_H = 84, 100       # px
EM = 66                        # glyph size in the grid, px per em
MARGIN = 40
WIDTH = 2 * MARGIN + COLS * CELL_W

# (heading, rows of COLS characters); the Greek and the maths are what odv Grotesk adds
SECTIONS = [
    ('Capitals', ['ABCDEFGHIJKLM', 'NOPQRSTUVWXYZ']),
    ('Lowercase', ['abcdefghijklm', 'nopqrstuvwxyz']),
    ('Accents and ligatures', ['ÁÉÍÓÖŐÚÜŰÄÇŠŽ', 'áéíóöőúüűäçšž', 'ÆŒØÞÐßæœøþðﬁﬂ']),
    ('Greek', ['ΑΒΓΔΕΖΗΘΙΚΛΜ', 'ΝΞΟΠΡΣΤΥΦΧΨΩ', 'αβγδεζηθικλμν', 'ξοπρσςτυφχψωϵ',
               'ϕάέήίόύώϊϋΐΰ']),
    ('Figures and symbols', ['0123456789½¼¾', '°%‰€$£¥¢₿#@&§']),
    ('Punctuation', ['.,:;…!?¡¿‘’“”', '‚„‹›«»-–—/\\|*', '()[]{}†‡•·¶′″']),
    ('Maths', ['∇∂∫∑∏√∞±∓×÷⋅−', '=≠≈≡≤≥∼∝∈∉∀∃∅', '∩∪⊂⊃⊆⊇∧∨¬⊥∥∠△', '→←↑↓↔⇒⇔<>↗↘◊○']),
]
STYLES = [('Regular', 'Regular'), ('Medium', 'Medium'), ('Bold', 'Bold'),
          ('Italic', 'Italic'), ('MediumItalic', 'Medium Italic'), ('BoldItalic', 'Bold Italic')]

CSS = """
.g{fill:#111}.m{fill:#8a8a8a}.r{fill:none;stroke:#e4e4e4;stroke-width:1}
@media (prefers-color-scheme:dark){.g{fill:#eee}.m{fill:#8a8a8a}.r{stroke:#333}}
"""


class Face:
    def __init__(self, style):
        path = FONTS / f'odvGrotesk-{style}.ttf'
        self.style = style
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt['head'].unitsPerEm
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.defs = {}

    def ref(self, name):
        """id of the glyph's outline in <defs>, adding it on first use."""
        key = f'{self.style}-{self.tt.getGlyphID(name)}'
        if key not in self.defs:
            rec = DecomposingRecordingPen(self.gs)
            self.gs[name].draw(rec)
            pen = SVGPathPen(self.gs, ntos=lambda v: f'{v:.0f}' if v == int(v) else f'{v:.1f}')
            rec.replay(pen)
            self.defs[key] = pen.getCommands()
        return key

    def ink(self, name):
        bp = BoundsPen(self.gs)
        self.gs[name].draw(bp)
        return bp.bounds

    def text(self, s, x, y, size, cls):
        """A line of kerned text as <use> elements, baseline at y; returns (svg, width)."""
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {'kern': True})
        k = size / self.upm
        out, pen = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = self.tt.getGlyphName(info.codepoint)
            if self.ink(name):
                out.append(use(self.ref(name), x + (pen + pos.x_offset) * k, y, k, cls))
            pen += pos.x_advance
        return ''.join(out), pen * k


def use(ref, x, y, k, cls):
    return f'<use href="#{ref}" class="{cls}" transform="translate({x:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})"/>'


def main():
    faces = {s: Face(s) for s, _ in STYLES}
    reg, bold = faces['Regular'], faces['Bold']
    body = []
    y = MARGIN + 52
    svg, _ = bold.text('odv Grotesk', MARGIN, y, 64, 'g')
    body.append(svg)
    y += 34
    svg, _ = reg.text('Schibsted Grotesk with Greek and maths characters, for odv.hu and LaTeX',
                      MARGIN, y, 17, 'm')
    body.append(svg)
    y += 46
    x = MARGIN
    for style, label in STYLES:
        svg, w = faces[style].text(label, x, y, 22, 'g')
        body.append(svg)
        x += w + 26
    y += 30
    for heading, rows in SECTIONS:
        y += 34
        svg, _ = reg.text(heading, MARGIN, y, 15, 'm')
        body.append(svg)
        y += 12
        for row in rows:
            assert len(row) <= COLS, row
            body.append(f'<rect class="r" x="{MARGIN + 0.5}" y="{y + 0.5}" '
                        f'width="{len(row) * CELL_W}" height="{CELL_H}"/>')
            for i in range(1, len(row)):
                xx = MARGIN + i * CELL_W + 0.5
                body.append(f'<path class="r" d="M{xx} {y}v{CELL_H}"/>')
            k = EM / reg.upm
            base = y + CELL_H * 0.70
            for i, ch in enumerate(row):
                name = reg.cmap[ord(ch)]
                b = reg.ink(name)
                cx = MARGIN + (i + 0.5) * CELL_W
                body.append(use(reg.ref(name), cx - (b[0] + b[2]) / 2 * k, base, k, 'g'))
            y += CELL_H
    height = y + MARGIN
    defs = ''.join(f'<path id="{key}" d="{d}"/>' for f in faces.values() for key, d in f.defs.items())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height:.0f}" '
        f'width="{WIDTH}" height="{height:.0f}" role="img" aria-label="odv Grotesk glyph overview">'
        f'<title>odv Grotesk glyph overview</title><style>{CSS}</style><defs>{defs}</defs>'
        + ''.join(body) + '</svg>\n')
    print(f'{OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024} kB')


if __name__ == '__main__':
    main()
