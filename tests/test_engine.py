"""Run with:  python -m unittest discover tests"""

import unittest

import chess

from engine import tree_demo
from engine.search import find_best_move


class TestTreeExample(unittest.TestCase):
    """The worked Alpha-Beta example from the AIES notes."""

    def test_root_value_and_pruned_leaves(self):
        value, visited, _ = tree_demo.run()
        self.assertEqual(value, 3)
        # E's right child (9) and the whole subtree G (7, 5) are never evaluated.
        self.assertEqual(visited, [2, 3, 5, 0, 1])


class TestChessSearch(unittest.TestCase):

    def test_pruning_gives_same_value_as_minimax(self):
        fens = [
            chess.STARTING_FEN,
            "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        ]
        for fen in fens:
            board = chess.Board(fen)
            plain = find_best_move(board, depth=2, use_pruning=False)
            pruned = find_best_move(board, depth=2, use_pruning=True,
                                    use_quiescence=False, use_tt=False)
            self.assertEqual(plain.score, pruned.score, fen)
            self.assertLess(pruned.stats.nodes, plain.stats.nodes, fen)

    def test_finds_mate_in_one_for_white(self):
        # Back-rank mate: Re8#
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        result = find_best_move(board, depth=3)
        self.assertEqual(result.move, chess.Move.from_uci("e1e8"))

    def test_finds_mate_in_one_for_black(self):
        board = chess.Board("4r1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        result = find_best_move(board, depth=3)
        self.assertEqual(result.move, chess.Move.from_uci("e8e1"))

    def test_captures_hanging_queen(self):
        # White's knight on c3 can take an undefended queen on d5.
        board = chess.Board("rnb1kbnr/pppp1ppp/8/3q4/8/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 4")
        result = find_best_move(board, depth=3)
        self.assertEqual(result.move, chess.Move.from_uci("c3d5"))

    def test_does_not_grab_defended_pawn_with_queen(self):
        # Qxd5?? would lose the queen to ...cxd5 (horizon effect test for quiescence).
        board = chess.Board("rnbqkbnr/pp2pppp/2p5/3p4/8/5Q2/PPPP1PPP/RNB1KBNR w KQkq - 0 3")
        result = find_best_move(board, depth=2)
        self.assertNotEqual(result.move, chess.Move.from_uci("f3d5"))


if __name__ == "__main__":
    unittest.main()
