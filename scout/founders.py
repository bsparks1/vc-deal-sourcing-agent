# Researches a company's founding team: who they are, their roles, and their backgrounds.
# Two web searches gather evidence, one LLM call extracts founders in a fixed shape, and code
# then checks that every founder is backed by a URL we actually fetched. Used by the
# research_founders tool (scout/tools.py) and the "Research founders" button on the Company page.

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from scout import config
from scout.web import get_tavily_client


class Founder(BaseModel):
    """One founder, as extracted from the search results."""

    name: str
    role: str = Field(description='e.g. "Co-founder & CEO". Empty string if the sources don\'t say.')
    background: str = Field(
        description="1-2 sentences on prior experience, only as stated in the sources. "
        "Empty string if the sources don't say."
    )
    source_urls: list[str] = Field(description="The URLs (from the results given) that support this.")


class FounderResearch(BaseModel):
    """The full answer the model must return."""

    founders: list[Founder]
    notes: str = Field(description="One sentence on what couldn't be found or confirmed.")


EXTRACT_PROMPT = """From the search results below, list the founders of {company_name} ({domain}).

Rules:
- Only include people the results explicitly describe as a founder or co-founder of THIS
  company. Ignore people with the same name at other companies.
- Use only what the results say. Never fill gaps from your own knowledge.
- For each founder, list the result URLs that support it. Use URLs exactly as given.
- Use role titles exactly as a result states them for that person.
- Don't silently join facts from different results about what might be the same person
  (e.g. "Mary, Co-Founder" on the company site and "Mary Peck launched the brand" in an
  article). If you do link them, say so in the background, e.g. "Named as co-founder
  'Mary' on the company site; full name from Atlanta Magazine", so a reader can check it.
- If no founder is named, return an empty list and say so in notes.

SEARCH RESULTS:
{evidence}
"""


def gather_evidence(company_name: str, domain: str, extra_urls: list[str]) -> list[dict]:
    """Run two founder-focused web searches, plus read any pages the agent already saw
    mentioning founders, and return the unique results (url, title, text)."""
    queries = [
        f'"{company_name}" founder',
        f"{company_name} {domain} co-founder background experience",
    ]
    results = {}  # keyed by URL, so a page found by both searches appears once
    client = get_tavily_client()
    for query in queries:
        # "advanced" depth costs more than "basic" but returns more relevant text per result,
        # which matters here: founder details are usually one line deep inside a page.
        response = client.search(query=query, max_results=config.SEARCH_MAX_RESULTS,
                                 search_depth="advanced")
        for item in response.get("results", []):
            results[item["url"]] = {"url": item["url"], "title": item.get("title", ""),
                                    "text": item.get("content", "")}
    if extra_urls:
        # Pages the agent already found that name a founder. Searches don't always surface
        # them again, so read them directly (at most 3, each cut to PAGE_MAX_CHARS).
        try:
            response = client.extract(urls=extra_urls[:3], format="text")
        except Exception:
            response = {}  # a bad URL shouldn't throw away the search results we already have
        for item in response.get("results", []):
            results[item["url"]] = {"url": item["url"], "title": "",
                                    "text": (item.get("raw_content") or "")[: config.PAGE_MAX_CHARS]}
    return list(results.values())


def research_founders(company_name: str, domain: str, extra_urls: list[str] | None = None) -> dict:
    """Find the company's founders and return them as a dict with sourced facts.

    Returns {"founders": [{"name", "role", "background", "source_urls"}], "notes": str,
    "sources_checked": [urls]}. Every founder kept has at least one real source URL.
    """
    config.require_keys()
    evidence = gather_evidence(company_name, domain, extra_urls or [])
    if not evidence:
        return {"founders": [], "notes": "Web search returned nothing.", "sources_checked": []}

    evidence_text = "\n\n".join(
        f"URL: {item['url']}\nTITLE: {item['title']}\n{item['text']}" for item in evidence
    )
    llm = ChatAnthropic(model=config.MODEL, api_key=config.ANTHROPIC_API_KEY,
                        max_tokens=config.SCORING_MAX_TOKENS)
    extractor = llm.with_structured_output(FounderResearch, method="json_schema")
    result: FounderResearch = extractor.invoke(EXTRACT_PROMPT.format(
        company_name=company_name, domain=domain, evidence=evidence_text))

    # Code check: keep only source URLs that were really in the search results (a model can
    # mistype or invent a URL), and drop any founder left with no real source at all.
    # [A5 Guardrails in code] Verify citations: keep only URLs we actually fetched, drop unsourced founders.
    fetched = {item["url"] for item in evidence}
    founders = []
    for founder in result.founders:
        real_sources = [url for url in founder.source_urls if url in fetched]
        if real_sources:
            founders.append({**founder.model_dump(), "source_urls": real_sources})

    return {"founders": founders, "notes": result.notes, "sources_checked": sorted(fetched)}


def describe_founder(founder) -> str:
    """One readable line for a founder. Handles both the new dict format and the plain
    strings saved before Step 9."""
    if isinstance(founder, str):
        return founder
    parts = [founder["name"], founder.get("role"), founder.get("background")]
    return " - ".join(part for part in parts if part)
