from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import cv2
from file_io import read_image_unicode, save_image_unicode
import numpy as np
import pandas as pd
from scipy import ndimage as ndi


HEATMAP_LABELS = {
    "coverage_percent": "Droplet coverage (%)",
    "count_per_10000_px2": "Droplets / 10,000 pixels²",
    "mean_area_px2": "Mean droplet area (pixels²)",
    "radial_zones": "Concentric zone (1 = innermost)",
}
SPATIAL_EXPORTS = (
    "spatial_summary.csv", "spatial_droplets.csv", "spatial_rings.csv",
    *[f"{key}.png" for key in HEATMAP_LABELS],
)


@dataclass
class SpatialResult:
    region: np.ndarray
    center_xy: tuple[float, float]
    kernel_size: int
    ring_count: int
    px_per_micron: float
    summary: dict[str, object]
    droplets: pd.DataFrame
    rings: pd.DataFrame
    heatmaps: dict[str, np.ndarray]


def mask_fingerprint(mask: np.ndarray) -> str:
    binary = np.ascontiguousarray(mask > 0, dtype=np.uint8)
    digest = hashlib.sha256(str(binary.shape).encode())
    digest.update(binary.tobytes())
    return digest.hexdigest()


def automatic_region(image: np.ndarray, threshold: int | None = None, dark: bool = False) -> np.ndarray:
    """Find the largest foreground component and fill its internal holes."""
    image = np.asarray(image)
    if image.dtype != np.uint8:
        raise ValueError("Automatic outlining requires an 8-bit image.")
    if image.ndim == 3 and image.shape[2] >= 3:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_RGB2GRAY)
    elif image.ndim == 2:
        gray = image
    else:
        raise ValueError("Choose a grayscale or RGB image for automatic outlining.")
    if threshold is not None and not 0 <= threshold <= 255:
        raise ValueError("The outline threshold must be between 0 and 255.")
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    mode = cv2.THRESH_BINARY_INV if dark else cv2.THRESH_BINARY
    if threshold is None:
        mode |= cv2.THRESH_OTSU
    _, binary = cv2.threshold(gray, threshold or 0, 255, mode)
    labeled, count = ndi.label(binary > 0, structure=np.ones((3, 3)))
    if not count:
        raise ValueError("No enclosing region was found. Adjust the threshold, draw an outline, or import a mask.")
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0
    return ndi.binary_fill_holes(labeled == int(sizes.argmax()))


def analyze_spatial(
    mask: np.ndarray,
    droplets: pd.DataFrame,
    region: np.ndarray,
    *,
    center_xy: tuple[float, float] | None = None,
    kernel_size: int = 31,
    ring_count: int = 5,
    px_per_micron: float = 0,
    result_name: str = "",
) -> SpatialResult:
    """Use saved droplet centroids for counts, and mask intersection for coverage.

    Droplets belong to the region/zone containing their rounded centroid. Their
    whole measured area is retained, even when their boundary crosses the region.
    Coverage always uses the exact foreground pixels intersecting the region.
    """
    binary = np.asarray(mask) > 0
    region = np.asarray(region) > 0
    if binary.ndim != 2 or region.shape != binary.shape:
        raise ValueError("The region mask must match the detection mask's width and height exactly.")
    if not region.any():
        raise ValueError("The enclosing region is empty.")
    if not isinstance(kernel_size, int) or not 3 <= kernel_size <= 1001 or kernel_size % 2 == 0:
        raise ValueError("Density window size must be an odd integer between 3 and 1001 pixels.")
    if not isinstance(ring_count, int) or not 1 <= ring_count <= 100:
        raise ValueError("Choose between 1 and 100 concentric zones.")
    if not np.isfinite(px_per_micron) or px_per_micron < 0:
        raise ValueError("Pixels per micron must be zero or a positive number.")

    height, width = binary.shape
    if center_xy is None:
        center_y, center_x = ndi.center_of_mass(region)
    else:
        center_x, center_y = center_xy
    if not (np.isfinite(center_x) and np.isfinite(center_y)
            and 0 <= center_x <= width - 1 and 0 <= center_y <= height - 1):
        raise ValueError("The reference center must be inside the image.")

    required = ["centroid-0", "centroid-1", "area"]
    if not all(column in droplets.columns for column in required):
        raise ValueError("Run automatic quantification to create droplet centroids and areas first.")
    table = droplets.copy().reset_index(drop=True)
    values = table[required].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, 2] <= 0).any():
        raise ValueError("Droplet measurements contain invalid centroids or areas.")
    ys, xs, areas = values.T
    if ((ys < 0) | (ys > height - 1) | (xs < 0) | (xs > width - 1)).any():
        raise ValueError("Droplet coordinates do not match the detection image.")
    pixel_y, pixel_x = np.floor(ys + 0.5).astype(int), np.floor(xs + 0.5).astype(int)
    inside = region[pixel_y, pixel_x]
    distances = np.hypot(xs - center_x, ys - center_y)
    distance_grid = np.hypot(np.arange(height)[:, None] - center_y, np.arange(width)[None, :] - center_x)
    max_radius = float(distance_grid[region].max())
    radius_step = max(max_radius, 1e-12) / ring_count
    # A rounded centroid uses the same zone as its region pixel. This guarantees
    # that every counted droplet belongs to a zone with nonzero region area.
    zones = np.zeros(binary.shape, dtype=np.uint16)
    zones[region] = np.minimum((distance_grid[region] / radius_step).astype(int), ring_count - 1) + 1
    table["inside_region"] = inside
    table["radial_zone"] = zones[pixel_y, pixel_x]
    table["distance_to_center_px"] = distances
    physical_columns = ["area_sqmicron", "eq_diam_micron", "distance_to_center_micron"]
    table = table.drop(columns=physical_columns, errors="ignore")
    if px_per_micron > 0:
        table["area_sqmicron"] = areas / px_per_micron ** 2
        if "equivalent_diameter" in table:
            table["eq_diam_micron"] = pd.to_numeric(table["equivalent_diameter"]) / px_per_micron
        table["distance_to_center_micron"] = distances / px_per_micron

    def summarize(region_part: np.ndarray, selected: np.ndarray) -> dict[str, object]:
        area = int(region_part.sum())
        foreground = int(np.count_nonzero(binary & region_part))
        count = int(selected.sum())
        row: dict[str, object] = {
            "region_area_px2": area,
            "droplet_pixels_px2": foreground,
            "coverage_percent": 100 * foreground / area if area else 0.0,
            "droplet_count": count,
            "count_per_10000_px2": count * 10000 / area if area else 0.0,
            "mean_droplet_area_px2": float(areas[selected].mean()) if count else None,
            "mean_distance_to_center_px": float(distances[selected].mean()) if count else None,
            "median_distance_to_center_px": float(np.median(distances[selected])) if count else None,
        }
        if px_per_micron > 0:
            area_um = area / px_per_micron ** 2
            row["region_area_micron2"] = area_um
            row["count_per_micron2"] = count / area_um if area_um else 0.0
            row["mean_droplet_area_micron2"] = float(areas[selected].mean()) / px_per_micron ** 2 if count else None
            row["mean_distance_to_center_micron"] = float(distances[selected].mean()) / px_per_micron if count else None
            row["median_distance_to_center_micron"] = float(np.median(distances[selected])) / px_per_micron if count else None
        return row

    summary = {
        "result_name": result_name, "center_x_px": float(center_x), "center_y_px": float(center_y),
        "pixels_per_micron": float(px_per_micron), "density_window_px": kernel_size,
        "radial_zones": ring_count, **summarize(region, inside),
    }
    rings = pd.DataFrame([
        {"result_name": result_name, "radial_zone": index,
         "inner_radius_px": (index - 1) * radius_step, "outer_radius_px": index * radius_step,
         **summarize(zones == index, inside & (table["radial_zone"].to_numpy() == index))}
        for index in range(1, ring_count + 1)
    ])

    centroid_counts = np.zeros(binary.shape, dtype=np.float32)
    centroid_areas = np.zeros(binary.shape, dtype=np.float32)
    np.add.at(centroid_counts, (pixel_y[inside], pixel_x[inside]), 1)
    np.add.at(centroid_areas, (pixel_y[inside], pixel_x[inside]), areas[inside])

    def window_sum(array: np.ndarray) -> np.ndarray:
        return cv2.boxFilter(array.astype(np.float32), -1, (kernel_size, kernel_size),
                             normalize=False, borderType=cv2.BORDER_CONSTANT)

    window_area = window_sum(region)
    window_counts = window_sum(centroid_counts)
    coverage = np.divide(window_sum(binary & region) * 100, window_area,
                         out=np.zeros(binary.shape, dtype=np.float32), where=window_area > 0)
    count_density = np.divide(window_counts * 10000, window_area,
                              out=np.zeros(binary.shape, dtype=np.float32), where=window_area > 0)
    mean_area = np.divide(window_sum(centroid_areas), window_counts,
                          out=np.full(binary.shape, np.nan, dtype=np.float32), where=window_counts > 0)
    heatmaps = {"coverage_percent": coverage, "count_per_10000_px2": count_density,
                "mean_area_px2": mean_area, "radial_zones": zones.astype(np.float32)}
    for heatmap in heatmaps.values():
        heatmap[~region] = np.nan
    return SpatialResult(region.copy(), (float(center_x), float(center_y)), kernel_size, ring_count,
                         float(px_per_micron), summary, table, rings, heatmaps)


def draw_spatial_figure(figure, source: np.ndarray, mask: np.ndarray, result: SpatialResult,
                        metric: str = "coverage_percent", dark: bool = False) -> object:
    """Draw a reviewable region outline beside a density or radial-zone map."""
    figure.clear()
    axes = figure.subplots(1, 2)
    axes[0].imshow(source, cmap="gray")
    if np.any(mask) and not np.all(mask):
        axes[0].contour(mask > 0, levels=[0.5], colors=["lime"], linewidths=0.5)
    axes[0].set_title("Enclosing region and droplets")
    data = np.ma.masked_invalid(result.heatmaps[metric])
    maximum = float(data.max()) if data.count() else 0.0
    options = {"vmin": 0, "vmax": 100 if metric == "coverage_percent" else max(maximum, 1.0)}
    plotted = axes[1].imshow(data, cmap="viridis", **options)
    axes[1].set_title(HEATMAP_LABELS[metric])
    colorbar = figure.colorbar(plotted, ax=axes[1], fraction=0.046, pad=0.04)
    height, width = result.region.shape
    for axis in axes:
        axis.contour(np.arange(-1, width + 1), np.arange(-1, height + 1),
                     np.pad(result.region, 1), levels=[0.5], colors=["cyan"], linewidths=1)
        axis.plot(*result.center_xy, marker="+", markersize=12, color="red", markeredgewidth=2)
        axis.set_xlim(-0.5, width - 0.5)
        axis.set_ylim(height - 0.5, -0.5)
        axis.set_xlabel("X (pixels)")
        axis.set_ylabel("Y (pixels)")
    background, foreground = ("#020617", "#e2e8f0") if dark else ("white", "#111827")
    figure.set_facecolor(background)
    for axis in (*axes, colorbar.ax):
        axis.set_facecolor(background)
        axis.tick_params(colors=foreground)
        axis.title.set_color(foreground)
        axis.xaxis.label.set_color(foreground)
        axis.yaxis.label.set_color(foreground)
        for spine in axis.spines.values():
            spine.set_edgecolor(foreground)
    figure.tight_layout()
    return axes[0]


def export_spatial(directory: Path, result: SpatialResult, mask: np.ndarray,
                   source: np.ndarray, region_source: str = "", outline_options: dict | None = None) -> None:
    from matplotlib.figure import Figure

    directory.mkdir(parents=True, exist_ok=True)
    save_image_unicode(directory / "region_mask.png", result.region.astype(np.uint8) * 255)
    pd.DataFrame([result.summary]).to_csv(directory / "spatial_summary.csv", index=False)
    result.droplets.to_csv(directory / "spatial_droplets.csv", index=False)
    result.rings.to_csv(directory / "spatial_rings.csv", index=False)
    for metric in HEATMAP_LABELS:
        figure = Figure(figsize=(11, 5), dpi=150)
        draw_spatial_figure(figure, source, mask, result, metric)
        figure.savefig(directory / f"{metric}.png", dpi=150)
    parameters = {
        "format": "segment_app_spatial", "version": 1,
        "center_xy": list(result.center_xy), "kernel_size": result.kernel_size,
        "ring_count": result.ring_count, "px_per_micron": result.px_per_micron,
        "mask_fingerprint": mask_fingerprint(mask), "measurements_current": True,
        "region_source": region_source, "outline_options": outline_options or {},
    }
    (directory / "parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")


def invalidate_spatial_exports(out_dir: Path, result_stem: str) -> bool:
    """Keep the user's outline/settings, but discard measurements of an old mask."""
    directory = out_dir / "spatial_analysis" / result_stem
    if not directory.is_dir():
        return False
    for filename in SPATIAL_EXPORTS:
        (directory / filename).unlink(missing_ok=True)
    parameter_path = directory / "parameters.json"
    if parameter_path.exists():
        parameters = json.loads(parameter_path.read_text(encoding="utf-8"))
        parameters["measurements_current"] = False
        parameter_path.write_text(json.dumps(parameters, indent=2), encoding="utf-8")
    return True
