from sqlalchemy import Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, relationship,  Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum
from datetime import datetime, timezone
from common.enums import TrainingFocusEnum, FormationEnum, PlayStyleEnum, MatchEventTypeEnum, TransferStatus
from common.constants import FORMATION_TEMPLATES
import json






Base = declarative_base()

class OriginalClub(Base):
    """
    Represents the starting state of football clubs.
    Used to initialize tournament-specific clubs.
    """
    __tablename__ = "original_clubs"

    club_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    club_name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    default_tactic_id: Mapped[int | None] = mapped_column(ForeignKey("club_tactics.tactic_id"), nullable=True)
    default_training_id: Mapped[int | None] = mapped_column(ForeignKey("club_training.training_id"), nullable=True)
    default_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=100_000_000)

    avg_overall: Mapped[float | None] = mapped_column(nullable=True)
    total_value: Mapped[int | None] = mapped_column(nullable=True)
    player_count: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    original_players: Mapped[list["OriginalPlayer"]] = relationship(back_populates="club")
    default_tactics: Mapped["ClubTactics"] = relationship(foreign_keys=[default_tactic_id])
    default_training: Mapped["ClubTraining"] = relationship(foreign_keys=[default_training_id])

    def __repr__(self) -> str:
        return f"<OriginalClub #{self.club_id} - {self.club_name} budget: {self.default_budget:_}>"

    def __str__(self) -> str:
        return f"{self.club_name} (ID: {self.club_id}) - Budget: {self.default_budget:_}"

class OriginalPlayer(Base):
    """
    Represents a complete player record from the male_players.csv dataset.
    Used as a template for tournament-specific players.
    """

    __tablename__ = "original_male_players"

    player_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id2: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String, nullable=False)
    overall_rating: Mapped[int] = mapped_column(Integer)
    pac: Mapped[int] = mapped_column(Integer)
    sho: Mapped[int] = mapped_column(Integer)
    pas: Mapped[int] = mapped_column(Integer)
    dri: Mapped[int] = mapped_column(Integer)
    defense: Mapped[int] = mapped_column(Integer)
    phy: Mapped[int] = mapped_column(Integer)
    acceleration: Mapped[int] = mapped_column(Integer)
    sprint_speed: Mapped[int] = mapped_column(Integer)
    positioning: Mapped[int] = mapped_column(Integer)
    finishing: Mapped[int] = mapped_column(Integer)
    shot_power: Mapped[int] = mapped_column(Integer)
    long_shots: Mapped[int] = mapped_column(Integer)
    volleys: Mapped[int] = mapped_column(Integer)
    penalties: Mapped[int] = mapped_column(Integer)
    vision: Mapped[int] = mapped_column(Integer)
    crossing: Mapped[int] = mapped_column(Integer)
    free_kick_accuracy: Mapped[int] = mapped_column(Integer)
    short_passing: Mapped[int] = mapped_column(Integer)
    long_passing: Mapped[int] = mapped_column(Integer)
    curve: Mapped[int] = mapped_column(Integer)
    dribbling: Mapped[int] = mapped_column(Integer)
    agility: Mapped[int] = mapped_column(Integer)
    balance: Mapped[int] = mapped_column(Integer)
    reactions: Mapped[int] = mapped_column(Integer)
    ball_control: Mapped[int] = mapped_column(Integer)
    composure: Mapped[int] = mapped_column(Integer)
    interceptions: Mapped[int] = mapped_column(Integer)
    heading_accuracy: Mapped[int] = mapped_column(Integer)
    def_awareness: Mapped[int] = mapped_column(Integer)
    standing_tackle: Mapped[int] = mapped_column(Integer)
    sliding_tackle: Mapped[int] = mapped_column(Integer)
    jumping: Mapped[int] = mapped_column(Integer)
    stamina: Mapped[int] = mapped_column(Integer)
    strength: Mapped[int] = mapped_column(Integer)
    aggression: Mapped[int] = mapped_column(Integer)

    position: Mapped[str] = mapped_column(String)
    weak_foot: Mapped[int] = mapped_column(Integer)
    skill_moves: Mapped[int] = mapped_column(Integer)
    preferred_foot: Mapped[str] = mapped_column(String)
    height: Mapped[str] = mapped_column(String)
    weight: Mapped[str] = mapped_column(String)
    alternative_positions: Mapped[str] = mapped_column(String)
    age: Mapped[int] = mapped_column(Integer)
    nation: Mapped[str] = mapped_column(String)
    league: Mapped[str] = mapped_column(String)
    team_name: Mapped[str] = mapped_column(String)
    play_style: Mapped[str] = mapped_column(String)
    profile_url: Mapped[str] = mapped_column(String)

    gk_diving: Mapped[int] = mapped_column(Integer)
    gk_handling: Mapped[int] = mapped_column(Integer)
    gk_kicking: Mapped[int] = mapped_column(Integer)
    gk_positioning: Mapped[int] = mapped_column(Integer)
    gk_reflexes: Mapped[int] = mapped_column(Integer)

    club_id: Mapped[int] = mapped_column(ForeignKey("original_clubs.club_id"), nullable=False, index=True)
    club: Mapped["OriginalClub"] = relationship(back_populates="original_players")

    def __repr__(self) -> str:
        return f"<OriginalPlayer #{self.player_id} - {self.name} ({self.position}, OVR: {self.overall_rating})>"

    def __str__(self) -> str:
        return f"{self.name} ({self.position}) - {self.team_name}, OVR: {self.overall_rating}"

class User(Base):
    """
    Represents a user of the game system.
    A user can create tournaments, and manage up to 3 clubs in different tournaments.
    """
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    created_tournaments: Mapped[list["Tournament"]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan"
    )

    managed_clubs: Mapped[list["TournamentClub"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User #{self.user_id} - {self.username}{' [ADMIN]' if self.is_admin else '[USER]'}>"

    def __str__(self) -> str:
        return f"{self.username} ({'admin' if self.is_admin else 'user'})"


class Tournament(Base):
    """
    Represents a tournament. A tournament may be created by a user (manager)
    or by an admin without any user participation.
    """
    __tablename__ = 'tournaments'

    tournament_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    start_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    number_of_clubs: Mapped[int] = mapped_column(nullable=False)
    round_simulation_interval: Mapped[int] = mapped_column(Integer, default=86400)  # seconds (e.g. 1 day)
    is_started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # One-to-many relationship with tournament clubs
    clubs: Mapped[list["TournamentClub"]] = relationship(back_populates="tournament")
    transfer_listings: Mapped[list["TransferListing"]] = relationship(
        back_populates="tournament",
        cascade="all, delete-orphan"
    )
    creator: Mapped["User"] = relationship(back_populates="created_tournaments")
    matches: Mapped[list["TournamentMatch"]] = relationship(
        back_populates="tournament",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tournament #{self.tournament_id} - {self.name}>"

    def __str__(self) -> str:
        creator = f"Created by User #{self.created_by_user_id}" if self.created_by_user_id else "Admin-created"
        return f"{self.name} (Clubs: {self.number_of_clubs}, Starts: {self.start_time.strftime('%Y-%m-%d')}) [{creator}]"

    def to_dict(self):
        return {
            "tournament_id": self.tournament_id,
            "name": self.name,
            "created_by_user_id": self.created_by_user_id,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "start_time": self.start_time.isoformat() if isinstance(self.start_time, datetime) else self.start_time,
            "number_of_clubs": self.number_of_clubs,
            "round_simulation_interval": self.round_simulation_interval,
            "is_started": self.is_started,
        }


class TournamentClub(Base):
    """
    Represents a club in a specific tournament. These records are
    initially created as empty AI-controlled slots, and filled in later
    when a user joins and selects an original club.
    """
    __tablename__ = 'tournament_clubs'

    club_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.tournament_id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    original_club_id: Mapped[int | None] = mapped_column(ForeignKey("original_clubs.club_id"), nullable=True, index=True)
    is_ai_controlled: Mapped[bool] = mapped_column(Boolean, default=True)
    budget: Mapped[int] = mapped_column(default=100_000_000, nullable=False)

    wins: Mapped[int] = mapped_column(default=0, nullable=False)
    draws: Mapped[int] = mapped_column(default=0, nullable=False)
    losses: Mapped[int] = mapped_column(default=0, nullable=False)
    goals_scored: Mapped[int] = mapped_column(default=0, nullable=False)
    goals_conceded: Mapped[int] = mapped_column(default=0, nullable=False)
    points: Mapped[int] = mapped_column(default=0, nullable=False)

    club_name: Mapped[str | None] = mapped_column(String, nullable=True)

    tactic_id: Mapped[int | None] = mapped_column(ForeignKey("club_tactics.tactic_id"))
    training_id: Mapped[int | None] = mapped_column(ForeignKey("club_training.training_id"))


    # Relationships
    tournament: Mapped["Tournament"] = relationship(back_populates="clubs")
    players: Mapped[list["TournamentPlayer"]] = relationship(back_populates="club")
    tactics: Mapped["ClubTactics"] = relationship(back_populates="club", uselist=False)
    training: Mapped["ClubTraining"] = relationship(back_populates="club", uselist=False)
    home_matches: Mapped[list["TournamentMatch"]] = relationship(back_populates="home_club",
                                                                 foreign_keys="[TournamentMatch.home_club_id]")
    away_matches: Mapped[list["TournamentMatch"]] = relationship(back_populates="away_club",
                                                                 foreign_keys="[TournamentMatch.away_club_id]")
    match_lineups: Mapped[list["MatchLineup"]] = relationship(back_populates="club", cascade="all, delete-orphan")
    user: Mapped["User"] = relationship(back_populates="managed_clubs")

    def __repr__(self) -> str:
        return f"<TournamentClub #{self.club_id} - {self.club_name or 'Unnamed'} - Budget: {self.budget}>"

    def __str__(self) -> str:
        return (
            f"{self.club_name or 'Unnamed'} | "
            f"Points: {self.points}, W:{self.wins} D:{self.draws} L:{self.losses} | "
            f"GF:{self.goals_scored} GA:{self.goals_conceded} | "
            f"{'AI-Controlled' if self.is_ai_controlled else 'User-Controlled'} | "
            f"budget: {self.budget:_}"
        )

    def to_dict(self, include_tournament_name=False): # Add flag
        data = {
            "club_id": self.club_id,
            "tournament_id": self.tournament_id,
            "user_id": self.user_id,
            "original_club_id": self.original_club_id,
            "is_ai_controlled": self.is_ai_controlled,
            "budget": self.budget,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "goals_scored": self.goals_scored,
            "goals_conceded": self.goals_conceded,
            "points": self.points,
            "club_name": self.club_name,
            "tactic_id": self.tactic_id,
            "training_id": self.training_id,
        }
        if include_tournament_name and self.tournament:
             data["tournament_name"] = self.tournament.name
        elif include_tournament_name:
             data["tournament_name"] = None # Or "N/A"

        return data

class TournamentPlayer(Base):
    """
    Represents a player within a tournament. This is a full copy of an original player
    with attributes that can be modified throughout the tournament lifecycle.
    """
    __tablename__ = "tournament_players"

    player_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_player_id: Mapped[int | None] = mapped_column(ForeignKey("original_male_players.player_id"), nullable=True,index=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("tournament_clubs.club_id"), nullable=False, index=True)

    # Core info
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    nation: Mapped[str] = mapped_column(String, nullable=False)
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[str] = mapped_column(String, nullable=False, index=True)
    alternative_positions: Mapped[str] = mapped_column(String, nullable=False, default="-")
    preferred_foot: Mapped[str] = mapped_column(String, nullable=False)
    height: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ratings
    overall_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    pace: Mapped[int] = mapped_column(Integer, nullable=False)
    shooting: Mapped[int] = mapped_column(Integer, nullable=False)
    passing: Mapped[int] = mapped_column(Integer, nullable=False)
    dribbling: Mapped[int] = mapped_column(Integer, nullable=False)
    defense: Mapped[int] = mapped_column(Integer, nullable=False)
    physical: Mapped[int] = mapped_column(Integer, nullable=False)

    # Detailed attributes
    acceleration: Mapped[int] = mapped_column(Integer, nullable=False)
    sprint_speed: Mapped[int] = mapped_column(Integer, nullable=False)
    positioning: Mapped[int] = mapped_column(Integer, nullable=False)
    finishing: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_power: Mapped[int] = mapped_column(Integer, nullable=False)
    long_shots: Mapped[int] = mapped_column(Integer, nullable=False)
    volleys: Mapped[int] = mapped_column(Integer, nullable=False)
    penalties: Mapped[int] = mapped_column(Integer, nullable=False)
    vision: Mapped[int] = mapped_column(Integer, nullable=False)
    crossing: Mapped[int] = mapped_column(Integer, nullable=False)
    free_kick_accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    short_passing: Mapped[int] = mapped_column(Integer, nullable=False)
    long_passing: Mapped[int] = mapped_column(Integer, nullable=False)
    curve: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    balance: Mapped[int] = mapped_column(Integer, nullable=False)
    reactions: Mapped[int] = mapped_column(Integer, nullable=False)
    ball_control: Mapped[int] = mapped_column(Integer, nullable=False)
    composure: Mapped[int] = mapped_column(Integer, nullable=False)
    interceptions: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    def_awareness: Mapped[int] = mapped_column(Integer, nullable=False)
    standing_tackle: Mapped[int] = mapped_column(Integer, nullable=False)
    sliding_tackle: Mapped[int] = mapped_column(Integer, nullable=False)
    jumping: Mapped[int] = mapped_column(Integer, nullable=False)
    stamina: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[int] = mapped_column(Integer, nullable=False)
    aggression: Mapped[int] = mapped_column(Integer, nullable=False)

    # GK attributes
    gk_diving: Mapped[int] = mapped_column(Integer, nullable=False)
    gk_handling: Mapped[int] = mapped_column(Integer, nullable=False)
    gk_kicking: Mapped[int] = mapped_column(Integer, nullable=False)
    gk_positioning: Mapped[int] = mapped_column(Integer, nullable=False)
    gk_reflexes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata
    weak_foot: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_moves: Mapped[int] = mapped_column(Integer, nullable=False)
    play_style: Mapped[str] = mapped_column(String, nullable=False, default="-")
    player_url: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Player status
    is_injured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    injury_rounds: Mapped[int] = mapped_column(default=0, nullable=False)

    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspended_rounds: Mapped[int] = mapped_column(Integer,default=0, nullable=False)
    yellow_card_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_yellow_card: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fitness: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    form: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    # Statistics
    goals_scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assists_given: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_yellow_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_red_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clean_sheets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_rating: Mapped[float] = mapped_column(Integer, default=0.0, nullable=False)
    motm_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    growth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    club: Mapped["TournamentClub"] = relationship(back_populates="players")
    transfer_listing: Mapped["TransferListing"] = relationship(
        back_populates="player",
        uselist=False
    )

    def __repr__(self) -> str:
        return f"<TournamentPlayer #{self.player_id} - {self.name} ({self.position}) - OVR {self.overall_rating}>"

    def __str__(self) -> str:
        status = []
        if self.is_injured:
            status.append(f"Injured ({self.injury_rounds} rounds)")
        if self.is_suspended:
            status.append(f"Suspended ({self.suspended_rounds} rounds)")
        status_str = " | ".join(status) if status else "Active"

        return (
            f"{self.name} | {self.nation} | {self.team_name} | Pos: {self.position} | Age: {self.age}| OVR: {self.overall_rating}\n"
            f"Pace: {self.pace} | Shooting: {self.shooting} | "
            f"Passing: {self.passing} | Dribbling: {self.dribbling} | Defense: {self.defense} | "
            f"Physical: {self.physical}\n"
            f"Weak Foot: {self.weak_foot} | Skill Moves: {self.skill_moves} | Value: {self.value:,} | "
            f"{status_str} | Fitness: {self.fitness} | Form: {self.form}"
        )

    def detailed_info(self) -> str:
        fields = []
        for attr in self.__table__.columns.keys():
            value = getattr(self, attr)
            fields.append(f"{attr}: {value}")
        return "\n".join(fields)

    def to_dict(self):
        return {
            "player_id": self.player_id,
            "club_id": self.club_id,
            "name": self.name,
            "nation": self.nation,
            "team_name": self.team_name,
            "position": self.position,
            "alternative_positions": self.alternative_positions,
            "preferred_foot": self.preferred_foot,
            "weak_foot": self.weak_foot,
            "skill_moves": self.skill_moves,
            "play_style": self.play_style,
            "height": self.height,
            "weight": self.weight,
            "age": self.age,
            "overall_rating": self.overall_rating,
            "pace": self.pace,
            "shooting": self.shooting,
            "passing": self.passing,
            "dribbling": self.dribbling,
            "defense": self.defense,
            "physical": self.physical,
            "stamina": self.stamina,
            "value": self.value,
            "is_injured": self.is_injured,
            "injury_rounds": self.injury_rounds,
            "is_suspended": self.is_suspended,
            "suspended_rounds": self.suspended_rounds,
            "has_yellow_card": self.has_yellow_card,
            "fitness": self.fitness,
            "form": self.form,

            "goals_scored": self.goals_scored,
            "assists_given": self.assists_given,
            "matches_played": self.matches_played,
            "avg_rating": self.avg_rating,
            "received_yellow_cards": self.received_yellow_cards,
            "received_red_cards": self.received_red_cards,
            "clean_sheets": self.clean_sheets,
            "motm_count": self.motm_count,
            "growth": self.growth,

        }


class ClubTactics(Base):
    """
    Stores the current tactical setup for a club in a tournament.
    These records are modified but not logged over time.
    """
    __tablename__ = 'club_tactics'

    tactic_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    captain_id: Mapped[int | None] = mapped_column(nullable=True)
    free_kick_taker_id: Mapped[int | None] = mapped_column(nullable=True)
    penalty_taker_id: Mapped[int | None] = mapped_column(nullable=True)
    corner_taker_id: Mapped[int | None] = mapped_column(nullable=True)

    starting_players: Mapped[str] = mapped_column(default="[]") # JSON string: list of objects with pos: player_id pairs
    substitutes: Mapped[str] = mapped_column(default="[]") # JSON string: list with player_ids

    formation: Mapped[FormationEnum] = mapped_column(
        SQLEnum(FormationEnum, native_enum=False),
        default=FormationEnum.FOUR_THREE_THREE
    )

    play_style: Mapped[PlayStyleEnum] = mapped_column(
        SQLEnum(PlayStyleEnum, native_enum=False),
        default=PlayStyleEnum.BALANCED
    )

    # Back-reference: one-to-one with TournamentClub
    club: Mapped["TournamentClub"] = relationship(back_populates="tactics", uselist=False)

    def __repr__(self) -> str:
        return f"<ClubTactics #{self.tactic_id} | {self.formation.value}, {self.play_style.value}>"

    def __str__(self) -> str:
        lines = [
            f"Tactics ID: {self.tactic_id}",
            f"Formation: {self.formation.value}",
            f"Play Style: {self.play_style.value}",
            f"Captain ID: {self.captain_id}",
            f"Free Kick Taker ID: {self.free_kick_taker_id}",
            f"Penalty Taker ID: {self.penalty_taker_id}",
            f"Corner Taker ID: {self.corner_taker_id}",
            f"Starting Lineup: {self.starting_players}",
            f"Substitutes: {self.substitutes}",
        ]
        return "\n".join(lines)

    def to_dict(self):

        ordered_starting_player_ids = []
        current_formation_value = self.formation.value if self.formation else None

        if current_formation_value and current_formation_value in FORMATION_TEMPLATES:
            template_positions = FORMATION_TEMPLATES[current_formation_value]  # e.g., ["GK", "RB", "CB", "CB", ...]

            # This is the JSON stored in DB: e.g., [{"GK": 101}, {"RB": 102}, {"CB": 103}, {"CB": 104}...]
            # It should correspond to the template in terms of player roles.
            raw_starters_list_of_dicts = []
            try:
                raw_starters_list_of_dicts = json.loads(self.starting_players or "[]")
            except (json.JSONDecodeError, TypeError) as e:
                print(
                    f"Error parsing self.starting_players JSON for tactics {self.tactic_id}: {e}. JSON: '{self.starting_players}'")

            if len(raw_starters_list_of_dicts) == len(template_positions):
                for i, template_pos_name in enumerate(template_positions):
                    slot_dict = raw_starters_list_of_dicts[i]  # e.g., {"GK": 101}
                    player_id_in_slot = None
                    if isinstance(slot_dict, dict) and len(slot_dict) == 1:
                        player_id_in_slot = list(slot_dict.values())[0]
                    elif slot_dict is None:  # If raw data explicitly stored None for a slot
                        player_id_in_slot = None
                    else:
                        print(f"Warning: Malformed slot_dict in tactics {self.tactic_id} at index {i}: {slot_dict}")

                    ordered_starting_player_ids.append(player_id_in_slot)
            else:
                print(
                    f"Warning: Length mismatch for tactics {self.tactic_id}. Template len: {len(template_positions)}, Stored lineup len: {len(raw_starters_list_of_dicts)}. Defaulting to Nones.")
                ordered_starting_player_ids = [None] * len(template_positions)

        else:  # Fallback if no valid formation
            if self.formation:
                print(
                    f"Warning: Formation '{current_formation_value}' for tactics {self.tactic_id} not found in FORMATION_TEMPLATES.")
            num_slots_fallback = 11  # Default if no other info
            try:
                raw = json.loads(self.starting_players or "[]")
                if isinstance(raw, list): num_slots_fallback = len(raw) if raw else 11
            except:
                pass
            ordered_starting_player_ids = [None] * num_slots_fallback

        # Process substitutes
        subs_ids = []
        try:
            raw_subs = json.loads(self.substitutes or "[]")
            if isinstance(raw_subs, list):
                subs_ids = [pid for pid in raw_subs if isinstance(pid, int)]
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing self.substitutes JSON for tactics {self.tactic_id}: {e}. JSON: '{self.substitutes}'")

        return {
            "tactic_id": self.tactic_id,
            "captain_id": self.captain_id,
            "free_kick_taker_id": self.free_kick_taker_id,
            "penalty_taker_id": self.penalty_taker_id,
            "corner_taker_id": self.corner_taker_id,
            "starting_player_ids_ordered": ordered_starting_player_ids,
            "substitute_player_ids": subs_ids,
            "formation": current_formation_value,
            "play_style": self.play_style.value if self.play_style else None,
        }


class ClubTraining(Base):
    """
    Stores the active training strategy for a tournament club.
    """
    __tablename__ = 'club_training'

    training_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intensity: Mapped[int] = mapped_column(nullable=False) # Value between 1 - 10
    focus_area: Mapped[TrainingFocusEnum] = mapped_column(
        SQLEnum(TrainingFocusEnum, native_enum=False),
        default=TrainingFocusEnum.BALANCED
    )

    # Back-reference: one-to-one with TournamentClub
    club: Mapped["TournamentClub"] = relationship(back_populates="training", uselist=False)



    def __repr__(self) -> str:
        return f"<ClubTraining #{self.training_id} - {self.focus_area} (Intensity: {self.intensity})>"

    def __str__(self) -> str:
        return f"{self.focus_area} (Intensity: {self.intensity})"

    def to_dict(self):
        return {
            "training_id": self.training_id,
            "intensity": self.intensity,
            "focus_area": self.focus_area.value,
        }


class TournamentMatch(Base):
    """
    Represents a single match in a tournament's fixture schedule.
    """
    __tablename__ = 'tournament_matches'

    match_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.tournament_id"), nullable=False, index=True)

    round_number: Mapped[int] = mapped_column(nullable=False, index=True)
    match_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    home_club_id: Mapped[int] = mapped_column(ForeignKey("tournament_clubs.club_id"), nullable=False, index=True)
    away_club_id: Mapped[int] = mapped_column(ForeignKey("tournament_clubs.club_id"), nullable=False, index=True)

    home_goals: Mapped[int | None] = mapped_column(nullable=True)
    away_goals: Mapped[int | None] = mapped_column(nullable=True)

    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)

    tournament: Mapped["Tournament"] = relationship(back_populates="matches")
    home_club: Mapped["TournamentClub"] = relationship(foreign_keys=[home_club_id], back_populates="home_matches")
    away_club: Mapped["TournamentClub"] = relationship(foreign_keys=[away_club_id], back_populates="away_matches")
    lineups: Mapped[list["MatchLineup"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    events: Mapped[list["TournamentMatchEvent"]] = relationship(back_populates="match", cascade="all, delete-orphan")

    def __repr__(self):
        if self.is_simulated:
            return f"<TournamentMatch #{self.match_id} Round: {self.round_number} - {self.home_club.club_name} {self.home_goals}  - {self.away_goals} {self.away_club.club_name} (Simulated)>"
        else:
            return f"<TournamentMatch #{self.match_id} Round: {self.round_number} - {self.home_club.club_name} vs {self.away_club.club_name}>"

    def __str__(self) -> str:
        if self.is_simulated:
            return f"Round: {self.round_number}, Time: {self.match_time} - {self.home_club.club_name} {self.home_goals} - {self.away_goals} {self.away_club.club_name} (Simulated)"
        else:
            return f"Round: {self.round_number}, Time: {self.match_time} - {self.home_club.club_name} vs {self.away_club.club_name}"

    def detailed(self) -> str:
        if self.is_simulated:
            return f"Round: {self.round_number}, Time: {self.match_time} - {self.home_club.club_name} ({self.home_club_id}) {self.home_goals} - {self.away_goals} {self.away_club.club_name} ({self.away_club_id}) (Simulated)"
        else:
            return f"Round: {self.round_number}, Time: {self.match_time} - {self.home_club.club_name} ({self.home_club_id}) vs {self.away_club.club_name} ({self.away_club_id})"

    def to_dict(self, include_clubs=False):
        """Converts the match object to a dictionary for API responses."""
        data = {
            "match_id": self.match_id,
            "tournament_id": self.tournament_id,
            "round_number": self.round_number,
            # Ensure datetime is converted to ISO format string
            "match_time": self.match_time.isoformat() if isinstance(self.match_time, datetime) else self.match_time,
            "home_club_id": self.home_club_id,
            "away_club_id": self.away_club_id,
            "home_goals": self.home_goals, # Can be None if not simulated
            "away_goals": self.away_goals, # Can be None if not simulated
            "is_simulated": self.is_simulated,
        }
        if include_clubs and self.home_club and self.away_club:
            data["home_club_name"] = self.home_club.club_name
            data["away_club_name"] = self.away_club.club_name
        elif include_clubs:
             # Handle cases where relationships might not be loaded (though less likely here)
             print(f"Warning: Club names requested for match {self.match_id}, but relationships not loaded.")
             data["home_club_name"] = None
             data["away_club_name"] = None
        return data

class TournamentMatchEvent(Base):
    """
    Stores individual events that occurred during a tournament match.
    Supports all major gameplay events: goals, cards, substitutions, etc.
    """
    __tablename__ = "tournament_match_events"

    event_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("tournament_matches.match_id"), nullable=False, index=True)
    club_id: Mapped[int | None] = mapped_column(ForeignKey("tournament_clubs.club_id"), nullable=True, index=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("tournament_players.player_id"), nullable=True)

    minute: Mapped[int] = mapped_column(nullable=False)

    event_type: Mapped[MatchEventTypeEnum] = mapped_column(SQLEnum(MatchEventTypeEnum, native_enum=False),nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    match: Mapped["TournamentMatch"] = relationship(back_populates="events")
    club: Mapped["TournamentClub"] = relationship()
    player: Mapped["TournamentPlayer"] = relationship()

    def __repr__(self) -> str:
        return f"<Event #{self.event_id} @ {self.minute}': {self.event_type} - {self.description}>"

    def __str__(self) -> str:
        return f"[{self.minute}'] {self.event_type}: {self.description}"

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "match_id": self.match_id,
            "club_id": self.club_id,
            "player_id": self.player_id,
            "minute": self.minute,
            "event_type": self.event_type.value,
            "description": self.description,
        }

class MatchLineup(Base):
    """
    Represents the lineup and bench players a club used in a specific match.
    """
    __tablename__ = "match_lineups"

    lineup_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("tournament_matches.match_id"), nullable=False, index=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("tournament_clubs.club_id"), nullable=False, index=True)

    formation: Mapped[FormationEnum] = mapped_column(
        SQLEnum(FormationEnum, native_enum=False), nullable=False
    )
    starting_players: Mapped[str] = mapped_column(String, nullable=False)
    substitutes: Mapped[str] = mapped_column(String, nullable=False)
    captain_id: Mapped[int | None] = mapped_column(nullable=True)

    match: Mapped["TournamentMatch"] = relationship(back_populates="lineups")
    club: Mapped["TournamentClub"] = relationship(back_populates="match_lineups")


class TransferListing(Base):
    """
    Represents a player placed on the transfer list, and their status.
    """
    __tablename__ = "transfer_listings"

    listing_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.tournament_id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tournament_players.player_id"), nullable=False, index=True)
    asking_price: Mapped[int] = mapped_column(nullable=False)

    status: Mapped[TransferStatus] = mapped_column(
        SQLEnum(TransferStatus, native_enum=False),
        default=TransferStatus.LISTED, index=True
    )
    listed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))

    tournament: Mapped["Tournament"] = relationship(back_populates="transfer_listings")
    player: Mapped["TournamentPlayer"] = relationship(back_populates="transfer_listing")




