from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .domain import ActionRequest, ActionResult, OperationalEvent


class Clock(Protocol):
    def now(self) -> datetime: ...


class SourceAdapter(Protocol):
    identity: str
    def normalize(self, raw: dict) -> OperationalEvent: ...


class ChannelProvider(Protocol):
    identity: str
    def send(self, request: ActionRequest) -> ActionResult: ...
