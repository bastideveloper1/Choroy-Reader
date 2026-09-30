"""Restrict source images to bounded raster formats, never SVG/EPS or plugins."""
import io
from PIL import Image

FORMATS = ('JPEG', 'PNG', 'WEBP', 'GIF', 'ICO', 'BMP')
MAX_PIXELS = 20_000_000
MAX_BYTES = 16 * 1024 * 1024


def open_image(data):
    if len(data) > MAX_BYTES:
        raise ValueError('Imagen demasiado grande')
    image = Image.open(io.BytesIO(data), formats=FORMATS)
    if image.width * image.height > MAX_PIXELS:
        image.close()
        raise ValueError('La imagen supera el límite de 20 megapíxeles')
    return image
