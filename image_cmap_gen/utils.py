from PIL import Image


def load_image(file_obj) -> Image.Image:
    """Load a PIL Image from an uploaded file object."""
    img = Image.open(file_obj).convert("RGB")
    return img


def resize_for_processing(img: Image.Image, max_side: int = 200) -> Image.Image:
    """Resize image so its longest side is at most max_side pixels."""
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    scale = max_side / max(w, h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    return img.resize((new_w, new_h), Image.LANCZOS)
