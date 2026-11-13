"""Accents for the Greek letters: monotonic precomposed forms and mark anchors.

Schibsted Grotesk positions combining marks with a mark-to-base lookup, but only
on its own letters; the Greek letters drawn by scripts/draw.py had no anchors, so
in λέξη the acute landed beside the letter. This module, run on the built font:

- gives every Greek letter without one a top anchor: the Latin twin's for Α Ε Ι Ο…,
  otherwise centred over the top of the glyph at x-height, ascender or cap height;
- puts the Greek capitals into the context that switches marks to their .case form
  after a capital, as it does after A–Z;
- adds the monotonic precomposed letters ά έ ή ί ό ύ ώ ϊ ϋ ΐ ΰ, Ά Έ Ή Ί Ό Ύ Ώ Ϊ Ϋ and
  the spacing ΄ ΅ as composites of the letter and the font's own acute and dieresis,
  so typed (precomposed) Greek never depends on mark positioning at all. On the
  capitals the tonos stands to the left of the letter, as Greek typography has it.

Returns the kerning sides for the new letters (see scripts/kern.py).
"""
import math

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

from geometry import glyph_path, intersect, rect

BIG = 10000

# precomposed letter: (base, marks...) — marks stacked on the base's top anchor
LOWER = {
    'ά': ('α', 'acutecomb'), 'έ': ('ε', 'acutecomb'), 'ή': ('η', 'acutecomb'),
    'ί': ('ι', 'acutecomb'), 'ό': ('ο', 'acutecomb'), 'ύ': ('υ', 'acutecomb'),
    'ώ': ('ω', 'acutecomb'),
    'ϊ': ('ι', 'uni0308'), 'ϋ': ('υ', 'uni0308'),
    'ΐ': ('ι', 'uni0308', 'acutecomb'), 'ΰ': ('υ', 'uni0308', 'acutecomb'),
}
UPPER_DIERESIS = {'Ϊ': 'Ι', 'Ϋ': 'Υ'}
UPPER_TONOS = {'Ά': 'Α', 'Έ': 'Ε', 'Ή': 'Η', 'Ί': 'Ι', 'Ό': 'Ο', 'Ύ': 'Υ', 'Ώ': 'Ω'}
SPACING = {'΄': ('acutecomb',), '΅': ('uni0308', 'acutecomb')}


def _uni(ch):
    return 'uni%04X' % ord(ch)


def _mark_lookups(tt):
    """(MarkBasePos subtable carrying acutecomb, the chain context for .case marks)."""
    gpos = tt['GPOS'].table
    base = None
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag != 'mark':
            continue
        for i in fr.Feature.LookupListIndex:
            lk = gpos.LookupList.Lookup[i]
            for st in lk.SubTable:
                s = st.ExtSubTable if lk.LookupType == 9 else st
                if getattr(s, 'LookupType', lk.LookupType) == 4 and 'acutecomb' in s.MarkCoverage.glyphs:
                    base = base or s
    gsub = tt['GSUB'].table
    case_ctx = []
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag != 'ccmp':
            continue
        for i in fr.Feature.LookupListIndex:
            lk = gsub.LookupList.Lookup[i]
            for st in lk.SubTable:
                s = st.ExtSubTable if lk.LookupType == 7 else st
                if (getattr(s, 'LookupType', lk.LookupType) == 6 and s.Format == 3
                        and s.BacktrackCoverage and 'A' in s.BacktrackCoverage[0].glyphs
                        and 'acutecomb' in s.InputCoverage[0].glyphs):
                    case_ctx.append(s.BacktrackCoverage[0])
    return base, case_ctx


class _Font:
    def __init__(self, tt):
        self.tt = tt
        self.gs = tt.getGlyphSet()
        self.cmap = tt.getBestCmap()
        self.glyf, self.hmtx = tt['glyf'], tt['hmtx']
        self.tan = math.tan(math.radians(-tt['post'].italicAngle))
        self.xh, self.cap = tt['OS/2'].sxHeight, tt['OS/2'].sCapHeight

    def name(self, ch):
        return self.cmap[ord(ch)] if len(ch) == 1 else ch

    def box(self, n):
        g = self.glyf[n]
        g.recalcBounds(self.glyf)
        return (g.xMin, g.yMin, g.xMax, g.yMax) if hasattr(g, 'xMin') else (0, 0, 0, 0)

    def span(self, n, y0, y1):
        """(xmin, xmax) of the ink between heights y0 and y1, or None."""
        cut = intersect(glyph_path(self.gs, n), rect(-BIG, y0, BIG, y1))
        b = cut.bounds
        return None if b == (0, 0, 0, 0) else (b[0], b[2])


def _anchors(f, sub, cls, greek):
    """Top anchors for the Greek letters the mark lookup doesn't know."""
    cov = sub.BaseCoverage.glyphs
    recs = dict(zip(cov, sub.BaseArray.BaseRecord))
    def anchor_of(n):
        a = recs[n].BaseAnchor[cls] if n in recs else None
        return (a.XCoordinate, a.YCoordinate) if a else None
    y_low, y_asc, y_cap = anchor_of('o')[1], anchor_of('l')[1], anchor_of('A')[1]
    added = {}
    for ch, n in greek:
        if n in recs:
            continue
        g = f.glyf[n]
        if g.isComposite() and len(g.components) == 1 and g.components[0].glyphName in recs:
            c = g.components[0]
            rec = otTables.BaseRecord()
            rec.BaseAnchor = []
            for a in recs[c.glyphName].BaseAnchor:      # all classes, moved with the component
                if a is None:
                    rec.BaseAnchor.append(None)
                    continue
                b = otTables.Anchor(); b.Format = 1
                b.XCoordinate, b.YCoordinate = a.XCoordinate + c.x, a.YCoordinate + c.y
                rec.BaseAnchor.append(b)
            added[n] = rec
            continue
        x0, _, x1, top = f.box(n)
        if ch.isupper():
            y = y_cap
        else:
            y = y_asc if top > f.xh + 0.08 * f.xh else y_low
        ym = min(top, y) - 100                        # just under the top of the ink
        s = f.span(n, ym, ym + 1) or (x0, x1)
        x = (s[0] + s[1]) / 2 + f.tan * (y - ym)      # carried up the slant to the anchor
        rec = otTables.BaseRecord()
        rec.BaseAnchor = [None] * sub.ClassCount
        a = otTables.Anchor(); a.Format = 1
        a.XCoordinate, a.YCoordinate = round(x), round(y)
        rec.BaseAnchor[cls] = a
        added[n] = rec
    if added:
        recs.update(added)
        gid = f.tt.getGlyphID
        order = sorted(recs, key=gid)
        sub.BaseCoverage.glyphs = order
        sub.BaseArray.BaseRecord = [recs[n] for n in order]
        sub.BaseArray.BaseCount = len(order)
    return {n: (r.BaseAnchor[cls].XCoordinate, r.BaseAnchor[cls].YCoordinate)
            for n, r in recs.items() if r.BaseAnchor[cls]}


def _add(f, name, uni, comps, width):
    pen = TTGlyphPen(f.gs)
    for base, dx, dy in comps:
        pen.addComponent(base, (1, 0, 0, 1, round(dx), round(dy)))
    g = pen.glyph()
    f.glyf[name] = g
    g.recalcBounds(f.glyf)
    f.hmtx[name] = (round(width), getattr(g, 'xMin', 0))
    for table in f.tt['cmap'].tables:
        if table.isUnicode():
            table.cmap[uni] = name


def accents(tt):
    f = _Font(tt)
    sub, case_ctx = _mark_lookups(tt)
    marks = dict(zip(sub.MarkCoverage.glyphs, sub.MarkArray.MarkRecord))
    cls = marks['acutecomb'].Class
    greek = [(chr(u), n) for u, n in sorted(f.cmap.items()) if 0x370 <= u < 0x400 and chr(u).isalpha()]
    top = _anchors(f, sub, cls, greek)

    # .case marks after Greek capitals too
    gid = tt.getGlyphID
    caps = [n for ch, n in greek if ch.isupper()]
    for c in case_ctx:
        c.glyphs = sorted(set(c.glyphs) | set(caps), key=gid)

    def mark_at(m, anchor):
        r = marks[m].MarkAnchor
        return (m, anchor[0] - r.XCoordinate, anchor[1] - r.YCoordinate)

    def dialytika_tonos(anchor):
        """Two dots spread wide enough for the acute to stand between them."""
        _, dx, dy = mark_at('uni0307', anchor)
        d0, d1, d2, d3 = f.box('uni0307')
        dw = d2 - d0
        a0, a1, a2, a3 = f.box('acutecomb')
        _, adx, ady = mark_at('acutecomb', anchor)
        cx = (d0 + d2) / 2 + dx                       # where the single dot would be
        half = (a2 - a0) / 2 + 0.35 * dw + dw / 2     # dot centre from the middle
        lift = (d1 + dy) - (a1 + ady) + 0.15 * (d3 - d1)   # acute's foot just above the dots' feet
        acx = (a0 + a2) / 2 + adx
        return [('uni0307', dx - half, dy), ('uni0307', dx + half, dy),
                ('acutecomb', adx + cx - acx, ady + lift)]

    new, sides = [], {}
    for ch, (base, *ms) in LOWER.items():
        b = f.name(base)
        if ms == ['uni0308', 'acutecomb']:
            comps = [(b, 0, 0)] + dialytika_tonos(top[b])
        else:
            comps = [(b, 0, 0)] + [mark_at(m, top[b]) for m in ms]
        new.append((ch, comps, f.hmtx[b][0]))
        sides[ch] = base
    for ch, base in UPPER_DIERESIS.items():
        b = f.name(base)
        new.append((ch, [(b, 0, 0), mark_at('uni0308', top[b])], f.hmtx[b][0]))
        sides[ch] = base
    # capitals: the lowercase acute, its top at cap height, to the left of the letter,
    # which moves right just far enough to clear it at the top
    ax0, ay0, ax1, ay1 = f.box('acutecomb')
    lsb = f.hmtx['H'][1] * 0.35
    dy = f.cap - ay1
    for ch, base in UPPER_TONOS.items():
        b = f.name(base)
        dx = lsb - ax0
        right = ax1 + dx                              # right edge of the tonos
        band = f.span(b, ay0 + dy, f.cap)
        gap = f.hmtx['H'][1] * 0.45
        shift = max(0, right + gap - (band[0] if band else f.box(b)[0]))
        new.append((ch, [(b, shift, 0), ('acutecomb', dx, dy)], f.hmtx[b][0] + shift))
        sides[ch] = (None, base)
    # spacing tonos and dialytika tonos: the marks over an imaginary x-height letter
    for ch, ms in SPACING.items():
        w = f.hmtx['o'][0] * 0.55
        y = top['o'][1]                               # the italic leans about mid-x-height
        anchor = (w / 2 + f.tan * (y - f.xh / 2), y)
        comps = dialytika_tonos(anchor) if len(ms) == 2 else [mark_at(m, anchor) for m in ms]
        new.append((ch, comps, w))

    for i, (ch, comps, width) in enumerate(new):
        # spread dots must not reach into the next letter: widen the glyph to hold them
        x0 = min(f.box(c)[0] + dx for c, dx, _ in comps)
        x1 = max(f.box(c)[2] + dx for c, dx, _ in comps)
        pad = f.hmtx['H'][1] * 0.25
        grow_l = max(0, pad - x0)
        grow_r = max(0, x1 + pad - width)
        if grow_l or grow_r:
            comps = [(c, dx + grow_l, dy) for c, dx, dy in comps]
            new[i] = (ch, comps, width + grow_l + grow_r)
    for ch, comps, width in new:
        name = _uni(ch)
        if name in tt.getGlyphOrder() or ord(ch) in f.cmap:
            continue
        _add(f, name, ord(ch), comps, width)
    tt.setGlyphOrder(f.glyf.glyphOrder)
    if 'GDEF' in tt and tt['GDEF'].table.GlyphClassDef:
        for ch, _, _ in new:
            tt['GDEF'].table.GlyphClassDef.classDefs[_uni(ch)] = 1
    return sides
