import sys
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from cards import Deck


class PlayerView(QWidget):
    """
    A circular seat indicator for a player.
    """
    def __init__(self, x, y, size, parent=None):
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
    def __init__(self, background_path, num_players=6):
        super().__init__()
        self.setWindowTitle("Poker Replay System - Table View")
        self.setGeometry(200, 100, 1920, 1080)

        self.background_path = background_path
        # clamp between 2 and 9
        self.num_players = max(2, min(num_players, 9))
        # placeholder for each player's two-card hand
        self.players_hands = [[] for _ in range(self.num_players)]

        # central widget for absolute positioning
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # background label
        self.bg_label = QLabel(self.central_widget)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        pixmap = QPixmap(self.background_path)
        self.bg_label.setPixmap(
            pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        )

        # action text overlay
        self.action_label = QLabel("", self.central_widget)
        self.action_label.setStyleSheet(
            "color: black; font-size: 24px; background: rgba(255,255,255,200);"
        )
        self.action_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.action_label.setGeometry(0, 0, self.width(), 50)

        # replay action list
        self.actions = []
        self.current_index = -1

        # storage for created player view widgets
        self.player_views = []

    def resizeEvent(self, event):
        # update background and action bar
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        pixmap = QPixmap(self.background_path)
        self.bg_label.setPixmap(
            pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        )
        self.action_label.setGeometry(0, 0, self.width(), 50)
        # reposition seats and cards
        self._position_players()
        return super().resizeEvent(event)

    def _position_players(self):
        # clear any previous widgets
        for w in self.player_views + getattr(self, 'card_labels', []):
            w.setParent(None)
        self.player_views = []
        self.card_labels = []

        # layout parameters
        radius_x = self.width() * 0.35
        radius_y = self.height() * 0.35
        center_x = self.width() / 2
        center_y = self.height() / 2
        seat_size = 80

        for i in range(self.num_players):
            # compute position around an ellipse
            angle = math.pi/2 + i * 2 * math.pi / self.num_players
            x = center_x + math.cos(angle) * radius_x
            y = center_y + math.sin(angle) * radius_y
            # draw seat
            pv = PlayerView(int(x), int(y), seat_size, parent=self.central_widget)
            pv.show()
            self.player_views.append(pv)
            # draw the two cards for this player
            hand = self.players_hands[i]
            for j, card in enumerate(hand):
                card_lbl = QLabel(self.central_widget)
                pix = QPixmap(card.image_path)
                cw, ch = 60, 90
                card_lbl.setPixmap(
                    pix.scaled(cw, ch, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                # position the two cards BELOW the seat
                offset_x = -cw - 5 if j == 0 else 5
                card_lbl.setGeometry(
                    int(x) + offset_x,
                    int(y) + seat_size//2 + 5,
                    cw, ch
                )
                card_lbl.show()
                self.card_labels.append(card_lbl)

    def set_hands(self, hands_list):
        """Assign each player's two-card hand and redraw."""
        self.num_players = len(hands_list)
        self.players_hands = hands_list
        self._position_players()

    def load_actions(self, actions):
        self.actions = actions
        if actions:
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

    def update_action(self):
        self.action_label.setText(self.actions[self.current_index])


class ControllerWindow(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller")
        self.setGeometry(1000, 100, 300, 200)
        self.prev_btn = QPushButton("Previous", self)
        self.prev_btn.setGeometry(50, 30, 200, 40)
        self.next_btn = QPushButton("Next", self)
        self.next_btn.setGeometry(50, 90, 200, 40)
        self.prev_btn.clicked.connect(self.prev_clicked)
        self.next_btn.clicked.connect(self.next_clicked)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    background_path = "assets/table_background.png"
    num_players = 6  # adjust up to 9

    main_win = MainWindow(background_path, num_players=num_players)
    ctrl_win = ControllerWindow()

    # connect replay controls
    ctrl_win.next_clicked.connect(main_win.next_action)
    ctrl_win.prev_clicked.connect(main_win.prev_action)

    # example replay actions
    sample_actions = [
        "Player1 posts small blind",
        "Player2 posts big blind",
        "Player3 calls 2",
        "Deal flop: A♠ K♥ 10♦",
        "Player1 bets 5",
        "Showdown: Player2 wins"
    ]
    main_win.load_actions(sample_actions)

    # deal and set hole cards
    deck = Deck().shuffle()
    hands = [deck.deal(2) for _ in range(num_players)]
    main_win.set_hands(hands)

    main_win.show()
    ctrl_win.show()
    sys.exit(app.exec_())
