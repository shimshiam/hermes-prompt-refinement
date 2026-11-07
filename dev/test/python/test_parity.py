"""The Python checks (checks.py) reach the same verdicts as the TypeScript
checker on every case in dev/test/parity/inputs.json; dev/build.mjs records
the TypeScript verdicts in dev/test/parity/expected.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import DEV, load_module

CASES = json.loads((DEV / "test/parity/expected.json").read_text(encoding="utf-8"))
checks = load_module("checks")


@pytest.mark.parametrize("case", CASES, ids=[c["original"][:40] for c in CASES])
def test_same_verdict_as_typescript(case):
    assert checks.check_preservation(case["original"], case["candidate"]) == case["issues"]


def test_parity_cases_cover_every_kind():
    kinds = {issue["kind"] for case in CASES for issue in case["issues"]}
    expected = {"destructive", "file-change", "install", "external", "spending", "permission", "delegation",
                "path", "inline-code", "reference", "url", "identifier", "number", "name", "negation",
                "requirement", "code-block"}
    assert expected <= kinds, expected - kinds
