"""A rounded corner whose curvature changes smoothly from end to end.

The corner turns from going straight up at S = (0, 0) to going right at T = (w, h),
like the top-left of the a's bowl. It is defined by its curvature as a function
of arc length, k(s), not by control points:

  - at S, k and dk/ds equal the bowl's (`k_side`, `dk_side`), so the curvature
    comb runs on from the bowl below without a step or a kink;
  - at T, k = 0 and dk/ds = 0, so the bend eases out into the flat top and there
    is no point where it visibly starts;
  - between them k(s) is a polynomial: the cubic Hermite blend of those end
    conditions plus four bumps that vanish, with their slopes, at both ends.
    For any weights of the last two bumps, the length L and the first two
    weights are solved (Newton) so the curve turns exactly 90 degrees and lands
    exactly on T; the last two are chosen (Nelder-Mead) to make the curvature
    as even as possible, i.e. to minimise the integral of (dk/ds)^2.

This is the idea behind clothoid or "continuous" corners (Apple's rounded
rectangles), carried one step further so the comb itself has no corners. The
curve is then written as a chain of short cubics that match its position,
direction and curvature at every node, so the outline stays G2 everywhere and
follows the true curve to a small fraction of a unit.

Pure Python, so the build needs nothing beyond fontTools.

    segs = corner(w, h, k_side, dk_side)   # [(p1, p2, p3), ...] cubics from S, origin at S
"""
import math

M = 240          # integration steps along the corner
SEGMENTS = 6     # cubics in the output


def _polymul(a, b):
    out = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


_B = [1, -2, 1]                                          # (1 - u)^2, times u^2 below
BUMPS = [[0, 0] + _polymul(_B, q) for q in ([1], [-0.5, 1], [0.25, -1, 1], [-0.125, 0.75, -1.5, 1])]


def _kappa_coeffs(L, c1, c2, k0, d0, extra=(0.0, 0.0)):
    """Coefficients (in u = s / L, low to high) of k(u)."""
    # Hermite: k(0) = k0, k'(0) = d0 (per unit length, so d0 * L per unit u), k(1) = k'(1) = 0
    h00 = [1, 0, -3, 2]
    h10 = [0, 1, -2, 1]
    c = [0.0] * 8
    for i, v in enumerate(h00):
        c[i] += k0 * v
    for i, v in enumerate(h10):
        c[i] += d0 * L * v
    for wgt, b in zip((c1, c2) + tuple(extra), BUMPS):
        for i, v in enumerate(b):
            c[i] += wgt * v
    return c


def _trace(L, c1, c2, k0, d0, n=M, extra=(0.0, 0.0)):
    """Sample the curve: lists of (x, y), heading theta (0 = up, + = turning right), k."""
    kc = _kappa_coeffs(L, c1, c2, k0, d0, extra)
    tc = [0.0] + [L * v / (i + 1) for i, v in enumerate(kc)]   # theta(u) = L * integral of k du
    pts, ths, ks = [(0.0, 0.0)], [], []
    for i in range(n + 1):
        u = i / n
        ths.append(sum(v * u ** j for j, v in enumerate(tc)))
        ks.append(sum(v * u ** j for j, v in enumerate(kc)))
    ds = L / n
    x = y = 0.0
    for i in range(n):                          # Simpson on each step
        um = (i + 0.5) / n
        thm = sum(v * um ** j for j, v in enumerate(tc))
        th0, th1 = ths[i], ths[i + 1]
        x += ds / 6 * (math.sin(th0) + 4 * math.sin(thm) + math.sin(th1))
        y += ds / 6 * (math.cos(th0) + 4 * math.cos(thm) + math.cos(th1))
        pts.append((x, y))
    return pts, ths, ks


def _residual(v, w, h, k0, d0, extra):
    L, c1, c2 = v
    pts, ths, _ = _trace(L, c1, c2, k0, d0, 80, extra)
    return [(ths[-1] - math.pi / 2) * max(w, h), pts[-1][0] - w, pts[-1][1] - h]


def _solve3(J, r):
    """Solve J x = r for a 3x3 system (Cramer)."""
    def det(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    d = det(J)
    if abs(d) < 1e-18:
        raise ValueError('singular')
    out = []
    for c in range(3):
        m = [row[:] for row in J]
        for i in range(3):
            m[i][c] = r[i]
        out.append(det(m) / d)
    return out


def cubic_g2(p0, t0, k0, p3, t1, k1, guess):
    """Handle lengths (a0, a1) so a cubic from p0 to p3 with unit tangents t0, t1
    has signed curvatures k0, k1 at its ends (Newton from `guess`)."""
    D = (p3[0] - p0[0], p3[1] - p0[1])

    def cr(a, b):
        return a[0] * b[1] - a[1] * b[0]
    c01, c0D, cD1 = cr(t0, t1), cr(t0, D), cr(D, t1)
    a0 = a1 = guess

    def f(a0, a1):
        return ((2 / 3) * (c0D - a1 * c01) - k0 * a0 * a0,
                (2 / 3) * (cD1 - a0 * c01) - k1 * a1 * a1)
    for _ in range(50):
        f0, f1 = f(a0, a1)
        if abs(f0) + abs(f1) < 1e-12:
            break
        j00, j01 = -2 * k0 * a0, -(2 / 3) * c01
        j10, j11 = -(2 / 3) * c01, -2 * k1 * a1
        det = j00 * j11 - j01 * j10
        if abs(det) < 1e-18:
            break
        da0 = (f0 * j11 - f1 * j01) / det
        da1 = (j00 * f1 - j10 * f0) / det
        a0, a1 = a0 - da0, a1 - da1
    if not (0.2 * guess < a0 < 3 * guess and 0.2 * guess < a1 < 3 * guess):
        a0 = a1 = guess                          # fall back to plain Hermite handles
    return a0, a1


def _fit(w, h, k0, d0, extra, v=None):
    """(L, c1, c2) for which the curve with these extra bump weights ends at T,
    turned 90 degrees; None if Newton finds none."""
    v = v or [0.5 * math.pi / 2 * (w + h) * 0.9, 0.0, 0.0]
    for _ in range(60):                          # damped Newton on (L, c1, c2)
        r = _residual(v, w, h, k0, d0, extra)
        if max(abs(x) for x in r) < 1e-6:
            return v
        J = [[0.0] * 3 for _ in range(3)]
        for j in range(3):
            e = 1e-4 * (abs(v[j]) + 1) if j == 0 else 1e-7 + 1e-4 * abs(v[j])
            vp = v[:]
            vp[j] += e
            rp = _residual(vp, w, h, k0, d0, extra)
            for i in range(3):
                J[i][j] = (rp[i] - r[i]) / e
        try:
            step = _solve3(J, r)
        except ValueError:
            return None
        lam = 1.0
        n0 = sum(x * x for x in r)
        while lam > 1e-3:
            vt = [v[i] - lam * step[i] for i in range(3)]
            if vt[0] > 0 and sum(x * x for x in _residual(vt, w, h, k0, d0, extra)) < n0:
                break
            lam /= 2
        v = vt
    r = _residual(v, w, h, k0, d0, extra)
    return v if max(abs(x) for x in r) < 1e-3 else None


def _unevenness(v, k0, d0, extra):
    """Integral of (dk/ds)^2 (dimensionless); inf if the curve bends backwards."""
    L, c1, c2 = v
    kc = _kappa_coeffs(L, c1, c2, k0, d0, extra)
    dc = [i * x for i, x in enumerate(kc)][1:]           # dk/du
    n = 60
    tot = 0.0
    for i in range(n + 1):
        u = i / n
        if sum(x * u ** j for j, x in enumerate(kc)) < -1e-9:
            return float('inf')
        dk = sum(x * u ** j for j, x in enumerate(dc)) / L
        tot += dk * dk * (L / n) * (0.5 if i in (0, n) else 1)
    return tot * L ** 3


def _nelder_mead(f, x0, step, iters=200):
    pts = [list(x0), [x0[0] + step, x0[1]], [x0[0], x0[1] + step]]
    vals = [f(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(3), key=lambda i: vals[i])
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        if vals[-1] - vals[0] < 1e-9 * (abs(vals[0]) + 1e-9):
            break
        c = [(pts[0][j] + pts[1][j]) / 2 for j in range(2)]
        xr = [2 * c[j] - pts[2][j] for j in range(2)]
        fr = f(xr)
        if fr < vals[0]:
            xe = [3 * c[j] - 2 * pts[2][j] for j in range(2)]
            fe = f(xe)
            pts[2], vals[2] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[1]:
            pts[2], vals[2] = xr, fr
        else:
            xc = [(c[j] + pts[2][j]) / 2 for j in range(2)]
            fc = f(xc)
            if fc < vals[2]:
                pts[2], vals[2] = xc, fc
            else:
                for i in (1, 2):
                    pts[i] = [(pts[0][j] + pts[i][j]) / 2 for j in range(2)]
                    vals[i] = f(pts[i])
    i = min(range(3), key=lambda i: vals[i])
    return pts[i]


def corner(w, h, k_side, dk_side=0.0):
    """The corner as cubics [(p1, p2, p3), ...] starting at S = (0, 0)."""
    k0, d0 = k_side, dk_side
    base = _fit(w, h, k0, d0, (0.0, 0.0))
    if base is None:
        raise ValueError(f'no smooth corner for w={w:.1f} h={h:.1f} k={k0:.5f} dk={d0:.2e}')
    cache = {}

    def f(extra):
        v = _fit(w, h, k0, d0, tuple(extra), base[:])
        if v is None:
            return float('inf')
        cache[tuple(extra)] = v
        return _unevenness(v, k0, d0, tuple(extra))
    scale = abs(base[1]) + abs(base[2]) + 1 / max(w, h)
    extra = tuple(_nelder_mead(f, [0.0, 0.0], 0.5 * scale))
    v = cache.get(extra) or _fit(w, h, k0, d0, extra, base[:])
    if v is None or _unevenness(v, k0, d0, extra) == float('inf'):
        extra, v = (0.0, 0.0), base
    L, c1, c2 = v
    pts, ths, ks = _trace(L, c1, c2, k0, d0, M, extra)
    if min(ks) < -1e-9:
        raise ValueError(f'corner would bend backwards: w={w:.1f} h={h:.1f}')
    pts[-1] = (float(w), float(h))
    # write it as cubics matching position, direction and curvature at each node
    out = []
    step = M // SEGMENTS
    for i in range(0, M, step):
        j = i + step
        p0, p3 = pts[i], pts[j]
        t0 = (math.sin(ths[i]), math.cos(ths[i]))
        t1 = (math.sin(ths[j]), math.cos(ths[j]))
        ds = L * step / M
        a0, a1 = cubic_g2(p0, t0, -ks[i], p3, t1, -ks[j], ds / 3)
        out.append(((p0[0] + a0 * t0[0], p0[1] + a0 * t0[1]),
                    (p3[0] - a1 * t1[0], p3[1] - a1 * t1[1]), p3))
    return out
