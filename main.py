# main.py
#
# Minimal PyQt5 UI to replay a scripted poker hand.
# - MainWindow renders a poker table background, seats, hole cards, and the board.
# - ControllerWindow provides Next/Previous buttons to step through parsed actions.
# - Uses `poker_utility.load_script` for input and Card.image_path for card art.

import sys
import math
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QPushButton
from PyQt5.QtCore    import pyqtSignal, Qt
from PyQt5.QtGui     import QPixmap

from poker_utility import load_script, Deck, ParsedHand, Action, seat_index


# =============================================================================
# Player seat widget
# =============================================================================

class PlayerView(QWidget):
    """
    A circular, semi-transparent widget representing a player's seat.

    Parameters
    ----------
    x, y : int
        Center position where the circular seat should be placed.
    size : int
        Diameter of the seat circle in pixels.
    parent : QWidget | None
        Parent widget.
    """
    def __init__(self, x: int, y: int, size: int, parent=None):
        super().__init__(parent)
        # Center the widget around (x, y)
        self.setGeometry(x - size//2, y - size//2, size, size)

        # Circular background (a QLabel styled as a circle via border-radius)
        self.circle = QLabel(self)
        self.circle.setGeometry(0, 0, size, size)
        self.circle.setStyleSheet(
            f"background-color: rgba(200,200,200,180); border-radius: {size//2}px;"
        )


# =============================================================================
# Main replay window
# =============================================================================

class MainWindow(QMainWindow):
    """
    Main poker replay view.

    Responsibilities:
      - Draw a background table image.
      - Lay out circular seat widgets in a ring.
      - Show each player's hole cards (if known).
      - Show community cards as the action stream reveals them.
      - Highlight the acting seat when stepping through actions.
    """
    def __init__(self, background_path: str, num_players: int = 6, anchor_seat: str = "BB"):
        super().__init__()
        self.setWindowTitle("Poker Replay System")
        self.setGeometry(100, 50, 1200, 800)

        self.background_path = background_path
        self.num_players     = max(2, min(num_players, 9))  # clamp to [2, 9]
        self.anchor_seat     = anchor_seat                  # seat to place at bottom

        # ---- state used for drawing ---------------------------------------
        # players_hands[i] is a list[Card] of that seat's revealed hole cards.
        self.players_hands: list[list] = [[] for _ in range(self.num_players)]

        # Community cards per street; filled in as actions occur.
        self.board_cards = {"flop": [], "turn": [], "river": []}

        # Full ordered action list and current playback index.
        self.actions: list[Action] = []
        self.current_index = -1

        # Remember last highlighted seat so we can unhighlight it.
        self.prev_highlight = None

        # ---- UI widgets ----------------------------------------------------
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Background table image (scaled to window)
        self.bg_label = QLabel(self.central_widget)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        pix = QPixmap(self.background_path)
        self.bg_label.setPixmap(pix.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        ))

        # Text banner at the top showing the raw action line currently shown
        self.action_label = QLabel("", self.central_widget)
        self.action_label.setStyleSheet(
            "background: rgba(255,255,255,200); font-size: 18px;"
        )
        self.action_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.action_label.setGeometry(0, 0, self.width(), 40)

        # Keep references to dynamically created widgets so we can remove/redraw
        self.player_views: list[PlayerView] = []
        self.card_labels:  list[QLabel]     = []  # hole cards
        self.board_labels: list[QLabel]     = []  # community cards

    # ---- Public API --------------------------------------------------------

    def set_state_from_parsed(self, parsed: ParsedHand):
        """
        Load player hole cards from a ParsedHand result and lay out seats.

        Only non-None cards are kept, so unknown hole cards render as empty seats.
        """
        self.players_hands = [
            [c for c in seat if c is not None] for seat in parsed.hole_cards
        ]
        self._position_players()

    def load_actions(self, moves: list[Action]):
        """Provide the full list of actions to replay and show the first one."""
        self.actions = moves
        if moves:
            self.current_index = 0
            self.update_action()

    def set_anchor_seat(self, seat: str):
        """Choose which seat should appear at the bottom and redraw."""
        self.anchor_seat = seat
        self._position_players()

    # ---- Navigation --------------------------------------------------------

    def next_action(self):
        """Advance to the next action (if any) and update the view."""
        if self.current_index < len(self.actions) - 1:
            self.current_index += 1
            self.update_action()

    def prev_action(self):
        """Go back to the previous action (if any) and update the view."""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_action()

    # ---- Qt event handlers -------------------------------------------------

    def resizeEvent(self, event):
        """
        Keep background and banner sized to the window.
        Recompute all positions when the window size changes.
        """
        # Resize background and rescale the background pixmap
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        pix = QPixmap(self.background_path)
        self.bg_label.setPixmap(pix.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        ))

        # Resize the action banner at the top
        self.action_label.setGeometry(0, 0, self.width(), 40)

        # Re-layout seats/cards to match the new window size
        self._position_players()
        return super().resizeEvent(event)

    # ---- Rendering / helpers ----------------------------------------------

    def update_action(self):
        """
        Render the current action:
          - Update banner text with the raw line.
          - If it's a street deal, reveal those board cards.
          - If it's a player action, highlight that seat.
        """
        move = self.actions[self.current_index]
        self.action_label.setText(move.raw)

        # Reveal community cards as soon as the corresponding action occurs
        if move.verb in ("flop", "turn", "river") and move.cards:
            self.board_cards[move.verb] = move.cards
            self._position_players()

        # Highlight only real player actions (seat != None)
        if move.seat is not None:
            if self.prev_highlight is not None:
                self.highlight_seat(self.prev_highlight, False)
            self.highlight_seat(move.seat, True)
            self.prev_highlight = move.seat

    def highlight_seat(self, idx: int, on: bool):
        """
        Toggle highlight color for a seat circle.

        Parameters
        ----------
        idx : int
            Seat index in [0, num_players-1].
        on : bool
            True to highlight (gold), False to reset (grey).
        """
        colour = "rgba(255,215,0,200)" if on else "rgba(200,200,200,180)"
        view = self.player_views[idx]
        r = view.circle.width() // 2
        view.circle.setStyleSheet(f"background-color: {colour}; border-radius: {r}px;")

    def _anchor_index(self) -> int:
        """Resolve the anchor seat name to an index for the current table size."""
        try:
            return seat_index(self.anchor_seat, self.num_players)
        except Exception:
            return 0  # fallback if a bad anchor is given

    def _position_players(self):
        """
        (Re)create and position all seat widgets and card labels.

        Strategy:
          - Remove old dynamic widgets (seats, hole cards, board cards).
          - Place seats on an ellipse centered in the window (cx, cy) with
            radii (rx, ry) for x/y, equally spaced by angle.
          - Place each player's known hole cards below their seat.
          - Center the board horizontally and place revealed community cards.
        """
        # Remove previous widgets by detaching parents; allows GC later.
        for w in self.player_views + self.card_labels + self.board_labels:
            w.setParent(None)
        self.player_views.clear()
        self.card_labels.clear()
        self.board_labels.clear()

        # --- layout constants (scaled by window size where needed) ----------
        cx, cy = self.width()/2, self.height()/2
        rx, ry = self.width()*0.38, self.height()*0.38   # ellipse radii
        seat_size = 150                                   # diameter in px

        card_w, card_h = 100, 150                         # hole/board card size
        card_gap = 10                                     # spacing between cards

        # ---- seats and hole cards -----------------------------------------
        step = 2*math.pi / self.num_players
        anchor_idx = self._anchor_index()

        for i in range(self.num_players):
            # Distribute players evenly in a circle (actually an ellipse).
            # Bottom of the screen corresponds to angle = +pi/2 in Qt (y grows downward).
            angle = math.pi/2 + (i - anchor_idx) * step
            x = cx + math.cos(angle) * rx
            y = cy + math.sin(angle) * ry

            # Create the seat circle
            pv = PlayerView(int(x), int(y), seat_size, parent=self.central_widget)
            pv.show()
            self.player_views.append(pv)

            # Draw known hole cards slightly below the seat circle.
            hand = self.players_hands[i]
            for j, card in enumerate(hand):
                lbl = QLabel(self.central_widget)
                lbl.setPixmap(
                    QPixmap(card.image_path).scaled(
                        card_w, card_h,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
                # Left and right offsets so the two cards sit side-by-side.
                offset_x = -card_w - 10 if j == 0 else 10
                lbl.setGeometry(
                    int(x + offset_x),
                    int(y + seat_size//2 + 10),
                    card_w, card_h
                )
                lbl.show()
                self.card_labels.append(lbl)

        # ---- community cards ----------------------------------------------
        # Concatenate streets in order; only already-revealed ones will be shown.
        board = self.board_cards["flop"] + self.board_cards["turn"] + self.board_cards["river"]
        total = len(board)

        # Compute centered starting X for however many board cards are visible.
        full_width = card_w*5 + card_gap*4  # nominal width for a full 5-card board
        start_x = cx - full_width/2 + (full_width - (total*card_w + (total-1)*card_gap))/2
        y = cy - card_h//2  # vertically centered

        for idx, card in enumerate(board):
            lbl = QLabel(self.central_widget)
            lbl.setPixmap(
                QPixmap(card.image_path).scaled(
                    card_w, card_h,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
            lbl.setGeometry(
                int(start_x + idx*(card_w + card_gap)),
                int(y),
                card_w, card_h
            )
            lbl.show()
            self.board_labels.append(lbl)


# =============================================================================
# Controls window
# =============================================================================

class ControllerWindow(QWidget):
    """Simple control window with two buttons that emit Next/Previous signals."""
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controls")
        self.setGeometry(50, 50, 200, 120)

        # Prev/Next buttons stacked vertically
        self.prev_btn = QPushButton("Previous", self)
        self.prev_btn.setGeometry(10, 10, 180, 40)

        self.next_btn = QPushButton("Next", self)
        self.next_btn.setGeometry(10, 70, 180, 40)

        # Wire button clicks to signals so the main window can connect handlers
        self.prev_btn.clicked.connect(self.prev_clicked)
        self.next_btn.clicked.connect(self.next_clicked)


# =============================================================================
# Bootstrap
# =============================================================================

if __name__ == "__main__":
    # Standard Qt application bootstrap
    app = QApplication(sys.argv)

    NUM = 9
    parsed = load_script("hand1.txt", NUM)

    mw = MainWindow("assets/table_background.jpg", NUM, "HJ")
    mw.set_state_from_parsed(parsed)     # populate seats/hole cards
    mw.load_actions(parsed.actions)      # provide the action timeline

    ctrl = ControllerWindow()
    ctrl.next_clicked.connect(mw.next_action)
    ctrl.prev_clicked.connect(mw.prev_action)

    mw.show()
    ctrl.show()
    sys.exit(app.exec_())
