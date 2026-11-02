from enum import Enum

class CFGType(Enum):
    CLASSIC = "classic"
    GATEWAY = "gateway"
    TEMPORAL = "temporal"

class CFGNodeType(Enum):
    """
    A code for the node type in the control flow graph.
    """
    ACTION = "ActionNode"
    GATEWAY = "GatewayNode"
    EVENT = "EventNode"
    TIMER_EVENT = "TimerEventNode"
    BLOCK = "BlockNode"
    FAKE = "FakeNode"

class CFGGatewayClass(Enum):
    PARALLEL = "parallel"
    EXCLUSIVE = "exclusive"

class CFGGatewayDirection(Enum):
    DIVERGENT = "divergent"
    CONVERGENT = "convergent"

class CFGEventType(Enum):
    START = "start"
    INTERMEDIATE = "intermediate"
    END = "end"
    BOUNDARY = "boundary"

class TemporalCategory(Enum):
    """
    A code for the temporal category.
    """
    STANDARD_CYCLE = "standard_cycle"
    INSTANCE_CYCLE = "instance_cycle"
    EXECUTION_DURATION = "execution_duration"
    EXECUTION_ITERATION = "execution_iteration"
    EXECUTION_BOUND = "execution_bound"
    KEEP_ALIVE_BOUND = "keep_alive_bound"
    EXACT = "exact"
    OFFSET = "offset"

class FHIRRelationshipType(str, Enum):
    """
    A code for the relationship type from FHIR Relationship Type value set.
    """
    AFTER_END = "after-end"
    BEFORE_END = "before-end"
    AFTER_START = "after-start"

class UCUMUnitOfTime(Enum):
    """
    Unit of time in UCUM.
    """
    S = "s"
    MIN = "min"
    H = "h"
    D = "d"
    WK = "wk"
    MO = "mo"
    A = "a"

class DayOfWeek(Enum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"

class EventTimingValueSet(Enum):
    """
    A code for the event timing from FHIR Event Timing value set (https://hl7.org/fhir/R5/valueset-event-timing.html).
    """

    MORN = "MORN"
    """Event occurs during the morning. The exact time is unspecified and established by institution convention or patient interpretation."""

    MORN_EARLY = "MORN.early"
    """Event occurs during the early morning. The exact time is unspecified and established by institution convention or patient interpretation."""

    MORN_LATE = "MORN.late"
    """Event occurs during the late morning. The exact time is unspecified and established by institution convention or patient interpretation."""

    NOON = "NOON"
    """Event occurs around 12:00pm. The exact time is unspecified and established by institution convention or patient interpretation."""

    AFT = "AFT"
    """Event occurs during the afternoon. The exact time is unspecified and established by institution convention or patient interpretation."""

    AFT_EARLY = "AFT.early"
    """Event occurs during the early afternoon. The exact time is unspecified and established by institution convention or patient interpretation."""

    AFT_LATE = "AFT.late"
    """Event occurs during the late afternoon. The exact time is unspecified and established by institution convention or patient interpretation."""

    EVE = "EVE"
    """Event occurs during the evening. The exact time is unspecified and established by institution convention or patient interpretation."""

    EVE_EARLY = "EVE.early"
    """Event occurs during the early evening. The exact time is unspecified and established by institution convention or patient interpretation."""

    EVE_LATE = "EVE.late"
    """Event occurs during the late evening. The exact time is unspecified and established by institution convention or patient interpretation."""

    NIGHT = "NIGHT"
    """Event occurs during the night. The exact time is unspecified and established by institution convention or patient interpretation."""

    PHS = "PHS"
    """Event occurs [offset] after subject goes to sleep. The exact time is unspecified and established by institution convention or patient interpretation."""

    IMD = "IMD"
    """Event occurs a single time (with no repetitions) as soon as possible after the scheduled or actual start of the overall event."""

    HS = "HS"
    """Prior to beginning a regular period of extended sleep (this would exclude naps). Note that this might occur at different times of day depending on a person's regular sleep schedule."""

    WAKE = "WAKE"
    """Upon waking up from a regular period of sleep, in order to start regular activities (this would exclude waking up from a nap or temporarily waking up during a period of sleep). Usage notes: Take pulse rate on waking in management of thyrotoxicosis; take BP on waking in management of hypertension; take basal body temperature on waking in establishing date of ovulation."""

    C = "C"
    """Meal (from lat. ante cibus)."""

    CM = "CM"
    """Breakfast (from lat. cibus matutinus)."""

    CD = "CD"
    """Lunch (from lat. cibus diurnus)."""

    CV = "CV"
    """Dinner (from lat. cibus vespertinus)."""

    AC = "AC"
    """Before meal (from lat. ante cibus)."""

    ACM = "ACM"
    """Before breakfast (from lat. ante cibus matutinus)."""

    ACD = "ACD"
    """Before lunch (from lat. ante cibus diurnus)."""

    ACV = "ACV"
    """Before dinner (from lat. ante cibus vespertinus)."""

    PC = "PC"
    """After meal (from lat. post cibus)."""

    PCM = "PCM"
    """After breakfast (from lat. post cibus matutinus)."""

    PCD = "PCD"
    """After lunch (from lat. post cibus diurnus)."""

    PCV = "PCV"
    """After dinner (from lat. post cibus vespertinus)."""


class TimingAbbreviationValueSet(Enum):
    """
    A code for the timing schedule from FHIR Timing Abbreviation value set (https://hl7.org/fhir/R5/valueset-timing-abbreviation.html).
    """

    C = "C"
    """Service is provided continuously between start time and stop time."""

    BID = "BID"
    """Two times a day at institution specified time."""

    TID = "TID"
    """Three times a day at institution specified time."""

    QID = "QID"
    """Four times a day at institution specified time."""

    AM = "AM"
    """Every morning at institution specified times."""

    PM = "PM"
    """Every afternoon at institution specified times."""

    QD = "QD"
    """Every day at institution specified times."""

    QOD = "QOD"
    """Every other day at institution specified times."""

    Q1H = "Q1H"
    """Every hour at institution specified times."""

    Q2H = "Q2H"
    """Every 2 hours at institution specified times."""

    Q3H = "Q3H"
    """Every 3 hours at institution specified times."""

    Q4H = "Q4H"
    """Every 4 hours at institution specified time."""

    Q6H = "Q6H"
    """Every 6 hours at institution specified time."""

    Q8H = "Q8H"
    """Every 8 hours at institution specified times."""

    BED = "BED"
    """At bedtime (institution specified time)."""

    WK = "WK"
    """Weekly at institution specified time."""

    MO = "MO"
    """Monthly at institution specified time."""

class BPMNEngines(Enum):
    CAMUNDA = "camunda"
    FLOWABLE = "flowable"
    SPIFF_ARENA = "spiff_arena"
