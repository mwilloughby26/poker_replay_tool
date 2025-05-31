# main.py

import sys
import math
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QPushButton
from PyQt5.QtCore    import pyqtSignal, Qt
from PyQt5.QtGui     import QPixmap

from poker_utility import load_script, Deck, ParsedHand, Action

class PlayerView(QWidget):
    def __init__(self, x: int, y: int, size: int, parent=None):
        super().__init__(parent)
        # center the widget
        self.setGeometry(x - size//2, y - size//2, size, size)
        # circular background
        self.circle = QLabel(self)
        self.circle.setGeometry(0, 0, size, size)
        self.circle.setStyleSheet(
            f"background-color: rgba(200,200,200,180); border-radius: {size//2}px;"
        )

class MainWindow(QMainWindow):
    def __init__(self, background_path: str, num_players: int = 6):
        super().__init__()
        self.setWindowTitle("Poker Replay System")
        self.setGeometry(100, 50, 1200, 800)

        self.background_path = background_path
        self.num_players     = max(2, min(num_players, 9))

        # ---- state to draw ----
        self.players_hands = [[] for _ in range(self.num_players)]
        self.board_cards    = {"flop": [], "turn": [], "river": []}
        self.actions: list[Action] = []
        self.current_index = -1
        self.prev_highlight = None

        # ---- UI widgets ----
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.bg_label = QLabel(self.central_widget)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        pix = QPixmap(self.background_path)
        self.bg_label.setPixmap(pix.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        ))

        self.action_label = QLabel("", self.central_widget)
        self.action_label.setStyleSheet(
            "background: rgba(255,255,255,200); font-size: 18px;"
        )
        self.action_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.action_label.setGeometry(0, 0, self.width(), 40)

        self.player_views = []
        self.card_labels  = []
        self.board_labels = []

    def resizeEvent(self, event):
        # keep bg + banner sized
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        pix = QPixmap(self.background_path)
        self.bg_label.setPixmap(pix.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        ))
        self.action_label.setGeometry(0, 0, self.width(), 40)
        self._position_players()
        return super().resizeEvent(event)

    def set_state_from_parsed(self, parsed: ParsedHand):
        # load hole cards
        self.players_hands = [
            [c for c in seat if c is not None] for seat in parsed.hole_cards
        ]
        self._position_players()

    def load_actions(self, moves: list[Action]):
        self.actions = moves
        if moves:
            self.current_index = 0
            self.update_action()

    def next_action(self):
        if self.current_index < len(self.actions) - 1:
            self.current_index += 1
            self.update_action()

    def prev_action(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_action()

    def highlight_seat(self, idx: int, on: bool):
        colour = "rgba(255,215,0,200)" if on else "rgba(200,200,200,180)"
        view = self.player_views[idx]
        r = view.circle.width() // 2
        view.circle.setStyleSheet(f"background-color: {colour}; border-radius: {r}px;")

    def update_action(self):
        move = self.actions[self.current_index]
        self.action_label.setText(move.raw)

        # reveal board cards when the flop/turn/river move occurs
        if move.verb in ("flop", "turn", "river") and move.cards:
            self.board_cards[move.verb] = move.cards
            self._position_players()

        # highlight only real seat moves
        if move.seat is not None:
            if self.prev_highlight is not None:
                self.highlight_seat(self.prev_highlight, False)
            self.highlight_seat(move.seat, True)
            self.prev_highlight = move.seat

    def _position_players(self):
        # clear previous widgets
        for w in self.player_views + self.card_labels + self.board_labels:
            w.setParent(None)
        self.player_views.clear()
        self.card_labels.clear()
        self.board_labels.clear()

        # draw seats & hole cards
        cx, cy = self.width()/2, self.height()/2
        rx, ry = self.width()*0.35, self.height()*0.35
        seat_size = 150   # ~2.5× bigger

        card_w, card_h = 100, 150  # ~2× bigger
        card_gap = 10

        for i in range(self.num_players):
            angle = math.pi/2 + i*2*math.pi/self.num_players
            x = cx + math.cos(angle) * rx
            y = cy + math.sin(angle) * ry

            # seat circle
            pv = PlayerView(int(x), int(y), seat_size, parent=self.central_widget)
            pv.show()
            self.player_views.append(pv)

            # hole cards
            hand = self.players_hands[i]
            for j, card in enumerate(hand):
                lbl = QLabel(self.central_widget)
                lbl.setPixmap(
                    QPixmap(card.image_path).scaled(
                        card_w, card_h,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
                offset_x = -card_w - 10 if j == 0 else 10
                lbl.setGeometry(
                    int(x + offset_x),
                    int(y + seat_size//2 + 10),
                    card_w, card_h
                )
                lbl.show()
                self.card_labels.append(lbl)

        # draw community cards
        board = self.board_cards["flop"] + self.board_cards["turn"] + self.board_cards["river"]
        total = len(board)
        full_width = card_w*5 + card_gap*4
        start_x = cx - full_width/2 + (full_width - (total*card_w + (total-1)*card_gap))/2
        y = cy - card_h//2

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

class ControllerWindow(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controls")
        self.setGeometry(50, 50, 200, 120)
        self.prev_btn = QPushButton("Previous", self)
        self.prev_btn.setGeometry(10, 10, 180, 40)
        self.next_btn = QPushButton("Next", self)
        self.next_btn.setGeometry(10, 70, 180, 40)
        self.prev_btn.clicked.connect(self.prev_clicked)
        self.next_btn.clicked.connect(self.next_clicked)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    NUM = 9
    parsed = load_script("hand1.txt", NUM)

    mw = MainWindow("assets/table_background.png", NUM)
    mw.set_state_from_parsed(parsed)
    mw.load_actions(parsed.actions)

    ctrl = ControllerWindow()
    ctrl.next_clicked.connect(mw.next_action)
    ctrl.prev_clicked.connect(mw.prev_action)

    mw.show()
    ctrl.show()
    sys.exit(app.exec_())
