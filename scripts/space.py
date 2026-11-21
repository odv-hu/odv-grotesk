"""Spacing (issue #26): sidebearings that Schibsted makes up for in its kerning.

The bowls of b, p, þ (right) and d, q (left) sit 10-20 units closer to their
neighbours than o does, and the shoulder of h about 30 closer than n's. Schibsted
gives most of it back in the kerning: d stands 16 units further than o from n, m,
k, t, v, y…, h 28 further than n from everything. Pairs it did not kern, or that
odv unkerned (o-d, b-d, a-d, h-u, b-l…), keep the tight sidebearing and sit
visibly closer than their neighbours.

So that space moves into the sidebearings, by the median of what Schibsted kerns
the glyph further than its model (o for the bowls, n for h's shoulder), and comes
off the kerning again: from each pair, as much as it was kerned further than the
model's pair, up to the amount moved. Pairs Schibsted already opened look as
before; the rest open by up to that amount. Every glyph in the same kerning
class moves with the letter (ð β ρ with b, đ with q), and composites (ď ĥ) with
their base.

The 1's flag is light, and the white under it reads as a gap before the stem; its
left sidebearing is reduced by ONE (2048ths of the em), keeping the kerning that
fits the flag against 5, 7 and the like.
"""
import statistics

from kern import Kerning, _set_x, _x
from modify import _shift_anchors, _shift_composites

# glyph: (side, model). The side moves by the median, over the letters in MEDIAN_OF,
# of how much further Schibsted kerns the glyph than the model.
BOWLS = {
    'h': ('right', 'n'),
    'b': ('right', 'o'),        # with p, ð, β, ρ in its kerning class
    'þ': ('right', 'o'),
    'd': ('left', 'o'),
    'q': ('left', 'o'),         # with đ
}
MEDIAN_OF = 'nmhilkrtfvwxyzuj'

ONE = 20                        # 2048ths of the em off the 1's left sidebearing


def _move(tt, name, dx, dadv, moved):
    """Shift a glyph's outline by dx and its advance by dadv; composites follow."""
    if name in moved:
        return
    glyf, hmtx = tt['glyf'], tt['hmtx']
    g = glyf[name]
    if g.isComposite():
        if any(c.glyphName in moved for c in g.components):
            return                                  # followed its base already
        for c in g.components:
            c.x += round(dx)
    elif g.numberOfContours > 0:
        g.coordinates.translate((round(dx), 0))
    g.recalcBounds(glyf)
    hmtx[name] = (hmtx[name][0] + round(dadv), getattr(g, 'xMin', 0))
    _shift_composites(tt, name, round(dx), round(dadv))
    _shift_anchors(tt, name, round(dx))
    moved.add(name)


def _offset(k, ch, side, model):
    """Median of how much further Schibsted kerns `ch` than `model` on `side`."""
    if side == 'right':
        d = [k.get(ch, x) - k.get(model, x) for x in MEDIAN_OF]
    else:
        d = [k.get(x, ch) - k.get(x, model) for x in MEDIAN_OF]
    return round(statistics.median(d))


def _members(k, g, side):
    """The glyphs kerned in the same class as g on that side (g alone if none)."""
    found = {g}
    for s in k.classes:
        if side == 'right':
            if g in s.Coverage.glyphs:
                c1 = s.ClassDef1.classDefs
                found |= {x for x in s.Coverage.glyphs if c1.get(x, 0) == c1.get(g, 0)}
        else:
            c2 = s.ClassDef2.classDefs
            if c2.get(g, 0):
                found |= {x for x, c in c2.items() if c == c2[g]}
    return found


def _give_back(k, g, model, side, d):
    """Take off each pair of g (and its class) as much as it was kerned further than
    the same pair with `model`, up to d."""
    def take(v, ref):
        return v - min(d, max(0, v - ref))
    for s in k.classes:
        c1, c2 = s.ClassDef1.classDefs, s.ClassDef2.classDefs
        cov = s.Coverage.glyphs
        if side == 'right':
            if g not in cov or model not in cov:
                continue
            row = s.Class1Record[c1.get(g, 0)].Class2Record
            ref = s.Class1Record[c1.get(model, 0)].Class2Record
            for j in range(s.Class2Count):
                _set_x(row[j], take(_x(row[j].Value1), _x(ref[j].Value1)))
        else:
            j, jm = c2.get(g, 0), c2.get(model, 0)
            if not j:
                continue
            for i in range(s.Class1Count):
                rec = s.Class1Record[i].Class2Record
                _set_x(rec[j], take(_x(rec[j].Value1), _x(rec[jm].Value1)))
    members = _members(k, g, side)
    for s in k.singles:
        for f, ps in zip(s.Coverage.glyphs, s.PairSet):
            for r in ps.PairValueRecord:
                if side == 'right' and f in members:
                    _set_x(r, take(_x(r.Value1), k.get(model, r.SecondGlyph)))
                elif side == 'left' and r.SecondGlyph in members:
                    _set_x(r, take(_x(r.Value1), k.get(f, model)))


def space(tt):
    """Move Schibsted's kerning of the bowls and of h into their sidebearings (BOWLS),
    and tighten the 1 (ONE). Run after kern.kern, so the Greek letters in the same
    classes move too, and before kern.even_rounds. Returns {glyph: units moved}."""
    k = Kerning(tt)
    offsets = {ch: _offset(k, ch, *sm) for ch, sm in BOWLS.items()}
    # d and q are the same bowl, and đ (a d) is in q's class: one amount for both
    offsets['d'] = offsets['q'] = round((offsets['d'] + offsets['q']) / 2)
    moved = set()
    for ch, (side, model) in BOWLS.items():
        d = offsets[ch]
        if d <= 0:
            continue
        g, m = k.glyph(ch), k.glyph(model)
        _give_back(k, g, m, side, d)
        for name in sorted(_members(k, g, side), key=lambda n: tt['glyf'][n].isComposite()):
            _move(tt, name, d if side == 'left' else 0, d, moved)
    one = round(ONE * tt['head'].unitsPerEm / 2048)
    _move(tt, 'one', -one, -one, moved)
    # pairs kerned closer, to fit the flag against 5, 7…: the flag stays where it was
    for s in k.classes:
        j = s.ClassDef2.classDefs.get('one', 0)
        if j:
            for i in range(s.Class1Count):
                rec = s.Class1Record[i].Class2Record[j]
                if _x(rec.Value1) < 0:
                    _set_x(rec, min(0, _x(rec.Value1) + one))
    for _, r in k.singles_of(set(tt.getGlyphOrder()), {'one'}):
        if _x(r.Value1) < 0:
            _set_x(r, min(0, _x(r.Value1) + one))
    offsets['one'] = -one
    return offsets
