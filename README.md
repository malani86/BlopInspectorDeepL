# Lipid Droplet Segmentation Application(segment_appV1)

A PySide6 desktop application for segmenting and quantifying lipid droplets in
microscopy images using a U-Net-dc model.

## Features

- Segment PNG, JPG, JPEG, TIFF, and TIFF stack images.
- Choose TIFF current slice, max projection, or all slices.
- Save predicted binary masks and green overlays.
- Quantify droplets into per-image CSV, combined CSV, and Excel reports.
- Show per-image summaries, total droplet count, and size statistics.
- Manually delete incorrect droplets after segmentation.
- Save and load analysis sessions as `.joblib` files.

## Project Structure

```text
segment_app/
├── main.py                      application entry point
├── main_window.py               main GUI window and user actions
├── controller.py                app state and run request management
├── backend.py                   command builder for batch segmentation
├── workers.py                   background process runner
├── quantify_droplets_batch.py   segmentation and quantification pipeline
├── preview_service.py           loads original/mask/overlay previews
├── imaging.py                   image and TIFF preview helpers
├── app_models.py                shared dataclasses and constants
├── config.py                    default settings
├── widgets.py                   reusable GUI widgets
├── models/                      neural network definitions
└── utils/                       training/preprocessing/metrics helpers
```

## Install

Create and activate a Python environment, then install the dependencies:

```bash
pip install -r requirements.txt
```

## Run the GUI

```bash
python segment_app/main.py
```

## Run the Batch Script Directly

```bash
python segment_app/quantify_droplets_batch.py \
  --img_dir path/to/images \
  --ckpt_path best_UNetDC_focal_model.pth \
  --out_dir quant_results \
  --save_overlays
```

For TIFF stacks, useful options are:

```bash
--tiff_mode current_slice
--tiff_mode max_projection
--tiff_mode all_slices
--tiff_as_png_style
```
## Rebuild on Windows

From the repository folder, with your application environment activated:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean segment_app.spec
```

The trained `best_UNetDC_focal_model.pth` and `icon.ico` must be in this folder.
Run `dist\segment_app\segment_app.exe`. Copy the **entire** `dist\segment_app`
folder when moving the application to another computer. You can create a desktop
shortcut to this executable. The batch worker runs through the same executable;
no separate batch executable is needed.

For a single-file executable instead:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name segment_app --icon icon.ico --add-data "best_UNetDC_focal_model.pth;." main.py
```

Build on Windows to produce a Windows executable. The model is bundled as a
read-only resource; results are saved outside the executable's temporary folder.

## Outputs

The analysis creates files such as:

```text
predicted_masks/*_pred.png
overlays/*_overlay.png
*_droplets.csv
all_droplets.csv
summary_per_image.csv
droplet_size_stats.csv
all_droplets.xlsx
size_histogram.png
```

## License Note

This project root includes an MIT license for original project files unless an
individual file says otherwise.


## Result folders and filenames

By default the GUI saves to `Documents/BlobInspector/results` in your home folder.
Use Select Output Folder to choose another location. Each run gets a short,
unique timestamp folder, for example `20261019_153000`; repeated runs keep the
previous results. The Open Output Folder action opens the current run directly.
Single-image and batch analyses use the same layout. Saved sessions default to
`saved_analyses` and restored sessions to `loaded_analyses` under the selected
results folder. Masks, source images, colored labels, overlays, CSV and Excel
reports retain their existing names. Spatial Analysis exports stay in
`spatial_analysis/<image_name>` inside the run folder.

Image reads and writes support accented names and `µ` on Windows. The app checks
that the output folder is writable before inference. Image writes use a temporary
file followed by replacement, and failures include the destination path.
CSV/Excel/plot exports use Python-aware paths already. If masks, overlays, Excel,
or quantification are disabled in Settings, those optional files are not created.
Keep the model and analysis settings used previously when comparing results.
