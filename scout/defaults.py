# The default fund profile template (Brand Project, from Scout v1; see SPEC.md).
# The Fund Profile page pre-fills its form with this until the user saves their own profile.
# List-like fields are plain text with one item per line, matching how the form shows them.

DEFAULT_FUND_PROFILE = {
    "fund_name": "Brand Project",
    "thesis": (
        "Pre-seed and seed investor in consumer packaged goods (CPG). We back founder-led "
        "brands very early, before national retail and before any priced VC round. "
        "When uncertain whether a company is truly early-stage, exclude it."
    ),
    "categories": "\n".join([
        "Functional food & beverage",
        "Better-for-you snacks",
        "Indie beauty & personal care",
        "Supplements & wellness",
    ]),
    "stages": "Pre-seed\nSeed",
    "check_size": "",  # not in the spec, so left for the user to fill in rather than guessed
    "include_signals": "\n".join([
        "Under ~10k Instagram followers",
        "Launched in the last 18 months",
        "DTC or 1-2 local retailers",
        "No funding announcements",
        "Founder-led",
    ]),
    "exclude_signals": "\n".join([
        "National retail (Whole Foods, Target, Costco, ...)",
        "Any priced VC round",
        "Over 50k followers",
        "Major press coverage",
        "Brands you recognize (e.g. Poppi, Olipop, Liquid Death)",
    ]),
    "daily_target": 3,
    # Scheduled runs spend API credits on their own, so they start switched off.
    "schedule_enabled": 0,
    "schedule_hour": 9,
}
