from __future__ import annotations

import json
from pathlib import Path

import cv2
from file_io import read_image_unicode, save_image_unicode
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.widgets import PolygonSelector
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from config import DEFAULT_DENSITY_KERNEL_SIZE, DEFAULT_RADIAL_BINS
from spatial_analysis import (
    HEATMAP_LABELS, SpatialResult, analyze_spatial, automatic_region,
    draw_spatial_figure, export_spatial, mask_fingerprint,
)


class SpatialAnalysisDialog(QDialog):
    exported = Signal(str)

    def __init__(self, *, mask: np.ndarray, droplets: pd.DataFrame,
                 source: np.ndarray, result_name: str, output_dir: Path,
                 px_per_micron: float, allow_automatic: bool = True,
                 dark: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Spatial Analysis — {result_name}")
        self.resize(1280, 850)
        self.setMinimumSize(960, 650)
        self.mask = mask > 0
        self.source = source
        if source.shape[:2] != self.mask.shape:
            raise ValueError("The source image must match the saved detection mask exactly.")
        self.droplets = droplets
        self.result_name = result_name
        self.output_dir = output_dir
        self.dark = dark
        self.region = np.ones(self.mask.shape, dtype=bool)
        self.region_source = "Full image"
        self.result: SpatialResult | None = None
        self._analysis_pending = True
        self._polygon: PolygonSelector | None = None
        self._outline_axis = None
        self._build_ui(px_per_micron, allow_automatic)
        restored = self._restore_outline()
        if not restored and allow_automatic:
            try:
                self.region = automatic_region(self.source)
                self.region_source = "Automatic outline (review before export)"
            except ValueError:
                self.region_source = "Full image — draw or import an enclosing region"
        if not restored:
            self._reset_center()
        self.update_analysis()

    def _build_ui(self, px_per_micron: float, allow_automatic: bool) -> None:
        controls = QWidget()
        controls.setMaximumWidth(300)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        region_group = QGroupBox("Enclosing cell or tissue")
        region_layout = QVBoxLayout(region_group)
        self.outline_method = QComboBox()
        self.outline_method.addItems(["Automatic threshold (Otsu)", "Manual intensity threshold"])
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 255)
        self.threshold_spin.setValue(30)
        self.threshold_spin.setEnabled(False)
        self.outline_method.currentIndexChanged.connect(
            lambda index: self.threshold_spin.setEnabled(index == 1)
        )
        self.dark_region = QCheckBox("Region is darker than background")
        self.auto_button = QPushButton("Auto outline")
        self.auto_button.setEnabled(allow_automatic)
        self.auto_button.clicked.connect(self._auto_outline)
        if not allow_automatic:
            hint = QLabel("An aligned original image is unavailable. Draw an outline or import a region mask.")
            hint.setWordWrap(True)
            region_layout.addWidget(hint)
        region_layout.addWidget(self.outline_method)
        region_layout.addWidget(self.threshold_spin)
        region_layout.addWidget(self.dark_region)
        region_layout.addWidget(self.auto_button)
        self.draw_button = QPushButton("Draw outline")
        self.draw_button.setCheckable(True)
        self.draw_button.toggled.connect(self._toggle_drawing)
        import_button = QPushButton("Import region mask...")
        import_button.clicked.connect(self._import_region)
        full_button = QPushButton("Use full image")
        full_button.clicked.connect(lambda: self._set_region(np.ones_like(self.mask), "Full image"))
        for button in (self.draw_button, import_button, full_button):
            region_layout.addWidget(button)
        self.region_label = QLabel()
        self.region_label.setWordWrap(True)
        region_layout.addWidget(self.region_label)
        controls_layout.addWidget(region_group)

        settings_group = QGroupBox("Spatial measurements")
        form = QFormLayout(settings_group)
        self.center_x = QDoubleSpinBox()
        self.center_y = QDoubleSpinBox()
        self.center_x.setRange(0, self.mask.shape[1] - 1)
        self.center_y.setRange(0, self.mask.shape[0] - 1)
        for spin in (self.center_x, self.center_y):
            spin.setDecimals(2)
            spin.valueChanged.connect(self._mark_pending)
        form.addRow("Center X (pixels)", self.center_x)
        form.addRow("Center Y (pixels)", self.center_y)
        reset_center = QPushButton("Use region center")
        reset_center.clicked.connect(self._reset_center)
        form.addRow(reset_center)
        self.kernel_spin = QSpinBox()
        self.kernel_spin.setRange(3, 1001)
        self.kernel_spin.setSingleStep(2)
        self.kernel_spin.setValue(DEFAULT_DENSITY_KERNEL_SIZE)
        self.kernel_spin.setToolTip("Odd window width in pixels. Density divides by region pixels inside each window.")
        self.rings_spin = QSpinBox()
        self.rings_spin.setRange(1, 100)
        self.rings_spin.setValue(DEFAULT_RADIAL_BINS)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0, 10000)
        self.scale_spin.setDecimals(4)
        self.scale_spin.setValue(self._measurement_scale(px_per_micron))
        self.scale_spin.setToolTip("Microscope calibration. Set to 0 for pixel units only.")
        for spin in (self.kernel_spin, self.rings_spin, self.scale_spin):
            spin.valueChanged.connect(self._mark_pending)
        form.addRow("Density window (pixels)", self.kernel_spin)
        form.addRow("Concentric zones", self.rings_spin)
        form.addRow("Pixels per micron", self.scale_spin)
        self.update_button = QPushButton("Update Analysis")
        self.update_button.clicked.connect(self.update_analysis)
        form.addRow(self.update_button)
        controls_layout.addWidget(settings_group)
        self.metric_combo = QComboBox()
        for key, title in HEATMAP_LABELS.items():
            self.metric_combo.addItem(title, key)
        self.metric_combo.currentIndexChanged.connect(self._render)
        controls_layout.addWidget(QLabel("Heatmap display"))
        controls_layout.addWidget(self.metric_combo)
        controls_layout.addStretch(1)

        self.figure = Figure(figsize=(9, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        if self.dark:
            for action in self.toolbar.actions():
                if action.icon().isNull():
                    continue
                pixmap = action.icon().pixmap(self.toolbar.iconSize())
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#e2e8f0"))
                painter.end()
                action.setIcon(QIcon(pixmap))
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.zones_table = QTableWidget()
        self.distance_table = QTableWidget()
        tables = QTabWidget()
        tables.addTab(self.zones_table, "Concentric zones")
        tables.addTab(self.distance_table, "Droplet distances")
        tables.setMaximumHeight(220)
        plots_layout = QVBoxLayout()
        plots_layout.addWidget(self.toolbar)
        plots_layout.addWidget(self.canvas, 1)
        legend = QLabel("Cyan: enclosing region · Green: detected droplets · Red +: reference center. Distances are 2D.")
        legend.setWordWrap(True)
        plots_layout.addWidget(legend)
        plots_layout.addWidget(self.summary_label)
        plots_layout.addWidget(tables)

        body = QHBoxLayout()
        body.addWidget(controls)
        body.addLayout(plots_layout, 1)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.export_button = QPushButton("Export Spatial Results")
        self.export_button.clicked.connect(self._export)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.addButton(self.export_button, QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addWidget(self.status_label)
        root.addWidget(buttons)

    def _measurement_scale(self, fallback: float) -> float:
        if {"area", "area_sqmicron"}.issubset(self.droplets.columns):
            areas = pd.to_numeric(self.droplets["area"], errors="coerce")
            physical = pd.to_numeric(self.droplets["area_sqmicron"], errors="coerce")
            valid = (areas > 0) & (physical > 0)
            if valid.any():
                return float(np.sqrt((areas[valid] / physical[valid]).median()))
        return max(0, float(fallback))

    def _restore_outline(self) -> bool:
        parameters_path = self.output_dir / "parameters.json"
        if not parameters_path.is_file():
            return False
        try:
            parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
            if parameters.get("format") != "segment_app_spatial":
                return False
            region = read_image_unicode(str(self.output_dir / "region_mask.png"), cv2.IMREAD_GRAYSCALE)
            if region is None or region.shape != self.mask.shape or not np.any(region):
                return False
            self.region = region > 0
            self.region_source = parameters.get("region_source", "Saved region")
            self.center_x.setValue(float(parameters["center_xy"][0]))
            self.center_y.setValue(float(parameters["center_xy"][1]))
            self.kernel_spin.setValue(int(parameters["kernel_size"]))
            self.rings_spin.setValue(int(parameters["ring_count"]))
            self.scale_spin.setValue(float(parameters["px_per_micron"]))
            outline = parameters.get("outline_options", {})
            self.outline_method.setCurrentIndex(1 if outline.get("manual_threshold") else 0)
            self.threshold_spin.setValue(int(outline.get("threshold", 30)))
            self.dark_region.setChecked(bool(outline.get("dark", False)))
            self._restored_mask_changed = parameters.get("mask_fingerprint") != mask_fingerprint(self.mask)
            return True
        except (ValueError, TypeError, KeyError, OSError, IndexError):
            return False

    def _mark_pending(self, *_args) -> None:
        self._analysis_pending = True
        if hasattr(self, "export_button"):
            self.export_button.setEnabled(False)
            self.status_label.setText("Settings changed. Click Update Analysis to refresh measurements before export.")

    def _reset_center(self) -> None:
        ys, xs = np.nonzero(self.region)
        self.center_x.setValue(float(xs.mean()))
        self.center_y.setValue(float(ys.mean()))

    def _set_region(self, region: np.ndarray, description: str) -> None:
        self._stop_drawing()
        if region.shape != self.mask.shape or not np.any(region):
            raise ValueError("Use a nonempty region mask with the same dimensions as the detection mask.")
        self.region = region > 0
        self.region_source = description
        self._reset_center()
        self.update_analysis()

    def _auto_outline(self) -> None:
        try:
            threshold = self.threshold_spin.value() if self.outline_method.currentIndex() else None
            region = automatic_region(self.source, threshold, self.dark_region.isChecked())
            self._set_region(region, "Automatic outline (review before export)")
        except ValueError as exc:
            QMessageBox.information(self, "Enclosing region", str(exc))

    def _import_region(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Import enclosing region mask", "",
                                                 "Mask images (*.png *.tif *.tiff *.bmp)")
        if not filename:
            return
        try:
            region = read_image_unicode(filename, cv2.IMREAD_UNCHANGED)
            if region is None:
                raise ValueError("Could not read this region mask.")
            if region.ndim == 3:
                region = np.any(region[:, :, :3] > 0, axis=2)
            self._set_region(region, f"Imported: {Path(filename).name}")
        except ValueError as exc:
            QMessageBox.information(self, "Import region mask", str(exc))

    def _toggle_drawing(self, enabled: bool) -> None:
        if not enabled:
            self._stop_drawing()
            self.export_button.setEnabled(self.result is not None and not self._analysis_pending)
            self.status_label.setText("Drawing cancelled. The previous region is preserved.")
            return
        if self._outline_axis is None:
            self.draw_button.setChecked(False)
            return
        if self.toolbar.mode:
            self.toolbar.pan() if "pan" in str(self.toolbar.mode).lower() else self.toolbar.zoom()
        self.draw_button.setText("Cancel drawing")
        self.status_label.setText("Click vertices around the region in the left image. Click the first vertex to finish.")
        self.export_button.setEnabled(False)
        self._polygon = PolygonSelector(self._outline_axis, self._polygon_selected,
                                         useblit=True, props={"color": "cyan", "linewidth": 2})
        self.canvas.setFocus()

    def _polygon_selected(self, vertices: list[tuple[float, float]]) -> None:
        region = np.zeros(self.mask.shape, dtype=np.uint8)
        points = np.rint(np.asarray(vertices)).astype(np.int32)
        if len(points) >= 3:
            cv2.fillPoly(region, [points], 1)
        if not region.any():
            self.status_label.setText("Draw a nonempty region with at least three vertices.")
            return
        self._set_region(region, "Drawn outline")

    def _stop_drawing(self) -> None:
        if self._polygon is not None:
            self._polygon.disconnect_events()
            self._polygon.set_visible(False)
            self._polygon = None
        self.draw_button.blockSignals(True)
        self.draw_button.setChecked(False)
        self.draw_button.setText("Draw outline")
        self.draw_button.blockSignals(False)

    def update_analysis(self) -> None:
        self._stop_drawing()
        self.export_button.setEnabled(False)
        try:
            self.result = analyze_spatial(
                self.mask, self.droplets, self.region,
                center_xy=(self.center_x.value(), self.center_y.value()),
                kernel_size=self.kernel_spin.value(), ring_count=self.rings_spin.value(),
                px_per_micron=self.scale_spin.value(), result_name=self.result_name,
            )
        except ValueError as exc:
            self.result = None
            self.status_label.setText(str(exc))
            return
        self.region_label.setText(self.region_source)
        summary = self.result.summary
        distance = summary["mean_distance_to_center_px"]
        distance_text = f"{distance:.2f} px" if distance is not None else "—"
        if distance is not None and self.result.px_per_micron > 0:
            distance_text += f" / {distance / self.result.px_per_micron:.2f} µm"
        self.summary_label.setText(
            f"Region: {summary['region_area_px2']:,} pixels² · "
            f"Droplets inside: {summary['droplet_count']} · "
            f"Coverage: {summary['coverage_percent']:.2f}% · Mean distance to center: {distance_text}"
        )
        self._populate_table(self.zones_table, self.result.rings)
        self._populate_table(self.distance_table, self.result.droplets)
        self._analysis_pending = False
        self._render()
        self.export_button.setEnabled(True)
        prefix = "Detections changed; measurements recalculated. " if getattr(self, "_restored_mask_changed", False) else ""
        self.status_label.setText(prefix + "Review the cyan outline, then export. Droplets are counted by centroid; coverage uses intersecting mask pixels.")

    @staticmethod
    def _populate_table(table: QTableWidget, values: pd.DataFrame) -> None:
        table.clear()
        table.setColumnCount(len(values.columns))
        table.setHorizontalHeaderLabels(list(values.columns))
        table.setRowCount(len(values))
        for row_index, row in enumerate(values.itertuples(index=False, name=None)):
            for column, value in enumerate(row):
                text = "—" if pd.isna(value) else f"{value:.4g}" if isinstance(value, float) else str(value)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()

    def _render(self, *_args) -> None:
        if self.result is None:
            return
        if self._polygon is not None:
            self._toggle_drawing(False)
        else:
            self._stop_drawing()
        self._outline_axis = draw_spatial_figure(
            self.figure, self.source, self.mask, self.result, self.metric_combo.currentData(), self.dark,
        )
        self.toolbar.update()
        self.canvas.draw_idle()

    def _export(self) -> None:
        if self.result is None or not self.export_button.isEnabled():
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            export_spatial(self.output_dir, self.result, self.mask, self.source, self.region_source,
                           {"manual_threshold": bool(self.outline_method.currentIndex()),
                            "threshold": self.threshold_spin.value(), "dark": self.dark_region.isChecked()})
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Spatial export", f"Could not export spatial results:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._restored_mask_changed = False
        self.status_label.setText(f"Spatial measurements, region mask, and heatmaps saved to {self.output_dir}")
        self.exported.emit(str(self.output_dir))

    def done(self, result: int) -> None:
        self._stop_drawing()
        super().done(result)
