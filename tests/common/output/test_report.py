from checkov.common.output.report import Report
from checkov.common.output.record import Record
from checkov.common.models.enums import CheckResult


def _failing_record(check_id: str, resource: str = "aws_s3_bucket.bucket",
                    resource_address: str | None = None,
                    bc_check_id: str | None = None) -> Record:
    return Record(
        check_id=check_id,
        check_name=check_id,
        check_result={"result": CheckResult.FAILED},
        code_block=[],
        file_path="main.tf",
        file_line_range=[1, 2],
        resource=resource,
        evaluations=None,
        check_class="",
        file_abs_path="/repo/main.tf",
        entity_tags=None,
        resource_address=resource_address,
        bc_check_id=bc_check_id,
    )


def test_handle_skipped_checks_uses_full_id_matching():
    # given: a skip comment for CKV_AWS_1 only
    report = Report("terraform_plan")
    for check_id in ("CKV_AWS_1", "CKV_AWS_10", "CKV_AWS_100"):
        report.add_record(_failing_record(check_id))
    enriched_resources = {
        "aws_s3_bucket.bucket": {
            "skipped_checks": [{"id": "CKV_AWS_1", "suppress_comment": "exact only"}],
        }
    }

    # when
    result = Report.handle_skipped_checks(report, enriched_resources)

    # then: only the full-ID match is skipped, the near IDs stay FAILED
    assert [record.check_id for record in result.skipped_checks] == ["CKV_AWS_1"]
    assert result.skipped_checks[0].check_result["suppress_comment"] == "exact only"
    assert {record.check_id for record in result.failed_checks} == {"CKV_AWS_10", "CKV_AWS_100"}
    assert result.get_summary() == {
        "passed": 0,
        "failed": 2,
        "skipped": 1,
        "parsing_errors": 0,
        "resource_count": 0,
        "checkov_version": result.get_summary()["checkov_version"],
    }


def test_handle_skipped_checks_longer_skip_id_does_not_suppress_prefixes():
    # given: a longer skip ID that previously substring-matched shorter check IDs
    report = Report("terraform_plan")
    for check_id in ("CKV_AWS_1", "CKV_AWS_10", "CKV_AWS_100"):
        report.add_record(_failing_record(check_id))
    enriched_resources = {
        "aws_s3_bucket.bucket": {
            "skipped_checks": [{"id": "CKV_AWS_100", "suppress_comment": "only 100"}],
        }
    }

    # when
    result = Report.handle_skipped_checks(report, enriched_resources)

    # then
    assert [record.check_id for record in result.skipped_checks] == ["CKV_AWS_100"]
    assert {record.check_id for record in result.failed_checks} == {"CKV_AWS_1", "CKV_AWS_10"}


def test_handle_skipped_checks_matches_bridgecrew_id_without_metadata():
    # given: offline run where the raw BC id is kept in the skip comment id field
    report = Report("terraform_plan")
    report.add_record(_failing_record("CKV_AWS_15", bc_check_id="BC_AWS_IAM_5"))
    report.add_record(_failing_record("CKV_AWS_16", bc_check_id="BC_AWS_IAM_6"))
    enriched_resources = {
        "aws_s3_bucket.bucket": {
            "skipped_checks": [{"id": "BC_AWS_IAM_5", "suppress_comment": "bc skip"}],
        }
    }

    # when
    result = Report.handle_skipped_checks(report, enriched_resources)

    # then
    assert [record.check_id for record in result.skipped_checks] == ["CKV_AWS_15"]
    assert [record.check_id for record in result.failed_checks] == ["CKV_AWS_16"]


def test_handle_skipped_checks_nested_module_skip():
    # given: a resource nested two modules deep, skipped on the inner and the outer module
    address = "module.outer.module.inner.aws_s3_bucket.bucket"
    report = Report("terraform_plan")
    report.add_record(_failing_record("CKV_AWS_1", resource_address=address))
    report.add_record(_failing_record("CKV_AWS_2", resource_address=address))
    enriched_resources = {
        "outer": {"skipped_checks": [{"id": "CKV_AWS_1", "suppress_comment": "outer module"}]},
        "inner": {"skipped_checks": [{"id": "CKV_AWS_1", "suppress_comment": "inner module"}]},
    }

    # when
    result = Report.handle_skipped_checks(report, enriched_resources)

    # then: the record is moved to skipped exactly once even though both modules skip it
    assert len(result.skipped_checks) == 1
    assert result.skipped_checks[0].check_id == "CKV_AWS_1"
    assert [record.check_id for record in result.failed_checks] == ["CKV_AWS_2"]


def test_handle_skipped_checks_module_near_id_stays_failed():
    # given: module-level skip for the longer ID must not suppress the shorter near ID
    address = "module.inner.aws_s3_bucket.bucket"
    report = Report("terraform_plan")
    report.add_record(_failing_record("CKV_AWS_1", resource_address=address))
    enriched_resources = {
        "inner": {"skipped_checks": [{"id": "CKV_AWS_100", "suppress_comment": "only 100"}]},
    }

    # when
    result = Report.handle_skipped_checks(report, enriched_resources)

    # then
    assert result.skipped_checks == []
    assert [record.check_id for record in result.failed_checks] == ["CKV_AWS_1"]


def test_get_module_address_parts():
    assert Report.get_module_address_parts("module.a.module.b.aws_s3_bucket.x") == ["a", "b"]
    assert Report.get_module_address_parts("module.a[0].module.b['k'].aws_s3_bucket.x") == ["a", "b"]
    assert Report.get_module_address_parts("aws_s3_bucket.x") == []
    assert Report.get_module_address_parts(None) == []


def test_from_reduced_json(json_reduced_report):
    # Act
    report = Report.from_reduced_json(json_reduced_report, 'mock_check_type')

    # Assert
    assert len(report.failed_checks) == 1
    assert len(report.passed_checks) == 1

    failed_check = report.failed_checks[0]
    passed_check = report.passed_checks[0]

    assert failed_check.check_id == 'CKV_GHA_2'
    assert failed_check.check_name == 'Ensure ACTIONS_ALLOW_UNSECURE_COMMANDS isn\u0027t true on environment variables'
    assert failed_check.check_result == {
        "result": "FAILED",
        "results_configuration": {}
    }
    assert failed_check.resource == 'jobs(container-test-job)'
    assert failed_check.file_path == '/.github/workflows/image_no_violation.yml'
    assert failed_check.file_line_range == [7, 7]
    assert failed_check.file_abs_path == '/tmp/checkov/elturgeman6/elturgeman/supplygoat1/main/src/.github/workflows/image_no_violation.yml'
    assert failed_check.code_block == [
        [
            7,
            "    runs-on: ubuntu-latest\n"
        ],
    ]
    assert failed_check.bc_check_id == 'BC_REPO_GITHUB_ACTION_1'

    assert passed_check.check_id == 'CKV_GHA_1'
    assert passed_check.check_name == 'Ensure ACTIONS_ALLOW_UNSECURE_COMMANDS isn\u0027t true on environment variables'
    assert passed_check.check_result == {
        "result": "PASSED",
        "results_configuration": {}
    }
    assert passed_check.resource == 'jobs(container-test-job)'
    assert passed_check.file_path == '/.github/workflows/image_no_violation.yml'
    assert passed_check.file_line_range == [7, 7]
    assert passed_check.file_abs_path == '/tmp/checkov/elturgeman6/elturgeman/supplygoat1/main/src/.github/workflows/image_no_violation.yml'
    assert passed_check.code_block == [
        [
            7,
            "    runs-on: ubuntu-latest\n"
        ],
    ]
    assert passed_check.bc_check_id == 'BC_REPO_GITHUB_ACTION_1'


def test_get_plan_resource_raw_id_1():
    resource_id = Report.get_plan_resource_raw_id("module.vnet[0].azurerm_subnet.subnet_for_each['snet-commonservices']")
    assert resource_id == 'azurerm_subnet.subnet_for_each'


def test_get_plan_resource_raw_id_2():
    resource_id = Report.get_plan_resource_raw_id("module.vnet[0].azurerm_subnet.subnet_for_each[1]")
    assert resource_id == 'azurerm_subnet.subnet_for_each'


def test_get_plan_resource_raw_id_3():
    resource_id = Report.get_plan_resource_raw_id("module.vnet[0].azurerm_subnet.subnet_for_each")
    assert resource_id == 'azurerm_subnet.subnet_for_each'


def test_get_plan_resource_raw_id_4():
    resource_id = Report.get_plan_resource_raw_id("module.vnet.azurerm_subnet.subnet_for_each")
    assert resource_id == 'azurerm_subnet.subnet_for_each'


def test_get_plan_resource_raw_id_5():
    resource_id = Report.get_plan_resource_raw_id("aws_route53_zone.example[\"example.com\"]")
    assert resource_id == 'aws_route53_zone.example'


def test_get_plan_resource_raw_id_6():
    resource_id = Report.get_plan_resource_raw_id("module.sg[\"bad_example\"].aws_security_group.bad")
    assert resource_id == 'aws_security_group.bad'


def test_get_plan_resource_raw_id_7():
    resource_id = Report.get_plan_resource_raw_id("type.name")
    assert resource_id == 'type.name'
