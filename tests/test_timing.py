"""Unit tests for kappicon.timing (PERF-01 helper; no display)."""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[1]
_PY = str(_REPO / "python")
if _PY not in sys.path:
    sys.path.insert(0, _PY)


class TestTiming(unittest.TestCase):
    def test_timing_enabled_false_when_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KAPPICON_TIMING", None)
            os.environ.pop("KAPPICON_DEBUG", None)
            from importlib import reload
            import kappicon.timing as timing

            reload(timing)
            self.assertFalse(timing.timing_enabled())

    def test_timing_enabled_false_for_zero(self) -> None:
        with patch.dict(os.environ, {"KAPPICON_TIMING": "0", "KAPPICON_DEBUG": ""}, clear=False):
            from importlib import reload
            import kappicon.timing as timing

            reload(timing)
            self.assertFalse(timing.timing_enabled())

    def test_timing_enabled_true_for_one(self) -> None:
        with patch.dict(os.environ, {"KAPPICON_TIMING": "1"}, clear=False):
            from importlib import reload
            import kappicon.timing as timing

            reload(timing)
            self.assertTrue(timing.timing_enabled())

    def test_timing_enabled_true_for_true_string(self) -> None:
        with patch.dict(os.environ, {"KAPPICON_TIMING": "true"}, clear=False):
            from importlib import reload
            import kappicon.timing as timing

            reload(timing)
            self.assertTrue(timing.timing_enabled())

    def test_span_logs_when_enabled(self) -> None:
        with patch.dict(os.environ, {"KAPPICON_TIMING": "1"}, clear=False):
            from importlib import reload
            import kappicon.timing as timing

            reload(timing)
            buf = io.StringIO()
            with redirect_stderr(buf):
                with timing.span("test.span"):
                    pass
            out = buf.getvalue()
            self.assertIn("kappicon timing", out)
            self.assertIn("test.span", out)
            self.assertIn("ms", out)

    def test_span_silent_when_disabled(self) -> None:
        with patch.dict(os.environ, {"KAPPICON_TIMING": "0"}, clear=False):
            from importlib import reload
            import kappicon.timing as timing

            reload(timing)
            buf = io.StringIO()
            with redirect_stderr(buf):
                with timing.span("quiet.span"):
                    pass
            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
