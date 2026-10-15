# Scores one company against the fund's thesis using the 100-point rubric from SPEC.md.
# This is a separate, focused LLM call (not the agent itself) that must answer in a fixed
# JSON shape, so every company is judged the same way and scores are easy to store and compare.
# The agent reaches it through the score_against_thesis tool in scout/tools.py.

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from scout import config

# The rubric: dimension -> maximum points. Totals 100.
RUBRIC_MAX = {"thesis_fit": 30, "stage_fit": 25, "product": 20, "team": 15, "market": 10}


class ScoreBreakdown(BaseModel):
    """Points for each rubric dimension. The descriptions are shown to the model."""

    thesis_fit: int = Field(description="0-30. Category and product match the fund's thesis.")
    stage_fit: int = Field(
        description="0-25. Truly early: little/no outside funding, small footprint, recent launch. "
        "Give 0-5 to established companies (national retail, priced VC rounds, big brands)."
    )
    product: int = Field(description="0-20. Differentiation and quality signals.")
    team: int = Field(description="0-15. Founder-market fit, relevant background. 7 if unknown.")
    market: int = Field(description="0-10. Category growth and tailwinds.")


class CompanyScore(BaseModel):
    """The full answer the model must return: scores, reasons, and red flags."""

    breakdown: ScoreBreakdown
    rationale: str = Field(description="2-4 sentences explaining the scores, citing the facts used.")
    exclusion_signals_found: list[str] = Field(
        description="Any of the fund's exclusion signals that the facts show. Empty list if none."
    )


SYSTEM_PROMPT = """You are a venture analyst scoring one company for this fund.

FUND PROFILE
Fund: {fund_name}
Thesis: {thesis}
Target categories:
{categories}
Stages: {stages}
Signals to look for:
{include_signals}
Signals that rule a company out:
{exclude_signals}

RUBRIC (100 points)
- thesis_fit (0-30): category and product match the thesis
- stage_fit (0-25): truly early. Heavily penalize established companies
- product (0-20): differentiation, quality signals
- team (0-15): founder-market fit, relevant background
- market (0-10): category growth and tailwinds

RULES
- Use only the facts provided. Never invent facts.
- When a dimension can't be judged from the facts, give about half its maximum points (neutral).
- If the facts show any exclusion signal, list it and score stage_fit 5 or lower.
"""


def clamp_scores(breakdown: ScoreBreakdown) -> dict:
    """Return the breakdown as a dict, with each score forced into 0..max.

    The model is told the ranges but could still return e.g. 32 for thesis_fit;
    clamping in code guarantees the total can never go above 100.
    """
    return {
        dimension: max(0, min(getattr(breakdown, dimension), maximum))
        for dimension, maximum in RUBRIC_MAX.items()
    }


def score_company(company_facts: str, profile: dict) -> dict:
    """Score one company against the fund profile and return the result as a dict.

    company_facts is plain text the agent gathered (what it makes, funding, traction,
    founders, with source URLs). The returned keys match the companies table columns.
    """
    config.require_keys()

    llm = ChatAnthropic(
        model=config.MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=config.SCORING_MAX_TOKENS,
        # Medium effort keeps scoring quick; the rubric and code rules do the heavy lifting.
        output_config={"effort": config.AGENT_EFFORT},
        # If the model's safety filter wrongly declines a request, Anthropic re-runs it on a
        # suitable fallback model inside the same call, instead of returning an empty answer.
        betas=["server-side-fallback-2026-07-01"],
        model_kwargs={"fallbacks": "default"},
    )
    # "json_schema" uses Anthropic's native structured outputs: the API guarantees the reply
    # matches CompanyScore's JSON schema, and LangChain turns it into a CompanyScore object.
    # [A6 Structured output] The API guarantees the reply matches the CompanyScore schema.
    scorer = llm.with_structured_output(CompanyScore, method="json_schema")

    # Fill the {placeholders} in the prompt; "or ''" avoids printing "None" for empty fields.
    system = SYSTEM_PROMPT.format(**{key: profile.get(key) or "" for key in [
        "fund_name", "thesis", "categories", "stages", "include_signals", "exclude_signals",
    ]})
    result: CompanyScore = scorer.invoke([
        ("system", system),
        ("user", f"Score this company.\n\nFACTS:\n{company_facts}"),
    ])

    # [A5 Guardrails in code] The model judges; code enforces ranges, adds the total, and caps it.
    breakdown = clamp_scores(result.breakdown)
    # The total is added up in code, not by the model, so it always equals the parts.
    total = sum(breakdown.values())
    # Hard rule: a company showing any exclusion signal can't rank as a good lead, however
    # well it fits the category. Without this, a famous brand still scored ~57/100 in testing.
    if result.exclusion_signals_found:
        total = min(total, config.EXCLUDED_SCORE_CAP)

    return {
        "score_total": total,
        "score_breakdown": breakdown,
        "rationale": result.rationale,
        "exclusion_signals_found": result.exclusion_signals_found,
    }
