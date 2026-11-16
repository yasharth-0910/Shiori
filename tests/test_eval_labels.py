"""D-24: data/eval/ (committed) holds labels for open documents only."""

from pathlib import Path

from collector.manifest import read_rows

REPO_ROOT = Path(__file__).resolve().parent.parent


def non_open_labels(eval_dir: Path, manifest: Path) -> list[str]:
    """Label files whose doc is not `open`, or not in the manifest at all."""
    license_of = {r.doc_id: r.license_class for r in read_rows(manifest)}
    return [
        str(path.relative_to(eval_dir))
        for path in sorted(eval_dir.glob("*/labels/*.jsonl"))
        if license_of.get(path.stem) != "open"
    ]


def test_committed_labels_are_for_open_documents_only() -> None:
    bad = non_open_labels(
        REPO_ROOT / "data/eval", REPO_ROOT / "data/manifests/documents.jsonl"
    )
    assert not bad, f"move these to data/eval_private/ (D-24): {bad}"


def test_check_catches_restricted_and_unknown_docs(tmp_path: Path) -> None:
    rows = read_rows(REPO_ROOT / "data/manifests/documents.jsonl")
    by_class = {r.license_class: r.doc_id for r in rows}
    labels = tmp_path / "eval" / "dev" / "labels"
    labels.mkdir(parents=True)
    for doc_id in [*by_class.values(), "not-in-manifest"]:
        (labels / f"{doc_id}.jsonl").write_text("{}\n")
    bad = non_open_labels(
        tmp_path / "eval", REPO_ROOT / "data/manifests/documents.jsonl"
    )
    assert {Path(b).stem for b in bad} == {
        by_class["restricted"],
        by_class["unknown"],
        "not-in-manifest",
    }
