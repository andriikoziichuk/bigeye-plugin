"""Round-trip tests for the schema validator."""
import sys
from pathlib import Path

from tests.validate_schema import validate_profiles_file, validate_settings_file

ROOT = Path(__file__).parent / "fixtures"


def main() -> int:
    failures: list[str] = []

    errs = validate_profiles_file(ROOT / "profiles_v05.json")
    if errs:
        failures.append(f"profiles_v05.json should validate, got: {errs}")

    errs = validate_profiles_file(ROOT / "profiles_legacy.json")
    if errs:
        failures.append(f"profiles_legacy.json should validate (legacy tolerated), got: {errs}")

    errs = validate_settings_file(ROOT / "settings_v05.json")
    if errs:
        failures.append(f"settings_v05.json should validate, got: {errs}")

    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("OK — validator round-trip passes for v0.5 + legacy fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
