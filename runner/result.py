from dataclasses import dataclass, field
from enum import Enum


class TestStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class StepResult:
    step: str
    apdu_sent: str
    response: str
    status: "TestStatus"
    message: str = ""

    def serialise_to_dict(self) -> dict:
        return {
            "step": self.step,
            "apdu_sent": self.apdu_sent,
            "response": self.response,
            "status": self.status.value,
            "message": self.message,
        }


@dataclass
class TestResult:
    tc_id: str
    title: str
    domain: str
    status: "TestStatus" = field(default_factory=lambda: TestStatus.SKIP)
    steps: list[StepResult] = field(default_factory=list)
    duration_ms: float = 0.0
    description: str = ""

    def serialise_to_dict(self) -> dict:
        return {
            "tc_id": self.tc_id,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "steps": [s.serialise_to_dict() for s in self.steps],
        }
