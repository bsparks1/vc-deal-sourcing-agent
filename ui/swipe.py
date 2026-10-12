# The swipeable company card on the Explore page, built as a small custom Streamlit component
# (HTML + CSS + JavaScript). Drag the card right for "interested" or left for "pass"; when it's
# thrown far enough, the JavaScript tells Python which way with setTriggerValue("swiped", ...).
# Company text is inserted with textContent (never innerHTML), because it comes from web pages
# and an LLM, and must never be treated as code.

import streamlit as st

CSS = """
.card { position: relative; padding: 22px 24px; border-radius: 16px; cursor: grab;
  border: 1px solid rgba(128,128,128,.3); background: var(--st-secondary-background-color, #f6f6f9);
  color: var(--st-text-color, inherit); user-select: none; touch-action: pan-y;
  box-shadow: 0 8px 24px rgba(0,0,0,.12); transition: transform .25s ease, opacity .25s ease; }
.card.dragging { transition: none; cursor: grabbing; }
.top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.name { font-size: 1.6rem; font-weight: 700; line-height: 1.2; }
.score { font-size: 1.5rem; font-weight: 700; white-space: nowrap; }
.score.high { color: #16a34a; } .score.mid { color: #ca8a04; } .score.low { color: #dc2626; }
.liner { margin: 10px 0 12px; font-size: 1.05rem; opacity: .9; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.chip { font-size: .8rem; padding: 3px 10px; border-radius: 999px; background: rgba(128,128,128,.15); }
.highlights { margin: 0; padding-left: 18px; font-size: .95rem; }
.highlights li { margin: 3px 0; }
.stamp { position: absolute; top: 18px; font-size: 1.3rem; font-weight: 800; padding: 4px 12px;
  border: 3px solid; border-radius: 8px; opacity: 0; transform: rotate(-12deg); }
.stamp.yes { left: 18px; color: #16a34a; } .stamp.no { right: 18px; color: #dc2626; transform: rotate(12deg); }
.hint { text-align: center; font-size: .8rem; opacity: .6; margin-top: 8px; }
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
  top.append(make('div', 'score ' + level, data.score + '/100'));
  card.append(top, make('div', 'liner', data.one_liner));
  const chips = make('div', 'chips');
  data.chips.forEach(text => chips.append(make('span', 'chip', text)));
  const list = make('ul', 'highlights');
  data.highlights.forEach(text => list.append(make('li', '', text)));
  card.append(chips, list, make('div', 'stamp yes', 'INTERESTED'), make('div', 'stamp no', 'PASS'));
  root.append(card, make('div', 'hint', 'Drag the card right if interested, left to pass'));
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


def card_data(company: dict) -> dict:
    """The few facts shown on the card itself; everything else is in "More detail"."""
    chips = [company.get("category"), company.get("stage"), company.get("location"),
             f"Founded {company['founded_year']}" if company.get("founded_year") else None]
    founders = [f["name"] if isinstance(f, dict) else f for f in company.get("founders") or []]
    highlights = [company.get("funding_summary")] + (company.get("traction") or [])[:3]
    if founders:
        highlights.append("Founders: " + ", ".join(founders[:3]))
    return {
        "name": company["name"], "score": company["score_total"] or 0,
        "one_liner": company.get("one_liner") or "",
        "chips": [str(c) for c in chips if c], "highlights": [str(h) for h in highlights if h],
    }


def swipe_card(company: dict) -> str | None:
    """Show the card. Returns 'right' or 'left' on the run right after a swipe, else None."""
    result = _swipe_component(
        data=card_data(company),
        key=f"swipe_{company['id']}",  # a new key per company gives each card a fresh start
        on_swiped_change=lambda: None,  # registers "swiped" as a value Python listens for
    )
    return result.swiped
