"""Minimax search with Alpha-Beta pruning (AIES Unit 1, Adversarial Search).

Mapping of the game formalization from the notes onto python-chess:
    Initial state       chess.Board()
    Player(s)           board.turn          (WHITE = MAX, BLACK = MIN)
    Actions(s)          board.legal_moves   (ordered by order_moves)
    Result(s, a)        board.push(a) ... board.pop()
    Terminal-Test(s)    no legal moves / draw rules
    Utility(s, p)       +/-MATE_SCORE for checkmate, 0 for a draw,
                        evaluate(board) as a heuristic at the depth cutoff

Alpha-Beta rules from the notes, as followed below:
    alpha = best (highest) value found so far for MAX, starts at -infinity
    beta  = best (lowest)  value found so far for MIN, starts at +infinity
    MAX only updates alpha, MIN only updates beta
    alpha/beta are passed DOWN to children, node values are passed UP
    prune the remaining children as soon as alpha >= beta
"""

import threading
import time
from dataclasses import dataclass

import chess
import chess.polyglot

from engine.evaluation import MATE_SCORE, PIECE_VALUES, evaluate

INF = float("inf")
MAX_QUIESCENCE_DEPTH = 8

# For MVV-LVA ordering the king must count as the *most* valuable attacker.
ATTACKER_VALUES = {**PIECE_VALUES, chess.KING: 2000}

# Transposition-table entry flags.
EXACT, LOWER, UPPER = 0, 1, 2


class SearchAborted(Exception):
    """Raised inside the tree when the time limit runs out or a stop is requested."""


@dataclass
class SearchStats:
    nodes: int = 0          # positions visited by the main alpha-beta search
    qnodes: int = 0         # positions visited by quiescence search
    cutoffs: int = 0        # times alpha >= beta caused the remaining moves to be pruned
    tt_hits: int = 0        # times a stored result for a repeated state was reused
    depth: int = 0          # deepest fully completed iteration
    time: float = 0.0       # seconds

    @property
    def total_nodes(self):
        return self.nodes + self.qnodes


@dataclass
class SearchResult:
    move: chess.Move
    score: float            # from White's point of view, in centipawns
    stats: SearchStats


def mated_score(side_to_move, ply):
    """Utility when `side_to_move` has been checkmated `ply` half-moves from the root.

    Subtracting ply makes the engine prefer the quickest mate and the slowest loss.
    """
    return -(MATE_SCORE - ply) if side_to_move == chess.WHITE else (MATE_SCORE - ply)


def is_mate_score(score):
    return abs(score) > MATE_SCORE - 1000


class Searcher:
    """Searches one position. Create a new one for every move."""

    def __init__(self, use_pruning=True, use_quiescence=True, use_tt=True,
                 time_limit=None, stop_event=None):
        # Plain minimax (no pruning) is only used for comparison, so it also
        # turns off the extras that rely on alpha/beta bounds.
        self.use_pruning = use_pruning
        self.use_quiescence = use_quiescence and use_pruning
        self.use_tt = use_tt and use_pruning
        self.time_limit = time_limit
        self.stop_event = stop_event or threading.Event()
        self.stats = SearchStats()
        self.tt = {}
        self._deadline = None

    # ------------------------------------------------------------------ ordering
    def order_moves(self, board, best_first=None, captures_only=False):
        """Order moves so the best are tried first (the notes' "Rules to find good ordering").

        1. the best move remembered for this state (from the previous iteration / TT)
        2. captures, most valuable victim first, least valuable attacker first (MVV-LVA)
        3. promotions
        4. checks ("threats")
        5. forward moves, then backward moves
        """
        moves = board.generate_legal_captures() if captures_only else board.legal_moves

        def score(move):
            if move == best_first:
                return 1_000_000
            value = 0
            if board.is_capture(move):
                victim = chess.PAWN if board.is_en_passant(move) else board.piece_type_at(move.to_square)
                attacker = board.piece_type_at(move.from_square)
                value += 100_000 + 10 * PIECE_VALUES[victim] - ATTACKER_VALUES[attacker]
            if move.promotion:
                value += 50_000 + PIECE_VALUES[move.promotion]
            if value == 0:
                if board.gives_check(move):
                    value += 10_000
                rank_change = chess.square_rank(move.to_square) - chess.square_rank(move.from_square)
                if board.turn == chess.BLACK:
                    rank_change = -rank_change
                value += rank_change
            return value

        return sorted(moves, key=score, reverse=True)

    # ------------------------------------------------------------------ helpers
    def _check_time(self):
        if self.stop_event.is_set():
            raise SearchAborted
        if self._deadline is not None and time.perf_counter() > self._deadline:
            raise SearchAborted

    @staticmethod
    def _is_draw(board):
        return (board.is_insufficient_material()
                or board.halfmove_clock >= 100
                or board.is_repetition(2))

    # ------------------------------------------------------------------ alpha-beta
    def alphabeta(self, board, depth, alpha, beta, maximizing, ply):
        """Value of `board` searched `depth` plies deep. MAX = White, MIN = Black."""
        self.stats.nodes += 1
        if self.stats.nodes % 1024 == 0:
            self._check_time()

        # Terminal-Test, part 1: draws by rule.
        if self._is_draw(board):
            return 0

        # Depth cutoff: estimate the position instead of searching further.
        if depth == 0:
            if self.use_quiescence:
                return self.quiescence(board, alpha, beta, maximizing, ply, 0)
            if not any(board.legal_moves):
                return mated_score(board.turn, ply) if board.is_check() else 0
            return evaluate(board)

        # Bookkeeping of repeated states (transposition table).
        key = chess.polyglot.zobrist_hash(board) if self.use_tt else None
        tt_move = None
        if key is not None and key in self.tt:
            tt_depth, tt_value, tt_flag, tt_move = self.tt[key]
            if tt_depth >= depth:
                self.stats.tt_hits += 1
                if tt_flag == EXACT:
                    return tt_value
                if tt_flag == LOWER:
                    alpha = max(alpha, tt_value)
                elif tt_flag == UPPER:
                    beta = min(beta, tt_value)
                if alpha >= beta:
                    return tt_value

        moves = self.order_moves(board, best_first=tt_move)

        # Terminal-Test, part 2: checkmate or stalemate.
        if not moves:
            return mated_score(board.turn, ply) if board.is_check() else 0

        alpha_orig, beta_orig = alpha, beta
        best_move = None

        if maximizing:                                   # MAX node: only updates alpha
            value = -INF
            for move in moves:
                board.push(move)                         # Result(s, a)
                child = self.alphabeta(board, depth - 1, alpha, beta, False, ply + 1)
                board.pop()
                if child > value:
                    value, best_move = child, move
                alpha = max(alpha, value)
                if self.use_pruning and alpha >= beta:   # prune: MIN will never allow this
                    self.stats.cutoffs += 1
                    break
        else:                                            # MIN node: only updates beta
            value = INF
            for move in moves:
                board.push(move)
                child = self.alphabeta(board, depth - 1, alpha, beta, True, ply + 1)
                board.pop()
                if child < value:
                    value, best_move = child, move
                beta = min(beta, value)
                if self.use_pruning and alpha >= beta:   # prune: MAX will never allow this
                    self.stats.cutoffs += 1
                    break

        if key is not None:
            if value <= alpha_orig:
                flag = UPPER        # all moves failed low: value is at most this
            elif value >= beta_orig:
                flag = LOWER        # a cutoff happened: value is at least this
            else:
                flag = EXACT
            self.tt[key] = (depth, value, flag, best_move)

        return value                                     # node value is passed up

    def quiescence(self, board, alpha, beta, maximizing, ply, qdepth):
        """Keep searching captures past the depth limit (avoids the horizon effect).

        Example: at depth 0, QxP looks like a pawn won, but the reply PxQ loses
        the queen. Quiescence search plays out captures until the position is quiet.
        """
        self.stats.qnodes += 1
        if self.stats.qnodes % 1024 == 0:
            self._check_time()

        if qdepth >= MAX_QUIESCENCE_DEPTH:
            return evaluate(board)

        if board.is_check():
            # In check, every legal move must be considered (no "stand pat").
            moves = self.order_moves(board)
            if not moves:
                return mated_score(board.turn, ply)
            best = -INF if maximizing else INF
        else:
            # "Stand pat": the side to move may also decline to capture.
            best = evaluate(board)
            if maximizing:
                if best >= beta:
                    return best
                alpha = max(alpha, best)
            else:
                if best <= alpha:
                    return best
                beta = min(beta, best)
            moves = self.order_moves(board, captures_only=True)

        for move in moves:
            board.push(move)
            value = self.quiescence(board, alpha, beta, not maximizing, ply + 1, qdepth + 1)
            board.pop()
            if maximizing:
                best = max(best, value)
                alpha = max(alpha, best)
            else:
                best = min(best, value)
                beta = min(beta, best)
            if alpha >= beta:
                self.stats.cutoffs += 1
                break
        return best

    # ------------------------------------------------------------------ root
    def _search_root(self, board, depth, moves):
        maximizing = board.turn == chess.WHITE
        alpha, beta = -INF, INF
        best_move, best_value = None, (-INF if maximizing else INF)
        for move in moves:
            board.push(move)
            value = self.alphabeta(board, depth - 1, alpha, beta, not maximizing, 1)
            board.pop()
            if maximizing and value > best_value:
                best_move, best_value = move, value
                alpha = max(alpha, value)
            elif not maximizing and value < best_value:
                best_move, best_value = move, value
                beta = min(beta, value)
        return best_move, best_value

    def search(self, board, max_depth):
        """Iterative deepening: search depth 1, 2, ..., max_depth.

        Each iteration tries the previous iteration's best move first, which is
        exactly the "ideal ordering" the notes describe. If time runs out, the
        result of the last completed iteration is used.
        """
        board = board.copy()
        start = time.perf_counter()
        self._deadline = start + self.time_limit if self.time_limit else None

        moves = self.order_moves(board)
        if not moves:
            raise ValueError("No legal moves: the game is over")

        best_move, best_value = moves[0], 0
        for depth in range(1, max_depth + 1):
            try:
                move, value = self._search_root(board, depth, moves)
            except SearchAborted:
                break
            best_move, best_value = move, value
            self.stats.depth = depth
            # Stop early once a forced mate has been found.
            if is_mate_score(value):
                break
            moves = [best_move] + [m for m in moves if m != best_move]

        self.stats.time = time.perf_counter() - start
        return SearchResult(best_move, best_value, self.stats)


def find_best_move(board, depth=3, time_limit=None, use_pruning=True,
                   use_quiescence=True, use_tt=True, stop_event=None):
    """Convenience wrapper: best move for the side to move in `board`."""
    searcher = Searcher(use_pruning=use_pruning, use_quiescence=use_quiescence,
                        use_tt=use_tt, time_limit=time_limit, stop_event=stop_event)
    return searcher.search(board, depth)
