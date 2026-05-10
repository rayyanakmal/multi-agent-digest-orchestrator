"""Regression tests for emoji presence across digest output formats."""

from src.agents.publish_digest import DigestFormatterAgent
from src.models.contracts import DigestOutput, SummaryItem


def build_summary(title: str, summary: str = "Example summary") -> SummaryItem:
    return SummaryItem(
        url="https://example.com/story",
        title=title,
        summary=summary,
        key_points=["point one"],
        source="Example Source",
        category="tooling",
        strategic_why="This matters for the test.",
    )


def test_markdown_layout_includes_page_and_item_emoji():
    tool_item = build_summary("LangChain async agent framework")
    digest = DigestOutput(
        title="Daily AI and Technology Digest - 2026-05-10",
        date="2026-05-10",
        top_takeaways=[],
        article_summaries=[tool_item],
        watchlist="Watch this",
        metadata={},
        layout_pages=[
            {
                "page": 2,
                "title": "System Design & Tooling",
                "sections": {
                    "tool_of_the_day": tool_item.model_dump(),
                    "infrastructure_updates": [],
                    "source": "Test Source",
                },
            }
        ],
        executive_snapshot=[],
    )

    markdown = DigestFormatterAgent.digest_to_markdown(digest)

    assert "## Page 2: 🏗️ System Design & Tooling" in markdown
    assert "#### 🔧 LangChain async agent framework" in markdown


def test_markdown_non_layout_briefs_include_contextual_emoji():
    repo_item = build_summary(
        "Top GitHub repository for AI agents",
        summary="Open source repository gains traction.",
    )
    digest = DigestOutput(
        title="Daily AI and Technology Digest - 2026-05-10",
        date="2026-05-10",
        top_takeaways=["One takeaway"],
        article_summaries=[repo_item],
        watchlist="Watch this",
        metadata={},
        layout_pages=[],
        executive_snapshot=[],
    )

    markdown = DigestFormatterAgent.digest_to_markdown(digest)

    assert "### 📦 Top GitHub repository for AI agents" in markdown


def test_html_uses_emoji_capable_font_fallbacks():
    tool_item = build_summary("LangChain async agent framework")
    digest = DigestOutput(
        title="Daily AI and Technology Digest - 2026-05-10",
        date="2026-05-10",
        top_takeaways=[],
        article_summaries=[tool_item],
        watchlist="Watch this",
        metadata={},
        layout_pages=[
            {
                "page": 2,
                "title": "System Design & Tooling",
                "sections": {
                    "tool_of_the_day": tool_item.model_dump(),
                    "infrastructure_updates": [],
                    "source": "Test Source",
                },
            }
        ],
        executive_snapshot=[],
    )

    html = DigestFormatterAgent.digest_to_html(digest)

    assert "Noto Color Emoji" in html
    assert "Apple Color Emoji" in html
    assert "<h2>🏗️ System Design &amp; Tooling</h2>" in html
