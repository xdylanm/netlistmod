from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).parent / "corpus"


def test_every_corpus_family_has_a_manifest_and_matching_hashes() -> None:
    families = {
        path.parent
        for path in CORPUS.rglob("*")
        if path.is_file() and path.suffix.lower() in {".cir", ".net", ".sp"}
    }
    assert families

    for family in families:
        manifest_path = family / "manifest.json"
        assert manifest_path.is_file(), f"Missing corpus manifest: {family}"
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["origin"]
        assert manifest["license"]
        assert manifest["author"]
        assert manifest["date"]

        fixtures: dict[str, str] = manifest["fixtures"]
        actual_names = {
            path.name for path in family.iterdir() if path.is_file() and path != manifest_path
        }
        assert set(fixtures) == actual_names
        for filename, expected_hash in fixtures.items():
            actual_hash = hashlib.sha256((family / filename).read_bytes()).hexdigest()
            assert actual_hash == expected_hash, f"Fixture hash changed: {family / filename}"
