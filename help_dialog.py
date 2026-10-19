from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from config import (
    DEFAULT_BACKGROUND_RADIUS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHECKPOINT,
    DEFAULT_DENSITY_KERNEL_SIZE,
    DEFAULT_MIN_AREA,
    DEFAULT_OUT_DIR,
    DEFAULT_PX_PER_MICRON,
    DEFAULT_RADIAL_BINS,
    DEFAULT_RESIZE_SIZE,
    DEFAULT_THRESHOLD,
    VALID_EXTS,
)


HELP_TOPICS: dict[str, tuple[str, str]] = {
    "quick_start": (
        "Quick Start",
        f"""
        <h1>Quick Start</h1>
        <p>Detect, measure, and review lipid droplets in microscopy images.
            Press <b>F1</b> to return to this guide from the main window.</p>
        <ol>
            <li><b>Load images.</b> Click <b>Open Image</b> for one file or
                <b>Open Folder</b> for all supported images directly inside a folder.
                Supported extensions: {', '.join(sorted(VALID_EXTS))}.</li>
            <li><b>Check the preview.</b> Click the current image name to choose
                another image. For a TIFF stack, use <b>Slice</b>, <b>Prev</b>,
                <b>Next</b>, or the slider to select a slice.</li>
            <li><b>Check Settings.</b> Select the trained UNetDC <b>.pth</b> file
                under <b>Checkpoint path</b>. Set <b>Pixels per micron</b> to
                your microscope calibration and choose the <b>TIFF stack mode</b>
                when working with stacks.</li>
            <li><b>Choose where to save.</b> Use
                <b>File &gt; Select Output Folder</b>. The default folder is
                <b>{DEFAULT_OUT_DIR}</b>.</li>
            <li><b>Run the analysis.</b> Click <b>Analyze</b>. Processing runs in
                the background; progress and error messages appear in the
                <b>Log</b> tab.</li>
            <li><b>Review detections.</b> Compare the original image, mask, and
                green overlay. Click <b>Labels</b> to give each droplet a different
                color in the middle panel. Open the <b>Droplets</b> tab to inspect measurements.
                Select a row to locate a droplet; use <b>Delete selected droplet</b>
                to remove an incorrect detection.</li>
            <li><b>Study spatial distribution (optional).</b> Open
                <b>Analysis &gt; Spatial Analysis...</b> to outline the surrounding
                region, inspect density, and measure distances to its center.
                Click <b>Export Spatial Results</b> to save these measurements.</li>
            <li><b>View and save results.</b> Click <b>Analysis Summary</b> for
                counts and size statistics or <b>Open Output</b> for exported files.
                After exporting any spatial results, click <b>Save Analysis</b>
                to include everything in a session you can reopen later.</li>
        </ol>
        <p>Keep <b>Save masks</b>, <b>Save overlays</b>, and
            <b>Run quantification automatically</b> enabled for a full review
            with measurements and deletion of incorrect detections.</p>
        <p>Use the <b>Labeling Guide</b> for colored droplet maps and the
            <b>Spatial Analysis</b> guide for region outlines, density, and distances.</p>
        """,
    ),
    "settings": (
        "Settings Guide",
        f"""
        <h1>Settings Guide</h1>
        <p>Open <b>Settings</b> from the toolbar or
            <b>Settings &gt; Open Settings</b>. Click <b>OK</b> to apply changes
            before the next analysis.</p>
        <h2>Detection and processing</h2>
        <ul>
            <li><b>Checkpoint path:</b> the trained UNetDC model file.
                The bundled model is <b>{DEFAULT_CHECKPOINT.name}</b>.</li>
            <li><b>Probability threshold:</b> pixels above this model probability
                become droplet pixels. Higher values give fewer detections;
                lower values include weaker signals and may include more noise.
                Default: <b>{DEFAULT_THRESHOLD:g}</b>.</li>
            <li><b>Minimum area:</b> removes connected objects smaller than this
                area in pixels squared, after the mask is resized back to the
                processed image dimensions. Default: <b>{DEFAULT_MIN_AREA}</b>.
                This filter runs before watershed separation.</li>
            <li><b>Batch size:</b> the number of images or slices processed together.
                Reduce it if memory runs out. Default: <b>{DEFAULT_BATCH_SIZE}</b>.</li>
            <li><b>Resize size:</b> the width and height used for model input.
                Default: <b>{DEFAULT_RESIZE_SIZE} &times; {DEFAULT_RESIZE_SIZE}</b>.
                Use a multiple of 16 for the UNetDC model.</li>
            <li><b>Background radius:</b> controls the size of the filter used to
                remove uneven background brightness. Use a positive value.
                Default: <b>{DEFAULT_BACKGROUND_RADIUS}</b>.</li>
            <li><b>Use watershed for droplet counting:</b> separates touching
                regions for labeling, counting, and measurement. It is enabled
                by default. Inspect the <b>Labels</b> view because separation can
                split one region into several droplets. Run <b>Analyze</b> again
                after changing this option.</li>
        </ul>
        <h2>Microscope calibration</h2>
        <p><b>Pixels per micron</b> converts pixels into physical units.
            Enter your microscope's calibration; the default
            <b>{DEFAULT_PX_PER_MICRON:g} pixels/&micro;m</b> is a starting value.</p>
        <p>If your metadata gives microns per pixel, enter its reciprocal.
            For example, 0.2 &micro;m/pixel means 5 pixels/&micro;m.
            Diameter in &micro;m = diameter in pixels / pixels per micron;
            area in &micro;m&sup2; = pixel area / (pixels per micron)&sup2;.
            Set this value to 0 to export measurements in pixels only.</p>
        <h2>Output options</h2>
        <ul>
            <li><b>Save masks:</b> writes black-and-white detection images,
                colored droplet maps, and numeric object labels.
                These files are needed to delete incorrect detections.</li>
            <li><b>Save overlays:</b> writes images with detected regions in green.
                The current exporter uses solid green; changing
                <b>Overlay alpha</b> does not change saved overlays.</li>
            <li><b>Run quantification automatically:</b> generates droplet
                measurements and summary tables after segmentation.
                Disable it to save segmentation images only.</li>
            <li><b>Generate Excel workbook:</b> exports droplet measurements
                and image summaries to an Excel file when quantification is enabled.</li>
            <li><b>TIFF stack mode</b> and <b>Segment TIFFs using PNG-style input:</b>
                see the TIFF Stack Guide for how these affect analysis.</li>
        </ul>
        """,
    ),
    "tiff_stacks": (
        "TIFF Stack Guide",
        f"""
        <h1>TIFF Stack Guide</h1>
        <p>TIFF files can contain one image or a stack of image slices.
            Select the analysis mode under <b>Settings &gt; TIFF stack mode</b>.</p>
        <ul>
            <li><b>Current slice</b> (default): analyzes the slice selected with
                the viewer's slice controls. In a folder run, the same selected
                slice index is used for each stack, limited to its available slices.</li>
            <li><b>All slices:</b> analyzes each slice separately and writes
                measurements for each one. A droplet visible in several slices
                can be counted several times. Measurements are 2D; this mode
                does not reconstruct 3D droplets or measure their volume.</li>
            <li><b>Max projection:</b> combines the brightest pixel at each
                position across the stack, then analyzes the resulting 2D image.
                Droplets from different slices may overlap in the projection.
                The model was trained on individual 2D images.</li>
        </ul>
        <h2>Preview and analysis mode</h2>
        <p>The viewer's <b>Slice</b> and <b>Projection</b> buttons change the
            preview. They do not change <b>TIFF stack mode</b> in Settings.
            Choose the mode in Settings before clicking <b>Analyze</b>.</p>
        <h2>PNG-style input</h2>
        <p><b>Segment TIFFs using PNG-style input</b> is enabled by default.
            It prepares TIFF images as 8-bit RGB inputs. For a single TIFF image
            or Current slice, it can use a PNG from the original input folder:
            a PNG with the same base name is preferred, otherwise the only eligible
            PNG in the folder is used. Check the <b>Log</b> for the reference folder
            and the results table for the PNG reference name.</p>
        <p>All slices uses each TIFF slice directly without a PNG reference.
            Max projection also uses the TIFF stack directly.</p>
        <p>For TIFF inputs processed without PNG-style input, the default
            probability threshold of <b>{DEFAULT_THRESHOLD:g}</b> is automatically
            replaced by <b>0.88</b>. A custom threshold is used as entered.</p>
        <h2>Result names</h2>
        <p>Slice results have names such as <b>sample_z000</b> (first slice)
            and <b>sample_z001</b> (second slice). The viewer displays slice numbers
            starting at 1. Projection results use <b>sample_maxproj</b>.
            A single-page TIFF uses its original base name.</p>
        """,
    ),
    "labeling": (
        "Labeling Guide",
        """
        <h1>Labeling Guide</h1>
        <p>Give each detected droplet its own color to inspect individual objects
            and check how touching droplets were separated.</p>
        <h2>Create and display the map</h2>
        <ol>
            <li>Open an image or folder, then open <b>Settings</b>.</li>
            <li>Enable <b>Save masks</b>. Enable
                <b>Run quantification automatically</b> for droplet measurements
                and selection of table rows.</li>
            <li>Choose whether to enable <b>Use watershed for droplet counting</b>,
                then click <b>OK</b> and <b>Analyze</b>.</li>
            <li>In <b>Image View</b>, click <b>Labels</b> beside <b>Mask</b>.
                The middle panel displays <b>Labeled droplets</b>.
                Click <b>Mask</b> to return to the black-and-white mask.</li>
        </ol>
        <h2>Read the colors and labels</h2>
        <p>Black is background. Each colored region is one labeled droplet.
            Its numeric ID matches the <b>label</b> column in the measurement
            table and CSV files. Colors identify objects within one image or
            slice; they do not encode size or intensity, and matching colors
            across slices do not establish that the objects are the same droplet.</p>
        <p><b>Watershed enabled:</b> touching regions can be separated into
            individual droplets with different colors. <b>Watershed disabled:</b>
            each connected region is one droplet. The label map and measurement
            table use the same object boundaries. Minimum area is applied to
            connected regions before watershed separation.</p>
        <h2>Inspect and correct a droplet</h2>
        <p>Click inside a colored droplet to select its exact row in the
            <b>Droplets</b> tab. Selecting a table row displays the matching image,
            slice, or projection. The Labels view stays selected while reviewing
            rows that have a label map.</p>
        <p>Click <b>Delete selected droplet</b> and confirm to remove the selected
            object. For results with saved labels, this removes only that labeled
            region, including when it touches another droplet. The remaining
            IDs and colors stay the same, so gaps in the label numbers are normal.</p>
        <p>Deletion updates the binary mask, colored and numeric label maps,
            overlay when available, and CSV measurements. See <b>Results and
            Export</b> for Excel files and spatial measurements after correction.</p>
        <h2>TIFF stacks</h2>
        <p>Choose an analyzed slice with <b>Slice</b> and the slice controls,
            or choose <b>Projection</b> for an analyzed maximum projection.
            Each result has its own label map and object IDs. The preview mode
            and the <b>TIFF stack mode</b> analysis setting are separate;
            see the <b>TIFF Stack Guide</b>.</p>
        <h2>Save and reopen labels</h2>
        <ul>
            <li><b>labeled_maps/*_labels.png:</b> a colored map for viewing or sharing.</li>
            <li><b>labeled_maps/*_labels.npy:</b> the numeric object map used for
                exact selection and correction. Background is 0; positive values
                match the droplet IDs.</li>
        </ul>
        <p>Both files are saved inside the output folder and included in
            <b>Save Analysis</b>. Keep the numeric label files with the analysis
            when continuing a review.</p>
        <h2>If Labels is unavailable</h2>
        <p>Enable <b>Save masks</b>, then analyze the image again. Older analyses
            need a new run to generate label maps. For TIFF stacks, select a
            slice or projection that was analyzed. If a label file is missing or
            does not match the saved mask, regenerate the result with Analyze.</p>
        <p>Colored maps are still created when automatic quantification is
            disabled, but no droplet measurement table is generated for selection.</p>
        """,
    ),
    "results": (
        "Results and Export",
        f"""
        <h1>Results and Export</h1>
        <h2>Inspect images and measurements</h2>
        <p><b>Image View</b> shows the original image, predicted mask, and overlay.
            White pixels in the mask and green pixels in the overlay are detected
            droplet regions. Use the zoom controls or <b>Fit</b> to inspect them.</p>
        <p><b>Labels</b> replaces the middle panel with a colored droplet map.
            Click a colored droplet to select its measurement row. See the
            <b>Labeling Guide</b> for object IDs, watershed separation, and correction.</p>
        <h2>Measurement tables</h2>
        <p><b>Analysis Summary</b> shows droplet counts and total detected area
            per image, plus the mean, median, and standard deviation of droplet
            diameters. Objects touching the image border or within the outer
            3-pixel margin are removed before measurement.</p>
        <p>The <b>Droplets</b> tab contains one row per measured droplet:</p>
        <ul>
            <li><b>filename:</b> source image, slice, or projection.</li>
            <li><b>label:</b> the droplet's identifier within that result.</li>
            <li><b>area:</b> the number of pixels belonging to the droplet.</li>
            <li><b>equivalent_diameter:</b> the diameter in pixels of a circle
                with the same area as the droplet.</li>
            <li><b>centroid-0 / centroid-1:</b> the droplet center's
                row (Y) / column (X) coordinates in the processed image.</li>
            <li><b>area_sqmicron / eq_diam_micron:</b> area in &micro;m&sup2;
                and diameter in &micro;m when Pixels per micron is positive.</li>
        </ul>
        <h2>Remove an incorrect detection</h2>
        <p>Select a row in <b>Droplets</b> to focus the viewer on that droplet.
            Click <b>Delete selected droplet</b> and confirm. Keep
            <b>Save masks</b> enabled when analyzing so the mask is available
            for correction.</p>
        <p>Deletion updates the mask, saved label maps, the saved overlay when
            available, droplet CSV files, image summaries, and size statistics.
            Existing Excel files
            and histogram images are not refreshed by deletion; use the updated
            CSV files for corrected measurements.</p>
        <p>Existing spatial measurements and heatmaps for this result are cleared
            after deletion. The enclosing region and its settings are preserved.
            Reopen <b>Spatial Analysis</b> and click <b>Export Spatial Results</b>
            to save updated measurements.</p>
        <h2>Exported files</h2>
        <p>Click <b>Open Output</b> to open the result folder. The default is
            <b>{DEFAULT_OUT_DIR}</b>. A single-image run saves under
            <b>single_runs/&lt;image-name&gt;</b> inside the chosen output folder.</p>
        <ul>
            <li><b>predicted_masks/*_pred.png:</b> detection masks.</li>
            <li><b>source_images/*.png:</b> the processed source images in the same
                coordinates as the saved masks, when Save masks is enabled.</li>
            <li><b>labeled_maps/*_labels.png:</b> colored droplet label maps.</li>
            <li><b>labeled_maps/*_labels.npy:</b> numeric object IDs; background is
                0, and positive IDs match the label column in the droplet CSV.</li>
            <li><b>overlays/*_overlay.png:</b> green detection overlays.</li>
            <li><b>*_droplets.csv:</b> measurements for one image or slice.</li>
            <li><b>all_droplets.csv:</b> combined droplet measurements.</li>
            <li><b>summary_per_image.csv:</b> counts and total area per image,
                including a TOTAL row.</li>
            <li><b>droplet_size_stats.csv:</b> mean, median, and standard deviation
                of diameter, in microns when calibrated or pixels otherwise.</li>
            <li><b>all_droplets.xlsx:</b> Excel workbook, when enabled.</li>
            <li><b>spatial_analysis/&lt;result-name&gt;/:</b> region masks,
                settings, CSV measurements, and PNG heatmaps after spatial export.</li>
        </ul>
        <p>Files depend on the output options enabled in Settings.
            Repeating an analysis in the same output folder can overwrite files
            with matching names. Choose a separate folder to keep each run.</p>
        <h2>Save and reopen an analysis</h2>
        <p>Click <b>Save Analysis</b> or <b>File &gt; Save Analysis As...</b>
            to save settings, tables, and result files in a <b>.joblib</b> file.
            Reopen it with <b>File &gt; Load Analysis...</b>.</p>
        <p>Original input images are referenced by their file paths. Keep them
            at the same location to view the originals when reopening an analysis.</p>
        <p>Colored labels and exported spatial files are included in the saved
            analysis. Export spatial results before saving the session to include
            the current region and measurements.</p>
        """,
    ),
    "spatial_analysis": (
        "Spatial Analysis",
        f"""
        <h1>Spatial Analysis</h1>
        <p>Analyze droplet distribution within an enclosing cell or tissue region.
            This tool works on one selected image, TIFF slice, or 2D projection.</p>
        <ol>
            <li>Run an analysis with <b>Save masks</b> and
                <b>Run quantification automatically</b> enabled.</li>
            <li>Select the image and analyzed slice or projection, then open
                <b>Analysis &gt; Spatial Analysis...</b> or click
                <b>Spatial Analysis</b> above the Droplets table.</li>
            <li><b>Review the enclosing region.</b> Cyan marks its boundary;
                green marks droplets; the red cross is the reference center.</li>
            <li>Choose the density window, number of concentric zones, and
                microscope calibration. Click <b>Update Analysis</b>.</li>
            <li>Choose a heatmap and review the zone and distance tables.
                Click <b>Export Spatial Results</b> to save them.</li>
        </ol>
        <h2>Define the region</h2>
        <p><b>Auto outline</b> thresholds image brightness, keeps the largest
            connected shape, and fills its holes. Use automatic thresholding
            or enter a manual intensity threshold. Select <b>Region is darker
            than background</b> when appropriate. The surrounding structure must
            be visible in the image; review the proposed outline.</p>
        <p><b>Draw outline:</b> click vertices around the region in the left image,
            then click the first vertex to finish. <b>Import region mask</b>
            accepts a black-and-white image with exactly the detection mask's
            dimensions; nonzero pixels are inside. <b>Use full image</b>
            includes the whole image. Imported masks are not resized: use the
            dimensions of the saved detection mask or source image.</p>
        <p>The reference center defaults to the mean position of the region's
            pixels. Edit <b>Center X (pixels)</b> and <b>Center Y (pixels)</b>
            to choose another point. <b>Use region center</b> restores the default.
            After changing measurements, click <b>Update Analysis</b> before export.</p>
        <p>The default <b>Density window (pixels)</b> is
            <b>{DEFAULT_DENSITY_KERNEL_SIZE}</b>; it must be odd and between 3 and
            1001 pixels. The default number of <b>Concentric zones</b> is
            <b>{DEFAULT_RADIAL_BINS}</b>, with 1 to 100 available.</p>
        <h2>What is measured?</h2>
        <ul>
            <li><b>Coverage:</b> detected droplet pixels inside the region divided
                by region pixels, expressed as a percentage.</li>
            <li><b>Counts:</b> droplets are included when their rounded centroid
                lies inside the region. Crossing droplets retain their whole
                measured area. Counts use the saved measurements, including
                watershed separation when it was enabled.</li>
            <li><b>Density window:</b> an odd square width in pixels. Each map
                value uses only the part of that window inside the region,
                including near the region and image boundaries.</li>
            <li><b>Heatmaps:</b> coverage, droplet count per 10,000 pixels squared,
                mean whole-droplet area at included centroids, or concentric zones.</li>
            <li><b>Concentric zones:</b> equally spaced radial intervals from
                the reference center to the farthest region pixel. Zone 1 is
                innermost. Their areas can differ. Each droplet belongs to its
                centroid pixel's zone; compare density or coverage when comparing
                regions of different area.</li>
            <li><b>Distances:</b> 2D Euclidean distances from each droplet centroid
                to the reference center. Rows outside the region remain in the
                export with <b>inside_region = False</b> and zone 0.</li>
        </ul>
        <p>Set <b>Pixels per micron</b> to your microscope calibration for physical
            area, density, and distance columns. Set it to 0 for pixel units only.
            Calibration in this window applies to spatial exports. Stack Z
            spacing and 3D distances are not included in this tool.</p>
        <h2>Exports and saved analyses</h2>
        <p>Files are saved under <b>spatial_analysis/&lt;result-name&gt;</b>
            inside the analysis output folder: <b>spatial_summary.csv</b>,
            <b>spatial_droplets.csv</b>, <b>spatial_rings.csv</b>, a region mask,
            settings, and four PNG previews with colorbars.</p>
        <p>Reopening the tool restores an exported outline and its settings.
            <b>Save Analysis</b> includes exported spatial files. New segmentation
            runs also save <b>source_images</b> so region outlines match the exact
            image used for detection. If an aligned original is unavailable in
            older results, draw or import a region instead.</p>
        <p>Deleting a droplet or rerunning segmentation clears the old spatial
            measurements and heatmaps while preserving your outline and settings.
            Reopen Spatial Analysis and export again to update the files.</p>
        """,
    ),
    "troubleshooting": (
        "Troubleshooting",
        """
        <h1>Troubleshooting</h1>
        <h2>Checkpoint file does not exist</h2>
        <p>Open <b>Settings</b>, click <b>Browse...</b> next to Checkpoint path,
            and select the trained UNetDC <b>.pth</b> model file.
            If the model fails to load, check the Log and use a checkpoint
            compatible with the UNetDC architecture.</p>
        <h2>No supported images found</h2>
        <p>Choose PNG, JPG, JPEG, TIF, or TIFF files. Folder analysis reads images
            directly inside the selected folder; it does not search subfolders.</p>
        <h2>No droplets detected, or too many detections</h2>
        <p>Check the original image and the TIFF analysis mode. For missing weak
            droplets, try lowering the <b>Probability threshold</b> or
            <b>Minimum area</b>. For excess noise, try raising them.
            Run the analysis again and inspect the mask and overlay.</p>
        <p>Objects touching or very near the image edge are removed automatically.
            For TIFF files, check the TIFF Stack Guide for PNG references and
            the automatic threshold change.</p>
        <h2>Sizes in microns look incorrect</h2>
        <p>Set <b>Pixels per micron</b> to the microscope calibration for these
            images. If the calibration is in microns per pixel, enter its
            reciprocal. Run the analysis again to recalculate measurements.</p>
        <h2>GPU memory error or slow processing</h2>
        <p>Reduce <b>Batch size</b>, for example to 1, and close other applications
            using GPU memory. A compatible CUDA GPU is used when available;
            CPU processing can take longer.</p>
        <h2>No summary or droplet table</h2>
        <p>Enable <b>Run quantification automatically</b> in Settings and analyze
            again. A completed segmentation-only run saves images without
            generating measurement tables.</p>
        <h2>Mask or overlay is unavailable</h2>
        <p>Enable <b>Save masks</b> and <b>Save overlays</b>, then analyze again.
            For TIFF stacks, select the analyzed slice or projection to inspect
            its matching results.</p>
        <h2>Cannot delete a droplet</h2>
        <p>Select a row in the <b>Droplets</b> tab first. Deletion requires a
            saved mask: enable <b>Save masks</b> and analyze again if it is missing.</p>
        <h2>Labels is disabled or a colored droplet has no table row</h2>
        <p>Enable <b>Save masks</b> and run <b>Analyze</b> again to create matching
            label maps. Older results and results with missing or inconsistent
            label files need regeneration. For TIFF files, select the analyzed
            slice or projection. To select rows, also enable
            <b>Run quantification automatically</b> before analysis.</p>
        <h2>Touching droplets have one color</h2>
        <p>Enable <b>Use watershed for droplet counting</b> and analyze again.
            Review the Labels view to check the separation; adjusting the
            probability threshold can also change which regions touch.</p>
        <h2>Spatial Analysis is unavailable</h2>
        <p>Run an analysis with <b>Save masks</b> and
            <b>Run quantification automatically</b> enabled. Select the analyzed
            image and slice or projection before opening
            <b>Analysis &gt; Spatial Analysis...</b>.</p>
        <h2>The enclosing region is incorrect or a region mask is rejected</h2>
        <p>Review the cyan outline. Adjust the automatic outline threshold or
            the dark-region option, draw a polygon, or import a region mask.
            Imported masks must be nonempty and match the saved detection mask's
            dimensions exactly; they are not resized automatically.</p>
        <h2>Spatial export is disabled or previous spatial files disappeared</h2>
        <p>After changing the center, density window, zones, or calibration,
            click <b>Update Analysis</b>. Use an odd density window size between
            3 and 1001 pixels. Finish or cancel drawing before export.</p>
        <p>Deleting detections or rerunning segmentation clears old spatial
            measurements while preserving the outline. Open Spatial Analysis,
            review the region, and export again to update the files.</p>
        <h2>Excel file is missing</h2>
        <p>Enable <b>Generate Excel workbook</b> and
            <b>Run quantification automatically</b>. Check the Log for an Excel
            export message. If Excel export is unavailable, use the CSV files.</p>
        <h2>An analysis fails or cannot be reopened</h2>
        <p>Read the last messages in the <b>Log</b> tab. Check that the input
            files and model exist and that the output folder is writable.
            To reopen a saved session, choose a <b>.joblib</b> file created with
            <b>Save Analysis</b>. Keep the original images at their saved paths.</p>
        <h2>Recent changes are missing from the application</h2>
        <p>Close and restart the app after updating its Python source. If you
            launch a packaged executable, rebuild it to include the updated
            interface and Help guides.</p>
        """,
    ),
}


class HelpDialog(QDialog):
    def __init__(self, topic_id: str = "quick_start", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resize(900, 640)
        self.setMinimumSize(640, 420)
        self.app_name = parent.windowTitle() if parent is not None else "Microscopy Analysis"
        self.topic_ids = tuple(HELP_TOPICS)

        self.heading = QLabel(f"{self.app_name} — User Guide")
        self.heading.setTextFormat(Qt.PlainText)
        self.heading.setWordWrap(True)
        self.heading.setStyleSheet("font-size: 18px; font-weight: 600; padding: 4px 0;")

        self.topic_list = QListWidget()
        self.topic_list.setAccessibleName("Help topics")
        self.topic_list.setMinimumWidth(180)
        self.topic_list.setMaximumWidth(220)
        self.topic_list.setWordWrap(True)
        self.topic_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.topic_list.addItems([title for title, _ in HELP_TOPICS.values()])

        self.content = QTextBrowser()
        self.content.setAccessibleName("Help guide")
        self.content.setOpenLinks(False)
        self.content.document().setDocumentMargin(16)
        self.content.document().setDefaultStyleSheet(
            "h1 { font-size: 22px; } h2 { font-size: 16px; margin-top: 20px; }"
            "p, li { margin-bottom: 10px; }"
        )

        body = QHBoxLayout()
        body.addWidget(self.topic_list)
        body.addWidget(self.content, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self.heading)
        root.addLayout(body, 1)
        root.addWidget(buttons)

        self.topic_list.currentRowChanged.connect(self._show_topic)
        selected_topic = topic_id if topic_id in HELP_TOPICS else "quick_start"
        self.topic_list.setCurrentRow(self.topic_ids.index(selected_topic))

    def _show_topic(self, index: int) -> None:
        if index < 0:
            return
        title, html = HELP_TOPICS[self.topic_ids[index]]
        self.setWindowTitle(f"{title} — {self.app_name} Help")
        self.content.setHtml(html)
        self.content.verticalScrollBar().setValue(0)
