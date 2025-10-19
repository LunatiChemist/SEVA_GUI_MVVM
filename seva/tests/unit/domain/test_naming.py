from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from seva.domain.entities import ClientDateTime, GroupId, PlanMeta
from seva.domain.naming import make_group_id


def _meta(experiment: str, subdir: str | None, client_dt: datetime) -> PlanMeta:
    return PlanMeta(
        experiment=experiment,
        subdir=subdir,
        client_dt=ClientDateTime(client_dt),
        group_id=GroupId("placeholder"),
    )


@patch("seva.domain.naming.random.choices", return_value=list("ABCD"))
def test_make_group_id_includes_subdir_and_datetime(mock_choices) -> None:
    meta = _meta(
        experiment="Battery Screening",
        subdir="plate 01",
        client_dt=datetime(2025, 10, 18, 15, 0, tzinfo=timezone.utc),
    )
    group_id = make_group_id(meta)
    token = str(group_id)

    assert token.startswith("Battery_Screening_plate_01__")
    assert "__20251018T150000Z__" in token
    assert token.endswith("__ABCD")
    mock_choices.assert_called_once()


@patch("seva.domain.naming.random.choices", return_value=list("1234"))
def test_make_group_id_sanitizes_components(_mock_choices) -> None:
    meta = _meta(
        experiment="  !Str@nge Name  ",
        subdir="Sub/Dir?",
        client_dt=datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc),
    )
    group_id = make_group_id(meta)

    assert group_id.value.startswith("Str_nge_Name_Sub_Dir__20250102T030400Z__1234")


@patch("seva.domain.naming.random.choices", return_value=list("ZXCV"))
def test_make_group_id_handles_missing_subdir(_mock_choices) -> None:
    meta = _meta(
        experiment="Quick Check",
        subdir=None,
        client_dt=datetime(2025, 6, 1, 8, 30, tzinfo=timezone.utc),
    )
    group_id = make_group_id(meta)

    assert group_id.value.startswith("Quick_Check__20250601T083000Z__ZXCV")
