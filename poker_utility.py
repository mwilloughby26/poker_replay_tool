# poker_utility.py
#
# Helpers for parsing poker hand scripts and dealing cards for tests.
# Main entry: `load_script(path, num_players)` → ParsedHand with:
#   • per-player hole cards
#   • ordered list of Actions (bets/checks/folds and flop/turn/river deals)
#
# Notes
# -----
# • Cards accept "T" or "10" for tens; suits C/D/H/S (any case).
# • Seats are dynamic by table size: we start from the canonical 9-max order
#   (UTG → ... → BTN → SB → BB) and trim earliest seats first as players drop.
# • Board deals are represented as Actions with seat=None.

from __future__ import annotations

import re, random
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# 1) Card types & parsing
# =============================================================================

# Suits and ranks used to synthesize a full deck in Deck().
SUITS = "cdhs"                      # clubs, diamonds, hearts, spades
RANKS = "23456789TJQKA"             # poker order, T for Ten

# Regex for a single card token.
#   Group 1: rank either "10" or one char in [2-9TJQKA]
#   Group 2: suit: C/D/H/S
# Flags: re.I makes it case-insensitive for both groups.
CARD_RE = re.compile(r"((?:10|[2-9TJQKA]))([CDHS])", re.I)


@dataclass(frozen=True)
class Card:
    """Immutable representation of a playing card (rank + suit)."""
    rank: str  # '2'..'9','T','J','Q','K','A'   (stored uppercase)
    suit: str  # 'c','d','h','s'                (stored lowercase)

    @property
    def image_path(self) -> str:
        """
        Relative path to a card image asset.
        """
        return f"assets/CARDS/{self.suit.lower()}/{self.rank.upper()}.png"


def parse_card(tok: str) -> Card:
    """
    Parse a single card token into a Card.
      - Accepts '10' or 'T' for tens.
      - Accepts suit letters C/D/H/S in any case.
    Raises:
      ValueError if the token is not a valid card.
    """
    m = CARD_RE.fullmatch(tok)
    if not m:
        raise ValueError(f"Bad card token '{tok}'")
    r, s = m.group(1).upper(), m.group(2).lower()
    return Card(r, s)


# =============================================================================
# 2) Seating configuration & resolution (dynamic by table size)
# =============================================================================

# Canonical 9-max order: earliest position -> blinds
_FULL_ORDER = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

# As table size shrinks, remove seats in this order (earliest first).
_TRIM_ORDER = ['UTG+2', 'UTG+1', 'UTG', 'LJ', 'HJ', 'CO', 'BTN']

# Accept common aliases
_SEAT_NORMALIZE = {
    'UTG1': 'UTG+1',
    'UTG2': 'UTG+2',
    'BUTTON': 'BTN', 'DEALER': 'BTN', 'D': 'BTN',
}


def _active_positions(n: int) -> list[str]:
    """
    Return the list of seat names for a table of size n (2..9),
    trimming earliest positions first so the tail (BTN, SB, BB) survives.

    Examples:
      n=9 -> ['UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB']
      n=8 -> ['UTG','UTG+1','LJ','HJ','CO','BTN','SB','BB']      (drop UTG+2)
      n=7 -> ['UTG','LJ','HJ','CO','BTN','SB','BB']              (drop UTG+2, UTG+1)
      n=6 -> ['LJ','HJ','CO','BTN','SB','BB']
      n=3 -> ['BTN','SB','BB']
      n=2 -> ['SB','BB']   (heads-up: dealer is SB)
    """
    if not (2 <= n <= 9):
        raise ValueError(f"Unsupported table size {n}; expected 2..9.")
    active = _FULL_ORDER.copy()
    to_remove = len(_FULL_ORDER) - n
    for pos in _TRIM_ORDER:
        if to_remove <= 0:
            break
        if pos in active:
            active.remove(pos)
            to_remove -= 1
    return active


def _normalize_seat_token(token: str) -> str:
    t = token.upper()
    return _SEAT_NORMALIZE.get(t, t)


def _seat(token: str, n: int, ln: int) -> int:
    """
    Resolve a seat token to a 0-based index based on the dynamic table order.

    Heads-up note:
      In HU poker, the dealer is the SB. If the script says 'BTN' with n=2,
      we map it to 'SB' so both 'BTN' and 'SB' work.
    """
    t = _normalize_seat_token(token)

    # Heads-up: treat BTN as SB (dealer posts SB)
    if n == 2 and t in ('BTN', 'BUTTON', 'DEALER', 'D'):
        t = 'SB'

    active = _active_positions(n)

    if t not in _FULL_ORDER:
        raise ValueError(f"[line {ln}] unknown seat '{token}'")
    if t not in active:
        # e.g., 'UTG+2' used at 7-max may have been trimmed.
        raise ValueError(f"[line {ln}] seat '{token}' ≥ players ({n})")

    return active.index(t)


# =============================================================================
# 3) Public helpers for the GUI (thin wrappers)
# =============================================================================

def active_positions(n: int) -> list[str]:
    """Public wrapper for the table's dynamic seating order."""
    return _active_positions(n)

def seat_index(token: str, n: int) -> int:
    """Public wrapper to resolve a seat token to its index for a table of size n."""
    return _seat(token, n, ln=0)


# =============================================================================
# 4) Actions & hand containers + valid verbs
# =============================================================================

# The only player-initiated action verbs accepted in the script.
# Street deals ("flop"/"turn"/"river") are handled separately.
_VALID_ACTIONS = {'raise','call','bet','check','fold'}


@dataclass
class Action:
    """
    One step in the hand:
      • For street deals (flop/turn/river): seat=None, amount=None, and
        'cards' holds the newly dealt board card(s).
      • For player actions (raise/call/bet/check/fold):
        seat is the seat index, 'verb' is the lowercased action,
        and 'amount' is a float for bet/raise/call when present, else None.
    """
    seat:   int | None
    verb:   str
    amount: float | None
    raw:    str                 # the original input line (useful for debugging)
    cards:  list[Card] | None = None


@dataclass
class ParsedHand:
    """
    Structured result of parsing a script file.

    hole_cards:
      list of length = num_players
      each entry is [Card|None, Card|None] (allowing unknown/unset)

    actions:
      time-ordered list of Action instances that includes both:
        - board deals (flop/turn/river) with seat=None
        - player actions (raise/call/bet/check/fold)
    """
    hole_cards: list[list[Card|None]]
    actions:    list[Action]


# =============================================================================
# 5) Script loader
# =============================================================================

def load_script(path: str|Path, num_players: int) -> ParsedHand:
    """
    Read a hand script and return hole cards + ordered actions.

    Input format (case-insensitive keywords; cards can be 'T' or '10'):
      HAND <SEAT> <CARD1> <CARD2>
      FLOP <C1> <C2> <C3>
      TURN <C1>
      RIVER <C1>
      <SEAT> <ACTION> [AMOUNT]

    Examples:
      HAND BTN Ah Kh
      HAND SB  9c 9d
      FLOP 7h 10c Js
      BTN bet 3.5
      SB  call 3.5
      TURN Qd
      BTN check
      SB  bet  7
      BTN fold
      RIVER 2c

    Notes:
      • <SEAT> must be valid for the given table size (dynamic trimming logic).
      • <ACTION> must be one of _VALID_ACTIONS.
      • AMOUNT is parsed as float when present; omitted for check/fold, etc.
      • The original line (with original casing) is stored in Action.raw.
    """
    hole = [[None, None] for _ in range(num_players)]
    actions: list[Action] = []

    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                # Skip blank lines and comments
                continue

            # Uppercase tokens for keywords / seats / verbs;
            # we still keep the exact original line in Action.raw.
            parts = line.upper().split()

            # 1) Hole cards: "HAND <SEAT> <CARD1> <CARD2>"
            if parts[0] == "HAND":
                if len(parts) != 4:
                    raise ValueError(f"[line {ln}] HAND needs 2 cards")
                idx = _seat(parts[1], num_players, ln)
                hole[idx][0] = parse_card(parts[2])
                hole[idx][1] = parse_card(parts[3])
                continue

            # 2) Street deals (modelled as Actions with seat=None)
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

            # 3) Regular player action: "<SEAT> <VERB> [AMOUNT]"
            idx = _seat(parts[0], num_players, ln)
            verb = parts[1].lower()
            if verb not in _VALID_ACTIONS:
                raise ValueError(f"[line {ln}] unknown verb '{verb}'")
            amt = float(parts[2]) if len(parts) == 3 else None
            actions.append(Action(idx, verb, amt, raw.strip(), None))

    return ParsedHand(hole, actions)


# =============================================================================
# 6) Minimal Deck (for tests)
# =============================================================================

class Deck:
    """
    Minimal deck helper for tests and ad-hoc dealing.

    Usage:
      d = Deck().shuffle()
      hole = d.deal(2)      # list[Card] of length 2
      flop = d.deal(3)
      turn = d.deal(1)
      river = d.deal(1)

    Notes:
      • `shuffle()` shuffles in place and returns self (chainable).
      • `deal(num)` returns a list[Card] and removes them from the deck.
      • `reset()` returns a fresh, unshuffled Deck instance.
    """
    def __init__(self):
        # Build 52 cards by combining each rank with each suit.
        self.cards = [parse_card(r+s) for s in SUITS for r in RANKS]

    def shuffle(self):
        random.shuffle(self.cards)
        return self

    def deal(self, num=1):
        # Split off the first `num` cards and update the deck.
        dealt, self.cards = self.cards[:num], self.cards[num:]
        return dealt

    def reset(self):
        # Return a brand-new Deck (does not mutate this instance).
        return Deck()
