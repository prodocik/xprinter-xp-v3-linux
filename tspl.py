"""TSPL/TSPL2 command builder for Xprinter thermal label printers."""

from label_sizes import mm_to_dots


class TSPLBuilder:
    """Builds a sequence of TSPL commands for label printing."""

    def __init__(self):
        self._commands = []

    def _cmd(self, text):
        self._commands.append(text)
        return self

    def size(self, width_mm, height_mm):
        """Set label width and height in mm."""
        return self._cmd(f"SIZE {width_mm} mm, {height_mm} mm")

    def gap(self, gap_mm, offset_mm=0):
        """Set gap distance between labels."""
        return self._cmd(f"GAP {gap_mm} mm, {offset_mm} mm")

    def direction(self, d=1, mirror=0):
        """Set print direction. d: 0 or 1, mirror: 0 or 1."""
        return self._cmd(f"DIRECTION {d},{mirror}")

    def density(self, n):
        """Set print density (darkness). n: 0-15."""
        n = max(0, min(15, n))
        return self._cmd(f"DENSITY {n}")

    def speed(self, n):
        """Set print speed. n: 1-5."""
        n = max(1, min(5, n))
        return self._cmd(f"SPEED {n}")

    def cls(self):
        """Clear image buffer."""
        return self._cmd("CLS")

    def bitmap(self, x, y, width_bytes, height, data):
        """
        Send raw monochrome bitmap.

        x, y: position in dots
        width_bytes: width in bytes (pixels / 8)
        height: height in dots/pixels
        data: raw bitmap bytes (1 = black, MSB first)
        """
        self._commands.append(f"BITMAP {x},{y},{width_bytes},{height},0,")
        self._commands.append(data)  # raw bytes appended after command
        return self

    def print_label(self, qty=1, sets=1):
        """Print labels. qty: number of label sets, sets: copies per set."""
        return self._cmd(f"PRINT {qty},{sets}")

    def build(self):
        """Build the complete command sequence as bytes."""
        parts = []
        for cmd in self._commands:
            if isinstance(cmd, bytes):
                parts.append(cmd)
            else:
                parts.append((cmd + "\r\n").encode("ascii"))
        self._commands.clear()
        return b"".join(parts)


def build_label_job(image_1bit, width_mm, height_mm, copies=1,
                    gap_mm=2, density=8, speed=3, dpi=203):
    """
    Build a complete TSPL print job from a 1-bit PIL Image.

    image_1bit: PIL Image in mode '1' (1-bit pixels), already sized to label.
    Returns bytes ready to send to the printer.
    """
    w_dots = image_1bit.width
    h_dots = image_1bit.height
    # Width must be byte-aligned
    width_bytes = (w_dots + 7) // 8

    # Convert PIL 1-bit image to raw bitmap bytes
    # In PIL mode '1': 0=black, 255=white
    # In TSPL BITMAP: 0=white, 1=black (inverted)
    raw = image_1bit.tobytes()

    # PIL packs 1-bit images as 1 byte per pixel in tobytes()
    # We need to repack into bit-packed format for TSPL
    bitmap_data = bytearray(width_bytes * h_dots)
    for row in range(h_dots):
        for col in range(w_dots):
            px = raw[row * w_dots + col] if (row * w_dots + col) < len(raw) else 255
            byte_idx = row * width_bytes + col // 8
            bit_idx = 7 - (col % 8)
            if px == 0:  # black pixel
                bitmap_data[byte_idx] |= (1 << bit_idx)

    builder = TSPLBuilder()
    builder.size(width_mm, height_mm)
    builder.gap(gap_mm)
    builder.direction(1)
    builder.density(density)
    builder.speed(speed)
    builder.cls()
    builder.bitmap(0, 0, width_bytes, h_dots, bytes(bitmap_data))
    builder.print_label(copies)

    return builder.build()
