# Raster Plot Digitization

Scanned datasheets and bitmap-only PDF plots cannot be handled reliably by PDF
vector extraction. The v1 workflow therefore uses a calibrated raster pipeline:

1. Prefer text, table, and vector extraction when available.
2. Render the target PDF page or plot region to a high-resolution bitmap.
3. Calibrate the plot with page number, plot rectangle, axis ranges, and
   log/linear axis modes.
4. Segment dark curve pixels with a tunable grayscale threshold.
5. Suppress long horizontal and vertical pixel runs, which are usually axes or
   grid lines.
6. Trace each requested X position by choosing the nearest continuous Y run.
7. Return points, pixel coordinates, coverage, gap count, and confidence for
   human review.

This is intentionally semi-automatic. It is more reliable to ask for a small
amount of calibration than to silently guess axes from a scanned image. The GUI
lets reviewers fill the page and plot rectangle from rendered evidence images,
then run the raster digitizer for one curve at a time.

## API

The local workbench exposes:

```http
POST /api/raster-digitize
```

Example request:

```json
{
  "session": "<upload-session>",
  "filename": "device.pdf",
  "page": 11,
  "plot_rect": [120, 180, 420, 360],
  "curve_name": "coss_pf",
  "x_range": [0.1, 1000],
  "y_range": [1, 100000],
  "threshold": 110,
  "initial_y_fraction": null
}
```

The response includes:

- `points`: calibrated X/Y values plus original pixel coordinates.
- `confidence`: a coverage/continuity score for review triage.
- `metrics`: requested point count, extracted point count, gaps, threshold, and
  dark-pixel fraction.

## Reliability Notes

- Use the tightest possible plot rectangle. A large crop that includes legends,
  labels, or neighboring charts reduces confidence.
- For multi-curve plots, digitize one curve at a time. A future UI should add
  click-based seed points or color selection for `Ciss`, `Coss`, and `Crss`.
- If the scan has colored curves, use a curve-color segmenter before dark-pixel
  tracing. The current v1 path is optimized for black datasheet traces.
- OCR should be used as an assistant for axis tick suggestions, not as the sole
  source of calibration. Manual confirmation remains the reliable path.
