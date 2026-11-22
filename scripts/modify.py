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
       c, instead of on a slant; the spine is left as it is. Then S_WIDTH as
       wide, so it does not read small beside z.
    C G S J 2 3 5 6 9  the same: every curved terminal cut level at the height
       of its inner corner (LEVEL_CUTS), in the default, tabular and numerator
       figures; superiors and fractions are made of the numerators and follow.
    taper  a level-cut curved stroke (c e s C G S J 2 3 5 6 9) no longer swells into
       its terminal: from the extreme of its bowl the outer edge eases in, so the
       end is TERMINAL_WEIGHT of the way from the thin to the side of o, O or 0
       (scripts/taper.py).
    r  the arm ends in a vertical cut, like the flags of f j y t, instead of one
       about 8 degrees off vertical. The cut stands at the tip and the underside
       runs on along its own curve to it, so the arm keeps its reach and the r
       its spacing.
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
width as sidebearing. In practice this touches Medium and Bold. Where a curve
meets another stroke in a crotch (b d p q n h m u r a, 6 9 & $), the two thinned
sides are carried on until they meet in a point again (CROTCH_MEET), instead of
being joined by a short flat. Where the other stroke is a straight stem (the
shoulders of n h m u r, the bowls of b d p q), the curve's move eases out to
nothing at the crotch (SHOULDER_EASE), so the junction keeps its weight.

Č č Ě ě ř Š š Ť Ž ž ǎ Ǧ are single outlines in Schibsted; they are rebuilt as the
letter and the caron mark first (_compose_carons), so they follow the letters.

Rule 4 runs over the whole font after the merge (ease_corners, from build.py):
quarter turns between two straight edges are redrawn as fair corners.

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
import taper

BIG = 10000
CHANGED = ('I', 'ı', 'ȷ', 'e', 'a', 'c', 's', 'p', 'uni0307', 'idieresis', 'f', 't', 'z', 'E', 'F', 'T', 'Z', 'L', 'H',
           '!', '?', '¡', '¿', 'exclamdown.case', 'questiondown.case', '.', ',', '‘', '“',
           'r', 'C', 'G', 'S', 'J') + tuple(n + form for n in ('two', 'three', 'five', 'six', 'nine')
                                       for form in ('', '.tf', '.numr'))

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

# the s, cut level at both ends and so a little lighter at its ends, read small beside
# the z: this much wider, with its stroke weights kept
S_WIDTH = 1.03

# a level-cut curved stroke tapers from the extreme of its bowl to the cut (taper.py),
# so its end is this far from the thin (0) to the side (1) of the matching round:
# o for lowercase, O for capitals, 0 for figures (in the same form, .tf or .numr)
TERMINAL_WEIGHT = 0.45

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


def _round_of(ch):
    """The round a level-cut terminal of `ch` is weighed against."""
    base, dot, form = ch.partition('.')
    if base in ('two', 'three', 'five', 'six', 'nine'):
        return 'zero' + dot + form
    return 'O' if ch[0].isupper() else 'o'


def _terminal_width(f, ch):
    """Width across the stroke of a level-cut end: TERMINAL_WEIGHT of the way from the
    thin (top) to the side of the matching round."""
    r = _round_of(ch)
    x0, y0, x1, y1 = f.bounds(r)
    side = f.hspan(r, (y0 + y1) / 2)[0][1]
    thin = f.vspan(r, (x0 + x1) / 2)[-1][1]
    return thin + TERMINAL_WEIGHT * (side - thin)


def _level_terminals(f, ch, select=None, at=0.0, glyph=None):
    """Cut the slanted terminals of `ch` level (_cut_level), by default at the height
    of the inner corner, the outer edge carried on along its own direction. Cut at
    the inner corner, the stroke then tapers so its end is _terminal_width wide
    (taper.py); the a's top, cut at its tip, keeps its weight."""
    out = glyph if glyph is not None else f.path(ch)
    cuts = _terminal_cuts(f, ch, select)
    if at == 0.0:
        rec = DecomposingRecordingPen(f.gs)
        f.gs[f.name(ch)].draw(rec)
        sh = math.tan(math.radians(f.italic))
        cs = taper.contours(rec, lambda p: (p[0] - p[1] * sh, p[1]))
        w_end = _terminal_width(f, ch)
    for p_in, p_out, tang in cuts:
        out = _cut_level(out, p_in, p_out, tang, at)
        if at == 0.0:
            out = taper.taper(out, cs, p_in, p_out, tang, w_end)
    return out


def _at_side(a, b, bb):
    """A terminal cut that reaches the left or right side of the letter (s, and the
    a's top), not a straight piece of a spine."""
    x0, _, x1, _ = bb
    tol = 0.06 * (x1 - x0)
    return min(abs(p[0] - x) for p in (a, b) for x in (x0, x1)) < tol


def _cuts(side=None, low=False, steep=30):
    """A selector for _terminal_cuts: cuts shallower than `steep` degrees (so not the
    diagonal of 2 or the stem of 5), on the given half of the letter ('left',
    'right') or reaching its side (None, as _at_side), and with `low`, only in its
    lower 40 % (the 5, whose bowl meets the stem in a shallow joint at mid-height)."""
    def select(a, b, bb):
        x0, y0, x1, y1 = bb
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if math.degrees(math.atan2(abs(b[1] - a[1]), abs(b[0] - a[0]))) > steep:
            return False
        if low and max(a[1], b[1]) > y0 + 0.4 * (y1 - y0):
            return False
        if side == 'left':
            return a[0] < cx and b[0] < cx
        if side == 'right':
            return a[0] > cx and b[0] > cx
        return _at_side(a, b, bb)
    return select


# the capitals and figures whose curved strokes end in a slanted cut, and where it is
LEVEL_CUTS = {'C': _cuts('right'), 'G': _cuts('right'), 'S': _cuts(), 'J': _cuts('left'),
              'two': _cuts(), 'three': _cuts('left'), 'five': _cuts(low=True),
              'six': _cuts('right'), 'nine': _cuts('left')}
FIGURE_FORMS = ('', '.tf', '.numr')     # default, tabular, numerators (superiors, fractions)


def r_level(f, ch, select):
    """Rule 2 for the capitals and figures: every curved terminal cut level at the
    height of its inner corner, as in e c s."""
    return _level_terminals(f, ch, select), f.adv(ch), 0


def _extend_to_x(seg, at_end, x):
    """A quadratic ('q', p0, c, p1) carried on past its end (or start) along its own
    curve to where it reaches `x`."""
    P = [seg[1], seg[2], seg[3]]
    lo, hi = (1.0, 3.0) if at_end else (-2.0, 0.0)
    f = lambda u: _bez('q', P, u)[0][0] - x
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if f(lo) * f(mid) <= 0 else (mid, hi)
    u = (lo + hi) / 2
    q = _casteljau(P, u)[0] if at_end else _casteljau(P, u)[1]
    return ('q', *q)


def r_r(f):
    """Rule 3: the arm ends in a vertical cut instead of one about 8 degrees off it.
    The cut stands at the tip of the arm, where its top corner is, and the underside
    is carried on along its own curve to meet it, so the arm keeps its reach and the
    r its spacing. (Carried on in a straight piece, the piece would be shorter than
    the Medium/Bold thinning moves it and fold out past the cut.)"""
    glyph = f.path('r')
    x0, _, x1, _ = bounds(glyph)
    steep = lambda a, b, bb: (a[0] > (x0 + x1) / 2 and b[0] > (x0 + x1) / 2
                              and abs(b[1] - a[1]) > 3 * abs(b[0] - a[0]))
    (a, b, _), = _terminal_cuts(f, 'r', steep)
    top, low = (a, b) if a[1] > b[1] else (b, a)
    rec = DecomposingRecordingPen(f.gs)
    f.gs[f.name('r')].draw(rec)
    sh = math.tan(math.radians(f.italic))
    cs = taper.contours(rec, lambda p: (p[0] - p[1] * sh, p[1]))
    out = pathops.Path()
    for segs in cs:
        n = len(segs)
        new = list(segs)
        for i, sg in enumerate(segs):
            ends = (sg[1], sg[2])
            if sg[0] == 'l' and any(taper._near(e, top) for e in ends) and any(taper._near(e, low) for e in ends):
                if taper._near(sg[1], top):           # top -> low, then the underside
                    j = (i + 1) % n
                    ext = _extend_to_x(segs[j], False, top[0])
                    new[j] = ext
                    new[i] = ('l', sg[1], ext[1])
                else:                                 # the underside, then low -> top
                    j = (i - 1) % n
                    ext = _extend_to_x(segs[j], True, top[0])
                    new[j] = ext
                    new[i] = ('l', ext[3], sg[2])
        out.moveTo(*new[0][1])
        for sg in new:
            if sg[0] == 'l':
                out.lineTo(*sg[2])
            else:
                out.quadTo(*sg[2], *sg[3])
        out.close()
    return simplify(out), f.adv('r'), 0


def r_e(f):
    return _level_terminals(f, 'e'), f.adv('e'), 0


def r_c(f):
    return _level_terminals(f, 'c'), f.adv('c'), 0


def r_s(f):
    """Both terminals cut level at the height of their inner corners, as in e and c;
    then S_WIDTH as wide about its centre, the verticals thinned back to their weight
    (erode_x), the sidebearings kept."""
    out = _level_terminals(f, 's', _at_side)
    if S_WIDTH == 1:
        return out, f.adv('s'), 0
    x0, _, x1, _ = bounds(out)
    l0, l1 = _hspan(out, 0.72 * f.xh)[0]
    side = l1 - l0                             # the upper bowl's left side
    cx = (x0 + x1) / 2
    out = transform(out, a=S_WIDTH, e=cx * (1 - S_WIDTH))
    thin = (S_WIDTH - 1) * side / 2
    if f.erode:                                # thinned with the rest, in the same pass
        f.extra_erode[f.name('s')] = thin
    else:
        out = erode_x(out, thin)
    dx = (x1 - x0) * (S_WIDTH - 1) / 2
    return move(out, dx), round(f.adv('s') + 2 * dx), dx


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
CROTCH_MEET = True       # inside corners with a curve: the moved sides meet in a point again
MEET_CAP = 2.0           # two curves that do not meet along their own course are carried on
                         # in straight lines, if they meet within this many times the gap
SHOULDER_EASE = True     # where a curve meets a straight stem in a crotch (the shoulders of
                         # n h m u r, the bowls of b d p q), the curve's move fades out
                         # towards the crotch, so the junction keeps Schibsted's weight
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


def _meet_line(kind, Q, L0, t, at_end, reach=0.5):
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
    if not (-reach < u < 1 + reach) or abs(g(u)) > 1e-3:
        return None
    left, right = _casteljau(Q, u)
    return left if at_end else right


def _meet_curves(ka, A, kb, B, reach=0.6):
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
    if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) > 1e-3 or not (0.2 < u < 1 + reach and -reach < v < 0.8):
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


def _ease_chain(pieces, moved, chain, shift, fwd, N=64):
    """Move the curve pieces `chain` (listed from a crotch outwards) sideways by `shift`
    times smoother(distance from the crotch / length of the chain), instead of by all of
    it: nothing at the crotch, all of it at the far end, with no step in direction or
    curvature anywhere. Each piece is written as one cubic matching position,
    direction and curvature of the moved curve at its ends."""
    samples, lengths = [], []
    for j in chain:
        k, P = pieces[j]
        pts = [_bez(k, P, t / N)[0] for t in range(N + 1)]
        L = [0.0]
        for m in range(1, N + 1):
            L.append(L[-1] + math.hypot(pts[m][0] - pts[m - 1][0], pts[m][1] - pts[m - 1][1]))
        samples.append(pts)
        lengths.append(L)
    total = sum(L[-1] for L in lengths)
    if total <= 0:
        return
    smoother = lambda u: u * u * u * (10 - 15 * u + 6 * u * u)
    start = 0.0
    for j, pts, L in zip(chain, samples, lengths):
        q = []
        for m, pt in enumerate(pts):
            d = start + (L[m] if fwd else L[-1] - L[m])        # distance from the crotch
            q.append((pt[0] + shift * smoother(min(d / total, 1.0)), pt[1]))
        start += L[-1]

        def jet(m):                        # one-sided, second order, at an end
            s = 1 if m == 0 else -1
            a, b, c = q[m], q[m + s], q[m + 2 * s]
            t = (s * (-3 * a[0] + 4 * b[0] - c[0]), s * (-3 * a[1] + 4 * b[1] - c[1]))
            n = math.hypot(*t)
            k = taper._curv3(a, b, c) if s > 0 else taper._curv3(c, b, a)
            return (t[0] / n, t[1] / n), k
        (t0, k0), (t1, k1) = jet(0), jet(N)
        P0, P3 = q[0], q[-1]
        chord = math.hypot(P3[0] - P0[0], P3[1] - P0[1])
        a0, a1 = fair.cubic_g2(P0, t0, k0, P3, t1, k1, chord / 3)
        moved[j] = ('c', [P0, (P0[0] + a0 * t0[0], P0[1] + a0 * t0[1]),
                          (P3[0] - a1 * t1[0], P3[1] - a1 * t1[1]), P3])


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
        if SHOULDER_EASE:
            for i in range(n):
                a, b = (i - 1) % n, i
                if (pieces[a][0] == 'l') == (pieces[b][0] == 'l'):
                    continue
                if sh[a] is None or sh[b] is None or sh[a] == sh[b]:
                    continue
                ta = _tangent_at(pieces[a][0], pieces[a][1], True)
                tb = _tangent_at(pieces[b][0], pieces[b][1], False)
                if ta[0] * tb[1] - ta[1] * tb[0] >= 0:
                    continue                   # not an inside corner
                fwd = pieces[b][0] != 'l'      # the curve runs away from the crotch
                s0 = sh[b] if fwd else sh[a]
                chain, j = [], (b if fwd else a)
                while pieces[j][0] != 'l' and sh[j] == s0 and len(chain) < n - 1:
                    chain.append(j)
                    j = (j + 1) % n if fwd else (j - 1) % n
                _ease_chain(pieces, moved, chain, s0, fwd)
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
                # each side. Where a curve is involved the moved sides are carried
                # on to meet (CROTCH_MEET), or cut back a little and joined by a
                # smooth curve (ROUND_CROSSINGS); otherwise, and where they do not
                # meet, they are joined by a short flat
                met = False
                if CROTCH_MEET and (ka != 'l' or kb != 'l'):
                    # a crotch stays a point, as Schibsted drew it: both moved sides are
                    # carried on along their own course until they meet, so neither bends;
                    # the notch sits a little deeper than Schibsted's (most where the sides
                    # meet at a shallow angle, as in b d p q n and 6 9)
                    if ka == 'l':
                        Q2 = _meet_line(kb, Pb, Pa[0], ta, False, 2.0)
                        if Q2 is not None:
                            moved[b] = (kb, Q2)
                            Pa[-1] = Q2[0]
                            met = True
                    elif kb == 'l':
                        Q2 = _meet_line(ka, Pa, Pb[0], tb, True, 2.0)
                        if Q2 is not None:
                            moved[a] = (ka, Q2)
                            Pb[0] = Q2[-1]
                            met = True
                    else:
                        uv = _meet_curves(ka, Pa, kb, Pb, 2.0)
                        if uv is None:
                            # too sharp a crotch to carry the curves on (the foot of a in
                            # Bold): carried on in straight lines along their own direction,
                            # unless the point would land far off (a shallow crotch, as ð)
                            ea, eb = Pa[-1], Pb[0]
                            da, db = _tangent_at(ka, Pa, True), _tangent_at(kb, Pb, False)
                            den = da[0] * db[1] - da[1] * db[0]
                            if abs(den) > 1e-9:
                                t = ((eb[0] - ea[0]) * db[1] - (eb[1] - ea[1]) * db[0]) / den
                                w = ((eb[0] - ea[0]) * da[1] - (eb[1] - ea[1]) * da[0]) / den
                                gap = math.hypot(eb[0] - ea[0], eb[1] - ea[1])
                                if t > 0 and w < 0 and max(t, -w) <= MEET_CAP * gap:
                                    blends[i] = ('ll', (ea[0] + t * da[0], ea[1] + t * da[1]), eb)
                                    met = True
                        if uv is not None:
                            moved[a] = (ka, _casteljau(Pa, uv[0])[0])
                            moved[b] = (kb, _casteljau(Pb, uv[1])[1])
                            moved[b][1][0] = moved[a][1][-1]
                            met = True
                if not met and ROUND_CROSSINGS and (ka != 'l' or kb != 'l'):
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
                elif not met:
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
            if bl[0] == 'll':                  # two straight pieces through a point
                pen.lineTo(bl[1])
                pen.lineTo(bl[2])
            elif bl[0] == 'c':
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
        _put(tt, name, _erode_glyph(p, e + f.extra_erode.get(name, 0), f.V, f.italic), hmtx[name][0])
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


RECIPES = {'r': r_r, 'I': r_I, 'ı': r_dotlessi, 'ȷ': r_dotlessj, 'p': r_p, 'e': r_e, 'a': r_a, 'c': r_c, 's': r_s, 'uni0307': r_dot,
           'idieresis': r_idieresis, 'f': r_f, 't': r_t}
for _base, _sel in LEVEL_CUTS.items():
    for _form in (FIGURE_FORMS if len(_base) > 1 else ('',)):
        RECIPES[_base + _form] = (lambda ch, sel: lambda f: r_level(f, ch, sel))(_base + _form, _sel)
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


# rule 4: where a straight edge turns through about a quarter into another straight edge
# by way of a curve (the hooks of f j t y l, g's ear, a's spur, the turns of { } and of
# the drawn ζ ξ ς τ), the curve is redrawn as a fair corner (fair.py): its curvature
# rises from nothing on the one straight edge and falls back to nothing on the other,
# with no point where the bend visibly starts. It starts where the old curve started,
# EASE_REACH times as far from the corner the two edges would make.
EASE_REACH = 1.0
EASE_TURN = (60, 120)    # degrees: what counts as a quarter turn
EASE_MAX_CURVES = 4      # curve pieces between the two straight edges


def _unit2(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _quarter_turns(segs):
    """(i, j, d1, d2): straight piece i, then 1..EASE_MAX_CURVES curves, then straight
    piece j, joined without a kink, turning through EASE_TURN."""
    n, out = len(segs), []
    for i in range(n):
        if segs[i][0] != 'l':
            continue
        j, m = (i + 1) % n, 0
        while segs[j][0] != 'l' and m < n:
            j, m = (j + 1) % n, m + 1
        if m == 0 or m > EASE_MAX_CURVES:
            continue
        A, B = segs[i][1], segs[j][1]
        d1 = _unit2((A[1][0] - A[0][0], A[1][1] - A[0][1]))
        d2 = _unit2((B[1][0] - B[0][0], B[1][1] - B[0][1]))
        t0 = _jet(*segs[(i + 1) % n], 0.0)[1]
        t1 = _jet(*segs[(j - 1) % n], 1.0)[1]
        if d1[0] * t0[0] + d1[1] * t0[1] < 0.999 or d2[0] * t1[0] + d2[1] * t1[1] < 0.999:
            continue
        turn = math.degrees(math.acos(max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1]))))
        if EASE_TURN[0] < turn < EASE_TURN[1]:
            out.append((i, j, d1, d2))
    return out


def _ease_contour(segs):
    """The contour with its quarter turns redrawn as fair corners; None if it has none."""
    n = len(segs)
    repl, drop, trim_end, trim_start = {}, set(), {}, {}
    for i, j, d1, d2 in _quarter_turns(segs):
        A, B = segs[i][1], segs[j][1]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        u = ((B[0][0] - A[1][0]) * d2[1] - (B[0][1] - A[1][1]) * d2[0]) / den
        V = (A[1][0] + u * d1[0], A[1][1] + u * d1[1])          # where the edges would meet
        r1 = math.hypot(V[0] - A[1][0], V[1] - A[1][1])
        r2 = math.hypot(V[0] - B[0][0], V[1] - B[0][1])
        l1 = math.hypot(A[1][0] - A[0][0], A[1][1] - A[0][1])
        l2 = math.hypot(B[1][0] - B[0][0], B[1][1] - B[0][1])
        a1, a2 = min(EASE_REACH * r1, r1 + 0.8 * l1), min(EASE_REACH * r2, r2 + 0.8 * l2)
        S = (V[0] - a1 * d1[0], V[1] - a1 * d1[1])
        try:
            cubics = fair.corner(a2, a1, 0.0, 0.0)              # x along d2, y along d1, from S
        except ValueError:
            continue
        g = lambda q: (S[0] + q[0] * d2[0] + q[1] * d1[0], S[1] + q[0] * d2[1] + q[1] * d1[1])
        trim_end[i], trim_start[j] = S, (V[0] + a2 * d2[0], V[1] + a2 * d2[1])
        k = (i + 1) % n
        while k != j:
            drop.add(k)
            k = (k + 1) % n
        repl[i] = [[None, g(c[0]), g(c[1]), g(c[2])] for c in cubics]
    if not repl:
        return None
    out = []
    for i, (kind, P) in enumerate(segs):
        if i in drop:
            continue
        Q = [tuple(q) for q in P]
        if i in trim_start:
            Q[0] = trim_start[i]
        if i in trim_end:
            Q[-1] = trim_end[i]
        out.append((kind, Q))
        for C in repl.get(i, ()):
            out.append(('c', C))
    for m in range(len(out)):                                   # each piece starts where the last ended
        out[m][1][0] = out[m - 1][1][-1]
    return out


def ease_corners(tt, skip=()):
    """Rule 4 over every simple glyph of `tt` (un-slanted for the italics); names in
    `skip` are left alone. Returns the names of the glyphs changed."""
    gs = tt.getGlyphSet()
    italic = -tt['post'].italicAngle
    glyf = tt['glyf']
    done = []
    for name in tt.getGlyphOrder():
        g = glyf[name]
        if name in skip or g.isComposite() or g.numberOfContours <= 0:
            continue
        p = glyph_path(gs, name, unslant=italic)
        new, changed = pathops.Path(), False
        for contour in _contours(p):
            segs = [(k, [tuple(q) for q in P]) for k, P in _segments(contour)]
            eased = _ease_contour(segs)
            changed |= eased is not None
            pen = new.getPen()
            pen.moveTo((eased or segs)[0][1][0])
            for kind, Q in eased or segs:
                if kind == 'l':
                    pen.lineTo(Q[1])
                elif kind == 'q':
                    pen.qCurveTo(Q[1], Q[2])
                else:
                    pen.curveTo(Q[1], Q[2], Q[3])
            pen.closePath()
        if changed:
            _put(tt, name, slant(simplify(new), italic), tt["hmtx"][name][0])
            done.append(name)
    return done


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


# Schibsted draws these as one outline (letter and caron together) instead of the letter
# with a caron mark, so they would not follow what is done to their letters: they are
# rebuilt as composites of the letter and uni030C, which their carons are, to a unit
CARONED = {'Ccaron': 'C', 'ccaron': 'c', 'Ecaron': 'E', 'ecaron': 'e', 'rcaron': 'r',
           'Scaron': 'S', 'scaron': 's', 'Tcaron': 'T', 'Zcaron': 'Z', 'zcaron': 'z',
           'uni01CE': 'a', 'Gcaron': 'G'}


def _compose_carons(tt):
    """Rebuild CARONED as composites, where the outline is the letter plus a shifted
    uni030C (to a unit); returns the names rebuilt."""
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
    glyf, hmtx = tt['glyf'], tt['hmtx']
    mark = 'uni030C'
    if mark not in glyf or glyf[mark].isComposite():
        return []

    def contours(name):
        g = glyf[name]
        coords, ends = list(g.coordinates), list(g.endPtsOfContours)
        out, start = [], 0
        for e in ends:
            out.append([tuple(coords[i]) for i in range(start, e + 1)])
            start = e + 1
        return out
    m = contours(mark)
    if len(m) != 1:
        return []
    m = m[0]
    done = []
    for name, base in CARONED.items():
        if name not in glyf or glyf[name].isComposite() or hmtx[name][0] != hmtx[base][0]:
            continue
        cs, bs = contours(name), contours(base)
        extra = [c for c in cs if c not in bs]
        if len(extra) != 1 or len(cs) != len(bs) + 1 or len(extra[0]) != len(m):
            continue
        c = extra[0]
        dx = min(x for x, _ in c) - min(x for x, _ in m)
        dy = min(y for _, y in c) - min(y for _, y in m)
        # the same caron, moved: every point within a unit (Schibsted's rounding)
        if any(min(abs(x - dx - mx) + abs(y - dy - my) for mx, my in m) > 1 for x, y in c):
            continue
        g = Glyph()
        g.numberOfContours = -1
        g.components = []
        for gname, x, y in ((base, 0, 0), (mark, dx, dy)):
            comp = GlyphComponent()
            comp.glyphName, comp.x, comp.y, comp.flags = gname, x, y, 0
            g.components.append(comp)
        glyf[name] = g
        g.recalcBounds(glyf)
        hmtx[name] = (hmtx[name][0], getattr(g, 'xMin', 0))
        done.append(name)
    return done


def modify(tt, font, src=None):
    """Apply the recipes, then the contrast correction, to `tt` (a TTFont);
    `font` is draw.Font on the same file `src`."""
    font.erode = erosion(font)
    font.extra_erode = {}                      # glyph -> thinning on top of font.erode
    font.upright = _upright_of(src) if src else None
    done = _compose_carons(tt)
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
