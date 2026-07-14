import ast
import glob
import builtins

def check_file(filepath):
    with open(filepath, 'r') as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        print(f"{filepath} SyntaxError: {e}")
        return

    # Track imported names
    imported_names = set(dir(builtins))
    imported_names.update(['False', 'True', 'None', 'self', 'Exception'])
    
    # We will just do a very primitive undefined name check
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.arg):
            imported_names.add(node.arg)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
            imported_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    imported_names.add(target.id)

    # Now check loads
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in imported_names:
                # We will ignore some common ones that might be dynamically assigned
                if node.id not in ['args', 'kwargs', 'super', 'print', '__file__', 'getattr', 'setattr', 'len', 'int', 'str', 'bool', 'isinstance', 'type', 'sum', 'open', 'range', 'enumerate']:
                    print(f"{filepath}:{node.lineno} possibly undefined name: {node.id}")

for f in glob.glob("src/*.py"):
    check_file(f)
