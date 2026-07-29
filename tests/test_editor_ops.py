"""Unit tests for Create-tab image prep (no GUI window)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Match load_engine path setup when PYTHONPATH is unset
_pkg = Path(__file__).resolve().parents[1] / "python"
if str(_pkg) not in sys.path:
    sys.path.insert(0, str(_pkg))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter

from kappicon import editor_ops as ops


def _solid(w, h, color, x0=0, y0=0, cw=None, ch=None):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    cw = cw if cw is not None else w
    ch = ch if ch is not None else h
    p = QPainter(img)
    p.fillRect(x0, y0, cw, ch, color)
    p.end()
    return img


class TestEditorOps(unittest.TestCase):
    def test_content_bbox_and_center(self):
        img = _solid(64, 64, QColor(255, 0, 0, 255), x0=40, y0=40, cw=10, ch=10)
        box = ops.content_bbox(img)
        self.assertIsNotNone(box)
        self.assertEqual(box.x(), 40)
        self.assertEqual(box.y(), 40)
        centered = ops.center_content(img)
        box2 = ops.content_bbox(centered)
        self.assertIsNotNone(box2)
        self.assertTrue(20 <= box2.x() <= 30)
        self.assertTrue(20 <= box2.y() <= 30)

    def test_flip_horizontal_swaps_sides(self):
        img = _solid(8, 8, QColor(0, 0, 0, 0))
        img.setPixelColor(0, 0, QColor(255, 0, 0, 255))
        out = ops.flip_horizontal(img)
        self.assertEqual(out.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(out.pixelColor(7, 0).red(), 255)

    def test_rotate_90_size_preserved(self):
        img = _solid(32, 32, QColor(0, 128, 255, 255), x0=0, y0=0, cw=8, ch=4)
        out = ops.rotate_90(img, clockwise=True)
        self.assertEqual(out.width(), 32)
        self.assertEqual(out.height(), 32)
        self.assertIsNotNone(ops.content_bbox(out))

    def test_apply_padding_shrinks_content(self):
        img = _solid(100, 100, QColor(10, 20, 30, 255))
        padded = ops.apply_padding(img, 20)
        box = ops.content_bbox(padded)
        self.assertIsNotNone(box)
        self.assertLessEqual(box.width(), 65)
        self.assertLessEqual(box.height(), 65)
        self.assertGreaterEqual(box.width(), 50)

    def test_monochrome_preserves_alpha_grayscale(self):
        img = _solid(4, 4, QColor(200, 50, 50, 180))
        out = ops.monochrome(img, color=None)
        c = out.pixelColor(1, 1)
        self.assertEqual(c.alpha(), 180)
        self.assertEqual(c.red(), c.green())
        self.assertEqual(c.green(), c.blue())

    def test_tint_blends_toward_color(self):
        img = _solid(4, 4, QColor(0, 0, 0, 255))
        out = ops.tint(img, QColor(255, 0, 0), amount=1.0)
        c = out.pixelColor(0, 0)
        self.assertEqual(c.red(), 255)
        self.assertEqual(c.green(), 0)
        self.assertEqual(c.blue(), 0)
        self.assertEqual(c.alpha(), 255)

    def test_drop_shadow_keeps_size_and_content(self):
        img = _solid(64, 64, QColor(255, 255, 255, 255), x0=16, y0=16, cw=20, ch=20)
        out = ops.drop_shadow(img, offset_x=3, offset_y=3, blur=2, opacity=0.5)
        self.assertEqual(out.width(), 64)
        self.assertEqual(out.height(), 64)
        self.assertGreaterEqual(out.pixelColor(20, 20).red(), 250)

    def test_outline_expands_alpha(self):
        img = _solid(32, 32, QColor(255, 0, 0, 255), x0=10, y0=10, cw=4, ch=4)
        out = ops.outline(img, width=2, color=QColor(0, 0, 0))
        edge = out.pixelColor(9, 11)
        self.assertGreater(edge.alpha(), 0)

    def test_trim_to_content_not_blank(self):
        img = _solid(64, 64, QColor(0, 255, 0, 255), x0=20, y0=20, cw=8, ch=8)
        out = ops.trim_to_content(img, square=True)
        self.assertEqual(out.width(), 64)
        box = ops.content_bbox(out)
        self.assertIsNotNone(box)
        self.assertGreater(box.width(), 8)

    def test_low_res_detection_and_integer_scale(self):
        tiny = _solid(48, 48, QColor(255, 0, 0, 255))
        big = _solid(512, 512, QColor(0, 255, 0, 255))
        self.assertTrue(ops.is_low_resolution(tiny))
        self.assertTrue(ops.is_modest_resolution(tiny))
        self.assertFalse(ops.is_low_resolution(big))
        self.assertEqual(ops.recommended_scale_mode(tiny), "crisp")
        self.assertEqual(ops.recommended_scale_mode(big), "smooth")
        self.assertEqual(ops.max_integer_scale(48, 48, 512), 10)
        self.assertEqual(ops.max_integer_scale(16, 16, 512), 32)
        hint = ops.import_quality_hint(tiny, 512)
        self.assertIn("48×48", hint)
        self.assertEqual(ops.import_quality_hint(big, 512), "")

    def test_upscale_nearest_keeps_blocky_edges(self):
        img = _solid(2, 2, QColor(0, 0, 0, 0))
        img.setPixelColor(0, 0, QColor(255, 0, 0, 255))
        out = ops.upscale_nearest(img, 4, 4)
        self.assertEqual(out.width(), 4)
        # Top-left 2×2 block should stay pure red
        self.assertEqual(out.pixelColor(0, 0).red(), 255)
        self.assertEqual(out.pixelColor(1, 1).red(), 255)
        self.assertEqual(out.pixelColor(2, 0).alpha(), 0)


if __name__ == "__main__":
    unittest.main()
