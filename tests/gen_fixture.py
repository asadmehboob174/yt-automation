import struct, zlib
from pathlib import Path

def make_png(w, h, rgb=(200, 60, 60)):
    def chunk(ct, d):
        c = ct + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    hdr = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    raw = b''
    for _ in range(h):
        raw += b'\x00' + bytes(rgb) * w
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return hdr + ihdr + idat + iend

out = Path(__file__).parent / "fixtures"
out.mkdir(parents=True, exist_ok=True)
p = out / "test_scene.png"
p.write_bytes(make_png(256, 256))
print(f"Created {p} ({p.stat().st_size} bytes)")
