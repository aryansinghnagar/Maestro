import pytest
import shutil
import tempfile
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication

from securesystemslib.signer import CryptoSigner
from tuf.api.metadata import (
    Metadata,
    Root,
    Timestamp,
    Snapshot,
    Targets,
    TargetFile,
    Key,
    Role,
    MetaFile,
)
from gesture_controller.core.updater import UpdateCheckerThread, LocalFileFetcher


@pytest.fixture
def temp_tuf_env():
    temp_dir = Path(tempfile.mkdtemp())
    repo_dir = temp_dir / "repo"
    client_dir = temp_dir / "client"
    repo_dir.mkdir()
    client_dir.mkdir()

    # Generate keys
    root_signer = CryptoSigner.generate_ed25519()
    targets_signer = CryptoSigner.generate_ed25519()
    snapshot_signer = CryptoSigner.generate_ed25519()
    timestamp_signer = CryptoSigner.generate_ed25519()

    root_key = Key.from_dict(root_signer.public_key.keyid, root_signer.public_key.to_dict())
    targets_key = Key.from_dict(
        targets_signer.public_key.keyid, targets_signer.public_key.to_dict()
    )
    snapshot_key = Key.from_dict(
        snapshot_signer.public_key.keyid, snapshot_signer.public_key.to_dict()
    )
    timestamp_key = Key.from_dict(
        timestamp_signer.public_key.keyid, timestamp_signer.public_key.to_dict()
    )

    expiry = datetime.now(timezone.utc) + timedelta(days=365)
    root = Root(
        version=1,
        spec_version="1.0.3",
        expires=expiry,
        keys={
            root_key.keyid: root_key,
            targets_key.keyid: targets_key,
            snapshot_key.keyid: snapshot_key,
            timestamp_key.keyid: timestamp_key,
        },
        roles={
            "root": Role([root_key.keyid], 1),
            "targets": Role([targets_key.keyid], 1),
            "snapshot": Role([snapshot_key.keyid], 1),
            "timestamp": Role([timestamp_key.keyid], 1),
        },
    )

    root_meta = Metadata(root)
    root_meta.sign(root_signer)
    root_json_bytes = json.dumps(root_meta.to_dict()).encode("utf-8")

    with open(repo_dir / "root.json", "wb") as f:
        f.write(root_json_bytes)
    with open(repo_dir / "1.root.json", "wb") as f:
        f.write(root_json_bytes)

    yield {
        "repo_dir": repo_dir,
        "client_dir": client_dir,
        "root_json_bytes": root_json_bytes,
        "targets_signer": targets_signer,
        "snapshot_signer": snapshot_signer,
        "timestamp_signer": timestamp_signer,
        "expiry": expiry,
    }

    shutil.rmtree(temp_dir)


def write_tuf_metadata(env, target_filename, target_version, target_url):
    repo_dir = env["repo_dir"]
    targets_signer = env["targets_signer"]
    snapshot_signer = env["snapshot_signer"]
    timestamp_signer = env["timestamp_signer"]
    expiry = env["expiry"]

    target_data = b"dummy content"
    with open(repo_dir / target_filename, "wb") as f:
        f.write(target_data)

    target_hash = hashlib.sha256(target_data).hexdigest()
    tf = TargetFile(
        length=len(target_data),
        hashes={"sha256": target_hash},
        path=target_filename,
        unrecognized_fields={"custom": {"version": target_version, "release_url": target_url}},
    )

    targets = Targets(
        version=1, spec_version="1.0.3", expires=expiry, targets={target_filename: tf}
    )
    targets_meta = Metadata(targets)
    targets_meta.sign(targets_signer)
    targets_json_bytes = json.dumps(targets_meta.to_dict()).encode("utf-8")

    with open(repo_dir / "targets.json", "wb") as f:
        f.write(targets_json_bytes)
    with open(repo_dir / "1.targets.json", "wb") as f:
        f.write(targets_json_bytes)

    snapshot = Snapshot(
        version=1,
        spec_version="1.0.3",
        expires=expiry,
        meta={
            "targets.json": MetaFile(
                version=1,
                length=len(targets_json_bytes),
                hashes={"sha256": hashlib.sha256(targets_json_bytes).hexdigest()},
            )
        },
    )
    snapshot_meta = Metadata(snapshot)
    snapshot_meta.sign(snapshot_signer)
    snapshot_json_bytes = json.dumps(snapshot_meta.to_dict()).encode("utf-8")

    with open(repo_dir / "snapshot.json", "wb") as f:
        f.write(snapshot_json_bytes)
    with open(repo_dir / "1.snapshot.json", "wb") as f:
        f.write(snapshot_json_bytes)

    timestamp = Timestamp(
        version=1,
        spec_version="1.0.3",
        expires=expiry,
        snapshot_meta=MetaFile(
            version=1,
            length=len(snapshot_json_bytes),
            hashes={"sha256": hashlib.sha256(snapshot_json_bytes).hexdigest()},
        ),
    )
    timestamp_meta = Metadata(timestamp)
    timestamp_meta.sign(timestamp_signer)
    timestamp_json_bytes = json.dumps(timestamp_meta.to_dict()).encode("utf-8")

    with open(repo_dir / "timestamp.json", "wb") as f:
        f.write(timestamp_json_bytes)


def test_updater_is_newer() -> None:
    updater = UpdateCheckerThread("0.1.0")

    # Standard comparisons
    assert updater._is_newer("1.0.0", "0.1.0") is True
    assert updater._is_newer("0.1.1", "0.1.0") is True
    assert updater._is_newer("0.2.0", "0.1.5") is True
    assert updater._is_newer("0.1.0", "0.1.0") is False
    assert updater._is_newer("0.0.9", "0.1.0") is False

    # Version string format differences
    assert updater._is_newer("1.0.0.0", "1.0.0") is False
    assert updater._is_newer("1.0", "1.0.0") is False

    # Value error fallbacks
    assert updater._is_newer("abc", "1.0.0") is False


def test_updater_network_check_success(temp_tuf_env, qapp: QApplication) -> None:
    # Setup TUF metadata pointing to a newer version
    repo_url = temp_tuf_env["repo_dir"].as_uri() + "/"
    write_tuf_metadata(temp_tuf_env, "maestro-2.0.0.exe", "2.0.0", "https://github.com/tag/v2.0.0")

    updater = UpdateCheckerThread(
        current_version="0.1.0",
        metadata_url=repo_url,
        targets_url=repo_url,
        cache_dir=temp_tuf_env["client_dir"],
        bootstrap_root=temp_tuf_env["root_json_bytes"],
    )

    updates = []
    updater.update_available.connect(lambda v, url: updates.append((v, url)))

    updater.run()

    assert len(updates) == 1
    assert updates[0][0] == "2.0.0"
    assert updates[0][1] == "https://github.com/tag/v2.0.0"


def test_updater_network_check_no_update(temp_tuf_env, qapp: QApplication) -> None:
    # Setup TUF metadata pointing to an older version than current version
    repo_url = temp_tuf_env["repo_dir"].as_uri() + "/"
    write_tuf_metadata(temp_tuf_env, "maestro-0.9.0.exe", "0.9.0", "https://github.com/tag/v0.9.0")

    updater = UpdateCheckerThread(
        current_version="1.0.0",
        metadata_url=repo_url,
        targets_url=repo_url,
        cache_dir=temp_tuf_env["client_dir"],
        bootstrap_root=temp_tuf_env["root_json_bytes"],
    )

    updates = []
    updater.update_available.connect(lambda v, url: updates.append((v, url)))

    updater.run()

    assert len(updates) == 0


def test_updater_network_check_failure(temp_tuf_env, qapp: QApplication) -> None:
    repo_url = temp_tuf_env["repo_dir"].as_uri() + "/"

    # Intentionally corrupt the bootstrap root by signing with a different key
    bad_signer = CryptoSigner.generate_ed25519()
    bad_root_meta = Metadata(
        Root(
            version=1,
            spec_version="1.0.3",
            expires=datetime.now(timezone.utc) + timedelta(days=365),
            keys={},
            roles={
                "root": Role([], 1),
                "targets": Role([], 1),
                "snapshot": Role([], 1),
                "timestamp": Role([], 1),
            },
        )
    )
    bad_root_meta.sign(bad_signer)
    bad_root_bytes = json.dumps(bad_root_meta.to_dict()).encode("utf-8")

    updater = UpdateCheckerThread(
        current_version="0.1.0",
        metadata_url=repo_url,
        targets_url=repo_url,
        cache_dir=temp_tuf_env["client_dir"],
        bootstrap_root=bad_root_bytes,
    )

    errors = []
    updater.error.connect(lambda e: errors.append(e))

    updater.run()

    assert len(errors) == 1
    assert any(
        word in errors[0]
        for word in ["RepositoryError", "UnsignedMetadataError", "Signature", "signed by", "keys"]
    )


def test_tuf_threshold_3() -> None:
    """Verify default BOOTSTRAP_ROOT has threshold=3 for root/targets."""
    from gesture_controller.core.updater import BOOTSTRAP_ROOT

    root_role = BOOTSTRAP_ROOT["signed"]["roles"]["root"]
    targets_role = BOOTSTRAP_ROOT["signed"]["roles"]["targets"]
    assert root_role["threshold"] == 3
    assert targets_role["threshold"] == 3
    assert len(root_role["keyids"]) >= 5
    assert len(targets_role["keyids"]) >= 5
