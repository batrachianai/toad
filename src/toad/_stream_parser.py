import io
import re

import rich.repr

from typing import Generator, Iterable


type ParseResult[ParseType] = Generator[StreamRead | ParseType, Token, None]
type PatternCheck = Generator[None, str, object | None]


@rich.repr.auto
class Pattern[ValueType]:
    def __init__(self) -> None:
        self._generator = self.check()
        next(self._generator)
        self.value: ValueType | None = None

    def feed(self, text: str) -> bool | None:
        try:
            for character in text:
                self._generator.send(character)
        except StopIteration as stop_iteration:
            return stop_iteration.value
        else:
            return None

    def check(self) -> PatternCheck:
        return False
        yield


class StreamRead[ResultType]:
    pass


@rich.repr.auto
class Read[ResultType](StreamRead[ResultType]):
    def __init__(self, count: int) -> None:
        self.remaining = count


@rich.repr.auto
class ReadUntil[ResultType](StreamRead[ResultType]):
    def __init__(self, *characters: str) -> None:
        self.characters = characters
        self._regex = re.compile(
            "|".join(re.escape(character) for character in characters)
        )

    def __rich_repr__(self) -> rich.repr.Result:
        yield from self.characters


@rich.repr.auto
class ReadRegex[ResultType](StreamRead[ResultType]):
    def __init__(self, regex: str, max_length: int | None = None) -> None:
        self.regex = regex
        self.max_length = max_length
        self._buffer = io.StringIO()

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.regex

    @property
    def buffer_size(self) -> int:
        return self._buffer.tell()


@rich.repr.auto
class ReadPatterns[ResultType](StreamRead[ResultType]):
    def __init__(self, start: str = "", **patterns: Pattern) -> None:
        self.patterns = patterns
        self._text: list[str] = [start] if start else []

    @property
    def unconsumed_text(self) -> str:
        return "".join(self._text)

    def __rich_repr__(self) -> rich.repr.Result:
        for key, value in self.patterns.items():
            yield key, value

    @property
    def is_exhausted(self) -> bool:
        return not self.patterns

    def feed(self, text: str) -> tuple[int, tuple[str, object] | None]:
        consumed = 0
        for consumed, character in enumerate(text, 1):
            items = list(self.patterns.items())
            for name, sequence_validator in items:
                value = sequence_validator.feed(character)
                if value is False:
                    self.patterns.pop(name)
                elif value:
                    return consumed, (name, value)
        self._text.append(text[:consumed])
        return consumed, None


@rich.repr.auto
class Token:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.text

    def __str__(self) -> str:
        return self.text


class SeparatorToken(Token):
    pass


class MatchToken(Token):
    def __init__(self, text: str, match: re.Match) -> None:
        self.match = match
        super().__init__(text)

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.match


class EOFToken(Token):
    pass


class PatternToken(Token):
    def __init__(self, name: str, value: object) -> None:
        self.name = name
        self.value = value
        super().__init__("")

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.name
        yield None, self.value


class StreamParser[ParseType]:
    def __init__(self):
        self._gen = self.parse()
        self._reading: StreamRead | ParseType = next(self._gen)

    def read(self, count: int) -> Read:
        return Read(count)

    def read_until(self, *characters: str) -> ReadUntil:
        """Read until the given characters."""
        return ReadUntil(*characters)

    def read_regex(self, regex: str) -> ReadRegex:
        """Search for the matching regex."""
        return ReadRegex(regex)

    def read_patterns(self, start: str = "", **patterns) -> ReadPatterns:
        """Read until a pattern matches, or the patterns have been exhausted.

        Args:
            start: Initial part of the string.
            **patterns: One or more patterns.


        """
        return ReadPatterns(start, **patterns)

    def feed(self, text: str) -> Iterable[Token]:
        if not text or self._gen is None:
            yield EOFToken()
            return

        def send(token: Token) -> Iterable[Token]:
            try:
                while True:
                    new_token = self._gen.send(token)
                    if isinstance(new_token, StreamRead):
                        self._reading = new_token
                        break
                    else:
                        token = new_token
                        yield token

            except StopIteration:
                self._gen.close()
                self._gen = None

        while text:
            if isinstance(self._reading, Read):
                if self._reading.remaining:
                    read_text = text[: self._reading.remaining]
                    read_text_length = len(read_text)
                    self._reading.remaining -= read_text_length
                    text = text[read_text_length:]
                    yield from send(Token(read_text))
                else:
                    yield from send(Token(""))

            elif isinstance(self._reading, ReadUntil):
                if (match := self._reading._regex.search(text)) is not None:
                    start, end = match.span(0)
                    read_text = text[:start]

                    if read_text:
                        yield from send(Token(read_text))
                        text = text[start:]
                    else:
                        yield from send(SeparatorToken(text[start:end]))
                        text = text[end:]
                else:
                    yield from send(Token(text))
                    text = ""

            elif isinstance(self._reading, ReadRegex):
                self._reading._buffer.write(text)
                match_text = self._reading._buffer.getvalue()
                if (
                    match := re.search(self._reading.regex, match_text, re.VERBOSE)
                ) is not None:
                    token_text = match_text[: match.start(0)]
                    if token_text:
                        yield from send(Token(token_text))
                    end = match.end(0)
                    yield from send(MatchToken(match.group(0), match))
                    text = text[end:]
                else:
                    yield from send(Token(match_text))
                    text = ""

            elif isinstance(self._reading, ReadPatterns):
                consumed, pattern_match = self._reading.feed(text)

                if pattern_match is not None:
                    name, value = pattern_match
                    yield from send(PatternToken(name, value))
                    text = text[consumed:]
                else:
                    if self._reading.is_exhausted:
                        unconsumed_text = self._reading.unconsumed_text
                        yield from send(Token(unconsumed_text))
                        text = text[consumed:]
                    else:
                        text = ""

    def parse(self) -> ParseResult[ParseType]:
        yield from ()


if __name__ == "__main__":
    # from rich import print

    import string

    class KeyValue(Pattern):
        def check(self) -> PatternCheck:
            """Parses text in the form key:'value'

            e.g

            """
            key: str = ""
            value: str = ""
            is_letter = string.ascii_lowercase.__contains__
            if not is_letter(character := (yield)):
                return False
            key += character
            while is_letter(character := (yield)):
                key += character
            if character != ":":
                return False
            if (yield) != "'":
                return False
            while is_letter(character := (yield)):
                value += character
            if character != "'":
                return False
            self.value = (key, value)
            return True

    class TestParser(StreamParser):
        def parse(self) -> ParseResult:
            token = yield self.read_patterns(key_value=KeyValue())
            print("!", repr(token))
            yield token
            while token := (yield self.read(1)):
                print(repr(token))
            # while True:
            #     token = yield self.read_until(":")
            #     if not token:
            #         break
            #     yield token
            #     if isinstance(token, SeparatorToken):
            #         break
            #     key += token.text

            # while token := (yield self.read_regex(r"\'.*?\'")):
            #     yield token
            #     if isinstance(token, MatchToken):
            #         break

            # string = yield self.read_regex("'.*?'")
            # print("VALUE=", string)

            # yield (yield self.read(3))
            # while (text := (yield self.read_until("'"))) != "'":
            #     yield text
            # yield text
            # while (text := (yield self.read_until("'"))) != "'":
            #     yield text
            # yield text

    parser = TestParser()

    for chunk in ["foo", ":", "'bar", "asd", "asdasd", "';"]:
        for token in parser.feed(chunk):
            print(repr(token))
