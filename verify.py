from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend-cloudrun"
FRONTEND = ROOT / "frontend"
LOGIN = ROOT / "ecosense-login"
VERIFY = ROOT / "verify"


def run(command: list[str], cwd: Path = ROOT, *, required: bool = True) -> bool:
    print(f"\n== {' '.join(command)} ==")
    print(f"cwd: {cwd}")
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        message = f"FAILED: {' '.join(command)} exited {result.returncode}"
        if required:
            raise SystemExit(message)
        print(message)
        return False
    print("PASS")
    return True


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def python_executable() -> str:
    venv_python = BACKEND / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def npx_command() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def compile_python() -> None:
    run([python_executable(), "-m", "compileall", "app", "tests"], cwd=BACKEND)


def test_backend() -> None:
    tests = [
        "tests/test_ai_report_frequency_regression.py",
        "tests/test_latest_data_status_regression.py",
        "tests/test_openapi_integration_endpoints.py",
    ]
    run([python_executable(), "-m", "pytest", *tests, "-q"], cwd=BACKEND)


def pyright() -> None:
    if not command_exists(npx_command()):
        print("\nSKIP: npx is not available; install Node.js to run Pyright.")
        return
    run([npx_command(), "--yes", "pyright", "--project", str(ROOT / "pyrightconfig.json")], cwd=ROOT)


def frontend_typecheck() -> None:
    if not (FRONTEND / "node_modules").exists():
        print("\nSKIP: frontend/node_modules not found; run npm install in frontend for Vue typecheck.")
        return
    run([npm_command(), "run", "build"], cwd=FRONTEND)


def login_typecheck() -> None:
    if not (LOGIN / "node_modules").exists():
        print("\nSKIP: ecosense-login/node_modules not found; run npm install in ecosense-login for React build.")
        return
    run([npm_command(), "run", "build"], cwd=LOGIN)


def check() -> None:
    compile_python()
    test_backend()
    spec()
    pyright()
    frontend_typecheck()
    login_typecheck()
    print("\nDONE: verify check PASS")


def lsp() -> None:
    pyright()
    frontend_typecheck()
    login_typecheck()
    print("\nDONE: verify lsp PASS")


def test() -> None:
    test_backend()
    print("\nDONE: verify test PASS")


def spec() -> None:
    run([python_executable(), "scripts/check_specs.py"], cwd=ROOT)
    print("\nDONE: verify spec PASS")


def afk() -> None:
    config_path = VERIFY / "afk-test.config.json"
    if not config_path.exists():
        raise SystemExit(f"FAILED: missing {config_path.relative_to(ROOT)}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    for section in ["project", "baseline", "optional", "artifacts", "environment", "autonomy", "blockers"]:
        if section not in config:
            raise SystemExit(f"FAILED: {config_path.relative_to(ROOT)} missing section: {section}")

    print("\nDONE: verify afk PASS")


def db() -> None:
    run([python_executable(), "scripts/verify_db_automation.py"], cwd=BACKEND)
    print("\nDONE: verify db PASS")


def security() -> None:
    print("\nNo project-specific security scanner configured yet.")
    print("DONE: verify security PASS")


def all_checks() -> None:
    check()
    security()
    print("\nDONE: verify all PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="EcoMind-AI verification entrypoint.")
    parser.add_argument(
        "target",
        nargs="?",
        default="check",
        choices=["check", "test", "lsp", "spec", "afk", "db", "security", "all"],
    )
    args = parser.parse_args()
    {
        "check": check,
        "test": test,
        "lsp": lsp,
        "spec": spec,
        "afk": afk,
        "db": db,
        "security": security,
        "all": all_checks,
    }[args.target]()


if __name__ == "__main__":
    main()
