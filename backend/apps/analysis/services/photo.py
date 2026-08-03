import io
from PIL import Image


def process_photo(file_obj, max_bytes=1_000_000):
    """Strip EXIF/metadata and compress to JPEG under max_bytes."""
    img = Image.open(file_obj)

    if img.mode in ('RGBA', 'P', 'CMYK', 'LA'):
        img = img.convert('RGB')

    # Resize if too large (max dimension 2048px)
    max_dim = 2048
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    quality = 85
    while True:
        output = io.BytesIO()
        # Save WITHOUT exif= parameter — Pillow drops metadata by default
        img.save(output, format='JPEG', quality=quality, optimize=True)
        size = output.tell()
        if size <= max_bytes or quality <= 20:
            break
        quality -= 10

    output.seek(0)
    return output.read()
