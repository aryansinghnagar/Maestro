#!/usr/bin/env python
"""Download script to fetch MediaPipe Hand Landmarker model file automatically."""

import sys
import urllib.request
from pathlib import Path

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
TARGET_DIR = Path(__file__).parent.parent / "gesture_controller" / "data"
TARGET_FILE = TARGET_DIR / "hand_landmarker.task"


def download_model() -> int:
    print(f"Checking MediaPipe model status...")
    if TARGET_FILE.exists():
        print(f"Model file hand_landmarker.task already exists at: {TARGET_FILE.absolute()}")
        return 0

    print(f"Downloading MediaPipe Hand Landmarker model from Google storage APIs...")
    print(f"Source: {MODEL_URL}")
    print(f"Destination: {TARGET_FILE.absolute()}")

    try:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)

        # Download with simple progress reporting
        def progress_hook(count, block_size, total_size):
            progress = count * block_size
            percent = min(100, int(progress * 100 / total_size))
            sys.stdout.write(
                f"\rDownloading... {percent}% ({progress // 1024} KB / {total_size // 1024} KB)"
            )
            sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, str(TARGET_FILE), reporthook=progress_hook)
        print("\nDownload complete successfully!")
        return 0
    except Exception as e:
        print(f"\nFailed to download MediaPipe Hand Landmarker model: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(download_model())
