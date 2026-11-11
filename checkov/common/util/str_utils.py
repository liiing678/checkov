import platform
import re
from pathlib import PureWindowsPath
from typing import Any

seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
seconds_per_unit_regex = r"^\d+[s|m|h|d|w]"

IS_WINDOWS = platform.system() == "Windows"


def skip_check_matches_check_id(skip_check: dict[str, Any], check_id: str, bc_check_id: str | None = None) -> bool:
    """Check whether a collected skip comment applies to a check using full-ID matching.

    Skip comments may use either a Checkov ID (``CKV_*``/``CKV2_*``) or a Bridgecrew/Prisma
    ID (``BC_*``). The context parser normalizes the comment to a Checkov ID when the policy
    metadata mapping is available and keeps the original Bridgecrew ID in ``bc_id``; without
    metadata the raw comment ID is kept unchanged.

    Matching is intentionally exact (equality only) - a substring check such as
    ``check_id in skip_id`` would wrongly suppress ``CKV_AWS_1`` and ``CKV_AWS_10`` when
    only ``CKV_AWS_100`` was skipped.
    """
    if not check_id:
        return False

    skip_id = skip_check.get("id")
    if skip_id and skip_id == check_id:
        return True

    skip_bc_id = skip_check.get("bc_id")
    if skip_bc_id and bc_check_id and skip_bc_id == bc_check_id:
        return True
    # The comment used a Bridgecrew ID but the policy metadata mapping is unavailable
    # (offline runs), so the raw Bridgecrew ID is still stored in the id field.
    if skip_id and bc_check_id and skip_id == bc_check_id:
        return True

    return False


# Matches IDs of the form: LETTERS_CUSTOM_uuid (e.g. CKV_CUSTOM_abc-123, RANDOM_CUSTOM_abc-123)
CUSTOM_CHECK_ID_RE = re.compile(r'^[A-Za-z]+_CUSTOM_([a-f0-9\-]{36})$', re.IGNORECASE)


def skip_check_matches_custom_check_id(skip_id: str, check_id: str, prefix_suppression_enabled: bool = True) -> bool:
    """Match custom check skip comments that may use different ID prefixes but the same UUID.

    Only ``*_CUSTOM_<uuid>`` IDs get the relaxed treatment; built-in checks keep full-ID
    exact matching to avoid false positives such as ``CKV_AWS_1`` suppressing ``CKV_AWS_10``.
    """
    if not skip_id or not check_id:
        return False
    if skip_id == check_id:
        return True
    if not prefix_suppression_enabled:
        return False
    skip_match = CUSTOM_CHECK_ID_RE.match(skip_id)
    check_match = CUSTOM_CHECK_ID_RE.match(check_id)
    if not skip_match or not check_match:
        return False
    return skip_match.group(1) == check_match.group(1)


# method 'str.removeprefix()' was added in Python 3.9
def removeprefix(input_str: str, prefix: str) -> str:
    if input_str.startswith(prefix):
        return input_str[len(prefix):]
    return input_str


# in case of comparing paths from the BE and from the client, we have to make sure the structures are the same
# e.g: in windows the separator for the path is '\' while in linux/max it is '/'
def align_path(path: str) -> str:
    return path.replace('\\', '/')


def get_rootless_path(path: str) -> str:
    """Strip a leading drive, UNC share or root prefix from a Windows path.

    Only for use on Windows -- guard calls with ``IS_WINDOWS``. On POSIX a leading '//'
    is a valid root, which Windows semantics would misread as a UNC share.

    Replaces ``path.replace(Path(path).anchor, "", 1)``, which is not positionally
    aware: for a mixed-separator path like ``/repo\\client\\Dockerfile`` the anchor is a
    bare ``'\\'``, so ``str.replace`` removes the first separator anywhere in the string
    and yields ``/repoclient\\Dockerfile``.

    Separators are left as-is; use ``align_path()`` for a platform-independent form.
    """
    win_anchor = PureWindowsPath(path).anchor
    if win_anchor not in ('', '\\', '/'):  # a real drive (C:\) or UNC (\\srv\share\)
        path = path[len(win_anchor):]
    return path.lstrip('\\/')


def convert_to_seconds(input_str: str) -> int:
    if re.search(seconds_per_unit_regex, input_str) is None:
        raise Exception(f"format error for input str, usage: {seconds_per_unit_regex}")
    return int(input_str[:-1]) * seconds_per_unit[input_str[-1]]
