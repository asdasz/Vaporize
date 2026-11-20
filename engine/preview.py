"""What each answer to a number prompt would do (e.g. "spend 3 mana" → value 4 → +1 VP).

For every possible answer the pending card (or attack) is replayed on a throwaway copy of the state, exactly like
`Respond` would do it, until it finishes or stops at its next question. The result is summarised as what changed
for the acting player: VP, inf, cards drawn, damage dealt, the stats of the unit it puts into play, and the next
question (e.g. "Choose a unit to deal 5 damage"). Nothing hidden is revealed: only counts and prompt texts.
"""

from __future__ import annotations

from typing import Any

from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.events import Event
from engine.history import copy_state
from engine.prompts import NeedChoice, Prompt
from engine.state import GameState

MAX_ANSWERS = 21  # at most this many values are previewed (number prompts are small: mana, gold, "times")


def _run(trial: GameState, catalog: Catalog, answers: list[Any]) -> Prompt | None:
    """Replay the pending choice on `trial`. Returns the next prompt, or None when it resolved completely."""
    from engine.actions import _play_card  # local import: actions imports view-independent engine modules
    from engine.attacks import attack

    pending = trial.pending
    assert pending is not None
    trial.pending = None
    events: list[Event] = []
    try:
        if pending.kind == "play":
            _play_card(trial, catalog, pending.seat, pending.card_uid, answers, events, pending.swap)
        elif pending.kind == "attack":
            attack(trial, catalog, pending.seat, pending.card_uid, pending.target_uid, events, answers)
        else:
            raise ValueError(pending.kind)
    except NeedChoice as need:
        return need.prompt
    return None


def _units(state: GameState) -> dict[str, int]:
    return {u.uid: u.current_hp or 0 for p in state.players for _, u in state.units_of(p.seat)}


def _summary(base: GameState, trial: GameState, seat: int, card_uid: str, kind: str, nxt: Prompt | None) -> dict[str, Any]:
    before, after = base.players[seat], trial.players[seat]
    out: dict[str, Any] = {}
    vp = after.vp - before.vp
    inf = (after.inf + after.develop_inf) - (before.inf + before.develop_inf)
    drawn = len(after.hand) - (len(before.hand) - (1 if kind == "play" else 0))
    if vp:
        out["vp"] = vp
    if inf:
        out["inf"] = inf
    if drawn > 0:
        out["draw"] = drawn
    hp_before, hp_after = _units(base), _units(trial)
    damage = sum(max(0, hp - hp_after.get(uid, 0)) for uid, hp in hp_before.items())
    kills = sum(1 for uid in hp_before if uid not in hp_after)
    if damage:
        out["damage"] = damage
    if kills:
        out["kills"] = kills
    unit = next((u for _, u in trial.units_of(seat) if u.uid == card_uid and uid_new(base, card_uid)), None)
    if unit is not None:
        out["unit"] = [unit.attack_value, unit.current_hp or 0]
    if nxt is not None:
        out["next"] = {"key": nxt.key, "params": dict(nxt.params)}
    return out


def uid_new(base: GameState, uid: str) -> bool:
    return all(u.uid != uid for p in base.players for _, u in base.units_of(p.seat))


def number_previews(state: GameState, catalog: Catalog) -> dict[str, dict[str, Any]]:
    """{answer: summary} for the pending number prompt, or {} when there's nothing to preview."""
    pending = state.pending
    if pending is None or pending.prompt.kind != "number" or pending.kind not in ("play", "attack"):
        return {}
    prompt = pending.prompt
    out: dict[str, dict[str, Any]] = {}
    for value in range(prompt.min, min(prompt.max, prompt.min + MAX_ANSWERS - 1) + 1):
        trial = copy_state(state)
        try:
            nxt = _run(trial, catalog, [*pending.answers, value])
        except IllegalAction:
            continue
        out[str(value)] = _summary(state, trial, pending.seat, pending.card_uid, pending.kind, nxt)
    return out
