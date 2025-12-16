import os

os.environ["PYTHONWARNINGS"] = "ignore::SyntaxWarning"

from toad.cli import main

if __name__ == "__main__":
    main()
