"""Compare plain Minimax with Alpha-Beta pruning on a few positions.

Shows the two claims from the notes:
  * "Pruning does not affect final result" -> both give the same value
  * pruning (helped by good move ordering) visits far fewer nodes

    python compare.py            # depth 3
    python compare.py --depth 2
"""

import argparse

import chess

from engine.search import find_best_move

POSITIONS = {
    "Start position": chess.STARTING_FEN,
    "Italian game": "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "Middlegame": "r2q1rk1/pp2bppp/2n1bn2/3p4/3P4/2NBBN2/PP3PPP/R2Q1RK1 w - - 0 11",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=3)
    args = parser.parse_args()

    header = f"{'Position':<16}{'Algorithm':<12}{'Value':>8}{'Nodes':>12}{'Cutoffs':>10}{'Time':>9}"
    print(header)
    print("-" * len(header))
    for name, fen in POSITIONS.items():
        board = chess.Board(fen)
        for label, pruning in (("Minimax", False), ("Alpha-Beta", True)):
            # Quiescence and the transposition table are switched off so that
            # the only difference between the two rows is the pruning itself.
            result = find_best_move(board, depth=args.depth, use_pruning=pruning,
                                    use_quiescence=False, use_tt=False)
            s = result.stats
            print(f"{name:<16}{label:<12}{result.score:>8}{s.nodes:>12,}{s.cutoffs:>10,}{s.time:>8.2f}s")
        print()


if __name__ == "__main__":
    main()
