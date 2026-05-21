from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "specs"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL specs: {message}")


def find_features() -> list[Path]:
    if not SPEC_DIR.exists():
        fail("missing specs/ directory")
    return sorted(SPEC_DIR.rglob("*.feature"))


def check_basic_shape(features: list[Path]) -> None:
    if not features:
        fail("no specs/**/*.feature files found")

    for path in features:
        text = path.read_text(encoding="utf-8").strip()
        relative = path.relative_to(ROOT)
        if not text:
            fail(f"{relative} is empty")
        if "Feature:" not in text:
            fail(f"{relative} has no Feature")
        if "Scenario:" not in text and "Scenario Outline:" not in text:
            fail(f"{relative} has no Scenario")


def resolve_gherkin() -> list[str] | None:
    names = ["gherkin-v39"]
    if os.name == "nt":
        names = ["gherkin-v39.cmd", "gherkin-v39.exe", "gherkin-v39.ps1", "gherkin-v39"]

    for name in names:
        resolved = shutil.which(name)
        if not resolved:
            continue
        if resolved.lower().endswith(".ps1"):
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if not pwsh:
                continue
            return [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved]
        return [resolved]
    return None


def check_with_gherkin(features: list[Path]) -> None:
    command_prefix = resolve_gherkin()
    if command_prefix is None:
        fail("gherkin-v39 was not found on PATH")

    command = [
        *command_prefix,
        "--predictable-ids",
        "-f",
        "ndjson",
        *[str(path.relative_to(ROOT)) for path in features],
    ]
    print(f"$ {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr)
    if completed.returncode != 0:
        fail(f"gherkin-v39 exited {completed.returncode}")

    seen = {"source": False, "gherkinDocument": False, "pickle": False}
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        for key in seen:
            if key in event:
                seen[key] = True
    missing = [key for key, value in seen.items() if not value]
    if missing:
        fail(f"gherkin-v39 output missing events: {', '.join(missing)}")


def main() -> int:
    features = find_features()
    check_basic_shape(features)
    check_with_gherkin(features)
    print(f"PASS specs: parsed {len(features)} feature file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
