from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class WebsiteAuditState(str, Enum):
    NOT_RUN = "not_run"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WebsiteAuditResult:
    state: WebsiteAuditState
    reason: str
    audited_at: datetime
