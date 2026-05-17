import math
import unittest

from datasheet2spice.extractors.raster_digitizer import digitize_raster_curve_from_image


class RasterDigitizerTests(unittest.TestCase):
    def test_digitizes_calibrated_log_log_raster_curve(self):
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            self.skipTest(f"Pillow not installed: {exc}")

        x_range = (0.1, 1000.0)
        y_range = (1.0, 100000.0)
        plot_rect = (52, 24, 620, 380)
        image = Image.new("RGB", (660, 420), "white")
        draw = ImageDraw.Draw(image)
        left, top, right, bottom = plot_rect

        for i in range(5):
            x = left + (right - left) * i / 4
            draw.line([(x, top), (x, bottom)], fill=(220, 220, 220), width=1)
        for i in range(6):
            y = top + (bottom - top) * i / 5
            draw.line([(left, y), (right, y)], fill=(220, 220, 220), width=1)
        draw.line([(left, top), (left, bottom), (right, bottom)], fill=(0, 0, 0), width=2)

        def curve(x_value: float) -> float:
            return 82000.0 / (1.0 + (x_value / 0.32) ** 0.74) + 8.0

        def x_to_px(x_value: float) -> float:
            t = (math.log10(x_value) - math.log10(x_range[0])) / (math.log10(x_range[1]) - math.log10(x_range[0]))
            return left + t * (right - left)

        def y_to_px(y_value: float) -> float:
            t = (math.log10(y_value) - math.log10(y_range[0])) / (math.log10(y_range[1]) - math.log10(y_range[0]))
            return bottom - t * (bottom - top)

        samples = [0.1 * (10000.0 ** (idx / 220)) for idx in range(221)]
        polyline = [(x_to_px(x), y_to_px(curve(x))) for x in samples]
        draw.line(polyline, fill=(0, 0, 0), width=3)

        x_values = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0, 100.0, 500.0]
        result = digitize_raster_curve_from_image(
            image,
            plot_rect_px=plot_rect,
            curve_name="coss_pf",
            y_unit="pF",
            x_range=x_range,
            y_range=y_range,
            x_values=x_values,
            threshold=90,
        )

        self.assertGreaterEqual(result["metrics"]["coverage"], 0.9)
        self.assertGreater(result["confidence"], 0.75)
        extracted = {point["x"]: point["y"] for point in result["points"]}
        relative_errors = [abs(extracted[x] - curve(x)) / curve(x) for x in extracted]
        self.assertLess(max(relative_errors), 0.25)


if __name__ == "__main__":
    unittest.main()
