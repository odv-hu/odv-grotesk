"""Outline helpers for drawing the added glyphs.

Everything is drawn in an upright design space; italic fonts are un-slanted
on the way in (italic_unslant) and slanted back at the end, so one recipe
serves both styles.
"""
import math
import pathops
from fontTools.pens.basePen import BasePen

UNION, INTERSECTION, DIFFERENCE = (pathops.PathOp.UNION,
                                   pathops.PathOp.INTERSECTION,
                                   pathops.PathOp.DIFFERENCE)
BUTT, ROUND, SQUARE = (pathops.LineCap.BUTT_CAP, pathops.LineCap.ROUND_CAP,
                       pathops.LineCap.SQUARE_CAP)
JOIN_ROUND, JOIN_MITER = pathops.LineJoin.ROUND_JOIN, pathops.LineJoin.MITER_JOIN


class _ToPath(BasePen):
    """Feeds any glyph (TrueType quadratics, components) into a pathops Path."""

    def __init__(self, glyphset, path):
        super().__init__(glyphset)
        self.path = path

    def _moveTo(self, pt):
        self.path.moveTo(*pt)

    def _lineTo(self, pt):
        self.path.lineTo(*pt)

    def _curveToOne(self, a, b, c):
        self.path.cubicTo(*a, *b, *c)

    def _qCurveToOne(self, a, b):
        self.path.quadTo(*a, *b)

    def _closePath(self):
        self.path.close()

    _endPath = _closePath


def simplify(p):
    p = pathops.Path(p)
    p.simplify(fix_winding=True, keep_starting_points=False, clockwise=False)
    return p


def union(*paths):
    out = pathops.Path()
    for p in paths:
        out = pathops.op(out, p, UNION, fix_winding=True, clockwise=False)
    return out


def intersect(a, b):
    return pathops.op(a, b, INTERSECTION, fix_winding=True, clockwise=False)


def subtract(a, b):
    return pathops.op(a, b, DIFFERENCE, fix_winding=True, clockwise=False)


def transform(p, a=1, b=0, c=0, d=1, e=0, f=0):
    return p.transform(a, b, c, d, e, f)


def move(p, dx=0, dy=0):
    return transform(p, e=dx, f=dy)


def rect(x0, y0, x1, y1):
    p = pathops.Path()
    p.moveTo(x0, y0); p.lineTo(x1, y0); p.lineTo(x1, y1); p.lineTo(x0, y1); p.close()
    return p


def polygon(*pts):
    p = pathops.Path()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    p.close()
    return p


# ---------- skeletons ----------

class Skeleton:
    """An open or closed centre-line, built from lines, cubics and elliptic arcs."""

    def __init__(self, x, y):
        self.cmds = [('M', (x, y))]
        self.pt = (x, y)

    def line(self, x, y):
        self.cmds.append(('L', (x, y))); self.pt = (x, y); return self

    def curve(self, x1, y1, x2, y2, x, y):
        self.cmds.append(('C', (x1, y1, x2, y2, x, y))); self.pt = (x, y); return self

    def arc(self, cx, cy, rx, ry, a0, a1):
        """Elliptic arc from angle a0 to a1 (degrees, counter-clockwise positive).
        The current point should already be at a0."""
        n = max(1, int(math.ceil(abs(a1 - a0) / 90)))
        step = (a1 - a0) / n
        for i in range(n):
            t0 = math.radians(a0 + i * step); t1 = math.radians(a0 + (i + 1) * step)
            k = 4 / 3 * math.tan((t1 - t0) / 4)
            p0 = (cx + rx * math.cos(t0), cy + ry * math.sin(t0))
            p3 = (cx + rx * math.cos(t1), cy + ry * math.sin(t1))
            p1 = (p0[0] - k * rx * math.sin(t0), p0[1] + k * ry * math.cos(t0))
            p2 = (p3[0] + k * rx * math.sin(t1), p3[1] - k * ry * math.cos(t1))
            self.curve(*p1, *p2, *p3)
        return self

    def close(self):
        self.cmds.append(('Z', ())); return self


def at(cx, cy, rx, ry, a):
    t = math.radians(a)
    return (cx + rx * math.cos(t), cy + ry * math.sin(t))


def stroke(skel, vertical, horizontal=None, cap=BUTT, join=JOIN_ROUND):
    """Stroke a skeleton with a broad 'elliptical pen': vertical strokes get
    `vertical` width, horizontal strokes `horizontal` width (grotesk contrast)."""
    horizontal = horizontal or vertical
    k = vertical / horizontal
    p = pathops.Path()
    for op, a in skel.cmds:
        if op == 'M':
            p.moveTo(a[0], a[1] * k)
        elif op == 'L':
            p.lineTo(a[0], a[1] * k)
        elif op == 'C':
            p.cubicTo(a[0], a[1] * k, a[2], a[3] * k, a[4], a[5] * k)
        elif op == 'Z':
            p.close()
    p.stroke(vertical, cap, join, 4)
    p.convertConicsToQuads()
    return simplify(transform(p, d=1 / k))


def ellipse_ring(x0, y0, x1, y1, vertical, horizontal):
    """A closed oval whose outer edge fills the box (x0, y0, x1, y1)."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0 - vertical) / 2, (y1 - y0 - horizontal) / 2
    s = Skeleton(cx + rx, cy).arc(cx, cy, rx, ry, 0, 360).close()
    return stroke(s, vertical, horizontal)


# ---------- reading glyphs ----------

def glyph_path(glyphset, name, unslant=0.0):
    p = pathops.Path()
    glyphset[name].draw(_ToPath(glyphset, p))
    p = simplify(p)
    if unslant:
        p = transform(p, c=-math.tan(math.radians(unslant)))
    return p


def slant(p, angle):
    return transform(p, c=math.tan(math.radians(angle))) if angle else p


def bounds(p):
    return p.bounds  # (xmin, ymin, xmax, ymax)
