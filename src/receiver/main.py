from __future__ import annotations

import csv
import json
import os
import socket
import ssl
import struct
import time
from pathlib import Path


def recv_exact(sock: ssl.SSLSocket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Socket closed while receiving data")
        data.extend(chunk)
    return bytes(data)


def main() -> None:
    received_dir = Path(os.getenv("RECEIVED_DIR", "/app/data/received"))
    log_dir = Path(os.getenv("LOG_DIR", "/app/data/logs"))
    cert_path = Path(os.getenv("TLS_CERT_PATH", "/app/certs/server.crt"))
    key_path = Path(os.getenv("TLS_KEY_PATH", "/app/certs/server.key"))
    receiver_port = int(os.getenv("RECEIVER_PORT", "8443"))

    frames_out = received_dir / "frames"
    receiver_done = received_dir / "receiver.done"
    receiver_log = log_dir / "receiver_log.csv"

    received_dir.mkdir(parents=True, exist_ok=True)
    frames_out.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    for old_frame in frames_out.glob("*.jpg"):
        old_frame.unlink()
    for old_file in [receiver_done, receiver_log]:
        if old_file.exists():
            old_file.unlink()

    if not cert_path.exists() or not key_path.exists():
        raise FileNotFoundError(
            "TLS certificate files are missing. Run scripts/host/generate_certs.sh first."
        )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", receiver_port))
        server_sock.listen(1)
        Path("/tmp/ready").write_text("ready\n", encoding="utf-8")

        with receiver_log.open("w", newline="", encoding="utf-8") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(["recv_ts_epoch", "frame_index", "payload_bytes", "message_type"])

            conn, _ = server_sock.accept()
            with context.wrap_socket(conn, server_side=True) as tls_conn:
                while True:
                    try:
                        header_len = struct.unpack("!I", recv_exact(tls_conn, 4))[0]
                        if header_len <= 0:
                            break
                        header_raw = recv_exact(tls_conn, header_len)
                        payload_len = struct.unpack("!I", recv_exact(tls_conn, 4))[0]
                        payload = recv_exact(tls_conn, payload_len) if payload_len else b""
                    except ConnectionError:
                        break

                    header = json.loads(header_raw.decode("utf-8"))
                    msg_type = str(header.get("type", "frame"))
                    frame_index = int(header.get("frame_index", -1))

                    writer.writerow([f"{time.time():.6f}", frame_index, len(payload), msg_type])
                    log_file.flush()

                    if msg_type == "eof":
                        break

                    out_name = f"frame_{frame_index:06d}.jpg"
                    (frames_out / out_name).write_bytes(payload)

    receiver_done.write_text("done\n", encoding="utf-8")


if __name__ == "__main__":
    main()