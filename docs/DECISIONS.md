# Decisions

Rule interpretations and technical choices that aren't spelled out in `docs/RULES.md`. Confirm or overturn them here.

## Rules (to confirm)

1. **"Played this turn" and the card itself.** `played_this_turn` counts the card being played unless the condition says `other: true` (card text "other ... cards"). Cards played later never count.
2. **"In your discard pile" during a turn** counts `discard + in_play`, including the card currently resolving.
3. **Mid-turn reshuffle.** If a draw effect empties the deck mid-turn, only the `discard` pile is reshuffled. Cards played this turn (`in_play`) stay out until clean up.
4. **Units count as played cards** for the 2-card minimum and for "played this turn" conditions, even though they go to the board instead of `in_play`.
5. **Resource caps.** Passives and prepare cap at the class `limit` (Mage: 4). Card effects cap at `hard_max` (Mage: 7). A gain never lowers a value that is already above the cap.

6. **Undo and hidden information.** Undo and Cancel can't go back past an action that revealed hidden information (drawing a card, reshuffling, and later scouting or revealing market cards). That action becomes the new checkpoint.
7. **Cancel keeps start-of-turn effects.** Cancel returns to the state right after start of turn (e.g. the Mage's +3 mana stays).
8. **Other players see plays immediately.** Cards played and then undone are visible to everyone (they're in the log). If uncommitted plays should stay hidden until End turn, the server can send opponents the last committed state instead.

9. **"[invoke] for X"** succeeds when the invoke value is **at least** X (card 010: Mage spends 3 mana, +1 spell bonus = 4).
10. **Split "limited to a single row"** (card 009) means all damage goes to units on **one tier**, of any players.
11. **Heal with a cap** (card 011: "can't have more than 6 HP after this card resolves") stops healing at 6 but never lowers a unit that already has more.
12. **Prepare (Mage)**: "refresh 1 spent mana" is implemented as +1 mana up to the limit of 4.
13. **Positive effects are optional.** Damage, healing and drawing a scouted card can be skipped (`allow_skip`). Invoke can't be skipped, but you may spend 0.
14. **Scout with a short deck** looks only at the cards left. It shuffles the discard pile only if the deck is completely empty.
15. **Invoke happens once per card.** Every `{invoke: N}` on the same card reuses the value. The spell bonus applies to spells only, not units.
16. **Tokens develop and score.** A summoned token is a unit, so it can develop (taking a normal spot) and scores VP by its tier like any other unit.
17. **Develop cost comes from the unit owner's class board** (the `develop_cost` of the target tier).
18. **What can be removed.** A card in your hand, played this turn or in the discard pile. Never from the deck. Hand removal can't take you below 2 cards in hand.
19. **Removing a played card keeps its effects.** Inf it gave stays, and its elements still count as played this turn.
20. **"Next spell" bonuses (032)** are used up by the next spell played, even if it doesn't invoke. The fire check uses printed elements.
21. **"Prepare ×N, can exceed your mana limit" (033, 034)** goes up to the Mage's hard maximum of 7. 031's prepare ×2 respects the limit of 4.
22. **Unique elements (031, 035, 043)** count elements on cards played this turn. A card with all elements counts as all five. 031 and 035 count only *other* cards; 043 counts all.
23. **036 option 1** can hit any unit on any tier. **Option 2** splits damage among units of any player on tiers where you have at least one unit, and may span several such tiers.
24. **037 "rows"** are tiers. Tokens count.
25. **038** plays a spell from the discard pile: it moves to "played this turn", counts as played (elements, "next spell" bonuses) and resolves fully. 038 can't pick itself.
26. **039** "deal 1 damage" may hit any unit on any tier, or nothing. Once the card is drawn, the play can't be cancelled.
27. **040** hits every unit on the chosen tier, your own included. Value = invoke + other fire cards played this turn.
28. **041**: the next spell resolves twice and invokes once (mana is spent once). +1 VP per unit (any owner) destroyed by that spell.
29. **042**: your units on the board get +invoke attack until the end of your turn. +1 VP per enemy unit destroyed by your units' attacks this turn.
30. **043** health = invoke + 1. Units don't get the spell bonus.
31. **044** "non-primary" means the card has at least one element outside your class's primary elements (Mage: fire, water). After every card you play while 044 is on the board, it checks whether at least 4 such cards were played this turn. The first time that's true, you gain 2 inf. It doesn't fire again that turn (Jan's ruling).
32. **045** adds +1 to your spells' invoke values while it's on the board. Several copies stack.
33. **Attacks** follow the rulebook: same tier or one higher, enemy units only, attacker taps, damage = attack, no strike back.
34. **Refreshed-out market cards** go to the market's face-up removed pile, which sits on the left next to the deck. They don't go straight back into the deck: the removed pile is shuffled into a new deck only when the deck runs out (rulebook).
35. **Mage element swap** (Jan's ruling): free, once per turn, chosen when playing a card. A two-element card can't end up with the same element twice. All-element cards can't change, and "all" can't be chosen. A card with no element can't change either. The swap lasts while the card is in play (units keep it while on the board) and resets when the card goes to the discard pile.
36. **Basic supply (701–712)** is a separate face-up pile, buyable at any time for its printed cost (3). It's never part of the 6-card shared market and can't be refreshed. When it's empty, it's empty.
37. **713** counts cards with at least one of your class's primary elements (Mage: fire, water) played this turn, including element swaps.
38. **714** "any unit" means allies and enemies on any tier, and it can be skipped.
39. **715** only moves a card played this turn that's still in the "played" zone (units on the board can't be moved). The moved card's effects stay, and it still counts as played this turn.
40. **716** is a mandatory cost: the card can't be played without one of your units to damage. A shield on that unit still absorbs the hit.
41. **717 / 720** are influence cards, so their invoke gets no spell bonus. "(max. 4)" caps the inf, not the mana you can spend.
42. **719** counts every prepare triggered this turn, including start-of-turn prepares and this card's own.
43. **720**'s optional discard respects the 2-card minimum, so a card can only be discarded if you'd still have 2 or more.
44. **721**'s shield goes on one of your own units, and can be skipped.
45. **722** counts different tiers with at least one of your units (tokens count as tier 1). Prepares respect the mana limit.
46. **723**: "in your discard pile" includes cards played this turn and 723 itself. With 4+ lightning there, no damage and no unit needed. Otherwise the 3 damage to your unit is mandatory.
47. **724**'s refund = the develop cost of the tier the unit leaves (T2→T1: 3, T3→T2: 4, T4→T3: 5, from the owner's class). Degrading needs a free spot below. Units on tier 1 and undeveloped tokens can't degrade.
48. **725** hits any unit on any tier. +2 inf only if that damage destroys it.
49. **726**: buying it by losing 3 VP needs at least 3 VP. It's a flat 3 VP, with no market price modifier.
50. **727** counts enemy units destroyed by you this turn (attacks and card effects).
51. **728**: discarded scouted cards go to your discard pile, and the rest stay on top in the same order. Once you've seen them, the play can't be cancelled.
52. **729**'s free develop still needs a free spot and a unit that isn't frozen.
53. **730** counts other cards played this turn with fire **or** water (a card with both counts once). Prepare respects the limit.
54. **731** is discarded at the very start of your end of turn (before scoring), only if you tick it in the end-turn panel.
55. **734** puts the chosen market card on the shared removed pile, and a new card is revealed into that same spot.
56. **736** lets you look at each other player's hand and pick an influence card. Players with no influence card are skipped. The opponents' 2-card minimum doesn't apply (it isn't their own action).
57. **737**: "your market" = your private market. The refreshes are free and you pick 0–3.
58. **740 / 753**: "other" cards leave the card itself out. 753's chosen cards are shuffled into the deck, and the whole deck is reshuffled.
59. **742**: both bonuses are optional. "Every market" = the shared market and every player's private market, once each, for free.
60. **743** may develop the same unit twice (T1→T3).
61. **744** picks one unit of each other player (tiers 1–3). With 3 other fire cards, the damage is invoke + 3.
62. **746** swaps the tier spots of 2 of your units (tokens that haven't developed can't be swapped). With 2 other shadow cards, you also swap 2 units of every other player and deal 1 damage to each of them.
63. **748**: the 2 revealed wind cards stay in your hand but are locked for the rest of the turn.
64. **749**: after drawing 1, you choose to discard all the others or put them back on top in any order.
65. **751** and **754** give extra attacks for this turn only. 751 targets one of your units.
66. **755**: the second unit must be different from the first. One invoke sets both values.
67. **756** stuns up to [invoke] different enemy units (one token each).
68. **757**: the discount = prepares triggered this turn at the moment you develop. It's used up by your next develop action.
69. **758** counts any unit you kill (by attacks or card effects) while 758 is in your discard pile or played this turn.
70. **759**: "2 wind cards" counts this turn's wind cards. 759 is fire, so it doesn't count itself.
71. **760** "once for each enemy" = degrade players − 1 times (3 with 4 players), as Jan ruled. You choose any unit each time, and the same unit may be degraded again.
72. **761** can boost any unit, but only your own units attack on your turn. The VP comes when that unit's attack kills a unit this turn.
73. **762**: the returned unit goes back to its owner's hand without damage or tokens. Then a different random card from that hand is discarded (random, so it can't be undone).
74. **763** ignores shields (it kills, it doesn't deal damage). It's optional per opponent, and tokens count as cost 0.
75. **764**: other players draw right away, so their hands can go above 7.
76. **765** may shield any units (yours or enemies'), up to [invoke], max. 2.
77. **766**: the water count includes 766 itself (the discard pile includes cards played this turn).
78. **767**: each hit is a separate damage instance, so you choose a target each time and a shield absorbs one hit.
79. **769** copies the market card's effects as if you'd played it. Spells get the spell invoke bonus, but it doesn't count as a card you played (no element, no "played this turn"). Then that card goes to the removed pile.
80. **770**: invoke/2 rounded up, + 1. Paying 3 inf is optional and must be affordable.
81. **771**: "harmed" = actually lost HP (a shielded hit doesn't count).
82. **772** kills every unit on the chosen tier, yours too.
83. **773** gains the killed unit's current HP and VP = its tier − 1 (a tier 1 unit gives 0).
84. **774**: the 10 cards are discard + played this turn. Units on the board don't count.
85. **778**: the attacker takes 1 damage on every attack against 778, even if 778 dies.
86. **781**: "any tier" means any tier, lower ones too, this turn.
87. **782**: unit EOT abilities happen before the Mage's EOT mana loss, so 782 can invoke with the turn's mana. The prompt happens when you end the turn, and you can cancel back.
88. **786** caps every single hit (attack or effect) at 2 damage.
89. **787** damages the other units on the tier it enters, not itself. It fires whenever it's developed (action or card effect).
90. **788**'s stun is added after each attack, if the target survives.
91. **789** prepares once per invoke, before you choose how much mana to spend.
92. **791**: its owner gains the VP every time it takes damage and survives, even on another player's turn.
93. **793** shuffles the most recent shadow card from your discard pile into your deck automatically (the owner may not be the active player, so there's no prompt).
94. **795** is always shuffled back into your deck when it dies (automatic, no prompt).
95. **797 / 786**: damage reduction applies first, then the per-hit cap. A hit reduced to 0 does nothing.
96. **798**: an enemy attacking any of your units takes 1 damage per 798 you have. It stacks with 778's own thorns.
97. **799**: it enters on tier 1 first (needs a free tier 1 spot), then may move to tier 3 if there's a free spot there.
98. **801**'s taunt covers attacks and enemy card effects that choose a unit, not "all units on a tier" effects.
99. **802** counts elements that appear on at least 2 *other* cards played this turn (each card counts an element once).
100. **803**: its attack hits every enemy unit on the target's tier (not your own units). With 4+ water in your discard pile, they're frozen.
101. **804** affects influence cards played *after* it this turn.
102. **807** counts 807 itself (it's fire and wind and in "played this turn"). Each point is a separate 1-damage / 1-HP choice.
103. **810**: VP can't go below 0.

## Technical

1. **Engine models are stdlib dataclasses, not Pydantic.** This keeps `engine/` dependency-free and pure. Validation happens in `engine/loader.py`. Pydantic is used for HTTP/WebSocket schemas in `server/`.
2. **Temporary dev API.** `server/dev_service.py` exposes hot-seat games over plain HTTP (`/api/dev/games/...`). It will be replaced by lobby rooms + WebSockets.
3. **Locale namespaces** match file names: `ui`, `cards`, `classes`, `keywords`, `log`, `error`, `prompt`. A key is `<namespace>.<path>`, e.g. `ui.panel.end_turn`, `cards.MAG-S001.name`, `log.card_played`, `prompt.invoke`.
4. **Icons are inline SVG** (`client/js/icons.js`), so there's no external icon font or CDN.
5. **Test-only cards.** Engine tests that need special effects define cards with `catalog_with()` in `tests/helpers.py` instead of depending on real card data.
6. **Hand order is client-side.** Reordering cards by drag and drop (move and shift, not swap) doesn't go through the server. The order is stored per game and seat in `sessionStorage`. If it ever needs to sync across devices, add a `reorder_hand` action.
7. **Playing by drag.** A card is played by dragging it up out of the hand. Clicking no longer plays, to avoid accidental plays.
8. **Card names.** The card table has no names yet. Names are `MAG 009 · Spell` (number + type) until real names arrive (add a Name column).
9. **IDs use the printed card number.** "New card #" is unique across the whole game, so IDs are `<CLASS>-<SOURCE><NNN>` (e.g. `MAG-S001`, `MAG-P031`).
10. **One way to remove cards.** Removal happens only through the overlay, opened from the "Remove a card" chip. The inline trash buttons on hand cards and in the sidebar are gone.
