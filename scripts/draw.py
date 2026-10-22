"""Draw the added Greek and maths glyphs for one style of Schibsted Grotesk.

    python3 scripts/draw.py upstream/SchibstedGrotesk-Regular.ttf sources/Regular.ufo

Each glyph is a recipe: built from the font's own letters (cut, joined, mirrored)
where a Greek letter shares their structure, drawn as a stroked centre-line
where it doesn't. Stem widths, heights and sidebearings are measured from the
font, so the same recipes serve every weight and the italic.

Glyphs listed in sources/hand-edited.txt are left alone, so a glyph can be
finished by hand in a font editor without being overwritten.
"""
import math
import sys
from pathlib import Path

import ufoLib2
from fontTools.ttLib import TTFont

from geometry import (BUTT, JOIN_MITER, Skeleton, bounds, ellipse_ring, glyph_path,
                      intersect, move, polygon, rect, slant, stroke, subtract,
                      transform, union)

BIG = 10000


class Font:
    """The base font, un-slanted, with its measured proportions."""

    def __init__(self, path):
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.italic = -self.tt['post'].italicAngle  # 12 for the italic
        self._cache = {}
        os2 = self.tt['OS/2']
        self.xh, self.cap = os2.sxHeight, os2.sCapHeight
        o = self.bounds('o')
        self.os = o[3] - self.xh                      # overshoot
        self.asc = self.bounds('l')[3]
        self.desc = self.bounds('p')[1]
        self.V = self.hspan('n', self.xh * 0.45)[0][1]           # straight stem
        self.Vr = self.hspan('o', (o[1] + o[3]) / 2)[0][1]       # round stem
        self.H = self.vspan('o', (o[0] + o[2]) / 2)[-1][1]       # thin horizontal
        self.CV = self.hspan('H', self.cap * 0.25)[0][1]
        self.CH = self.vspan('E', (self.bounds('E')[0] + self.bounds('E')[2]) / 2)[-1][1]
        self.D = self.hspan('v', self.xh * 0.6)[0][1]            # diagonal, measured across
        self.SB = self.lsb('n')                                  # straight sidebearing
        self.SBr = self.lsb('o')                                 # round
        self.SBd = self.lsb('v')                                 # diagonal

    def name(self, ch):
        return self.cmap[ord(ch)] if len(ch) == 1 else ch

    def path(self, ch):
        n = self.name(ch)
        if n not in self._cache:
            self._cache[n] = glyph_path(self.gs, n, unslant=self.italic)
        return self._cache[n]

    def bounds(self, ch):
        return bounds(self.path(ch))

    def adv(self, ch):
        return self.tt['hmtx'][self.name(ch)][0]

    def lsb(self, ch):
        return self.bounds(ch)[0]

    def rsb(self, ch):
        return self.adv(ch) - self.bounds(ch)[2]

    def hspan(self, ch, y):
        """[(x, width), ...] of the ink crossed by a horizontal line at y."""
        cut = intersect(self.path(ch), rect(-BIG, y - 0.5, BIG, y + 0.5))
        return sorted((c[0], c[2] - c[0]) for c in (_cb(k) for k in cut.contours))

    def vspan(self, ch, x):
        """[(y, height), ...] of the ink crossed by a vertical line at x, bottom up."""
        cut = intersect(self.path(ch), rect(x - 0.5, -BIG, x + 0.5, BIG))
        return sorted((c[1], c[3] - c[1]) for c in (_cb(k) for k in cut.contours))


def _cb(contour):
    import pathops
    p = pathops.Path()
    contour.draw(p.getPen())
    return p.bounds


def fit(p, lsb, rsb):
    """Place the outline at the given sidebearings; returns (outline, advance)."""
    x0, _, x1, _ = bounds(p)
    return move(p, lsb - x0), round(x1 - x0 + lsb + rsb)


def para(x0, y0, x1, y1, w):
    """A diagonal stroke with horizontal ends, `w` wide measured horizontally."""
    return polygon((x0 - w / 2, y0), (x0 + w / 2, y0), (x1 + w / 2, y1), (x1 - w / 2, y1))


# ---------- recipes: each returns (outline, advance) in upright space ----------

def r_kappa(f):
    return intersect(f.path('k'), rect(-BIG, -BIG, BIG, f.xh)), f.adv('k')


def r_rho(f):
    o, p = f.bounds('o'), f.bounds('p')
    sx = (p[2] - p[0]) / (o[2] - o[0])
    bowl = transform(f.path('o'), a=sx, e=p[0] - o[0] * sx)
    stem = rect(p[0], f.desc, p[0] + f.V, (o[1] + o[3]) / 2)
    return union(bowl, stem), f.adv('p')


def r_sigma(f):
    o = f.bounds('o'); cx = (o[0] + o[2]) / 2
    top = o[3]                  # the bar sits on the bowl's overshoot, so they meet flush
    bowl = subtract(f.path('o'), rect(cx, top, BIG, BIG))
    bar = rect(cx - 0.04 * (o[2] - o[0]), top - f.H, o[2] + 0.1 * (o[2] - o[0]), top)
    return fit(union(bowl, bar), f.SBr, f.SBd * 0.6)


def _lunate(f, y0, y1, width, v, h, bar=True):
    """∈-like: a semicircle open to the right with a middle bar."""
    L = f.SB
    lc = L + v / 2
    yc = (y0 + y1) / 2
    ry = (y1 - y0 - h) / 2
    rx = ry * 0.98
    cx = lc + rx
    R = L + width
    s = (Skeleton(R, y1 - h / 2).line(cx, y1 - h / 2)
         .arc(cx, yc, rx, ry, 90, 270).line(R, y0 + h / 2))
    out = stroke(s, v, h)
    if bar:
        out = union(out, rect(lc, yc - h / 2, R - 0.06 * width, yc + h / 2))
    return fit(out, L, f.SB * 0.55)


def r_epsilon_lunate(f):        # ϵ (\epsilon in unicode-math)
    o = f.bounds('o')
    return _lunate(f, -f.os, f.xh + f.os, 0.8 * (o[2] - o[0]), f.Vr, f.H)


def r_element(f):               # ∈
    m = f.bounds('×')
    yc = (m[1] + m[3]) / 2
    half = 0.56 * (m[3] - m[1])
    return _lunate(f, yc - half, yc + half, 0.86 * 2 * half, f.V, f.H)


def r_epsilon(f):               # ε (\varepsilon)
    o = f.bounds('o'); w = o[2] - o[0]
    v, h = f.Vr * 0.97, f.H
    L = f.SBr
    mid = f.xh * 0.53
    # upper bowl: smaller, sits on the middle
    ux0, ux1, uy0, uy1 = L + 0.06 * w, L + 0.86 * w, mid - h / 2, f.xh + f.os
    ucx, ucy = (ux0 + ux1) / 2 + 0.04 * w, (uy0 + uy1) / 2
    urx, ury = ucx - ux0 - v / 2, (uy1 - uy0 - h) / 2
    upper = Skeleton(*_pt(ucx, ucy, urx, ury, 18)).arc(ucx, ucy, urx, ury, 18, 270)
    # lower bowl: wider
    lx0, lx1, ly0, ly1 = L, L + 0.9 * w, -f.os, mid + h / 2
    lcx, lcy = (lx0 + lx1) / 2 + 0.04 * w, (ly0 + ly1) / 2
    lrx, lry = lcx - lx0 - v / 2, (ly1 - ly0 - h) / 2
    lower = Skeleton(*_pt(lcx, lcy, lrx, lry, 90)).arc(lcx, lcy, lrx, lry, 90, 342)
    middle = rect(ucx - 0.12 * w, mid - h / 2, ucx + 0.02 * w, mid + h / 2)
    out = union(stroke(upper, v, h), stroke(lower, v, h), middle)
    return fit(out, L, f.SBr * 0.7)


def _pt(cx, cy, rx, ry, a):
    t = math.radians(a)
    return cx + rx * math.cos(t), cy + ry * math.sin(t)


def r_lambda(f):
    d = f.D
    left, right = f.SBd + d / 2, f.SBd + 0.92 * (f.adv('v') - 2 * f.SBd) - d / 2
    top = (left + 0.2 * (right - left), f.asc)
    long_ = para(top[0], top[1], right, 0, d)
    t = 0.56                                   # where the short leg meets the long one
    meet = (top[0] + (right - top[0]) * t, f.asc * (1 - t))
    foot = left + meet[1] * math.tan(math.radians(f.italic)) * 0.6  # keep the leg's angle once slanted
    short = para(foot, 0, meet[0], meet[1], d)
    out = intersect(union(long_, short), rect(-BIG, 0, BIG, f.asc))
    return fit(out, f.SBd, f.SBd)


def r_chi(f):
    d = f.D * 1.02
    w = f.adv('x') - 2 * f.SBd
    l, r = f.SBd + d / 2, f.SBd + w - d / 2
    out = union(para(l, f.xh, r, f.desc, d), para(r, f.xh, l, f.desc, d))
    out = intersect(out, rect(-BIG, f.desc, BIG, f.xh))
    return fit(out, f.SBd, f.SBd)


def r_gamma(f):
    d = f.D
    w = f.adv('v') - 2 * f.SBd
    l, r = f.SBd + d / 2, f.SBd + w - d / 2
    cx = (l + r) / 2
    arms = union(para(l, f.xh, cx, 0, d), para(r, f.xh, cx, 0, d))
    arms = intersect(arms, rect(-BIG, 0, BIG, f.xh))
    tail = rect(cx - f.V / 2, f.desc, cx + f.V / 2, f.H)
    return fit(union(arms, tail), f.SBd, f.SBd)


def r_delta(f):
    bowl = f.path('o')
    o = bounds(bowl); w = o[2] - o[0]; cx = (o[0] + o[2]) / 2
    v, h = f.Vr, f.H
    yt = f.asc - h / 2
    # leaves the bowl at its top, rises steeply to the left, then turns right into a flat top
    s = (Skeleton(cx + 0.04 * w, f.xh - 0.3 * h)
         .curve(cx - 0.10 * w, f.xh + 0.03 * f.xh, cx - 0.29 * w, f.xh + 0.06 * f.xh,
                cx - 0.29 * w, f.xh + 0.18 * f.xh)
         .curve(cx - 0.29 * w, yt - 0.03 * f.xh, cx - 0.18 * w, yt, cx + 0.02 * w, yt)
         .line(cx + 0.36 * w, yt))
    # less contrast than elsewhere: the rising stroke is shallow and would get too thin
    return fit(union(bowl, stroke(s, v, (v + h) / 2)), f.SBr, f.SBr * 0.8)


def r_zeta(f):
    o = f.bounds('o'); w = (o[2] - o[0]) * 0.84
    v, h = f.Vr, f.H
    L = f.SBr + v / 2
    R = L + w - v
    yt = f.asc - h / 2
    yb = h / 2
    p1 = (R, yt)
    p2 = (L + 0.12 * w, f.xh * 0.40)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    n = math.hypot(dx, dy)
    c1 = (p2[0] + dx / n * 0.16 * f.xh, p2[1] + dy / n * 0.16 * f.xh)   # keep the spine's direction
    s = (Skeleton(L - 0.02 * w, yt).line(*p1).line(*p2)
         .curve(*c1, L + 0.02 * w, yb, L + 0.36 * w, yb)
         .line(R - 0.24 * w, yb)
         .curve(R - 0.06 * w, yb, R, yb - 0.08 * f.xh, R, yb - 0.22 * f.xh)
         .line(R, f.desc * 0.82))
    return fit(stroke(s, v, h, join=JOIN_MITER), f.SBr, f.SBr * 0.8)


def r_theta(f):
    o = f.bounds('o'); w = 0.9 * (o[2] - o[0])
    ring = ellipse_ring(0, -f.os, w, f.asc + f.os, f.Vr, f.H)
    yc = f.asc / 2
    bar = rect(f.Vr / 2, yc - f.H / 2, w - f.Vr / 2, yc + f.H / 2)
    return fit(union(ring, bar), f.SBr, f.SBr)


def r_eta(f):
    stem = f.hspan('n', f.xh * 0.45)[-1]
    leg = rect(stem[0], f.desc, stem[0] + stem[1], f.H)
    return union(f.path('n'), leg), f.adv('n')


def r_tau(f):
    t = intersect(f.path('t'), rect(-BIG, -BIG, BIG, f.xh))
    stem = f.hspan('t', f.xh * 0.5)[0]
    sc = stem[0] + stem[1] / 2
    bar = f.hspan('t', f.xh - f.H / 2)[0]
    reach = max(bar[0] + bar[1] - sc, sc - bar[0])     # make the bar symmetric
    out = union(t, rect(sc - reach, f.xh - f.H, sc + reach, f.xh))
    return fit(out, f.SBd, f.SBd)


def _cup(f):
    o = f.bounds('o'); cy = (o[1] + o[3]) / 2
    bottom = intersect(f.path('o'), rect(-BIG, -BIG, BIG, cy))
    sides = union(rect(o[0], cy - 1, o[0] + f.Vr, f.xh), rect(o[2] - f.Vr, cy - 1, o[2], f.xh))
    return union(bottom, sides)


def r_upsilon(f):
    return _cup(f), f.adv('o')


def r_psi(f):
    cup = _cup(f); o = bounds(cup); cx = (o[0] + o[2]) / 2
    stem = rect(cx - f.V / 2, f.desc, cx + f.V / 2, f.asc)
    return fit(union(cup, stem), f.SBr, f.SBr)


def r_phi(f):
    o = f.bounds('o'); w = 1.06 * (o[2] - o[0])
    ring = ellipse_ring(0, -f.os, w, f.xh + f.os, f.Vr, f.H)
    stem = rect(w / 2 - f.V / 2, f.desc, w / 2 + f.V / 2, f.asc)
    return fit(union(ring, stem), f.SBr, f.SBr)


def r_omega(f):
    o = f.bounds('o'); w = 1.42 * (o[2] - o[0])
    v, h = f.Vr, f.H
    L, R = v / 2, w - v / 2
    M = w / 2
    cy = f.xh * 0.42
    ry = cy - (-f.os + h / 2)
    top = f.xh * 0.62
    left = (Skeleton(L, f.xh).line(L, cy)
            .arc((L + M) / 2, cy, (M - L) / 2, ry, 180, 360).line(M, top))
    right = (Skeleton(R, f.xh).line(R, cy)
             .arc((R + M) / 2, cy, (R - M) / 2, ry, 360, 180).line(M, top))
    out = union(stroke(left, v, h), stroke(right, v, h))
    return fit(out, f.SBr, f.SBr)


# capitals

def r_Gamma(f):
    e = f.bounds('E')
    stem_r = f.hspan('E', f.cap * 0.25)[0]
    keep = union(rect(-BIG, -BIG, stem_r[0] + stem_r[1], BIG), rect(-BIG, f.cap - f.CH - 1, BIG, BIG))
    return intersect(f.path('E'), keep), f.adv('E') - round(0.04 * (e[2] - e[0]))


def r_Lambda(f):
    return transform(f.path('V'), d=-1, f=f.cap), f.adv('V')


def r_Theta(f):
    O = f.bounds('O'); w = O[2] - O[0]
    yc = (O[1] + O[3]) / 2
    bar = rect(O[0] + 0.3 * w, yc - f.CH / 2, O[2] - 0.3 * w, yc + f.CH / 2)
    return union(f.path('O'), bar), f.adv('O')


def r_Xi(f):
    S = f.bounds('Σ'); x0, x1 = S[0] + 0.02 * (S[2] - S[0]), S[2] - 0.02 * (S[2] - S[0])
    inset = 0.12 * (x1 - x0)
    yc = f.cap / 2
    out = union(rect(x0, f.cap - f.CH, x1, f.cap), rect(x0, 0, x1, f.CH),
                rect(x0 + inset, yc - f.CH / 2, x1 - inset, yc + f.CH / 2))
    return out, f.adv('Σ')


def r_Phi(f):
    O = f.bounds('O'); w = 1.0 * (O[2] - O[0])
    ring = ellipse_ring(0, f.cap * 0.16, w, f.cap * 0.84, f.CV, f.CH)
    stem = rect(w / 2 - f.CV / 2, 0, w / 2 + f.CV / 2, f.cap)
    return fit(union(ring, stem), f.SBr, f.SBr)


def r_Psi(f):
    O = f.bounds('O'); w = 1.0 * (O[2] - O[0])
    v, h = f.CV, f.CH
    L, R = v / 2, w - v / 2
    cx = w / 2
    ybot = f.cap * 0.30 + h / 2
    rx = (R - L) / 2
    ry = rx * 0.82
    yc = ybot + ry
    cup = Skeleton(L, f.cap).line(L, yc).arc(cx, yc, rx, ry, 180, 360).line(R, f.cap)
    stem = rect(cx - v / 2, 0, cx + v / 2, f.cap)
    return fit(union(stroke(cup, v, h), stem), f.SB * 0.6, f.SB * 0.6)


# maths

def r_nabla(f):
    return transform(f.path('Δ'), d=-1, f=f.cap), f.adv('Δ')


def r_forall(f):
    return transform(f.path('A'), d=-1, f=f.cap), f.adv('A')


def r_exists(f):
    p = transform(f.path('E'), a=-1)
    return fit(p, f.rsb('E'), f.lsb('E'))


def r_minusplus(f):
    b = f.bounds('±')
    return transform(f.path('±'), d=-1, f=b[1] + b[3]), f.adv('±')



def r_perp(f):
    """⊥: an upturned T in the weight of +, as wide as +, cap height tall."""
    b = f.bounds('+')
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    v = f.hspan('+', (cy + b[3]) / 2)[0][1]       # vertical arm, across
    h = f.vspan('+', (b[0] + cx) / 2)[0][1]       # horizontal arm, up
    bar = rect(b[0], 0, b[2], h)
    stem = rect(cx - v / 2, 0, cx + v / 2, f.cap)
    return union(bar, stem), f.adv('+')

# name -> (unicode, recipe or alias base)
GLYPHS = {
    # Greek capitals that are Latin letters
    'uni0391': (0x0391, 'A'), 'uni0392': (0x0392, 'B'), 'uni0395': (0x0395, 'E'),
    'uni0396': (0x0396, 'Z'), 'uni0397': (0x0397, 'H'), 'uni0399': (0x0399, 'I'),
    'uni039A': (0x039A, 'K'), 'uni039C': (0x039C, 'M'), 'uni039D': (0x039D, 'N'),
    'uni039F': (0x039F, 'O'), 'uni03A1': (0x03A1, 'P'), 'uni03A4': (0x03A4, 'T'),
    'uni03A5': (0x03A5, 'Y'), 'uni03A7': (0x03A7, 'X'),
    # drawn capitals
    'uni0393': (0x0393, r_Gamma), 'uni0398': (0x0398, r_Theta), 'uni039B': (0x039B, r_Lambda),
    'uni039E': (0x039E, r_Xi), 'uni03A6': (0x03A6, r_Phi), 'uni03A8': (0x03A8, r_Psi),
    # lowercase
    'uni03BF': (0x03BF, 'o'), 'uni03B9': (0x03B9, 'ı'), 'uni03BD': (0x03BD, 'v'),
    'uni03B3': (0x03B3, r_gamma), 'uni03B4': (0x03B4, r_delta), 'uni03B5': (0x03B5, r_epsilon),
    'uni03B6': (0x03B6, r_zeta), 'uni03B7': (0x03B7, r_eta), 'uni03B8': (0x03B8, r_theta),
    'uni03BA': (0x03BA, r_kappa), 'uni03BB': (0x03BB, r_lambda), 'uni03C1': (0x03C1, r_rho),
    'uni03C3': (0x03C3, r_sigma), 'uni03C4': (0x03C4, r_tau), 'uni03C5': (0x03C5, r_upsilon),
    'uni03C6': (0x03C6, r_phi), 'uni03C7': (0x03C7, r_chi), 'uni03C8': (0x03C8, r_psi),
    'uni03C9': (0x03C9, r_omega), 'uni03D5': (0x03D5, r_phi), 'uni03F5': (0x03F5, r_epsilon_lunate),
    # maths
    'uni2207': (0x2207, r_nabla), 'uni2208': (0x2208, r_element), 'uni2200': (0x2200, r_forall),
    'uni2203': (0x2203, r_exists), 'uni2213': (0x2213, r_minusplus),
    'uni22C5': (0x22C5, '·'), 'uni223C': (0x223C, '~'),
    'uni22A5': (0x22A5, r_perp),
}


def draw(font_path, ufo_path, only=None):
    f = Font(font_path)
    keep = set()
    hand = Path(__file__).resolve().parent.parent / 'sources' / 'hand-edited.txt'
    if hand.exists():
        keep = {ln.split('#')[0].strip() for ln in hand.read_text().splitlines()} - {''}
    ufo_path = Path(ufo_path)
    ufo = ufoLib2.Font.open(ufo_path) if ufo_path.exists() else ufoLib2.Font()
    ufo.info.unitsPerEm = f.tt['head'].unitsPerEm
    ufo.info.xHeight, ufo.info.capHeight = f.xh, f.cap
    ufo.info.italicAngle = -f.italic
    for name, (uni, recipe) in GLYPHS.items():
        if name in keep or (only and name not in only):
            continue
        if name in f.tt.getGlyphOrder():
            continue  # the font already has it
        if name in ufo:
            del ufo[name]
        g = ufo.newGlyph(name)
        g.unicodes = [uni]
        if isinstance(recipe, str):
            base = f.name(recipe)
            g.width = f.adv(recipe)
            g.getPen().addComponent(base, (1, 0, 0, 1, 0, 0))
            continue
        outline, width = recipe(f)
        outline = slant(outline, f.italic)
        g.width = width
        outline.draw(g.getPen())
    ufo.save(ufo_path, overwrite=True)
    return f


if __name__ == '__main__':
    draw(sys.argv[1], sys.argv[2], set(sys.argv[3:]) or None)
