"""Reshape three Latin letters of Schibsted Grotesk, in place, before the merge.

    I  the top and bottom serifs come off: a plain stem, spaced like the stem of H.
    e  the end of the lower stroke is cut level instead of on a slant, so the
       opening between it and the bar is a horizontal slot.
    a  (two-storey forms only) the top of the bowl runs flat out from the stem
       and turns down in a tighter corner, instead of sloping down to the left.

Like draw.py, each change is a recipe on the font's own outlines, measured per
style, so the same code serves every weight; italics are un-slanted first and
slanted back after. The italic a is single-storey and is left as it is.
Accented letters are composites of these glyphs and follow; their marks and
the mark-attachment anchors are shifted where the I moved.
"""
import math

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

from geometry import (bounds, glyph_path, intersect, polygon, rect, slant, subtract,
                      union)
import pathops

BIG = 10000
CHANGED = ('I', 'e', 'a')

# the a's bowl: where the flat top ends, as a share of the counter's width from
# the left, and how full the corner is (0.55 is a circle, higher is squarer)
A_FLAT = 0.32
A_TENSION = 0.66
A_TENSION_OUT = 0.58                         # the outside stays rounder, so the corner isn't heavy


# ---------- helpers ----------

def _contours(p):
    out = []
    for c in p.contours:
        q = pathops.Path()
        c.draw(q.getPen())
        out.append(q)
    return out


def _area(p):
    x0, y0, x1, y1 = p.bounds
    return (x1 - x0) * (y1 - y0)


def _hspan(p, y):
    cut = intersect(p, rect(-BIG, y - 0.25, BIG, y + 0.25))
    return sorted((c.bounds[0], c.bounds[2]) for c in _contours(cut))


def _vspan(p, x):
    cut = intersect(p, rect(x - 0.25, -BIG, x + 0.25, BIG))
    return sorted((c.bounds[1], c.bounds[3]) for c in _contours(cut))


def _corner(x_side, y_low, x_top, y_top, x_right, k):
    """Region under a rounded corner: up the side from (x_side, y_low), round
    into the top at (x_top, y_top), flat to x_right, down and back."""
    p = pathops.Path()
    p.moveTo(x_side, y_low)
    p.cubicTo(x_side, y_low + k * (y_top - y_low),
              x_top - k * (x_top - x_side), y_top,
              x_top, y_top)
    p.lineTo(x_right, y_top)
    p.lineTo(x_right, y_low)
    p.close()
    return p


# ---------- recipes (upright space) ----------

def r_I(f):
    """A plain stem as wide as the old one, with the sidebearings of H's stem."""
    I = f.path('I')
    x0, x1 = _hspan(I, f.cap / 2)[0]
    H = f.path('H')
    hx0, hx1, hadv = bounds(H)[0], bounds(H)[2], f.adv('H')
    lsb, rsb = hx0, hadv - hx1
    stem = rect(lsb, 0, lsb + (x1 - x0), f.cap)
    return stem, round(lsb + (x1 - x0) + rsb), lsb - x0


def r_e(f):
    """Cut the lower terminal level, at the height of its inner corner."""
    e = f.path('e')
    rec = DecomposingRecordingPen(f.gs)
    f.gs[f.name('e')].draw(rec)
    pts = []           # (prev_on, prev_offcurve, on) for each segment
    cur = None
    cx = (bounds(e)[0] + bounds(e)[2]) / 2
    xh = f.xh
    cut = None
    # the unslant shear is applied by glyph_path; replay it here on the raw points
    sh = math.tan(math.radians(f.italic))
    un = lambda p: (p[0] - p[1] * sh, p[1])
    for op, args in rec.value:
        if op == 'moveTo':
            cur = un(args[0]); start = cur; last_ctrl = None
        elif op == 'lineTo':
            nxt = un(args[0])
            if (cur[0] > cx and nxt[0] > cx and 0.1 * xh < cur[1] < 0.45 * xh
                    and 0.1 * xh < nxt[1] < 0.45 * xh and abs(cur[1] - nxt[1]) > 5):
                cut = (cur, nxt, last_ctrl)
            cur = nxt; last_ctrl = None
        elif op in ('qCurveTo', 'curveTo'):
            ctrl = [un(a) for a in args if a is not None]
            last_ctrl = ctrl[-2] if len(ctrl) > 1 else cur
            cur = ctrl[-1]
        elif op == 'closePath':
            cur = start
    if cut is None:
        raise ValueError('e: terminal cut not found')
    a, b, _ = cut
    p_in, p_out = (a, b) if a[1] > b[1] else (b, a)
    # tangent of the outer curve arriving at p_out: from the off-curve before it,
    # whichever way the contour runs
    tang = _outer_tangent(rec, p_out, un)
    dy = p_in[1] - p_out[1]
    ext = (p_out[0] + tang[0] / tang[1] * dy, p_in[1])
    patch = polygon(p_in, ext, p_out)
    return union(e, patch), f.adv('e'), 0


def _outer_tangent(rec, p_out, un):
    """Direction (dx, dy>0) of the outer edge where it meets the terminal cut."""
    cur = None
    for op, args in rec.value:
        if op == 'moveTo':
            cur = un(args[0])
            continue
        pts = [un(a) for a in args if a is not None]
        if op in ('qCurveTo', 'curveTo'):
            if _near(pts[-1], p_out):          # curve ends at the tip
                d = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
                return d if d[1] > 0 else (-d[0], -d[1])
            if _near(cur, p_out):              # curve leaves the tip
                d = (pts[0][0] - cur[0], pts[0][1] - cur[1])
                return (-d[0], -d[1]) if d[1] < 0 else d
        if pts:
            cur = pts[-1]
    raise ValueError('e: outer edge not found')


def _near(p, q, tol=0.6):
    return p is not None and abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol


def r_a(f):
    """Flatten the top of the bowl: flat out from the stem, then a tighter corner."""
    a = f.path('a')
    cs = _contours(a)
    if len(cs) != 2:
        return None                            # single-storey (italic): leave it
    inner = min(cs, key=_area)
    ix0, iy0, ix1, iy1 = inner.bounds          # counter
    ox0 = a.bounds[0]                          # outside of the bowl's left side
    # the bowl's top stroke just left of the stem: bottom is the counter top
    spans = [s for s in _vspan(a, ix1 - 4) if abs(s[0] - iy1) < 3]
    if not spans:
        return None
    y_top = spans[0][1]
    # where the counter is widest on the left, and the bowl's outside there
    ys = [iy0 + (iy1 - iy0) * t / 100 for t in range(20, 81)]
    y_mid = min(ys, key=lambda y: _hspan(inner, y)[0][0])
    # where both edges of the top stroke are still flat, going left from the stem
    x_flat = ix1
    x = ix1 - 4
    while x > ix0:
        v = _vspan(a, x)
        top = [s for s in v if s[0] > iy1 - 40 and s[0] < iy1 + 1]
        if not top or abs(top[0][0] - iy1) > 0.5 or abs(top[0][1] - y_top) > 0.5:
            break
        x_flat = x
        x -= 2
    xi = _hspan(inner, y_mid)[0][0]
    xo = _hspan(a, y_mid)[0][0]
    x_ti = ix0 + A_FLAT * (ix1 - ix0)          # counter's flat top starts here
    x_to = x_ti - 0.10 * (ix1 - ix0)           # outside starts turning a little earlier
    x_ti, x_to = min(x_ti, x_flat), min(x_to, x_flat)
    box = rect(ox0 - 10, y_mid, x_flat, y_top)
    q_out = _corner(xo, y_mid, x_to, y_top, x_flat, A_TENSION_OUT)
    q_in = _corner(xi, y_mid, x_ti, iy1, x_flat, A_TENSION)
    out = union(subtract(a, box), subtract(q_out, q_in))
    return out, f.adv('a'), 0


RECIPES = {'I': r_I, 'e': r_e, 'a': r_a}


# ---------- applying to the TTFont ----------

def _put(tt, name, path, width):
    pen = TTGlyphPen(None)
    path.draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
    g = pen.glyph()
    glyf = tt['glyf']
    glyf[name] = g
    g.recalcBounds(glyf)
    tt['hmtx'][name] = (width, getattr(g, 'xMin', 0))


def _shift_composites(tt, base, dx, dadv, new_adv, old_adv):
    """Composites built on `base`: marks move with the stem, the advance follows."""
    glyf, hmtx = tt['glyf'], tt['hmtx']
    classes = {}
    if 'GDEF' in tt and tt['GDEF'].table.GlyphClassDef:
        classes = tt['GDEF'].table.GlyphClassDef.classDefs
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if not g.isComposite() or g.components[0].glyphName != base:
            continue
        for c in g.components[1:]:
            if classes.get(c.glyphName) == 3:   # a mark over or under the stem
                c.x += round(dx)
            else:                               # a following letter, as in IJ
                c.x += dadv
        hmtx[name] = (hmtx[name][0] + dadv, hmtx[name][1])
        g.recalcBounds(glyf)
        hmtx[name] = (hmtx[name][0], getattr(g, 'xMin', 0))


def _shift_anchors(tt, name, dx):
    """Move the GPOS mark-to-base anchors of one glyph sideways."""
    if 'GPOS' not in tt or not dx:
        return
    for lookup in tt['GPOS'].table.LookupList.Lookup:
        subs = lookup.SubTable
        if lookup.LookupType == 9:
            subs = [s.ExtSubTable for s in subs]
        for s in subs:
            if getattr(s, 'LookupType', lookup.LookupType) != 4 or not hasattr(s, 'BaseCoverage'):
                continue
            if name not in s.BaseCoverage.glyphs:
                continue
            rec = s.BaseArray.BaseRecord[s.BaseCoverage.glyphs.index(name)]
            for anc in rec.BaseAnchor:
                if anc is not None:
                    anc.XCoordinate += round(dx)


def modify(tt, font):
    """Apply the recipes to `tt` (a TTFont); `font` is draw.Font on the same file."""
    done = []
    for ch in CHANGED:
        name = font.name(ch)
        r = RECIPES[ch](font)
        if r is None:
            continue
        path, width, dx = r
        old_adv = tt['hmtx'][name][0]
        _put(tt, name, slant(path, font.italic), width)
        if dx or width != old_adv:
            _shift_composites(tt, name, dx, width - old_adv, width, old_adv)
            _shift_anchors(tt, name, dx)
        done.append(name)
    for tag in ('hdmx', 'LTSH', 'VDMX'):
        if tag in tt:
            del tt[tag]
    return done
