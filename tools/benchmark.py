"""Bounded renderer soak: a visual day, with all species and unchanged game/save."""
# ruff: noqa: E402

import argparse
from copy import deepcopy
import ctypes
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from config.data import SCENES
from game.engine import Farm
from visual.scene import Renderer


def resident_bytes():
    if sys.platform == "win32":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_working",
                    "working",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        result = Counters()
        result.cb = ctypes.sizeof(result)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(result), result.cb):
            raise ctypes.WinError()
        return result.working
    if sys.platform.startswith("linux"):
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    return None


def benchmark(frames=1200):
    app = QApplication.instance() or QApplication([])
    saved = json.loads((ROOT / "tests/fixtures/v0.1.0-save.json").read_text(encoding="utf-8"))
    farm = Farm(clock=lambda: saved["last_accounted"])
    farm.state = deepcopy(saved)
    before = deepcopy(farm.state)
    renderer = Renderer()
    start_time = datetime(2026, 1, 1)
    for index in range(60):
        renderer.render(farm, SCENES[index % 6], start_time, phase=index / 3)
    memory_before = resident_bytes()
    durations = []
    for index in range(frames):
        phase = index * 86400 / max(1, frames - 1)
        moment = start_time + timedelta(seconds=phase)
        start = time.perf_counter()
        image = renderer.render(farm, SCENES[index % 6], moment, phase=phase + index * 0.13)
        durations.append((time.perf_counter() - start) * 1000)
        assert not image.isNull()
        if index % 120 == 0:
            app.processEvents()
    memory_after = resident_bytes()
    growth = memory_after - memory_before if memory_before is not None else None
    assert farm.state == before
    mean = statistics.mean(durations)
    return {
        "ok": mean < 100 and (growth is None or growth < 64 * 1024 * 1024),
        "frames": frames,
        "simulated_visual_hours": 24,
        "render_mean_ms": round(mean, 3),
        "render_p95_ms": round(sorted(durations)[int(len(durations) * 0.95)], 3),
        "resident_before_bytes": memory_before,
        "resident_after_bytes": memory_after,
        "resident_growth_bytes": growth,
        "cached_light_plates": len(renderer.light.plates),
        "cached_animal_frames": len(renderer.animal_frames),
        "economy_unchanged": farm.state == before,
        "representatives": {key: len(farm.representatives(key)) for key in SCENES},
        "platform": sys.platform,
        "scope": "1200 sampled renders across one visual day; not 24 wall-clock hours",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "qa-output/performance.json")
    parser.add_argument("--frames", type=int, default=1200)
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("--frames must be at least 20")
    result = benchmark(args.frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
