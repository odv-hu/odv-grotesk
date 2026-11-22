"""A curved stroke that does not swell into its level-cut terminal.

Schibsted's curved strokes get heavier towards their terminals: the S runs from
148 units at the top of its bowl to 182-190 on its side and 216-220 at its ends
(Regular). Cut on a slant this was hidden; cut level it shows as a heavy flat end
just where the stroke should be lightest. So, after the level cut, the outer edge
is moved in, by an amount that eases in from nothing at the extreme of the bowl
(the top of C, the bottom of J, where the edge runs level; strictly a little after
it, CLEAR) to what makes the end
`w_end` wide, measured across the stroke, at the cut. The ease is
u^3 (10 - 15u + 6u^2), so the edge keeps its direction and curvature where the
taper begins; past the old outer corner the edge runs on with that corner's own
curvature to the cut. The inner edge and the cut are untouched.

The new edge is written as cubics matching position, direction and curvature at
every node (fair.cubic_g2), and the ink beyond it is taken off.

    out = taper(glyph, contours, p_in, p_out, tang, t_in, w_end)
"""
import math

import pathops

import fair
from geometry import subtract

SEGMENTS = 6     # cubics in the new edge
CLEAR = 0.2      # the taper starts this share of the way from the extreme to the corner,
                 # clear of the extreme, where the Medium/Bold thinning blends its two halves
STEP = 1.0       # sampling step along the edge, font units


def contours(rec, un):
    """The recorded outline as contours of segments ('l', p0, p1) or ('q', p0, c, p1),
    implied on-curve points resolved, every point passed through `un`."""
    out, cur, start, segs = [], None, None, None
    for op, args in rec.value:
        pts = [un(a) for a in args if a is not None]
        if op == 'moveTo':
            segs = []
            out.append(segs)
            cur = start = pts[0]
        elif op == 'lineTo':
            segs.append(('l', cur, pts[0]))
            cur = pts[0]
        elif op == 'qCurveTo':
            offs, end = pts[:-1], pts[-1]
            p0 = cur
            for i, c in enumerate(offs):
                p1 = end if i == len(offs) - 1 else ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2)
                segs.append(('q', p0, c, p1))
                p0 = p1
            cur = end
        elif op in ('closePath', 'endPath'):
            if math.hypot(cur[0] - start[0], cur[1] - start[1]) > 1e-6:
                segs.append(('l', cur, start))
            cur = start
        else:
            raise ValueError(f'unexpected {op}')
    return out


def _near(p, q, tol=0.8):
    return abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol


def _rev(s):
    return ('l', s[2], s[1]) if s[0] == 'l' else ('q', s[3], s[2], s[1])


def _eval(s, t):
    """Point, first and second derivative."""
    if s[0] == 'l':
        p0, p1 = s[1], s[2]
        d = (p1[0] - p0[0], p1[1] - p0[1])
        return (p0[0] + t * d[0], p0[1] + t * d[1]), d, (0.0, 0.0)
    _, p0, c, p1 = s
    pt = tuple((1 - t) ** 2 * p0[i] + 2 * (1 - t) * t * c[i] + t * t * p1[i] for i in (0, 1))
    d = tuple(2 * (1 - t) * (c[i] - p0[i]) + 2 * t * (p1[i] - c[i]) for i in (0, 1))
    dd = tuple(2 * (p1[i] - 2 * c[i] + p0[i]) for i in (0, 1))
    return pt, d, dd


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _length(s):
    prev, acc = _eval(s, 0)[0], 0.0
    for j in range(1, 33):
        p = _eval(s, j / 32)[0]
        acc += math.hypot(p[0] - prev[0], p[1] - prev[1])
        prev = p
    return acc


def _curv3(a, b, c):
    """Signed curvature of the circle through three points."""
    ax, ay = b[0] - a[0], b[1] - a[1]
    bx, by = c[0] - b[0], c[1] - b[1]
    la, lb, lc = math.hypot(ax, ay), math.hypot(bx, by), math.hypot(c[0] - a[0], c[1] - a[1])
    return 2 * (ax * by - ay * bx) / (la * lb * lc) if la * lb * lc else 0.0


def edges(cs, p_in, p_out):
    """The outer edge from p_out and the inner edge from p_in, each as segments
    running away from the cut p_in-p_out; None if no contour has that cut."""
    for segs in cs:
        n = len(segs)
        for i, s in enumerate(segs):
            if s[0] != 'l':
                continue
            if _near(s[1], p_in) and _near(s[2], p_out):
                return ([segs[(i + 1 + j) % n] for j in range(n - 1)],
                        [_rev(segs[(i - 1 - j) % n]) for j in range(n - 1)])
            if _near(s[1], p_out) and _near(s[2], p_in):
                return ([_rev(segs[(i - 1 - j) % n]) for j in range(n - 1)],
                        [segs[(i + 1 + j) % n] for j in range(n - 1)])
    return None


def inner_direction(inner):
    """Unit direction of the inner edge at the cut, pointing towards the cut."""
    _, d, _ = _eval(inner[0], 0.0)
    return _unit((-d[0], -d[1]))


def _back_to_extreme(outer):
    """Samples of the outer edge from the outer corner back to the extreme of the
    bowl, where the edge runs level; None if there is none."""
    pts = [_eval(outer[0], 0.0)[0]]
    for s in outer:
        if s[0] == 'q':
            _, q0, c, q1 = s
            den = q0[1] - 2 * c[1] + q1[1]
            te = (q0[1] - c[1]) / den if abs(den) > 1e-9 else None
            if te is not None and 1e-6 < te <= 1:
                n = max(4, int(_length(s) * te / STEP))
                pts += [_eval(s, te * j / n)[0] for j in range(1, n + 1)]
                return pts
        elif abs(s[1][1] - s[2][1]) < 1e-6:
            return pts
        n = max(8, int(_length(s) / STEP))
        pts += [_eval(s, j / n)[0] for j in range(1, n + 1)]
    return None


def _smoother(u):
    return u * u * u * (10 - 15 * u + 6 * u * u)


def _inner_at(inner, y):
    """Where the inner edge, followed away from the cut, first reaches height y, and
    its direction there pointing back towards the cut."""
    prev = _eval(inner[0], 0.0)[0]
    for s in inner:
        n = max(8, int(_length(s) / STEP))
        for j in range(1, n + 1):
            p = _eval(s, j / n)[0]
            if (prev[1] - y) * (p[1] - y) <= 0 and p[1] != prev[1]:
                u = (y - prev[1]) / (p[1] - prev[1])
                return ((prev[0] + u * (p[0] - prev[0]), y), _unit((prev[0] - p[0], prev[1] - p[1])))
            prev = p
    return None


def _land(pts, y):
    """`pts` cut where they first cross height y (going from the first towards the last),
    or carried on along their last direction to it if they never reach it."""
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
            u = (y - a[1]) / (b[1] - a[1])
            return pts[:i] + [(a[0] + u * (b[0] - a[0]), y)]
    a, b = pts[-2], pts[-1]
    if abs(b[1] - a[1]) > 1e-9:
        u = (y - b[1]) / (b[1] - a[1])
        return pts[:-1] + [(b[0] + u * (b[0] - a[0]), y)]
    return pts


def taper(glyph, cs, p_in, p_out, tang, w_end, y=None):
    """`glyph` (already cut level, at height `y`, by default that of p_in) with the
    outer edge eased in so that the end is w_end wide across the stroke. `cs` are the
    contours of the glyph before the cut, p_in and p_out the inner and outer corner
    of the old cut, `tang` the outer edge's direction at p_out."""
    found = edges(cs, p_in, p_out)
    if found is None:
        return glyph
    outer, inner = found
    t_in = inner_direction(inner)
    if y is None or abs(y - p_in[1]) < 0.5:
        y = p_in[1]
    else:                                  # cut above the inner corner: measure from the
        hit = _inner_at(inner, y)          # inner edge where the cut meets it
        if hit is None:
            return glyph
        p_in, t_in = hit
    s = math.copysign(1, p_out[0] - p_in[0])
    back = _back_to_extreme(outer)
    if back is None or len(back) < 8:
        return glyph
    pts = back[::-1]                                   # extreme ... outer corner
    pts = pts[int(CLEAR * len(pts)):]
    # past the outer corner, run on with the corner's own curvature to the cut level
    t = _unit(tang)
    d0 = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
    if t[0] * d0[0] + t[1] * d0[1] < 0:
        t = (-t[0], -t[1])
    k = _curv3(pts[-7], pts[-4], pts[-1])
    th, p = math.atan2(t[1], t[0]), pts[-1]
    for _ in range(4000):
        if (p[1] - y) * (p_out[1] - y) <= 0:
            break
        th += k * STEP
        p = (p[0] + math.cos(th) * STEP, p[1] + math.sin(th) * STEP)
        pts.append(p)
    a, b = pts[-2], pts[-1]
    if b[1] != a[1]:
        u = (y - a[1]) / (b[1] - a[1])
        pts[-1] = (a[0] + u * (b[0] - a[0]), y)
    # how much the end must come in
    width = abs(pts[-1][0] - p_in[0]) * abs(t_in[1])
    d_end = width - w_end
    if d_end <= 1:
        return glyph
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))

    def normal(i):                                     # pointing away from the stroke
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        tx, ty = _unit((b[0] - a[0], b[1] - a[1]))
        return (ty, -tx)
    nX = normal(len(pts) - 1)
    sign = 1 if nX[0] * (pts[-1][0] - p_in[0]) + nX[1] * (pts[-1][1] - p_in[1]) >= 0 else -1
    new = []
    for i, q in enumerate(pts):
        n = normal(i)
        dl = d_end * _smoother(L[i] / L[-1])
        new.append((q[0] - sign * n[0] * dl, q[1] - sign * n[1] * dl))
    new = _land(new, y)                                # end exactly on the cut
    L = [0.0]
    for i in range(1, len(new)):
        L.append(L[-1] + math.hypot(new[i][0] - new[i - 1][0], new[i][1] - new[i - 1][1]))
    # cubics through SEGMENTS + 1 nodes, matching position, direction and curvature
    idx = [round(j * (len(new) - 1) / SEGMENTS) for j in range(SEGMENTS + 1)]

    def jet(i):
        i = min(max(i, 3), len(new) - 4)
        a, b, c = new[i - 3], new[i], new[i + 3]
        return _unit((c[0] - a[0], c[1] - a[1])), _curv3(a, b, c)
    edge = pathops.Path()
    edge.moveTo(*new[0])
    for j in range(SEGMENTS):
        i0, i1 = idx[j], idx[j + 1]
        P0, P3 = new[i0], new[i1]
        (t0, k0), (t1, k1) = jet(i0), jet(i1)
        a0, a1 = fair.cubic_g2(P0, t0, k0, P3, t1, k1, (L[i1] - L[i0]) / 3)
        edge.cubicTo(P0[0] + a0 * t0[0], P0[1] + a0 * t0[1],
                     P3[0] - a1 * t1[0], P3[1] - a1 * t1[1], *P3)
    # the ink beyond the new edge: bounded by the edge, the cut line and A's normal
    R = 4 * w_end
    nA = normal(0)
    nA = (sign * nA[0], sign * nA[1])
    E = new[-1]
    edge.lineTo(E[0] + s * R, y)
    edge.lineTo(new[0][0] + nA[0] * R, new[0][1] + nA[1] * R)
    edge.close()
    return subtract(glyph, edge)


def thin_inner(glyph, cs, p_in, p_out, amount, y):
    """`glyph` with the inner edge of a level-cut stroke eased out towards the outer edge,
    by `amount` at the cut (height y) and by nothing at the extreme of the counter, with
    the same ease as the taper, so the end is a little lighter while the outside of the
    stroke stays where it is."""
    found = edges(cs, p_in, p_out)
    if found is None or amount < 0.5:
        return glyph
    _, inner = found
    hit = _inner_at(inner, y) if abs(y - p_in[1]) >= 0.5 else (p_in, inner_direction(inner))
    if hit is None:
        return glyph
    start = hit[0]
    # samples of the inner edge from the cut back to the extreme of the counter: from
    # where it crosses the cut until it stops rising (or falling)
    pts, prev = [start], _eval(inner[0], 0.0)[0]
    on, way = abs(y - p_in[1]) < 0.5, 0
    for s in inner:
        n = max(8, int(_length(s) / STEP))
        stop = False
        for j in range(1, n + 1):
            p = _eval(s, j / n)[0]
            if not on:
                on = (prev[1] - y) * (p[1] - y) <= 0
            else:
                dy = p[1] - prev[1]
                if way == 0 and abs(dy) > 1e-6:
                    way = 1 if dy > 0 else -1
                elif way and dy * way < 0:
                    stop = True
                    break
                pts.append(p)
            prev = p
        if stop:
            break
    if len(pts) < 8:
        return glyph
    pts = pts[::-1]                             # extreme ... cut
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))

    def normal(i):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        tx, ty = _unit((b[0] - a[0], b[1] - a[1]))
        return (ty, -tx)
    nE = normal(len(pts) - 1)                   # into the counter: away from the outer corner
    sign = 1 if nE[0] * (pts[-1][0] - p_out[0]) + nE[1] * (pts[-1][1] - p_out[1]) >= 0 else -1
    new, back = [], []
    for i, q in enumerate(pts):
        n = normal(i)
        d = amount * _smoother(L[i] / L[-1])
        new.append((q[0] - sign * n[0] * d, q[1] - sign * n[1] * d))       # into the ink
        back.append((q[0] + sign * n[0] * 12, q[1] + sign * n[1] * 12))   # just inside the counter
    new = _land(new, y)                         # end exactly on the cut
    back = back[:len(new)]
    L = [0.0]
    for i in range(1, len(new)):
        L.append(L[-1] + math.hypot(new[i][0] - new[i - 1][0], new[i][1] - new[i - 1][1]))
    idx = [round(j * (len(new) - 1) / SEGMENTS) for j in range(SEGMENTS + 1)]

    def jet(i):
        i = min(max(i, 3), len(new) - 4)
        a, b, c = new[i - 3], new[i], new[i + 3]
        return _unit((c[0] - a[0], c[1] - a[1])), _curv3(a, b, c)
    add = pathops.Path()
    add.moveTo(*new[0])
    for j in range(SEGMENTS):
        i0, i1 = idx[j], idx[j + 1]
        P0, P3 = new[i0], new[i1]
        (t0, k0), (t1, k1) = jet(i0), jet(i1)
        a0, a1 = fair.cubic_g2(P0, t0, k0, P3, t1, k1, (L[i1] - L[i0]) / 3)
        add.cubicTo(P0[0] + a0 * t0[0], P0[1] + a0 * t0[1],
                    P3[0] - a1 * t1[0], P3[1] - a1 * t1[1], *P3)
    add.lineTo(back[-1][0], y)
    for q in reversed(back):
        add.lineTo(*q)
    add.close()
    return subtract(glyph, add)
