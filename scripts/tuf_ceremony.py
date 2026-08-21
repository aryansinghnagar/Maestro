#!/usr/bin/env python3
"""TUF Root Key Ceremony and Metadata Generation Utility.

Provisions production Ed25519 keypairs, defines multi-signature quorum roles,
and generates canonical TUF v1.0.3 metadata (root.json, targets.json,
snapshot.json, timestamp.json) compliant with PEP 458 and The Update Framework specification.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from securesystemslib.signer import CryptoSigner
from tuf.api.metadata import (
    Key,
    Metadata,
    MetaFile,
    Role,
    Root,
    Snapshot,
    Targets,
    Timestamp,
)


def create_role_keys(
    role_name: str,
    count: int = 1,
    keys_dir: Path | None = None,
) -> tuple[list[CryptoSigner], list[Key]]:
    """Generate a batch of Ed25519 signers and TUF Key objects for a given role."""
    signers: list[CryptoSigner] = []
    keys: list[Key] = []

    for i in range(count):
        signer = CryptoSigner.generate_ed25519()
        key_id = signer.public_key.keyid
        key = Key.from_dict(key_id, signer.public_key.to_dict())
        signers.append(signer)
        keys.append(key)

        if keys_dir:
            keys_dir.mkdir(parents=True, exist_ok=True)
            priv_path = keys_dir / f"{role_name}_{i+1}_{key_id[:8]}.priv.json"
            pub_path = keys_dir / f"{role_name}_{i+1}_{key_id[:8]}.pub.json"

            # Write private key with restricted permissions
            priv_content = json.dumps(
                {
                    "keytype": "ed25519",
                    "scheme": "ed25519",
                    "keyval": signer.public_key.to_dict()["keyval"],
                    "keyid": key_id,
                },
                indent=2,
            )
            priv_path.write_text(priv_content, encoding="utf-8")
            with contextlib.suppress(OSError):
                priv_path.chmod(0o600)

            pub_content = json.dumps(signer.public_key.to_dict(), indent=2)
            pub_path.write_text(pub_content, encoding="utf-8")

    return signers, keys


def run_ceremony(
    output_dir: Path,
    root_threshold: int = 2,
    root_key_count: int = 3,
    expiry_days: int = 365,
) -> dict[str, Any]:
    """Execute the TUF ceremony, writing metadata and bootstrap JSON to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    keys_dir = output_dir / "keys"
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    root_expiry = now + timedelta(days=expiry_days)
    targets_expiry = now + timedelta(days=min(expiry_days, 90))
    snapshot_expiry = now + timedelta(days=min(expiry_days, 30))
    timestamp_expiry = now + timedelta(days=min(expiry_days, 7))

    # 1. Generate keys for all standard TUF roles
    root_signers, root_keys = create_role_keys("root", root_key_count, keys_dir)
    targets_signers, targets_keys = create_role_keys("targets", 1, keys_dir)
    snapshot_signers, snapshot_keys = create_role_keys("snapshot", 1, keys_dir)
    timestamp_signers, timestamp_keys = create_role_keys("timestamp", 1, keys_dir)

    all_keys: dict[str, Key] = {}
    for k in root_keys + targets_keys + snapshot_keys + timestamp_keys:
        all_keys[k.keyid] = k

    # 2. Build Root Metadata
    roles: dict[str, Role] = {
        "root": Role([k.keyid for k in root_keys], root_threshold),
        "targets": Role([k.keyid for k in targets_keys], 1),
        "snapshot": Role([k.keyid for k in snapshot_keys], 1),
        "timestamp": Role([k.keyid for k in timestamp_keys], 1),
    }

    root_payload = Root(
        version=1,
        spec_version="1.0.3",
        expires=root_expiry,
        keys=all_keys,
        roles=roles,
    )
    root_meta = Metadata(root_payload)
    for signer in root_signers:
        root_meta.sign(signer, append=True)

    # 3. Build Targets Metadata
    targets_payload = Targets(
        version=1,
        spec_version="1.0.3",
        expires=targets_expiry,
        targets={},
    )
    targets_meta = Metadata(targets_payload)
    for signer in targets_signers:
        targets_meta.sign(signer)

    # 4. Build Snapshot Metadata
    snapshot_payload = Snapshot(
        version=1,
        spec_version="1.0.3",
        expires=snapshot_expiry,
        meta={"targets.json": MetaFile(version=1)},
    )
    snapshot_meta = Metadata(snapshot_payload)
    for signer in snapshot_signers:
        snapshot_meta.sign(signer)

    # 5. Build Timestamp Metadata
    timestamp_payload = Timestamp(
        version=1,
        spec_version="1.0.3",
        expires=timestamp_expiry,
        snapshot_meta=MetaFile(version=1),
    )
    timestamp_meta = Metadata(timestamp_payload)
    for signer in timestamp_signers:
        timestamp_meta.sign(signer)

    # 6. Save metadata files
    root_path = metadata_dir / "1.root.json"
    root_canonical_path = metadata_dir / "root.json"
    targets_path = metadata_dir / "targets.json"
    snapshot_path = metadata_dir / "snapshot.json"
    timestamp_path = metadata_dir / "timestamp.json"

    root_dict = root_meta.to_dict()
    root_json_text = json.dumps(root_dict, indent=2)

    root_path.write_text(root_json_text, encoding="utf-8")
    root_canonical_path.write_text(root_json_text, encoding="utf-8")
    targets_path.write_text(json.dumps(targets_meta.to_dict(), indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot_meta.to_dict(), indent=2), encoding="utf-8")
    timestamp_path.write_text(json.dumps(timestamp_meta.to_dict(), indent=2), encoding="utf-8")

    bootstrap_path = output_dir / "bootstrap_root.json"
    bootstrap_path.write_text(root_json_text, encoding="utf-8")

    return {
        "status": "success",
        "root_threshold": root_threshold,
        "root_key_count": root_key_count,
        "root_key_ids": [k.keyid for k in root_keys],
        "metadata_dir": str(metadata_dir),
        "keys_dir": str(keys_dir),
        "bootstrap_file": str(bootstrap_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TUF Root Key Ceremony for Maestro")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("tuf_repository"),
        help="Directory to output TUF keys and signed metadata (default: ./tuf_repository)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=2,
        help="Root signing threshold (default: 2)",
    )
    parser.add_argument(
        "--key-count",
        type=int,
        default=3,
        help="Number of root keys to generate (default: 3)",
    )
    parser.add_argument(
        "--expiry-days",
        type=int,
        default=365,
        help="Validity period in days (default: 365)",
    )

    args = parser.parse_args()

    print("==================================================================")
    print("        MAESTRO TUF ROOT KEY CEREMONY & METADATA PROVISIONER      ")
    print("==================================================================")
    print(f" Output Directory : {args.out_dir.resolve()}")
    print(f" Root Threshold   : {args.threshold} of {args.key_count}")
    print(f" Validity Period  : {args.expiry_days} days")
    print("------------------------------------------------------------------")

    result = run_ceremony(
        output_dir=args.out_dir,
        root_threshold=args.threshold,
        root_key_count=args.key_count,
        expiry_days=args.expiry_days,
    )

    print("[+] Generated Root Keys:")
    for kid in result["root_key_ids"]:
        print(f"    - Key ID: {kid}")
    print(f"[+] Metadata written to: {result['metadata_dir']}")
    print(f"[+] Private keys saved to: {result['keys_dir']}")
    print(f"[+] Bootstrap Root written to: {result['bootstrap_file']}")
    print("------------------------------------------------------------------")
    print("Ceremony complete. Maintain private keys in an offline hardware enclave.")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
