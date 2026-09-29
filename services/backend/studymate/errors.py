"""Errors that carry a user-facing (Korean) message to the client."""

from __future__ import annotations


class UserFacingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ModelMissingError(UserFacingError):
    def __init__(self, what: str) -> None:
        super().__init__(
            "model_missing", f"{what} 모델이 설치되어 있지 않습니다. 설정 > 모델에서 받아주세요."
        )
