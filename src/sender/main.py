from __future__ import annotations

import csv
import json
import os
import socket
import ssl
import struct
import time
from pathlib import Path


def connect_tls(host: str, port: int, attempts: int = 120, delay_s: float = 1.0) -> ssl.SSLSocket:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            raw_sock = socket.create_connection((host, port), timeout=5)
            tls_sock = context.wrap_socket(raw_sock, server_hostname=host)
            return tls_sock
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_s)

    raise RuntimeError(f"Unable to connect to receiver {host}:{port}. Last error: {last_error}")


def send_message(sock: ssl.SSLSocket, header: dict, payload: bytes) -> None:
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    sock.sendall(struct.pack("!I", len(header_bytes)))
    sock.sendall(header_bytes)
    sock.sendall(struct.pack("!I", len(payload)))
    if payload:
        sock.sendall(payload)


def main() -> None:
    generated_dir = Path(os.getenv("GENERATED_DIR", "/app/data/generated"))
    log_dir = Path(os.getenv("LOG_DIR", "/app/data/logs"))
    receiver_host = os.getenv("RECEIVER_HOST", "stream-receiver")
    receiver_port = int(os.getenv("RECEIVER_PORT", "8443"))

    frames_dir = generated_dir / "frames"
    done_path = generated_dir / "generator.done"
    sender_done = generated_dir / "sender.done"
    sender_log = log_dir / "sender_log.csv"

    log_dir.mkdir(parents=True, exist_ok=True)
    if sender_log.exists():
        sender_log.unlink()
    if sender_done.exists():
        sender_done.unlink()

    with sender_log.open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.writer(log_file)
        writer.writerow(["send_ts_epoch", "frame_index", "payload_bytes"])

        sock = connect_tls(receiver_host, receiver_port)
        Path("/tmp/ready").write_text("ready\n", encoding="utf-8")

        with sock:
            frame_idx = 0
            while True:
                frame_path = frames_dir / f"frame_{frame_idx:06d}.jpg"

                if frame_path.exists():
                    payload = frame_path.read_bytes()
                    header = {
                        "type": "frame",
                        "frame_index": frame_idx,
                        "sent_at": time.time(),
                    }
                    send_message(sock, header, payload)
                    writer.writerow([f"{time.time():.6f}", frame_idx, len(payload)])
                    log_file.flush()
                    frame_idx += 1
                    continue

                if done_path.exists():
                    send_message(
                        sock,
                        {
                            "type": "eof",
                            "frame_index": frame_idx,
                            "sent_at": time.time(),
                        },
                        b"",
                    )
                    break

                time.sleep(0.05)

    sender_done.write_text("done\n", encoding="utf-8")


if __name__ == "__main__":
    main()