from cshit.lex.interfaces import TokenType, IToken
from cshit.utils import pretty_list


class ParserError(Exception):
    pass


class MessageError(ParserError):
    message: str

    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return self.message


class WrongToken(ParserError):
    got: IToken
    required: list[TokenType]
    def __init__(self, got: IToken, *required: TokenType):
        self.got = got
        self.required = list(required)

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"Required one of {pretty_list(self.required)}, but got {self.got}"


class IParser:
    pass