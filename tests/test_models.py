from codereview_agent.models import ReviewMetadata, ReviewReport
from openai.lib._pydantic import to_strict_json_schema


def test_review_report_contract() -> None:
    report = ReviewReport(summary="ok", score=90)
    assert report.issues == []
    assert report.score == 90
    assert isinstance(report.metadata, ReviewMetadata)
    assert report.metadata.model_dump() == {
        "project": "",
        "mode": "",
        "files_reviewed": "",
        "model": "",
    }


def test_review_metadata_has_fixed_fields() -> None:
    metadata = ReviewMetadata(project="demo", mode="llm", files_reviewed="1", model="test-model")

    assert metadata.model_dump() == {
        "project": "demo",
        "mode": "llm",
        "files_reviewed": "1",
        "model": "test-model",
    }


def test_review_report_strict_schema_contains_only_fixed_metadata_properties() -> None:
    schema = to_strict_json_schema(ReviewReport)
    metadata_schema = schema["$defs"]["ReviewMetadata"]

    assert set(metadata_schema["properties"]) == {"project", "mode", "files_reviewed", "model"}
    assert metadata_schema["required"] == ["project", "mode", "files_reviewed", "model"]
    assert metadata_schema["additionalProperties"] is False
