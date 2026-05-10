"""Regression tests for digest spacing and typography improvements."""

import re
from src.agents.publish_digest import DigestFormatterAgent
from src.models.contracts import DigestOutput, SummaryItem


def test_html_output_has_correct_line_height():
    """Verify HTML output uses line-height: 1.5 for body text."""
    digest = DigestOutput(
        title="Test Digest",
        date="2026-05-09",
        top_takeaways=["Takeaway 1", "Takeaway 2"],
        article_summaries=[],
        watchlist="Test watchlist",
        metadata={"source": "test"},
        layout_pages=[
            {
                "page": 1,
                "title": "Test Page",
                "sections": {
                    "executive_snapshot": ["Snapshot 1"],
                    "trending_github_repos": [],
                    "paper_of_the_day": None,
                    "source": "test source",
                },
            }
        ],
    )
    
    html = DigestFormatterAgent.digest_to_html(digest)
    
    # Check that line-height is 1.5 in body CSS
    assert "line-height: 1.5;" in html, "Body should have line-height: 1.5"
    # Verify it's not the old 1.6
    assert "line-height: 1.6;" not in html, "Body should not have old line-height: 1.6"


def test_html_output_font_family_order():
    """Verify font-family prioritizes text fonts over emoji fonts."""
    digest = DigestOutput(
        title="Test Digest",
        date="2026-05-09",
        top_takeaways=["Takeaway 1"],
        article_summaries=[],
        watchlist="Test watchlist",
        metadata={"source": "test"},
        layout_pages=[
            {
                "page": 1,
                "title": "Test",
                "sections": {"executive_snapshot": [], "trending_github_repos": [], "paper_of_the_day": None, "source": "test"},
            }
        ],
    )
    
    html = DigestFormatterAgent.digest_to_html(digest)
    
    # Extract the font-family declaration
    font_family_match = re.search(r'font-family:\s*"([^"]+)"(?:,\s*"([^"]+)")*(?:,\s*([^;]+));', html)
    assert font_family_match, "Should find font-family declaration in CSS"
    
    css_snippet = re.search(r'font-family:\s*([^;]+);', html).group(1)
    
    # Check that text fonts come first
    avenir_idx = css_snippet.find("Avenir Next")
    segoe_ui_idx = css_snippet.find('"Segoe UI"')
    emoji_idx = css_snippet.find("Apple Color Emoji")
    
    assert avenir_idx >= 0, "Should have Avenir Next in font stack"
    assert emoji_idx >= 0, "Should have emoji fonts as fallback"
    assert avenir_idx < emoji_idx, "Text fonts (Avenir) should come before emoji fonts"


def test_html_css_spacing_values():
    """Verify critical CSS spacing values match reference style."""
    digest = DigestOutput(
        title="Test",
        date="2026-05-09",
        top_takeaways=["Test"],
        article_summaries=[],
        watchlist="Test",
        metadata={"test": "value"},
        layout_pages=[
            {
                "page": 1,
                "title": "Test",
                "sections": {"executive_snapshot": [], "trending_github_repos": [], "paper_of_the_day": None, "source": "test"},
            }
        ],
    )
    
    html = DigestFormatterAgent.digest_to_html(digest)
    
    # Verify key spacing tokens
    assert ".takeaways { background: #eef4f1; border-left: 4px solid var(--accent); padding: 8px 12px; margin-bottom: 12px; }" in html, \
        "Takeaways should have reduced padding (8px 12px) and margin-bottom (12px)"
    
    assert ".page-block { background: var(--page-bg); padding: 14px 16px;" in html, \
        "Page-block should have reduced padding (14px 16px)"
    
    assert ".page-head { border-bottom: 2px solid var(--accent); margin-bottom: 10px; padding-bottom: 5px; }" in html, \
        "Page-head should have tightened margin-bottom (10px) and padding-bottom (5px)"
    
    assert ".snapshot { background: #eef4f1; border-left: 3px solid var(--accent); padding: 7px 10px; margin-bottom: 8px; }" in html, \
        "Snapshot should have reduced padding (7px 10px) and margin-bottom (8px)"


def test_markdown_output_spacing_consistency():
    """Verify markdown output has consistent blank-line spacing between sections."""
    digest = DigestOutput(
        title="Test Digest",
        date="2026-05-09",
        top_takeaways=["Takeaway 1", "Takeaway 2"],
        article_summaries=[
            SummaryItem(
                url="https://example.com",
                title="Test Article",
                summary="Test summary",
                source="Test Source",
                category="general",
                strategic_why="Strategic reason",
                confidence=0.9,
            )
        ],
        watchlist="Test watchlist",
        metadata={"source": "test"},
        layout_pages=[],  # Use flat layout for markdown
    )
    
    markdown = DigestFormatterAgent.digest_to_markdown(digest)
    
    # Check that markdown has proper structure without excessive blank lines
    lines = markdown.split("\n")
    
    # Find consecutive blank lines (should be minimal)
    consecutive_blanks = 0
    max_consecutive_blanks = 0
    for line in lines:
        if line.strip() == "":
            consecutive_blanks += 1
            max_consecutive_blanks = max(max_consecutive_blanks, consecutive_blanks)
        else:
            consecutive_blanks = 0
    
    # Allow up to 2 consecutive blank lines but not more
    assert max_consecutive_blanks <= 2, \
        f"Markdown should not have excessive blank lines (found {max_consecutive_blanks})"


def test_markdown_includes_section_headers():
    """Verify markdown output includes proper section headers."""
    digest = DigestOutput(
        title="Test Digest",
        date="2026-05-09",
        top_takeaways=["Takeaway 1"],
        article_summaries=[],
        watchlist="Watchlist content",
        metadata={"source": "test"},
        layout_pages=[],
    )
    
    markdown = DigestFormatterAgent.digest_to_markdown(digest)
    
    # Verify key sections are present
    assert "## Key Takeaways" in markdown, "Should have Key Takeaways section"
    assert "## Article Briefs" in markdown, "Should have Article Briefs section"
    assert "## Watchlist" in markdown, "Should have Watchlist section"
    assert "## Metadata" in markdown, "Should have Metadata section"
