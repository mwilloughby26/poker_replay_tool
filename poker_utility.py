# poker_utility.py

import re, random
from dataclasses import dataclass
from pathlib import Path

# --- seats & verbs ---------------------------------------------------------
SEAT_ALIAS = {
    'UTG':0, 'UTG+1':1,'UTG1':1,'UTG+2':2,'UTG2':2,
    'LJ':3, 'HJ':4, 'CO':5, 'BTN':6, 'SB':7, 'BB':8
}
_VALID_ACTIONS = {'raise','call','bet','check','fold'}

# --- card parsing ----------------------------------------------------------
SUITS = "cdhs"
RANKS = "23456789TJQKA"
CARD_RE = re.compile(r"((?:10|[2-9TJQKA]))([CDHS])", re.I)

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str
    @property
    def image_path(self) -> str:
        return f"assets/Set_A/small/card_a_{self.suit.lower()}{self.rank.upper()}.png"

def parse_card(tok: str) -> Card:
    m = CARD_RE.fullmatch(tok)
    if not m:
        raise ValueError(f"Bad card token '{tok}'")
    r, s = m.group(1).upper(), m.group(2).lower()
    return Card(r, s)

# --- moves & hand ----------------------------------------------------------
@dataclass
class Action:
    seat:   int | None           # None for board‐deals
    verb:   str                  # e.g. 'flop','turn','river' or 'raise','fold',...
    amount: float | None
    raw:    str
    cards:  list[Card] | None = None

@dataclass
class ParsedHand:
    hole_cards: list[list[Card|None]]
    actions:    list[Action]

def load_script(path: str|Path, num_players: int) -> ParsedHand:
    hole = [[None, None] for _ in range(num_players)]
    actions: list[Action] = []

    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.upper().split()

            # 1) hole cards
            if parts[0] == "HAND":
                if len(parts) != 4:
                    raise ValueError(f"[line {ln}] HAND needs 2 cards")
                idx = _seat(parts[1], num_players, ln)
                hole[idx][0] = parse_card(parts[2])
                hole[idx][1] = parse_card(parts[3])
                continue

            # 2) board deals as moves
            if parts[0] == "FLOP":
                cards = [parse_card(tok) for tok in parts[1:4]]
                actions.append(Action(None, "flop", None, raw.strip(), cards))
                continue
            if parts[0] == "TURN":
                card = [parse_card(parts[1])]
                actions.append(Action(None, "turn", None, raw.strip(), card))
                continue
            if parts[0] == "RIVER":
                card = [parse_card(parts[1])]
                actions.append(Action(None, "river", None, raw.strip(), card))
                continue

            # 3) regular player action
            idx = _seat(parts[0], num_players, ln)
            verb = parts[1].lower()
            if verb not in _VALID_ACTIONS:
                raise ValueError(f"[line {ln}] unknown verb '{verb}'")
            amt = float(parts[2]) if len(parts) == 3 else None
            actions.append(Action(idx, verb, amt, raw.strip(), None))

    return ParsedHand(hole, actions)

def _seat(token: str, n: int, ln: int) -> int:
    if token not in SEAT_ALIAS:
        raise ValueError(f"[line {ln}] unknown seat '{token}'")
    idx = SEAT_ALIAS[token]
    if idx >= n:
        raise ValueError(f"[line {ln}] seat '{token}' ≥ players ({n})")
    return idx

# --- a minimal Deck for testing -------------------------------------------
class Deck:
    def __init__(self):
        self.cards = [parse_card(r+s) for s in SUITS for r in RANKS]
    def shuffle(self):
        random.shuffle(self.cards)
        return self
    def deal(self, num=1):
        dealt, self.cards = self.cards[:num], self.cards[num:]
        return dealt
    def reset(self):
        return Deck()
