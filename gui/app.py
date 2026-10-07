"""Pygame front end: the human plays against the Alpha-Beta engine."""

import os
import threading

import chess
import pygame

from engine.search import MATE_SCORE, find_best_move, is_mate_score

SQUARE = 80
BOARD_PX = SQUARE * 8
PANEL_W = 300
WIDTH, HEIGHT = BOARD_PX + PANEL_W, BOARD_PX
FPS = 30

LIGHT = (240, 217, 181)
DARK = (181, 136, 99)
SELECTED = (246, 246, 105)
LAST_MOVE = (205, 210, 106)
CHECK = (235, 80, 80)
HINT = (60, 60, 60, 90)
PANEL_BG = (38, 36, 33)
TEXT = (230, 230, 230)
MUTED = (150, 150, 150)
ACCENT = (120, 190, 120)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Solid glyphs are used for both colours; White pieces are filled white and
# then outlined with the hollow glyph.
SOLID = {chess.KING: "♚", chess.QUEEN: "♛", chess.ROOK: "♜",
         chess.BISHOP: "♝", chess.KNIGHT: "♞", chess.PAWN: "♟"}
HOLLOW = {chess.KING: "♔", chess.QUEEN: "♕", chess.ROOK: "♖",
          chess.BISHOP: "♗", chess.KNIGHT: "♘", chess.PAWN: "♙"}


def _font(size):
    if os.path.exists(FONT_PATH):
        return pygame.font.Font(FONT_PATH, size)
    return pygame.font.SysFont("dejavusans,segoeuisymbol,arialunicodems", size)


def format_score(score):
    if score is None:
        return "-"
    if is_mate_score(score):
        plies = MATE_SCORE - abs(score)
        moves = (plies + 1) // 2
        return f"{'+' if score > 0 else '-'}M{moves}"
    return f"{score / 100:+.2f}"


class ChessApp:
    def __init__(self, depth=3, human_color=chess.WHITE, time_limit=3.0):
        pygame.init()
        pygame.display.set_caption("Chess - Alpha-Beta Pruning")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.piece_font = _font(int(SQUARE * 0.78))
        self.font = _font(18)
        self.small = _font(14)
        self.title_font = _font(22)
        self.banner_font = _font(34)

        self.depth = depth
        self.time_limit = time_limit
        self.human_color = human_color
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self):
        self._stop_ai()
        self.board = chess.Board()
        self.selected = None
        self.last_result = None
        self.last_ai_san = "-"
        self._move_cache = (None, [])
        self.ai_thread = None
        self.ai_result = None
        self.stop_event = threading.Event()

    def _stop_ai(self):
        if getattr(self, "ai_thread", None) and self.ai_thread.is_alive():
            self.stop_event.set()
            self.ai_thread.join()
        self.ai_thread = None
        self.ai_result = None

    def undo(self):
        """Take back the last human move (and the AI's reply, if it was made)."""
        self._stop_ai()
        self.selected = None
        if self.board.move_stack:
            self.board.pop()
        while self.board.move_stack and self.board.turn != self.human_color:
            self.board.pop()
        self.last_result = None

    @property
    def ai_thinking(self):
        return self.ai_thread is not None

    def game_over(self):
        return self.board.is_game_over(claim_draw=True)

    # ------------------------------------------------------------------ AI
    def _start_ai(self):
        self.stop_event = threading.Event()
        board, stop_event = self.board.copy(), self.stop_event

        def work():
            result = find_best_move(board, depth=self.depth, time_limit=self.time_limit,
                                    stop_event=stop_event)
            if not stop_event.is_set():
                self.ai_result = result

        self.ai_thread = threading.Thread(target=work, daemon=True)
        self.ai_thread.start()

    def _update_ai(self):
        if self.game_over():
            return
        if self.board.turn != self.human_color and not self.ai_thinking:
            self._start_ai()
        elif self.ai_thinking and self.ai_result is not None:
            result = self.ai_result
            self.ai_thread.join()
            self.ai_thread, self.ai_result = None, None
            self.last_ai_san = self.board.san(result.move)
            self.board.push(result.move)
            self.last_result = result

    # ------------------------------------------------------------------ input
    def _square_at(self, pos):
        x, y = pos
        if x >= BOARD_PX or y >= BOARD_PX:
            return None
        file, row = x // SQUARE, y // SQUARE
        if self.human_color == chess.WHITE:
            return chess.square(file, 7 - row)
        return chess.square(7 - file, row)

    def _square_rect(self, square):
        file, rank = chess.square_file(square), chess.square_rank(square)
        if self.human_color == chess.WHITE:
            col, row = file, 7 - rank
        else:
            col, row = 7 - file, rank
        return pygame.Rect(col * SQUARE, row * SQUARE, SQUARE, SQUARE)

    def _legal_targets(self, from_square):
        return {m.to_square for m in self.board.legal_moves if m.from_square == from_square}

    def on_click(self, pos):
        if self.ai_thinking or self.game_over() or self.board.turn != self.human_color:
            return
        square = self._square_at(pos)
        if square is None:
            return
        piece = self.board.piece_at(square)

        if self.selected is not None and square in self._legal_targets(self.selected):
            move = chess.Move(self.selected, square)
            moving = self.board.piece_at(self.selected)
            if moving.piece_type == chess.PAWN and chess.square_rank(square) in (0, 7):
                move.promotion = chess.QUEEN   # auto-promote to a queen
            self.board.push(move)
            self.selected = None
        elif piece and piece.color == self.human_color:
            self.selected = square
        else:
            self.selected = None

    def on_key(self, key):
        if key == pygame.K_u:
            self.undo()
        elif key == pygame.K_r:
            self.reset()
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.depth = min(self.depth + 1, 8)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.depth = max(self.depth - 1, 1)

    # ------------------------------------------------------------------ drawing
    def _draw_board(self):
        last = self.board.peek() if self.board.move_stack else None
        for square in chess.SQUARES:
            rect = self._square_rect(square)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            color = LIGHT if light else DARK
            if last and square in (last.from_square, last.to_square):
                color = LAST_MOVE
            if square == self.selected:
                color = SELECTED
            pygame.draw.rect(self.screen, color, rect)

        if self.board.is_check():
            king = self.board.king(self.board.turn)
            pygame.draw.rect(self.screen, CHECK, self._square_rect(king), 5)

        # Coordinates along the bottom and left edges.
        for i in range(8):
            files = "abcdefgh" if self.human_color == chess.WHITE else "hgfedcba"
            ranks = "87654321" if self.human_color == chess.WHITE else "12345678"
            self.screen.blit(self.small.render(files[i], True, (90, 70, 50)),
                             (i * SQUARE + SQUARE - 12, BOARD_PX - 18))
            self.screen.blit(self.small.render(ranks[i], True, (90, 70, 50)),
                             (3, i * SQUARE + 2))

        for square, piece in self.board.piece_map().items():
            self._draw_piece(piece, self._square_rect(square))

        if self.selected is not None:
            overlay = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)
            for target in self._legal_targets(self.selected):
                overlay.fill((0, 0, 0, 0))
                if self.board.piece_at(target):
                    pygame.draw.circle(overlay, HINT, (SQUARE // 2, SQUARE // 2), SQUARE // 2 - 3, 6)
                else:
                    pygame.draw.circle(overlay, HINT, (SQUARE // 2, SQUARE // 2), SQUARE // 7)
                self.screen.blit(overlay, self._square_rect(target))

    def _draw_piece(self, piece, rect):
        fill = (255, 255, 255) if piece.color == chess.WHITE else (20, 20, 20)
        glyph = self.piece_font.render(SOLID[piece.piece_type], True, fill)
        self.screen.blit(glyph, glyph.get_rect(center=rect.center))
        if piece.color == chess.WHITE:
            outline = self.piece_font.render(HOLLOW[piece.piece_type], True, (20, 20, 20))
            self.screen.blit(outline, outline.get_rect(center=rect.center))

    def _text(self, text, pos, font=None, color=TEXT):
        self.screen.blit((font or self.font).render(text, True, color), pos)

    def _draw_panel(self):
        x0 = BOARD_PX
        pygame.draw.rect(self.screen, PANEL_BG, (x0, 0, PANEL_W, HEIGHT))
        x, y = x0 + 16, 14

        self._text("Alpha-Beta Chess", (x, y), self.title_font)
        y += 38
        you = "White" if self.human_color == chess.WHITE else "Black"
        self._text(f"You: {you}    Depth: {self.depth}", (x, y))
        y += 28

        if self.game_over():
            status, color = "Game over", ACCENT
        elif self.ai_thinking:
            status, color = "AI thinking...", (240, 200, 90)
        else:
            status, color = "Your move", ACCENT
        self._text(status, (x, y), color=color)
        y += 36

        self._text("Last AI search", (x, y), color=MUTED)
        y += 24
        r = self.last_result
        rows = [
            ("Move", self.last_ai_san if r else "-"),
            ("Eval (White)", format_score(r.score) if r else "-"),
            ("Depth reached", str(r.stats.depth) if r else "-"),
            ("Nodes searched", f"{r.stats.nodes:,}" if r else "-"),
            ("Quiescence nodes", f"{r.stats.qnodes:,}" if r else "-"),
            ("Cutoffs (a>=b)", f"{r.stats.cutoffs:,}" if r else "-"),
            ("TT hits", f"{r.stats.tt_hits:,}" if r else "-"),
            ("Time", f"{r.stats.time:.2f}s" if r else "-"),
        ]
        for label, value in rows:
            self._text(label, (x, y), self.small, MUTED)
            self._text(value, (x + 150, y), self.small)
            y += 20
        y += 14

        self._text("Moves", (x, y), color=MUTED)
        y += 24
        lines = self._move_lines()
        max_lines = (HEIGHT - y - 80) // 18
        for line in lines[-max_lines:]:
            self._text(line, (x, y), self.small)
            y += 18

        help_y = HEIGHT - 70
        for line in ("Click a piece, then a square", "U undo   R restart", "+ / -  change depth"):
            self._text(line, (x, help_y), self.small, MUTED)
            help_y += 20

    def _move_lines(self):
        key = tuple(self.board.move_stack)
        if self._move_cache[0] == key:
            return self._move_cache[1]
        temp = chess.Board()
        lines = []
        for i, move in enumerate(self.board.move_stack):
            san = temp.san(move)
            temp.push(move)
            if i % 2 == 0:
                lines.append(f"{i // 2 + 1}. {san}")
            else:
                lines[-1] += f"   {san}"
        self._move_cache = (key, lines)
        return lines

    def _draw_game_over(self):
        outcome = self.board.outcome(claim_draw=True)
        if outcome is None:
            return
        if outcome.winner is None:
            text = f"Draw ({outcome.termination.name.replace('_', ' ').title()})"
        elif outcome.winner == self.human_color:
            text = "Checkmate - you win!"
        else:
            text = "Checkmate - computer wins"
        overlay = pygame.Surface((BOARD_PX, 90), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, BOARD_PX // 2 - 45))
        label = self.banner_font.render(text, True, (255, 255, 255))
        self.screen.blit(label, label.get_rect(center=(BOARD_PX // 2, BOARD_PX // 2 - 8)))
        hint = self.small.render("Press R to play again", True, (200, 200, 200))
        self.screen.blit(hint, hint.get_rect(center=(BOARD_PX // 2, BOARD_PX // 2 + 26)))

    # ------------------------------------------------------------------ loop
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.on_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self.on_key(event.key)

            self._update_ai()

            self._draw_board()
            self._draw_panel()
            if self.game_over():
                self._draw_game_over()
            pygame.display.flip()
            self.clock.tick(FPS)

        self._stop_ai()
        pygame.quit()


def run(depth=3, human_color=chess.WHITE, time_limit=3.0):
    ChessApp(depth=depth, human_color=human_color, time_limit=time_limit).run()
