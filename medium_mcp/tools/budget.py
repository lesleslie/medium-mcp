from __future__ import annotations

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.models.dto import BudgetStatus


async def budget_remaining(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
) -> BudgetStatus:
    """Local read. Zero upstream calls. Spec §6.2.

    Delegates to ``Medium2Client.budget_status()`` rather than recomputing the
    period and reset time. Two implementations of "when does the month roll
    over" would eventually disagree, and the disagreement would be silent.
    """
    status = await client.budget_status()
    return BudgetStatus(
        remaining_calls=status["remaining_calls"],
        monthly_budget=status["monthly_budget"],
        period=status["period"],
        resets_at=status["resets_at"],
    )
