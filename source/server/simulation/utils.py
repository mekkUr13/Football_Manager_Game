from common.enums import MatchEventTypeEnum
import random
from typing import List

def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0

def choose_event_type() -> MatchEventTypeEnum:
    """
    Randomly selects a top-level simulation event (CHANCE, INJURY, FOUL, THROW_IN).

    Returns:
        MatchEventTypeEnum: The selected primary event type.
    """
    pool = [
        (MatchEventTypeEnum.CHANCE, 0.60),
        (MatchEventTypeEnum.INJURY, 0.05),
        (MatchEventTypeEnum.FOUL, 0.25),
        (MatchEventTypeEnum.THROW_IN, 0.10),
    ]
    r = random.random()
    cumulative = 0
    for event, weight in pool:
        cumulative += weight
        if r < cumulative:
            return event
    return MatchEventTypeEnum.CHANCE

def get_weighted_injury_duration() -> int:
    # Favor short injuries; weights sum to 100%
    weights = [0.25, 0.2, 0.15, 0.1, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.01]
    return random.choices(range(1, 13), weights=weights, k=1)[0]
