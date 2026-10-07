"""Play chess against a Minimax + Alpha-Beta pruning engine.

    python main.py                      # you are White, engine searches 3 plies
    python main.py --color black        # you are Black, the engine moves first
    python main.py --depth 4 --time 5   # deeper search, up to 5 s per move
"""

import argparse

import chess

from gui.app import run


def main():
    parser = argparse.ArgumentParser(description="Human vs Computer chess (Alpha-Beta pruning)")
    parser.add_argument("--depth", type=int, default=3, help="search depth in plies (default 3)")
    parser.add_argument("--color", choices=["white", "black"], default="white", help="your colour")
    parser.add_argument("--time", type=float, default=3.0, help="max seconds per AI move (default 3)")
    args = parser.parse_args()

    run(depth=args.depth,
        human_color=chess.WHITE if args.color == "white" else chess.BLACK,
        time_limit=args.time)


if __name__ == "__main__":
    main()
