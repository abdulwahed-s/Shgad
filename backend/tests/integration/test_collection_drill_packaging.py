"""The unchanged demo questions work without locally excluded documentation."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import collection_drill  # noqa: E402

DEMO_QUESTIONS_SHA256 = (
    "e28386816121b3bfddb26fa35cb72b6deeb3bdc3108664e8619fe3f6a1372239"
)


def portable_files(tmp_path):
    assert collection_drill.DEMO == (
        collection_drill.ROOT / "data/evaluation/collection_demo_v1.json"
    )
    for source in (
        Path(collection_drill.__file__),
        collection_drill.SMOKE,
        collection_drill.DEMO,
    ):
        destination = tmp_path / source.relative_to(collection_drill.ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def test_packaged_demo_has_the_exact_original_ten_questions_and_order(
    tmp_path, monkeypatch
):
    portable_files(tmp_path)
    monkeypatch.setattr(
        collection_drill,
        "SMOKE",
        tmp_path / "data/evaluation/collection_smoke_v1.jsonl",
    )
    monkeypatch.setattr(
        collection_drill, "DEMO", tmp_path / "data/evaluation/collection_demo_v1.json"
    )
    smoke, demo = collection_drill.plan()
    assert len(smoke) == 20 and len(demo) == 10
    assert (
        hashlib.sha256(
            json.dumps(demo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        == DEMO_QUESTIONS_SHA256
    )


def test_fresh_plan_needs_only_committed_files_and_makes_zero_provider_calls(tmp_path):
    portable_files(tmp_path)
    result = subprocess.run(
        [sys.executable, "-I", "scripts/collection_drill.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "smoke": 20,
        "original_demo": 10,
        "max_requests": 36,
        "provider_calls": 0,
        "credentials_loaded": False,
    }
    assert not (tmp_path / "docs").exists()
