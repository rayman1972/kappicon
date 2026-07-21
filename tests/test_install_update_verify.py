"""SECU-02: install.sh non-git update uses checksum verification (offline tests)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO / "install.sh"


class TestInstallUpdateVerify(unittest.TestCase):
    def test_install_sh_source_contracts(self) -> None:
        text = INSTALL_SH.read_text(encoding="utf-8", errors="replace")
        self.assertIn("SHA256SUMS", text)
        self.assertIn("sha256sum", text)
        self.assertIn("archive/refs/tags", text)
        self.assertIn("mktemp", text)
        # Must not curl product binaries from raw main
        self.assertNotIn(
            "raw.githubusercontent.com/rayman1972/kappicon/main/cli/kappicon-cli",
            text,
        )
        self.assertNotIn(
            "raw.githubusercontent.com/rayman1972/kappicon/main/gui/kappicon",
            text,
        )
        # Non-git update must fail closed without SUMS (message present)
        self.assertTrue(
            "SHA256SUMS release asset" in text
            or "cannot safely update" in text.lower(),
            "install.sh should mention fail-closed missing SUMS",
        )

    def test_sha256sum_happy_path(self) -> None:
        self.assertTrue(shutil.which("sha256sum"), "sha256sum required on test host")
        with tempfile.TemporaryDirectory(prefix="kappicon-sum-") as tmp:
            d = Path(tmp)
            payload = b"kappicon-release-payload-vtest\n"
            name = "kappicon-9.9.9.tar.gz"
            (d / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (d / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
            proc = subprocess.run(
                ["bash", "-c", f"cd {d!s} && sha256sum -c SHA256SUMS"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_sha256sum_mismatch_fails(self) -> None:
        self.assertTrue(shutil.which("sha256sum"), "sha256sum required on test host")
        with tempfile.TemporaryDirectory(prefix="kappicon-sum-bad-") as tmp:
            d = Path(tmp)
            name = "kappicon-9.9.9.tar.gz"
            (d / name).write_bytes(b"real-bytes\n")
            (d / "SHA256SUMS").write_text(
                f"{'0' * 64}  {name}\n", encoding="utf-8"
            )
            proc = subprocess.run(
                ["bash", "-c", f"cd {d!s} && sha256sum -c SHA256SUMS"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)

    def test_verify_sha256sums_helper_from_install_sh(self) -> None:
        """Source verify_sha256sums from install.sh and exercise it offline."""
        text = INSTALL_SH.read_text(encoding="utf-8", errors="replace")
        m = re.search(
            r"^verify_sha256sums\(\) \{.*?\n\}",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(m, "verify_sha256sums not found in install.sh")
        func = m.group(0)
        with tempfile.TemporaryDirectory(prefix="kappicon-helper-") as tmp:
            d = Path(tmp)
            name = "kappicon-1.2.3.tar.gz"
            payload = b"abc\n"
            (d / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (d / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
            script = f"""
set -e
{func}
verify_sha256sums {d!s} {name}
"""
            proc = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

            # Mismatch
            (d / "SHA256SUMS").write_text(f"{'a' * 64}  {name}\n", encoding="utf-8")
            proc2 = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc2.returncode, 0)


if __name__ == "__main__":
    unittest.main()
