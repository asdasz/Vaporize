"""Loads and validates card + class YAML files into a Catalog.

This is the only engine module that touches the file system.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

import engine.effects  # noqa: F401  (registers primitives before validation)
from engine.cards import CardDef
from engine.catalog import Catalog
from engine.classes import ClassDef, ResourceRule, TierRule
from engine.effects.registry import validate_effects
from engine.invoke import INVOKE_MODES
from engine.values import validate_value
from engine.rules import CARD_TYPES, CLASS_TRIGGERS, ELEMENTS, SOURCES, UNIT_TRIGGERS

CARD_ID_RE = re.compile(r"^[A-Z]{3}-[A-Z]?\d{2,3}$")
CARD_KEYS = {
    "id", "number", "type", "cost", "elements", "class", "source", "copies",
    "attack", "health", "effects", "triggers", "modifiers", "alt_cost", "hand_eot", "in_discard", "pre_effects",
    "invoke",
}
UNIT_MODIFIERS = {
    "spell_invoke_bonus", "extra_attacks", "develop_discount", "thorns", "stun_on_attack",
    "max_damage_per_hit", "prepare_before_invoke", "taunt", "cleave", "freeze_on_attack", "ally_thorns",
    "ally_damage_reduction", "cheat_death", "shuffle_on_death",
    "vp_per_tax",  # 144: gain N VP for each tax you pay
    "resource_bank",  # 143: you may keep class resource on this unit
    "develop_with_resource",  # 145: may be developed paying the class resource instead of inf
}
CLASS_MODIFIERS = {
    "spell_invoke_bonus", "element_swap_once_per_turn",
    "unit_health_bonus",  # Monarch: your units enter play with +N HP
    "any_tier_attack_once_per_turn",  # Monarch: once per turn a unit may attack without tier restrictions
}
CARD_INVOKE_KEYS = {"free", "max"}


class DataValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("invalid game data:\n  " + "\n  ".join(errors))
        self.errors = errors


def _read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def parse_card(raw: Any, where: str) -> tuple[CardDef | None, list[str]]:
    if not isinstance(raw, dict):
        return None, [f"{where}: card file must be a mapping"]
    errors: list[str] = []
    errors += [f"{where}: unknown key {k!r}" for k in sorted(raw.keys() - CARD_KEYS)]
    for key in ("id", "type", "cost", "class", "source"):
        if key not in raw:
            errors.append(f"{where}: missing {key!r}")
    if errors:
        return None, errors

    card_id = raw["id"]
    if not isinstance(card_id, str) or not CARD_ID_RE.match(card_id):
        errors.append(f"{where}: bad id {card_id!r} (expected e.g. MAG-S001 or SHR-001)")
    if raw["type"] not in CARD_TYPES:
        errors.append(f"{where}: type must be one of {CARD_TYPES}")
    if raw["source"] not in SOURCES:
        errors.append(f"{where}: source must be one of {SOURCES}")
    if not isinstance(raw["cost"], int) or raw["cost"] < 0:
        errors.append(f"{where}: cost must be a non-negative integer")
    number = raw.get("number")
    if number is not None and (isinstance(number, bool) or not isinstance(number, int) or number < 1):
        errors.append(f"{where}: number must be a positive integer")
    copies = raw.get("copies", 1)
    if not isinstance(copies, int) or copies < 1:
        errors.append(f"{where}: copies must be a positive integer")

    elements = raw.get("elements", [])
    if elements == ["all"]:
        elements = list(ELEMENTS)
    if not isinstance(elements, list) or any(e not in ELEMENTS for e in elements):
        errors.append(f"{where}: elements must be a list of {ELEMENTS} or [all]")
        elements = []

    attack, health = raw.get("attack"), raw.get("health")
    if raw["type"] == "unit":
        for name, value in (("attack", attack), ("health", health)):
            if value is None:
                errors.append(f"{where}: unit needs {name}")
            else:
                errors += validate_value(value, f"{where}.{name}")
    elif attack is not None or health is not None:
        errors.append(f"{where}: only units have attack/health")

    effects = raw.get("effects", []) or []
    errors += validate_effects(effects, f"{where}.effects")
    pre_effects = raw.get("pre_effects", []) or []
    errors += validate_effects(pre_effects, f"{where}.pre_effects")
    triggers_raw = raw.get("triggers", {}) or {}
    triggers: dict[str, tuple[dict[str, Any], ...]] = {}
    if not isinstance(triggers_raw, dict):
        errors.append(f"{where}: triggers must be a mapping")
    else:
        for trig, nodes in triggers_raw.items():
            if trig not in UNIT_TRIGGERS:
                errors.append(f"{where}: unknown trigger {trig!r}")
                continue
            nodes = nodes or []
            errors += validate_effects(nodes, f"{where}.triggers.{trig}")
            triggers[trig] = tuple(nodes)

    modifiers = raw.get("modifiers", []) or []
    if not isinstance(modifiers, list):
        errors.append(f"{where}: modifiers must be a list")
        modifiers = []
    for i, mod in enumerate(modifiers):
        if not isinstance(mod, dict) or not mod.keys() <= UNIT_MODIFIERS:
            errors.append(f"{where}.modifiers[{i}]: known modifiers are {sorted(UNIT_MODIFIERS)}")

    alt_cost = raw.get("alt_cost")
    if alt_cost is not None and (
        not isinstance(alt_cost, dict) or alt_cost.keys() != {"lose_vp"} or not isinstance(alt_cost["lose_vp"], int)
    ):
        errors.append(f"{where}: alt_cost must be {{lose_vp: N}}")

    hand_eot = raw.get("hand_eot")
    if hand_eot is not None and (not isinstance(hand_eot, dict) or hand_eot.keys() != {"discard_for_vp"}):
        errors.append(f"{where}: hand_eot must be {{discard_for_vp: N}}")
    in_discard = raw.get("in_discard")
    if in_discard is not None and (not isinstance(in_discard, dict) or in_discard.keys() != {"vp_per_kill"}):
        errors.append(f"{where}: in_discard must be {{vp_per_kill: N}}")

    invoke_rules = raw.get("invoke")
    if invoke_rules is not None and (
        not isinstance(invoke_rules, dict)
        or not invoke_rules.keys() <= CARD_INVOKE_KEYS
        or not isinstance(invoke_rules.get("free", False), bool)
        or not isinstance(invoke_rules.get("max", 0), int)
    ):
        errors.append(f"{where}: invoke must be {{free: true|false, max: N}}")

    if errors:
        return None, errors
    return (
        CardDef(
            id=card_id,
            type=raw["type"],
            cost=raw["cost"],
            elements=tuple(elements),
            card_class=raw["class"],
            source=raw["source"],
            copies=copies,
            number=number,
            attack=attack,
            health=health,
            effects=tuple(effects),
            triggers=triggers,
            modifiers=tuple(modifiers),
            pre_effects=tuple(pre_effects),
            alt_cost=alt_cost,
            hand_eot=hand_eot,
            in_discard=in_discard,
            invoke_rules=invoke_rules,
        ),
        [],
    )


def parse_class(raw: Any, where: str) -> tuple[ClassDef | None, list[str]]:
    if not isinstance(raw, dict):
        return None, [f"{where}: class file must be a mapping"]
    errors: list[str] = []
    for key in ("id", "primary_elements", "resource", "tiers", "removal_costs"):
        if key not in raw:
            errors.append(f"{where}: missing {key!r}")
    if errors:
        return None, errors

    res = raw["resource"]
    resource = ResourceRule(
        key=res["key"], start=res.get("start", 0), limit=res.get("limit"), hard_max=res.get("hard_max")
    )
    tiers: dict[int, TierRule] = {}
    for tier in (1, 2, 3, 4):
        t = raw["tiers"].get(tier)
        if t is None:
            errors.append(f"{where}: missing tier {tier}")
            continue
        spots = t.get("spots")
        if tier < 4 and (not isinstance(spots, int) or spots < 1):
            errors.append(f"{where}: tier {tier} needs a positive 'spots'")
        tiers[tier] = TierRule(spots=spots, develop_cost=t.get("develop_cost"), vp=t.get("vp", 0))

    passives = raw.get("passives", []) or []
    for i, passive in enumerate(passives):
        w = f"{where}.passives[{i}]"
        if "trigger" in passive:
            if passive["trigger"] not in CLASS_TRIGGERS:
                errors.append(f"{w}: unknown trigger {passive['trigger']!r}")
            errors += validate_effects(passive.get("effects", []), f"{w}.effects")
        elif passive.get("modifier") not in CLASS_MODIFIERS:
            errors.append(f"{w}: needs a 'trigger' or a known 'modifier' {sorted(CLASS_MODIFIERS)}")
    prepare = raw.get("prepare", []) or []
    errors += validate_effects(prepare, f"{where}.prepare")
    invoke_mode = (raw.get("invoke") or {}).get("mode")
    if invoke_mode not in INVOKE_MODES:
        errors.append(f"{where}: invoke.mode must be one of {INVOKE_MODES}")
    invoke_max = (raw.get("invoke") or {}).get("max")
    if invoke_max is not None and (isinstance(invoke_max, bool) or not isinstance(invoke_max, int) or invoke_max < 1):
        errors.append(f"{where}: invoke.max must be a positive integer")

    if errors:
        return None, errors
    return (
        ClassDef(
            id=raw["id"],
            primary_elements=tuple(raw["primary_elements"]),
            resource=resource,
            tiers=tiers,
            removal_costs=tuple(raw["removal_costs"]),
            passives=tuple(passives),
            prepare=tuple(prepare),
            invoke=dict(raw.get("invoke", {}) or {}),
        ),
        [],
    )


def load_catalog(data_dir: Path) -> Catalog:
    errors: list[str] = []
    cards: dict[str, CardDef] = {}
    for path in sorted((data_dir / "cards").rglob("*.yaml")):
        where = str(path.relative_to(data_dir))
        card, errs = parse_card(_read_yaml(path), where)
        errors += errs
        if card is None:
            continue
        if not path.stem.startswith(card.id + "_"):
            errors.append(f"{where}: file name must start with '{card.id}_'")
        rel = path.relative_to(data_dir / "cards").parts
        if card.source in ("shared", "basic"):
            if rel[0] != "shared" or card.card_class != "shared":
                errors.append(f"{where}: shared and basic cards live in cards/shared/ with class: shared")
        elif rel[:2] != (card.card_class, card.source):
            errors.append(f"{where}: expected location cards/{card.card_class}/{card.source}/")
        if card.id in cards:
            errors.append(f"{where}: duplicate card id {card.id}")
        cards[card.id] = card

    classes: dict[str, ClassDef] = {}
    for path in sorted((data_dir / "classes").glob("*.yaml")):
        where = str(path.relative_to(data_dir))
        cdef, errs = parse_class(_read_yaml(path), where)
        errors += errs
        if cdef is not None:
            if cdef.id != path.stem:
                errors.append(f"{where}: class id must match the file name")
            classes[cdef.id] = cdef

    numbers: dict[int, str] = {}
    for card in cards.values():
        if card.card_class != "shared" and card.card_class not in classes:
            errors.append(f"card {card.id}: unknown class {card.card_class!r}")
        if card.number is not None:
            if card.number in numbers:
                errors.append(f"card {card.id}: number {card.number} already used by {numbers[card.number]}")
            numbers[card.number] = card.id

    if errors:
        raise DataValidationError(errors)
    return Catalog(cards=cards, classes=classes)
