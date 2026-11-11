import argparse
import json
from pathlib import Path

from checkov.common.models.enums import CheckResult
from checkov.common.output.record import Record
from checkov.common.output.baseline import Baseline
from checkov.runner_filter import RunnerFilter
from checkov.terraform.runner import Runner


SCOPED_FIXTURES = Path(__file__).parents[2] / "scoped_baseline_resources"
SCOPED_CHECKS = ["CKV_AWS_18", "CKV_AWS_145"]


def _run_scoped_folder(folder: Path):
    return Runner().run(root_folder=str(folder), runner_filter=RunnerFilter(checks=SCOPED_CHECKS))


def _failed_checks_by_file(report) -> dict[str, list[tuple[str, str]]]:
    findings: dict[str, list[tuple[str, str]]] = {}
    for check in report.failed_checks:
        findings.setdefault(check.file_path, []).append((check.check_id, check.resource))
    return findings


def _write_baseline(tmp_path: Path, failed_checks: list[dict]) -> Path:
    baseline_path = tmp_path / ".checkov.baseline"
    baseline_path.write_text(json.dumps({"failed_checks": failed_checks}))
    return baseline_path


def _build_record(check_id: str, resource: str, file_path: str) -> Record:
    return Record(
        check_id=check_id,
        check_name="check-name",
        check_result={"result": CheckResult.FAILED},
        code_block=[],
        file_path=file_path,
        file_line_range=[1, 2],
        resource=resource,
        evaluations=None,
        check_class="check-class",
        file_abs_path=file_path,
    )


def test_to_dict():
    # given
    test_folder = Path(__file__).parent / "fixtures"
    checks = ["CKV_AWS_18", "CKV_AWS_19", "CKV_AWS_21", "CKV2_AWS_6"]  # 1 pass, 2 fail, 1 skip
    report = Runner().run(root_folder=str(test_folder), runner_filter=RunnerFilter(checks=checks))

    baseline = Baseline()
    baseline.add_findings_from_report(report)

    # when
    output = baseline.to_dict()

    # then
    assert output == {
        "failed_checks": [
            {
                "file": "/main.tf",
                "findings": [
                    {
                        "resource": "aws_s3_bucket.destination",
                        "check_ids": ["CKV2_AWS_6", "CKV_AWS_18"],
                    }
                ],
            },
            {
                "file": "/main_2.tf",
                "findings": [
                    {
                        "resource": "aws_s3_bucket.destination_2",
                        "check_ids": ["CKV2_AWS_6", "CKV_AWS_18"],
                    },
                    {
                        "resource": "aws_s3_bucket.destination_3",
                        "check_ids": ["CKV2_AWS_6", "CKV_AWS_18"],
                    },
                ],
            },
        ]
    }


def test_baseline_matches_findings_within_file_scope(tmp_path):
    # given: a baseline created from a scan of the common parent of both
    # directories. Both directories declare an aws_s3_bucket.logs resource,
    # but only A's CKV_AWS_18 is part of the baseline.
    baseline_path = _write_baseline(
        tmp_path,
        [
            {
                "file": "/A/main.tf",
                "findings": [
                    {"resource": "aws_s3_bucket.logs", "check_ids": ["CKV_AWS_18"]},
                ],
            },
        ],
    )
    baseline = Baseline()
    baseline.from_json(str(baseline_path))

    # when: the same common parent is scanned again
    report = _run_scoped_folder(SCOPED_FIXTURES)
    baseline.compare_and_reduce_reports([report])
    findings = _failed_checks_by_file(report)

    # then: A's baselined CKV_AWS_18 is removed, while A's other rule stays new
    assert findings["/A/main.tf"] == [("CKV_AWS_145", "aws_s3_bucket.logs")]

    # and: B's same-named resource is not treated as an old finding just
    # because the resource and the rule match A's baseline entry
    assert sorted(findings["/B/main.tf"]) == [
        ("CKV_AWS_145", "aws_s3_bucket.logs"),
        ("CKV_AWS_18", "aws_s3_bucket.logs"),
    ]


def test_baseline_scoped_matching_keeps_new_failures_in_third_scope(tmp_path):
    # given: only A's finding is part of the baseline
    baseline_path = _write_baseline(
        tmp_path,
        [
            {
                "file": "/A/main.tf",
                "findings": [
                    {"resource": "aws_s3_bucket.logs", "check_ids": ["CKV_AWS_18"]},
                ],
            },
        ],
    )
    baseline = Baseline()
    baseline.from_json(str(baseline_path))

    # when: a third directory containing genuinely new failures is scanned
    report = _run_scoped_folder(SCOPED_FIXTURES)
    baseline.compare_and_reduce_reports([report])
    findings = _failed_checks_by_file(report)

    # then: C's failures are reported instead of being silently dropped
    assert sorted(findings["/C/main.tf"]) == [
        ("CKV_AWS_145", "aws_s3_bucket.logs"),
        ("CKV_AWS_18", "aws_s3_bucket.logs"),
    ]


def test_baseline_output_skipped_keeps_evidence_within_file_scope(tmp_path):
    # given
    baseline_path = _write_baseline(
        tmp_path,
        [
            {
                "file": "/A/main.tf",
                "findings": [
                    {"resource": "aws_s3_bucket.logs", "check_ids": ["CKV_AWS_18"]},
                ],
            },
        ],
    )
    baseline = Baseline(output_skipped=True)
    baseline.from_json(str(baseline_path))

    # when: the common parent is scanned and baselined findings are emitted as skipped
    report = _run_scoped_folder(SCOPED_FIXTURES)
    baseline.compare_and_reduce_reports([report])

    # then: exactly one record, the in-scope baselined finding, is skipped
    # and its evidence (resource, file and result details) stays intact
    assert len(report.skipped_checks) == 1
    skipped = report.skipped_checks[0]
    assert skipped.check_id == "CKV_AWS_18"
    assert skipped.resource == "aws_s3_bucket.logs"
    assert skipped.file_path == "/A/main.tf"
    assert skipped.check_result["result"] == CheckResult.SKIPPED
    assert skipped.check_result["suppress_comment"] == "baseline-skipped"

    findings = _failed_checks_by_file(report)
    assert findings["/A/main.tf"] == [("CKV_AWS_145", "aws_s3_bucket.logs")]
    assert sorted(findings["/B/main.tf"]) == [
        ("CKV_AWS_145", "aws_s3_bucket.logs"),
        ("CKV_AWS_18", "aws_s3_bucket.logs"),
    ]


def test_baseline_supports_legacy_entries_without_file_scope(tmp_path):
    # given: a legacy-style baseline whose entries only carry resource + check ids
    baseline_path = _write_baseline(
        tmp_path,
        [
            {
                "findings": [
                    {"resource": "aws_s3_bucket.logs", "check_ids": ["CKV_AWS_18"]},
                ],
            },
        ],
    )
    baseline = Baseline()
    baseline.from_json(str(baseline_path))

    # when / then: the legacy entry still suppresses the matching resource + rule
    record = _build_record("CKV_AWS_18", "aws_s3_bucket.logs", "/main.tf")
    assert baseline._is_check_in_baseline(record) is True

    # and: non-matching rules or resources remain visible as new failures
    other_check = _build_record("CKV_AWS_145", "aws_s3_bucket.logs", "/main.tf")
    other_resource = _build_record("CKV_AWS_18", "aws_s3_bucket.other", "/main.tf")
    assert baseline._is_check_in_baseline(other_check) is False
    assert baseline._is_check_in_baseline(other_resource) is False


def test_baseline_does_not_match_scoped_entry_in_other_file():
    # given: a scoped baseline entry for the same resource name in a different file
    baseline = Baseline()
    baseline.failed_checks = [
        {
            "file": "/A/main.tf",
            "findings": [
                {"resource": "aws_s3_bucket.logs", "check_ids": ["CKV_AWS_18"]},
            ],
        }
    ]

    # when / then: the identical resource + rule in another file is treated as new
    record = _build_record("CKV_AWS_18", "aws_s3_bucket.logs", "/B/main.tf")
    assert baseline._is_check_in_baseline(record) is False

    # and: the same file still matches
    matching_record = _build_record("CKV_AWS_18", "aws_s3_bucket.logs", "/A/main.tf")
    assert baseline._is_check_in_baseline(matching_record) is True
