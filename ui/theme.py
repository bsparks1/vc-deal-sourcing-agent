# The parts of Scout's design system that Streamlit's theme settings can't express:
# page titles (a small uppercase "eyebrow" over a large "display" title), tabular score numbers,
# and 6px square list markers; plus making dark the default. Colors, fonts and corner radii
# live in .streamlit/config.toml.
# Styles here use the current text color with opacity, so they work in dark and light mode.

import html

import streamlit as st

ACCENT = "#3F8A64"  # forest green, lifted slightly so it reads on both dark and light grounds

CSS = f"""
<style>
/* Page title: eyebrow over display-md */
.sc-eyebrow {{ font-family: 'Geist Mono', monospace; font-size: .72rem; font-weight: 500;
  letter-spacing: .16em; text-transform: uppercase; color: {ACCENT}; margin: 0 0 .5rem; }}
.sc-display {{ font-family: Inter, sans-serif; font-weight: 600; font-size: 2.25rem;
  line-height: 1.1; letter-spacing: -.022em; margin: 0; }}
.sc-subtitle {{ opacity: .62; margin: .5rem 0 0; font-size: .95rem; }}
.sc-header {{ padding-bottom: 1.1rem; margin-bottom: 1.4rem; border-bottom: 1px solid rgba(128,128,128,.22); }}

/* Section headings (st.subheader): small, tight, editorial */
h3 {{ letter-spacing: -.01em; }}

/* stat-num: scores and counts use tabular figures so digits line up */
[data-testid="stMetricValue"], .sc-stat {{ font-variant-numeric: tabular-nums; letter-spacing: -.02em; }}
[data-testid="stMetricLabel"] p {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .1em; opacity: .62; }}

/* Lists: a 6px square marker instead of a bullet */
[data-testid="stMarkdownContainer"] ul {{ list-style: none; padding-left: 1.15rem; }}
[data-testid="stMarkdownContainer"] ul li {{ position: relative; }}
[data-testid="stMarkdownContainer"] ul li::before {{ content: ""; position: absolute; left: -1.1rem;
  top: .62em; width: 6px; height: 6px; background: {ACCENT}; }}

/* Tighter, quieter captions */
[data-testid="stCaptionContainer"] {{ opacity: .7; }}
</style>
"""


# Dark by default, light by choice. Streamlit offers System / Light / Dark in its menu, but with
# a light theme defined it starts on "System" (following the computer's setting). On a browser's
# first visit this script saves "Dark" (the same value Streamlit saves when you click Dark),
# records that it did so, and reloads. After that it never runs again, so a later choice of
# Light or System is kept. Note: the theme key is a Streamlit internal and could change.
DARK_BY_DEFAULT_JS = """
<script>
  if (localStorage.getItem("scout-dark-default") === null) {
    localStorage.setItem("scout-dark-default", "done");
    localStorage.setItem("stActiveTheme-/-v2", JSON.stringify("Dark"));
    location.reload();
  }
</script>
"""


def apply_theme() -> None:
    """Add Scout's extra styles to the page, and default new visitors to dark mode.

    Called once per page view from app.py.
    """
    st.html(CSS)
    # Our own fixed script (no user data in it), so allowing JavaScript here is safe.
    st.html(DARK_BY_DEFAULT_JS, unsafe_allow_javascript=True)


def page_header(eyebrow: str, title: str, subtitle: str | None = None) -> None:
    """The standard page title: a small uppercase label over a large title.

    Titles can contain user or web data (fund and company names), so they're escaped:
    shown as text, never treated as HTML.
    """
    sub = f'<p class="sc-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    st.html(f'<div class="sc-header"><p class="sc-eyebrow">{html.escape(eyebrow)}</p>'
            f'<div class="sc-display">{html.escape(title)}</div>{sub}</div>')
