"""Resolve FHIR event-time conventions into exact, six-field UTC cron schedules."""
from datetime import time
from itertools import product
from typing import List, Set, Tuple

from src.domain.enums import EventTimingValueSet as When, UCUMUnitOfTime
from src.domain.temporal_constraint import InstanceCycleTemporalConstraint
from src.utils.settings import TemporalSettings


class TemporalScheduleMapper:
    @staticmethod
    def is_immediate(constraint: InstanceCycleTemporalConstraint) -> bool:
        """Identify the non-recurring immediate event code.

        :param constraint: Calendar/event temporal metadata.
        :type constraint: InstanceCycleTemporalConstraint
        :return: Whether the sole event code is IMD.
        :rtype: bool
        """
        return constraint.when == [When.IMD]

    @staticmethod
    def _clock_points(constraint: InstanceCycleTemporalConstraint, policy: TemporalSettings) -> List[Tuple[time, int]]:
        """Resolve clocks and signed minute offsets without changing source metadata.

        :param constraint: Calendar/event temporal metadata.
        :type constraint: InstanceCycleTemporalConstraint
        :param policy: Configured UTC clock conventions.
        :type policy: TemporalSettings
        :return: Clock and minute-shift pairs; shifts may cross midnight.
        :rtype: List[Tuple[datetime.time, int]]
        """
        if constraint.time_of_day:
            return [(clock, 0) for clock in constraint.time_of_day]
        anchors = {
            When.AC: When.C, When.ACM: When.CM, When.ACD: When.CD, When.ACV: When.CV,
            When.PC: When.C, When.PCM: When.CM, When.PCD: When.CD, When.PCV: When.CV,
        }
        before = {When.AC, When.ACM, When.ACD, When.ACV, When.HS}
        points: List[Tuple[time, int]] = []
        for code in constraint.when or [When.MORN]:
            if constraint.offset is None:
                points.extend((clock, 0) for clock in policy.when_times[code])
                continue
            if code in anchors:
                clocks = policy.when_times[anchors[code]]
            elif code in {When.HS, When.PHS}:
                clocks = [policy.sleep_time]
            else:
                clocks = policy.when_times[code]
            delta = (-1 if code in before else 1) * constraint.offset
            points.extend((clock, delta) for clock in clocks)
        return points

    @classmethod
    def to_cron(cls, constraint: InstanceCycleTemporalConstraint, policy: TemporalSettings) -> str:
        """Compile a calendar schedule without inventing extra clock/day combinations.

        :param constraint: Event-time, explicit clock and weekday constraints.
        :type constraint: InstanceCycleTemporalConstraint
        :param policy: Configured event clocks, interpreted in UTC.
        :type policy: TemporalSettings
        :return: Six-field cron expression suitable for a timeCycle definition.
        :rtype: str
        :raises ValueError: If one cron cannot faithfully encode the supplied schedule.
        """
        if cls.is_immediate(constraint):
            raise ValueError('IMD is a one-shot activation, not a recurring cron schedule')
        if constraint.code is not None:
            raise ValueError('Timing.code abbreviations are not supported for automatic scheduling')
        if constraint.count is not None or any(v is not None for v in (
                constraint.period_max, constraint.frequency_max, constraint.count_max)):
            raise ValueError('Finite calendar counts and ranges are not supported')
        if constraint.period is not None and (
                constraint.period != 1 or constraint.period_unit not in {UCUMUnitOfTime.D, UCUMUnitOfTime.WK}):
            raise ValueError('Calendar intervals other than one day/week are not supported')
        points = cls._clock_points(constraint, policy)
        if not points:
            raise ValueError('The schedule contains no clock times')
        weekdays = ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')
        days = {weekdays.index(day.value.upper()) for day in constraint.day_of_week}
        weekly = constraint.period_unit == UCUMUnitOfTime.WK
        if not days:
            days = {0} if weekly else set(range(7))
        normalized: Set[Tuple[int, int]] = set()
        for clock, delta in points:
            if clock.tzinfo is not None or clock.microsecond:
                raise ValueError('Cron clocks require whole seconds in UTC')
            day_shift, seconds = divmod(clock.hour * 3600 + clock.minute * 60 + clock.second + delta * 60, 86400)
            normalized.add((seconds, day_shift))
        if constraint.frequency is not None:
            expected = len(normalized) * (len(days) if weekly else 1)
            if constraint.frequency != expected:
                raise ValueError('Clock occurrences do not match frequency; adjust the clock policy')
        schedule = {
            (seconds % 60, seconds // 60 % 60, seconds // 3600, (day + shift) % 7)
            for seconds, shift in normalized for day in days
        }
        fields = [sorted({point[index] for point in schedule}) for index in range(4)]
        if set(product(*fields)) != schedule:
            raise ValueError('These clock/day combinations cannot be represented by a single cron schedule')
        second, minute, hour, selected_days = fields
        day_field = '*' if len(selected_days) == 7 else ','.join(weekdays[d] for d in selected_days)
        return f"{','.join(map(str, second))} {','.join(map(str, minute))} {','.join(map(str, hour))} * * {day_field}"
