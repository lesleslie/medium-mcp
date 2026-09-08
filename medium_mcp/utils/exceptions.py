from __future__ import annotations

from typing import Any


class MediumError(Exception):
    """Base for every medium-mcp raised exception.

    Carries a human-readable message and a structured context dict so
    upstream tools can render both: ``str(err)`` for logs and
    ``err.context`` / ``err.to_payload()`` for MCP error responses.
    """

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = dict(context or {})

    def __str__(self) -> str:
        if not self.context:
            return self.message
        ctx = ", ".join(f"{k}={v}" for k, v in sorted(self.context.items()))
        return f"{self.message} ({ctx})"


class ConfigurationError(MediumError):
    """Raised when a required setting is missing or malformed at startup."""


class UpstreamError(MediumError):
    """Raised when medium2 returns a non-success status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.status_code = status_code
        self.body = body


class RateLimitedError(UpstreamError):
    """Upstream returned 429; treat as transient, do not retry metered calls."""


class NotFoundError(UpstreamError):
    """Upstream returned 404; treat as terminal for the requested resource."""


class BudgetExhaustedError(MediumError):
    """Monthly budget exhausted or below headroom. Caller must NOT retry.

    The structured payload mirrors the spec's budget-error JSON so MCP
    clients can present ``cached_alternatives`` and the reset time.
    """

    def __init__(
        self,
        message: str,
        *,
        requested_calls: int,
        remaining_calls: int,
        monthly_budget: int,
        period: str,
        resets_at: str,
        cached_alternatives: list[str],
    ) -> None:
        super().__init__(
            message,
            context={
                "requested_calls": requested_calls,
                "remaining_calls": remaining_calls,
                "monthly_budget": monthly_budget,
                "period": period,
                "resets_at": resets_at,
            },
        )
        self.requested_calls = requested_calls
        self.remaining_calls = remaining_calls
        self.monthly_budget = monthly_budget
        self.period = period
        self.resets_at = resets_at
        self.cached_alternatives = cached_alternatives

    def to_payload(self) -> dict[str, Any]:
        """Exactly the spec §6.2 refusal payload — no extra keys.

        ``monthly_budget`` is deliberately absent: the refusal states what was
        asked for and what is left, and ``budget_remaining`` is the (free) tool
        that reports the configured budget.
        """
        return {
            "error": "budget_exhausted",
            "remaining_calls": self.remaining_calls,
            "requested_calls": self.requested_calls,
            "period": self.period,
            "resets_at": self.resets_at,
            "retryable": False,
            "cached_alternatives": self.cached_alternatives.copy(),
        }
