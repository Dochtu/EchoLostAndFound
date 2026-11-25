"""Summarize the M5-C-A-R2 pytest JUnit XML and diff it against the R1 run.

Purpose: prove the 278-test suite is the *same* suite (no test deleted, renamed
away, skipped or weakened to make R2 pass).  Only test ids are compared; the
R2 result itself comes from ``junit_r2.xml`` produced by pytest.

Run:
    Server\\.venv\\Scripts\\python.exe M5CAR2\\tools\\summarize_tests.py
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R2_XML = ROOT / "M5CAR2" / "evidence" / "tests" / "junit_r2.xml"
R1_XML = ROOT / "M5CAR1" / "evidence" / "tests" / "junit_r1.xml"
OUT = ROOT / "M5CAR2" / "evidence" / "tests" / "tests_summary.json"


def cases(path: Path) -> tuple[list[dict], dict]:
    tree = ET.parse(path)
    root = tree.getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    rows: list[dict] = []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    for suite in suites:
        for key in ("tests", "failures", "errors", "skipped"):
            totals[key] += int(float(suite.get(key, "0")))
        totals["time"] += float(suite.get("time", "0"))
        for case in suite.findall("testcase"):
            outcome = "passed"
            if case.find("failure") is not None:
                outcome = "failed"
            elif case.find("error") is not None:
                outcome = "error"
            elif case.find("skipped") is not None:
                outcome = "skipped"
            rows.append(
                {
                    "id": f"{case.get('classname', '')}::{case.get('name', '')}",
                    "classname": case.get("classname", ""),
                    "name": case.get("name", ""),
                    "outcome": outcome,
                    "time": float(case.get("time", "0")),
                }
            )
    return rows, totals


def main() -> int:
    if not R2_XML.exists():
        raise SystemExit(f"missing {R2_XML}")
    r2_rows, r2_totals = cases(R2_XML)

    payload = {
        "suite": "M5-C-A-R2",
        "junit": str(R2_XML.relative_to(ROOT)).replace("\\", "/"),
        "totals": r2_totals,
        "outcomes": {
            "passed": sum(1 for row in r2_rows if row["outcome"] == "passed"),
            "failed": sum(1 for row in r2_rows if row["outcome"] == "failed"),
            "error": sum(1 for row in r2_rows if row["outcome"] == "error"),
            "skipped": sum(1 for row in r2_rows if row["outcome"] == "skipped"),
        },
        "per_module": {},
    }
    for row in r2_rows:
        module = row["classname"].rsplit(".", 1)[-1]
        bucket = payload["per_module"].setdefault(module, {"tests": 0, "failed": 0})
        bucket["tests"] += 1
        if row["outcome"] in ("failed", "error"):
            bucket["failed"] += 1

    if R1_XML.exists():
        r1_rows, r1_totals = cases(R1_XML)
        r1_ids = {row["id"] for row in r1_rows}
        r2_ids = {row["id"] for row in r2_rows}
        payload["baseline_r1"] = {
            "junit": str(R1_XML.relative_to(ROOT)).replace("\\", "/"),
            "totals": r1_totals,
            "removed_test_ids": sorted(r1_ids - r2_ids),
            "added_test_ids": sorted(r2_ids - r1_ids),
            "same_test_ids": r1_ids == r2_ids,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["totals"], ensure_ascii=False))
    print("outcomes:", payload["outcomes"])
    if "baseline_r1" in payload:
        print("r1 totals:", payload["baseline_r1"]["totals"])
        print("same_test_ids:", payload["baseline_r1"]["same_test_ids"])
        print("removed:", len(payload["baseline_r1"]["removed_test_ids"]))
        print("added:", len(payload["baseline_r1"]["added_test_ids"]))
    print(f"wrote {OUT.relative_to(ROOT)}")
    ok = (
        payload["outcomes"]["failed"] == 0
        and payload["outcomes"]["error"] == 0
        and payload["outcomes"]["skipped"] == 0
        and payload.get("baseline_r1", {}).get("same_test_ids", True)
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
