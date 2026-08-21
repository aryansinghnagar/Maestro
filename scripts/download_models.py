#!/usr/bin/env python
"""Download script to fetch MediaPipe Hand Landmarker model file automatically with integrity check."""

import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
EXPECTED_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
TARGET_DIR = Path(__file__).parent.parent / "gesture_controller" / "data"
TARGET_FILE = TARGET_DIR / "hand_landmarker.task"


def verify_sha256(file_path: Path, expected_hash: str) -> bool:
    """Calculate and compare SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()
    return actual_hash.lower() == expected_hash.lower()


def download_model() -> int:
    print("Checking MediaPipe model status...")
    if TARGET_FILE.exists():
        if verify_sha256(TARGET_FILE, EXPECTED_SHA256):
            print(
                f"Model file hand_landmarker.task already exists and verified at: {TARGET_FILE.absolute()}"
            )
            return 0
        print("Existing model failed SHA-256 verification. Re-downloading...")

    print("Downloading MediaPipe Hand Landmarker model from Google storage APIs...")
    print(f"Source: {MODEL_URL}")
    print(f"Destination: {TARGET_FILE.absolute()}")

    try:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(delete=False, dir=TARGET_DIR, suffix=".tmp") as tmp_file:
            tmp_path = Path(tmp_file.name)

        def progress_hook(count: int, block_size: int, total_size: int) -> None:
            progress = count * block_size
            percent = min(100, int(progress * 100 / total_size)) if total_size > 0 else 0
            sys.stdout.write(
                f"\rDownloading... {percent}% ({progress // 1024} KB / {max(1, total_size // 1024)} KB)"
            )
            sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, str(tmp_path), reporthook=progress_hook)
        print("\nDownload finished. Verifying SHA-256 integrity...")

        if not verify_sha256(tmp_path, EXPECTED_SHA256):
            tmp_path.unlink(missing_ok=True)
            print("ERROR: Downloaded model SHA-256 checksum mismatch! Aborting.")
            return 1

        tmp_path.replace(TARGET_FILE)
        print("Model verified and installed successfully!")
        return 0
    except Exception as e:
        print(f"\nFailed to download MediaPipe Hand Landmarker model: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(download_model())
