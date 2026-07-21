"""Application entrypoint."""
from __future__ import annotations

import sys


def main(argv=None) -> int:
    """Start the kAppIcon GUI. Returns process exit code."""
    from kappicon.timing import span

    argv = list(sys.argv if argv is None else argv)
    with span("python.main"):
        # Import UI only when launching (requires PyQt6)
        try:
            from PyQt6.QtWidgets import QApplication  # noqa: F401
        except ImportError:
            print(
                "PyQt6 is required for the GUI. Install python3-pyqt6 / python-pyqt6.",
                file=sys.stderr,
            )
            return 1

        with span("python.import_ui"):
            from kappicon.ui import run_app

        with span("python.run_app"):
            return run_app(argv)


if __name__ == "__main__":
    raise SystemExit(main())
