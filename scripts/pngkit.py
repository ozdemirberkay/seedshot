"""Minimal image helpers for seedshot (standard library only).

Both stores reject images with an alpha channel, and both simulator and
emulator capture paths produce RGBA. These helpers turn raw captures into
24-bit RGB PNGs and read image headers, without needing Pillow.
"""
import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def write_rgb_png(path, width, height, rgb):
    """Write 8-bit RGB pixels (len == width*height*3) as a PNG without alpha."""
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw += b"\x00"  # filter: none (zlib level 9 still beats most RGBA encoders)
        raw += rgb[y * stride:(y + 1) * stride]
    data = PNG_SIG
    data += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def _drop_alpha(px, r, g, b, step=4):
    n = len(px) // step
    rgb = bytearray(n * 3)
    rgb[0::3] = px[r::step]
    rgb[1::3] = px[g::step]
    rgb[2::3] = px[b::step]
    return rgb


def bmp_to_rgb(data):
    """Decode a 24/32-bit uncompressed or BITFIELDS BMP. Returns (w, h, rgb)."""
    if data[:2] != b"BM":
        raise ValueError("not a BMP file")
    offset = struct.unpack("<I", data[10:14])[0]
    header_size = struct.unpack("<I", data[14:18])[0]
    width, height = struct.unpack("<ii", data[18:26])
    bpp = struct.unpack("<H", data[28:30])[0]
    compression = struct.unpack("<I", data[30:34])[0]
    top_down = height < 0
    height = abs(height)
    if bpp == 32:
        if compression == 3 and header_size >= 52:
            masks = struct.unpack("<III", data[54:66])
        else:
            masks = (0xFF0000, 0xFF00, 0xFF)  # BGRA
        index = {0xFF: 0, 0xFF00: 1, 0xFF0000: 2, 0xFF000000: 3}
        r, g, b = (index[m] for m in masks)
        row_bytes = width * 4
        step = 4
    elif bpp == 24:
        r, g, b = 2, 1, 0
        row_bytes = (width * 3 + 3) & ~3
        step = 3
    else:
        raise ValueError(f"unsupported BMP bit depth {bpp}")
    rows = [data[offset + y * row_bytes: offset + y * row_bytes + width * step] for y in range(height)]
    if not top_down:
        rows.reverse()
    return width, height, _drop_alpha(b"".join(rows), r, g, b, step)


def rgba_to_rgb(px):
    return _drop_alpha(px, 0, 1, 2, 4)


def image_info(path):
    """Return dict(format, width, height, alpha, bit_depth) for PNG or JPEG."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] == PNG_SIG:
        width, height, depth, color = struct.unpack(">IIBB", data[16:26])
        alpha = color in (4, 6)
        pos = 8
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            kind = data[pos + 4:pos + 8]
            if kind == b"tRNS":
                alpha = True
            if kind == b"IDAT":
                break
            pos += 12 + length
        return {"format": "png", "width": width, "height": height, "alpha": alpha,
                "bit_depth": depth, "color_type": color}
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos < len(data):
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
                return {"format": "jpeg", "width": width, "height": height, "alpha": False, "bit_depth": 8}
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                pos += 2
                continue
            pos += 2 + struct.unpack(">H", data[pos + 2:pos + 4])[0]
    return None


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png_rgb(path):
    """Pure-Python decode of an 8-bit, non-interlaced PNG to (w, h, rgb).

    Slow (seconds per screenshot), used only when Pillow isn't installed.
    """
    with open(path, "rb") as f:
        data = f.read()
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", data[16:29])
    if depth != 8 or interlace or color not in (0, 2, 4, 6):
        raise ValueError("unsupported PNG layout; install Pillow (pip install pillow)")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    idat, pos = bytearray(), 8
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(height * stride)
    prev = bytearray(stride)
    for y in range(height):
        ftype = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up_left = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    if channels == 3:
        return width, height, out
    if channels == 4:
        return width, height, _drop_alpha(out, 0, 1, 2, 4)
    gray = out[0::channels]
    rgb = bytearray(len(gray) * 3)
    rgb[0::3] = rgb[1::3] = rgb[2::3] = gray
    return width, height, rgb


def strip_alpha(path):
    """Rewrite an image in place as 8-bit RGB without alpha. Returns the method used."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            fmt = im.format
            rgb = im.convert("RGB")
        if fmt == "JPEG":
            rgb.save(path, "JPEG", quality=95)
        else:
            rgb.save(path, "PNG", optimize=True)
        return "pillow"
    except ImportError:
        width, height, rgb = decode_png_rgb(path)
        write_rgb_png(path, width, height, rgb)
        return "pure-python"
