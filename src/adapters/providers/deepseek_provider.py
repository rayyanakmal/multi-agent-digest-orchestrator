"""DeepSeek LLM provider adapter"""

from src.adapters.llm_service import LLMAdapter, SummaryRequest, SummaryResponse, DigestCompositionRequest, DigestCompositionResponse
import requests
import json
from typing import Optional


class DeepSeekAdapter(LLMAdapter):
    """Adapter for DeepSeek API"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1", model: str = "deepseek-chat"):
        """Initialize DeepSeek adapter
        
        Args:
            api_key: DeepSeek API key
            base_url: DeepSeek API base URL
            model: Model name (e.g., 'deepseek-chat')
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def summarize_article(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize an article using DeepSeek API"""
        # A1: Truncate input content to 1500 chars to reduce token overhead.
        # Most relevant info is in the first 1500 chars; full articles waste tokens.
        truncated_content = request.content[:1500]
        if len(request.content) > 1500:
            truncated_content = truncated_content.rsplit(' ', 1)[0] + "..."
        
        prompt = f"""You are a senior intelligence analyst for developers in Hong Kong.

Return ONLY valid JSON with this schema:
{{
  "summary": "70-120 words plain English summary",
  "key_points": ["point 1", "point 2", "point 3"],
  "strategic_why": "why this matters for a developer in Hong Kong",
  "category": "research|tooling|infrastructure|vertical|hardware|security|general",
  "confidence": 0.0
}}

Rules:
- summary must be 70-120 words.
- strategic_why is mandatory and concrete.
- key_points should be 2-3 concise bullets.
- confidence must be between 0 and 1.

Article to analyze:

Title: {request.title}

Content:
{truncated_content}
"""

        response_data = self._call_api(prompt)
        
        # Extract summary
        summary = response_data.get("summary", "")
        strategic_why = response_data.get(
            "strategic_why",
            "This matters because it affects implementation choices for engineers shipping AI products in Hong Kong.",
        )
        category = response_data.get("category", "general")
        confidence = response_data.get("confidence", 0.7)
        tokens_used = response_data.get("tokens_used", 0)
        cost_usd = response_data.get("cost_usd", 0.0)

        key_points = response_data.get("key_points") or []
        if not isinstance(key_points, list):
            key_points = []
        key_points = [str(point).strip() for point in key_points if str(point).strip()][:3]
        if not key_points:
            key_points = [sentence.strip() for sentence in summary.split(".") if sentence.strip()][:3]

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))

        return SummaryResponse(
            summary=summary,
            key_points=key_points,
            strategic_why=strategic_why,
            category=category,
            confidence=confidence,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )

    def compose_digest(self, request: DigestCompositionRequest) -> DigestCompositionResponse:
        """Compose a final digest from article summaries using DeepSeek API"""
        summaries_text = "\n\n".join([
            f"- {s.summary}" for s in request.summaries
        ])
        
        prompt = f"""Based on these article summaries about {request.topic}, 
provide:
1. Top 3 key takeaways (bullet points)
2. A watchlist item (what to watch tomorrow)

Summaries:
{summaries_text}

Format your response as:
KEY TAKEAWAYS:
- [takeaway 1]
- [takeaway 2]
- [takeaway 3]

WATCHLIST:
[watchlist item]"""

        response_data = self._call_api(prompt)
        
        takeaways_text = response_data.get("takeaways", "")
        watchlist_text = response_data.get("watchlist", "")
        tokens_used = response_data.get("tokens_used", 0)
        cost_usd = response_data.get("cost_usd", 0.0)
        
        # Parse takeaways
        takeaways = [line.strip() for line in takeaways_text.split("\n") 
                    if line.strip() and line.strip().startswith("-")]
        takeaways = [t.lstrip("-").strip() for t in takeaways][:3]

        return DigestCompositionResponse(
            takeaways=takeaways,
            watchlist=watchlist_text,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )

    def get_provider_name(self) -> str:
        """Return provider name"""
        return "deepseek"

    def _call_api(self, prompt: str) -> dict:
        """Call DeepSeek API and return structured response
        
        Args:
            prompt: The prompt to send to DeepSeek
            
        Returns:
            dict: Response with keys: 'summary', 'takeaways', 'watchlist', 'tokens_used', 'cost_usd'
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful news analyst. Provide concise, actionable insights."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "max_tokens": 350
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content from API response
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            
            # Estimate cost: DeepSeek pricing ~$0.0005 per 1K tokens for chat
            cost_usd = (tokens_used / 1000) * 0.0005
            
            # Parse response sections
            summary = content
            takeaways = ""
            watchlist = ""

            # Try structured JSON first (for summarize_article prompts).
            structured = {}
            cleaned_content = content.strip()
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content.strip("`")
                if cleaned_content.startswith("json"):
                    cleaned_content = cleaned_content[4:].strip()

            try:
                if cleaned_content.startswith("{") and cleaned_content.endswith("}"):
                    structured = json.loads(cleaned_content)
            except json.JSONDecodeError:
                structured = {}
            
            if "KEY TAKEAWAYS:" in content:
                parts = content.split("WATCHLIST:")
                if len(parts) == 2:
                    takeaways = parts[0].replace("KEY TAKEAWAYS:", "").strip()
                    watchlist = parts[1].strip()
                else:
                    takeaways = parts[0].replace("KEY TAKEAWAYS:", "").strip()
            
            return {
                "summary": structured.get("summary", summary),
                "key_points": structured.get("key_points", []),
                "strategic_why": structured.get(
                    "strategic_why",
                    "This matters because it affects implementation choices for engineers shipping AI products in Hong Kong.",
                ),
                "category": structured.get("category", "general"),
                "confidence": structured.get("confidence", 0.7),
                "takeaways": takeaways,
                "watchlist": watchlist,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd
            }
        except requests.exceptions.RequestException as e:
            # Return a safe default on API failure
            return {
                "summary": "Unable to summarize due to API error. Please try again.",
                "key_points": [],
                "strategic_why": "This matters because outages in model providers can disrupt automated intelligence pipelines for teams in Hong Kong.",
                "category": "general",
                "confidence": 0.3,
                "takeaways": "",
                "watchlist": "",
                "tokens_used": 0,
                "cost_usd": 0.0
            }
