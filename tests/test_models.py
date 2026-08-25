from codereview_agent.models import ReviewReport


def test_review_report_contract() -> None:
    report = ReviewReport(summary="ok", score=90)
    assert report.issues == []
    assert report.score == 90

