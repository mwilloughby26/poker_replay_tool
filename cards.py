import random
 
class Card:
    """
    Represents a single playing card. Suits and ranks are baked into the class.
    """
    SUITS = ["c", "d", "h", "s"]
    RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

    def __init__(self, suit: str, rank: str, image_path: str = None):
        if suit not in Card.SUITS:
            raise ValueError(f"Invalid suit: {suit}. Must be one of {Card.SUITS}")
        if rank not in Card.RANKS:
            raise ValueError(f"Invalid rank: {rank}. Must be one of {Card.RANKS}")
        self.suit = suit
        self.rank = rank
        self.image_path = image_path  # for rendering in the UI

    def __repr__(self):
        return f"{self.rank}{self.suit}"


class Deck:
    """
    Represents a deck of playing cards. Builds cards using Card.SUITS and Card.RANKS.
    """
    def __init__(self, img_folder: str = "assets/cards"):
        # Build all 52 standard cards
        self.cards = [
            Card(s, r, f"assets/Set_A/small/card_a_{s}{r}.png")
            for s in Card.SUITS
            for r in Card.RANKS
        ]

    def shuffle(self):
        """Randomize the order of cards in the deck."""
        random.shuffle(self.cards)
        return self  # allow chaining

    def deal(self, num: int = 1):
        """Remove and return the top `num` cards."""
        dealt, self.cards = self.cards[:num], self.cards[num:]
        return dealt

    def reset(self):
        """Rebuilds a fresh deck and returns it."""
        return Deck()
