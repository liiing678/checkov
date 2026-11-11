from pathlib import PurePosixPath

import pytest

from checkov.common.util.str_utils import removeprefix
from checkov.common.util.str_utils import convert_to_seconds
from checkov.common.util.str_utils import get_rootless_path
from checkov.common.util.str_utils import skip_check_matches_check_id, skip_check_matches_custom_check_id


@pytest.mark.parametrize(
    "skip_check,check_id,bc_check_id,expected",
    [
        # exact Checkov ID match
        ({"id": "CKV_AWS_1"}, "CKV_AWS_1", None, True),
        # near IDs must never match via substring semantics
        ({"id": "CKV_AWS_1"}, "CKV_AWS_10", None, False),
        ({"id": "CKV_AWS_1"}, "CKV_AWS_100", None, False),
        ({"id": "CKV_AWS_100"}, "CKV_AWS_1", None, False),
        ({"id": "CKV_AWS_100"}, "CKV_AWS_10", None, False),
        ({"id": "CKV_AWS_10"}, "CKV_AWS_100", None, False),
        # Bridgecrew ID normalized to Checkov ID, original kept in bc_id
        ({"id": "CKV_AWS_15", "bc_id": "BC_AWS_IAM_5"}, "CKV_AWS_15", "BC_AWS_IAM_5", True),
        ({"id": "CKV_AWS_15", "bc_id": "BC_AWS_IAM_5"}, "CKV_AWS_16", "BC_AWS_IAM_6", False),
        # offline runs: raw Bridgecrew ID remains in id, match via record bc_check_id
        ({"id": "BC_AWS_IAM_5"}, "CKV_AWS_15", "BC_AWS_IAM_5", True),
        ({"id": "BC_AWS_IAM_5"}, "CKV_AWS_15", "BC_AWS_IAM_6", False),
        # defensive: empty values never match
        ({"id": ""}, "CKV_AWS_1", None, False),
        ({}, "CKV_AWS_1", None, False),
    ],
)
def test_skip_check_matches_check_id(skip_check, check_id, bc_check_id, expected):
    assert skip_check_matches_check_id(skip_check, check_id, bc_check_id) is expected


@pytest.mark.parametrize(
    "skip_id,check_id,expected",
    [
        ("CKV_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678",
         "CKV_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678", True),
        # different prefix, same UUID still suppresses custom checks
        ("LETTER_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678",
         "CKV_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678", True),
        # same prefix family but different UUID must not suppress
        ("CKV_CUSTOM_ffffffff-ffff-ffff-ffff-ffffffffffff",
         "CKV_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678", False),
        # fuzzy custom matching never applies to built-in check IDs
        ("CKV_AWS_1", "CKV_AWS_10", False),
        ("", "CKV_AWS_1", False),
    ],
)
def test_skip_check_matches_custom_check_id(skip_id, check_id, expected):
    assert skip_check_matches_custom_check_id(skip_id, check_id) is expected


def test_skip_check_matches_custom_check_id_can_be_disabled():
    skip_id = "LETTER_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678"
    check_id = "CKV_CUSTOM_a12f9ef1-1234-5678-1234-1234d0225678"
    assert skip_check_matches_custom_check_id(skip_id, check_id, prefix_suppression_enabled=False) is False
    assert skip_check_matches_custom_check_id(skip_id, check_id) is True


@pytest.mark.parametrize(
    "input_str,prefix,expected",
    [
        ("/path/to/something", "/path", "/to/something"),
        ("path/to/something", "path", "/to/something"),
        ("/path/path/to/something", "/path", "/path/to/something"),
        ("/path/to/something", "/not_found", "/path/to/something"),
        ("/path/to/something", "", "/path/to/something"),
    ],
    ids=["abs_path", "rel_path", "double_path", "not_found", "empty"],
)
def test_removeprefix(input_str: str, prefix: str, expected: str) -> None:
    assert removeprefix(input_str, prefix) == expected


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("503s", 503),
        ("3h", 10800),
        ("8m", 480),
        ("2d", 172800),
        ("1w", 604800),
    ],
    ids=["503 seconds", "3 hours", "8 minutes", "2 days", "1 week"],
)
def test_convert_to_seconds(input_str: str, expected: str) -> None:
    assert convert_to_seconds(input_str) == expected


@pytest.mark.parametrize(
    "input_str",
    [
        "4",
        "5ss",
        "6c",
    ],
    ids=["no char", "two chars", "wrong char"]
)
def test_convert_to_seconds_fails(input_str: str) -> None:
    with pytest.raises(Exception) as a:
        convert_to_seconds(input_str)
        print(a)


@pytest.mark.parametrize(
    "input_path,expected",
    [
        ("/my-project.api\\client\\Dockerfile.base", "my-project.api\\client\\Dockerfile.base"),
        ("C:\\work\\repo\\Dockerfile", "work\\repo\\Dockerfile"),
        ("\\\\srv\\share\\repo\\Dockerfile", "repo\\Dockerfile"),
        ("\\work\\repo\\Dockerfile", "work\\repo\\Dockerfile"),
        ("my-project.api\\client\\Dockerfile.base", "my-project.api\\client\\Dockerfile.base"),
        ("/my-project.api/client/Dockerfile.base", "my-project.api/client/Dockerfile.base"),
        ("my-project.api/client/Dockerfile.base", "my-project.api/client/Dockerfile.base"),
        ("/a\\b\\c\\d\\Dockerfile", "a\\b\\c\\d\\Dockerfile"),
        ("Dockerfile", "Dockerfile"),
    ],
    ids=[
        "win_slash_prefixed",
        "win_drive_absolute",
        "win_unc",
        "win_root_relative",
        "win_plain_relative",
        "posix_slash_prefixed",
        "posix_relative",
        "nested_deep",
        "single_file",
    ],
)
def test_get_rootless_path(input_path: str, expected: str) -> None:
    assert get_rootless_path(input_path) == expected


def test_get_rootless_path_must_not_be_used_on_posix() -> None:
    """Documents why callers guard on ``IS_WINDOWS``.

    A leading '//' is a valid POSIX root, but Windows semantics read it as a UNC share
    and drop two segments. Callers must keep the ``anchor`` expression on POSIX.
    """
    input_path = "//srv/share/repo/Dockerfile"

    posix_result = input_path.replace(PurePosixPath(input_path).anchor, "", 1)

    assert posix_result == "srv/share/repo/Dockerfile"
    assert get_rootless_path(input_path) != posix_result
