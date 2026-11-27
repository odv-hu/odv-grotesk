"""Compare two builds of odv Grotesk glyph by glyph: what changed, new kinks, new
curvature steps, and before/after images (#33).

    python3 scripts/check.py BASE_DIR HEAD_DIR OUT_DIR

BASE_DIR and HEAD_DIR hold odvGrotesk-*.ttf (the base branch's build and the pull
request's). OUT_DIR gets report.md, report.json and images/: per changed glyph, base and
head side by side, filled and as outlines with points, plus a text line per style.
Exits with 1 when the head build has a kink above KINK_FAIL_DEG that the base build does
not have at that place, so the check fails.

Measured on the final TrueType outlines, after rounding and thinning, because several
problems only appeared there. Only what is new or worse than in the base build is
reported, so kinks that predate a change (some of Schibsted's own) never fail a check.
Needs freetype-py, uharfbuzz and Pillow on top of requirements.txt (requirements-check.txt).
"""
import json
import math
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

KINK_MIN_DEG = 0.5      # a turn at a point meant to be smooth, above this, is a kink
KINK_MAX_DEG = 15.0     # a new point turning more than this is a corner on purpose; a point
                        # that was smooth in the base build is a kink at any angle
KINK_FAIL_DEG = 0.5     # new kinks above this fail the check
WORSE_BY_DEG = 0.2      # an existing kink counts as worse when it grows by more than this
STEP_RATIO = 1.8        # curvature on one side of a join more than this times the other
STEP_MIN_CURV = 1 / 4000  # ignore steps between nearly straight pieces (1/units)
MATCH_UNITS = 12        # a head point matches a base point within this distance
SAMPLE = 'Hamburgefonstiv Árvíztűrő tükörfúrógép 0123456789 nunhum ΑΒΓ αβγδ ∇∈∀'


# ---------------------------------------------------------------- outlines

def contours(glyf, name):
    """The glyph's contours as lists of (x, y, on_curve), components resolved."""
    g = glyf[name]
    coords, ends, flags = g.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append([(coords[i][0], coords[i][1], bool(flags[i] & 1)) for i in range(start, end + 1)])
        start = end + 1
    return out


def signature(font, name):
    """What makes two builds of a glyph the same: outline points, flags and advance."""
    glyf = font['glyf']
    pts = tuple(tuple(c) for c in contours(glyf, name))
    return pts, font['hmtx'][name][0]


def expand(contour):
    """Insert the implied on-curve points between two off-curve points, so every
    quadratic piece is (on, off, on) or a line (on, on)."""
    pts, n = [], len(contour)
    if not any(on for *_, on in contour):          # all off-curve: TrueType's special case
        for i in range(n):
            (x0, y0, _), (x1, y1, _) = contour[i], contour[(i + 1) % n]
            pts += [((x0 + x1) / 2, (y0 + y1) / 2, True, True), (x1, y1, False, False)]
        return pts
    k = next(i for i, (*_, on) in enumerate(contour) if on)
    seq = contour[k:] + contour[:k]
    for i, (x, y, on) in enumerate(seq):
        nx, ny, non = seq[(i + 1) % n]
        pts.append((x, y, on, False))
        if not on and not non:
            pts.append(((x + nx) / 2, (y + ny) / 2, True, True))   # implied point
    return pts


def joins(contour):
    """For every on-curve point: (x, y, implied, tangent in, tangent out, curvature in,
    curvature out, curve on both sides)."""
    pts = expand(contour)
    n = len(pts)
    on_idx = [i for i, p in enumerate(pts) if p[2]]
    pieces = []                                       # pieces between consecutive on-curve points
    for a, b in zip(on_idx, on_idx[1:] + on_idx[:1]):
        seq = [pts[a]]
        j = (a + 1) % n
        while j != b:
            seq.append(pts[j])
            j = (j + 1) % n
        seq.append(pts[b])
        pieces.append([(p[0], p[1]) for p in seq])
    result = []
    for i, idx in enumerate(on_idx):
        before, after = pieces[i - 1], pieces[i]
        x, y, _, implied = pts[idx]
        tin = _tangent(before, end=True)
        tout = _tangent(after, end=False)
        if tin is None or tout is None:
            continue
        result.append(dict(x=x, y=y, implied=implied, tin=tin, tout=tout,
                           kin=_curvature(before, end=True), kout=_curvature(after, end=False),
                           curves=len(before) == 3 and len(after) == 3,
                           line_curve=(len(before) == 3) != (len(after) == 3)))
    return result


def _tangent(piece, end):
    if end:
        (x0, y0), (x1, y1) = piece[-2], piece[-1]
    else:
        (x0, y0), (x1, y1) = piece[0], piece[1]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    return None if length == 0 else (dx / length, dy / length)


def _curvature(piece, end):
    """Curvature of a quadratic piece at its start or end; 0 for a line."""
    if len(piece) != 3:
        return 0.0
    (x0, y0), (x1, y1), (x2, y2) = piece
    d = (2 * (x2 - x1), 2 * (y2 - y1)) if end else (2 * (x1 - x0), 2 * (y1 - y0))
    dd = (2 * (x2 - 2 * x1 + x0), 2 * (y2 - 2 * y1 + y0))
    speed = math.hypot(*d)
    return 0.0 if speed == 0 else abs(d[0] * dd[1] - d[1] * dd[0]) / speed ** 3


def turn(t1, t2):
    dot = max(-1.0, min(1.0, t1[0] * t2[0] + t1[1] * t2[1]))
    return math.degrees(math.acos(dot))


def defects(font, name):
    """Turns at curve joins (every angle, for matching against the base) and curvature
    steps of one glyph."""
    kinks, steps = [], []
    for c in contours(font['glyf'], name):
        for j in joins(c):
            angle = turn(j['tin'], j['tout'])
            if j['curves'] or j['line_curve']:
                kinks.append(dict(x=j['x'], y=j['y'], deg=round(angle, 2)))
            if j['curves'] and angle <= KINK_MIN_DEG:
                lo, hi = sorted((j['kin'], j['kout']))
                if hi > STEP_MIN_CURV and (lo == 0 or hi / lo > STEP_RATIO):
                    steps.append(dict(x=j['x'], y=j['y'], ratio=round(hi / lo, 2) if lo else None))
    return kinks, steps


def new_or_worse(head, base, key, worse):
    """Head defects with no base defect nearby, or one that got worse."""
    out = []
    for d in head:
        near = [b for b in base if math.hypot(b['x'] - d['x'], b['y'] - d['y']) <= MATCH_UNITS]
        if not near or all(worse(d[key], b[key]) for b in near):
            out.append(d)
    return out


def new_kinks(head, base):
    """Head joins that turn by more than KINK_MIN_DEG where the base build was smoother:
    a point that was smooth (under KINK_MAX_DEG) and now turns more, at any angle, or a
    new point turning between KINK_MIN_DEG and KINK_MAX_DEG."""
    out = []
    for d in head:
        if d['deg'] <= KINK_MIN_DEG:
            continue
        near = [b for b in base if math.hypot(b['x'] - d['x'], b['y'] - d['y']) <= MATCH_UNITS]
        if near:
            b = min(near, key=lambda b: math.hypot(b['x'] - d['x'], b['y'] - d['y']))
            if b['deg'] < KINK_MAX_DEG and d['deg'] > b['deg'] + WORSE_BY_DEG:
                out.append(dict(d, was=b['deg']))
        elif d['deg'] < KINK_MAX_DEG:
            out.append(d)
    return out


def step_worse(h, b):
    if h is None:
        return b is not None
    return b is not None and h > b * 1.1


# ---------------------------------------------------------------- images

def render_glyph(path, name, size):
    """Unhinted FreeType bitmap of one glyph, as a Pillow image, plus its metrics."""
    import freetype
    from PIL import Image
    face = freetype.Face(str(path))
    face.set_pixel_sizes(0, size)
    face.load_glyph(face.get_name_index(name.encode()), freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_RENDER)
    bm = face.glyph.bitmap
    img = Image.frombytes('L', (bm.width, bm.rows), bytes(bm.buffer)) if bm.width else Image.new('L', (1, 1))
    return img, face.glyph.bitmap_left, face.glyph.bitmap_top


def glyph_panel(font_path, font, name, label, size=360):
    """Filled glyph and, next to it, the outline with on-curve (filled) and off-curve
    (open) points, on a common baseline."""
    from PIL import Image, ImageDraw
    upm = font['head'].unitsPerEm
    scale = size / upm
    asc, desc = font['hhea'].ascent, font['hhea'].descent
    adv = font['hmtx'][name][0]
    w, h = int(max(adv, upm * .6) * scale) + 40, int((asc - desc) * scale) + 60
    panel = Image.new('RGB', (2 * w, h), 'white')
    draw = ImageDraw.Draw(panel)
    base_y = 30 + asc * scale
    for ox in (0, w):
        draw.line([(ox + 20, base_y), (ox + 20 + adv * scale, base_y)], fill='#c9c9c9')
        draw.line([(ox + 20, base_y), (ox + 20, base_y - asc * scale)], fill='#e4e4e4')
        draw.line([(ox + 20 + adv * scale, base_y), (ox + 20 + adv * scale, base_y - asc * scale)], fill='#e4e4e4')
    img, left, top = render_glyph(font_path, name, size)
    ink = Image.new('RGB', img.size, '#111111')
    panel.paste(ink, (int(20 + left), int(base_y - top)), img)
    for c in contours(font['glyf'], name):
        flat = []
        for p in expand(c):
            flat.append(p)
        _draw_outline(draw, flat, w + 20, base_y, scale)
    draw.text((6, 4), label, fill='#555555')
    return panel


def zoom_panel(font, name, x, y, label, half=60, scale=4):
    """The outline around one point, 2*half units square at scale px per unit, so a
    kink of a few units can be seen."""
    from PIL import Image, ImageDraw
    size = 2 * half * scale
    panel = Image.new('RGB', (size, size + 18), 'white')
    draw = ImageDraw.Draw(panel)
    for c in contours(font['glyf'], name):
        _draw_outline(draw, expand(c), size / 2 - x * scale, 18 + size / 2 + y * scale, scale, steps=48)
    draw.text((4, 2), label, fill='#555555')
    draw.rectangle([0, 18, size - 1, size + 17], outline='#c9c9c9')
    return panel


def _draw_outline(draw, pts, ox, oy, scale, steps=12):
    tx = lambda x, y: (ox + x * scale, oy - y * scale)
    n = len(pts)
    line = []
    for i, (x, y, on, _) in enumerate(pts):
        if on:
            line.append(tx(x, y))
            continue
        (x0, y0, *_), (x2, y2, *_) = pts[i - 1], pts[(i + 1) % n]
        for k in range(1, steps):
            t = k / steps
            bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x + t * t * x2
            by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y + t * t * y2
            line.append(tx(bx, by))
    if line:
        draw.line(line + [line[0]], fill='#1f56c4', width=2)
    for x, y, on, implied in pts:
        px, py = tx(x, y)
        r = 4
        if implied:
            continue
        if on:
            draw.rectangle([px - r, py - r, px + r, py + r], fill='#1f56c4')
        else:
            draw.ellipse([px - r, py - r, px + r, py + r], outline='#1f56c4', width=2)


def text_line(path, text, size=48):
    """A line of text at reading size, shaped by HarfBuzz, drawn with FreeType unhinted."""
    import freetype
    import uharfbuzz as hb
    from PIL import Image
    blob = hb.Blob.from_file_path(str(path))
    font = hb.Font(hb.Face(blob))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    face = freetype.Face(str(path))
    face.set_pixel_sizes(0, size)
    upm = face.units_per_EM
    scale = size / upm
    width = int(sum(p.x_advance for p in buf.glyph_positions) * scale) + 40
    img = Image.new('L', (width, int(size * 1.6)), 255)
    x, base = 20.0, size * 1.15
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        face.load_glyph(info.codepoint, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_RENDER)
        bm = face.glyph.bitmap
        if bm.width:
            g = Image.frombytes('L', (bm.width, bm.rows), bytes(bm.buffer))
            ox = int(round(x + pos.x_offset * scale + face.glyph.bitmap_left))
            oy = int(round(base - pos.y_offset * scale - face.glyph.bitmap_top))
            img.paste(0, (ox, oy), g)
        x += pos.x_advance * scale
    return img.convert('RGB')


def side_by_side(a, b, gap=24):
    from PIL import Image
    out = Image.new('RGB', (a.width + gap + b.width, max(a.height, b.height)), 'white')
    out.paste(a, (0, 0))
    out.paste(b, (a.width + gap, 0))
    return out


def stacked(images, gap=8):
    from PIL import Image
    out = Image.new('RGB', (max(i.width for i in images), sum(i.height for i in images) + gap * (len(images) - 1)), 'white')
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


# ---------------------------------------------------------------- report

def safe(name):
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)


def compare(base_dir, head_dir, out_dir, images=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'images').mkdir(exist_ok=True)
    report, failed = {}, False
    for head_path in sorted(head_dir.glob('odvGrotesk-*.ttf')):
        style = head_path.stem.split('-', 1)[1]
        base_path = base_dir / head_path.name
        head = TTFont(head_path)
        base = TTFont(base_path) if base_path.exists() else None
        names = head.getGlyphOrder()
        added = [g for g in names if base is None or g not in base['glyf']]
        removed = [g for g in base.getGlyphOrder() if g not in head['glyf']] if base else []
        changed = [g for g in names if g not in added and signature(head, g) != signature(base, g)]
        entry = dict(changed=changed, added=added, removed=removed, kinks={}, steps={})
        for g in changed + added:
            hk, hs = defects(head, g)
            bk, bs = defects(base, g) if g in changed else ([], [])
            nk = new_kinks(hk, bk)
            ns = new_or_worse(hs, bs, 'ratio', step_worse)
            if nk:
                entry['kinks'][g] = nk
                failed |= any(k['deg'] > KINK_FAIL_DEG for k in nk)
            if ns:
                entry['steps'][g] = ns
            if images and g in changed:
                rows = [side_by_side(glyph_panel(base_path, base, g, f'{style} {g}: base'),
                                     glyph_panel(head_path, head, g, f'{style} {g}: pull request'))]
                for d in (nk + ns)[:4]:   # close-ups of the first new defects
                    where = f"({d['x']:g}, {d['y']:g})"
                    rows.append(side_by_side(zoom_panel(base, g, d['x'], d['y'], f'base {where}'),
                                             zoom_panel(head, g, d['x'], d['y'], f'pull request {where}')))
                stacked(rows).save(out_dir / 'images' / f'{style}-{safe(g)}.png')
        if images and (changed or added) and base is not None:
            stacked([text_line(base_path, SAMPLE), text_line(head_path, SAMPLE)]).save(
                out_dir / 'images' / f'{style}-text.png')
        report[style] = entry
    (out_dir / 'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
    (out_dir / 'report.md').write_text(markdown(report, failed))
    return report, failed


def markdown(report, failed):
    lines = ['## Glyph check', '']
    total = sum(len(e['changed']) + len(e['added']) + len(e['removed']) for e in report.values())
    if not total:
        lines.append('No glyph outlines or advances changed.')
        return '\n'.join(lines) + '\n'
    lines += ['| Style | Changed | Added | Removed | New kinks | New curvature steps |', '|---|---|---|---|---|---|']
    for style, e in report.items():
        lines.append(f"| {style} | {len(e['changed'])} | {len(e['added'])} | {len(e['removed'])} | "
                     f"{sum(len(v) for v in e['kinks'].values())} | {sum(len(v) for v in e['steps'].values())} |")
    lines.append('')
    for style, e in report.items():
        if e['changed']:
            shown = ', '.join(f'`{g}`' for g in e['changed'][:60])
            more = f' and {len(e["changed"]) - 60} more' if len(e['changed']) > 60 else ''
            lines.append(f'**{style}** changed: {shown}{more}')
            lines.append('')
    defects_found = [(s, g, k) for s, e in report.items() for g, ks in e['kinks'].items() for k in ks]
    if defects_found:
        lines += [f'### New or worse kinks (above {KINK_MIN_DEG}°)', '', '| Style | Glyph | At (x, y) | Turn |', '|---|---|---|---|']
        lines += [f"| {s} | `{g}` | {k['x']:g}, {k['y']:g} | {k['deg']}°" + (f" (was {k['was']}°)" if 'was' in k else ' (new point)') + ' |'
                  for s, g, k in defects_found]
        lines.append('')
    steps_found = [(s, g, k) for s, e in report.items() for g, ks in e['steps'].items() for k in ks]
    if steps_found:
        lines += [f'### New or larger curvature steps (ratio above {STEP_RATIO})', '',
                  '| Style | Glyph | At (x, y) | Ratio |', '|---|---|---|---|']
        lines += [f"| {s} | `{g}` | {k['x']:g}, {k['y']:g} | {k['ratio'] or 'line to curve'} |" for s, g, k in steps_found[:80]]
        if len(steps_found) > 80:
            lines.append(f'| … | {len(steps_found) - 80} more in report.json | | |')
        lines.append('')
    lines.append('**Result:** ' + ('new kinks, the check fails.' if failed else 'no new kinks.'))
    lines.append('')
    lines.append('Before/after images of every changed glyph and a text line per style are in the '
                 '`glyph-check` artifact of this run.')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    _, failed = compare(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print((Path(sys.argv[3]) / 'report.md').read_text())
    sys.exit(1 if failed else 0)
