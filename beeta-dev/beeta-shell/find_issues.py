import ast
import os
import glob

def check_file(filepath):
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read())
    
    # Very basic check for missing imports (NameError) by tracking defined names vs used names
    # Actually, let's just write a mock for 'gi' and load them.
