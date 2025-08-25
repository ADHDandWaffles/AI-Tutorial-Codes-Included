import ast

def safe_eval_math(expr: str) -> str:
    node = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
               ast.USub, ast.UAdd, ast.FloorDiv, ast.AST)
    def check(n):
        if not isinstance(n, allowed): raise ValueError("Unsafe expression")
        for c in ast.iter_child_nodes(n): check(c)
    check(node)
    return str(eval(compile(node, "<math>", "eval"), {"__builtins__": {}}, {}))
