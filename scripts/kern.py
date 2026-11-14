"""Kerning for the Greek letters: each one borrows the kerning of a Latin letter
with the same side, e.g. Τ that of T, Λ that of A on both sides, Γ the left of E
and the right of T.

Schibsted Grotesk kerns with one pair-adjustment lookup: a subtable of single
pairs (exceptions) and a subtable of class pairs. A Greek letter is put into the
same left/right classes as its Latin model, and every exception that involves the
model is copied for it, so Greek pairs, and mixed Greek and Latin pairs, kern
exactly like the Latin pairs they look like.

It also takes out Schibsted's opening of round lowercase pairs (even_rounds): Schibsted
kerns o, b, p apart from a following o, d, c, e, q by 40-70 units, so `pod` and
`boo` sit looser than `no` and much looser than `oz`, which it kerns together.
Two rounds need a little less space between them than a round and a stem, since
they curve away from each other; Schibsted's sidebearings alone already give that. The kerning that pulls z towards o, e, c and s is halved
with it, so o-z does not end up much tighter than p-o.
"""
import copy

from fontTools.ttLib.tables import otTables

# Greek letter: (left side from, right side from). The left side is what meets the
# letter before it (the second glyph of a pair), the right side what meets the next
# one. None leaves that side unkerned: no Latin letter has a side close enough.
SIDES = {
    # capitals with a Latin twin
    'Α': ('A', 'A'), 'Β': ('B', 'B'), 'Ε': ('E', 'E'), 'Ζ': ('Z', 'Z'), 'Η': ('H', 'H'),
    'Ι': ('I', 'I'), 'Κ': ('K', 'K'), 'Μ': ('M', 'M'), 'Ν': ('N', 'N'), 'Ο': ('O', 'O'),
    'Ρ': ('P', 'P'), 'Τ': ('T', 'T'), 'Υ': ('Y', 'Y'), 'Χ': ('X', 'X'),
    # drawn capitals
    'Γ': ('E', 'T'),            # E's stem on the left, open under the arm like T
    'Θ': ('O', 'O'), 'Φ': ('O', 'O'),
    'Λ': ('A', 'A'),            # V turned over
    'Ξ': ('E', 'E'), 'Ψ': ('U', 'U'),
    # capitals Schibsted has, kerned only against punctuation
    'Δ': ('A', 'A'), 'Π': ('H', 'H'), 'Σ': ('E', 'E'), 'Ω': ('O', 'O'),
    # lowercase
    'α': ('o', 'a'), 'β': ('b', 'b'),
    'γ': ('v', 'v'),
    'δ': ('b', 'o'),            # left: the rising stroke is ascender-high, like b's stem
    'ε': ('o', 'c'), 'ϵ': ('o', 'c'),
    'ζ': ('b', None), 'ξ': ('b', None),     # ξ: ζ's top and tail
    'η': ('n', 'n'),
    'θ': ('O', 'O'),            # an ascender-high O
    'ι': ('ı', 'ı'),
    'κ': ('n', 'k'),            # k below the x-height: a plain stem on the left
    'λ': ('b', 'A'),
    'μ': ('u', 'u'),
    'ν': ('u', 'v'),
    'ο': ('o', 'o'),
    'π': ('t', 't'), 'τ': ('t', 't'),
    'ρ': ('o', 'p'),
    'σ': ('o', 't'),            # the bar on the right ends like t's
    'ς': ('o', 'c'),            # the top of c
    'υ': ('u', 'u'), 'ψ': ('u', 'u'), 'ω': ('u', 'u'),
    'φ': ('o', 'o'), 'ϕ': ('o', 'o'),
    'χ': ('x', 'x'),
}


# even_rounds: first glyphs whose right side is round, second glyphs whose left side
# is; their class pairs (and exceptions) are scaled by ROUND_KERN where positive.
ROUND_RIGHT = 'op'          # with b, þ, ð, ρ, ö … in the same classes
ROUND_LEFT = 'odeq'         # with c, ο, ε, σ, ö … in the same classes
ROUND_KERN = 0.0
# and z against rounds: Schibsted kerns them together by 15-50 units, which with the
# round pairs closed up left o-z much tighter than p-o. Half of it keeps `poz` even
# without letting `ezzel` fall apart.
Z_AFTER = 'opce'            # these followed by z
Z_BEFORE = 'odeqs'          # z followed by these
Z_KERN = 0.5


def _subtables(lookup):
    if lookup.LookupType == 9:
        return [s.ExtSubTable for s in lookup.SubTable]
    return list(lookup.SubTable)


def _kern_lookups(tt):
    g = tt['GPOS'].table
    idx = {i for fr in g.FeatureList.FeatureRecord if fr.FeatureTag == 'kern'
           for i in fr.Feature.LookupListIndex}
    return [g.LookupList.Lookup[i] for i in sorted(idx)]


def _sort_coverage(tt, sub, parallel=None):
    """Keep a coverage sorted by glyph ID, carrying an array indexed by it along."""
    gid = tt.getGlyphID
    glyphs = sub.Coverage.glyphs
    order = sorted(range(len(glyphs)), key=lambda i: gid(glyphs[i]))
    sub.Coverage.glyphs = [glyphs[i] for i in order]
    if parallel:
        setattr(sub, parallel, [getattr(sub, parallel)[i] for i in order])


def _pairs(tt, sub, left, right, letters, own):
    """Single pairs: copy every pair whose first glyph is a right-side model, or whose
    second glyph is a left-side model, for each combination of the glyph and its copies.
    A pair the font already has is left as it is, and a glyph the font already kerns
    (`own`) gets only pairs with letters, so its own pairs with punctuation still apply."""
    pairs = {(f, r.SecondGlyph): r
             for f, ps in zip(sub.Coverage.glyphs, sub.PairSet) for r in ps.PairValueRecord}
    added = {}
    for (f, s), r in pairs.items():
        for f2 in [f] + right.get(f, []):
            for s2 in [s] + left.get(s, []):
                if (f2, s2) in pairs or (f2, s2) in added:
                    continue
                if (f2 in own or s2 in own) and not (f2 in letters and s2 in letters):
                    continue
                c = copy.deepcopy(r)
                c.SecondGlyph = s2
                added[(f2, s2)] = c
    sets = dict(zip(sub.Coverage.glyphs, sub.PairSet))
    for (f, _), r in added.items():
        if f not in sets:
            sets[f] = otTables.PairSet()
            sets[f].PairValueRecord = []
        sets[f].PairValueRecord.append(r)
    gid = tt.getGlyphID
    for ps in sets.values():
        ps.PairValueRecord.sort(key=lambda r: gid(r.SecondGlyph))
        ps.PairValueCount = len(ps.PairValueRecord)
    sub.Coverage.glyphs = list(sets)
    sub.PairSet = list(sets.values())
    sub.PairSetCount = len(sub.PairSet)
    _sort_coverage(tt, sub, 'PairSet')


def _classes(tt, sub, left, right, letters):
    """Class pairs: put each copy into its model's classes. A glyph that already has a
    left class of its own (Δ Π Σ Ω α β μ π, kerned against quotes, figures and dashes)
    keeps it, and only the pairs with letters, all zero in Schibsted, are filled in
    from the model."""
    cov = set(sub.Coverage.glyphs)
    c1, c2 = sub.ClassDef1.classDefs, sub.ClassDef2.classDefs
    for model, copies in right.items():
        if model not in cov:
            continue
        for g in copies:
            if g not in cov:
                sub.Coverage.glyphs.append(g)
                cov.add(g)
            if c1.get(model):
                c1[g] = c1[model]
            else:
                c1.pop(g, None)
    rows = {c1.get(g, 0) for g in cov & letters}
    for model, copies in left.items():
        for g in copies:
            own = c2.get(g)
            if not own:
                if c2.get(model):
                    c2[g] = c2[model]
                else:
                    c2.pop(g, None)
                continue
            if sum(1 for c in c2.values() if c == own) > 1:
                continue                                  # shared with other glyphs: leave it
            m = c2.get(model, 0)
            for i in rows:
                rec = sub.Class1Record[i].Class2Record
                if getattr(rec[own].Value1, 'XAdvance', 0) == 0:
                    v = copy.deepcopy(rec[own].Value1)
                    v.XAdvance = getattr(rec[m].Value1, 'XAdvance', 0)
                    rec[own].Value1 = v
    _sort_coverage(tt, sub)


def kern(tt, accented=None):
    """Give the Greek letters of `tt` the kerning of their Latin models (SIDES).
    `accented` maps accented letters (scripts/accents.py) to the letter whose sides
    they take, or to (left, right) letters, None leaving a side unkerned.
    Returns the number of Greek letters kerned."""
    cmap = tt.getBestCmap()
    left, right = {}, {}      # model glyph -> Greek glyphs taking that side
    done = 0
    sides = dict(SIDES)
    for ch, base in (accented or {}).items():
        l, r = base if isinstance(base, tuple) else (base, base)
        sides[ch] = (l and SIDES[l][0], r and SIDES[r][1])
    for ch, (l, r) in sides.items():
        g = cmap.get(ord(ch))
        if g is None:
            continue
        for side, model in ((left, l), (right, r)):
            if model is not None:
                side.setdefault(cmap[ord(model)], []).append(g)
        done += 1
    letters = {g for u, g in cmap.items() if chr(u).isalpha()}
    subs = [sub for lookup in _kern_lookups(tt) if lookup.LookupType in (2, 9)
            for sub in _subtables(lookup) if getattr(sub, 'LookupType', 2) == 2]
    greek = {g for gs in list(left.values()) + list(right.values()) for g in gs}
    own = {g for sub in subs for g in greek
           if g in sub.Coverage.glyphs or (sub.Format == 2 and sub.ClassDef2.classDefs.get(g))}
    for sub in subs:
        if sub.Format == 1:
            _pairs(tt, sub, left, right, letters, own)
        else:
            _classes(tt, sub, left, right, letters)
    return done


def _scale_pairs(tt, firsts, seconds, scale, sign):
    """Scale the kerning of the class pairs of `firsts` followed by `seconds` (letters),
    and of the exceptions among their class members, where its sign is `sign`."""
    cmap = tt.getBestCmap()
    firsts = [cmap[ord(c)] for c in firsts]
    seconds = [cmap[ord(c)] for c in seconds]
    subs = [sub for lookup in _kern_lookups(tt) if lookup.LookupType in (2, 9)
            for sub in _subtables(lookup) if getattr(sub, 'LookupType', 2) == 2]
    g1, g2, values = set(firsts), set(seconds), []
    for sub in subs:
        if sub.Format == 2:
            c1, c2 = sub.ClassDef1.classDefs, sub.ClassDef2.classDefs
            rows = {c1.get(g, 0) for g in firsts if g in sub.Coverage.glyphs}
            cols = {c2.get(g, 0) for g in seconds}
            assert 0 not in rows and 0 not in cols, 'a letter is in a catch-all class'
            g1 |= {g for g in sub.Coverage.glyphs if c1.get(g, 0) in rows}
            g2 |= {g for g, c in c2.items() if c in cols}
            values += [sub.Class1Record[i].Class2Record[j].Value1 for i in rows for j in cols]
    for sub in subs:
        if sub.Format == 1:
            values += [r.Value1 for f, ps in zip(sub.Coverage.glyphs, sub.PairSet)
                       for r in ps.PairValueRecord if f in g1 and r.SecondGlyph in g2]
    changed = 0
    for v in values:
        if v is not None and getattr(v, 'XAdvance', 0) * sign > 0:
            v.XAdvance = round(v.XAdvance * scale)
            changed += 1
    return changed


def even_rounds(tt):
    """Round lowercase pairs no longer kerned apart (ROUND_KERN), and z no longer
    pulled as close to rounds (Z_KERN). Returns the number of values changed."""
    return (_scale_pairs(tt, ROUND_RIGHT, ROUND_LEFT, ROUND_KERN, +1)
            + _scale_pairs(tt, Z_AFTER, 'z', Z_KERN, -1)
            + _scale_pairs(tt, 'z', Z_BEFORE, Z_KERN, -1))
