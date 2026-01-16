from pygments.util import ClassNotFound
from pygments.lexers import get_lexer_by_name
from pygments.token import Token

SPECIAL = {Token.Name.Function.Magic, Token.Name.Function, Token.Name.Class}


def get_special_name_from_code(code: str, language: str) -> list[str]:
    try:
        lexer = get_lexer_by_name(
            language,
            stripnl=False,
            ensurenl=True,
            tabsize=8,
        )
    except ClassNotFound:
        lexer = get_lexer_by_name(
            "text",
            stripnl=False,
            ensurenl=True,
            tabsize=8,
        )
    special: list[str] = []
    for token_type, token in lexer.get_tokens(code):
        if token_type in SPECIAL:
            special.append(token)
    return special
