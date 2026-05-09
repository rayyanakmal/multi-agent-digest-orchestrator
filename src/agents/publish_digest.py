"""Digest formatting and publishing agent"""

from datetime import datetime
from html import escape
from typing import Optional
from src.agents.base_agent import BaseAgent
from src.models.contracts import AgentMessage, DigestOutput, SummaryItem, RunContext


class DigestFormatterAgent(BaseAgent):
    """Formats digest output for publication"""

    def __init__(self):
        """Initialize digest formatter agent"""
        super().__init__("digest_formatter")

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Format digest for publication
        
        Args:
            context: Run context
            input_data: Should contain 'summaries' list
            
        Returns:
            AgentMessage: Result with formatted digest
        """
        msg = self.create_message(context, "format_digest")
        
        try:
            summaries_data = input_data.get("summaries", [])
            summaries = [SummaryItem(**s) for s in summaries_data]
            
            digest = self._create_digest(summaries, context)
            
            return msg.with_success(
                payload=digest.model_dump(),
                metadata={
                    "article_count": len(summaries),
                    "formatted": True
                }
            )
        except Exception as e:
            return msg.with_error(f"Digest formatting failed: {str(e)}")

    def _create_digest(self, summaries: list[SummaryItem], context: RunContext) -> DigestOutput:
        """Create formatted digest from summaries
        
        Args:
            summaries: List of summarized articles
            context: Run context with metadata
            
        Returns:
            DigestOutput: Formatted digest
        """
        # Extract top takeaways from summaries (prioritize strategic why statements)
        takeaways = [s.strategic_why for s in summaries[:3] if s.strategic_why]
        if len(takeaways) < 3:
            takeaways.extend([s.summary for s in summaries[: (3 - len(takeaways))]])
        
        # Create title
        today = datetime.utcnow().strftime("%Y-%m-%d")
        title = f"Daily AI and Technology Digest - {today}"
        
        # Create watchlist
        watchlist = (
            "Monitor model governance shifts, infrastructure cost volatility, and"
            " fast-moving open-source tooling changes that can alter build vs buy decisions."
        )

        layout_pages = self._build_layout_pages(summaries, today, context)
        executive_snapshot = [
            "Developer velocity remains tied to tooling maturity, not just model quality.",
            "Infrastructure announcements are outpacing most teams' integration readiness.",
            "Open-source repos continue to be leading indicators for practical agent patterns.",
            "Security and policy constraints are becoming architecture decisions, not legal afterthoughts.",
            "Teams that pair fast experimentation with observability are shipping faster with less rework.",
        ]
        
        # Create digest
        digest = DigestOutput(
            title=title,
            date=today,
            top_takeaways=takeaways,
            article_summaries=summaries,
            watchlist=watchlist,
            layout_pages=layout_pages,
            executive_snapshot=executive_snapshot,
            metadata={
                "source_count": context.fetch_count,
                "deduplicated_count": context.deduplicated_count,
                "summarized_count": context.summarized_count,
                "run_time_sec": (datetime.utcnow() - context.start_time).total_seconds(),
                "cost_usd": context.budget_spent_usd,
                "provider": "deepseek"  # TODO: Get from context
            }
        )
        
        return digest

    def _build_layout_pages(self, summaries: list[SummaryItem], date: str, context: RunContext) -> list[dict]:
        """Build the Technical Architect 5-page layout from flat summaries."""
        rotation_map = {
            "Monday": "Healthcare",
            "Tuesday": "Fintech",
            "Wednesday": "Robotics",
            "Thursday": "Cybersecurity",
            "Friday": "Climate/Energy",
            "Saturday": "Education",
            "Sunday": "Open Source",
        }
        weekday = datetime.utcnow().strftime("%A")
        vertical = rotation_map.get(weekday, "Open Source")

        github_items = [s for s in summaries if "github" in s.url.lower() or "github" in s.source.lower()][:5]
        paper_item = next((s for s in summaries if "arxiv" in s.url.lower() or "arxiv" in s.source.lower()), None)

        tooling_items = [
            s for s in summaries
            if s.category in {"tooling", "infrastructure"}
            or any(k in (s.title + " " + s.summary).lower() for k in ["api", "sdk", "framework", "aws", "azure", "gcp", "vertex", "bedrock"])
        ][:6]

        vertical_keywords = {
            "Healthcare": ["health", "medical", "hospital", "diagnostic", "biotech"],
            "Fintech": ["fintech", "bank", "payment", "fraud", "trading"],
            "Robotics": ["robot", "autonomous", "drone", "manipulation"],
            "Cybersecurity": ["security", "vulnerability", "cve", "threat", "malware"],
            "Climate/Energy": ["energy", "climate", "grid", "battery", "carbon"],
            "Education": ["education", "learning", "school", "student", "classroom"],
            "Open Source": ["open source", "github", "oss", "repo", "license"],
        }
        selected_vertical_keywords = vertical_keywords.get(vertical, [])
        vertical_items = [
            s for s in summaries
            if any(k in (s.title + " " + s.summary).lower() for k in selected_vertical_keywords)
        ][:5]

        hardware_items = [
            s for s in summaries
            if s.category in {"hardware", "infrastructure"}
            or any(k in (s.title + " " + s.summary).lower() for k in ["semiconductor", "foundry", "tsmc", "intel", "samsung", "edge", "iot", "chip", "gpu"])
        ][:6]

        # Fallback population so each page has content even when sources are sparse.
        fallback = [s for s in summaries if s not in github_items and s not in tooling_items and s not in vertical_items and s not in hardware_items]
        if not github_items:
            github_items = fallback[:3]
        if not paper_item:
            paper_item = fallback[3] if len(fallback) > 3 else (fallback[0] if fallback else None)
        if not tooling_items:
            tooling_items = fallback[:4]
        if not vertical_items:
            vertical_items = fallback[4:8] if len(fallback) > 7 else fallback[:4]
        if not hardware_items:
            hardware_items = fallback[8:12] if len(fallback) > 11 else fallback[:4]

        all_links = [
            {"title": s.title, "url": s.url, "source": s.source, "priority": "Must Read" if i < 10 else "Skim Later"}
            for i, s in enumerate(summaries[:20])
        ]

        return [
            {
                "page": 1,
                "title": "The Daily Sprints (Code & Research)",
                "sections": {
                    "executive_snapshot": [
                        "Model capabilities are improving, but integration maturity remains the bottleneck.",
                        "Repo activity indicates strong momentum around practical agent frameworks.",
                        "Research velocity is high; production relevance depends on tooling readiness.",
                        "Infrastructure announcements should be evaluated against latency and cost constraints.",
                        "Teams with strong evaluation loops are converting insights into shippable features faster.",
                    ],
                    "trending_github_repos": [s.model_dump() for s in github_items[:5]],
                    "paper_of_the_day": paper_item.model_dump() if paper_item else None,
                    "source": "GitHub Trending, arXiv cs.AI",
                },
            },
            {
                "page": 2,
                "title": "System Design & Tooling",
                "sections": {
                    "tool_of_the_day": tooling_items[0].model_dump() if tooling_items else None,
                    "infrastructure_updates": [s.model_dump() for s in tooling_items[1:6]],
                    "source": "AWS ML Blog, Azure AI, Google Cloud AI",
                },
            },
            {
                "page": 3,
                "title": "Specialized Industry Vertical",
                "sections": {
                    "rotation": vertical,
                    "case_study": vertical_items[0].model_dump() if vertical_items else None,
                    "supporting_items": [s.model_dump() for s in vertical_items[1:5]],
                    "source": "VentureBeat, The Verge and domain sources",
                },
            },
            {
                "page": 4,
                "title": "Global Tech & Hardware",
                "sections": {
                    "semiconductors": [
                        s.model_dump()
                        for s in hardware_items
                        if any(k in (s.title + " " + s.summary).lower() for k in ["semiconductor", "foundry", "tsmc", "intel", "samsung", "chip", "gpu"])
                    ][:4],
                    "edge_ai": [
                        s.model_dump()
                        for s in hardware_items
                        if any(k in (s.title + " " + s.summary).lower() for k in ["edge", "iot", "mobile processor", "on-device"])
                    ][:4],
                    "source": "Reuters Technology, Nikkei Asia (Tech), hardware wires",
                },
            },
            {
                "page": 5,
                "title": "Code Snippets & Metadata",
                "sections": {
                    "daily_code_hack": (
                        "LangChain pattern: chain a retrieval step with a strict JSON parser so"
                        " every summary includes category, strategic_why, and confidence fields"
                        " before rendering."
                    ),
                    "scout_metadata": {
                        "sources_scanned": context.fetch_count,
                        "deduplicated": context.deduplicated_count,
                        "summarized": context.summarized_count,
                        "cost_usd": context.budget_spent_usd,
                        "generated_at": date,
                    },
                    "index_of_links": all_links,
                },
            },
        ]

    @staticmethod
    def digest_to_markdown(digest: DigestOutput) -> str:
        """Convert digest to markdown format
        
        Args:
            digest: Formatted digest
            
        Returns:
            str: Markdown representation
        """
        md_lines = [f"# {digest.title}", ""]

        if digest.layout_pages:
            for page in digest.layout_pages:
                page_no = page.get("page")
                page_title = page.get("title", "Untitled")
                sections = page.get("sections", {})

                md_lines.extend([f"---", f"## Page {page_no}: {page_title}", ""])

                if page_no == 1:
                    md_lines.append("### Executive Snapshot")
                    for line in sections.get("executive_snapshot", []):
                        md_lines.append(f"- {line}")
                    md_lines.extend(["", "### Trending GitHub Repos", ""])
                    for item in sections.get("trending_github_repos", []):
                        md_lines.extend(DigestFormatterAgent._render_item_block(item))
                    md_lines.extend(["", "### Paper of the Day", ""])
                    pod = sections.get("paper_of_the_day")
                    if pod:
                        md_lines.extend(DigestFormatterAgent._render_item_block(pod))

                elif page_no == 2:
                    md_lines.extend(["### Tool of the Day", ""])
                    tool = sections.get("tool_of_the_day")
                    if tool:
                        md_lines.extend(DigestFormatterAgent._render_item_block(tool))
                    md_lines.extend(["", "### Infrastructure", ""])
                    for item in sections.get("infrastructure_updates", []):
                        md_lines.extend(DigestFormatterAgent._render_item_block(item))

                elif page_no == 3:
                    md_lines.append(f"### The Rotation: {sections.get('rotation', 'General')}")
                    md_lines.extend(["", "### Case Study", ""])
                    case_study = sections.get("case_study")
                    if case_study:
                        md_lines.extend(DigestFormatterAgent._render_item_block(case_study))
                    md_lines.extend(["", "### Supporting Signals", ""])
                    for item in sections.get("supporting_items", []):
                        md_lines.extend(DigestFormatterAgent._render_item_block(item))

                elif page_no == 4:
                    md_lines.extend(["### Semiconductors", ""])
                    semis = sections.get("semiconductors", [])
                    for item in semis:
                        md_lines.extend(DigestFormatterAgent._render_item_block(item))
                    md_lines.extend(["", "### Edge AI", ""])
                    for item in sections.get("edge_ai", []):
                        md_lines.extend(DigestFormatterAgent._render_item_block(item))

                elif page_no == 5:
                    md_lines.extend(["### Daily Prompt / Code Hack", sections.get("daily_code_hack", ""), ""])
                    md_lines.extend(["### Scout Metadata", ""])
                    metadata = sections.get("scout_metadata", {})
                    for key, value in metadata.items():
                        md_lines.append(f"- {key}: {value}")
                    md_lines.extend(["", "### Index of Links", ""])
                    links = sections.get("index_of_links", [])
                    md_lines.append("#### Must Read")
                    for link in [l for l in links if l.get("priority") == "Must Read"]:
                        md_lines.append(f"- [{link.get('title')}]({link.get('url')}) ({link.get('source')})")
                    md_lines.extend(["", "#### Skim Later"])
                    for link in [l for l in links if l.get("priority") == "Skim Later"]:
                        md_lines.append(f"- [{link.get('title')}]({link.get('url')}) ({link.get('source')})")

                source_line = sections.get("source")
                if source_line:
                    md_lines.extend(["", f"Source lane: {source_line}", ""])

            return "\n".join(md_lines)

        md_lines.extend(["## Key Takeaways", ""])
        for takeaway in digest.top_takeaways:
            md_lines.append(f"- {takeaway}")
        md_lines.extend(["", "## Article Briefs", ""])
        for summary in digest.article_summaries:
            md_lines.append(f"### {summary.title}")
            md_lines.append(f"**Source:** {summary.source}")
            md_lines.append(f"**Summary:** {summary.summary}")
            if summary.key_points:
                md_lines.append("**Key Points:**")
                for point in summary.key_points:
                    md_lines.append(f"  - {point}")
            md_lines.append(f"**Strategic Why (HK):** {summary.strategic_why}")
            md_lines.append(f"[Read More]({summary.url})")
            md_lines.append("")
        md_lines.extend(["## Watchlist", f"{digest.watchlist}", ""])
        md_lines.append("## Metadata")
        for key, value in digest.metadata.items():
            md_lines.append(f"- {key}: {value}")
        return "\n".join(md_lines)

    @staticmethod
    def digest_to_html(digest: DigestOutput) -> str:
        """Convert digest to HTML format
        
        Args:
            digest: Formatted digest
            
        Returns:
            str: HTML representation
        """
        pages_html = []
        for page in digest.layout_pages:
            page_no = page.get("page")
            page_title = escape(str(page.get("title", "Untitled")))
            sections = page.get("sections", {})
            page_emoji = DigestFormatterAgent._page_emoji(page_no)

            blocks = [f'<section class="page-block"><div class="page-head"><div class="kicker">Page {page_no}</div><h2>{page_emoji} {page_title}</h2></div>']

            if page_no == 1:
                bullets = "".join(
                    [f"<li>{escape(str(b))}</li>" for b in sections.get("executive_snapshot", [])]
                )
                blocks.append(f'<div class="snapshot"><h3>Executive Snapshot</h3><ul>{bullets}</ul></div>')
                blocks.append('<h3>Trending GitHub Repos</h3>')
                for item in sections.get("trending_github_repos", []):
                    blocks.append(DigestFormatterAgent._render_html_item_card(item, lane="Sprint", lane_emoji="⚡"))
                pod = sections.get("paper_of_the_day")
                if pod:
                    blocks.append('<h3>Paper of the Day</h3>')
                    blocks.append(DigestFormatterAgent._render_html_item_card(pod, lane="Research", lane_emoji="🔬"))

            elif page_no == 2:
                blocks.append('<h3>Tool of the Day</h3>')
                tool = sections.get("tool_of_the_day")
                if tool:
                    blocks.append(DigestFormatterAgent._render_html_item_card(tool, lane="Tooling", lane_emoji="🛠️"))
                blocks.append('<h3>Infrastructure Updates</h3>')
                for item in sections.get("infrastructure_updates", []):
                    blocks.append(DigestFormatterAgent._render_html_item_card(item, lane="Infrastructure", lane_emoji="☁️"))

            elif page_no == 3:
                rotation = escape(str(sections.get("rotation", "General")))
                blocks.append(f'<div class="rotation">Vertical Rotation: <strong>{rotation}</strong></div>')
                case_study = sections.get("case_study")
                if case_study:
                    blocks.append('<h3>Case Study</h3>')
                    blocks.append(DigestFormatterAgent._render_html_item_card(case_study, lane="Case Study", lane_emoji="🧭"))
                blocks.append('<h3>Supporting Signals</h3>')
                for item in sections.get("supporting_items", []):
                    blocks.append(DigestFormatterAgent._render_html_item_card(item, lane="Vertical", lane_emoji="📌"))

            elif page_no == 4:
                blocks.append('<h3>Semiconductors</h3>')
                for item in sections.get("semiconductors", []):
                    blocks.append(DigestFormatterAgent._render_html_item_card(item, lane="Hardware", lane_emoji="🧠"))
                blocks.append('<h3>Edge AI</h3>')
                for item in sections.get("edge_ai", []):
                    blocks.append(DigestFormatterAgent._render_html_item_card(item, lane="Edge", lane_emoji="📡"))

            elif page_no == 5:
                hack = escape(str(sections.get("daily_code_hack", "")))
                blocks.append(f'<div class="code-block"><h3>Daily Prompt / Code Hack</h3><p>{hack}</p></div>')

                metadata = sections.get("scout_metadata", {})
                blocks.append('<h3>Scout Metadata</h3><div class="meta-grid">')
                for key, value in metadata.items():
                    blocks.append(
                        f'<div class="meta-row"><span class="meta-key">{escape(str(key)).replace("_", " ")}</span><span class="meta-value">{escape(str(value))}</span></div>'
                    )
                blocks.append('</div>')

                links = sections.get("index_of_links", [])
                must_read = [l for l in links if l.get("priority") == "Must Read"]
                skim = [l for l in links if l.get("priority") == "Skim Later"]
                blocks.append('<div class="link-list">')
                blocks.append('<h3>Must Read</h3><ul>')
                for item in must_read:
                    blocks.append(
                        f'<li><a href="{escape(str(item.get("url", "")))}">{ escape(str(item.get("title", "Untitled")))}</a> <span class="src">({escape(str(item.get("source", "Unknown")))})</span></li>'
                    )
                blocks.append('</ul>')
                blocks.append('<h3>Skim Later</h3><ul>')
                for item in skim:
                    blocks.append(
                        f'<li><a href="{escape(str(item.get("url", "")))}">{ escape(str(item.get("title", "Untitled")))}</a> <span class="src">({escape(str(item.get("source", "Unknown")))})</span></li>'
                    )
                blocks.append('</ul></div>')

            source_lane = sections.get("source")
            if source_lane:
                blocks.append(f'<div class="source-lane">Source lane: {escape(str(source_lane))}</div>')

            blocks.append('</section>')
            pages_html.append("\n".join(blocks))

        top_takeaways = "".join([f"<li>{escape(str(t))}</li>" for t in digest.top_takeaways[:3]])
        metadata_strip = " &nbsp;·&nbsp; ".join(
            [
                f'<strong>{escape(str(k)).replace("_", " ")}:</strong> {escape(str(v))}'
                for k, v in digest.metadata.items()
            ]
        )
        pages_joined = "\n".join(pages_html)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(digest.title)}</title>
  <style>
    :root {{
      --ink: #1a1a1a;
      --muted: #6b7280;
      --accent: #0b5d5c;
      --warn-bg: #fff8ed;
      --warn-border: #c07820;
      --border: #e2e6e3;
      --page-bg: #fafaf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f5f4f0; color: var(--ink); font-family: "Avenir Next", "Segoe UI", system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 24px 20px 48px; }}
    .hero {{ padding: 16px 0 12px; border-bottom: 2px solid var(--accent); margin-bottom: 16px; }}
    .hero h1 {{ margin: 0; font-size: 26px; color: var(--ink); line-height: 1.2; }}
    .hero .sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
    .strip {{ margin-top: 6px; font-size: 11px; color: var(--muted); }}
    .takeaways {{ background: #eef4f1; border-left: 4px solid var(--accent); padding: 10px 14px; margin-bottom: 16px; }}
    .takeaways h3 {{ margin: 0 0 5px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--accent); }}
    .takeaways ul {{ margin: 0; padding-left: 16px; }}
    .takeaways li {{ margin: 3px 0; font-size: 13px; }}
    .page-block {{ background: var(--page-bg); padding: 16px 18px; margin-top: 0; break-before: page; page-break-before: always; }}
    .page-block:first-of-type {{ break-before: auto; page-break-before: auto; }}
    .page-head {{ border-bottom: 2px solid var(--accent); margin-bottom: 12px; padding-bottom: 6px; }}
    .kicker {{ color: var(--muted); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; }}
    .page-head h2 {{ margin: 2px 0 0; font-size: 20px; }}
    h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--accent); margin: 12px 0 5px; break-after: avoid-page; page-break-after: avoid; }}
    .snapshot {{ background: #eef4f1; border-left: 3px solid var(--accent); padding: 8px 12px; margin-bottom: 10px; }}
    .snapshot h3 {{ margin: 0 0 4px; }}
    .snapshot ul {{ margin: 0; padding-left: 16px; }}
    .snapshot li {{ margin: 2px 0; font-size: 13px; }}
    .rotation {{ border-left: 3px solid #c07820; padding: 6px 10px; margin-bottom: 10px; font-size: 13px; color: #5f3c08; background: var(--warn-bg); }}
    .entry {{ break-inside: avoid; page-break-inside: avoid; padding: 2px 0; }}
    .entry h4 {{ margin: 0 0 1px; font-size: 15px; line-height: 1.3; }}
    .meta {{ font-size: 11px; color: var(--muted); margin: 0 0 4px; }}
    .entry p {{ margin: 3px 0 4px; font-size: 13px; }}
    .strategic {{ background: var(--warn-bg); border-left: 3px solid var(--warn-border); padding: 5px 10px; margin: 4px 0; font-size: 12px; break-inside: avoid; page-break-inside: avoid; }}
    .strategic strong {{ color: #6b3a00; }}
    .entry ul {{ margin: 3px 0 4px; padding-left: 18px; }}
    .entry ul li {{ font-size: 12px; margin: 1px 0; }}
    .entry a {{ font-size: 12px; color: var(--accent); text-decoration: none; }}
    .entry-rule {{ border: none; border-top: 1px solid var(--border); margin: 6px 0; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin: 6px 0; }}
    .meta-row {{ font-size: 12px; }}
    .meta-key {{ color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em; display: block; }}
    .meta-value {{ font-weight: 600; display: block; }}
    .link-list ul {{ margin: 4px 0 0; padding-left: 16px; }}
    .link-list li {{ margin: 2px 0; font-size: 12px; }}
    .src {{ color: var(--muted); font-size: 11px; }}
    .source-lane {{ margin-top: 8px; font-size: 11px; color: var(--muted); border-top: 1px dashed var(--border); padding-top: 6px; }}
    .code-block {{ background: #eef3f5; border-left: 3px solid var(--accent); padding: 8px 12px; font-size: 12px; margin: 6px 0; }}
        @media screen and (max-width: 720px) {{
      .container {{ padding: 16px 12px 40px; }}
      .hero h1 {{ font-size: 20px; }}
      .page-head h2 {{ font-size: 17px; }}
            .meta-grid {{ grid-template-columns: 1fr; }}
    }}
    @media print {{
      body {{ background: #ffffff; }}
      .container {{ max-width: none; margin: 0; padding: 0; }}
      .page-block {{ background: #ffffff; }}
    }}
    @page {{ size: A4; margin: 14mm; }}
  </style>
</head>
<body>
  <div class="container">
    <header class="hero">
      <h1>{escape(digest.title)}</h1>
      <div class="sub">Technical Architect Briefing | {escape(digest.date)}</div>
      <div class="strip">{metadata_strip}</div>
    </header>

    <section class="takeaways">
      <h3>Top Strategic Takeaways</h3>
      <ul>{top_takeaways}</ul>
    </section>

        {pages_joined}
  </div>
</body>
</html>
"""

    @staticmethod
    def _render_item_block(item: dict) -> list[str]:
        """Render a digest entry block with mandatory Strategic Why section."""
        lines = []
        title = item.get("title", "Untitled")
        source = item.get("source", "Unknown")
        summary = item.get("summary", "No summary available")
        strategic_why = item.get(
            "strategic_why",
            "This matters because it affects implementation choices for engineers shipping AI products in Hong Kong.",
        )
        url = item.get("url", "")

        lines.append(f"#### {title}")
        lines.append(f"**Source:** {source}")
        lines.append(f"**Summary:** {summary}")
        lines.append(f"**Strategic Why (HK):** {strategic_why}")
        if item.get("key_points"):
            lines.append("**Key Points:**")
            for point in item.get("key_points", [])[:3]:
                lines.append(f"- {point}")
        if url:
            lines.append(f"[Read More]({url})")
        lines.append("")
        return lines

    @staticmethod
    def _render_html_item_card(item: dict, lane: str, lane_emoji: str = "📰") -> str:
        """Render one article entry block for HTML output (minimalist)."""
        title = escape(str(item.get("title", "Untitled")))
        source = escape(str(item.get("source", "Unknown")))
        summary = escape(str(item.get("summary", "No summary available")))
        strategic_why = escape(
            str(
                item.get(
                    "strategic_why",
                    "This matters because it affects implementation choices for engineers shipping AI products.",
                )
            )
        )
        url = escape(str(item.get("url", "")))
        confidence = item.get("confidence", 0.7)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.7
        confidence_label = "High" if confidence_value >= 0.8 else "Med" if confidence_value >= 0.55 else "Low"
        emoji = DigestFormatterAgent._contextual_emoji(item)

        key_points_html = ""
        points = item.get("key_points", [])
        if isinstance(points, list) and points:
            points_html = "".join([f"<li>{escape(str(point))}</li>" for point in points[:3]])
            key_points_html = f"<ul>{points_html}</ul>"

        link_html = f'<a href="{url}">→ Source</a>' if url else ""

        return (
            '<article class="entry">'
            f'<h4>{emoji} {title}</h4>'
            f'<div class="meta">{source} · Confidence: {confidence_label}</div>'
            f'<p>{summary}</p>'
            f'<div class="strategic"><strong>Strategic Why:</strong> {strategic_why}</div>'
            f'{key_points_html}'
            f'{link_html}'
            '</article>'
            '<hr class="entry-rule">'
        )

    @staticmethod
    def _contextual_emoji(item: dict) -> str:
        """Pick a contextual emoji from item content."""
        text = (
            str(item.get("title", "")) + " " +
            str(item.get("summary", "")) + " " +
            str(item.get("category", ""))
        ).lower()
        if any(k in text for k in ["github", "repo", "open source", "oss", "repository"]):
            return "📦"
        if any(k in text for k in ["arxiv", "research", "paper", "study", "academic"]):
            return "🔬"
        if any(k in text for k in ["security", "cve", "vulnerability", "threat", "malware", "breach"]):
            return "🔐"
        if any(k in text for k in ["chip", "gpu", "semiconductor", "tsmc", "foundry", "hardware", "processor"]):
            return "💾"
        if any(k in text for k in ["robot", "autonomous", "drone", "manipulation"]):
            return "🤖"
        if any(k in text for k in ["health", "medical", "hospital", "diagnostic", "biotech"]):
            return "🏥"
        if any(k in text for k in ["fintech", "bank", "payment", "fraud", "trading"]):
            return "💳"
        if any(k in text for k in ["climate", "energy", "grid", "battery", "carbon"]):
            return "🌱"
        if any(k in text for k in ["sdk", "api", "framework", "toolkit", "library", "aws", "azure", "gcp", "bedrock", "vertex"]):
            return "🔧"
        if any(k in text for k in ["model", "llm", "agent", "inference", "training", "fine-tun"]):
            return "🧠"
        if any(k in text for k in ["edge", "iot", "on-device", "mobile processor"]):
            return "📡"
        return "📰"

    @staticmethod
    def _page_emoji(page_no: int) -> str:
        """Small emoji taxonomy for quick visual orientation."""
        mapping = {
            1: "🚀",
            2: "🏗️",
            3: "🧭",
            4: "🌐",
            5: "🧪",
        }
        return mapping.get(page_no, "📰")
