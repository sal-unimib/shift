from typing import Self
from abc import ABC, abstractmethod
from fhir.resources import timing
import math
from src.domain.enums import DayOfWeek
from src.domain.enums import EventTimingValueSet
from src.domain.enums import TemporalCategory
from src.domain.enums import TimingAbbreviationValueSet
from src.domain.enums import UCUMUnitOfTime
from datetime import datetime, time
from fhir.resources.duration import Duration
from fhir.resources.timing import Timing
from typing import Any, Dict, List, Optional, Tuple, Union
import re


def _time_of_day(value: Union[str, time]) -> time:
    """
    Normalize a FHIR time without discarding seconds or fractional seconds.

    :param value: ISO time string or an already parsed time object.
    :type value: Union[str, datetime.time]
    :return: Time without timezone information, as required by FHIR time.
    :rtype: datetime.time
    """
    result = value if isinstance(value, time) else time.fromisoformat(value)
    if result.tzinfo is not None:
        raise ValueError("FHIR timeOfDay must not include a timezone.")
    return result


def _date_time(value: Union[str, datetime]) -> datetime:
    """
    Normalize an exact time or schedule bound without assuming a timezone.

    :param value: Aware datetime or full ISO timestamp with seconds and timezone.
    :type value: Union[str, datetime.datetime]
    :return: Datetime preserving its timezone offset and fractional seconds.
    :rtype: datetime.datetime
    """
    if isinstance(value, str):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
            raise ValueError("SHIFT requires a full timestamp with seconds and timezone.")
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("SHIFT requires an exact datetime with an explicit timezone.")
    return value


def _duration_unit(value: Duration) -> UCUMUnitOfTime:
    """
    Read a Duration's UCUM code, falling back only to a supported unit symbol.

    :param value: Duration carrying a UCUM code and an optional display unit.
    :type value: fhir.resources.duration.Duration
    :return: Supported time unit; the human-readable unit never overrides code.
    :rtype: UCUMUnitOfTime
    """
    if value.system not in (None, "http://unitsofmeasure.org"):
        raise ValueError("Only UCUM time units are supported.")
    if value.value is None or not math.isfinite(float(value.value)) or value.value < 0:
        raise ValueError("A duration requires a non-negative finite value.")
    if value.comparator is not None:
        raise ValueError("Duration comparators require an explicit resolution before transformation.")
    return UCUMUnitOfTime(value.code if value.code is not None else value.unit)


def _timing_code(value: Timing) -> Optional[TimingAbbreviationValueSet]:
    """
    Select the supported abbreviation from equivalent Timing.code codings.

    :param value: FHIR Timing resource containing optional code translations.
    :type value: fhir.resources.timing.Timing
    :return: Unique supported abbreviation, or None for an absent/text-only code.
    :rtype: Optional[TimingAbbreviationValueSet]
    """
    codings = value.code.coding if value.code else None
    if not codings:
        return None
    known = {c.code for c in codings if c.code in {item.value for item in TimingAbbreviationValueSet}}
    if len(known) != 1:
        raise ValueError("Timing.code must resolve to one supported SHIFT timing abbreviation.")
    return TimingAbbreviationValueSet(known.pop())

class UCUMConverter:

    @staticmethod
    def to_seconds(value: float, unit: UCUMUnitOfTime) -> float:
        """
        Convert a supported UCUM time quantity to seconds.

        :param value: Numeric quantity to convert.
        :type value: float
        :param unit: Supported UCUM time unit.
        :type unit: UCUMUnitOfTime
        :return: Seconds; months and years retain SHIFT's 30/365-day approximation.
        :rtype: float
        """
        factors = {UCUMUnitOfTime.S: 1, UCUMUnitOfTime.MIN: 60, UCUMUnitOfTime.H: 3600,
                   UCUMUnitOfTime.D: 86400, UCUMUnitOfTime.WK: 604800,
                   UCUMUnitOfTime.MO: 2592000, UCUMUnitOfTime.A: 31536000}
        return float(value) * factors[UCUMUnitOfTime(unit)]
    
    @classmethod
    def get_cycle_iteration_duration_in_seconds(cls, frequency : int, period : float, period_unit : UCUMUnitOfTime) -> int:
        return math.ceil(cls.to_seconds(period, period_unit) / frequency)

class FHIRTemporalConstraint:
    """
    Represents the temporal constraints associated with a clinical
    pathway action.

    A single action may be associated with multiple temporal categories.
    """

    label : str
    """Label for the temporal constraint."""

    # STANDARD CYCLE
    period : Optional[float]
    """Period of the execution."""
    period_max : Optional[float]
    """Maximum period of the execution."""
    period_unit : Optional[UCUMUnitOfTime]
    """Unit of the period."""
    frequency : Optional[int]
    """Frequency of the execution."""
    frequency_max : Optional[int]
    """Maximum frequency of the execution."""
    #EXECUTION ITERATION (if without period and frequency).
    count : Optional[int]
    """Count of the execution"""
    count_max : Optional[int]
    """Maximum count of the execution."""

    # INSTANCE CYCLE
    day_of_week : List[DayOfWeek]
    """Day of the week of the execution."""
    time_of_day : List[time]
    """Time of the day of the execution."""
    when : List[EventTimingValueSet]
    """When of the execution."""
    offset : Optional[int]
    """Offset of the execution."""
    code : Optional[TimingAbbreviationValueSet]
    """Code of the execution."""
    
    # EXECUTION DURATION
    duration : Optional[float]
    """Duration of the execution."""
    duration_unit : Optional[UCUMUnitOfTime]
    """Unit of the duration."""

    # EXECUTION BOUND
    duration_max : Optional[float]
    """Maximum duration of the execution."""

    # KEEP ALIVE BOUND
    bounds_duration : Optional[float]
    """Duration limit of the execution."""
    bounds_duration_unit : Optional[UCUMUnitOfTime]
    """Unit of the duration limit of the execution."""
    bounds_period_start : Optional[datetime]
    """Start date of the period limit of the execution."""
    bounds_period_end : Optional[datetime]
    """End date of the period limit of the execution."""

    # EXACT
    event : Optional[datetime]
    """Exact time of the execution."""

    # OFFSET
    offset_duration : Optional[float]
    """Time to wait before starting the execution."""
    offset_duration_unit : Optional[UCUMUnitOfTime]
    """Unit of the time to wait before starting the execution."""

    def __init__(self):
        self.label = ""
        self.day_of_week = []
        self.time_of_day = []
        self.when = []
        self.offset = None
        self.period = None
        self.period_max = None
        self.period_unit = None
        self.frequency = None
        self.frequency_max = None
        self.count = None
        self.count_max = None
        self.code = None
        self.duration = None
        self.duration_unit = None
        self.duration_max = None
        self.bounds_duration = None
        self.bounds_duration_unit = None
        self.bounds_period_start = None
        self.bounds_period_end = None
        self.event = None
        self.offset_duration = None
        self.offset_duration_unit = None

    def get_categories(self) -> List[TemporalCategory]:
        """
        Return the list of temporal categories associated with the temporal constraint.

        Temporal categories are defined as follows:
        - STANDARD_CYCLE: the action has a period or frequency.
        - INSTANCE_CYCLE: the action has a day of week, time of day, when, offset, or code.
        - EXECUTION_DURATION: the action has a duration.
        - EXECUTION_ITERATION: count repeats the action only when no scheduled cycle exists.
        - EXECUTION_BOUND: the action has a maximum duration.
        - KEEP_ALIVE_BOUND: bounds duration or bounds period, even without a cycle.
        - EXACT: the action has an exact event.
        - OFFSET: the action has an offset duration.

        :return: List of temporal categories.
        :rtype: List[TemporalCategory]
        """
        categories = []
        if self.period or self.frequency:
            categories.append(TemporalCategory.STANDARD_CYCLE)

        if len(self.day_of_week) > 0 or len(self.time_of_day) > 0 or len(self.when) > 0 or self.code:
            categories.append(TemporalCategory.INSTANCE_CYCLE)

        # A count limits the scheduler when a cycle exists; otherwise it repeats the action.
        if self.count is not None and not any(category in categories for category in (
                TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE)):
            categories.append(TemporalCategory.EXECUTION_ITERATION)

        if self.duration is not None:
            categories.append(TemporalCategory.EXECUTION_DURATION)
        
        if self.duration_max is not None:
            categories.append(TemporalCategory.EXECUTION_BOUND)
        if self.bounds_duration is not None or self.bounds_period_start is not None or self.bounds_period_end is not None:
            categories.append(TemporalCategory.KEEP_ALIVE_BOUND)

        if self.event:
            categories.append(TemporalCategory.EXACT)
        
        if self.offset_duration is not None:
            categories.append(TemporalCategory.OFFSET)
        
        return categories
    
    def get_label_groups(self) -> List[Tuple[TemporalCategory, ...]]:
        """Return the semantic slots used by semicolon-separated Timing labels.

        Exact activation precedes duration, maximum duration, action iteration,
        cycle and Keep Alive. Equal duration bounds share a slot, as do interval
        and calendar metadata describing the same cycle. RelatedAction offsets
        do not consume a Timing label.

        :return: Ordered groups of present categories sharing one label.
        :rtype: List[Tuple[TemporalCategory, ...]]
        """
        categories = set(self.get_categories())
        groups: List[Tuple[TemporalCategory, ...]] = []
        order = (TemporalCategory.EXACT, TemporalCategory.EXECUTION_DURATION,
                 TemporalCategory.EXECUTION_BOUND, TemporalCategory.EXECUTION_ITERATION,
                 TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE,
                 TemporalCategory.KEEP_ALIVE_BOUND)
        for category in order:
            if category not in categories:
                continue
            if category == TemporalCategory.EXECUTION_BOUND and self.duration is not None and self.duration == self.duration_max:
                index = next(i for i, group in enumerate(groups) if TemporalCategory.EXECUTION_DURATION in group)
                groups[index] += (category,)
            elif category == TemporalCategory.INSTANCE_CYCLE and TemporalCategory.STANDARD_CYCLE in categories:
                index = next(i for i, group in enumerate(groups) if TemporalCategory.STANDARD_CYCLE in group)
                groups[index] += (category,)
            else:
                groups.append((category,))
        return groups

    def get_label(self, temporal_category: TemporalCategory) -> str:
        """Resolve one category's label from Timing.code.text in the documented order.

        Empty slots and missing trailing labels stay empty. Generated unbounded
        Keep Alive has no slot. Offset labels come from their separate duration.
        The original combined text remains unchanged in self.label and JSON.

        :param temporal_category: Category whose concrete label is requested.
        :type temporal_category: TemporalCategory
        :return: Trimmed label for that category, or an empty string.
        :rtype: str
        :raises ValueError: If more labels are supplied than present semantic slots.
        """
        category = TemporalCategory(temporal_category)
        groups = self.get_label_groups()
        if category == TemporalCategory.OFFSET:
            if self.offset_duration is None:
                return ""
            if not groups:
                return (self.label or "").strip()
            return f"{self.offset_duration:g} {self.offset_duration_unit.value}"
        index = next((i for i, group in enumerate(groups) if category in group), None)
        if index is None:
            return ""
        labels = [label.strip() for label in (self.label or "").split(";")]
        if len(labels) > len(groups):
            order = "; ".join("/".join(c.value for c in group) for group in groups)
            raise ValueError(f"Timing.code.text has {len(labels)} labels for {len(groups)} slots; expected order: {order}")
        return labels[index] if index < len(labels) else ""

    def is_executable(self) -> bool:
        """
        Check if the temporal constraint is executable, i.e., if it has an instance cycle.

        :return: True if the temporal constraint is executable, False otherwise.
        :rtype: bool
        """
        return TemporalCategory.INSTANCE_CYCLE in self.get_categories()
    
    def add_offset_duration(self, offset_duration: Duration):
        """
        Add an offset duration to the temporal constraint.

        :param offset_duration: Offset duration.
        :type offset_duration: Duration
        """
        FHIRTemporalConstraint.validate_fhir_duration_offset(offset_duration)
        self.offset_duration = offset_duration.value
        self.offset_duration_unit = _duration_unit(offset_duration)

    def get_cycle_iteration_duration_in_seconds(self, support_max : bool = True) -> Optional[int]:
        """
        Method to get the cycle iteration duration in seconds.
        It returns None value when The temporal constraint is not a standard cycle

        :param support_max: Whether to support max values for period and frequency.
        :type support_max: bool
        :return: Cycle iteration duration in seconds.
        :rtype: Optional[int]
        """
        if self.period is None or self.period_unit is None:
            return None
        period = self.period_max if support_max and self.period_max is not None else self.period
        frequency = self.frequency_max if support_max and self.frequency_max is not None else self.frequency
        if frequency is None:
            frequency = 1
        if frequency <= 0 or period <= 0:
            raise ValueError("A cycle requires a positive period and frequency.")
        return UCUMConverter.get_cycle_iteration_duration_in_seconds(frequency, period, self.period_unit)

    def get_execution_duration_in_seconds(self) -> Optional[int]:
        """
        Method to get the execution duration in seconds.

        :return: Execution duration in seconds.
        :rtype: Optional[int]
        """
        if self.duration is not None:
            return math.ceil(UCUMConverter.to_seconds(self.duration, self.duration_unit))
    
    def get_execution_bound_in_seconds(self) -> Optional[int]:
        """
        Method to get the execution bound in seconds.

        :return: Execution bound in seconds.
        :rtype: Optional[int]
        """
        if self.duration_max is not None:
            return math.ceil(UCUMConverter.to_seconds(self.duration_max, self.duration_unit))
    
    def get_bounds_duration_in_seconds(self) -> Optional[int]:
        """
        Method to get the bounds duration in seconds.
        If the result is None it could be:
        - No bounds_duration is defined
        - The bounds_period_end is undefined

        :return: Bounds duration in seconds.
        :rtype: Optional[int]
        """
        if self.bounds_duration is not None and self.bounds_duration_unit is not None:
            return math.ceil(UCUMConverter.to_seconds(self.bounds_duration, self.bounds_duration_unit))
        elif self.bounds_period_start and self.bounds_period_end:
            return math.ceil((self.bounds_period_end - self.bounds_period_start).total_seconds())

    def to_event_temporal_constraint(self, action_id: str, temporal_category : TemporalCategory) -> Optional["TemporalConstraint"]:
        """
        Convert source temporal metadata into a concrete constraint.

        A lifetime without recurrence also supports an unresolved STANDARD_CYCLE
        declaration; a recurrence without lifetime supports an empty KEEP_ALIVE_BOUND.

        :param action_id: FHIR action identifier associated with the constraint.
        :type action_id: str
        :param temporal_category: The temporal category of the event temporal constraint.
        :type temporal_category: TemporalCategory
        :return: Event temporal constraint.
        :rtype: Optional[TemporalConstraint]
        """
        temporal_category = TemporalCategory(temporal_category)
        categories = self.get_categories()
        if temporal_category == TemporalCategory.KEEP_ALIVE_BOUND and any(category in categories for category in (
                TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE)):
            return KeepAliveBoundTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        if (temporal_category == TemporalCategory.STANDARD_CYCLE
                and TemporalCategory.KEEP_ALIVE_BOUND in categories
                and not any(c in categories for c in (TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE))):
            # Action counts remain iteration metadata, not an invented recurrence.
            return StandardCycleTemporalConstraint(action_id, "", None, None, None)
        if temporal_category not in categories:
            return None

        if temporal_category == TemporalCategory.STANDARD_CYCLE:
            return StandardCycleTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.INSTANCE_CYCLE:
            return InstanceCycleTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.EXECUTION_DURATION:
            return ExecutionDurationTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.EXECUTION_BOUND:
            return ExecutionBoundTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.EXACT:
            return ExactTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.OFFSET:
            return OffsetTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.EXECUTION_ITERATION:
            return ExecutionIterationTemporalConstraint.from_fhir_temporal_constraint(action_id, self)
        elif temporal_category == TemporalCategory.KEEP_ALIVE_BOUND:
            return KeepAliveBoundTemporalConstraint.from_fhir_temporal_constraint(action_id, self)

    def to_json(self) -> Dict[str, Any]:
        """
        Convert FHIR temporal metadata to JSON without dropping zero values or exact events.

        :return: JSON object representing the TemporalConstraint.
        :rtype: Dict[str, Any]
        """
        return {
            "label": self.label,
            "period": float(self.period) if self.period is not None else None,
            "period_max": float(self.period_max) if self.period_max is not None else None,
            "period_unit": self.period_unit.value if self.period_unit else None,
            "frequency": self.frequency,
            "frequency_max": self.frequency_max,
            "count": self.count,
            "count_max": self.count_max,
            "day_of_week": [d.value for d in self.day_of_week],
            "time_of_day": [t.isoformat() for t in self.time_of_day],
            "when": [w.value for w in self.when],
            "offset": self.offset,
            "code": self.code.value if self.code else None,
            "duration": float(self.duration) if self.duration is not None else None,
            "duration_unit": self.duration_unit.value if self.duration_unit else None,
            "duration_max": float(self.duration_max) if self.duration_max is not None else None,
            "bounds_duration": float(self.bounds_duration) if self.bounds_duration is not None else None,
            "bounds_duration_unit": self.bounds_duration_unit.value if self.bounds_duration_unit else None,
            "bounds_period_start": self.bounds_period_start.isoformat() if self.bounds_period_start else None,
            "bounds_period_end": self.bounds_period_end.isoformat() if self.bounds_period_end else None,
            "event": self.event.isoformat() if self.event else None,
            "offset_duration": float(self.offset_duration) if self.offset_duration is not None else None,
            "offset_duration_unit": self.offset_duration_unit.value if self.offset_duration_unit else None,
        }
        
    @staticmethod
    def validate_fhir_timing(timing: Timing, throw_exception: bool = True) -> bool:
        """
        Validate supported FHIR Timing fields and their combinations.

        Preserves interval/calendar combinations. Rejects contradictory fields and
        forms the current scalar-event model cannot represent instead of dropping them.

        :param timing: Timing resource to validate, including empty optional fields.
        :type timing: fhir.resources.timing.Timing
        :param throw_exception: Raise ValueError on invalid input; otherwise return False.
        :type throw_exception: bool
        :return: Whether the Timing is supported and internally consistent.
        :rtype: bool
        """
        try:
            if timing is None:
                raise ValueError("A Timing resource is required.")
            events = timing.event or []
            repeat = timing.repeat
            code = _timing_code(timing)
            if len(events) > 1:
                raise ValueError("SHIFT supports one exact event per action.")
            if events and (repeat is not None or code is not None):
                raise ValueError("Exact events cannot be combined with a repeating schedule in SHIFT.")
            for event in events:
                _date_time(event)
            if repeat is None:
                return True
            times = [_time_of_day(t) for t in repeat.timeOfDay or []]
            when = [EventTimingValueSet(w) for w in repeat.when or []]
            if times and when:
                raise ValueError("timeOfDay and when cannot be combined.")
            if EventTimingValueSet.IMD in when and (
                    len(when) != 1 or times or repeat.dayOfWeek or code is not None
                    or repeat.period is not None or repeat.frequency is not None
                    or repeat.count not in (None, 1) or repeat.offset not in (None, 0)
                    or repeat.boundsDuration is not None or repeat.boundsPeriod is not None):
                raise ValueError("IMD must describe a single immediate activation without a recurring schedule.")
            for day in repeat.dayOfWeek or []:
                DayOfWeek(day)
            if repeat.offset is not None and (not when or any(w.value in ("C", "CM", "CD", "CV") for w in when)):
                raise ValueError("Timing.offset requires a compatible when event.")
            for low, high in (("period", "periodMax"), ("duration", "durationMax"),
                              ("frequency", "frequencyMax"), ("count", "countMax")):
                minimum, maximum = getattr(repeat, low), getattr(repeat, high)
                if minimum is not None and (not math.isfinite(float(minimum)) or minimum < 0):
                    raise ValueError(f"{low} must be non-negative and finite.")
                if maximum is not None and (minimum is None or maximum < minimum or not math.isfinite(float(maximum))):
                    raise ValueError(f"{high} requires {low} and cannot be smaller than it.")
            if repeat.period is not None:
                UCUMUnitOfTime(repeat.periodUnit)
                if repeat.period <= 0:
                    raise ValueError("A repeating interval must be strictly positive.")
            if repeat.duration is not None:
                UCUMUnitOfTime(repeat.durationUnit)
            if repeat.frequency is not None and repeat.frequency <= 0:
                raise ValueError("frequency must be positive.")
            if repeat.count is not None and repeat.count <= 0:
                raise ValueError("count must be positive.")
            calendar = bool(times or when or repeat.dayOfWeek or code)
            if repeat.frequency is not None and repeat.period is None and not calendar:
                raise ValueError("frequency requires an interval or a calendar schedule in SHIFT.")
            if repeat.boundsRange is not None:
                raise ValueError("boundsRange requires an explicit resolution before transformation.")
            if repeat.boundsDuration is not None:
                _duration_unit(repeat.boundsDuration)
            if repeat.boundsPeriod is not None:
                start = _date_time(repeat.boundsPeriod.start) if repeat.boundsPeriod.start is not None else None
                end = _date_time(repeat.boundsPeriod.end) if repeat.boundsPeriod.end is not None else None
                if start is not None and end is not None and start > end:
                    raise ValueError("A boundsPeriod cannot end before it starts.")
            return True
        except (ValueError, TypeError, AttributeError, OverflowError) as error:
            if throw_exception:
                raise ValueError(str(error)) from error
            return False
    
    @staticmethod
    def validate_fhir_duration_offset(duration_offset: Duration, throw_exception: bool = True) -> bool:
        """
        Validate a relative duration using its UCUM code rather than display text.

        :param duration_offset: Non-negative relative duration.
        :type duration_offset: fhir.resources.duration.Duration
        :param throw_exception: Raise on invalid input; otherwise return False.
        :type throw_exception: bool
        :return: Whether the duration is supported.
        :rtype: bool
        """
        try:
            _duration_unit(duration_offset)
            return True
        except (ValueError, TypeError, AttributeError, OverflowError) as error:
            if throw_exception:
                raise ValueError(str(error)) from error
            return False

    @staticmethod
    def from_fhir_constraints(timing: Optional[Timing] = None, offset_duration: Optional[Duration] = None) -> "FHIRTemporalConstraint":
        """
        Create a FHIRTemporalConstraint from FHIR constraints (FHIR Timing and Duration resources).

        :param timing: FHIR Timing resource.
        :type timing: Optional[Timing]
        :param offset_duration: FHIR Duration resource.
        :type offset_duration: Optional[Duration]
        :return: FHIRTemporalConstraint.
        :rtype: FHIRTemporalConstraint
        """
        if timing and offset_duration:
            tc = FHIRTemporalConstraint.from_fhir_timing(timing)
            tc.add_offset_duration(offset_duration)
        elif timing:
            tc = FHIRTemporalConstraint.from_fhir_timing(timing)
        elif offset_duration:
            tc = FHIRTemporalConstraint.from_fhir_offset_duration(offset_duration)
        else:
            # TODO Custom Exception
            raise ValueError("No timing or offset duration provided")
        return tc

    @staticmethod
    def from_fhir_timing(timing: Timing) -> "FHIRTemporalConstraint":
        """
        Extract supported Timing values without losing exact events or optional fields.

        :param timing: Valid FHIR Timing with interval, calendar, duration or exact data.
        :type timing: fhir.resources.timing.Timing
        :return: Temporal metadata preserving all supported combined constraints.
        :rtype: FHIRTemporalConstraint
        """
        FHIRTemporalConstraint.validate_fhir_timing(timing)
        tc = FHIRTemporalConstraint()
        repeat = timing.repeat
        if repeat is not None:
            for target, source in (("period", "period"), ("period_max", "periodMax"),
                                   ("frequency", "frequency"), ("frequency_max", "frequencyMax"),
                                   ("count", "count"), ("count_max", "countMax"),
                                   ("duration", "duration"), ("duration_max", "durationMax")):
                setattr(tc, target, getattr(repeat, source))
            tc.period_unit = UCUMUnitOfTime(repeat.periodUnit) if repeat.periodUnit else None
            if tc.period is not None and tc.frequency is None:
                tc.frequency = 1
            tc.duration_unit = UCUMUnitOfTime(repeat.durationUnit) if repeat.durationUnit else None
            tc.day_of_week = [DayOfWeek(day) for day in repeat.dayOfWeek or []]
            tc.time_of_day = [_time_of_day(t) for t in repeat.timeOfDay or []]
            tc.when = [EventTimingValueSet(w) for w in repeat.when or []]
            tc.offset = repeat.offset
            if repeat.boundsDuration is not None:
                tc.bounds_duration = repeat.boundsDuration.value
                tc.bounds_duration_unit = _duration_unit(repeat.boundsDuration)
            if repeat.boundsPeriod is not None:
                tc.bounds_period_start = _date_time(repeat.boundsPeriod.start) if repeat.boundsPeriod.start is not None else None
                tc.bounds_period_end = _date_time(repeat.boundsPeriod.end) if repeat.boundsPeriod.end is not None else None
        tc.event = _date_time(timing.event[0]) if timing.event else None
        tc.code = _timing_code(timing)
        tc.label = (timing.code.text or "") if timing.code else ""
        return tc
    
    @staticmethod
    def from_fhir_offset_duration(offset_duration: Duration) -> "FHIRTemporalConstraint":
        """
        Create a FHIRTemporalConstraint from a FHIR Duration resource.

        :param offset_duration: FHIR Duration resource.
        :type offset_duration: Duration
        :return: FHIRTemporalConstraint instance.
        :rtype: FHIRTemporalConstraint
        """
        FHIRTemporalConstraint.validate_fhir_duration_offset(offset_duration)
        tc = FHIRTemporalConstraint()
        tc.offset_duration = offset_duration.value
        tc.offset_duration_unit = _duration_unit(offset_duration)
        tc.label = f"{offset_duration.value} {offset_duration.unit or tc.offset_duration_unit.value}"

        return tc
        
    @staticmethod
    def from_json(json_payload: Dict[str, Any]) -> "FHIRTemporalConstraint":
        """
        Restore temporal metadata from JSON, including exact events and optional lists.

        :param json_payload: Serialized FHIR temporal metadata; omitted fields use defaults.
        :type json_payload: Dict[str, Any]
        :return: Independent temporal metadata object.
        :rtype: FHIRTemporalConstraint
        """
        tc = FHIRTemporalConstraint()
        tc.label = json_payload.get("label") or ""
        for field in ("period", "period_max", "frequency", "frequency_max", "count", "count_max",
                      "duration", "duration_max", "bounds_duration", "offset_duration"):
            setattr(tc, field, json_payload.get(field))
        for field in ("period_unit", "duration_unit", "bounds_duration_unit", "offset_duration_unit"):
            setattr(tc, field, UCUMUnitOfTime(json_payload[field]) if json_payload.get(field) else None)
        tc.day_of_week = [DayOfWeek(d) for d in json_payload.get("day_of_week") or []]
        tc.time_of_day = [_time_of_day(t) for t in json_payload.get("time_of_day") or []]
        tc.when = [EventTimingValueSet(w) for w in json_payload.get("when") or []]
        tc.offset = json_payload.get("offset")
        tc.code = TimingAbbreviationValueSet(json_payload["code"]) if json_payload.get("code") else None
        for field in ("bounds_period_start", "bounds_period_end", "event"):
            setattr(tc, field, _date_time(json_payload[field]) if json_payload.get(field) else None)
        return tc

class TemporalConstraint(ABC):
    action_id: str
    label : str
    temporal_category : TemporalCategory
    
    def __init__(self, action_id: str, label: str, temporal_category : TemporalCategory):
        self.action_id = action_id
        self.label = label
        self.temporal_category = temporal_category
    
    @classmethod
    @abstractmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> Self:
        pass
    
    @classmethod
    def from_json(cls, json: Dict[str, Any]) -> Self:
        """
        Dispatch a serialized temporal constraint to its concrete subclass.

        :param json: Constraint payload containing a supported temporal_category.
        :type json: Dict[str, Any]
        :return: Concrete constraint preserving the serialized temporal values.
        :rtype: TemporalConstraint
        :raises ValueError: If the temporal category is missing or unsupported.
        """
        if not isinstance(json, dict) or "temporal_category" not in json:
            raise ValueError("A temporal constraint requires a temporal_category.")
        category = TemporalCategory(json["temporal_category"])
        implementations = {
            TemporalCategory.STANDARD_CYCLE: StandardCycleTemporalConstraint,
            TemporalCategory.INSTANCE_CYCLE: InstanceCycleTemporalConstraint,
            TemporalCategory.EXECUTION_DURATION: ExecutionDurationTemporalConstraint,
            TemporalCategory.EXECUTION_BOUND: ExecutionBoundTemporalConstraint,
            TemporalCategory.EXACT: ExactTemporalConstraint,
            TemporalCategory.OFFSET: OffsetTemporalConstraint,
            TemporalCategory.EXECUTION_ITERATION: ExecutionIterationTemporalConstraint,
            TemporalCategory.KEEP_ALIVE_BOUND: KeepAliveBoundTemporalConstraint,
        }
        return implementations[category].from_json(json)

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        pass
    
class StandardCycleTemporalConstraint(TemporalConstraint):
    period : Optional[float]
    period_max : Optional[float]
    period_unit : Optional[UCUMUnitOfTime]
    frequency : Optional[int]
    frequency_max : Optional[int]
    count : Optional[int]
    count_max : Optional[int]

    def __init__(
        self,
        action_id: str,
        label : str,
        period : Optional[float],
        period_unit : Optional[UCUMUnitOfTime],
        frequency : Optional[int],
        period_max : Optional[float] = None,
        frequency_max : Optional[int] = None,
        count : Optional[int] = None,
        count_max : Optional[int] = None
    ):
        super().__init__(action_id, label, TemporalCategory.STANDARD_CYCLE)
        self.period = period
        self.period_unit = period_unit
        self.frequency = frequency
        self.period_max = period_max
        self.frequency_max = frequency_max
        self.count = count
        self.count_max = count_max
    
    @classmethod
    def from_fhir_temporal_constraint(cls, action_id : str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "StandardCycleTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: StandardCycleTemporalConstraint
        """
        return cls(
            action_id = action_id,
            label = fhir_temporal_constraint.get_label(TemporalCategory.STANDARD_CYCLE),
            period = fhir_temporal_constraint.period,
            period_unit = fhir_temporal_constraint.period_unit,
            frequency = fhir_temporal_constraint.frequency,
            period_max = fhir_temporal_constraint.period_max,
            frequency_max = fhir_temporal_constraint.frequency_max,
            count = fhir_temporal_constraint.count,
            count_max = fhir_temporal_constraint.count_max,
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "StandardCycleTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: StandardCycleTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            period = json["period"],
            period_unit = UCUMUnitOfTime(json["period_unit"]) if json.get("period_unit") is not None else None,
            frequency = json["frequency"],
            period_max = json.get("period_max"),
            frequency_max = json.get("frequency_max"),
            count = json.get("count"),
            count_max = json.get("count_max"),
        )
    
    def to_json(self) -> Dict[str, Any]:
        """
        Serialize temporal values, preserving zero quantities and optional fields.

        :return: Serialized temporal data.
        :rtype: Dict[str, Any]
        """
        return {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "period" : float(self.period) if self.period is not None else None,
            "period_max" : float(self.period_max) if self.period_max is not None else None,
            "period_unit" : self.period_unit.value if self.period_unit is not None else None,
            "frequency" : self.frequency,
            "frequency_max" : self.frequency_max,
            "count" : self.count,
            "count_max" : self.count_max,
        }
    
class InstanceCycleTemporalConstraint(TemporalConstraint):
    day_of_week : List[DayOfWeek]
    time_of_day : List[time]
    when : List[EventTimingValueSet]
    offset : Optional[int]
    code : Optional[TimingAbbreviationValueSet]

    def __init__(
        self,
        action_id: str,
        label: str,
        day_of_week : List[DayOfWeek], 
        time_of_day : List[time], 
        when : List[EventTimingValueSet],
        offset : Optional[int],
        code : Optional[TimingAbbreviationValueSet] = None,
        *, period: Optional[float] = None, period_unit: Optional[UCUMUnitOfTime] = None,
        frequency: Optional[int] = None, count: Optional[int] = None,
        period_max: Optional[float] = None, frequency_max: Optional[int] = None,
        count_max: Optional[int] = None
    ):
        """
        Initialize temporal/action metadata without dropping optional combined constraints.

        :param action_id: FHIR action identifier.
        :type action_id: str
        :param label: Human-readable temporal label.
        :type label: str
        :param day_of_week: Selected weekdays.
        :type day_of_week: List[DayOfWeek]
        :param time_of_day: Selected clock times, retaining seconds and fractional seconds.
        :type time_of_day: List[datetime.time]
        :param when: Selected event-timing codes.
        :type when: List[EventTimingValueSet]
        :param offset: Offset from the named event in minutes.
        :type offset: Optional[int]
        :param code: Optional timing abbreviation.
        :type code: Optional[TimingAbbreviationValueSet]
        :param period: Optional interval combined with the calendar schedule.
        :type period: Optional[float]
        :param period_unit: Unit of an optional interval combined with the calendar.
        :type period_unit: Optional[UCUMUnitOfTime]
        :param frequency: Optional executions per interval.
        :type frequency: Optional[int]
        :param count: Optional total number of scheduled occurrences.
        :type count: Optional[int]
        :param period_max: Optional upper interval bound.
        :type period_max: Optional[float]
        :param frequency_max: Optional maximum frequency.
        :type frequency_max: Optional[int]
        :param count_max: Optional maximum occurrence count.
        :type count_max: Optional[int]
        """
        super().__init__(action_id, label, TemporalCategory.INSTANCE_CYCLE)
        self.day_of_week = day_of_week
        self.time_of_day = time_of_day
        self.when = when
        self.offset = offset
        self.code = code
        self.period, self.period_unit, self.frequency = period, period_unit, frequency
        self.count, self.period_max = count, period_max
        self.frequency_max, self.count_max = frequency_max, count_max
    
    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "InstanceCycleTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: InstanceCycleTemporalConstraint
        """
        return cls(
            action_id = action_id,
            label = fhir_temporal_constraint.get_label(TemporalCategory.INSTANCE_CYCLE),
            day_of_week = fhir_temporal_constraint.day_of_week,
            time_of_day = fhir_temporal_constraint.time_of_day,
            when = fhir_temporal_constraint.when,
            offset = fhir_temporal_constraint.offset,
            code = fhir_temporal_constraint.code,
            period=fhir_temporal_constraint.period, period_unit=fhir_temporal_constraint.period_unit,
            frequency=fhir_temporal_constraint.frequency, count=fhir_temporal_constraint.count,
            period_max=fhir_temporal_constraint.period_max,
            frequency_max=fhir_temporal_constraint.frequency_max, count_max=fhir_temporal_constraint.count_max
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "InstanceCycleTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: InstanceCycleTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            day_of_week = [DayOfWeek(dow) for dow in json.get("day_of_week") or []],
            time_of_day = [_time_of_day(t) for t in json.get("time_of_day") or []],
            when = [EventTimingValueSet(w) for w in json.get("when") or []],
            offset = json.get("offset"),
            code = TimingAbbreviationValueSet(json["code"]) if json.get("code") else None,
            period=json.get("period"), period_unit=UCUMUnitOfTime(json["period_unit"]) if json.get("period_unit") else None,
            frequency=json.get("frequency"), count=json.get("count"), period_max=json.get("period_max"),
            frequency_max=json.get("frequency_max"), count_max=json.get("count_max"),
        )
    
    def to_json(self) -> Dict[str, Any]:
        """
        Serialize temporal values, preserving zero quantities and optional fields.

        :return: Serialized temporal data.
        :rtype: Dict[str, Any]
        """
        result = {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "day_of_week" : [dow.value for dow in self.day_of_week],
            "time_of_day" : [t.isoformat() for t in self.time_of_day],
            "when" : [w.value for w in self.when],
            "offset" : self.offset,
            "code" : self.code.value if self.code else None,
        }
        for field in ("period", "frequency", "count", "period_max", "frequency_max", "count_max"):
            value = getattr(self, field)
            if value is not None:
                result[field] = float(value) if field in ("period", "period_max") else value
        if self.period_unit is not None:
            result["period_unit"] = self.period_unit.value
        return result

class ExecutionDurationTemporalConstraint(TemporalConstraint):
    duration : float
    duration_unit : UCUMUnitOfTime

    def __init__(self, action_id: str, label: str, duration : float, duration_unit : UCUMUnitOfTime):
        super().__init__(action_id, label, TemporalCategory.EXECUTION_DURATION)
        self.duration = duration
        self.duration_unit = duration_unit

    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "ExecutionDurationTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: ExecutionDurationTemporalConstraint
        """
        return cls(
            action_id=action_id,
            label=fhir_temporal_constraint.get_label(TemporalCategory.EXECUTION_DURATION),
            duration=fhir_temporal_constraint.duration,
            duration_unit=fhir_temporal_constraint.duration_unit
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "ExecutionDurationTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: ExecutionDurationTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            duration = json["duration"],
            duration_unit = UCUMUnitOfTime(json["duration_unit"]),
        )
    
    def to_json(self) -> Dict[str, Any]:
        return {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "duration" : float(self.duration),
            "duration_unit" : self.duration_unit.value,
        }

class ExecutionBoundTemporalConstraint(TemporalConstraint):
    """Action execution limit, preserving both durations and absolute bounds."""

    def __init__(self, action_id: str, label: str, duration_max: Optional[float] = None,
                 duration_unit: Optional[UCUMUnitOfTime] = None, *,
                 bounds_duration: Optional[float] = None,
                 bounds_duration_unit: Optional[UCUMUnitOfTime] = None,
                 bounds_period_start: Optional[datetime] = None,
                 bounds_period_end: Optional[datetime] = None):
        """
        Initialize an execution limit without conflating task and schedule durations.

        :param action_id: FHIR action identifier.
        :type action_id: str
        :param label: Human-readable constraint label.
        :type label: str
        :param duration_max: Optional maximum duration of the action.
        :type duration_max: Optional[float]
        :param duration_unit: Unit of the maximum action duration.
        :type duration_unit: Optional[UCUMUnitOfTime]
        :param bounds_duration: Optional outer duration bound.
        :type bounds_duration: Optional[float]
        :param bounds_duration_unit: Unit of the outer duration bound.
        :type bounds_duration_unit: Optional[UCUMUnitOfTime]
        :param bounds_period_start: Optional beginning of the execution window.
        :type bounds_period_start: Optional[datetime.datetime]
        :param bounds_period_end: Optional end of the execution window.
        :type bounds_period_end: Optional[datetime.datetime]
        """
        super().__init__(action_id, label, TemporalCategory.EXECUTION_BOUND)
        self.duration_max, self.duration_unit = duration_max, duration_unit
        self.bounds_duration, self.bounds_duration_unit = bounds_duration, bounds_duration_unit
        self.bounds_period_start, self.bounds_period_end = bounds_period_start, bounds_period_end

    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint: FHIRTemporalConstraint) -> "ExecutionBoundTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: ExecutionBoundTemporalConstraint
        """
        tc = fhir_temporal_constraint
        return cls(action_id, tc.get_label(TemporalCategory.EXECUTION_BOUND), tc.duration_max, tc.duration_unit,
                   bounds_duration=tc.bounds_duration, bounds_duration_unit=tc.bounds_duration_unit,
                   bounds_period_start=tc.bounds_period_start, bounds_period_end=tc.bounds_period_end)

    @classmethod
    def from_json(cls, json: Dict[str, Any]) -> "ExecutionBoundTemporalConstraint":
        """
        Restore duration or absolute execution limits from serialized data.

        :param json: Serialized execution limit.
        :type json: Dict[str, Any]
        :return: Concrete execution limit.
        :rtype: ExecutionBoundTemporalConstraint
        """
        return cls(json["action_id"], json.get("label") or "", json.get("duration_max"),
                   UCUMUnitOfTime(json["duration_unit"]) if json.get("duration_unit") else None,
                   bounds_duration=json.get("bounds_duration"),
                   bounds_duration_unit=UCUMUnitOfTime(json["bounds_duration_unit"]) if json.get("bounds_duration_unit") else None,
                   bounds_period_start=_date_time(json["bounds_period_start"]) if json.get("bounds_period_start") else None,
                   bounds_period_end=_date_time(json["bounds_period_end"]) if json.get("bounds_period_end") else None)

    def to_json(self) -> Dict[str, Any]:
        """
        Serialize the execution limit without dropping zero values or timezone offsets.

        :return: JSON-compatible execution limit.
        :rtype: Dict[str, Any]
        """
        result = {"action_id": self.action_id, "temporal_category": self.temporal_category.value,
                  "label": self.label,
                  "duration_max": float(self.duration_max) if self.duration_max is not None else None,
                  "duration_unit": self.duration_unit.value if self.duration_unit is not None else None}
        if self.bounds_duration is not None:
            result["bounds_duration"] = float(self.bounds_duration)
        if self.bounds_duration_unit is not None:
            result["bounds_duration_unit"] = self.bounds_duration_unit.value
        for field in ("bounds_period_start", "bounds_period_end"):
            if getattr(self, field) is not None:
                result[field] = getattr(self, field).isoformat()
        return result

class ExactTemporalConstraint(TemporalConstraint):
    event : datetime

    def __init__(self, action_id: str, label : str, event : datetime):
        super().__init__(action_id, label, TemporalCategory.EXACT)
        self.event = event
    
    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "ExactTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: ExactTemporalConstraint
        """
        return cls(
            action_id = action_id,
            label = fhir_temporal_constraint.get_label(TemporalCategory.EXACT),
            event = fhir_temporal_constraint.event
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "ExactTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: ExactTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            event = _date_time(json["event"]),
        )
    
    def to_json(self) -> Dict[str, Any]:
        return {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "event" : self.event.isoformat(),
        }

class OffsetTemporalConstraint(TemporalConstraint):
    offset_duration : float
    offset_duration_unit : UCUMUnitOfTime
    
    def __init__(self, action_id: str, label: str, offset_duration : float, offset_duration_unit : UCUMUnitOfTime):
        super().__init__(action_id, label, TemporalCategory.OFFSET)
        self.offset_duration = offset_duration
        self.offset_duration_unit = offset_duration_unit
    
    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "OffsetTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: OffsetTemporalConstraint
        """
        return cls(
            action_id = action_id,
            label = fhir_temporal_constraint.get_label(TemporalCategory.OFFSET),
            offset_duration = fhir_temporal_constraint.offset_duration,
            offset_duration_unit = fhir_temporal_constraint.offset_duration_unit
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "OffsetTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: OffsetTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            offset_duration = json["offset_duration"],
            offset_duration_unit = UCUMUnitOfTime(json["offset_duration_unit"]),
        )
    
    def to_json(self) -> Dict[str, Any]:
        return {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "offset_duration" : float(self.offset_duration),
            "offset_duration_unit" : self.offset_duration_unit.value,
        }

class ExecutionIterationTemporalConstraint(TemporalConstraint):
    """
    Represents an execution iteration temporal constraint.
    Corresponds to FHIR PlanDefinition.action.timing.repeat.count, FHIR PlanDefinition.action.timing.repeat.countMax
    """

    count : int
    """Count."""
    count_max : Optional[int]
    """Count max."""

    def __init__(self, action_id: str, label: str, count : int, count_max : Optional[int]):
        super().__init__(action_id, label, TemporalCategory.EXECUTION_ITERATION)
        self.count = count
        self.count_max = count_max
    
    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "ExecutionIterationTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: ExecutionIterationTemporalConstraint
        """
        return cls(
            action_id = action_id,
            label = fhir_temporal_constraint.get_label(TemporalCategory.EXECUTION_ITERATION),
            count = fhir_temporal_constraint.count,
            count_max = fhir_temporal_constraint.count_max
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "ExecutionIterationTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: ExecutionIterationTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            count = json["count"],
            count_max = json.get("count_max"),
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "count" : self.count,
            "count_max" : self.count_max,
        }

class KeepAliveBoundTemporalConstraint(TemporalConstraint):
    """
    Represents a keep-alive bound temporal constraint.
    Corresponds to FHIR PlanDefinition.action.timing.repeat.boundsDuration, 
    FHIR PlanDefinition.action.timing.repeat.boundsPeriod
    """
    
    bounds_duration : Optional[float]
    """Duration bound."""
    bounds_duration_unit : Optional[UCUMUnitOfTime]
    """Duration unit."""
    bounds_period_start : Optional[datetime]
    """Period start."""
    bounds_period_end : Optional[datetime]
    """Period end."""

    def __init__(
        self,
        action_id: str,
        label: str,
        bounds_duration: Optional[float],
        bounds_duration_unit: Optional[UCUMUnitOfTime],
        bounds_period_start: Optional[datetime],
        bounds_period_end: Optional[datetime]
    ):
        super().__init__(action_id, label, TemporalCategory.KEEP_ALIVE_BOUND)
        self.bounds_duration = bounds_duration
        self.bounds_duration_unit = bounds_duration_unit
        self.bounds_period_start = bounds_period_start
        self.bounds_period_end = bounds_period_end
    
    @classmethod
    def from_fhir_temporal_constraint(cls, action_id: str, fhir_temporal_constraint : FHIRTemporalConstraint) -> "KeepAliveBoundTemporalConstraint":
        """Extract the concrete constraint with its category-specific Timing label.

        :param action_id: Owning FHIR action linkId.
        :type action_id: str
        :param fhir_temporal_constraint: Combined source temporal metadata.
        :type fhir_temporal_constraint: FHIRTemporalConstraint
        :return: Concrete constraint retaining its values and resolved label.
        :rtype: KeepAliveBoundTemporalConstraint
        """
        return cls(
            action_id=action_id,
            label=fhir_temporal_constraint.get_label(TemporalCategory.KEEP_ALIVE_BOUND),
            bounds_duration=fhir_temporal_constraint.bounds_duration,
            bounds_duration_unit=fhir_temporal_constraint.bounds_duration_unit,
            bounds_period_start=fhir_temporal_constraint.bounds_period_start,
            bounds_period_end=fhir_temporal_constraint.bounds_period_end
        )
    
    @classmethod
    def from_json(cls, json : Dict[str, Any]) -> "KeepAliveBoundTemporalConstraint":
        """
        Restore the concrete temporal constraint from serialized values.

        :param json: Serialized concrete temporal constraint.
        :type json: Dict[str, Any]
        :return: Concrete temporal constraint.
        :rtype: KeepAliveBoundTemporalConstraint
        """
        return cls(
            action_id = json["action_id"],
            label = json.get("label") or "",
            bounds_duration = json.get("bounds_duration"),
            bounds_duration_unit = UCUMUnitOfTime(json["bounds_duration_unit"]) if json.get("bounds_duration_unit") else None,
            bounds_period_start = _date_time(json["bounds_period_start"]) if json.get("bounds_period_start") else None,
            bounds_period_end = _date_time(json["bounds_period_end"]) if json.get("bounds_period_end") else None,
        )

    def to_json(self) -> Dict[str, Any]:
        """
        Serialize temporal values, preserving zero quantities and optional fields.

        :return: Serialized temporal data.
        :rtype: Dict[str, Any]
        """
        return {
            "action_id" : self.action_id,
            "temporal_category" : self.temporal_category.value,
            "label" : self.label,
            "bounds_duration" : float(self.bounds_duration) if self.bounds_duration is not None else None,
            "bounds_duration_unit" : self.bounds_duration_unit.value if self.bounds_duration_unit else None,
            "bounds_period_start" : self.bounds_period_start.isoformat() if self.bounds_period_start else None,
            "bounds_period_end" : self.bounds_period_end.isoformat() if self.bounds_period_end else None,
        }

