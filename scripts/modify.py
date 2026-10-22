"""Reshape Schibsted Grotesk towards odv Grotesk, in place, before the merge.

    I  the top and bottom serifs come off: a plain stem, spaced like the stem of H.
    e  the end of the lower stroke is cut level instead of on a slant, so the
       opening between it and the bar is a horizontal slot.
    a  (two-storey forms only) the top of the bowl runs flat out from the stem
       and turns down in a tighter corner, instead of sloping down to the left.
    c  both terminals cut level, like the e.
    i  the stem a touch heavier than n's (I_STEM); i, í, ï, ij... follow.
    p  the counter moved right until stem and bowl are equally thick at
       mid-height, which also widens the join of bowl and stem.
    ˙  the dot of i and j is a square whose top is level with the top of l.
       It is a little wider than the stem, relatively wider in light weights
       and narrower in heavy ones (as in Akkurat: 1.32 at Light, 1.14 at
       Regular, 1.06 at Bold). It is the same glyph as the dot accent and the
       two dots of the dieresis (ä ö ü ...), so those turn square with it; ï
       has its own outline and is squared the same way.
    f t  in the italics, the upright f and t slanted, instead of the cursive
       forms (f with a descender, t with a hooked foot).

Contrast: Schibsted's heavier weights put nearly all their extra weight into
the verticals, so horizontals look thin next to the stems (in Bold the bar of
e is 0.57 of the stem, Akkurat Bold's 0.73). Where a style's contrast (thin
of o / stem of n) is below CONTRAST, every outline is thinned horizontally,
which narrows verticals and leaves horizontals as they are, until it reaches
it; dots keep their shape. Advances stay, so the letters gain the removed
width as sidebearing. In practice this touches Medium and Bold.

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
CHANGED = ('I', 'ı', 'e', 'a', 'c', 'p', 'uni0307', 'idieresis', 'f', 't')

# the a's bowl: where the flat top ends, as a share of the counter's width from
# the left, and how full the corner is (0.55 is a circle, higher is squarer)
A_FLAT = 0.32
A_TENSION = 0.66
A_TENSION_OUT = 0.58                         # the outside stays rounder, so the corner isn't heavy

# the square dot: width in stems of dotless i, against the stem in thousandths of the em
DOT_SIDE = ((50, 1.32), (85, 1.14), (125, 1.06))

CONTRAST = 0.87          # thin of o / stem of n to aim for (Akkurat Regular 0.86, Bold 0.87)
MIN_ERODE = 5            # font units; below this a style is left alone


# the i's stem, in stems of n (Akkurat's i is a little heavier than its n: 87 vs 85)
I_STEM = 1.06

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


def _level_terminals(f, ch):
    """Cut each slanted terminal of `ch` level, at the height of its inner corner;
    the outer edge is carried on along its own direction to meet the new cut."""
    glyph = f.path(ch)
    rec = DecomposingRecordingPen(f.gs)
    f.gs[f.name(ch)].draw(rec)
    x0, y0, x1, y1 = bounds(glyph)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # glyph_path un-slants with this shear; replay it on the raw points
    sh = math.tan(math.radians(f.italic))
    un = lambda p: (p[0] - p[1] * sh, p[1])
    cuts = []
    cur = start = None
    for op, args in rec.value:
        pts = [un(a) for a in args if a is not None]
        if op == 'moveTo':
            cur = start = pts[0]
            continue
        if op in ('lineTo', 'closePath', 'endPath'):
            nxt = pts[0] if op == 'lineTo' else start
            if (cur[0] > cx and nxt[0] > cx and abs(cur[0] - nxt[0]) > 5
                    and abs(cur[1] - nxt[1]) > 5):
                cuts.append((cur, nxt))
            cur = nxt
        else:
            cur = pts[-1]
    if not cuts:
        raise ValueError(f'{ch}: no slanted terminal found')
    out = glyph
    for a, b in cuts:
        # the inner corner is the one nearer the middle of the letter
        da = math.hypot(a[0] - cx, a[1] - cy)
        db = math.hypot(b[0] - cx, b[1] - cy)
        p_in, p_out = (a, b) if da < db else (b, a)
        tang = _outer_tangent(rec, p_out, un)
        dy = p_in[1] - p_out[1]
        ext = (p_out[0] + tang[0] / tang[1] * dy, p_in[1])
        out = union(out, polygon(p_in, ext, p_out))
    return out


def r_e(f):
    return _level_terminals(f, 'e'), f.adv('e'), 0


def r_c(f):
    return _level_terminals(f, 'c'), f.adv('c'), 0


def _dot_side(f):
    stem = f.hspan('ı', f.xh / 2)[0][1] - 2 * f.erode
    t = stem / f.tt['head'].unitsPerEm * 1000
    pts = DOT_SIDE
    if t <= pts[0][0]:
        k = pts[0][1]
    elif t >= pts[-1][0]:
        k = pts[-1][1]
    else:
        for (a, ka), (b, kb) in zip(pts, pts[1:]):
            if a <= t <= b:
                k = ka + (kb - ka) * (t - a) / (b - a)
    return k * stem


def _square_dots(f, p, above):
    """Replace the round contours of `p` lying above `above` with squares whose
    top is level with the top of l, on the same vertical centre lines."""
    side = _dot_side(f)
    top = f.asc
    out = pathops.Path()
    for c in _contours(p):
        x0, y0, x1, y1 = c.bounds
        if y0 > above and 0.85 < (x1 - x0) / (y1 - y0) < 1.15:
            mx = (x0 + x1) / 2
            c = rect(mx - side / 2, top - side, mx + side / 2, top)
        out = union(out, c)
    return out


def _widen_x(p, d):
    """Thicken `p` horizontally by `d` on each side (exact for straight stems)."""
    return union(p, p.transform(1, 0, 0, 1, -d, 0), p.transform(1, 0, 0, 1, d, 0))


def _i_widen(f):
    stem = f.hspan('ı', f.xh * 0.5)[0][1]
    return max(0.0, (I_STEM * f.V - stem) / 2)


def r_dotlessi(f):
    """The stem of i a touch heavier than n's: next to the round letters, whose
    sides are heavier than the straight stems, an i as thick as n looks thin."""
    return _widen_x(f.path('ı'), _i_widen(f)), f.adv('ı'), 0


def r_p(f):
    """Move the counter of p to the right until the stem and the far side of the
    bowl are equally thick at mid-height; the join of bowl and stem gains the
    same amount."""
    p = f.path('p')
    cs = _contours(p)
    if len(cs) != 2:
        return None
    inner = min(cs, key=_area)
    outer = max(cs, key=_area)
    y = (inner.bounds[1] + inner.bounds[3]) / 2
    spans = _hspan(p, y)
    if len(spans) != 2:
        return None
    left, right = spans[0][1] - spans[0][0], spans[1][1] - spans[1][0]
    s = (right - left) / 2
    if s <= 0.5:
        return None
    return subtract(outer, inner.transform(1, 0, 0, 1, s, 0)), f.adv('p'), 0


def r_dot(f):
    return _square_dots(f, f.path('uni0307'), -BIG), 0, 0


def r_idieresis(f):
    p = _square_dots(f, f.path('idieresis'), f.xh)
    d = _i_widen(f)
    out = pathops.Path()
    for c in _contours(p):
        if c.bounds[1] < f.xh / 2:          # the stem, not the dots
            c = _widen_x(c, d)
        out = union(out, c)
    return out, f.adv('idieresis'), 0


def _from_upright(f, ch):
    """Italic only: the upright letter, brought to the italic's stem weight."""
    up = f.upright
    if up is None:
        return None
    p = up.path(ch)
    extra = (up.V - f.V) / 2
    if extra > 0.5:
        p = erode_x(p, extra)
    old = f.hspan(ch, f.xh * 0.5)[0]
    new = _hspan(p, f.xh * 0.5)[0]
    dx = (new[0] + new[1]) / 2 - (old[0] + old[1] / 2)
    return p, up.adv(ch), dx


def r_f(f):
    return _from_upright(f, 'f')


def r_t(f):
    return _from_upright(f, 't')


# ---------- contrast ----------

def erode_x(p, e):
    """Thin `p` horizontally by `e` on each side: verticals lose 2e, horizontals
    nothing. Exact: a point stays if the horizontal segment of half-length e
    around it lies wholly inside, so the outline minus the region swept by its
    own edges moving e left and right. Each edge is split where it turns
    vertically, so every piece sweeps a simple ribbon."""
    sweep = pathops.Path()
    for kind, seg in _segments(p):
        pieces = ([(kind, seg)] if kind == 'l' else
                  [('q', q) for q in _split_quad_y(*seg)] if kind == 'q' else
                  [('c', c) for c in _split_cubic_y(*seg)])
        for k, sg in pieces:
            r = _ribbon(k, sg, e)
            if r is not None:
                r.draw(sweep.getPen())
    sweep.simplify(fix_winding=True, clockwise=False)
    return subtract(p, sweep)


def _segments(p):
    """Every edge of `p` as ('l'|'q'|'c', points), implied on-curves resolved."""
    from fontTools.pens.basePen import BasePen

    class Seg(BasePen):
        def __init__(self):
            super().__init__(None)
            self.out = []

        def _moveTo(self, pt):
            self.start = pt

        def _lineTo(self, pt):
            a = self._getCurrentPoint()
            if a != pt:
                self.out.append(('l', (a, pt)))

        def _qCurveToOne(self, c, pt):
            self.out.append(('q', (self._getCurrentPoint(), c, pt)))

        def _curveToOne(self, c1, c2, pt):
            self.out.append(('c', (self._getCurrentPoint(), c1, c2, pt)))

        def _closePath(self):
            a = self._getCurrentPoint()
            if a != self.start:
                self.out.append(('l', (a, self.start)))

        _endPath = _closePath

    pen = Seg()
    p.draw(pen)
    return pen.out


def _sh(pt, d):
    return (pt[0] + d, pt[1])


def _ribbon(kind, seg, e):
    a, b = seg[0], seg[-1]
    if abs(a[1] - b[1]) < 1e-6 and all(abs(q[1] - a[1]) < 1e-6 for q in seg):
        return None                                   # horizontal: sweeps no area
    r = pathops.Path()
    pen = r.getPen()
    pen.moveTo(_sh(a, -e))
    if kind == 'l':
        pen.lineTo(_sh(b, -e))
        pen.lineTo(_sh(b, e))
        pen.lineTo(_sh(a, e))
    elif kind == 'q':
        pen.qCurveTo(_sh(seg[1], -e), _sh(b, -e))
        pen.lineTo(_sh(b, e))
        pen.qCurveTo(_sh(seg[1], e), _sh(a, e))
    else:
        pen.curveTo(_sh(seg[1], -e), _sh(seg[2], -e), _sh(b, -e))
        pen.lineTo(_sh(b, e))
        pen.curveTo(_sh(seg[2], e), _sh(seg[1], e), _sh(a, e))
    pen.closePath()
    r.simplify(fix_winding=True, clockwise=False)
    return r


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _split_quad_y(a, c, b):
    d = a[1] - 2 * c[1] + b[1]
    if abs(d) > 1e-9:
        t = (a[1] - c[1]) / d
        if 1e-4 < t < 1 - 1e-4:
            ac, cb = _lerp(a, c, t), _lerp(c, b, t)
            m = _lerp(ac, cb, t)
            return [(a, ac, m), (m, cb, b)]
    return [(a, c, b)]


def _split_cubic_y(p0, p1, p2, p3):
    # roots of the y-derivative
    a = -p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]
    b = 2 * (p0[1] - 2 * p1[1] + p2[1])
    c = p1[1] - p0[1]
    ts = []
    if abs(a) < 1e-9:
        if abs(b) > 1e-9:
            ts = [-c / b]
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            r = math.sqrt(disc)
            ts = [(-b - r) / (2 * a), (-b + r) / (2 * a)]
    ts = sorted(t for t in ts if 1e-4 < t < 1 - 1e-4)
    out, seg, t0 = [], (p0, p1, p2, p3), 0.0
    for t in ts:
        u = (t - t0) / (1 - t0)
        q0, q1, q2, q3 = seg
        a1, b1, c1 = _lerp(q0, q1, u), _lerp(q1, q2, u), _lerp(q2, q3, u)
        d1, e1 = _lerp(a1, b1, u), _lerp(b1, c1, u)
        m = _lerp(d1, e1, u)
        out.append((q0, a1, d1, m))
        seg, t0 = (m, e1, c1, q3), t
    out.append(seg)
    return out


def _inside(a, b):
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def _erode_glyph(p, e, stem):
    cs = _contours(p)
    bbs = [c.bounds for c in cs]
    dots = []
    for i, (c, b) in enumerate(zip(cs, bbs)):
        w, h = b[2] - b[0], b[3] - b[1]
        alone = not any(j != i and (_inside(bbs[j], b) or _inside(b, bbs[j]))
                        for j in range(len(cs)))
        if alone and h > 0 and 0.75 < w / h < 1.33 and max(w, h) < 2.4 * stem:
            dots.append(c)
    body = subtract(p, union(*dots)) if dots else p
    out = erode_x(body, e)
    return union(out, *dots) if dots else out


def erosion(f):
    """How much to thin this style's verticals on each side, in font units."""
    e = (f.V - f.H / CONTRAST) / 2
    return e if e >= MIN_ERODE else 0


def _erode_all(tt, f, e):
    gs = tt.getGlyphSet()
    glyf, hmtx = tt['glyf'], tt['hmtx']
    n = 0
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if name == '.notdef' or g.isComposite() or g.numberOfContours <= 0:
            continue
        p = glyph_path(gs, name, unslant=f.italic)
        _put(tt, name, slant(_erode_glyph(p, e, f.V), f.italic), hmtx[name][0])
        n += 1
    return n


def _strip_hinting(tt):
    """The TrueType instructions refer to the old points; drop them all."""
    from fontTools.ttLib.tables import ttProgram
    for tag in ('fpgm', 'prep', 'cvt '):
        if tag in tt:
            del tt[tag]
    glyf = tt['glyf']
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if hasattr(g, 'program'):
            g.program = ttProgram.Program()
            g.program.fromBytecode(b'')
    if 'gasp' in tt:
        tt['gasp'].gaspRange = {0xFFFF: 0x000F}


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


RECIPES = {'I': r_I, 'ı': r_dotlessi, 'p': r_p, 'e': r_e, 'a': r_a, 'c': r_c, 'uni0307': r_dot,
           'idieresis': r_idieresis, 'f': r_f, 't': r_t}


# ---------- applying to the TTFont ----------

def _tidy(path):
    """Boolean operations leave flat runs as strings of tiny curves; turn curves
    with a control point on their chord into lines and merge collinear lines."""
    from fontTools.pens.recordingPen import RecordingPen
    rec = RecordingPen()
    path.draw(rec)
    out = []

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def flat(a, b, c):
        d = math.hypot(c[0] - a[0], c[1] - a[1]) or 1
        return abs(cross(a, b, c)) / d < 0.3

    cur = start = None
    for op, args in rec.value:
        if op == 'moveTo':
            cur = start = args[0]
            out.append((op, args))
            continue
        if op == 'qCurveTo' and len(args) == 2 and flat(cur, args[0], args[1]):
            op, args = 'lineTo', (args[1],)
        if op == 'curveTo' and flat(cur, args[0], args[2]) and flat(cur, args[1], args[2]):
            op, args = 'lineTo', (args[2],)
        if (op == 'lineTo' and out and out[-1][0] == 'lineTo' and len(out) >= 2
                and flat(_last_pt(out[:-1]), out[-1][1][0], args[0])):
            out[-1] = (op, args)           # extend the previous line
        else:
            out.append((op, args))
        if op in ('closePath', 'endPath'):
            cur = start
        elif args:
            cur = args[-1]
    return out


def _last_pt(ops):
    for op, args in reversed(ops):
        if args:
            return args[-1]


def _put(tt, name, path, width):
    pen = TTGlyphPen(None)
    cpen = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
    for op, args in _tidy(path):
        getattr(cpen, op)(*args)
    g = pen.glyph()
    glyf = tt['glyf']
    glyf[name] = g
    g.recalcBounds(glyf)
    tt['hmtx'][name] = (width, getattr(g, 'xMin', 0))


def _shift_composites(tt, base, dx, dadv):
    """Composites using `base` (accented letters, IJ, ligatures): marks move with
    the letter they sit on, letters after each `base` move by the change in its
    advance."""
    glyf, hmtx = tt['glyf'], tt['hmtx']
    classes = {}
    if 'GDEF' in tt and tt['GDEF'].table.GlyphClassDef:
        classes = tt['GDEF'].table.GlyphClassDef.classDefs
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if not g.isComposite() or not any(c.glyphName == base for c in g.components):
            continue
        acc = 0            # advance gained by the bases so far
        on = 0             # shift of the letter the next mark sits on
        for c in g.components:
            if c.glyphName == base:
                c.x += acc
                on = acc + dx
                acc += dadv
            elif classes.get(c.glyphName) == 3:
                c.x += round(on)
            else:
                c.x += acc
                on = acc
        g.recalcBounds(glyf)
        hmtx[name] = (hmtx[name][0] + acc, getattr(g, 'xMin', 0))


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


def _upright_of(src):
    from pathlib import Path
    import draw
    p = Path(src)
    style = p.stem.split('-')[-1]
    if 'Italic' not in style:
        return None
    up = style.replace('Italic', '') or 'Regular'
    return draw.Font(p.with_name(p.stem.rsplit('-', 1)[0] + f'-{up}{p.suffix}'))


def modify(tt, font, src=None):
    """Apply the recipes, then the contrast correction, to `tt` (a TTFont);
    `font` is draw.Font on the same file `src`."""
    font.erode = erosion(font)
    font.upright = _upright_of(src) if src else None
    done = []
    for ch in CHANGED:
        name = font.name(ch)
        r = RECIPES[ch](font)
        if r is None:
            continue
        path, width, dx = r
        old_adv = tt['hmtx'][name][0]
        _put(tt, name, slant(path, font.italic), width)
        if round(dx) or width != old_adv:
            _shift_composites(tt, name, dx, width - old_adv)
            _shift_anchors(tt, name, dx)
        done.append(name)
    if font.erode:
        _erode_all(tt, font, font.erode)
        _strip_hinting(tt)
        done.append(f'contrast: verticals thinned by {2 * font.erode:.0f} units')
    for tag in ('hdmx', 'LTSH', 'VDMX'):
        if tag in tt:
            del tt[tag]
    return done
