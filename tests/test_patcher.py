from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from codereview_agent.patcher import (
    PatchError,
    apply_patch_to_copy,
    apply_unified_patch_to_text,
    normalize_unified_patch,
)


PATCH = """--- a/sample.py
+++ b/sample.py
@@ -1,2 +1,2 @@
 def run():
-    return 1
+    return 2
"""

MALFORMED_COUNT_PATCH = PATCH.replace("@@ -1,2 +1,2 @@", "@@ -1,7 +1,5 @@")


def test_apply_unified_patch_to_text_checks_context() -> None:
    updated, filename = apply_unified_patch_to_text(
        "def run():\n    return 1\n",
        PATCH,
        expected_file="sample.py",
    )

    assert filename == "sample.py"
    assert updated == "def run():\n    return 2\n"


def test_patch_repairs_mismatched_hunk_counts_before_applying() -> None:
    normalized = normalize_unified_patch(
        MALFORMED_COUNT_PATCH,
        "def run():\n    return 1\n",
        expected_file="sample.py",
    )

    assert "@@ -1,2 +1,2 @@" in normalized
    updated, _filename = apply_unified_patch_to_text(
        "def run():\n    return 1\n",
        MALFORMED_COUNT_PATCH,
        expected_file="sample.py",
    )
    assert updated == "def run():\n    return 2\n"


def test_patch_count_repair_does_not_bypass_context_validation() -> None:
    with pytest.raises(PatchError, match="原文件"):
        normalize_unified_patch(
            MALFORMED_COUNT_PATCH,
            "def run():\n    return 9\n",
            expected_file="sample.py",
        )


def test_apply_patch_uses_isolated_copy_and_creates_zip(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_bytes(b"def run():\n    return 1\n")

    result = apply_patch_to_copy(tmp_path, PATCH, expected_file="sample.py")

    assert source.read_text(encoding="utf-8") == "def run():\n    return 1\n"
    assert (result.workspace / "sample.py").read_text(encoding="utf-8") == "def run():\n    return 2\n"
    with ZipFile(BytesIO(result.zip_bytes)) as archive:
        assert archive.read("sample.py") == b"def run():\n    return 2\n"


def test_apply_patch_to_copy_repairs_mismatched_hunk_counts(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_bytes(b"def run():\n    return 1\n")

    result = apply_patch_to_copy(tmp_path, MALFORMED_COUNT_PATCH, expected_file="sample.py")

    with ZipFile(BytesIO(result.zip_bytes)) as archive:
        assert archive.read("sample.py") == b"def run():\n    return 2\n"


def test_patch_rejects_path_traversal() -> None:
    unsafe = PATCH.replace("sample.py", "../secrets.py")

    with pytest.raises(PatchError):
        apply_unified_patch_to_text("def run():\n    return 1\n", unsafe)
