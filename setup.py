import ast
from pathlib import Path

from setuptools import setup


def read_version():
    """Read the standalone script's version without importing the CLI."""
    script = Path(__file__).with_name("frames")
    tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "VERSION"
            for target in statement.targets
        ):
            return ast.literal_eval(statement.value)
    raise ValueError("VERSION assignment not found in frames")


setup(version=read_version())
