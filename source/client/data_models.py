from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

"""
Defines simple data classes used on the client-side to represent
data structures received from the server. These help in organizing
and accessing data within the client application code.
"""

@dataclass
class ClientPlayer:
    """Represents player data as needed by the client UI."""
    player_id: int
    club_id: int
    name: str
    position: str
    age: int
    overall_rating: int
    value: int
    status: str # Derived status like 'Fit', 'Inj (2r)', 'Sus (1r)'
    nation: Optional[str] = None
    pace: Optional[int] = None
    shooting: Optional[int] = None
    passing: Optional[int] = None
    dribbling: Optional[int] = None
    defense: Optional[int] = None
    physical: Optional[int] = None
    alternative_positions: str = ""
    # Status details used to derive the 'status' string
    is_injured: bool = False
    injury_rounds: int = 0
    is_suspended: bool = False
    suspended_rounds: int = 0
    has_yellow_card: bool = False

    # Factory method to create an instance from a dictionary
    @classmethod
    def from_dict(cls, data: dict, labels):
        """Creates a ClientPlayer instance from a dictionary, deriving the status."""
        status = cls._derive_status(data, labels)
        return cls(
            player_id=data.get('player_id', -1),
            club_id=data.get('club_id', -1),
            name=data.get('name', 'N/A'),
            position=data.get('position', 'N/A'),
            age=data.get('age', 0),
            overall_rating=data.get('overall_rating', 0),
            value=data.get('value', 0),
            status=status,
            nation=data.get('nation'),
            pace=data.get('pace'),
            shooting=data.get('shooting'),
            passing=data.get('passing'),
            dribbling=data.get('dribbling'),
            defense=data.get('defense'),
            physical=data.get('physical'),
            is_injured=data.get('is_injured', False),
            alternative_positions=data.get('alternative_positions', "-"),
            injury_rounds=data.get('injury_rounds', 0),
            is_suspended=data.get('is_suspended', False),
            suspended_rounds=data.get('suspended_rounds', 0),
            has_yellow_card=data.get('has_yellow_card', False)
        )

    @staticmethod
    def _derive_status(player_dict: dict, labels) -> str:
        """Helper to determine the display status text."""
        if player_dict.get('is_injured', False):
            rounds = player_dict.get('injury_rounds', 0)
            status_text = labels.get_text("INJURED", "Inj")
            return status_text + (f" ({rounds}r)" if rounds > 0 else "")
        elif player_dict.get('is_suspended', False):
            rounds = player_dict.get('suspended_rounds', 0)
            status_text = labels.get_text("SUSPENDED", "Sus")
            return status_text + (f" ({rounds}r)" if rounds > 0 else "")
        else:
            return labels.get_text("FIT", "Fit")


@dataclass
class ClientClubInfo:
    """Represents basic info about a user's club slot."""
    club_id: int
    club_name: Optional[str] # Name is None for empty slots
    tournament_id: int
    original_club_id: Optional[int]
    budget: int
    tournament_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            club_id=data.get('club_id', -1),
            club_name=data.get('club_name'), # Can be None
            tournament_id=data.get('tournament_id', -1),
            original_club_id=data.get('original_club_id'), # Can be None
            budget=data.get('budget', 0),
            tournament_name=data.get('tournament_name')
        )


@dataclass
class ClientLeague:
    """Represents info about an available league."""
    tournament_id: int
    name: str
    filled_slots: int
    number_of_clubs: int
    start_time_iso: str # Keep as string for display formatting later

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            tournament_id=data.get('tournament_id', -1),
            name=data.get('name', 'Unknown League'),
            filled_slots=data.get('filled_slots', 0),
            number_of_clubs=data.get('number_of_clubs', 0),
            start_time_iso=data.get('start_time', '') # Get the ISO string
        )

@dataclass
class ClientClubDetail:
    """Represents detailed info for club selection."""
    original_club_id: int
    club_name: str
    is_taken: bool
    taken_by: Optional[str] = None # Username or "AI"
    avg_ovr: Optional[float] = None
    total_value: Optional[int] = None
    player_count: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            original_club_id=data.get('original_club_id', -1),
            club_name=data.get('club_name', 'Unknown'),
            is_taken=data.get('is_taken', False),
            taken_by=data.get('taken_by'),
            avg_ovr=data.get('avg_ovr'),
            total_value=data.get('total_value'),
            player_count=data.get('player_count')
        )

@dataclass
class ClientLeagueDetail:
    """Represents full details of a league for ClubSelectScreen."""
    tournament_id: int
    name: str
    number_of_clubs: int
    start_time_iso: str
    taken_clubs: List[ClientClubDetail] = field(default_factory=list)
    available_clubs: List[ClientClubDetail] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        league_info = data.get('league', {})
        taken_list = [ClientClubDetail.from_dict(tc) for tc in data.get('taken_clubs', [])]
        available_list = [ClientClubDetail.from_dict(ac) for ac in data.get('available_clubs', [])]
        return cls(
            tournament_id=league_info.get('tournament_id', -1),
            name=league_info.get('name', 'Unknown League'),
            number_of_clubs=league_info.get('number_of_clubs', 0),
            start_time_iso=league_info.get('start_time', ''),
            taken_clubs=taken_list,
            available_clubs=available_list
        )

@dataclass
class ClientMatch:
    """Represents match data for the fixtures screen."""
    match_id: int
    round_number: int
    match_time_iso: str
    home_club_id: int
    away_club_id: int
    home_club_name: Optional[str] # Server needs to provide this
    away_club_name: Optional[str] # Server needs to provide this
    home_goals: Optional[int]
    away_goals: Optional[int]
    is_simulated: bool

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            match_id=data.get('match_id', -1),
            round_number=data.get('round_number', 0),
            match_time_iso=data.get('match_time', ''),
            home_club_id=data.get('home_club_id', -1),
            away_club_id=data.get('away_club_id', -1),
            home_club_name=data.get('home_club_name'),
            away_club_name=data.get('away_club_name'),
            home_goals=data.get('home_goals'), # Can be None
            away_goals=data.get('away_goals'), # Can be None
            is_simulated=data.get('is_simulated', False)
        )

@dataclass
class ClientStandingEntry:
    """Represents a single entry in the league standings table."""
    position: int
    club_id: int
    club_name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    points: int

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            position=data.get('position', 0),
            club_id=data.get('club_id', -1),
            club_name=data.get('club_name', 'N/A'),
            played=data.get('played', 0),
            wins=data.get('wins', 0),
            draws=data.get('draws', 0),
            losses=data.get('losses', 0),
            goals_scored=data.get('goals_scored', 0),
            goals_conceded=data.get('goals_conceded', 0),
            goal_difference=data.get('goal_difference', 0),
            points=data.get('points', 0)
        )

@dataclass
class ClientTrainingSettings:
    """Represents the training settings fetched from the server."""
    intensity: int
    focus_area: str # Store the focus area as its string value (e.g., "attack")

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            intensity=data.get('intensity', 3), # Default intensity if missing
            focus_area=data.get('focus_area', 'balanced') # Default focus if missing
        )

@dataclass
class ClientTacticsSettings:
    """Represents the tactics settings fetched from the server."""
    formation: Optional[str] = None # e.g., "4-4-2"
    play_style: Optional[str] = None # e.g., "balanced"
    captain_id: Optional[int] = None
    free_kick_taker_id: Optional[int] = None
    penalty_taker_id: Optional[int] = None
    corner_taker_id: Optional[int] = None
    starting_player_ids_ordered: List[Optional[int]] = field(default_factory=list)
    substitute_player_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        # Check keys used here match server response
        print(f"DEBUG from_dict input data: {data}")  # Add log
        settings = cls(
            formation=data.get('formation'),
            play_style=data.get('play_style'),
            captain_id=data.get('captain_id'),
            free_kick_taker_id=data.get('free_kick_taker_id'),  # Check key again
            penalty_taker_id=data.get('penalty_taker_id'),  # Check key again
            corner_taker_id=data.get('corner_taker_id'),
            starting_player_ids_ordered=data.get('starting_player_ids_ordered', []),
            substitute_player_ids=data.get('substitute_player_ids', [])
        )
        print(f"DEBUG from_dict created settings: {settings}")  # Add log
        return settings

    def to_payload_dict(self) -> Dict[str, Any]:
        """Creates a dictionary suitable for sending as update payload."""
        # Only include fields relevant for the update endpoint
        return {
            "formation": self.formation,
            "play_style": self.play_style,
            "captain_id": self.captain_id,
            "free_kick_taker_id": self.free_kick_taker_id,
            "penalty_taker_id": self.penalty_taker_id,
            "corner_taker_id": self.corner_taker_id,
        }

    def __eq__(self, other):
        """Custom equality check based on update payload fields."""
        if not isinstance(other, ClientTacticsSettings):
            return NotImplemented
        # Compare only the fields that are sent in the update payload
        return self.to_payload_dict() == other.to_payload_dict()

@dataclass
class ClientTransferListedPlayer:
    """Represents a player on the transfer list with all necessary details for display."""
    player_id: int
    listing_club_id: int # The ID of the club that listed the player
    name: str
    position: str
    age: int
    overall_rating: int
    value: int
    asking_price: int
    status: str # Derived status: "Fit", "Inj (2r)", "Sus (1r)"

    is_injured: bool = False
    injury_rounds: int = 0
    is_suspended: bool = False
    suspended_rounds: int = 0
    has_yellow_card: bool = False # Though less relevant for transfer list directly

    @classmethod
    def from_dict(cls, data: dict, labels): # labels needed for status derivation
        """Creates a ClientTransferListedPlayer instance from a dictionary."""
        # Use the same status derivation logic as ClientPlayer
        derived_status = ClientPlayer._derive_status(data, labels) # Use staticmethod

        return cls(
            player_id=data.get('player_id', -1),
            listing_club_id=data.get('club_id', -1), # This is player.club_id from server
            name=data.get('name', 'N/A'),
            position=data.get('position', 'N/A'),
            age=data.get('age', 0),
            overall_rating=data.get('overall_rating', 0),
            value=data.get('value', 0),
            asking_price=data.get('asking_price', 0), # New field
            status=derived_status,
            is_injured=data.get('is_injured', False),
            injury_rounds=data.get('injury_rounds', 0),
            is_suspended=data.get('is_suspended', False),
            suspended_rounds=data.get('suspended_rounds', 0),
            has_yellow_card=data.get('has_yellow_card', False)
        )


@dataclass
class ClientPlayerProfileData:
    """Holds all detailed data for a player to be displayed on their profile screen."""
    # Player Attributes (subset from ClientPlayer or TournamentPlayer.to_dict())
    player_id: int
    name: str
    nation: Optional[str] = None
    club_name: Optional[str] = None  # Name of the club the player belongs to
    club_id: Optional[int] = None  # ID of the club the player belongs to
    age: int = 0
    position: str = "N/A"
    overall_rating: int = 0
    status: str = "Fit"  # Derived: "Fit", "Inj (2r)", "Sus (1r)"
    is_injured: bool = False
    injury_rounds: int = 0
    is_suspended: bool = False
    suspended_rounds: int = 0

    preferred_foot: Optional[str] = None
    weak_foot: Optional[int] = None
    skill_moves: Optional[int] = None

    base_attr1_val: Optional[int] = None  # Pace / Diving
    base_attr2_val: Optional[int] = None  # Shooting / Handling
    base_attr3_val: Optional[int] = None  # Passing / Kicking
    base_attr4_val: Optional[int] = None  # Dribbling / Reflexes
    base_attr5_val: Optional[int] = None  # Defense / Speed (GK)
    base_attr6_val: Optional[int] = None  # Physical / Positioning (GK)

    alternative_positions: str = "-"
    height_cm: Optional[int] = None  # Parsed from original height string
    weight_kg: Optional[int] = None  # Assuming weight is in kg
    fitness: int = 100
    form: int = 50

    play_style_tags: Optional[str] = None  # Original 'play style' string from data

    # Stats
    yellow_cards_received: int = 0
    red_cards_received: int = 0
    goals_scored: int = 0
    assists_given: int = 0
    clean_sheets: int = 0  # Relevant for GK/Def
    matches_played: int = 0
    avg_rating: float = 0.0  # Match average rating
    motm_count: int = 0  # Man of the Match awards
    growth: int = 0  # Player development points/potential
    value: int = 0  # Market value

    # Transfer Context
    is_on_transfer_list: bool = False
    asking_price: Optional[int] = None
    listing_id: Optional[int] = None  # ID of the TransferListing record if listed

    @staticmethod
    def _parse_height_cm(height_str: Optional[str]) -> Optional[int]:
        if not height_str:
            return None
        try:
            if "cm" in height_str:
                # Format like "185cm" or "185cm / 6'1""
                return int(height_str.split("cm")[0].strip())
        except ValueError:
            print(f"Could not parse height_cm from: {height_str}")
        return None

    @staticmethod
    def _parse_weight_kg(weight_str: Optional[str]) -> Optional[int]:
        if not weight_str:
            return None
        try:
            if "kg" in weight_str:
                return int(weight_str.split("kg")[0].strip())
            # Could add lbs to kg conversion if needed
        except ValueError:
            print(f"Could not parse weight_kg from: {weight_str}")
        return None

    @classmethod
    def from_dict(cls, data: dict, labels):  # labels for status
        """Creates ClientPlayerProfileData from a dictionary (likely from server)."""
        player_pos = data.get('position', "N/A")
        is_gk = player_pos.upper() == "GK"

        # Base attributes mapping
        base_attr1 = data.get('pace')
        base_attr2 = data.get('shooting')
        base_attr3 = data.get('passing')
        base_attr4 = data.get('dribbling')
        base_attr5 = data.get('defense')
        base_attr6 = data.get('physical')

        print(f"--- PlayerProfile.from_dict for {data.get('name', 'N/A')} ---")
        print(f"  Is GK: {is_gk}")
        print(f"  Raw data.get('gk_diving'): {data.get('gk_diving')}, Raw data.get('pace'): {data.get('pace')}")
        print(f"  Base Attr 1 (Pace/Diving) assigned: {base_attr1}")
        print(f"  Base Attr 2 (Sho/Handling) assigned: {base_attr2}")
        print(f"  Base Attr 3 (Pas/Kicking) assigned: {base_attr3}")
        print(f"  Base Attr 4 (Dri/Reflexes) assigned: {base_attr4}")
        print(f"  Base Attr 5 (Def/SpeedGK) assigned: {base_attr5}")
        print(f"  Base Attr 6 (Phy/PosGK) assigned: {base_attr6}")
        print(f"  Raw data.get('weak_foot'): {data.get('weak_foot')}")
        print(f"  Raw data.get('skill_moves'): {data.get('skill_moves')}")
        print(f"  Raw data.get('play_style') for play_style_tags: {data.get('play_style')}")
        print(f"  Raw data.get('avg_rating'): {data.get('avg_rating')}, .get('motm_count'): {data.get('motm_count')}, .get('growth'): {data.get('growth')}")
        print(f"  Raw data.get('received_yellow_cards'): {data.get('received_yellow_cards')}, .get('received_red_cards'): {data.get('received_red_cards')}")

        return cls(
            player_id=data.get('player_id', -1),
            name=data.get('name', 'N/A'),
            nation=data.get('nation'),
            club_name=data.get('team_name'),  # 'team_name' from TournamentPlayer.to_dict()
            club_id=data.get('club_id'),  # 'club_id' from TournamentPlayer.to_dict()
            age=data.get('age', 0),
            position=player_pos,
            overall_rating=data.get('overall_rating', 0),
            status=ClientPlayer._derive_status(data, labels),  # Use existing helper
            is_injured=data.get('is_injured', False),
            injury_rounds=data.get('injury_rounds', 0),
            is_suspended=data.get('is_suspended', False),
            suspended_rounds=data.get('suspended_rounds', 0),

            preferred_foot=data.get('preferred_foot'),
            weak_foot=data.get('weak_foot'),
            skill_moves=data.get('skill_moves'),

            base_attr1_val=base_attr1,
            base_attr2_val=base_attr2,
            base_attr3_val=base_attr3,
            base_attr4_val=base_attr4,
            base_attr5_val=base_attr5,
            base_attr6_val=base_attr6,

            alternative_positions=data.get('alternative_positions', "-"),
            height_cm=cls._parse_height_cm(data.get('height')),
            weight_kg=cls._parse_weight_kg(data.get('weight')),  # Assuming weight is like "75kg"
            fitness=data.get('fitness', 100),
            form=data.get('form', 50),

            play_style_tags=data.get('play_style'),  # This is the comma-separated string

            yellow_cards_received=data.get('received_yellow_cards', 0),
            red_cards_received=data.get('received_red_cards', 0),
            goals_scored=data.get('goals_scored', 0),
            assists_given=data.get('assists_given', 0),
            clean_sheets=data.get('clean_sheets', 0),
            matches_played=data.get('matches_played', 0),
            avg_rating=data.get('avg_rating', 0.0),
            motm_count=data.get('motm_count', 0),
            growth=data.get('growth', 0),
            value=data.get('value', 0),

            is_on_transfer_list=data.get('is_on_transfer_list', False),
            asking_price=data.get('asking_price'),  # Will be present if on list
            listing_id=data.get('listing_id')  # Will be present if on list
        )