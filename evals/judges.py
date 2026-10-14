# The two LLM-as-judge evaluators that check the agent's saved companies (Build Step 10):
#   early_stage        - is this company actually early-stage? (the v1 failure mode)
#   founders_supported - are the saved founder facts backed by their source pages?
# Each judge gathers its own evidence from the web, so it checks the agent's work instead of
# just re-reading the agent's own claims. Used by evals/run_evals.py via Phoenix evals.

import json
from typing import Literal

from langchain_anthropic import ChatAnthropic
from phoenix.evals import Score, create_evaluator
from pydantic import BaseModel

from scout import config
from scout.web import get_tavily_client

# Per source page shown to a judge. Must be at least what the agent and founder research saw
# (PAGE_MAX_CHARS): with a shorter cut, the judge missed a founder named halfway down an
# article and wrongly marked a correct claim "unsupported".
PAGE_CHARS = config.PAGE_MAX_CHARS
# How many cited pages the founders judge reads. It was 4, and the Step 11 baseline showed
# the cost: founders citing 5-7 pages had correct claims marked "not provided" because the
# judge never opened the later pages. 8 covers every company in that baseline.
FOUNDER_PAGES = 8


class Verdict(BaseModel):
    """What a judge must return: one label from a fixed list, plus its reasoning."""

    label: str
    explanation: str


class EarlyStageVerdict(Verdict):
    label: Literal["early_stage", "not_early_stage", "unclear"]


class FoundersVerdict(Verdict):
    label: Literal["supported", "partially_supported", "unsupported"]


def read_pages(urls: list[str], limit: int = 3) -> str:
    """Fetch up to `limit` pages and return their text, each labelled with its URL."""
    if not urls:
        return "(no source pages)"
    try:
        response = get_tavily_client().extract(urls=urls[:limit], format="text")
    except Exception as error:  # one bad URL shouldn't stop the whole eval
        return f"(could not read source pages: {error})"
    pages = [f"URL: {p['url']}\n{(p.get('raw_content') or '')[:PAGE_CHARS]}"
             for p in response.get("results", [])]
    return "\n\n".join(pages) or "(source pages could not be read)"


# [A12 Evals] The judge gathers its own evidence instead of re-reading the agent's claims.
def independent_search(name: str) -> str:
    """Search for funding/retail news about the company: evidence the agent may have missed."""
    response = get_tavily_client().search(
        query=f'"{name}" funding OR raised OR investors OR retail OR stores', max_results=5)
    return "\n\n".join(f"URL: {r['url']}\n{r.get('content', '')}"
                       for r in response.get("results", []))


# [A6 Structured output] Each verdict is a fixed label plus an explanation.
def ask_judge(prompt: str, verdict_type: type[Verdict]) -> Verdict:
    """Send one judging prompt to Claude and get back a structured verdict."""
    llm = ChatAnthropic(model=config.MODEL, api_key=config.ANTHROPIC_API_KEY,
                        max_tokens=config.SCORING_MAX_TOKENS)
    # Same structured-output method as scoring.py: Sonnet 5.5 rejects the forced tool call
    # that Phoenix's built-in Anthropic judge uses, so we make the call ourselves.
    return llm.with_structured_output(verdict_type, method="json_schema").invoke(prompt)


EARLY_STAGE_PROMPT = """You are auditing an AI research agent for a pre-seed/seed venture fund.
The agent said this company is a very early-stage startup. Decide whether that's true.

Early-stage means: launched recently (roughly the last 2 years), little or no outside funding
(no priced VC round), small footprint (DTC or a few local stores, not national retail), and
not part of or owned by a larger company. Judge from the EVIDENCE, not from the agent's claims.
Use "unclear" only if the evidence genuinely can't settle it.

COMPANY: {name} ({domain})
AGENT'S CLAIMS: stage={stage}; funding={funding}; traction={traction}

EVIDENCE FROM THE AGENT'S SOURCES:
{source_text}

EVIDENCE FROM AN INDEPENDENT SEARCH:
{search_text}
"""

FOUNDERS_PROMPT = """You are auditing an AI research agent. Check whether each founder claim
below is supported by the source pages it cites. A claim is supported only if the pages say
it; general plausibility doesn't count.

Labels: "supported" (every claim backed), "partially_supported" (names right but some role or
background details not in the sources), "unsupported" (a founder isn't shown as a founder of
this company in the sources). Say which claims failed in your explanation.

COMPANY: {name}
FOUNDER CLAIMS:
{claims}

SOURCE PAGES:
{source_text}
"""

EARLY_SCORES = {"early_stage": 1.0, "unclear": 0.5, "not_early_stage": 0.0}
FOUNDER_SCORES = {"supported": 1.0, "partially_supported": 0.5, "unsupported": 0.0}


# [A12 Evals] LLM-as-judge for the v1 failure mode: is this company really early-stage?
@create_evaluator(name="early_stage", kind="llm")
def early_stage(name: str, domain: str, stage: str, funding: str, traction: str,
                sources: list) -> Score:
    """Judge whether the company is truly early-stage, using its sources plus a fresh search."""
    prompt = EARLY_STAGE_PROMPT.format(
        name=name, domain=domain, stage=stage, funding=funding, traction=traction,
        source_text=read_pages(sources), search_text=independent_search(name))
    verdict = ask_judge(prompt, EarlyStageVerdict)
    return Score(score=EARLY_SCORES[verdict.label], label=verdict.label,
                 explanation=verdict.explanation)


@create_evaluator(name="founders_supported", kind="llm")
def founders_supported(name: str, founders: list) -> Score:
    """Judge whether the saved founder facts are backed by the pages they cite."""
    # Only founders saved from Step 9 on carry sources; older plain-text entries can't be checked.
    checkable = [f for f in founders if isinstance(f, dict)]
    if not checkable:
        # No LLM call needed: nothing to check. score=None keeps it out of the averages.
        return Score(score=None, label="no_founders", explanation="No sourced founders saved.")

    urls = list(dict.fromkeys(url for f in checkable for url in f["source_urls"]))  # unique, in order
    claims = json.dumps([{k: f[k] for k in ("name", "role", "background", "source_urls")}
                         for f in checkable], indent=2)
    verdict = ask_judge(FOUNDERS_PROMPT.format(name=name, claims=claims,
                                               source_text=read_pages(urls, limit=FOUNDER_PAGES)),
                        FoundersVerdict)
    return Score(score=FOUNDER_SCORES[verdict.label], label=verdict.label,
                 explanation=verdict.explanation)
