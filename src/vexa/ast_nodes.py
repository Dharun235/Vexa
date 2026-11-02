from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    kind: str
    argument: str | None
    line: int
    column: int = 1
    confidence: float | None = None


class VexaError(Exception):
    def __init__(
        self,
        message: str,
        line: int | None = None,
        kind: str = "runtime",
        column: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.kind = kind
        self.column = column
