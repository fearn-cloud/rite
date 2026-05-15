from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationError:
    code: str
    path: str
    message: str
