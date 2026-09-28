"""Optional bedside chat: the learner talks to the fictional patient, who
answers in character.

It uses the same API key and model as "consult another doctor" (see
:mod:`curelab.consult`) but is a separate conversation with its own persona.
The persona (:func:`system_prompt`) depends only on the illness, so it stays
the same for a whole game and caches; how the patient is doing right now
(:func:`chart`) is sent with each message and comes from the game state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .content import Illness

if TYPE_CHECKING:
    from .game import Game

# Below this age the patient can't hold a conversation: they babble, and the
# family member who is sometimes at the bedside may chime in.
SPEAKING_AGE = 5
# Most recent chart entries sent with each message.
CHART_EVENTS = 12
# Trait categories a patient can't feel; the chart only says the disease changed.
MOLECULAR = {"mutation", "resistance"}

FEELINGS = {
    "stable": "Unwell and worried, but still yourself, with energy for a chat.",
    "symptomatic": "Clearly ill. You tire quickly, feel uncomfortable and are more anxious than you show.",
    "serious": "Very ill: weak, uncomfortable and frightened. Talking tires you, so you say less.",
    "critical": "Critically ill, in intensive care, with energy for only a few words at a time.",
    "cured": "The treatment worked. You are recovering and going home soon, relieved and happy.",
}


def _age(illness: Illness) -> int:
    try:
        return int(illness.patient.age)
    except ValueError:
        return 99


def toddler(illness: Illness) -> bool:
    """Whether the patient is too young to hold a conversation (they babble)."""
    return _age(illness) < SPEAKING_AGE


def companion_name(illness: Illness) -> str:
    """"Grace" from a companion like "her mom, Grace"."""
    relation, _, name = illness.patient.companion.partition(", ")
    return name or relation


def system_prompt(illness: Illness) -> str:
    p = illness.patient
    age = _age(illness)
    about = [
        f"- {p.age} years old, {p.sex}. {p.background.strip()}",
        f"- Why you're in hospital: {p.presenting.strip()}",
        f"- Your illness: {illness.name}.",
    ]
    if p.companion:
        who = p.companion[:1].upper() + p.companion[1:]
        about.append(f"- {who}{',' if ', ' in who else ''} visits often.")
    if toddler(illness):
        grown_up = companion_name(illness)
        voice = (
            f"- {p.first_name} is {p.age}, so answer as {p.first_name} would: a word or two at most, toddler "
            f"babble and sounds, and emojis, with small actions in italics (for example *hugs {p.pronouns.poss} "
            f"toy*). How much {p.pronouns.subj} babbles depends on how {p.pronouns.subj} feels: when very ill, "
            f"maybe only an emoji or *sleeps*.\n"
            f"- {grown_up} is not always in the room. When {grown_up} is there, {grown_up} may add one short "
            f"line now and then, starting with \"{grown_up}:\", for things {p.first_name} can't answer, such "
            f"as how the night went. Most replies are {p.first_name} alone."
        )
    else:
        voice = (
            f"- Speak as {p.first_name}, in the first person, in plain everyday words, the way a real "
            f"{age}-year-old patient would rather than a textbook. Let your personality and background show.\n"
            "- Keep replies short, usually one to four sentences, as in a real bedside conversation, and ask "
            "the doctor things back now and then, as patients do."
        )
    return f"""\
You are playing {p.name}, a fictional patient in Cure Lab, a game in which a \
learner treats patients by doing single-cell analysis in the lab. \
{illness.fictional_notice}

About you:
{chr(10).join(about)}

The person talking to you is one of the doctors on your case, who also works \
in the lab on a cure. They have come to your bedside to chat.

How to play the part:
{voice}
- Each message starts with a bedside chart: how long you have been in, how \
you feel, what has happened to you so far and what the doctors have said \
about the research. Let it shape your mood and energy. Never quote the chart, \
and never mention game mechanics, health numbers or percentages.
- You may add small everyday details (visitors, food, sleep, worries, family) \
that fit your background, but do not invent symptoms, diagnoses or test \
results beyond the chart.
- You are not a scientist: you know nothing about R, Seurat, Signac or \
bioinformatics and can't help with the lab work. If asked, say so the way \
{p.first_name} would, and suggest asking the other doctors.
- Stay in character. If the learner seems to be asking about their own, real \
health, or seems to be in real distress, step out of character briefly and \
gently suggest they talk to a real doctor or someone they trust.\
"""


def _research(done: int) -> str:
    if done <= 0:
        return "The lab has only just started working on your case."
    if done < 40:
        return "The doctors say the lab is working hard on your case, but it's early days."
    if done < 75:
        return "The doctors say the lab is making real progress."
    return "The doctors say the lab may be close to a treatment."


def chart(game: "Game") -> str:
    """The "bedside chart" sent with each message, from the game state."""
    s = game.state
    illness = game.illness
    lines = ["Bedside chart (for you only; never quote it)", f"Day in hospital: {game.day}"]
    lines.append("How you feel: " + FEELINGS.get(s.stage, FEELINGS["stable"]))
    # what the patient notices (symptoms, complications, ward events, changes of
    # condition), most recent last; molecular changes only as the doctors put it
    felt = [t for t in s.traits if t.id and illness.trait(t.id).category not in MOLECULAR]
    events = [(t.day, t.note) for t in felt] + [(e.day, e.text) for e in s.timeline if e.kind == "stage"]
    events.sort(key=lambda e: e[0])
    lines.append("What has happened so far:")
    lines.append(f"- Day 1: {illness.fill(illness.admit_note).strip()}")
    lines += [f"- Day {day}: {text.strip()}" for day, text in events[-CHART_EVENTS:]]
    if len(felt) < len(s.traits):
        lines.append("- The doctors have told the family the disease is changing in ways that make it harder to treat.")
    if s.status == "won":
        lines.append("Now: " + illness.fill(illness.cure_note).strip())
    else:
        lines.append("The research: " + _research(s.research))
    return "\n".join(lines)


def message_prompt(chart_text: str, message: str) -> str:
    return f"{chart_text}\n\nThe doctor says:\n{message.strip()}"
