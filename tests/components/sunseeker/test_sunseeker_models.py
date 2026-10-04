"""Tests for Sunseeker schedule and state model classes."""

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_new_schedule_generates_api_payload() -> None:
    """Test enabled slots serialize with correct weekdays and zone names."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        Sunseeker_new_schedule,
    )

    schedule = Sunseeker_new_schedule()
    schedule.zones = [(1, "Front"), (2, "Back")]
    schedule.schedule_pause = True
    monday_first = schedule.GetDay(1, 1)
    monday_first.enabled = True
    monday_first.start = 8 * 3600
    monday_first.end = 10 * 3600 + 30 * 60
    monday_first.region_id = [2]

    payload = schedule.GenerateAttributeData()

    assert payload["pause"] is True
    assert payload["locations"] == ["Front", "Back"]
    assert payload["monday"][0] == {
        "enabled": True,
        "starttime": "08:00",
        "endtime": "10:30",
        "locations": ["Back"],
    }
    assert payload["monday"][1]["enabled"] is False
    assert schedule.generate_enabled_time_list(payload) == [
        {
            "unlock": True,
            "period": [1],
            "start": 8 * 3600,
            "active": True,
            "end": 10 * 3600 + 30 * 60,
            "need_fllow_boader": False,
            "region_id": [2],
        }
    ]


async def test_new_schedule_parses_v_payload() -> None:
    """Test parsing wireless schedule data into day and slot state."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        Sunseeker_new_schedule,
    )

    schedule = Sunseeker_new_schedule()
    schedule.zones = [(1, "Front")]
    schedule.parse_schedule_data_V(
        {
            "data": {
                "pause": True,
                "recommendedTimeFlag": True,
                "timeCustomFlag": False,
                "timeZone": "Europe/Copenhagen",
                "time": [
                    {
                        "period": [1],
                        "start": 28800,
                        "end": 36000,
                        "region_id": [1],
                        "active": True,
                        "needFllowBoader": True,
                    }
                ],
            }
        }
    )

    monday = schedule.GetDay(1, 1)
    assert monday.enabled is True
    assert monday.start == 28800
    assert monday.end == 36000
    assert monday.region_id == [1]
    assert monday.need_fllow_boader is True
    assert schedule.schedule_pause is True
    assert schedule.schedule_recommended is True
    assert schedule.schedule_custom is False
    assert schedule.timezone == "Europe/Copenhagen"
    assert schedule.GenerateTimeData() == [
        {
            "period": [1],
            "unlock": True,
            "region_id": [1],
            "start": 28800,
            "active": True,
            "end": 36000,
            "need_fllow_boader": True,
        }
    ]


async def test_v1_schedule_payload_formatting() -> None:
    """Test V1 schedule serialization preserves time and weekday conventions."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        Sunseeker_new_schedule,
    )

    schedule = Sunseeker_new_schedule()
    payload = {
        "monday": [
            {
                "enabled": True,
                "starttime": "06:30",
                "endtime": "08:00:00",
            }
        ],
        "sunday": [
            {
                "enabled": True,
                "starttime": "21:15",
                "endtime": "22:45",
            }
        ],
    }

    assert schedule.generate_enabled_time_list_V1(payload) == [
        {
            "dayOfWeek": 1,
            "startAt": "06:30:00",
            "endAt": "08:00:00",
            "trimFlag": True,
        },
        {
            "dayOfWeek": 7,
            "startAt": "21:15:00",
            "endAt": "22:45:00",
            "trimFlag": True,
        },
    ]


async def test_old_schedule_mqtt_updates_and_serializes_two_slots() -> None:
    """Test MQTT schedule parsing handles midnight and an absent second slot."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        SunseekerSchedule,
        SunseekerSchedule2,
    )

    schedule = SunseekerSchedule()
    schedule.UpdateFromMqtt(
        {
            "slice": [{"start": 480, "end": 1440}],
            "Trimming": True,
        },
        1,
    )
    assert schedule.GetDay(1).start == "08:00"
    assert schedule.GetDay(1).end == "24:00"
    assert schedule.GetDay(1).trim is True
    assert schedule.IsEmpty() is False

    schedule2 = SunseekerSchedule2()
    schedule2.UpdateFromMqtt(
        {
            "slice": [
                {"start": 480, "end": 600},
                {"start": 780, "end": 900},
            ],
            "Trimming": [True, False],
        },
        1,
    )
    payload = schedule2.GenerateAttributeData()
    assert payload["monday"] == [
        {"enabled": True, "starttime": "08:00", "endtime": "10:00", "trim": True},
        {"enabled": True, "starttime": "13:00", "endtime": "15:00", "trim": False},
    ]

    schedule2.UpdateFromMqtt({"slice": []}, 1)
    assert schedule2.GetDay(1, 1).enabled is False
    assert schedule2.GetDay(1, 2).enabled is False


async def test_zone_and_consumable_defaults_are_independent() -> None:
    """Test each mower model instance owns its mutable defaults."""
    from custom_components.sunseeker.sunseeker_consumable_items import (  # noqa: PLC0415
        SunseekerConsumableItems,
    )
    from custom_components.sunseeker.sunseeker_zone import (  # noqa: PLC0415
        SunseekerZone,
    )

    first = SunseekerZone()
    second = SunseekerZone()
    first.multi_zigzag_angles.append(15)
    first.zigzag_1.angle = 45
    assert second.multi_zigzag_angles == []
    assert second.zigzag_1.angle == 0

    consumables = SunseekerConsumableItems()
    assert consumables.blade is not consumables.small_blade
    assert consumables.cutter is not consumables.small_cutter
    consumables.blade.twt = 100
    assert consumables.small_blade.twt == 0
