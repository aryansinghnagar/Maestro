import json
from pathlib import Path
from scripts.tuf_ceremony import run_ceremony, create_role_keys


def test_create_role_keys(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    signers, keys = create_role_keys("root", count=2, keys_dir=keys_dir)

    assert len(signers) == 2
    assert len(keys) == 2
    assert len(list(keys_dir.glob("*.priv.json"))) == 2
    assert len(list(keys_dir.glob("*.pub.json"))) == 2


def test_run_ceremony_generates_valid_tuf_metadata(tmp_path: Path) -> None:
    out_dir = tmp_path / "tuf_repo"
    res = run_ceremony(
        output_dir=out_dir,
        root_threshold=2,
        root_key_count=3,
        expiry_days=30,
    )

    assert res["status"] == "success"
    assert res["root_threshold"] == 2
    assert len(res["root_key_ids"]) == 3

    meta_dir = out_dir / "metadata"
    assert (meta_dir / "root.json").exists()
    assert (meta_dir / "1.root.json").exists()
    assert (meta_dir / "targets.json").exists()
    assert (meta_dir / "snapshot.json").exists()
    assert (meta_dir / "timestamp.json").exists()
    assert (out_dir / "bootstrap_root.json").exists()

    # Validate JSON schema structure of root.json
    root_data = json.loads((meta_dir / "root.json").read_text(encoding="utf-8"))
    assert root_data["signed"]["_type"] == "root"
    assert root_data["signed"]["spec_version"] == "1.0.3"
    assert root_data["signed"]["roles"]["root"]["threshold"] == 2
    assert len(root_data["signatures"]) == 3
