from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StudioError(Exception):
    code: str
    message: str
    detail: dict[str, Any] | None = None
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


class NotFoundError(StudioError):
    def __init__(self, message: str = "Không tìm thấy dữ liệu") -> None:
        super().__init__("NOT_FOUND", message, status_code=404)


class ConflictError(StudioError):
    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, detail, 409)


class ProviderUnavailableError(StudioError):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__("PROVIDER_UNAVAILABLE", message, {"provider": provider}, 503)
