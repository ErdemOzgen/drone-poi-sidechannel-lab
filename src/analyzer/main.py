from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def safe_float(value: float) -> str:
    if np.isnan(value):
        return "nan"
    return f"{value:.6f}"


def main() -> None:
    generated_dir = Path(os.getenv("GENERATED_DIR", "/app/data/generated"))
    log_dir = Path(os.getenv("LOG_DIR", "/app/data/logs"))
    metrics_dir = Path(os.getenv("METRICS_DIR", "/app/data/metrics"))
    reports_dir = Path(os.getenv("REPORTS_DIR", "/app/data/reports"))
    experiment_id = os.getenv("EXPERIMENT_ID", "baseline-local")

    metadata_path = generated_dir / "frame_metadata.csv"
    sender_log_path = log_dir / "sender_log.csv"

    metrics_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata file: {metadata_path}")
    if not sender_log_path.exists():
        raise FileNotFoundError(f"Missing sender log: {sender_log_path}")

    metadata = pd.read_csv(metadata_path)
    sender = pd.read_csv(sender_log_path)

    merged = sender.merge(metadata, on="frame_index", how="inner")
    if merged.empty:
        raise RuntimeError("No overlapping rows between sender log and frame metadata")

    merged["time_bucket_s"] = np.floor(merged["relative_time_s"]).astype(int)

    timeseries = (
        merged.groupby("time_bucket_s", as_index=False)
        .agg(
            payload_bytes=("payload_bytes_x", "sum"),
            stimulus_ratio=("stimulus_on", "mean"),
            avg_changed_area_percent=("changed_area_percent", "mean"),
        )
        .sort_values("time_bucket_s")
    )

    frame_corr = np.nan
    if merged["stimulus_on"].nunique() > 1 and merged["payload_bytes_x"].nunique() > 1:
        frame_corr = merged["stimulus_on"].corr(merged["payload_bytes_x"])

    on_mask = merged["stimulus_on"] == 1
    avg_on = float(merged.loc[on_mask, "payload_bytes_x"].mean()) if on_mask.any() else np.nan
    avg_off = float(merged.loc[~on_mask, "payload_bytes_x"].mean()) if (~on_mask).any() else np.nan

    delta_pct = np.nan
    if not np.isnan(avg_on) and not np.isnan(avg_off) and avg_off != 0:
        delta_pct = ((avg_on - avg_off) / avg_off) * 100.0

    timeseries_path = metrics_dir / "traffic_timeseries.csv"
    timeseries.to_csv(timeseries_path, index=False)

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(timeseries["time_bucket_s"], timeseries["payload_bytes"], label="bytes/sec", color="#0b3c5d")
    ax1.set_xlabel("time (s)")
    ax1.set_ylabel("payload bytes/sec", color="#0b3c5d")

    ax2 = ax1.twinx()
    ax2.plot(
        timeseries["time_bucket_s"],
        timeseries["stimulus_ratio"],
        label="stimulus ratio",
        color="#e67e22",
        alpha=0.7,
    )
    ax2.set_ylabel("stimulus ratio [0..1]", color="#e67e22")

    fig.suptitle(f"Encrypted Traffic vs Stimulus - {experiment_id}")
    fig.tight_layout()

    plot_path = reports_dir / "stimulus_overlay.png"
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)

    report_path = reports_dir / "final_report.md"
    with report_path.open("w", encoding="utf-8") as report:
        report.write(f"# Experiment Report: {experiment_id}\n\n")
        report.write("## Summary\n\n")
        report.write(f"- Frames sent: {int(len(sender))}\n")
        report.write(f"- Frames analyzed: {int(len(merged))}\n")
        report.write(f"- Avg frame bytes (stimulus on): {safe_float(avg_on)}\n")
        report.write(f"- Avg frame bytes (stimulus off): {safe_float(avg_off)}\n")
        report.write(f"- Delta on vs off (%): {safe_float(delta_pct)}\n")
        report.write(f"- Correlation(stimulus_on, frame_bytes): {safe_float(frame_corr)}\n")
        report.write("\n## Outputs\n\n")
        report.write(f"- Timeseries CSV: {timeseries_path}\n")
        report.write(f"- Overlay plot: {plot_path}\n")

    print(f"[analyzer] Wrote {timeseries_path}")
    print(f"[analyzer] Wrote {plot_path}")
    print(f"[analyzer] Wrote {report_path}")


if __name__ == "__main__":
    main()