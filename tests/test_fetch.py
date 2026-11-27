"""Offline tests for the downloads in scripts/odvmath.py (#24): retries of the CTAN
redirector, fallback to fixed mirrors, checksum checked per attempt, source in the log.

    python3 -m unittest discover -s tests
"""
import hashlib
import io
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import odvmath  # noqa: E402

GOOD = b'pinned font bytes'


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def server(plan):
    """urlopen stand-in: plan maps a URL to a list of outcomes, one per request
    (bytes = content, Exception = raised), so the redirector can fail, then work."""
    calls = []

    def urlopen(url, timeout=None):
        calls.append(url)
        outcome = plan[url].pop(0) if isinstance(plan[url], list) else plan[url]
        if isinstance(outcome, Exception):
            raise outcome
        return Response(outcome, url.replace('mirrors.ctan.org', 'some-mirror.example'))
    return urlopen, calls


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = mock.patch.object(odvmath, 'ROOT', Path(self.tmp.name))
        self.root.start()
        self.pin = mock.patch.object(odvmath, 'NEWCM_SHA256', hashlib.sha256(GOOD).hexdigest())
        self.pin.start()

    def tearDown(self):
        self.pin.stop()
        self.root.stop()
        self.tmp.cleanup()

    def run_source(self, plan):
        urlopen, calls = server(plan)
        out = io.StringIO()
        with mock.patch.object(odvmath.urllib.request, 'urlopen', urlopen), redirect_stdout(out):
            path = odvmath.source()
        return path, calls, out.getvalue()

    def urls(self):
        redirector = odvmath.CTAN_REDIRECTOR + odvmath.NEWCM_PATH
        mirrors = [m + odvmath.NEWCM_PATH for m in odvmath.CTAN_MIRRORS]
        return redirector, mirrors

    def test_redirector_retried_after_tls_error(self):
        redirector, _ = self.urls()
        tls = urllib.error.URLError('[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed')
        path, calls, log = self.run_source({redirector: [tls, GOOD]})
        self.assertEqual(path.read_bytes(), GOOD)
        self.assertEqual(calls, [redirector, redirector])
        self.assertIn('downloaded NewCMMath-Book.otf from https://some-mirror.example/', log)

    def test_fixed_mirror_after_redirector_fails(self):
        redirector, mirrors = self.urls()
        down = urllib.error.URLError('connection refused')
        plan = {redirector: [down] * odvmath.CTAN_REDIRECTOR_TRIES, mirrors[0]: GOOD}
        path, calls, log = self.run_source(plan)
        self.assertEqual(path.read_bytes(), GOOD)
        self.assertEqual(calls[-1], mirrors[0])
        self.assertIn(f'from {mirrors[0]}', log)

    def test_checksum_mismatch_moves_on(self):
        redirector, mirrors = self.urls()
        stale = b'an older copy on a lagging mirror'
        plan = {redirector: [stale] * odvmath.CTAN_REDIRECTOR_TRIES, mirrors[0]: stale, mirrors[1]: GOOD}
        path, calls, log = self.run_source(plan)
        self.assertEqual(path.read_bytes(), GOOD)
        self.assertEqual(len(calls), odvmath.CTAN_REDIRECTOR_TRIES + 2)
        self.assertIn('sent different content', log)

    def test_all_sources_fail_with_each_reason_and_the_hint(self):
        redirector, mirrors = self.urls()
        new = b'a newer New Computer Modern'
        plan = {redirector: [new] * odvmath.CTAN_REDIRECTOR_TRIES, mirrors[0]: new, mirrors[1]: urllib.error.URLError('timeout')}
        with self.assertRaises(SystemExit) as raised:
            self.run_source(plan)
        message = str(raised.exception)
        self.assertIn(hashlib.sha256(new).hexdigest(), message)
        self.assertIn('timeout', message)
        self.assertIn('update NEWCM_VERSION and NEWCM_SHA256', message)
        self.assertFalse((Path(self.tmp.name) / 'upstream' / 'NewCMMath-Book.otf').exists())

    def test_cached_file_is_not_downloaded_again(self):
        cached = Path(self.tmp.name) / 'upstream' / 'NewCMMath-Book.otf'
        cached.parent.mkdir()
        cached.write_bytes(GOOD)
        path, calls, _ = self.run_source({})
        self.assertEqual(calls, [])
        self.assertEqual(path, cached)

    def test_licence_falls_back_to_ctan_without_checksum(self):
        gfl = [odvmath.GFL_URL] + odvmath.ctan(odvmath.GFL_PATH)
        plan = {gfl[0]: urllib.error.URLError('tug.org down'), gfl[1]: b'GUST Font License'}
        urlopen, calls = server(plan)
        with mock.patch.object(odvmath.urllib.request, 'urlopen', urlopen), redirect_stdout(io.StringIO()):
            path = odvmath.fetch(gfl, 'GUST-FONT-LICENSE.txt')
        self.assertEqual(path.read_bytes(), b'GUST Font License')
        self.assertEqual(calls, gfl[:2])


if __name__ == '__main__':
    unittest.main()
