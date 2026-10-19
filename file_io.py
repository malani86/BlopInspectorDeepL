"""Unicode-safe image I/O shared by the GUI and batch worker."""
from pathlib import Path
import os
import tempfile
import cv2
import numpy as np


def read_image_unicode(path: str | Path, flags: int = cv2.IMREAD_COLOR):
    """Match imread's None-on-failure behavior without native path handling."""
    try:
        data = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
        return cv2.imdecode(data, flags) if data.size else None
    except (OSError, cv2.error):
        return None


def save_image_unicode(path: str | Path, image: np.ndarray) -> None:
    """Encode first, then atomically replace the destination via Python."""
    path = Path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        success, encoded = cv2.imencode(path.suffix, image)
        if not success:
            raise OSError("OpenCV could not encode the image")
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=path.suffix, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded.tobytes())
        os.replace(temporary, path)
    except (OSError, cv2.error) as exc:
        raise OSError(f"Could not save image to {path}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
