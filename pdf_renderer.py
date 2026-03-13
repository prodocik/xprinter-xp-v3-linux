"""PDF loading and rendering to images for label printing."""

import fitz  # PyMuPDF
from PIL import Image
import io

from label_sizes import mm_to_dots


class PDFDocument:
    """Manages a loaded PDF and renders pages to images."""

    def __init__(self, path):
        self._doc = fitz.open(path)
        self._path = path

    @property
    def page_count(self):
        return len(self._doc)

    @property
    def path(self):
        return self._path

    def close(self):
        self._doc.close()

    def render_page(self, page_num, dpi=203):
        """Render a page to a PIL Image at given DPI."""
        page = self._doc[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img

    def render_thumbnail(self, page_num, max_size=150):
        """Render a small thumbnail of a page."""
        page = self._doc[page_num]
        # Calculate zoom to fit within max_size
        rect = page.rect
        scale = min(max_size / rect.width, max_size / rect.height)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img

    def render_preview(self, page_num, max_width=600, max_height=800):
        """Render a preview-sized image of a page."""
        page = self._doc[page_num]
        rect = page.rect
        scale = min(max_width / rect.width, max_height / rect.height, 4.0)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img


def prepare_label_image(pil_image, width_mm, height_mm, dpi=203):
    """
    Scale and convert a rendered page to a 1-bit label image.

    Returns a PIL Image in mode '1' sized to the label dimensions.
    """
    target_w = mm_to_dots(width_mm, dpi)
    target_h = mm_to_dots(height_mm, dpi)

    # Scale to fit within label, maintaining aspect ratio
    img = pil_image
    scale = min(target_w / img.width, target_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Create white canvas at label size and paste centered
    canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    canvas.paste(img, (x_offset, y_offset))

    # Convert to grayscale, then to 1-bit with dithering
    gray = canvas.convert("L")
    mono = gray.convert("1")  # Floyd-Steinberg dithering by default

    return mono


def pil_to_gdk_pixbuf(pil_image):
    """Convert a PIL Image to GdkPixbuf.Pixbuf for GTK display."""
    from gi.repository import GdkPixbuf, GLib

    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    width, height = pil_image.size
    data = pil_image.tobytes()
    gbytes = GLib.Bytes.new(data)

    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        gbytes,
        GdkPixbuf.Colorspace.RGB,
        False,  # no alpha
        8,      # bits per sample
        width,
        height,
        width * 3,  # rowstride
    )
    return pixbuf
