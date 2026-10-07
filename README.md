# Alpha-Beta Chess — AIES Mini Project

Human vs Computer chess. The computer chooses its moves with **Minimax + Alpha-Beta
pruning**, written by hand from AIES Unit 1 ("Adversarial Search", pp. ~300–325).

- **Language:** Python 3
- **python-chess:** board representation and the rules of chess (legal moves, check, castling,
  en passant, draws). It is *not* used for any AI. All search code is in `engine/`.
- **pygame:** desktop GUI

## Setup & run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py                      # you play White, engine depth 3
python main.py --color black        # you play Black
python main.py --depth 4 --time 5   # stronger, up to 5 s per move
```
Controls: click a piece, then a destination square (pawns auto-promote to a queen).
`U` undo · `R` restart · `+`/`-` change search depth.

```bash
python -m engine.tree_demo          # the A–G worked example from the notes, traced
python compare.py                   # Minimax vs Alpha-Beta: same value, far fewer nodes
python -m unittest discover tests   # tests
```

## Project structure
```
main.py              command-line entry point
gui/app.py           pygame board, input, side panel with search statistics
engine/search.py     minimax + alpha-beta, move ordering, quiescence, iterative deepening
engine/evaluation.py heuristic evaluation (material + piece-square tables)
engine/tree_demo.py  alpha-beta on the abstract tree from the notes
compare.py           node-count comparison
tests/test_engine.py
```

## How the notes map onto the code
| Concept in the notes | Where |
|---|---|
| Initial state | `chess.Board()` |
| Player(s): MAX / MIN | White = MAX, Black = MIN (`maximizing` flag) |
| Actions(s) | `board.legal_moves`, ordered by `Searcher.order_moves` |
| Result(s, a) | `board.push(move)` / `board.pop()` |
| Terminal-Test(s) | no legal moves (mate/stalemate), draw rules: `Searcher.alphabeta` |
| Utility(s, p) | ±`MATE_SCORE` for a win/loss, 0 for a draw |
| Heuristic evaluation at the cutoff | `engine/evaluation.py: evaluate` |
| α = best for MAX (starts at −∞), β = best for MIN (starts at +∞) | `Searcher._search_root` |
| MAX updates only α, MIN updates only β | the two branches of `Searcher.alphabeta` |
| Prune when **α ≥ β** | `if self.use_pruning and alpha >= beta: break` |
| α, β passed down; node values passed up | arguments vs. `return value` |
| Move ordering: captures first, then threats, forward, backward | `order_moves` (MVV-LVA captures, promotions, checks, forward/backward) |
| "Bookkeep the states, as states may repeat" | transposition table keyed by Zobrist hash |
| Worked example (A…G, answer 3) | `engine/tree_demo.py` |
| Pruning doesn't change the result | `compare.py`, `test_pruning_gives_same_value_as_minimax` |

### Extensions beyond the notes
- **Iterative deepening:** searches depth 1, 2, …, N, and each iteration starts with the
  previous best move (near "ideal ordering"). It also lets the time limit stop the search safely.
- **Quiescence search:** at depth 0, captures are played out until the position is quiet. Without
  it the engine would think "QxP wins a pawn" and miss the recapture (the *horizon effect*).

## Sample result (`python compare.py`, depth 3)
| Position | Minimax nodes | Alpha-Beta nodes | Same value? |
|---|---|---|---|
| Start position | 9,762 | 781 | ✔ (50) |
| Italian game | 39,538 | 1,729 | ✔ (135) |
| Middlegame | 82,447 | 3,519 | ✔ (225) |
