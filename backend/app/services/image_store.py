import uuid
from pathlib import Path

from app.config import settings

SKETCH_DIR = Path(__file__).resolve().parent.parent.parent / "generated_sketches"
SKETCH_DIR.mkdir(exist_ok=True)


def save_sketch(image_bytes: bytes) -> tuple[str, str]:
    """Returns (file_path, served_url)."""
    filename = f"{uuid.uuid4().hex}.png"
    path = SKETCH_DIR / filename
    path.write_bytes(image_bytes)
    return str(path), sketch_url_for(str(path))


def load_sketch(file_path: str) -> bytes:
    return Path(file_path).read_bytes()


def sketch_url_for(file_path: str) -> str:
    # local_base_url, not public_base_url -- the browser fetches this
    # directly, it never needs to go through the ngrok tunnel.
    return f"{settings.local_base_url}/sketches/{Path(file_path).name}"
