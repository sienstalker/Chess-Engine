"""The worked Alpha-Beta example from the AIES notes, on an abstract game tree.

            A            MAX
         /     \\
        B       C        MIN
       / \\     / \\
      D   E   F   G      MAX
     /\\  /\\  /\\  /\\
    2 3 5 9 0 1 7 5      leaves (Utility values)

Expected (from the notes): value of A = 3; E's right child (9) is pruned
because at E alpha=5 >= beta=3; the whole subtree G is pruned because at C
alpha=3 >= beta=1.

Run:  python -m engine.tree_demo
"""

INF = float("inf")

TREE = {
    "A": ["B", "C"],
    "B": ["D", "E"],
    "C": ["F", "G"],
    "D": [2, 3],
    "E": [5, 9],
    "F": [0, 1],
    "G": [7, 5],
}


def alphabeta(node, alpha, beta, maximizing, visited, log, indent=0):
    """Same structure as Searcher.alphabeta in engine/search.py, on a tiny tree."""
    pad = "  " * indent
    if not isinstance(node, str):            # leaf: return its utility
        visited.append(node)
        return node

    log.append(f"{pad}{node} ({'MAX' if maximizing else 'MIN'}): alpha={alpha}, beta={beta}")
    children = TREE[node]
    if maximizing:
        value = -INF
        for i, child in enumerate(children):
            value = max(value, alphabeta(child, alpha, beta, False, visited, log, indent + 1))
            alpha = max(alpha, value)
            if alpha >= beta:
                log.append(f"{pad}  alpha={alpha} >= beta={beta} -> prune {children[i + 1:]}")
                break
    else:
        value = INF
        for i, child in enumerate(children):
            value = min(value, alphabeta(child, alpha, beta, True, visited, log, indent + 1))
            beta = min(beta, value)
            if alpha >= beta:
                log.append(f"{pad}  alpha={alpha} >= beta={beta} -> prune {children[i + 1:]}")
                break
    log.append(f"{pad}{node} returns {value}")
    return value


def run():
    visited, log = [], []
    value = alphabeta("A", -INF, INF, True, visited, log)
    return value, visited, log


if __name__ == "__main__":
    value, visited, log = run()
    print("\n".join(log))
    print(f"\nMinimax value of A: {value}")
    print(f"Leaves evaluated:   {visited}  ({len(visited)} of 8)")
