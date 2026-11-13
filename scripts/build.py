"""Build odv Grotesk from Schibsted Grotesk: reshaped I, a, e plus the added glyphs,
Greek accents (scripts/accents.py), and the Greek letters kerned like their Latin
models (scripts/kern.py).

    python3 scripts/build.py            # draw the added glyphs, then build all styles
    python3 scripts/build.py --no-draw  # build from sources/*.ufo as they are

Downloads the pinned Schibsted Grotesk release into upstream/ on first run,
writes fonts/ttf/*.ttf (desktop, LuaLaTeX) and fonts/webfonts/*.woff2 (web).
"""
import argparse
import sys
import urllib.request
from pathlib import Path

import ufoLib2
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accents  # noqa: E402
import draw  # noqa: E402
import kern  # noqa: E402
import modify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.3.5'
FAMILY = 'odv Grotesk'
PS_FAMILY = 'odvGrotesk'
UPSTREAM_COMMIT = 'd485f61f105e1b3935f4d21dfb4d371359798603'  # Schibsted Grotesk 1.100
UPSTREAM_URL = ('https://raw.githubusercontent.com/schibsted/schibsted-grotesk/'
                f'{UPSTREAM_COMMIT}/fonts/ttf/SchibstedGrotesk-{{style}}.ttf')
STYLES = ['Regular', 'Medium', 'Bold', 'Italic', 'MediumItalic', 'BoldItalic']
COPYRIGHT_ADDITION = ('Greek and mathematical additions and modifications copyright 2026 '
                      'Balázs Fürtön (https://github.com/odv-hu/odv-grotesk).')
MANUFACTURER = 'o d v'
MANUFACTURER_URL = 'https://odv.hu'
DESIGNER = 'Bakken & Baeck AS, Henrik Kongsvoll (Schibsted Grotesk); Balázs Fürtön (odv Grotesk)'
VENDOR_ID = 'NONE'  # not registered with Microsoft; Schibsted's 'BBT' belongs to Bakken & Baeck


def font_revision(version):
    """head.fontRevision for MAJOR.MINOR.PATCH: 0.3.2 -> 0.302. Needs MINOR < 10 and PATCH < 100."""
    major, minor, patch = (int(n) for n in version.split('.'))
    assert minor < 10 and patch < 100, version
    return float(f'{major}.{minor}{patch:02d}')


def upstream(style):
    path = ROOT / 'upstream' / f'SchibstedGrotesk-{style}.ttf'
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        print(f'downloading {path.name}')
        urllib.request.urlretrieve(UPSTREAM_URL.format(style=style), path)
    return path


def merge(tt, ufo):
    glyf, hmtx = tt['glyf'], tt['hmtx']
    order = tt.getGlyphOrder()
    added = []
    for name in sorted(ufo.keys()):
        if name in order:
            continue
        g = ufo[name]
        if g.components and not g.contours and len(g.components) == 1:
            # an alias such as Ι -> I: take the advance of the base as it is now
            g.width = hmtx[g.components[0].baseGlyph][0]
        pen = TTGlyphPen(tt.getGlyphSet())
        g.draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        if g.components and not g.contours:
            tg = pen.glyph()
        else:
            tg = pen.glyph(round=float)
            modify.round_smooth(tg)     # smooth nodes rounded to stay smooth
        glyf[name] = tg  # also appends the name to the glyph order
        added.append((name, g))
    tt.setGlyphOrder(glyf.glyphOrder)
    for name, g in added:
        tg = glyf[name]
        tg.recalcBounds(glyf)
        hmtx[name] = (round(g.width), getattr(tg, 'xMin', 0))
        for u in g.unicodes:
            for table in tt['cmap'].tables:
                if table.isUnicode():
                    table.cmap[u] = name
    if 'GDEF' in tt and tt['GDEF'].table.GlyphClassDef:
        for name, _ in added:
            tt['GDEF'].table.GlyphClassDef.classDefs[name] = 1
    for tag in ('hdmx', 'LTSH', 'VDMX'):
        if tag in tt:
            del tt[tag]
    return [n for n, _ in added]


def rename(tt):
    name = tt['name']
    for rec in name.names:
        s = rec.toUnicode()
        if rec.nameID == 0:
            s = s.rstrip() + ' ' + COPYRIGHT_ADDITION
        elif rec.nameID == 5:
            s = f'Version {VERSION}; based on Schibsted Grotesk 1.100'
        elif rec.nameID == 8:
            s = MANUFACTURER
        elif rec.nameID == 9:
            s = DESIGNER
        elif rec.nameID == 11:
            s = MANUFACTURER_URL
        elif rec.nameID in (1, 3, 4, 6, 16, 18, 21):
            s = s.replace('Schibsted Grotesk', FAMILY).replace('SchibstedGrotesk', PS_FAMILY)
            if rec.nameID == 3:
                s = f'{VERSION};ODV;' + s.split(';')[-1]
        else:
            continue
        rec.string = s
    tt['head'].fontRevision = font_revision(VERSION)
    os2 = tt['OS/2']
    os2.achVendID = VENDOR_ID
    os2.ulUnicodeRange1 |= 1 << 7            # Greek and Coptic
    os2.ulUnicodeRange2 |= 1 << (38 - 32)    # Mathematical Operators
    os2.ulCodePageRange1 |= 1 << 3           # 1253 Greek


def build(style, redraw):
    src = upstream(style)
    ufo_path = ROOT / 'sources' / f'{style}.ufo'
    if redraw or not ufo_path.exists():
        draw.draw(src, ufo_path)
    tt = TTFont(src)
    modify.modify(tt, draw.Font(src), src)
    added = merge(tt, ufoLib2.Font.open(ufo_path))
    accented = accents.accents(tt)
    kerned = kern.kern(tt, accented)
    hand = ROOT / 'sources' / 'hand-edited.txt'
    skip = {ln.strip() for ln in hand.read_text().splitlines()
            if ln.strip() and not ln.startswith('#')} if hand.exists() else set()
    faired = modify.fair_outlines(tt, skip)
    rename(tt)
    out = ROOT / 'fonts' / 'ttf' / f'{PS_FAMILY}-{style}.ttf'
    out.parent.mkdir(parents=True, exist_ok=True)
    tt.save(out)
    web = ROOT / 'fonts' / 'webfonts' / f'{PS_FAMILY}-{style}.woff2'
    web.parent.mkdir(parents=True, exist_ok=True)
    tt.flavor = 'woff2'
    tt.save(web)
    print(f'{out.name}: {len(added)} glyphs added, {kerned} Greek letters kerned, '
          f'{len(faired)} outlines smoothed')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-draw', action='store_true', help='use sources/*.ufo as they are')
    ap.add_argument('styles', nargs='*', default=STYLES)
    a = ap.parse_args()
    for st in a.styles:
        build(st, not a.no_draw)
