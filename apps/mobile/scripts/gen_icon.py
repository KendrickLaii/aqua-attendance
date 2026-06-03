"""Generate a solid brand-color PNG for app.json (run once: python scripts/gen_icon.py)."""
import struct
import zlib
from pathlib import Path

W, H = 192, 192
R, G, B = 0x16, 0x0D, 0x47


def chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def main() -> None:
    raw = b"".join(b"\x00" + bytes([R, G, B]) * W for _ in range(H))
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    out = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    out.write_bytes(png)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
