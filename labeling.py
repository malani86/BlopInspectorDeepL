from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.measure import label, regionprops_table
from skimage.segmentation import watershed


DROPLET_COLUMNS = ["label", "area", "equivalent_diameter", "centroid-0", "centroid-1"]


def split_mask_with_watershed(binary_mask: np.ndarray) -> np.ndarray:
    binary = binary_mask.astype(bool)
    if not np.any(binary):
        return np.zeros(binary.shape, dtype=np.int32)
    distance = ndi.distance_transform_edt(binary)
    max_coords = peak_local_max(distance, labels=binary, min_distance=3, exclude_border=False)
    if len(max_coords) == 0:
        return label(binary, connectivity=1).astype(np.int32)
    local_maxima = np.zeros(distance.shape, dtype=bool)
    local_maxima[tuple(max_coords.T)] = True
    markers, _ = ndi.label(local_maxima)
    if markers.max() == 0:
        return label(binary, connectivity=1).astype(np.int32)
    return watershed(-distance, markers, mask=binary).astype(np.int32)


def label_droplets(binary_mask: np.ndarray, min_area: int, *, use_watershed: bool) -> np.ndarray:
    labeled = label(binary_mask > 0, connectivity=1)
    sizes = np.bincount(labeled.ravel())
    keep = sizes >= min_area
    keep[0] = False
    binary = keep[labeled]
    if use_watershed:
        return split_mask_with_watershed(binary)
    return label(binary, connectivity=1).astype(np.int32)


def measure_droplet_labels(labeled: np.ndarray, px_per_um: float | None) -> pd.DataFrame:
    if not np.any(labeled):
        table = pd.DataFrame(columns=DROPLET_COLUMNS)
        if px_per_um is not None and px_per_um > 0:
            table["area_sqmicron"] = pd.Series(dtype=float)
            table["eq_diam_micron"] = pd.Series(dtype=float)
        return table
    table = pd.DataFrame(regionprops_table(
        labeled, properties=["label", "area", "equivalent_diameter", "centroid"],
    ))
    if px_per_um is not None and px_per_um > 0:
        table["area_sqmicron"] = table["area"] / px_per_um ** 2
        table["eq_diam_micron"] = table["equivalent_diameter"] / px_per_um
    return table


def colorize_labels(labeled: np.ndarray) -> np.ndarray:
    """Give each object ID a stable bright color; reserve black for background."""
    # This triangular permutation spreads neighboring IDs across the RGB cube
    # without repeating colors for the first 208**3 objects. Each multiplier
    # on a new input channel is coprime to 208, making the mapping reversible.
    encoded = labeled.astype(np.int64) % (208 ** 3)
    red = (73 * (encoded % 208) + 19) % 208
    green = (151 * (encoded // 208 % 208) + 129 * red ** 2 + 99 * red + 192) % 208
    blue = (157 * (encoded // (208 ** 2)) + 26 * green ** 2 + 54 * green + 20 * red + 144) % 208
    rgb = np.stack((48 + red, 48 + green, 48 + blue), axis=-1).astype(np.uint8)
    rgb[labeled == 0] = 0
    return rgb


# Keep the existing public import used by the batch pipeline.
from file_io import save_image_unicode


def save_label_maps(out_dir: Path, stem: str, labeled: np.ndarray) -> None:
    directory = out_dir / "labeled_maps"
    directory.mkdir(parents=True, exist_ok=True)
    np.save(directory / f"{stem}_labels.npy", labeled.astype(np.int32), allow_pickle=False)
    rgb = colorize_labels(labeled)
    save_image_unicode(directory / f"{stem}_labels.png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def clear_label_maps(out_dir: Path, stem: str) -> None:
    for suffix in (".npy", ".png"):
        (out_dir / "labeled_maps" / f"{stem}_labels{suffix}").unlink(missing_ok=True)


def load_label_map(out_dir: Path, stem: str, mask: np.ndarray | None = None) -> np.ndarray | None:
    path = out_dir / "labeled_maps" / f"{stem}_labels.npy"
    if not path.is_file():
        return None
    labeled = np.load(path, allow_pickle=False)
    if labeled.ndim != 2 or not np.issubdtype(labeled.dtype, np.integer) or np.any(labeled < 0):
        raise ValueError("The saved droplet label map is invalid. Analyze this image again.")
    if mask is not None and (labeled.shape != mask.shape or not np.array_equal(labeled > 0, mask > 0)):
        raise ValueError("The droplet label map does not match the saved mask. Analyze this image again.")
    return labeled
