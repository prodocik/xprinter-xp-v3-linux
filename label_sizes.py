"""Preset label sizes for common thermal labels."""

# Each entry: name -> (width_mm, height_mm)
LABEL_SIZES = {
    "20 × 10 мм": (20, 10),
    "30 × 20 мм": (30, 20),
    "40 × 20 мм": (40, 20),
    "40 × 30 мм": (40, 30),
    "58 × 30 мм": (58, 30),
    "58 × 40 мм": (58, 40),
    "60 × 40 мм": (60, 40),
    "80 × 50 мм": (80, 50),
    "80 × 60 мм": (80, 60),
    "100 × 60 мм": (100, 60),
    "100 × 70 мм": (100, 70),
    "100 × 150 мм": (100, 150),
    "120 × 75 мм": (120, 75),
}

DEFAULT_SIZE = "58 × 40 мм"


def mm_to_dots(mm, dpi=203):
    """Convert millimeters to dots at given DPI."""
    return int(mm * dpi / 25.4)
