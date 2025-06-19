import re
from ingest import clean_summary


def test_clean_summary_strips_html_and_truncates():
    entry = {
        "summary": (
            "<div><p>This <b>is</b> <i>HTML</i> &amp; <span>more</span>. "
            "<img src='x.jpg'/>Another sentence with extra words.</p></div>"
        )
    }
    result = clean_summary(entry, char_limit=40)
    assert not re.search(r"<[^>]+>", result)
    assert "&amp;" not in result
    assert len(result) <= 41
    if len(result) > 40:
        assert result.endswith("…")
