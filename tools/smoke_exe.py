"""Test the actual bundled app from an unrelated working directory, using a fresh profile."""

import argparse
import hashlib
import json
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
            expected_coins = 50 if iteration == 0 else 37
            assert result["coins"] == expected_coins and save.exists(), result
            assert result["platform"] == sys.platform, result
            (out / f"smoke-{iteration + 1}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            if iteration == 0:
                # A distinctive QA balance proves the second launch loads the save.
                saved = json.loads(save.read_text(encoding="utf-8"))
                saved["coins"] = 37
                save.write_text(json.dumps(saved), encoding="utf-8")
    with exe.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    summary = {
        "ok": True,
        "platform": sys.platform,
        "name": exe.name,
        "bytes": exe.stat().st_size,
        "sha256": digest,
        "launches": 2,
        "cwd_independent": True,
        "save_restored": True,
        "scenes": 6,
    }
    (out / "executable.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (exe.parent / "SHA256SUMS.txt").write_text(f"{digest}  {exe.name}\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
