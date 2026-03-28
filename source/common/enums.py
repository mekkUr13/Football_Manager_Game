from enum import Enum

class TransferStatus(str,Enum):
    """Defines the status of a player on the transfer list."""
    LISTED = "listed"
    OFFER_RECEIVED = "offer_received"
    SOLD = "sold"

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

class FormationEnum(str,Enum):
    """Defines standard formations used by clubs and lineups."""
    FOUR_THREE_THREE = "4-3-3"
    FOUR_FOUR_TWO = "4-4-2"
    THREE_FOUR_THREE = "3-4-3"
    FIVE_TWO_ONE_TWO = "5-2-1-2"

class PlayStyleEnum(str,Enum):
    """Defines tactical play styles for clubs."""
    DEFENSIVE = "defensive"
    BALANCED = "balanced"
    ATTACKING = "attacking"
    HIGH_PRESS = "high_press"
    COUNTER_ATTACK = "counter_attack"
    POSSESSION = "possession"
    WIDE = "wide"
    NARROW = "narrow"

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

class TrainingFocusEnum(str,Enum):
    """Defines focus areas for club training plans."""
    BALANCED = "balanced"
    ATTACK = "attack"
    DEFENSE = "defense"
    STAMINA = "stamina"
    TACTICAL = "tactical"
    TECHNICAL = "technical"
    MENTALITY = "mentality"
    PHYSICAL = "physical"

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

class MatchEventTypeEnum(str,Enum):
    """Defines various match events that can occur during a game."""
    GOAL = "GOAL"
    ASSIST = "ASSIST"
    YELLOW_CARD = "YELLOW_CARD"
    RED_CARD = "RED_CARD"
    SUBSTITUTION = "SUBSTITUTION"
    INJURY = "INJURY"
    CHANCE = "CHANCE"
    SAVE = "SAVE"
    PENALTY_MISSED = "PENALTY_MISSED"
    PENALTY = "PENALTY"
    FREE_KICK = "FREE_KICK"
    CORNER_KICK = "CORNER_KICK"
    OFFSIDE = "OFFSIDE"
    FOUL = "FOUL"
    KICKOFF = "KICKOFF"
    THROW_IN = "THROW_IN"
    GOAL_KICK = "GOAL_KICK"
    HALFTIME = "HALFTIME"
    FULLTIME = "FULLTIME"
    OWN_GOAL = "OWN_GOAL"
    REBOUND = "REBOUND"
    MISTAKE = "MISTAKE"
    MOTM = "MOTM"

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()