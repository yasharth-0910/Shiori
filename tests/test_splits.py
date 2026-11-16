"""The org -> split assignment is frozen (D-40): any change needs a decision entry.
FROZEN is a copy of data/eval/splits.json made when the split was committed."""

import json
from pathlib import Path

from collector.manifest import read_rows
from eval.splits import check

REPO_ROOT = Path(__file__).resolve().parent.parent
FROZEN = {
    "こども家庭庁": "train",
    "サイバー通信情報監理委員会": "train",
    "デジタル庁": "train",
    "人事院": "train",
    "個人情報保護委員会": "train",
    "八王子市": "train",
    "公正取引委員会": "train",
    "内閣府": "dev",
    "北海道": "test",
    "厚生労働省": "dev",
    "和歌山県": "dev",
    "国土交通省": "train",
    "奈良市": "train",
    "富山市": "train",
    "岡山県": "test",
    "川口市": "train",
    "復興庁": "train",
    "文部科学省": "test",
    "新潟県": "dev",
    "旭川市": "dev",
    "最高裁判所": "test",
    "松江市": "train",
    "横須賀市": "train",
    "気象衛星センター": "test",
    "法務省": "dev",
    "消費者庁": "train",
    "環境省": "train",
    "経済産業省": "test",
    "総務省": "dev",
    "船橋市": "test",
    "衆議院": "train",
    "財務省": "train",
    "農林水産省": "dev",
    "郡山市": "train",
    "金沢市": "train",
    "防衛省": "test",
    "鹿児島市": "train",
}


def test_splits_json_is_frozen() -> None:
    now = json.loads((REPO_ROOT / "data/eval/splits.json").read_text())
    changed = {
        o: (FROZEN.get(o), now.get(o))
        for o in FROZEN.keys() | now.keys()
        if FROZEN.get(o) != now.get(o)
    }
    assert not changed, f"splits are frozen (D-40), org: (frozen, now): {changed}"


def test_every_org_in_the_manifest_is_assigned() -> None:
    orgs = {
        r.issuer_org for r in read_rows(REPO_ROOT / "data/manifests/documents.jsonl")
    }
    assert orgs == set(FROZEN)


def test_phase_3_split_constraints_hold() -> None:
    rows = read_rows(REPO_ROOT / "data/manifests/documents.jsonl")
    failed = [c for c, ok, _ in check(FROZEN, rows) if not ok]
    assert not failed
