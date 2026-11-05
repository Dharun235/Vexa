from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    kind: str
    argument: str | None
    line: int
    column: int = 1
    confidence: float | None = None
    body: tuple = ()  # commands inside an if or for each block
    orelse: tuple = ()  # commands after else
    condition: "Expr | None" = None  # the expression an if tests
    origin: str | None = None  # library file a used define came from


@dataclass(frozen=True)
class Expr:
    """An expression node: kind names the operation, value holds its literal or name."""

    kind: str
    value: object = None
    args: tuple = ()
    line: int = 1
    column: int = 1


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
        self.file = None  # set when the error is in a used library file
