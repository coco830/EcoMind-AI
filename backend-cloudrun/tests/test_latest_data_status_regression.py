from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from app.api.v1 import data as data_api


def test_get_latest_data_handles_rows_without_status(monkeypatch) -> None:
    async def fake_get_latest_values(self, device_ids=None, org_id=None, pollutant_code=None):
        return [
            {
                "ts": datetime(2026, 4, 9, 16, 0, 0),
                "device_id": "MN001",
                "pollutant_code": "w01018",
                "value": 42.5,
                "flag": "N",
            }
        ]

    monkeypatch.setattr(
        data_api.MonitoringService,
        "get_latest_values",
        fake_get_latest_values,
    )

    current_user = SimpleNamespace(
        is_superadmin=True,
        org_id=None,
        organization=None,
    )

    responses = asyncio.run(
        data_api.get_latest_data(
            current_user=current_user,
            db=object(),
            device_id=None,
            limit=100,
        )
    )

    assert len(responses) == 1
    assert responses[0].device_id == "MN001"
    assert responses[0].status == 0
