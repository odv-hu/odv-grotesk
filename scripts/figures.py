"""Figures (issue #36): equal-width figures by default, narrowed.

Schibsted's default figures are proportional; its tabular figures (zero.tf ...
nine.tf, behind `tnum`) are drawn wider and stand in 1300 units in every weight.
Software that applies no OpenType features (CAD and drafting programs, many table
tools) only ever shows the default figures, so columns of numbers do not line up
there, and a 1 leaves a gap in a dimension string.

odv makes the tabular figures the default and narrows them, so they line up in
columns without spreading out running text:

- The figures map to the .tf glyphs. `pnum` (Schibsted's own lookup, .tf to
  the proportional figures) gives the proportional figures back; `tnum` has
  nothing left to do. Every other feature that takes figures (fractions,
  numerators, denominators, superiors, ordinals, `zero`) is given the .tf
  figures too, with the same results.
- Each .tf figure is the proportional figure's own drawing (one drawing per
  figure, whichever spacing is on), in an advance of WIDTH, the change split
  equally between its sides so the drawing keeps its own balance. The 1 keeps
  Schibsted's tabular 1, whose foot fills the wider slot.
- Regular and Medium (and their italics) share one width, so a total set in
  Medium lines up under rows in Regular. Bold's width gives its widest figure,
  the 4, the room Medium's 4 has in 1200.
- The .tf figures are not kerned (that would break the columns), except
  against the en dash, which keeps from them the distance one 0 keeps from the
  next, as kern.dashes does for the proportional figures.
"""
import copy

from fontTools.ttLib.tables import otTables

from kern import DASHES, Kerning, _sides, _sort_coverage, _subtables

FIGURES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
DRAWN_TABULAR = {'one'}                 # these keep Schibsted's tabular drawing
WIDTH = {'Regular': 1200, 'Medium': 1200, 'Bold': 1260}   # 2048ths of the em, by weight
SLASHED = ('zero.zero', 'zero.tf.zero')  # the `zero` feature's 0 (in Schibsted the plain 0) and its tabular twin


def _weight(style):
    return style.replace('Italic', '') or 'Regular'


def _respace(tt, name, src, width):
    """Glyph `name` becomes the drawing of `src` in an advance of `width`, the change
    split equally between the sides. Returns the shift applied to the drawing."""
    glyf, hmtx = tt['glyf'], tt['hmtx']
    g = copy.deepcopy(glyf[src])
    adv = hmtx[src][0]
    dx = round((width - adv) / 2)
    if g.isComposite():
        for c in g.components:
            c.x += dx
    elif g.numberOfContours:
        g.coordinates.translate((dx, 0))
    glyf[name] = g
    g.recalcBounds(glyf)
    hmtx[name] = (width, getattr(g, 'xMin', 0))
    return dx


def _slashed(tt, width):
    """The tabular twin of the `zero` feature's glyph: Schibsted's zero.zero built on zero.tf."""
    src, name = SLASHED
    glyf, hmtx = tt['glyf'], tt['hmtx']
    if src not in glyf.keys():
        return None
    g = copy.deepcopy(glyf[src])
    if g.isComposite():
        for c in g.components:           # zero.tf already stands where it should
            if c.glyphName in FIGURES:
                c.glyphName += '.tf'
    else:
        g.coordinates.translate((round((width - hmtx[src][0]) / 2), 0))
    glyf[name] = g          # appends the name to the glyph order
    tt.setGlyphOrder(glyf.glyphOrder)
    g.recalcBounds(glyf)
    hmtx[name] = (width, getattr(g, 'xMin', 0))
    if 'GDEF' in tt and tt['GDEF'].table.GlyphClassDef:
        tt['GDEF'].table.GlyphClassDef.classDefs[name] = 1
    return name


def _feature_lookups(gsub, tags):
    return {i for fr in gsub.FeatureList.FeatureRecord if fr.FeatureTag in tags
            for i in fr.Feature.LookupListIndex}


def _twin(name):
    return name + '.tf' if name in FIGURES else None


def _extend_gsub(tt, slashed):
    """Every lookup that takes a proportional figure takes its .tf twin as well, with
    the same result; pnum and tnum, which switch between the two, are left as they are
    (but learn the `zero` glyph's twin)."""
    gsub = tt['GSUB'].table
    gid = tt.getGlyphID
    spacing = _feature_lookups(gsub, {'pnum', 'tnum'})
    slashed_src = SLASHED[0]
    extended = 0
    for i, lookup in enumerate(gsub.LookupList.Lookup):
        for st in _subtables(lookup):
            if i in spacing:
                if slashed and hasattr(st, 'mapping'):
                    m = st.mapping
                    if 'zero.tf' in m:                       # pnum: .tf -> proportional
                        m[slashed] = slashed_src
                    elif 'zero' in m:                        # tnum: proportional -> .tf
                        m[slashed_src] = slashed
                continue
            if hasattr(st, 'mapping'):                       # single
                m = st.mapping
                for f in FIGURES:
                    if f in m and _twin(f) not in m:
                        out = m[f]
                        if slashed and f == 'zero' and out == slashed_src:
                            out = slashed
                        m[_twin(f)] = out
                        extended += 1
            elif hasattr(st, 'alternates'):                  # alternate
                for f in FIGURES:
                    if f in st.alternates and _twin(f) not in st.alternates:
                        st.alternates[_twin(f)] = list(st.alternates[f])
                        extended += 1
            elif hasattr(st, 'ligatures'):                   # ligature: first glyph only
                for f in FIGURES:
                    if f in st.ligatures and _twin(f) not in st.ligatures:
                        st.ligatures[_twin(f)] = copy.deepcopy(st.ligatures[f])
                        extended += 1
            elif getattr(st, 'Format', None) == 3:           # coverage-based (chain) context
                covs = (getattr(st, 'BacktrackCoverage', []) + getattr(st, 'InputCoverage', [])
                        + getattr(st, 'LookAheadCoverage', []) + getattr(st, 'Coverage', []))
                for cov in covs:
                    add = [_twin(g) for g in cov.glyphs if _twin(g) and _twin(g) not in cov.glyphs]
                    if add:
                        cov.glyphs = sorted(cov.glyphs + add, key=gid)
                        extended += len(add)
            else:
                assert not any(f in _glyphs_of(st) for f in FIGURES), \
                    f'lookup {i} takes figures in a form figures.py does not extend'
    return extended


def _glyphs_of(st):
    names = set()
    for attr in ('Coverage', 'InputCoverage', 'BacktrackCoverage', 'LookAheadCoverage'):
        v = getattr(st, attr, None)
        for cov in (v if isinstance(v, list) else [v] if v else []):
            names |= set(cov.glyphs)
    for attr in ('ClassDef', 'InputClassDef', 'BacktrackClassDef', 'LookAheadClassDef'):
        cd = getattr(st, attr, None)
        if cd:
            names |= set(cd.classDefs)
    return names


def _dashes(tt):
    """The en dash keeps from a .tf figure the distance one zero.tf keeps from the next,
    as single pairs ahead of the class kerning (the .tf figures have no other kerning)."""
    k = Kerning(tt)
    sub = k.singles[0]
    tabular = [f + '.tf' for f in FIGURES]
    sets = dict(zip(sub.Coverage.glyphs, sub.PairSet))
    done = {}

    def pair(first, second, value):
        if first not in sets:
            sets[first] = otTables.PairSet()
            sets[first].PairValueRecord = []
        recs = sets[first].PairValueRecord
        assert not any(r.SecondGlyph == second for r in recs), (first, second)
        r = otTables.PairValueRecord()
        r.SecondGlyph = second
        r.Value1 = otTables.ValueRecord()
        r.Value1.XAdvance = value
        recs.append(r)

    for d in DASHES:
        if d not in tt['glyf'].keys():
            continue
        g = tt['glyf'][d]
        g.recalcBounds(tt['glyf'])
        y = (g.yMin + g.yMax) / 2
        l0, r0 = _sides(tt, 'zero.tf', y)
        ld, rd = _sides(tt, d, y)
        after, before = round(l0 - ld), round(r0 - rd)
        for f in tabular:
            pair(f, d, after)
            pair(d, f, before)
        done[d] = (after, before)
    gid = tt.getGlyphID
    for ps in sets.values():
        ps.PairValueRecord.sort(key=lambda r: gid(r.SecondGlyph))
        ps.PairValueCount = len(ps.PairValueRecord)
    sub.Coverage.glyphs = list(sets)
    sub.PairSet = list(sets.values())
    sub.PairSetCount = len(sub.PairSet)
    _sort_coverage(tt, sub, 'PairSet')
    return done


def figures(tt, style):
    """Equal-width figures by default for one style. Run last, after the outlines are
    final, so the .tf figures get the finished drawings. Returns a summary."""
    width = WIDTH[_weight(style)]
    for f in FIGURES:
        src = f + '.tf' if f in DRAWN_TABULAR else f
        _respace(tt, f + '.tf', src, width)
    slashed = _slashed(tt, width)
    for table in tt['cmap'].tables:
        if table.isUnicode():
            for i, f in enumerate(FIGURES):
                if 0x30 + i in table.cmap:
                    table.cmap[0x30 + i] = f + '.tf'
    extended = _extend_gsub(tt, slashed)
    dashed = _dashes(tt)
    return {'width': width, 'lookups extended': extended, 'dashes': dashed}
