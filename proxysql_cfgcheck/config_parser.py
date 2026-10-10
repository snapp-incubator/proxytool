from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

@dataclass(frozen=True)
class Position:
    line: int
    column: int

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: Position

class ConfigSyntaxError(RuntimeError):
    def __init__(self, message: str, position: Position | None = None) -> None:
        if position:
            message = f"{message} at line {position.line}, column {position.column}"
        super().__init__(message)
        self.position = position


class Tokenizer:
    SYMBOLS = {"=", ",", ";", "{", "}", "(", ")"}

    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.index = 0
        self.line = 1
        self.column = 1

    def tokens(self) -> List[Token]:
        result: List[Token] = []
        while not self._eof:
            char = self._peek()
            if char in " \t\r":
                self._advance()
                continue
            if char == "\n":
                self._advance(newline=True)
                continue
            if char == "#":
                self._consume_comment()
                continue
            if char == '"':
                result.append(self._consume_string())
                continue
            if char in self.SYMBOLS:
                result.append(self._consume_symbol())
                continue
            if char.isdigit() or (char == "-" and self._peek_next().isdigit()):
                result.append(self._consume_number())
                continue
            if char.isalpha() or char == "_":
                result.append(self._consume_identifier())
                continue
            raise ConfigSyntaxError(f"Unexpected character '{char}'", self._position)
        return result

    def _consume_comment(self) -> None:
        while not self._eof and self._peek() != "\n":
            self._advance()

    def _consume_string(self) -> Token:
        start = self._position
        self._advance()
        chars: List[str] = []
        while not self._eof:
            ch = self._peek()
            if ch == '"':
                self._advance()
                literal = "".join(chars)
                return Token("STRING", _unescape_string(literal), start)
            if ch == "\\":
                self._advance()
                if self._eof:
                    raise ConfigSyntaxError("Unterminated escape sequence", start)
                chars.append(self._translate_escape(self._peek()))
                self._advance()
                continue
            chars.append(ch)
            self._advance()
        raise ConfigSyntaxError("Unterminated string literal", start)

    def _translate_escape(self, ch: str) -> str:
        escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
        return escapes.get(ch, ch)

    def _consume_symbol(self) -> Token:
        start = self._position
        char = self._peek()
        self._advance()
        return Token(char, char, start)

    def _consume_number(self) -> Token:
        start = self._position
        literal = []
        if self._peek() == "-":
            literal.append(self._peek())
            self._advance()
        while not self._eof and self._peek().isdigit():
            literal.append(self._peek())
            self._advance()
        if not self._eof and self._peek() == ".":
            literal.append(".")
            self._advance()
            if self._eof or not self._peek().isdigit():
                raise ConfigSyntaxError("Invalid number literal", start)
            while not self._eof and self._peek().isdigit():
                literal.append(self._peek())
                self._advance()
        return Token("NUMBER", "".join(literal), start)

    def _consume_identifier(self) -> Token:
        start = self._position
        literal = []
        while not self._eof and (self._peek().isalnum() or self._peek() == "_"):
            literal.append(self._peek())
            self._advance()
        return Token("IDENT", "".join(literal), start)

    @property
    def _eof(self) -> bool:
        return self.index >= self.length

    def _peek(self) -> str:
        return self.text[self.index]

    def _peek_next(self) -> str:
        if self.index + 1 >= self.length:
            return "\0"
        return self.text[self.index + 1]

    def _advance(self, newline: bool = False) -> None:
        self.index += 1
        if newline:
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    @property
    def _position(self) -> Position:
        return Position(self.line, self.column)


def parse_config(text: str) -> dict[str, Any]:
    tokens = Tokenizer(text).tokens()
    parser = _Parser(tokens)
    return parser.parse()


class _Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.index = 0

    def parse(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        while not self._at_end:
            key = self._consume("IDENT")
            self._consume("=")
            value = self._parse_value()
            config[key.value] = value
            self._consume_optional_setting_terminator()
        return config

    def _parse_value(self) -> Any:
        if self._match("STRING"):
            return self._previous().value
        if self._match("NUMBER"):
            literal = self._previous().value
            return float(literal) if "." in literal else int(literal)
        if self._match("IDENT"):
            ident = self._previous().value
            lowered = ident.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
            if lowered == "null":
                return None
            return ident
        if self._match("{"):
            return self._parse_object()
        if self._match("("):
            return self._parse_list()
        raise ConfigSyntaxError("Unexpected token", self._peek().position if not self._at_end else None)

    def _parse_object(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        while not self._check("}"):
            key = self._consume("IDENT")
            self._consume("=")
            data[key.value] = self._parse_value()
            self._consume_optional_setting_terminator()
        self._consume("}")
        return data

    def _parse_list(self) -> List[Any]:
        items: List[Any] = []
        while not self._check(")"):
            items.append(self._parse_value())
            self._consume_optional_separator(stop_token=")")
        self._consume(")")
        return items

    def _consume_optional_separator(self, stop_token: str) -> None:
        if self._check(stop_token):
            return
        if self._match(","):
            return

    def _consume_optional_setting_terminator(self) -> None:
        if self._match(";"):
            return
        self._match(",")

    def _match(self, kind: str) -> bool:
        if self._check(kind):
            self.index += 1
            return True
        return False

    def _check(self, kind: str) -> bool:
        if self._at_end:
            return False
        return self._peek().kind == kind

    def _consume(self, kind: str) -> Token:
        if self._check(kind):
            self.index += 1
            return self.tokens[self.index - 1]
        raise ConfigSyntaxError(f"Expected token '{kind}'", self._peek().position if not self._at_end else None)

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _previous(self) -> Token:
        return self.tokens[self.index - 1]

    @property
    def _at_end(self) -> bool:
        return self.index >= len(self.tokens)


def _unescape_string(literal: str) -> str:
    return literal
