from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).parent / "corpus"
NGSPICE = CORPUS / "ngspice"
STUBS = NGSPICE / "solver_stubs"


def test_every_corpus_family_has_a_manifest_and_matching_hashes() -> None:
    # A family is a folder holding netlists, or one holding a manifest (the solver stubs).
    families = {
        path.parent
        for path in CORPUS.rglob("*")
        if path.is_file()
        and (path.suffix.lower() in {".cir", ".net", ".sp"} or path.name == "manifest.json")
    }
    assert STUBS in families and STUBS / "raw" in families

    for family in families:
        manifest_path = family / "manifest.json"
        assert manifest_path.is_file(), f"Missing corpus manifest: {family}"
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["origin"]
        assert manifest["license"]
        assert manifest["author"]
        assert manifest["date"]

        fixtures: dict[str, str | dict[str, Any]] = manifest["fixtures"]
        actual_names = {
            path.name for path in family.iterdir() if path.is_file() and path != manifest_path
        }
        assert set(fixtures) == actual_names
        for filename, fixture_metadata in fixtures.items():
            actual_hash = hashlib.sha256((family / filename).read_bytes()).hexdigest()
            expected_hash = (
                fixture_metadata
                if isinstance(fixture_metadata, str)
                else fixture_metadata["sha256"]
            )
            assert actual_hash == expected_hash, f"Fixture hash changed: {family / filename}"


def test_every_accept_fixture_runs_in_ngspice_or_has_a_reason() -> None:
    """Decision 0008: a fixture's optional ``solver`` field is ``{"skip": reason}``, or names
    stub files for its includes (``stubs``) and an included harness (``harness``)."""
    families = sorted(
        family.name
        for family in NGSPICE.iterdir()
        if family.is_dir() and not family.name.endswith("_rejects") and family != STUBS
    )
    from tests.solver.test_ngspice_corpus import FAMILIES, solver_fields

    assert sorted(FAMILIES) == families
    fields = solver_fields()
    assert {path.parent.name for path in fields} == set(families)
    for path, field in fields.items():
        assert set(field) <= {"skip", "stubs", "harness"}, path
        if "skip" in field:
            assert set(field) == {"skip"} and isinstance(field["skip"], str), path
            assert len(field["skip"]) > 20, f"give the reason: {path}"
        for stub in [*field.get("stubs", {}).values(), *filter(None, [field.get("harness")])]:
            assert (STUBS / stub).is_file(), f"{path}: missing stub {stub}"
