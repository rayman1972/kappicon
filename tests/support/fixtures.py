"""File writers for kAppIcon tests (paths must stay under a sandbox)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from tests.support.xdg_sandbox import XDGSandbox


def write_desktop(
    path: Path | str,
    *,
    name: str,
    icon: str = "utilities-terminal",
    extra_desktop_entry_lines: Optional[Sequence[str]] = None,
    actions: Optional[Sequence[tuple[str, str, str]]] = None,
    exec_cmd: str = "true",
) -> Path:
    """
    Write a multi-section .desktop file.

    actions: list of (action_id, action_name, action_exec)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Exec={exec_cmd}",
        f"Icon={icon}",
    ]
    if actions:
        action_ids = ";".join(a[0] for a in actions) + ";"
        lines.append(f"Actions={action_ids}")
    if extra_desktop_entry_lines:
        lines.extend(extra_desktop_entry_lines)
    lines.append("")
    if actions:
        for action_id, action_name, action_exec in actions:
            lines.extend(
                [
                    f"[Desktop Action {action_id}]",
                    f"Name={action_name}",
                    f"Exec={action_exec}",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_png(path: Path | str, size: int = 32) -> Path:
    """Write a minimal valid solid-color PNG (stdlib only)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 1x1 or size x size solid red RGBA
    w = h = max(1, int(size))
    raw_rows = []
    for _ in range(h):
        row = b"\x00" + (b"\xff\x00\x00\xff" * w)
        raw_rows.append(row)
    raw = b"".join(raw_rows)
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def write_svg(path: Path | str, *, fill: str = "#3366ff") -> Path:
    """Write a minimal valid SVG for magick-free file-install fixtures."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">\n'
        f'  <rect width="64" height="64" fill="{fill}"/>\n'
        "</svg>\n"
    )
    path.write_text(svg, encoding="utf-8")
    return path


def install_system_app(
    sandbox: XDGSandbox,
    desktop_id: str,
    **desktop_kwargs,
) -> Path:
    """Write a system launcher under the sandbox applications dir."""
    if "name" not in desktop_kwargs:
        desktop_kwargs["name"] = Path(desktop_id).stem
    return write_desktop(sandbox.system_apps / desktop_id, **desktop_kwargs)


def install_user_override(
    sandbox: XDGSandbox,
    desktop_id: str,
    **desktop_kwargs,
) -> Path:
    """Write a user .desktop override under USER_APPS_DIR."""
    if "name" not in desktop_kwargs:
        desktop_kwargs["name"] = Path(desktop_id).stem
    return write_desktop(sandbox.user_apps / desktop_id, **desktop_kwargs)
