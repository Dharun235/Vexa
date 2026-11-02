from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    kind: str
    argument: str | None
    line: int


class VexaError(Exception):
    def __init__(self, message: str, line: int | None = None, kind: str = "runtime"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.kind = kind

    def as_dict(self):
        return {"kind": self.kind, "message": self.message, "line": self.line}
