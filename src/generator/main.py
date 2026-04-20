from __future__ import annotations

import csv
import math
import os
import time
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def compute_stimulus(stimulus_cfg: dict, t_s: float, total_duration: float) -> dict:
    stim_type = str(stimulus_cfg.get("type", "baseline_static"))
    start_time = float(stimulus_cfg.get("start_time", 0.0))
    stop_time = float(stimulus_cfg.get("stop_time", total_duration))
    active_window = start_time <= t_s <= stop_time

    area_percent = float(stimulus_cfg.get("changed_area_percent", 0.0))
    region_count = int(stimulus_cfg.get("region_count", 1))
    brightness = float(stimulus_cfg.get("brightness_level", 1.0))
    bit_value = 0

    if stim_type == "baseline_static":
        active_window = False

    elif stim_type == "area_sweep" and active_window:
        progress = (t_s - start_time) / max(stop_time - start_time, 1e-6)
        area_percent = 2.0 + 78.0 * progress

    elif stim_type == "fragmentation_sweep" and active_window:
        levels = [1, 2, 4, 8, 16, 32]
        progress = (t_s - start_time) / max(stop_time - start_time, 1e-6)
        level_idx = min(len(levels) - 1, int(progress * len(levels)))
        region_count = levels[level_idx]
        area_percent = max(area_percent, 20.0)

    elif stim_type == "brightness_sweep" and active_window:
        progress = (t_s - start_time) / max(stop_time - start_time, 1e-6)
        brightness = 0.2 + 0.8 * progress
        area_percent = max(area_percent, 25.0)
        region_count = max(region_count, 8)

    elif stim_type == "watermark_pattern":
        pattern = str(stimulus_cfg.get("binary_pattern", "10110011"))
        window_ms = int(stimulus_cfg.get("window_ms", 1000))
        window_s = window_ms / 1000.0
        bit_value = 0

        if active_window and pattern and window_s > 0:
            bit_index = int((t_s - start_time) / window_s)
            if 0 <= bit_index < len(pattern):
                bit_value = 1 if pattern[bit_index] == "1" else 0
            active_window = bit_value == 1
        else:
            active_window = False

        area_percent = max(area_percent, 25.0)
        region_count = max(region_count, 8)

    area_percent = float(np.clip(area_percent, 0.0, 100.0))
    region_count = max(1, region_count)
    brightness = float(np.clip(brightness, 0.0, 1.0))

    flicker = int(t_s * 4.0) % 2 == 0
    stimulus_on = int(active_window and flicker)

    return {
        "stimulus_on": stimulus_on,
        "bit_value": bit_value,
        "changed_area_percent": area_percent,
        "region_count": region_count,
        "brightness_level": brightness,
    }


def draw_regions(
    image: Image.Image,
    frame_idx: int,
    changed_area_percent: float,
    region_count: int,
    brightness_level: float,
) -> None:
    width, height = image.size
    draw = ImageDraw.Draw(image)

    total_pixels = width * height
    changed_pixels = int(total_pixels * (changed_area_percent / 100.0))
    if changed_pixels <= 0:
        return

    pixels_per_region = max(1, changed_pixels // max(region_count, 1))
    side = max(1, int(math.sqrt(pixels_per_region)))
    side = min(side, width, height)

    color_value = int(255 * brightness_level)
    color = (color_value, color_value, color_value)

    rng = np.random.default_rng(seed=frame_idx)

    for _ in range(region_count):
        x0 = int(rng.integers(0, max(1, width - side + 1)))
        y0 = int(rng.integers(0, max(1, height - side + 1)))
        draw.rectangle((x0, y0, x0 + side, y0 + side), fill=color)


def main() -> None:
    generated_dir = Path(os.getenv("GENERATED_DIR", "/app/data/generated"))
    log_dir = Path(os.getenv("LOG_DIR", "/app/data/logs"))
    config_path = Path(os.getenv("EXPERIMENT_CONFIG", "/app/configs/experiments/baseline.yaml"))

    config = load_yaml(config_path)
    video_cfg = config.get("video", {})
    stimulus_cfg = config.get("stimulus", {})

    width = int(video_cfg.get("width", os.getenv("WIDTH", 640)))
    height = int(video_cfg.get("height", os.getenv("HEIGHT", 360)))
    fps = float(video_cfg.get("fps", os.getenv("FPS", 15)))
    duration_s = float(video_cfg.get("duration_seconds", os.getenv("TRIAL_DURATION", 90)))
    jpeg_quality = int(video_cfg.get("jpeg_quality", os.getenv("JPEG_QUALITY", 85)))

    frame_count = max(1, int(duration_s * fps))
    frame_interval_s = 1.0 / max(fps, 1.0)

    frames_dir = generated_dir / "frames"
    metadata_path = generated_dir / "frame_metadata.csv"
    done_path = generated_dir / "generator.done"

    frames_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    for old_frame in frames_dir.glob("*.jpg"):
        old_frame.unlink()
    for old_file in [metadata_path, done_path, log_dir / "generator.log"]:
        if old_file.exists():
            old_file.unlink()

    Path("/tmp/ready").write_text("ready\n", encoding="utf-8")

    with metadata_path.open("w", newline="", encoding="utf-8") as metadata_file:
        writer = csv.writer(metadata_file)
        writer.writerow(
            [
                "frame_index",
                "frame_ts_epoch",
                "relative_time_s",
                "stimulus_on",
                "bit_value",
                "changed_area_percent",
                "region_count",
                "brightness_level",
                "file_name",
                "payload_bytes",
            ]
        )

        start_epoch = time.time()
        for frame_idx in range(frame_count):
            frame_ts = time.time()
            relative_t = frame_idx * frame_interval_s

            stimulus = compute_stimulus(stimulus_cfg, relative_t, duration_s)

            background = (236, 236, 236)
            image = Image.new("RGB", (width, height), background)

            if stimulus["stimulus_on"]:
                draw_regions(
                    image=image,
                    frame_idx=frame_idx,
                    changed_area_percent=stimulus["changed_area_percent"],
                    region_count=stimulus["region_count"],
                    brightness_level=stimulus["brightness_level"],
                )

            frame_name = f"frame_{frame_idx:06d}.jpg"
            frame_path = frames_dir / frame_name
            image.save(frame_path, format="JPEG", quality=jpeg_quality)
            payload_bytes = frame_path.stat().st_size

            writer.writerow(
                [
                    frame_idx,
                    f"{frame_ts:.6f}",
                    f"{relative_t:.6f}",
                    stimulus["stimulus_on"],
                    stimulus["bit_value"],
                    f"{stimulus['changed_area_percent']:.4f}",
                    stimulus["region_count"],
                    f"{stimulus['brightness_level']:.4f}",
                    frame_name,
                    payload_bytes,
                ]
            )
            metadata_file.flush()

            elapsed = time.time() - start_epoch
            target = (frame_idx + 1) * frame_interval_s
            sleep_s = max(0.0, target - elapsed)
            if sleep_s > 0:
                time.sleep(sleep_s)

    done_path.write_text("done\n", encoding="utf-8")


if __name__ == "__main__":
    main()