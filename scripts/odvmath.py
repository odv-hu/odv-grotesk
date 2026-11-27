"""Build odv Math: New Computer Modern Math Book at 112 %, renamed.

    python3 scripts/odvmath.py                     # download the pinned NewCM, build odv Math
    python3 scripts/odvmath.py path/to/Source.otf  # build from a local file (testing)

odv Grotesk's maths is Computer Modern: odv-latex's odv.sty sets New Computer Modern
Math Book at mathscale=1.12, the size at which it sits with the grotesk. Keynote can't
scale a font and the web only roughly (size-adjust), so odv Math is that font made
112 % larger once, here, and every app uses it at its nominal size.

The scaling touches no outline: unitsPerEm (and the CFF FontMatrix with it) is set to
1/1.12 of the original, so outlines, advances, kerning, the MATH table and the
vertical metrics all grow together. The font is renamed, as the GUST Font License
asks of modified versions, and keeps that licence; GUST-FONT-LICENSE.txt and
README-odvMath.txt go with it.

Writes fonts/otf/odvMath-Regular.otf and fonts/webfonts/odvMath-Regular.woff2.
"""
import hashlib
import http.client
import sys
import urllib.error
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SCALE = 1.12                      # = odv.sty's default mathscale
FAMILY, PS_NAME = 'odv Math', 'odvMath-Regular'
NEWCM_VERSION = '8.1.1'           # CTAN keeps only the latest: a new upstream fails the hash
NEWCM_PATH = 'fonts/newcomputermodern/otf/NewCMMath-Book.otf'     # in the CTAN tree
NEWCM_SHA256 = '2ea09ebc9167b1e1a66f31390dc917f2d4004ecfca72d51b28010e4ad6becd95'  # 8.1.1, licence checked: GFL
NEWCM_LICENSE_PATH = 'fonts/newcomputermodern/License.txt'
GFL_URL = 'https://tug.org/fonts/licenses/GUST-FONT-LICENSE.txt'
GFL_PATH = 'fonts/tex-gyre/doc/GUST-FONT-LICENSE.txt'                # a copy on CTAN, as fallback
# mirrors.ctan.org redirects each request to a random mirror, and a broken one can fail
# a release (#24). So: the redirector a few times (each try gets a new mirror), then two
# fixed, well-kept mirrors with the same tree.
CTAN_REDIRECTOR = 'https://mirrors.ctan.org/'
CTAN_REDIRECTOR_TRIES = 3
CTAN_MIRRORS = ['https://ftp.fau.de/ctan/', 'https://ctan.math.utah.edu/ctan/tex-archive/']
TIMEOUT = 60                      # seconds per attempt
SOURCE = ('New Computer Modern Math Book {v} by Antonis Tsolomitis '
          '(https://ctan.org/pkg/newcomputermodern), after Computer Modern by Donald E. Knuth')
CHANGE = 'scaled to 112 % (unitsPerEm {a} -> {b}) and renamed odv Math'


def ctan(path):
    """Download addresses for a file in the CTAN tree, in the order to try them."""
    return [CTAN_REDIRECTOR + path] * CTAN_REDIRECTOR_TRIES + [m + path for m in CTAN_MIRRORS]


def matches_pin(data):
    return NEWCM_SHA256 is not None and hashlib.sha256(data).hexdigest() == NEWCM_SHA256


def check(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if NEWCM_SHA256 is None:
        raise SystemExit(f'{path.name}: sha256 {digest}\n'
                         f'Check the licence of this version (License.txt next to it on CTAN: '
                         f'the maths fonts must be GFL), then set NEWCM_SHA256 in {__file__}.')
    if digest != NEWCM_SHA256:
        raise SystemExit(f'{path.name} changed upstream (sha256 {digest}). CTAN has a new '
                         f'New Computer Modern: check its License.txt, then update '
                         f'NEWCM_VERSION and NEWCM_SHA256.')


def fetch(urls, name, accept=None, hint=''):
    """Download name into upstream/ from the first of urls that works, unless it is there.

    A source is skipped on a network or TLS error, and also when accept(data) is false
    (for the font: its checksum does not match the pin), so the next source is tried.
    The log says which address the file finally came from."""
    path = ROOT / 'upstream' / name
    if path.exists():
        return path
    path.parent.mkdir(exist_ok=True)
    failures = []
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                data, final = response.read(), response.geturl()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
            failures.append(f'{url}: {error}')
            print(f'  {name}: {url} failed ({error}), trying the next source')
            continue
        if accept is not None and not accept(data):
            digest = hashlib.sha256(data).hexdigest()
            failures.append(f'{final}: unexpected content (sha256 {digest})')
            print(f'  {name}: {final} sent different content (sha256 {digest}), trying the next source')
            continue
        path.write_bytes(data)
        print(f'downloaded {name} from {final}')
        return path
    raise SystemExit(f'could not download {name}:\n  ' + '\n  '.join(failures) + (f'\n{hint}' if hint else ''))


def source():
    accept = matches_pin if NEWCM_SHA256 is not None else None
    path = fetch(ctan(NEWCM_PATH), 'NewCMMath-Book.otf', accept,
                 hint='If every mirror sends the same other sha256, CTAN has a new New Computer '
                      'Modern: check its License.txt, then update NEWCM_VERSION and NEWCM_SHA256.')
    check(path)
    return path


README = '''odv Math
========

{note}.

The maths font for odv Grotesk: Computer Modern at the size at which it sits with
the grotesk (odv-latex sets it at mathscale=1.12). Only unitsPerEm changed; the
outlines, metrics and MATH table are New Computer Modern's, unmodified.

Licence: GUST Font License, see GUST-FONT-LICENSE.txt (an instance of the LaTeX
Project Public License 1.3c). The font is renamed, as that licence asks of
modified versions. New Computer Modern's own licence notes are in
NewCM-License.txt. odv Grotesk, in the same release, is under the SIL Open Font
License (OFL.txt).

Files to be renamed in derived works (GFL clause 1): odvMath-*.otf, odvMath-*.woff2.
'''


def licence_files(note):
    """GUST-FONT-LICENSE.txt, New Computer Modern's License.txt and a readme next to
    the font, so they travel with it in the release zip."""
    out = ROOT / 'fonts' / 'otf'
    out.mkdir(parents=True, exist_ok=True)
    # no checksum for the licences: any mirror's copy will do
    gfl = fetch([GFL_URL] + ctan(GFL_PATH), 'GUST-FONT-LICENSE.txt')
    (out / 'GUST-FONT-LICENSE.txt').write_bytes(gfl.read_bytes())
    newcm = fetch(ctan(NEWCM_LICENSE_PATH), 'NewCM-License.txt')
    (out / 'NewCM-License.txt').write_bytes(newcm.read_bytes())
    (out / 'README-odvMath.txt').write_text(README.format(note=note))


def build(src, version, source_note=None):
    tt = TTFont(src)
    old = tt['head'].unitsPerEm
    new = round(old / SCALE)
    tt['head'].unitsPerEm = new
    if 'CFF ' in tt:
        cff = tt['CFF '].cff
        top = cff.topDictIndex[0]
        top.FontMatrix = [1 / new, 0, 0, 1 / new, 0, 0]
        cff.fontNames = [PS_NAME]
        top.FullName, top.FamilyName = FAMILY, FAMILY
        if hasattr(top, 'Weight'):
            top.Weight = 'Regular'
    elif 'glyf' in tt:
        raise SystemExit('odv Math expects a CFF (.otf) source')

    note = (source_note or SOURCE.format(v=NEWCM_VERSION)) + '; ' + CHANGE.format(a=old, b=new)
    name = tt['name']
    copyright_ = name.getDebugName(0) or ''
    for rec in list(name.names):
        if rec.nameID in (16, 17, 18, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    for nid, s in {
        0: f'{copyright_} odv Math: {note}.'.strip(),
        1: FAMILY, 2: 'Regular', 3: f'{version};ODV;{PS_NAME}', 4: FAMILY,
        5: f'Version {version}; {note}', 6: PS_NAME,
        8: 'o d v', 11: 'https://odv.hu',
        13: 'GUST Font License (an instance of the LaTeX Project Public License 1.3c); '
            'see GUST-FONT-LICENSE.txt.',
        14: 'https://tug.org/fonts/licenses/GUST-FONT-LICENSE.txt',
    }.items():
        name.setName(s, nid, 3, 1, 0x409)
        if name.getName(nid, 1, 0, 0):
            name.setName(s, nid, 1, 0, 0)
    tt['OS/2'].achVendID = 'NONE'
    from build import font_revision          # same scheme as odv Grotesk
    tt['head'].fontRevision = font_revision(version)

    otf = ROOT / 'fonts' / 'otf' / f'{PS_NAME}.otf'
    otf.parent.mkdir(parents=True, exist_ok=True)
    tt.save(otf)
    web = ROOT / 'fonts' / 'webfonts' / f'{PS_NAME}.woff2'
    web.parent.mkdir(parents=True, exist_ok=True)
    tt.flavor = 'woff2'
    tt.save(web)
    print(f'{otf.name}: {Path(src).name} at {SCALE:.0%} (unitsPerEm {old} -> {new})')
    return otf


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build import VERSION
    if len(sys.argv) > 1:
        build(sys.argv[1], VERSION, f'{Path(sys.argv[1]).name} (local test build)')
    else:
        src = source()
        build(src, VERSION)
        old = TTFont(src)['head'].unitsPerEm
        licence_files(SOURCE.format(v=NEWCM_VERSION) + '; ' + CHANGE.format(a=old, b=round(old / SCALE)))
