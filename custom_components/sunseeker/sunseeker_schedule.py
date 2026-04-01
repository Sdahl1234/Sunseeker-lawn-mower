"""SunseekerPy."""

import json
import logging
import time
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from .sunseeker import SunseekerDevice


_LOGGER = logging.getLogger(__name__)


class Sunseeker_new_schedule_day:
    """Day class."""

    def __init__(self, day: int, index: int) -> None:
        """Init."""
        self.day = day
        self.day_index = index
        self.unlock = True
        self.region_id = []
        self.start = 0  # 25200,
        self.active = True
        self.end = 0  # 43200,
        self.need_fllow_boader = False
        self.enabled = False


class Sunseeker_new_schedule:
    """Schedule class."""

    def __init__(self) -> None:
        """Init."""
        self.mower: SunseekerDevice
        self.schedule_pause: bool = False
        self.schedule_custom: bool = False
        self.schedule_recommended: bool = False
        self.zones = []
        self.timezone = None
        self.days: list[Sunseeker_new_schedule_day] = []
        for x in range(1, 8):
            self.days.append(Sunseeker_new_schedule_day(x - 1, 1))
            self.days.append(Sunseeker_new_schedule_day(x - 1, 2))

    def GetDay(self, daynumber: int, index: int) -> Sunseeker_new_schedule_day:
        """Get the day."""
        for day in self.days:
            if (day.day == daynumber) and (day.day_index == index):
                return day
        return None

    def Mapday(self, day) -> str:
        """Maps daynumber to text."""
        if day == 1:
            return "monday"
        if day == 2:
            return "tuesday"
        if day == 3:
            return "wednesday"
        if day == 4:
            return "thursday"
        if day == 5:
            return "friday"
        if day == 6:
            return "saturday"
        if day == 0:
            return "sunday"
        return ""

    def get_id_by_name(self, names: list[str]) -> list[int]:
        """Converts the list of names to zone ids."""
        ids: list[int] = []
        for zone_id, zone_name in self.zones:
            if zone_name in names:
                ids.append(zone_id)
        return ids

    def seconds_to_hhmm(self, seconds):
        """Sec to hhmm format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:02}:{minutes:02}"

    def GenerateAttributeData(self):
        """Generate att data."""
        schedule = {
            "recommended_time_work": self.schedule_recommended,
            "user_defined": self.schedule_custom,
            "pause": self.schedule_pause,
            "locations": [],
            "monday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "tuesday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "wednesday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "thursday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "friday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "saturday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "sunday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
        }
        for zone in self.zones:
            zoneid, zonename = zone
            schedule["locations"].append(zonename)
        for day in self.days:
            daytext = self.Mapday(day.day)
            dayindex = day.day_index - 1
            schedule[daytext][dayindex]["enabled"] = day.enabled
            schedule[daytext][dayindex]["starttime"] = self.seconds_to_hhmm(day.start)
            schedule[daytext][dayindex]["endtime"] = self.seconds_to_hhmm(day.end)
            for loc in day.region_id:
                for zone in self.zones:
                    zoneid, zonename = zone
                    if loc == zoneid:
                        schedule[daytext][dayindex]["locations"].append(zonename)

        return schedule

    def GenerateTimeData(self) -> list:
        """Generate Timedata to send."""
        data = []
        for day in self.days:
            if day.enabled:
                daydata = {
                    "period": [day.day],
                    "unlock": day.unlock,
                    "region_id": day.region_id,
                    "start": day.start,
                    "active": day.active,
                    "end": day.end,
                    "need_fllow_boader": day.need_fllow_boader,
                }
                data.append(daydata)
        return data

    def hhmm_to_seconds(self, hhmm: str) -> int:
        """Convert a time string in 'HH:MM' format to seconds since midnight."""
        try:
            hours, minutes = map(int, hhmm.split(":"))
            return hours * 3600 + minutes * 60
        except Exception as err:  # noqa: BLE001, F841
            # raise ValueError(f"Invalid time format '{hhmm}': {err}") from
            return 0

    def generate_enabled_time_list_V1(self, schedule: dict) -> list[dict]:
        """Generate a list of enabled time entries in the required V1 format."""

        def to_hms(value: str) -> str:
            # "09:00" -> "09:00:00", keeps "HH:MM:SS" unchanged
            return value if value.count(":") == 2 else f"{value}:00"

        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]

        out: list[dict] = []

        for day_index, day_name in enumerate(days, start=1):
            for entry in schedule.get(day_name, []):
                if entry.get("enabled") is True:
                    out.append(  # noqa: PERF401
                        {
                            "dayOfWeek": day_index,  # Monday=1
                            "startAt": to_hms(entry["starttime"]),
                            "endAt": to_hms(entry["endtime"]),
                            "trimFlag": True,
                        }
                    )
        return out

    def generate_enabled_time_list(self, schedule: dict) -> list[dict]:
        """Generate a list of enabled time entries in the required format."""

        time_list: list[dict] = []
        day_order = [
            "sunday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
        ]
        # for day, entries in schedule.items():
        for day, entries in sorted(
            schedule.items(),
            key=lambda x: (
                day_order.index(x[0].lower()) if x[0].lower() in day_order else 99
            ),
        ):
            # Convert day name to period number (Monday=1, ..., Sunday=7)
            day_to_period = {
                "sunday": 0,
                "monday": 1,
                "tuesday": 2,
                "wednesday": 3,
                "thursday": 4,
                "friday": 5,
                "saturday": 6,
            }
            period = (
                [day_to_period.get(day.lower())]
                if day.lower() in day_to_period
                else None
            )
            if not period:
                continue
            for entry in entries:
                if not entry.get("enabled"):
                    continue
                item: dict = {
                    "unlock": True,
                    "period": period,
                    "start": self.hhmm_to_seconds(entry.get("starttime")),
                    "active": True,
                    "end": self.hhmm_to_seconds(entry.get("endtime")),
                    "need_fllow_boader": False,
                }
                # Optionally add region_id if present and non-empty
                if entry.get("locations"):
                    item["region_id"] = self.get_id_by_name(entry["locations"])
                time_list.append(item)
        return time_list

    def parse_schedule_data_V1(self, data):
        """Parsing schedule data V model."""
        need_update = False

        def hms_to_seconds(value: str) -> int:
            hours, minutes, seconds = map(int, value.split(":"))
            return hours * 3600 + minutes * 60 + seconds

        def update_var_if_changed(old_value: Any, new_value: Any) -> Any:
            """Update a variable if the new value is different."""
            nonlocal need_update
            if isinstance(old_value, dict) and isinstance(new_value, dict):
                if old_value != new_value:
                    _LOGGER.debug(
                        f"dict - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
                    )
                    need_update = True
                    return new_value.copy()
                return old_value
            if isinstance(old_value, list) and isinstance(new_value, list):
                if old_value != new_value:
                    _LOGGER.debug(
                        f"list - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
                    )
                    need_update = True
                    return new_value.copy()
                return old_value
            if old_value != new_value:
                _LOGGER.debug(f"simple - Old_value: {old_value} New_value: {new_value}")  # noqa: G004
                need_update = True
                return new_value
            return old_value

        if "pause" in data:
            self.schedule_pause = data.get("pause")
        if "deviceSchedules" in data["data"]:
            ctime = data.get("data").get("deviceSchedules")
            if ctime:
                for day in self.days:
                    day.enabled = False
                oldday = -1
                index = 1
                for day in ctime:
                    day_of_week = day.get("dayOfWeek")
                    if oldday == day_of_week:
                        index = index + 1
                    else:
                        index = 1
                    oldday = day_of_week

                    dayobj = self.GetDay(day_of_week, index)
                    if dayobj:
                        dayobj.enabled = True
                        dayobj.need_fllow_boader = update_var_if_changed(
                            dayobj.need_fllow_boader,
                            day.get(
                                "trimFlag",
                                dayobj.need_fllow_boader,
                            ),
                        )
                        start = hms_to_seconds(day.get("startAt"))
                        dayobj.start = update_var_if_changed(
                            dayobj.start,
                            start,
                        )
                        end = hms_to_seconds(day.get("endAt"))
                        dayobj.end = update_var_if_changed(
                            dayobj.end,
                            end,
                        )

    def Get_schedule_data_V1(self):
        """Get schedule data for V1."""
        # self.url + self.cmdurl + f"device-schedule/{deviceId}"
        endpoint = (
            f"/app_wirelessv1_mower/wirelessv1/device-schedule/{self.mower.deviceId}"
        )
        try:
            url_ = self.mower.url + endpoint
            headers_ = {
                "Content-Type": "application/json",
                "Accept-Language": self.mower.language,
                "Authorization": "bearer " + self.mower.access_token,
                "Host": self.mower.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get schedule data header: {headers_} url: {url_}")  # noqa: G004
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            self.parse_schedule_data_V1(response_data)
            logdata = json.dumps(response_data)
            _LOGGER.debug(f"Get device schedule {logdata}")  # noqa: G004

            if response_data["code"] != 0:
                _LOGGER.debug("Error getting device schedule")
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get device schedule: failed {error}")  # noqa: G004


class SunseekerScheduleDay:
    """Day."""

    def __init__(self, day: int) -> None:
        """Init."""
        self.mqtt_day = {}
        self.day = day
        self.start: str = "00:00"
        self.end: str = "00:00"
        self.trim: bool = False

    def Update(self) -> None:
        """Update from settings."""

    def IsEmpty(self) -> bool:
        """Check if day is empty."""
        if self.start == "00:00" and self.end == "00:00":
            return True
        return False


class SunseekerSchedule:
    """Sunseeker schedule."""

    SavedData: None

    def __init__(self) -> None:
        """Init."""
        self.days = []
        for x in range(1, 8):
            self.days.append(SunseekerScheduleDay(x))

    def IsEmpty(self) -> bool:
        """Check if week is empty."""
        if (
            self.GetDay(1).IsEmpty()
            and self.GetDay(2).IsEmpty()
            and self.GetDay(3).IsEmpty()
            and self.GetDay(4).IsEmpty()
            and self.GetDay(5).IsEmpty()
            and self.GetDay(6).IsEmpty()
            and self.GetDay(7).IsEmpty()
        ):
            return True
        return False

    def GetDay(self, daynumber: int) -> SunseekerScheduleDay:
        """Get the day."""
        for day in self.days:
            if day.day == daynumber:
                return day
        return None

    def UpdateFromMqtt(self, data, daynumber: int) -> None:
        """From mqtt."""
        self.GetDay(daynumber).mqtt_day = data
        asc: SunseekerScheduleDay = self.GetDay(daynumber)
        if len(data) > 0:
            Start = None
            End = None
            Trimming = None
            for key, value in data.items():
                if key == "slice":
                    for a in value[0].items():
                        if a[0] == "start":
                            Start = a[1]
                        if a[0] == "end":
                            End = a[1]
                if key == "Trimming":
                    Trimming = value
            if Start is not None:
                asc.start = time.strftime("%H:%M", time.gmtime(int(Start) * 60))[0:5]
            if End is not None:
                if int(End) == 1440:
                    asc.end = "24:00"
                else:
                    asc.end = time.strftime("%H:%M", time.gmtime(int(End) * 60))[0:5]
            if Trimming is not None:
                asc.trim = Trimming
