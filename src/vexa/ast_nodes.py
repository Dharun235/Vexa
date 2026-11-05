"""The syntax tree the parser produces: commands, expressions and the Vexa error type."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    """One statement of a program.

    kind names the command, argument holds its main operand, and line/column give its
    source position. Block commands keep their nested commands in body and orelse.
    """

    kind: str
    argument: str | None
    line: int
    column: int = 1
    confidence: float | None = None
    body: tuple = ()  # commands inside an if or for each block
    orelse: tuple = ()  # commands after else
    condition: "Expr | None" = None  # the expression an if tests
    origin: str | None = None  # library file a used define came from
    extra: object = None  # let: type; define: (return type, defaults); use: alias


@dataclass(frozen=True)
class Expr:
    """An expression node: kind names the operation, value holds its literal or name."""

    kind: str
    value: object = None
    args: tuple = ()
    line: int = 1
    column: int = 1


class VexaError(Exception):
    """An error to show the user, with its source position.

    kind is "syntax", "type", "runtime", "input" and so on; line and column are None
    when the error has no place in the source. file names the used library it came from.
    """

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
