"""Test the actual bundled app from an unrelated working directory, using a fresh profile."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, default=Path("qa-output/packaged"))
    args = parser.parse_args()
    exe = args.executable.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        with exe.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise AssertionError("Not a Windows executable")
            stream.seek(0x3C)
            offset = struct.unpack("<I", stream.read(4))[0]
            stream.seek(offset)
            if stream.read(6) != b"PE\x00\x00\x64\x86":
                raise AssertionError("Not a Windows x64 executable")
    with tempfile.TemporaryDirectory(prefix="idlefarm-exe-") as directory:
        root = Path(directory)
        report = root / "result.json"
        save = root / "isolated-profile" / "save.json"
        for iteration in range(2):
            report.unlink(missing_ok=True)
            run = subprocess.run(
                [str(exe), "--save", str(save), "--smoke", str(report)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if run.returncode != 0:
                raise AssertionError(f"Packaged app exit {run.returncode}: {run.stderr}")
            result = json.loads(report.read_text(encoding="utf-8"))
            assert result["ok"] and result["packaged"] and len(result["scenes"]) == 6, result
            assert result["version"] == "0.3.0" and result["startup_scene"] == "fields", result
            assert result["save_status"] == "saved", result
            assert result["build_commit"], result
            expected_commit = os.getenv("IDLEFARM_BUILD_COMMIT")
            if expected_commit:
                assert result["build_commit"] == expected_commit, result
            checks = result["feature_checks"]
            assert checks["tutorial_seconds"] == 60 and checks["normal_wheat_seconds"] == 3600, result
            assert all(
                checks[name]
                for name in (
                    "batch_operations",
                    "batch_confirmation_dialog",
                    "recovery_dialog_cancel",
                    "pending_purchase_retry_once",
                    "recovery_preserves_files",
                    "resume_matches_reopen",
                    "legacy_save_compatible",
                )
            ), result
            assert result["logical_resolution"] == [512, 288] and result["animal_frames"] == 72, result
            assert len(result["interiors"]) == 5, result
            expected_coins = 50 if iteration == 0 else 37
            assert result["coins"] == expected_coins and save.exists(), result
            assert result["platform"] == sys.platform, result
            (out / f"smoke-{iteration + 1}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            if iteration == 0:
                # A distinctive QA balance proves the second launch loads the save.
                saved = json.loads(save.read_text(encoding="utf-8"))
                saved["coins"] = 37
                save.write_text(json.dumps(saved), encoding="utf-8")
        bad_save = root / "invalid-profile" / "save.json"
        bad_save.parent.mkdir()
        saved = json.loads(save.read_text(encoding="utf-8"))
        saved["last_accounted"] = 10**1000
        bad_save.write_text(json.dumps(saved), encoding="utf-8")
        bad_backup = bad_save.with_suffix(".json.bak")
        bad_backup.write_bytes(save.read_bytes())
        original_primary, original_backup = bad_save.read_bytes(), bad_backup.read_bytes()
        rejected_report = root / "recovery-result.json"
        rejected = subprocess.run(
            [str(exe), "--save", str(bad_save), "--smoke", str(rejected_report)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        refusal = json.loads(rejected_report.read_text(encoding="utf-8"))
        assert rejected.returncode == 1 and refusal["recovery_required"] and refusal["backup_available"], (
            refusal
        )
        assert bad_save.read_bytes() == original_primary and bad_backup.read_bytes() == original_backup
        assert not list(bad_save.parent.glob("*.corrupt-*"))
        (out / "recovery-guard.json").write_text(json.dumps(refusal, indent=2), encoding="utf-8")
    with exe.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    summary = {
        "ok": True,
        "platform": sys.platform,
        "name": exe.name,
        "bytes": exe.stat().st_size,
        "sha256": digest,
        "launches": 2,
        "recovery_launches": 1,
        "total_launches": 3,
        "recovery_guard_verified": True,
        "cwd_independent": True,
        "save_restored": True,
        "version": "0.3.0",
        "commit": result["build_commit"],
        "feature_checks": checks,
        "scenes": 6,
    }
    (out / "executable.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (exe.parent / "SHA256SUMS.txt").write_text(f"{digest}  {exe.name}\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
