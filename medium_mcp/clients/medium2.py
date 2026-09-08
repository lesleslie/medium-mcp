from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx2

from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.dhara.keys import budget_key
from medium_mcp.utils.exceptions import (
    BudgetExhaustedError,
    ConfigurationError,
    NotFoundError,
    RateLimitedError,
    UpstreamError,
)


class Medium2Client:
    """Typed wrapper around httpx2 that enforces the budget guard.

    Each call:
    1. Gates on Dhara reachability — with no counter there is no guard, so the
       call is refused rather than made unmetered.
    2. Reserves ``min_cost * max_pages`` budget via ``DharaClient.inc_atomic``,
       whose headroom check and write both happen inside the per-month lock.
    3. Issues a single GET to the upstream (medium2 is paginated; pagination is
       the caller's responsibility, not the client's).
    4. Keeps the reservation on success **and** on any upstream error (per spec
       §6.2: failed calls count).

    **Multi-page reservations are NOT supported in v1.** ``max_pages=1`` is the
    only allowed value, enforced by the lock acquiring exactly the requested
    count: the reservation is taken atomically as one increment, so there is no
    partial-reservation state to unwind. ``_release_reservation`` exists only for
    the pre-flight failure path (reserved but never dispatched); it is not a
    per-page refund mechanism. Supporting ``max_pages > 1`` would require either
    holding the lock across N network calls or reintroducing a refund race, and
    v1 does neither.
    """

    def __init__(
        self,
        *,
        settings: MediumSettings,
        dhara: DharaClient,
        transport: httpx2.MockTransport | None = None,
    ) -> None:
        self.settings = settings
        self.dhara = dhara
        self._transport = transport

    def _period(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    def current_period(self) -> str:
        """Public accessor for the YYYY-MM budget period.

        Wraps ``_period`` so external callers (tests, ``tools/budget.py``) do not
        have to reach into a private attribute. Tests that need to assert against
        the period key should call ``client.current_period()`` — the private
        name is preserved for backward compatibility with any code that already
        reached for ``client._period()``.
        """
        return self._period()

    def _resets_at(self) -> str:
        return (
            (datetime.now(UTC).replace(day=1) + timedelta(days=32))
            .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _budget_ceiling(self) -> int:
        """Reservations may never push the counter past this value."""
        return self.settings.monthly_budget - self.settings.budget_reserve_headroom

    async def _reserve_budget(self, calls: int) -> tuple[int, str]:
        """Reserve ``calls`` against the month's counter, atomically.

        The read, the headroom check, and the write all happen inside
        ``DharaClient.inc_atomic``'s lock. Nothing here inspects the counter
        first: doing so would reintroduce the check-then-act race this method
        exists to close.

        Returns ``(counter_value_after_reservation, period)``. Raises
        ``BudgetExhaustedError`` when the reservation would breach the ceiling —
        in which case the counter was **not** advanced.
        """
        period = self._period()
        key = budget_key(period)
        ceiling = self._budget_ceiling()
        counter, accepted = await self.dhara.inc_atomic(
            key,
            increment=calls,
            max_value=ceiling,
        )
        if not accepted:
            raise BudgetExhaustedError(
                "monthly budget exhausted or below headroom",
                requested_calls=calls,
                remaining_calls=max(0, ceiling - counter),
                monthly_budget=self.settings.monthly_budget,
                period=period,
                resets_at=self._resets_at(),
                cached_alternatives=self._cached_alternatives(),
            )
        return counter, period

    async def _release_reservation(self, period: str, calls: int) -> None:
        """Give back a reservation that was taken but never dispatched.

        Uses the same per-period lock as ``_reserve_budget`` so a release can
        never interleave with another reservation's read-check-write. Only the
        pre-flight failure path calls this; a call that reached RapidAPI keeps
        its reservation regardless of status (spec §6.2).
        """
        if calls <= 0:
            return
        await self.dhara.dec_atomic(budget_key(period), decrement=calls)

    @staticmethod
    def _cached_alternatives() -> list[str]:
        """Tools whose output is cacheable and may serve recent reads."""
        return ["user_info", "article_metadata", "tag_info"]

    async def budget_status(self) -> dict[str, Any]:
        """Single source of truth for period, reset time, and remaining calls.

        ``tools/budget.budget_remaining`` converts this dict into a
        ``BudgetStatus`` and computes nothing itself.
        """
        period = self._period()
        key = budget_key(period)
        used = await self.dhara.get_counter(key)
        return {
            "calls_used": used,
            "remaining_calls": max(0, self.settings.monthly_budget - used),
            "monthly_budget": self.settings.monthly_budget,
            "period": period,
            "resets_at": self._resets_at(),
        }

    async def request(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        min_cost: int = 1,
        max_pages: int = 1,
        tool_name: str,
    ) -> dict[str, Any]:
        self._check_max_pages(max_pages, tool_name)
        await self._ensure_dhara_reachable(tool_name)
        reserved = min_cost * max_pages
        _counter, period = await self._reserve_budget(reserved)
        key_value = await self._take_rapidapi_key(period, reserved, tool_name)
        response = await self._dispatch(endpoint, params, key_value, tool_name)
        self._raise_for_status(response, endpoint, tool_name)
        return self._parse_body(response)

    def _check_max_pages(self, max_pages: int, tool_name: str) -> None:
        if max_pages != 1:
            raise ConfigurationError(
                "max_pages > 1 is not supported in v1; reserve one page per call",
                context={"max_pages": max_pages, "tool": tool_name},
            )

    async def _ensure_dhara_reachable(self, tool_name: str) -> None:
        """Dhara-down gate. No counter means no guard.

        An unguarded metered call is budget we can never account for, so
        refuse before reserving.
        """
        if await self.dhara.probe():
            return
        raise UpstreamError(
            "dhara unreachable; refusing metered call",
            status_code=0,
            body="",
            context={"reason": "dhara_unreachable", "tool": tool_name},
        )

    async def _take_rapidapi_key(self, period: str, reserved: int, tool_name: str) -> str:
        """Return the secret or release the reservation and raise."""
        if self.settings.rapidapi_key is None:
            # Reserved but never dispatched — hand the reservation back.
            await self._release_reservation(period, reserved)
            raise ConfigurationError(
                "rapidapi_key missing — validate_rapidapi_key must run at startup",
                context={"env_var": "MEDIUM_MCP_RAPIDAPI_KEY", "tool": tool_name},
            )
        return self.settings.rapidapi_key.get_secret_value()

    def _build_transport(self) -> httpx2.MockTransport | httpx2.AsyncHTTPTransport:
        if self._transport is not None:
            return self._transport
        return httpx2.AsyncHTTPTransport()

    @staticmethod
    def _build_headers(key_value: str) -> dict[str, str]:
        return {
            "X-RapidAPI-Key": key_value,
            "X-RapidAPI-Host": "medium2.p.rapidapi.com",
        }

    async def _dispatch(
        self,
        endpoint: str,
        params: dict[str, Any],
        key_value: str,
        tool_name: str,
    ) -> httpx2.Response:
        base = self.settings.rapidapi_base_url.rstrip("/")
        url = urljoin(base + "/", endpoint)
        try:
            async with httpx2.AsyncClient(
                transport=self._build_transport(),
                timeout=self.settings.http_timeout_seconds,
            ) as http:
                return await http.get(
                    url,
                    params=params,
                    headers=self._build_headers(key_value),
                )
        except httpx2.HTTPError as exc:
            # Network errors: count as metered (spec rule).
            raise UpstreamError(
                "transport error talking to medium2",
                status_code=0,
                body=str(exc),
                context={"endpoint": endpoint, "tool": tool_name},
            ) from exc

    @staticmethod
    def _raise_for_status(response: httpx2.Response, endpoint: str, tool_name: str) -> None:
        """Any non-2xx counts as a metered failure (spec rule)."""
        code = response.status_code
        if code == 404:
            raise NotFoundError(
                "medium2 returned 404",
                status_code=404,
                body=response.text,
                context={"endpoint": endpoint, "tool": tool_name},
            )
        if code == 429:
            raise RateLimitedError(
                "medium2 returned 429",
                status_code=429,
                body=response.text,
                context={"endpoint": endpoint, "tool": tool_name},
            )
        if code >= 400:
            raise UpstreamError(
                f"medium2 returned {code}",
                status_code=code,
                body=response.text,
                context={"endpoint": endpoint, "tool": tool_name},
            )

    @staticmethod
    def _parse_body(response: httpx2.Response) -> dict[str, Any]:
        """The reservation stands: this call reached RapidAPI (spec §6.2)."""
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw": response.text}
