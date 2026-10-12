# The swipeable company card on the Explore page, built as a small custom Streamlit component
# (HTML + CSS + JavaScript). Drag the card right for "interested" or left for "pass"; when it's
# thrown far enough, the JavaScript tells Python which way with setTriggerValue("swiped", ...).
# Company text is inserted with textContent (never innerHTML), because it comes from web pages
# and an LLM, and must never be treated as code.

import streamlit as st

# Styled to Scout's design system: a near-square card with a hairline border, tabular score,
# square tags, 6px square list markers, and desaturated colors. The --st-* variables are
# Streamlit's own theme colors, so the card follows dark or light mode automatically.
CSS = """
.card { position: relative; padding: 24px 26px 22px; border-radius: 2px; cursor: grab;
  border: 1px solid var(--st-border-color, rgba(128,128,128,.25));
  background: var(--st-secondary-background-color, #121418); color: var(--st-text-color, #fdfcfb);
  font-family: Inter, sans-serif; user-select: none; touch-action: pan-y;
  transition: transform .25s ease, opacity .25s ease; }
.card.dragging { transition: none; cursor: grabbing; }
.eyebrow { font-family: 'Geist Mono', monospace; font-size: .7rem; letter-spacing: .16em;
  text-transform: uppercase; color: #3F8A64; margin-bottom: 10px; }
.top { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
.name { font-size: 1.75rem; font-weight: 600; line-height: 1.15; letter-spacing: -.02em; }
.score { font-size: 1.75rem; font-weight: 600; white-space: nowrap; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; }
.score small { font-size: .85rem; font-weight: 500; opacity: .5; margin-left: 2px; }
.score.high { color: #6E9C7E; } .score.mid { color: #B8955E; } .score.low { color: #B5716A; }
.liner { margin: 10px 0 16px; font-size: 1rem; line-height: 1.5; opacity: .82; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.chip { font-size: .75rem; padding: 3px 8px; border-radius: 2px;
  border: 1px solid var(--st-border-color, rgba(128,128,128,.25)); opacity: .85; }
.rule { height: 1px; background: var(--st-border-color, rgba(128,128,128,.25)); margin: 0 0 14px; }
.highlights { margin: 0; padding: 0; list-style: none; font-size: .92rem; line-height: 1.5; }
.highlights li { position: relative; padding-left: 18px; margin: 5px 0; }
.highlights li::before { content: ""; position: absolute; left: 0; top: .55em; width: 6px; height: 6px;
  background: #3F8A64; }
.stamp { position: absolute; top: 20px; font-family: 'Geist Mono', monospace; font-size: .85rem;
  font-weight: 500; letter-spacing: .16em; padding: 5px 10px; border: 1.5px solid; border-radius: 2px;
  opacity: 0; }
.stamp.yes { left: 20px; color: #6E9C7E; } .stamp.no { right: 20px; color: #B5716A; }
.hint { text-align: center; font-family: 'Geist Mono', monospace; font-size: .7rem;
  letter-spacing: .12em; text-transform: uppercase; opacity: .45; margin-top: 10px; }
"""

JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  parentElement.querySelectorAll('.swipe-root').forEach(el => el.remove());  // clear old card

  const make = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;  // textContent: shown as text, never run
    return el;
  };
  const root = make('div', 'swipe-root');
  const card = make('div', 'card');
  const top = make('div', 'top');
  top.append(make('div', 'name', data.name));
  const level = data.score >= 75 ? 'high' : data.score >= 60 ? 'mid' : 'low';
  const score = make('div', 'score ' + level, String(data.score));
  score.append(make('small', '', '/100'));
  top.append(score);
  card.append(make('div', 'eyebrow', 'Match ' + data.position), top, make('div', 'liner', data.one_liner));
  const chips = make('div', 'chips');
  data.chips.forEach(text => chips.append(make('span', 'chip', text)));
  const list = make('ul', 'highlights');
  data.highlights.forEach(text => list.append(make('li', '', text)));
  card.append(chips, make('div', 'rule'), list, make('div', 'stamp yes', 'INTERESTED'),
              make('div', 'stamp no', 'PASS'));
  root.append(card, make('div', 'hint', 'Drag right to watch  /  left to pass'));
  parentElement.append(root);

  // Follow the pointer while dragging; tilt the card and fade in the matching stamp.
  let startX = null, dx = 0;
  const yes = card.querySelector('.yes'), no = card.querySelector('.no');
  card.addEventListener('pointerdown', e => {
    startX = e.clientX; card.classList.add('dragging'); card.setPointerCapture(e.pointerId);
  });
  card.addEventListener('pointermove', e => {
    if (startX === null) return;
    dx = e.clientX - startX;
    card.style.transform = `translateX(${dx}px) rotate(${dx / 20}deg)`;
    yes.style.opacity = Math.max(0, dx / 120); no.style.opacity = Math.max(0, -dx / 120);
  });
  card.addEventListener('pointerup', () => {
    if (startX === null) return;
    startX = null; card.classList.remove('dragging');
    if (Math.abs(dx) > 120) {  // thrown far enough: fly off screen, then tell Python
      const direction = dx > 0 ? 'right' : 'left';
      card.style.transform = `translateX(${dx > 0 ? 900 : -900}px) rotate(${dx / 10}deg)`;
      card.style.opacity = 0;
      setTimeout(() => setTriggerValue('swiped', direction), 220);
    } else {  // not far enough: snap back to the middle
      card.style.transform = ''; yes.style.opacity = 0; no.style.opacity = 0;
    }
    dx = 0;
  });
}
"""

# Registered once when this file is imported (not on every rerun), as Streamlit recommends.
_swipe_component = st.components.v2.component("scout_swipe_card", css=CSS, js=JS)


def card_data(company: dict, position: str) -> dict:
    """The few facts shown on the card itself; everything else is in "More detail"."""
    chips = [company.get("category"), company.get("stage"), company.get("location"),
             f"Founded {company['founded_year']}" if company.get("founded_year") else None]
    founders = [f["name"] if isinstance(f, dict) else f for f in company.get("founders") or []]
    highlights = [company.get("funding_summary")] + (company.get("traction") or [])[:3]
    if founders:
        highlights.append("Founders: " + ", ".join(founders[:3]))
    return {
        "name": company["name"], "score": company["score_total"] or 0, "position": position,
        "one_liner": company.get("one_liner") or "",
        "chips": [str(c) for c in chips if c], "highlights": [str(h) for h in highlights if h],
    }


def swipe_card(company: dict, position: str = "") -> str | None:
    """Show the card. Returns 'right' or 'left' on the run right after a swipe, else None.

    position is a short label for the card's eyebrow, like "1 of 6".
    """
    result = _swipe_component(
        data=card_data(company, position),
        key=f"swipe_{company['id']}",  # a new key per company gives each card a fresh start
        on_swiped_change=lambda: None,  # registers "swiped" as a value Python listens for
    )
    return result.swiped
