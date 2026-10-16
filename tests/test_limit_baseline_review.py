import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
import limit_baseline_review as report


def test_native_baseline_distinguishes_unsupported_features_from_existing_adjustment():
    saved = json.loads((ROOT/'conformance/evidence/limit_features_baseline.json').read_bytes())
    actual = report.review(Path(saved['raw']['path']), saved['source_revision'], saved['runtime_image'])
    assert actual == saved and len(actual['failed_features']) == 10
    assert not actual['qualified_contracts'] and not actual['full_v05_accepted']


def test_path_shadow_recorder_failure_cannot_be_used_as_feature_counterexample():
    saved = json.loads((ROOT/'conformance/evidence/limit_features_baseline.json').read_bytes())
    rejected = Path('C:/oblimit_full/.qualification/limit-features-baseline/d7c1b8be942b46cfb68f25b54a93388b/result.json')
    with pytest.raises(AssertionError):
        report.review(rejected, '1eef9eb98db00675033ea72b2bdb0c8421b52675', saved['runtime_image'])
