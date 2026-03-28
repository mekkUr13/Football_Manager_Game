from dataclasses import dataclass
from server.database.models import TournamentClub, Tournament, ClubTactics, ClubTraining, TournamentPlayer


@dataclass
class MatchSimulationData:
    """
    Data container for simulating a single match.

    This object is returned by DataManager and contains all
    necessary information to simulate a match, detached from the database.
    """
    match_id: int

    home_club: TournamentClub
    away_club: TournamentClub
    tournament: Tournament
    round_number: int

    home_tactics: ClubTactics
    away_tactics: ClubTactics

    home_training: ClubTraining
    away_training: ClubTraining

    all_players: list[TournamentPlayer]

@dataclass
class ClubSimulationStats:
    base_team_strength: float
    base_atk_strength: float
    base_mid_strength: float
    base_def_strength: float
    fitness_level: float
    form: float
    correct_primary_positions: int
    correct_secondary_positions: int
    overall_team_strength: float