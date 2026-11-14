"""Reshape Schibsted Grotesk towards odv Grotesk, in place, before the merge.

    I  the top and bottom serifs come off: a plain stem, spaced like the stem of H.
    e  the end of the lower stroke is cut level instead of on a slant, so the
       opening between it and the bar is a horizontal slot.
    a  (two-storey forms only) the top of the bowl runs flat out from the stem
       and turns down in a rounder corner, instead of sloping down to the left.
       The corner is curvature-continuous (scripts/fair.py): the bend eases in
       from the flat and out into the bowl, with no point where it visibly
       starts (issue #19). The terminal at the top is cut level, at the height
       of its tip (A_TERMINAL), instead of on a slant.
    c  both terminals cut level, like the e.
    s  both terminals cut level at the height of their inner corners, like e and
       c, instead of on a slant; the spine is left as it is.
    i j  the stem a touch heavier than n's (I_STEM), the same in both, since
       they share the dot and usually stand together; í, ï, ĵ, ij, ι and the
       fi ligatures follow.
    p  the counter moved right until stem and bowl are equally thick at
       mid-height, which also widens the join of bowl and stem.
    ! ? ¡ ¿ .  their dots squares like the dot of i, the same size; : ; … · ŀ
       and the tabular forms are made of the full stop and follow.
    , ‘ “  a square head the size of the full stop's dot and a straight tail
       leaning left, cut level; ; ’ ” ‚ „ ʼ ŉ are made of the comma and follow.
    z E F T Z L H  where the stems are thinned (see Contrast), the straight bars
       back to Schibsted's proportion to the stem, so these letters are not darker
       than their neighbours.
    ˙  the dot of i and j is a square whose top is level with the top of l.
       It overhangs the stem by the same amount on each side in every weight
       (DOT_OVERHANG), so it is relatively wider in light weights and closer
       to the stem in heavy ones. It is the same glyph as the dot accent and the
       two dots of the dieresis (ä ö ü ...), so those turn square with it; ï
       has its own outline and is squared the same way.
    f t  in the italics, the upright f and t slanted, instead of the cursive
       forms (f with a descender, t with a hooked foot).

Contrast: Schibsted's heavier weights put nearly all their extra weight into
the verticals, so horizontals look thin next to the stems (in Bold the bar of
e is 0.57 of the stem, against 0.81 in Regular). Where a style's contrast (thin
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
import array
import math

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.misc.roundTools import otRound
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

from geometry import (bounds, glyph_path, intersect, move, polygon, rect, simplify, slant,
                      subtract, transform, union)
import pathops

import fair

BIG = 10000
CHANGED = ('I', 'ı', 'ȷ', 'e', 'a', 'c', 's', 'p', 'uni0307', 'idieresis', 'f', 't', 'z', 'E', 'F', 'T', 'Z', 'L', 'H',
           '!', '?', '¡', '¿', 'exclamdown.case', 'questiondown.case', '.', ',', '‘', '“')

# the a's bowl: where the flat top starts, as a share of the counter's width from
# the left, for the counter and for the outside. The outside reaches further, so
# it is squarer than the counter, and starts 0.10 of the counter earlier, so the
# two flats begin together (issue #19).
A_FLAT_IN = 0.65
A_FLAT_OUT = 0.75

# the a's top terminal is cut level: at the height of its outer corner (1.0), of its
# inner corner (0.0, as e c s), or between. 1.0 keeps the tip where it is and takes
# the slanted wedge off under it.
A_TERMINAL = 1.0

# the square dot overhangs the stem of dotless i by this much on each side, in
# 2048ths of the em, in every weight: 192 units wide in Regular, 276 in Bold.
DOT_OVERHANG = 12

# thin of o / stem of n to aim for: about the contrast Schibsted drew its own Italic
# with (0.86; Regular has 0.83, Bold 0.73), where bars and stems read as one weight
CONTRAST = 0.87
MIN_ERODE = 5            # font units; below this a style is left alone


# the stem of i and j, in stems of n: a touch heavier, so they don't read thin next to
# round letters. 1.024 looked thin beside n and l; at 1.06 the i stood visibly heavier
# than l and the f of fi beside it (issue #5).
I_STEM = 1.045

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


def _bez(kind, P, t):
    """Point, first and second derivative of a line, quadratic or cubic at t."""
    mt = 1 - t
    if kind == 'l':
        d = (P[1][0] - P[0][0], P[1][1] - P[0][1])
        return (P[0][0] + t * d[0], P[0][1] + t * d[1]), d, (0.0, 0.0)
    if kind == 'q':
        pt = tuple(mt * mt * P[0][k] + 2 * mt * t * P[1][k] + t * t * P[2][k] for k in (0, 1))
        d1 = tuple(2 * (mt * (P[1][k] - P[0][k]) + t * (P[2][k] - P[1][k])) for k in (0, 1))
        d2 = tuple(2 * (P[2][k] - 2 * P[1][k] + P[0][k]) for k in (0, 1))
        return pt, d1, d2
    pt = tuple(mt ** 3 * P[0][k] + 3 * mt * mt * t * P[1][k] + 3 * mt * t * t * P[2][k]
               + t ** 3 * P[3][k] for k in (0, 1))
    d1 = tuple(3 * (mt * mt * (P[1][k] - P[0][k]) + 2 * mt * t * (P[2][k] - P[1][k])
                    + t * t * (P[3][k] - P[2][k])) for k in (0, 1))
    d2 = tuple(6 * (mt * (P[2][k] - 2 * P[1][k] + P[0][k]) + t * (P[3][k] - 2 * P[2][k] + P[1][k]))
               for k in (0, 1))
    return pt, d1, d2


def _curvature(kind, P, t):
    _, d1, d2 = _bez(kind, P, t)
    sp = math.hypot(*d1)
    return abs(d1[0] * d2[1] - d1[1] * d2[0]) / sp ** 3, sp


def _bowl_side(contour, y_lo, y_hi):
    """The leftmost point of a contour between two heights, where the a's corner
    takes over from the bowl, with the bowl's curvature there and the rate it
    changes at going up (so the corner can continue both). Read from the
    outline's own segments; a point within 0.1 % of a segment's end is the node."""
    segs = _segments(contour)
    best = None
    for i, (kind, P) in enumerate(segs):
        ts = [0.0, 1.0]
        if kind == 'q':
            den = P[0][0] - 2 * P[1][0] + P[2][0]
            if abs(den) > 1e-9:
                ts.append((P[0][0] - P[1][0]) / den)
        elif kind == 'c':                       # x'(t) = 0: a t^2 + b t + c
            a = -P[0][0] + 3 * P[1][0] - 3 * P[2][0] + P[3][0]
            b = 2 * (P[0][0] - 2 * P[1][0] + P[2][0])
            c = P[1][0] - P[0][0]
            if abs(a) > 1e-9:
                disc = b * b - 4 * a * c
                if disc >= 0:
                    ts += [(-b + sg * math.sqrt(disc)) / (2 * a) for sg in (1, -1)]
            elif abs(b) > 1e-9:
                ts.append(-c / b)
        for t in ts:
            if not 0 <= t <= 1:
                continue
            t = 0.0 if t < 1e-3 else 1.0 if t > 1 - 1e-3 else t
            pt = _bez(kind, P, t)[0]
            if y_lo <= pt[1] <= y_hi and (best is None or pt[0] < best[0][0] - 1e-6):
                best = (pt, i, t)
    pt, i, t = best
    # the piece of outline just below that point: in the same segment, or in a neighbour
    cands = [(i, t)]
    if t == 0.0:
        cands.append(((i - 1) % len(segs), 1.0))
    if t == 1.0:
        cands.append(((i + 1) % len(segs), 0.0))
    below = []
    for j, tj in cands:
        kind, P = segs[j]
        for step in (-0.01, 0.01):
            if 0 <= tj + step <= 1:
                y = _bez(kind, P, tj + step)[0][1]
                if y < pt[1]:
                    below.append((y, j, tj, step))
    _, j, tj, step = min(below)
    kind, P = segs[j]
    if kind == 'l':
        return pt, 0.0, 0.0
    k0, sp = _curvature(kind, P, tj)
    k1, _ = _curvature(kind, P, tj + step * 0.1)
    return pt, k0, (k0 - k1) / (abs(step) * 0.1 * sp)


def _flat_start(contour, y):
    """Left end of the contour's horizontal straight edge at height y that runs
    furthest right (the top of the a's bowl, into the stem)."""
    lines = [(max(P[0][0], P[1][0]), min(P[0][0], P[1][0])) for kind, P in _segments(contour)
             if kind == 'l' and abs(P[0][1] - y) < 1e-6 and abs(P[1][1] - y) < 1e-6]
    return max(lines)[1]


def _corner(x_side, y_low, x_top, y_top, x_right, k_side, dk_side):
    """Region under a rounded corner: up the side from (x_side, y_low), round
    into the top at (x_top, y_top), flat to x_right, down and back. The corner
    is fair.corner: it continues the side's curvature and its rate of change,
    and eases out to none into the top."""
    p = pathops.Path()
    p.moveTo(x_side, y_low)
    for seg in fair.corner(x_top - x_side, y_top - y_low, k_side, dk_side):
        p.cubicTo(*[v for x, y in seg for v in (x + x_side, y + y_low)])
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


def _terminal_cuts(f, ch, select=None):
    """The slanted terminal cuts of `ch`, in upright space, as (inner corner, outer
    corner, direction of the outer edge at the outer corner). By default the cuts
    on the right half of the letter (e, c); `select(a, b, bounds)` picks others."""
    glyph = f.path(ch)
    rec = DecomposingRecordingPen(f.gs)
    f.gs[f.name(ch)].draw(rec)
    bb = bounds(glyph)
    x0, y0, x1, y1 = bb
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if select is None:
        select = lambda a, b, bb: a[0] > cx and b[0] > cx
    # glyph_path un-slants with this shear; replay it on the raw points
    sh = math.tan(math.radians(f.italic))
    un = lambda p: (p[0] - p[1] * sh, p[1])
    found = []
    cur = start = None
    for op, args in rec.value:
        pts = [un(a) for a in args if a is not None]
        if op == 'moveTo':
            cur = start = pts[0]
            continue
        if op in ('lineTo', 'closePath', 'endPath'):
            nxt = pts[0] if op == 'lineTo' else start
            if (abs(cur[0] - nxt[0]) > 5 and abs(cur[1] - nxt[1]) > 5
                    and select(cur, nxt, bb)):
                found.append((cur, nxt))
            cur = nxt
        else:
            cur = pts[-1]
    if not found:
        raise ValueError(f'{ch}: no slanted terminal found')
    cuts = []
    for a, b in found:
        # the inner corner is the one nearer the middle of the letter
        da = math.hypot(a[0] - cx, a[1] - cy)
        db = math.hypot(b[0] - cx, b[1] - cy)
        p_in, p_out = (a, b) if da < db else (b, a)
        cuts.append((p_in, p_out, _outer_tangent(rec, p_out, un)))
    return cuts


def _cut_level(glyph, p_in, p_out, tang, at=0.0):
    """Recut one slanted terminal level. `at` places the new cut between the height
    of the inner corner (0) and of the outer corner (1). Below the outer corner the
    outer edge is carried on along its own direction to the new cut; above the
    inner corner what lies beyond the new cut is taken off, up to the inner edge."""
    y_in, y_out = p_in[1], p_out[1]
    y = y_in + at * (y_out - y_in)
    on_cut = lambda yy: p_out[0] + (p_in[0] - p_out[0]) * (yy - y_out) / (y_in - y_out)
    out = glyph
    if at < 1:                                  # outer edge carried on to the cut
        ext = (p_out[0] + tang[0] / tang[1] * (y - y_out), y)
        out = union(out, polygon((on_cut(y), y), ext, p_out))
    if at > 0:                                  # the inner corner trimmed back to it
        d = math.copysign(BIG, p_in[0] - p_out[0])
        band = polygon((on_cut(y), y), p_in, (p_in[0] + d, y_in), (p_in[0] + d, y))
        # only the piece at this terminal, not other strokes the band crosses
        for piece in _contours(intersect(out, band)):
            px0, py0, px1, py1 = piece.bounds
            if px0 - 1 <= p_in[0] <= px1 + 1 and py0 - 1 <= p_in[1] <= py1 + 1:
                out = subtract(out, piece)
    return out


def _level_terminals(f, ch, select=None, at=0.0, glyph=None):
    """Cut the slanted terminals of `ch` level (_cut_level), by default at the height
    of the inner corner, the outer edge carried on along its own direction."""
    out = glyph if glyph is not None else f.path(ch)
    for p_in, p_out, tang in _terminal_cuts(f, ch, select):
        out = _cut_level(out, p_in, p_out, tang, at)
    return out


def _at_side(a, b, bb):
    """A terminal cut that reaches the left or right side of the letter (s, and the
    a's top), not a straight piece of a spine."""
    x0, _, x1, _ = bb
    tol = 0.06 * (x1 - x0)
    return min(abs(p[0] - x) for p in (a, b) for x in (x0, x1)) < tol


def r_e(f):
    return _level_terminals(f, 'e'), f.adv('e'), 0


def r_c(f):
    return _level_terminals(f, 'c'), f.adv('c'), 0


def r_s(f):
    """Both terminals cut level at the height of their inner corners, as in e and c."""
    return _level_terminals(f, 's', _at_side), f.adv('s'), 0


def _dot_side(f):
    stem = f.hspan('ı', f.xh / 2)[0][1] - 2 * f.erode
    return stem + 2 * DOT_OVERHANG * f.tt['head'].unitsPerEm / 2048


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


def _i_widen(f, ch='ı'):
    """How much to add on each side of the stem of `ch` for I_STEM stems of n,
    measured after the contrast correction thins both by 2 * f.erode."""
    stem = f.hspan(ch, f.xh * 0.5)[0][1]
    e2 = 2 * f.erode
    return max(0.0, (I_STEM * (f.V - e2) + e2 - stem) / 2)


def r_dotlessi(f):
    """The stem of i a touch heavier than n's: next to the round letters, whose
    sides are heavier than the straight stems, an i as thick as n looks thin."""
    return _widen_x(f.path('ı'), _i_widen(f)), f.adv('ı'), 0


def r_dotlessj(f):
    """j's stem as heavy as i's, so ij and the dots above them match."""
    return _widen_x(f.path('ȷ'), _i_widen(f, 'ȷ')), f.adv('ȷ'), 0


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


def _square_points(f, ch):
    """The round dot of ! ? ¡ ¿ . made a square like the dot of i: the same size,
    on the same vertical centre line; on the baseline where the dot sat on it."""
    side = _dot_side(f)
    stem = f.V
    out = pathops.Path()
    for c in _contours(f.path(ch)):
        x0, y0, x1, y1 = c.bounds
        w, h = x1 - x0, y1 - y0
        if 0.85 < w / h < 1.15 and w < 2.2 * stem:
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            bottom = 0 if abs(y0) < 0.25 * stem else my - side / 2
            c = rect(mx - side / 2, bottom, mx + side / 2, bottom + side)
        out = union(out, c)
    return out, f.adv(ch), 0


BARRED = ('z', 'E', 'F', 'T', 'Z', 'L', 'H')
BAR_SAMPLES = (0.06, 0.12, 0.5, 0.75, 0.88, 0.94)   # where across the letter to look for bars


def r_bars(f, ch):
    """The straight horizontal bars of z E F T Z L H back to Schibsted's proportion
    to the stem once the contrast correction has thinned the stems: the bars are
    horizontal and not thinned, so in Bold they came out as heavy as the stems.
    A bar on the baseline or at the top keeps its outer edge and its inner edge
    moves in; a middle bar thins about its centre line. Corners slide along a
    slanted neighbour (the diagonal of z and Z), so it keeps its angle."""
    e = getattr(f, 'erode', 0) or 0
    if e <= 0:
        return None
    p = f.path(ch)
    segs = [(k, P) for c in _contours(p) for k, P in _segments(c)]
    if any(k != 'l' for k, _ in segs):
        return None                            # only straight letters
    x0, y0, x1, y1 = p.bounds
    h = y1 - y0
    levels = {round(P[0][1], 3) for k, P in segs if abs(P[0][1] - P[1][1]) < 1e-6}
    k = (f.V - 2 * e) / f.V
    moves = {}
    for fx in BAR_SAMPLES:
        for a, b in _vspan(p, x0 + fx * (x1 - x0)):
            t = b - a
            if t > 0.4 * h or round(a, 3) not in levels or round(b, 3) not in levels:
                continue                       # a stem, or not a straight bar
            d = t * (1 - k)
            if abs(b - y1) < 0.5:              # at the top: the lower edge moves up
                moves[round(a, 3)] = a + d
            elif abs(a - y0) < 0.5:            # on the baseline: the upper edge moves down
                moves[round(b, 3)] = b - d
            else:                              # in the middle: both, about its centre
                moves[round(a, 3)] = a + d / 2
                moves[round(b, 3)] = b - d / 2
    if not moves:
        return None
    out = pathops.Path()
    pen = out.getPen()
    for c in _contours(p):
        pts = [P[0] for kk, P in _segments(c)]
        n = len(pts)
        new = []
        for i, q in enumerate(pts):
            y_new = moves.get(round(q[1], 3))
            if y_new is None:
                new.append(q)
                continue
            slanted = [r for r in (pts[i - 1], pts[(i + 1) % n])
                       if abs(r[1] - q[1]) > 0.5 and abs(r[0] - q[0]) > 0.5]
            if slanted:                        # slide along the diagonal
                r = slanted[0]
                t = (y_new - q[1]) / (r[1] - q[1])
                new.append((q[0] + t * (r[0] - q[0]), y_new))
            else:
                new.append((q[0], y_new))
        pen.moveTo(new[0])
        for q in new[1:]:
            pen.lineTo(q)
        pen.closePath()
    return out, f.adv(ch), 0


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

BLEND_SPAN = 2.5         # an extreme's blend reaches this many e to either side
ROUND_CROSSINGS = False  # round off the short flats at inside corners that involve a curve
ROUND_SPAN = 1.5         # how far back (in e) a rounded crossing starts on each side


def _casteljau(P, u):
    """Split a Bezier at u (any u, also outside 0..1): the parts before and after."""
    pts = [tuple(q) for q in P]
    left, right = [pts[0]], [pts[-1]]
    while len(pts) > 1:
        pts = [((1 - u) * a[0] + u * b[0], (1 - u) * a[1] + u * b[1]) for a, b in zip(pts, pts[1:])]
        left.append(pts[0])
        right.append(pts[-1])
    return left, right[::-1]


def _meet_line(kind, Q, L0, t, at_end):
    """The curve Q cut, or carried on, at its end (at_end) or start to where it
    crosses the line through L0 along t; None if it does not get there."""
    def g(u):
        pt = _bez(kind, Q, u)[0]
        return (pt[0] - L0[0]) * t[1] - (pt[1] - L0[1]) * t[0]
    u = 1.0 if at_end else 0.0
    for _ in range(40):
        gu = g(u)
        h = 1e-6
        dg = (g(u + h) - gu) / h
        if abs(dg) < 1e-12:
            return None
        step = gu / dg
        u -= step
        if abs(step) < 1e-10:
            break
    if not (-0.5 < u < 1.5) or abs(g(u)) > 1e-3:
        return None
    left, right = _casteljau(Q, u)
    return left if at_end else right


def _meet_curves(ka, A, kb, B):
    """Parameters (u, v) where curve A near its end crosses curve B near its start,
    carried on past the ends if need be; None if they do not meet."""
    u, v = 1.0, 0.0
    for _ in range(50):
        pa, pb = _bez(ka, A, u)[0], _bez(kb, B, v)[0]
        r = (pa[0] - pb[0], pa[1] - pb[1])
        if math.hypot(*r) < 1e-7:
            break
        _, da, _ = _bez(ka, A, u)
        _, db, _ = _bez(kb, B, v)
        det = -da[0] * db[1] + da[1] * db[0]   # Jacobian [da, -db]
        if abs(det) < 1e-12:
            return None
        du = (-r[0] * -db[1] + r[1] * -db[0]) / det
        dv = (-da[0] * r[1] + da[1] * r[0]) / det
        u, v = u + du, v + dv
    pa, pb = _bez(ka, A, u)[0], _bez(kb, B, v)[0]
    if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) > 1e-3 or not (0.2 < u < 1.6 and -0.6 < v < 0.8):
        return None
    return u, v


def _h_extremes(kind, P):
    """Parameters inside a curve where its tangent is horizontal."""
    ys = [q[1] for q in P]
    if kind == 'q':
        den = ys[0] - 2 * ys[1] + ys[2]
        ts = [(ys[0] - ys[1]) / den] if abs(den) > 1e-12 else []
    elif kind == 'c':
        a = -ys[0] + 3 * ys[1] - 3 * ys[2] + ys[3]
        b = 2 * (ys[0] - 2 * ys[1] + ys[2])
        c = ys[1] - ys[0]
        if abs(a) > 1e-12:
            disc = b * b - 4 * a * c
            ts = [(-b + sg * math.sqrt(disc)) / (2 * a) for sg in (1, -1)] if disc >= 0 else []
        else:
            ts = [-c / b] if abs(b) > 1e-12 else []
    else:
        ts = []
    return sorted(t for t in ts if 1e-3 < t < 1 - 1e-3)


def _jet(kind, P, u):
    """Point, unit tangent and signed curvature at u."""
    pt, d1, d2 = _bez(kind, P, u)
    sp = math.hypot(*d1)
    if sp < 1e-9:
        u2 = u + (1e-4 if u < 0.5 else -1e-4)
        pt2, d1, d2 = _bez(kind, P, u2)
        sp = math.hypot(*d1)
    return pt, (d1[0] / sp, d1[1] / sp), (d1[0] * d2[1] - d1[1] * d2[0]) / sp ** 3


def _tangent_at(kind, P, at_end):
    return _jet(kind, P, 1.0 if at_end else 0.0)[1]


def erode_x(p, e):
    """Thin `p` horizontally by `e` on each side: verticals lose 2e, horizontals
    nothing. Each piece of outline between horizontal tangents moves sideways by
    e, inward, as a whole, so its shape and curvature are kept exactly and the
    weights are those of thinning by e everywhere (the region a horizontal segment
    of half-length e fits in). Where that would break the outline (issue #19):

      - at the top and bottom of a round the two halves, moved towards each
        other, would cross in a point, and at the top and bottom of a counter,
        moved apart, they would leave a flat: there both halves are cut back about
        BLEND_SPAN e from the extreme and joined by a curve that matches their
        position, direction and curvature;
      - where a curve meets a slanted straight edge (a terminal cut), the edge
        moves by its own e and the curve is cut or carried on to meet it, so the
        cut keeps its angle;
      - a horizontal straight edge just follows the pieces at its ends."""
    p = simplify(p)                            # no overlaps; ink to the left of every contour
    out = pathops.Path()
    pen = out.getPen()
    for contour in _contours(p):
        pieces = []
        for kind, P in _segments(contour):    # split curves at their horizontal tangents
            P = [tuple(q) for q in P]
            last = 0.0
            for t in _h_extremes(kind, P):
                u = (t - last) / (1 - last)
                a, P = _casteljau(P, u)
                pieces.append((kind, a))
                last = t
            pieces.append((kind, P))
        n = len(pieces)
        if n == 0:
            continue

        def shift_of(piece):
            kind, P = piece
            _, t, _ = _jet(kind, P, 0.5)
            if abs(t[1]) < 1e-9:
                return None                    # horizontal: follows its neighbours
            return -e if t[1] > 0 else e       # outward normal (ty, -tx)

        sh = [shift_of(pc) for pc in pieces]
        moved = [(k, [(q[0] + (s or 0.0), q[1]) for q in P]) for (k, P), s in zip(pieces, sh)]
        blends = {}                            # node index -> cubic joining the two sides
        for i in range(n):
            a, b = (i - 1) % n, i
            sa, sb = sh[a], sh[b]
            ka, Pa = moved[a]
            kb, Pb = moved[b]
            if sa is None and sb is None:
                continue
            if sa is None or sb is None:       # a horizontal edge follows the other side
                if sa is None:
                    Pa[-1] = Pb[0]
                else:
                    Pb[0] = Pa[-1]
                continue
            if sa == sb:
                continue
            ta = _tangent_at(pieces[a][0], pieces[a][1], True)
            tb = _tangent_at(pieces[b][0], pieces[b][1], False)
            cr = ta[0] * tb[1] - ta[1] * tb[0]
            dot = ta[0] * tb[0] + ta[1] * tb[1]
            if abs(cr) < 0.035 and dot > 0 and ka != 'l' and kb != 'l':
                # an extreme of a round or a counter: cut both sides back, blend
                D = BLEND_SPAN * e
                cut = []
                for k, P, at_end in ((ka, Pa, True), (kb, Pb, False)):
                    x_node = P[-1][0] if at_end else P[0][0]
                    span = abs(P[-1][0] - P[0][0])
                    want = min(D, 0.6 * span)
                    lo, hi = (0.0, 1.0)
                    for _ in range(50):        # parameter at that horizontal distance
                        mid = (lo + hi) / 2
                        dx = abs(_bez(k, P, mid)[0][0] - x_node)
                        if at_end:
                            lo, hi = (mid, hi) if dx > want else (lo, mid)
                        else:
                            lo, hi = (lo, mid) if dx > want else (mid, hi)
                    cut.append((lo + hi) / 2)
                ua, ub = cut
                Pa2 = _casteljau(Pa, ua)[0]
                Pb2 = _casteljau(Pb, ub)[1]
                p0, t0, k0 = _jet(ka, Pa2, 1.0)
                p3, t1, k1 = _jet(kb, Pb2, 0.0)
                chord = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
                a0, a1 = fair.cubic_g2(p0, t0, k0, p3, t1, k1, chord / 3)
                blends[i] = ('c', ((p0[0] + a0 * t0[0], p0[1] + a0 * t0[1]),
                                   (p3[0] - a1 * t1[0], p3[1] - a1 * t1[1]), p3))
                moved[a] = (ka, Pa2)
                moved[b] = (kb, Pb2)
                continue
            # a corner whose sides move differently
            if cr < 0:
                # an inside corner (a notch, a crotch): the white widens by e on
                # each side, so the two moved sides are joined by a short flat,
                # or, where a curve is involved and ROUND_CROSSINGS is on, both
                # sides are cut back a little and joined by a smooth curve
                if ROUND_CROSSINGS and (ka != 'l' or kb != 'l'):
                    D = ROUND_SPAN * e
                    us = []
                    for k, P, at_end in ((ka, Pa, True), (kb, Pb, False)):
                        end_pt = P[-1] if at_end else P[0]
                        want = min(D, 0.45 * math.hypot(P[-1][0] - P[0][0], P[-1][1] - P[0][1]))
                        lo, hi = 0.0, 1.0
                        for _ in range(50):
                            mid = (lo + hi) / 2
                            q = _bez(k, P, mid)[0]
                            dd = math.hypot(q[0] - end_pt[0], q[1] - end_pt[1])
                            if at_end:
                                lo, hi = (mid, hi) if dd > want else (lo, mid)
                            else:
                                lo, hi = (lo, mid) if dd > want else (mid, hi)
                        us.append((lo + hi) / 2)
                    Pa2 = _casteljau(Pa, us[0])[0]
                    Pb2 = _casteljau(Pb, us[1])[1]
                    p0, t0, k0 = _jet(ka, Pa2, 1.0)
                    p3, t1, k1 = _jet(kb, Pb2, 0.0)
                    chord = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
                    a0, a1 = fair.cubic_g2(p0, t0, k0, p3, t1, k1, chord / 3)
                    blends[i] = ('c', ((p0[0] + a0 * t0[0], p0[1] + a0 * t0[1]),
                                       (p3[0] - a1 * t1[0], p3[1] - a1 * t1[1]), p3))
                    moved[a] = (ka, Pa2)
                    moved[b] = (kb, Pb2)
                else:
                    blends[i] = ('l', Pb[0])
                continue
            if ka == 'l' and kb == 'l':        # where the two moved edges cross
                A0, B0 = Pa[-1], Pb[0]
                den = ta[0] * tb[1] - ta[1] * tb[0]
                if abs(den) > 1e-9:
                    u = ((B0[0] - A0[0]) * tb[1] - (B0[1] - A0[1]) * tb[0]) / den
                    X = (A0[0] + u * ta[0], A0[1] + u * ta[1])
                else:
                    X = ((A0[0] + B0[0]) / 2, (A0[1] + B0[1]) / 2)
                Pa[-1] = X
                Pb[0] = X
            elif ka == 'l' or kb == 'l':       # the curve meets the moved straight edge
                if ka == 'l':
                    Q2 = _meet_line(kb, Pb, Pa[0], ta, False)
                    if Q2 is not None:
                        moved[b] = (kb, Q2)
                        Pa[-1] = Q2[0]
                    else:
                        Pb[0] = Pa[-1]
                else:
                    Q2 = _meet_line(ka, Pa, Pb[0], tb, True)
                    if Q2 is not None:
                        moved[a] = (ka, Q2)
                        Pb[0] = Q2[-1]
                    else:
                        Pa[-1] = Pb[0]
            else:                              # two curves (a crotch): cut both where they cross
                uv = _meet_curves(ka, Pa, kb, Pb)
                if uv is not None:
                    moved[a] = (ka, _casteljau(Pa, uv[0])[0])
                    moved[b] = (kb, _casteljau(Pb, uv[1])[1])
                    moved[b][1][0] = moved[a][1][-1]
                else:
                    X = ((Pa[-1][0] + Pb[0][0]) / 2, (Pa[-1][1] + Pb[0][1]) / 2)
                    Pa[-1] = X
                    Pb[0] = X
        def join(bl):
            if bl[0] == 'c':
                pen.curveTo(*bl[1])
            else:
                pen.lineTo(bl[1])

        pen.moveTo(moved[0][1][0])
        for i in range(n):
            kind, Q = moved[i]
            if i in blends and i != 0:
                join(blends[i])
            if kind == 'l':
                pen.lineTo(Q[1])
            elif kind == 'q':
                pen.qCurveTo(Q[1], Q[2])
            else:
                pen.curveTo(Q[1], Q[2], Q[3])
        if 0 in blends:
            join(blends[0])
        pen.closePath()
    return simplify(out)


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


def _inside(a, b):
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def _erode_glyph(p, e, stem, italic=0):
    cs = _contours(p)
    bbs = [slant(c, -italic).bounds if italic else c.bounds for c in cs]   # judged upright
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
    skip = {f.name(ch) for ch in NO_THIN}
    n = 0
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if name == '.notdef' or name in skip or g.isComposite() or g.numberOfContours <= 0:
            continue
        # thinned as drawn: a horizontal shift is the same slanted or not, and the
        # italic's rounds have their vertical extremes as drawn, not un-slanted
        p = glyph_path(gs, name)
        _put(tt, name, _erode_glyph(p, e, f.V, f.italic), hmtx[name][0])
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
    """Flatten the top of the bowl: flat out from the stem, then a fair corner."""
    a = f.path('a')
    cs = _contours(a)
    if len(cs) != 2:
        return None                            # single-storey (italic): leave it
    inner, outer = min(cs, key=_area), max(cs, key=_area)
    ix0, iy0, ix1, iy1 = inner.bounds          # counter
    ox0 = a.bounds[0]                          # outside of the bowl's left side
    # the bowl's top stroke just left of the stem: bottom is the counter top
    spans = [s for s in _vspan(a, ix1 - 4) if abs(s[0] - iy1) < 3]
    if not spans:
        return None
    y_top = spans[0][1]
    # where each edge's corner takes over from the bowl: its leftmost point
    y_lo, y_hi = iy0 + 0.2 * (iy1 - iy0), iy0 + 0.8 * (iy1 - iy0)
    s_in, k_in, dk_in = _bowl_side(inner, y_lo, y_hi)
    s_out, k_out, dk_out = _bowl_side(outer, y_lo, y_hi)
    # and where it hands over to the flat top: where the straight edge begins
    xf_in = _flat_start(inner, iy1)
    xf_out = _flat_start(outer, y_top)
    x_ti = min(ix0 + A_FLAT_IN * (ix1 - ix0), xf_in)              # counter's flat top starts here
    x_to = min(ix0 + (A_FLAT_OUT - 0.10) * (ix1 - ix0), xf_out)   # and the outside's
    # each edge is redone on its own filled contour, cut exactly at its own nodes
    o = union(subtract(outer, rect(ox0 - 10, s_out[1], xf_out, y_top)),
              _corner(s_out[0], s_out[1], x_to, y_top, xf_out, k_out, dk_out))
    c = union(subtract(inner, rect(ix0 - 10, s_in[1], xf_in, iy1)),
              _corner(s_in[0], s_in[1], x_ti, iy1, xf_in, k_in, dk_in))
    out = subtract(o, c)
    # the top terminal cut level, at the height of its outer corner (A_TERMINAL)
    out = _level_terminals(f, 'a', _at_side, A_TERMINAL, glyph=out)
    return out, f.adv('a'), 0


RECIPES = {'I': r_I, 'ı': r_dotlessi, 'ȷ': r_dotlessj, 'p': r_p, 'e': r_e, 'a': r_a, 'c': r_c, 's': r_s, 'uni0307': r_dot,
           'idieresis': r_idieresis, 'f': r_f, 't': r_t}
for _ch in BARRED:
    RECIPES[_ch] = (lambda ch: lambda f: r_bars(f, ch))(_ch)
for _ch in ('!', '?', '¡', '¿', 'exclamdown.case', 'questiondown.case', '.'):
    RECIPES[_ch] = (lambda ch: lambda f: _square_points(f, ch))(_ch)
RECIPES[','] = lambda f: r_comma(f)
for _ch in ('‘', '“'):
    RECIPES[_ch] = (lambda ch: lambda f: r_quoteleft(f, ch))(_ch)


# ---------- applying to the TTFont ----------

def _tidy(path):
    """Boolean operations leave flat runs as strings of tiny curves; turn curves
    with their control points on their chord into lines and merge collinear lines.
    Only truly straight ones: a gentle curve flattened into a line leaves a kink
    at each end (issue #19)."""
    from fontTools.pens.recordingPen import RecordingPen
    rec = RecordingPen()
    path.draw(rec)
    out = []

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def flat(a, b, c):
        d = math.hypot(c[0] - a[0], c[1] - a[1]) or 1
        return abs(cross(a, b, c)) / d < 0.02

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


SMOOTH_DEG = 2.0         # nodes turning less than this are meant to be smooth


def round_smooth(g):
    """Round a glyph's float coordinates to integers, placing each smooth node
    (turning less than SMOOTH_DEG, e.g. where two cubics met before conversion)
    at the nearby integer point that keeps it smoothest. Rounding each point on
    its own turns a node between short handles by a degree or more, a visible
    kink (issue #19); a horizontal or vertical neighbour stays so."""
    coords = [tuple(c) for c in g.coordinates]
    flags = list(g.flags)
    out = [(otRound(x), otRound(y)) for x, y in coords]
    start = 0
    for end in g.endPtsOfContours:
        idx = list(range(start, end + 1))
        n = len(idx)
        for k, i in enumerate(idx):
            if not flags[i] & 1 or n < 3:
                continue
            a, b = idx[k - 1], idx[(k + 1) % n]
            pa, pn, pb = coords[a], coords[i], coords[b]
            u = (pn[0] - pa[0], pn[1] - pa[1])
            v = (pb[0] - pn[0], pb[1] - pn[1])
            lu, lv = math.hypot(*u), math.hypot(*v)
            if lu < 1e-6 or lv < 1e-6:
                continue
            if (flags[a] & 1) and (flags[b] & 1):
                continue                         # between two lines: a corner or a straight run
            turn = math.degrees(abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
            if turn >= SMOOTH_DEG:
                continue
            ra, rb = out[a], out[b]
            # keep a horizontal or vertical neighbour edge so
            keep_x = abs(u[0]) < 1e-6 or abs(v[0]) < 1e-6
            keep_y = abs(u[1]) < 1e-6 or abs(v[1]) < 1e-6
            best, cost = out[i], None
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    c = (otRound(pn[0]) + dx, otRound(pn[1]) + dy)
                    if (keep_x and dx) or (keep_y and dy):
                        continue
                    d = math.hypot(c[0] - pn[0], c[1] - pn[1])
                    if d > 1.6:
                        continue
                    u2 = (c[0] - ra[0], c[1] - ra[1])
                    v2 = (rb[0] - c[0], rb[1] - c[1])
                    if not any(u2) or not any(v2):
                        continue
                    t = math.degrees(abs(math.atan2(u2[0] * v2[1] - u2[1] * v2[0], u2[0] * v2[0] + u2[1] * v2[1])))
                    k2 = t + 0.15 * d
                    if cost is None or k2 < cost:
                        best, cost = c, k2
            out[i] = best
        start = end + 1
    g.coordinates = GlyphCoordinates(out)


# ---------- smoothing what Schibsted left (issue #19) ----------

FAIR_KINK = (0.5, 10.0)  # smooth points turning this much (degrees) are straightened
FAIR_STEP = 2.5          # curvature steps this big (times the x-height) are evened out


def _quad_k(p0, c, p1, at_end):
    """Signed curvature of a quadratic at one end."""
    d1 = (2 * (p1[0] - c[0]), 2 * (p1[1] - c[1])) if at_end else (2 * (c[0] - p0[0]), 2 * (c[1] - p0[1]))
    d2 = (2 * (p1[0] - 2 * c[0] + p0[0]), 2 * (p1[1] - 2 * c[1] + p0[1]))
    sp = math.hypot(*d1)
    return 0.0 if sp < 1e-9 else (d1[0] * d2[1] - d1[1] * d2[0]) / sp ** 3


def _turn(u, v):
    return math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))


def fair_contour(pts, xh):
    """pts: [(x, y, on)] of one closed TrueType contour, floats. Straightens small
    kinks and evens out curvature steps between quadratics; returns the new list
    and how many points it changed."""
    changed = 0
    # 1. small kinks
    n = len(pts)
    for i in range(n):
        x, y, on = pts[i]
        if not on:
            continue
        a, b = pts[i - 1], pts[(i + 1) % n]
        u, v = (x - a[0], y - a[1]), (b[0] - x, b[1] - y)
        if math.hypot(*u) < 1e-6 or math.hypot(*v) < 1e-6:
            continue
        t = abs(_turn(u, v))
        if not FAIR_KINK[0] < t < FAIR_KINK[1]:
            continue
        if a[2] and b[2]:
            continue                           # two straight edges: a corner, as drawn
        if a[2]:                               # straight edge in, curve out: turn the handle
            L, d = math.hypot(*v), (u[0] / math.hypot(*u), u[1] / math.hypot(*u))
            pts[(i + 1) % n] = (x + L * d[0], y + L * d[1], False)
        elif b[2]:                             # curve in, straight edge out
            L, d = math.hypot(*u), (v[0] / math.hypot(*v), v[1] / math.hypot(*v))
            pts[i - 1] = (x - L * d[0], y - L * d[1], False)
        else:                                  # between two curves: onto the line of its handles
            dx, dy = b[0] - a[0], b[1] - a[1]
            k = ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)
            pts[i] = (a[0] + k * dx, a[1] + k * dy, True)
        changed += 1
    # 2. curvature steps: make implied points that need it explicit, then slide
    out = []
    n = len(pts)
    for i in range(n):
        out.append(pts[i])
        if not pts[i][2] and not pts[(i + 1) % n][2]:
            a, b = pts[i], pts[(i + 1) % n]
            out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 'implied'))
    pts = out
    n = len(pts)

    def on_before(j):                          # the on-curve (or implied) point before off-curve j
        q = pts[(j - 1) % n]
        return q

    res = []
    for i in range(n):
        x, y, on = pts[i]
        if not on:
            res.append(pts[i])
            continue
        a, b = pts[i - 1], pts[(i + 1) % n]
        keep = pts[i] if on is True else None
        if not a[2] and not b[2]:
            p0, p1 = on_before(i - 1), pts[(i + 2) % n]
            if p0[2] and p1[2]:
                kl = _quad_k(p0, a, (x, y), True)
                kr = _quad_k((x, y), b, p1, False)
                if kl * kr > 0 and abs(kl - kr) * xh >= FAIR_STEP:
                    lam0 = ((x - a[0]) * (b[0] - a[0]) + (y - a[1]) * (b[1] - a[1])) / \
                           ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)

                    def diff(lam):
                        q = (a[0] + lam * (b[0] - a[0]), a[1] + lam * (b[1] - a[1]))
                        return _quad_k(p0, a, q, True) - _quad_k(q, b, p1, False)
                    lo, hi = max(0.15, lam0 - 0.25), min(0.85, lam0 + 0.25)
                    if diff(lo) * diff(hi) < 0:
                        for _ in range(60):
                            mid = (lo + hi) / 2
                            if diff(lo) * diff(mid) <= 0:
                                hi = mid
                            else:
                                lo = mid
                        lam = (lo + hi) / 2
                        keep = (a[0] + lam * (b[0] - a[0]), a[1] + lam * (b[1] - a[1]), True)
                        changed += 1
        if keep is not None:
            res.append(keep)
    return res, changed


def fair_outlines(tt, skip=()):
    """Run fair_contour over every simple glyph of `tt`; names in `skip` are left
    alone. Returns the names of the glyphs changed."""
    glyf = tt['glyf']
    xh = tt['OS/2'].sxHeight
    done = []
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if name in skip or g.isComposite() or g.numberOfContours <= 0:
            continue
        coords, ends, flags = list(g.coordinates), list(g.endPtsOfContours), list(g.flags)
        new_pts, new_ends, total, start = [], [], 0, 0
        for e in ends:
            pts = [(float(coords[i][0]), float(coords[i][1]), bool(flags[i] & 1)) for i in range(start, e + 1)]
            start = e + 1
            if len(pts) >= 3:
                pts, c = fair_contour(pts, xh)
                total += c
            new_pts += pts
            new_ends.append(len(new_pts) - 1)
        if not total:
            continue
        g.coordinates = GlyphCoordinates([(p[0], p[1]) for p in new_pts])
        g.flags = array.array('B', [1 if p[2] else 0 for p in new_pts])
        g.endPtsOfContours = new_ends
        round_smooth(g)
        g.program = ttProgram.Program()
        g.program.fromBytecode(b'')
        g.recalcBounds(glyf)
        done.append(name)
    return done


def _put(tt, name, path, width):
    pen = TTGlyphPen(None)
    # cubics (the a's corner) into quadratics closely: a quadratic spline is only
    # tangent-continuous, and coarse pieces put visible curvature steps in a
    # curve whose curvature changes (issue #19)
    cpen = Cu2QuPen(pen, max_err=0.25, reverse_direction=True)
    for op, args in _tidy(path):
        getattr(cpen, op)(*args)
    g = pen.glyph(round=float)
    round_smooth(g)
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


# the comma: a square head like the full stop's, and a straight tail leaning left
COMMA_TAIL_DEPTH = 0.95  # below the baseline, in head sides
COMMA_TAIL_WIDTH = 0.62  # the tail's width across, at the top, in head sides
COMMA_TAIL_LEAN = 0.10   # how far (in head sides) the tail's end reaches left of the head
NO_THIN = (',', '‘', '“')  # drawn at their final weight: the contrast thinning skips them


def _comma_shape(f):
    """The new comma, upright: a square head of the full stop's size on the
    baseline, centred where Schibsted's round head was, and a straight tail of
    even width, leaning left, its end cut level."""
    side = _dot_side(f)
    old = f.path(',')
    top = old.bounds[3]
    lx, rx = _hspan(old, top * 0.45)[-1]       # across the round head
    cx = (lx + rx) / 2
    h0, h1 = cx - side / 2, cx + side / 2
    d = COMMA_TAIL_DEPTH * side
    w = COMMA_TAIL_WIDTH * side
    left_end = h0 - COMMA_TAIL_LEAN * side
    lean = (h1 - w) - left_end
    return polygon((h0, side), (h1, side), (h1, 0), (h1 - lean, -d), (h1 - w - lean, -d),
                   (h1 - w, 0), (h0, 0))


def r_comma(f):
    return _comma_shape(f), f.adv(','), 0


def r_quoteleft(f, ch):
    """‘ and “: the new comma turned round in the box of each old one, its top
    where the round head's top was, less the overshoot (the cap height)."""
    c = _comma_shape(f)
    cx0, cy0, cx1, cy1 = c.bounds
    _, rb, _, _ = f.bounds('.')
    out = pathops.Path()
    for old in _contours(f.path(ch)):
        x0, y0, x1, y1 = old.bounds
        top = y1 + min(rb, 0)
        # turn round about the centre of its box, then centre it in the old box
        q = transform(c, -1, 0, 0, -1, cx0 + cx1, cy0 + cy1)
        q = move(q, (x0 + x1) / 2 - (cx0 + cx1) / 2, top - cy1)
        out = union(out, q)
    return out, f.adv(ch), 0


UPPER_DOT = ('colon', 'colon.case', 'colon.tf', 'semicolon', 'semicolon.tf')
RAISED_COMMA = ('quoteright', 'quotedblright', 'uni02BC', 'napostrophe')
MIDDLE_DOT = ('periodcentered', 'periodcentered.case', 'periodcentered.loclCAT',
              'periodcentered.loclCAT.case', 'uni2219', 'Ldot', 'ldot')


def _place_dot_components(tt, font):
    """The full stop is now a smaller square sitting on the baseline. Where it is
    used as an upper dot (colon, semicolon), move it up so its top is where the
    round dot's top was, less the overshoot (the x-height); where it is a middle
    dot (·, ŀ, ∙), keep its centre where the round dot's was. Italics move along
    the slant."""
    name = font.name('.')
    _, rb, _, rt = font.bounds('.')            # the round dot, before the recipe
    side = _dot_side(font)
    tan = math.tan(math.radians(font.italic))
    up = rt + min(rb, 0) - side
    mid = (rb + rt) / 2 - side / 2
    glyf = tt['glyf']
    # the raised comma of ’ ” ʼ ŉ: its head's top where the round head's top was,
    # less the overshoot (the cap height)
    comma = font.name(',')
    up_comma = font.bounds(',')[3] + min(rb, 0) - side
    jobs = ([(n, up, 'top', name) for n in UPPER_DOT] + [(n, mid, 'all', name) for n in MIDDLE_DOT] +
            [(n, up_comma, 'all', comma) for n in RAISED_COMMA])
    for gname, dy, which, base in jobs:
        if gname not in glyf or not glyf[gname].isComposite():
            continue
        g = glyf[gname]
        comps = [c for c in g.components if c.glyphName == base]
        if not comps:
            continue
        if which == 'top':
            comps = [max(comps, key=lambda c: c.y)] if len(comps) > 1 or gname.startswith('semicolon') else []
        for c in comps:
            c.y = round(c.y + dy)
            c.x = round(c.x + dy * tan)
        g.recalcBounds(glyf)


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
    _place_dot_components(tt, font)
    if font.erode:
        _erode_all(tt, font, font.erode)
        done.append(f'contrast: verticals thinned by {2 * font.erode:.0f} units')
    # Every style has reshaped glyphs, so no style keeps hints: mixed hinted and unhinted
    # letters would render differently side by side on Windows.
    _strip_hinting(tt)
    for tag in ('hdmx', 'LTSH', 'VDMX'):
        if tag in tt:
            del tt[tag]
    return done
