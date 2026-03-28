import pandas as pd
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

from common.enums import MatchEventTypeEnum, TransferStatus
from server.database.models import OriginalPlayer, OriginalClub, Base, ClubTactics, ClubTraining, Tournament, \
    TournamentClub, TournamentMatch, TournamentPlayer, TournamentMatchEvent, TransferListing
from server.database.models import FormationEnum, PlayStyleEnum, TrainingFocusEnum
from server.database.db_session import SessionLocal, engine
from server.simulation.schemas import MatchSimulationData
from pathlib import Path
from common.constants import DATA_PATH, FORMATION_TEMPLATES, ATTACKERS, MIDFIELDERS, DEFENDERS, \
    FREE_AGENTS_CLUB_NAME_PREFIX
from common.utilities import log_to_screen
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import random
import json
from itertools import combinations

FOCUS_AREA_STATS = {
    TrainingFocusEnum.ATTACK: ["finishing", "long_shots", "positioning", "volleys", "dribbling", "shooting"],
    TrainingFocusEnum.DEFENSE: ["interceptions", "standing_tackle", "sliding_tackle", "heading_accuracy", "def_awareness", "defense"],
    TrainingFocusEnum.STAMINA: ["stamina", "strength", "aggression", "physical"],
    TrainingFocusEnum.TACTICAL: ["vision", "reactions", "composure", "interceptions", "passing"], # Mix
    TrainingFocusEnum.TECHNICAL: ["ball_control", "dribbling", "short_passing", "curve", "crossing", "passing"],
    TrainingFocusEnum.MENTALITY: ["aggression", "vision", "reactions", "composure", "positioning", "penalties"],
    TrainingFocusEnum.PHYSICAL: ["acceleration", "sprint_speed", "agility", "balance", "jumping", "stamina", "strength", "physical"],
    TrainingFocusEnum.BALANCED: ["pace", "shooting", "passing", "dribbling", "defense", "physical"] # Broad
}

FOCUS_LOW_STAT_TARGET = {
    TrainingFocusEnum.ATTACK: ("finishing", 75),
    TrainingFocusEnum.DEFENSE: ("standing_tackle", 75),
    TrainingFocusEnum.STAMINA: ("stamina", 80),
    TrainingFocusEnum.TACTICAL: ("vision", 70),
    TrainingFocusEnum.TECHNICAL: ("ball_control", 80),
    TrainingFocusEnum.MENTALITY: ("composure", 75),
    TrainingFocusEnum.PHYSICAL: ("strength", 75),
    TrainingFocusEnum.BALANCED: (None, 0) # No specific low stat boost for balanced
}

NATION_POPULARITY = {
    "top": {"Argentina", "Brazil", "France", "England", "Germany", "Spain", "Italy", "Portugal", "Netherlands", "Belgium"},
    "popular": {"Croatia", "Uruguay", "Denmark", "Switzerland", "Senegal", "USA", "Mexico", "Colombia", "Poland", "Sweden", "Norway", "Hungary"},
    # All others are considered 'other'
}

def get_stat(player, attr_name):
    val = getattr(player, attr_name, None)
    return int(val) if isinstance(val, (int, float)) and not pd.isna(val) else 0

def is_attacker(pos: str) -> bool:
    return pos in ATTACKERS


def is_midfielder(pos: str) -> bool:
    return pos in MIDFIELDERS

def is_defender(pos: str) -> bool:
    return pos in DEFENDERS



def calculate_player_value(player: OriginalPlayer, max_value: int = 100_000_000) -> int:
    """
    Calculates an estimated market value for a player based on various attributes.

    Args:
        player: The OriginalPlayer object containing base stats.
        max_value: The maximum possible value for a player.

    Returns:
        An integer representing the calculated player value.
    """
    if player.overall_rating < 40:  # Very low rated players have minimal value
        return random.randint(5_000, 75_000)

    # --- Base Value from OVR (Stronger scaling) ---
    # Exponential scaling - make high OVR players much more valuable
    # OVR contributes ~50% of max possible value at 100 OVR.
    ovr_ratio = player.overall_rating / 100.0
    base_ovr_value = (ovr_ratio ** 3.3) * (max_value * 0.55)

    # --- Age Modifier ---
    age = player.age
    if age <= 19:
        age_multiplier = 1.30  # Very high potential
    elif age <= 22:
        age_multiplier = 1.50  # Approaching peak potential
    elif age <= 26:
        age_multiplier = 1.60  # Prime years
    elif age <= 29:
        age_multiplier = 1.40  # Still prime
    elif age <= 31:
        age_multiplier = 1.00  # Good experience
    elif age <= 33:
        age_multiplier = 0.65  # Declining
    elif age <= 35:
        age_multiplier = 0.35  # Significant decline
    else:
        age_multiplier = 0.15  # Near retirement

    # --- Position Modifier  ---
    if player.position in ATTACKERS:
        position_multiplier = 1.25  # High value attackers
    elif player.position in MIDFIELDERS:
        position_multiplier = 1.05
    elif player.position in DEFENDERS and player.position != "GK":
        position_multiplier = 0.95
    elif player.position == "GK":
        position_multiplier = 0.80  # GKs generally cheaper
    else:
        position_multiplier = 1.0

    # --- Nation Popularity Modifier ---
    nation = player.nation
    if nation in NATION_POPULARITY["top"]:
        nation_multiplier = 1.12
    elif nation in NATION_POPULARITY["popular"]:
        nation_multiplier = 1.03
    else:
        nation_multiplier = 1.0

    # --- Skill Modifiers (Smaller impact) ---
    skill_moves_mult = 1.0 + (player.skill_moves - 3) * 0.03
    weak_foot_mult = 1.0 + (player.weak_foot - 3) * 0.05
    alt_pos_count = len(player.alternative_positions.split(
        ',')) if player.alternative_positions and player.alternative_positions != '-' else 0
    versatility_mult = 1.0 + alt_pos_count * 0.02

    # --- Attribute Modifiers (Smaller impact) ---
    attr_multiplier = 1.0
    if player.position == "GK":
        gk_avg = (player.gk_diving + player.gk_handling + player.gk_kicking + player.gk_positioning + player.gk_reflexes) / 5
        try:
            height = player.height.split('/')[0].strip()  # Extract height in feet
            if 'cm' in height:
                h_cm = int(height.replace('cm', '').strip())
            elif "'" in player.height:
                parts = player.height.replace('"', '').split("'"); h_cm = int(parts[0]) * 30.48 + int(parts[1]) * 2.54
            else:
                h_cm = 185
        except:
            h_cm = 185
        height_bonus = max(0, (h_cm - 185) / 20) * 0.09
        attr_multiplier = 1.0 + max(0, (gk_avg - 78)) * 0.005 + height_bonus  # Bonus for GK avg > 75
    else:  # Outfield Player
        # Weight key stats differently based on general role
        if player.position in ATTACKERS:
            key_stats = (player.pac * 1.1 + player.sho * 1.2 + player.dri * 1.1 + player.phy * 0.8 + player.pas * 0.9 + player.defense * 0.7) / 5.8
        elif player.position in MIDFIELDERS:
            key_stats = (player.pas * 1.2 + player.dri * 1.1 + player.sho * 1.0 + player.pac * 1.0 + player.defense * 1.0 + player.phy * 0.9) / 6.2
        else:  # DEFENDERS
            key_stats = (player.defense * 1.2 + player.phy * 1.1 + player.pac * 0.9 + player.pas * 1.0 + player.dri * 0.8 + player.sho * 0.6) / 5.6
        # Bonus if weighted key stats exceed overall
        attr_bonus = max(0, (key_stats - player.overall_rating) / 8) * 0.05
        attr_multiplier = 1.0 + attr_bonus

    # --- Combine Multipliers ---
    calculated_value = base_ovr_value * age_multiplier * position_multiplier * nation_multiplier \
                       * skill_moves_mult * weak_foot_mult * versatility_mult * attr_multiplier

    # --- Final Clamping and Rounding ---
    final_value = max(10_000, min(calculated_value, max_value))  # Min value 10k
    # Rounding
    if final_value > 10_000_000:
        final_value = round(final_value / 100_000) * 100_000
    elif final_value > 1_000_000:
        final_value = round(final_value / 50_000) * 50_000
    elif final_value > 100_000:
        final_value = round(final_value / 10_000) * 10_000
    else:
        final_value = round(final_value / 5_000) * 5_000

        # Clamp based on OVR bands to prevent weird results
        if player.overall_rating >= 85 and final_value < 20_000_000: final_value = 20_000_000 + random.randint(0,5_000_000)  # Ensure top players worth minimum
        if player.overall_rating < 60 and final_value > 2_000_000: final_value = max(25_000, min(final_value * 0.6,2_000_000))  # Cap lower players

    return int(final_value)

def calculate_club_budgets(df: pd.DataFrame, min_budget: int = 20_000_000, max_budget: int = 120_000_000) -> dict:
    """
    Calculates a fair inverse budget for each club based on average overall rating.
    Weaker teams receive higher budgets, stronger teams receive less.

    :param df: DataFrame with at least 'Team' and 'OVR' columns.
    :param min_budget: Minimum allowed club budget (e.g. 20 million).
    :param max_budget: Maximum allowed club budget (e.g. 120 million).
    :return: Dictionary mapping club names to their budget.
    """
    team_avg_ovr = df.groupby("Team")["OVR"].mean()

    min_ovr = team_avg_ovr.min()
    max_ovr = team_avg_ovr.max()

    budgets = {}
    for team, avg_ovr in team_avg_ovr.items():
        if max_ovr != min_ovr:
            normalized = (avg_ovr - min_ovr) / (max_ovr - min_ovr)
        else:
            normalized = 1.0

        inverted = 1.0 - normalized
        budget = int(round(min_budget + inverted * (max_budget - min_budget), 0))
        budgets[team] = budget

    log_to_screen("Calculated club budgets based on average overall ratings.", True)

    return budgets


class DataManager:
    """
    Handles all data operations related to original players and clubs.
    - Loads CSV data
    - Initializes and populates the database via SQLAlchemy ORM
    """

    def __init__(self, data_directory: Path = DATA_PATH, logging_enabled: bool = False) -> None:
        """
        Initializes the DataManager with a data path, sets up the DB schema,
        and populates tables if the DB is empty.

        :param data_directory: Path where CSV and DB file are located
        :param logging_enabled: Enable logging output
        """
        self.data_directory: Path = data_directory
        self.logging_enabled: bool = logging_enabled
        self.csv_path: Path = self.data_directory / "male_players.csv"
        self.player_data: Optional[pd.DataFrame] = None

        # Create all tables in the database if not present
        Base.metadata.create_all(bind=engine)
        log_to_screen("ORM models bound to the database.", self.logging_enabled)

        # Create session for interacting with DB
        self.session: Session = SessionLocal()

        # Only populate the database on first run
        if not self.session.query(OriginalPlayer).first():
            self._initialize_database()
            log_to_screen("Database initialized and populated with data.", self.logging_enabled)
        else:
            self._load_csv() # Uncomment for testing
            log_to_screen("Database already populated. Skipping initialization.", self.logging_enabled)


    def _initialize_database(self) -> None:
        """
        Loads player data from CSV and populates both the clubs and players tables.
        """
        self._load_csv()
        self._create_original_clubs()
        self._create_players()
        self._assign_default_lineups_and_specialists()
        self._calculate_and_store_club_stats()

    def _load_csv(self) -> None:
        """
        Loads the CSV into a pandas DataFrame and cleans it before further use.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV not found at: {self.csv_path}")
        self.player_data = pd.read_csv(self.csv_path)
        self._clean_player_dataframe()

        log_to_screen(
            f"Loaded and cleaned {len(self.player_data)} player records from CSV.",
            self.logging_enabled
        )

    def _clean_player_dataframe(self) -> None:
        """
        Cleans the player DataFrame:
        - Replaces nulls in categorical fields with '-'.
        - Fills missing goalkeeper stat fields with a random int between 10 and 33.
        - Casts all goalkeeper stat fields to integers.
        """
        if self.player_data is None:
            raise ValueError("Player data must be loaded before cleaning.")

        df = self.player_data

        # Fill nulls in string-based fields
        df["Alternative positions"] = df["Alternative positions"].fillna("-")
        df["play style"] = df["play style"].fillna("-")

        # Fill GK columns with random integers between 10 and 33 if null
        gk_columns = [
            "GK Diving", "GK Handling", "GK Kicking", "GK Positioning", "GK Reflexes"
        ]

        for column in gk_columns:
            df[column] = df[column].apply(
                lambda x: int(x) if pd.notna(x) else random.randint(10, 33)
            )

        self.player_data = df

    def _create_original_clubs(self) -> None:
        """
        Create OriginalClub records based on unique team names in the dataset.
        Each club also gets a default tactic and training plan.
        Weaker clubs get higher default budgets.
        """
        unique_teams = self.player_data["Team"].unique()
        club_budgets = calculate_club_budgets(self.player_data)

        for team_name in unique_teams:
            budget = club_budgets.get(team_name, 50_000_000)
            tactics = ClubTactics(
                formation=FormationEnum.FOUR_THREE_THREE,
                play_style=PlayStyleEnum.BALANCED,
                starting_players="[]",
                substitutes="[]",
                captain_id=None,
                free_kick_taker_id=None,
                penalty_taker_id=None,
                corner_taker_id=None,
            )
            self.session.add(tactics)
            self.session.flush()
            training = ClubTraining(
                focus_area=TrainingFocusEnum.BALANCED,
                intensity=3
            )
            self.session.add(training)
            self.session.flush()
            new_club = OriginalClub(
                club_name=team_name,
                default_budget=budget,
                default_tactic_id=tactics.tactic_id,
                default_training_id=training.training_id
            )
            self.session.add(new_club)

        self.session.commit()

        log_to_screen(f"Created {len(club_budgets)} original clubs with budgets, tactics, and training.", self.logging_enabled)

    def _create_players(self) -> None:
        """
        Adds all players to the original_male_players table with full CSV data.
        """
        club_map = {
            club.club_name: club.club_id
            for club in self.session.query(OriginalClub).all()
        }

        for _, row in self.player_data.iterrows():
            player = OriginalPlayer(
                id2=row.get("id2"),
                rank=row.get("Rank"),
                name=row.get("Name"),
                overall_rating=row.get("OVR"),
                pac=row.get("PAC"),
                sho=row.get("SHO"),
                pas=row.get("PAS"),
                dri=row.get("DRI"),
                defense=row.get("DEF"),
                phy=row.get("PHY"),
                acceleration=row.get("Acceleration"),
                sprint_speed=row.get("Sprint Speed"),
                positioning=row.get("Positioning"),
                finishing=row.get("Finishing"),
                shot_power=row.get("Shot Power"),
                long_shots=row.get("Long Shots"),
                volleys=row.get("Volleys"),
                penalties=row.get("Penalties"),
                vision=row.get("Vision"),
                crossing=row.get("Crossing"),
                free_kick_accuracy=row.get("Free Kick Accuracy"),
                short_passing=row.get("Short Passing"),
                long_passing=row.get("Long Passing"),
                curve=row.get("Curve"),
                dribbling=row.get("Dribbling"),
                agility=row.get("Agility"),
                balance=row.get("Balance"),
                reactions=row.get("Reactions"),
                ball_control=row.get("Ball Control"),
                composure=row.get("Composure"),
                interceptions=row.get("Interceptions"),
                heading_accuracy=row.get("Heading Accuracy"),
                def_awareness=row.get("Def Awareness"),
                standing_tackle=row.get("Standing Tackle"),
                sliding_tackle=row.get("Sliding Tackle"),
                jumping=row.get("Jumping"),
                stamina=row.get("Stamina"),
                strength=row.get("Strength"),
                aggression=row.get("Aggression"),
                position=row.get("Position"),
                weak_foot=row.get("Weak foot"),
                skill_moves=row.get("Skill moves"),
                preferred_foot=row.get("Preferred foot"),
                height=row.get("Height"),
                weight=row.get("Weight"),
                alternative_positions=row.get("Alternative positions"),
                age=row.get("Age"),
                nation=row.get("Nation"),
                league=row.get("League"),
                team_name=row.get("Team"),
                play_style=row.get("play style"),
                profile_url=row.get("url"),
                gk_diving=row.get("GK Diving"),
                gk_handling=row.get("GK Handling"),
                gk_kicking=row.get("GK Kicking"),
                gk_positioning=row.get("GK Positioning"),
                gk_reflexes=row.get("GK Reflexes"),
                club_id=club_map[row["Team"]],
            )

            self.session.add(player)

        self.session.commit()

        log_to_screen(
            f"Populated original_male_players with {len(self.player_data)} players.",
            self.logging_enabled
        )

    def _calculate_and_store_club_stats(self) -> None:
        """Calculates avg OVR, total value, and player count for each OriginalClub."""
        session = SessionLocal()  # Use a separate session for this operation
        try:
            print("Calculating and storing original club stats...")
            all_original_clubs = session.query(OriginalClub).options(
                joinedload(OriginalClub.original_players)  # Eager load players
            ).all()
            updated_count = 0
            for club in all_original_clubs:
                players = club.original_players
                if players:
                    club.player_count = len(players)
                    club.avg_overall = round(sum(p.overall_rating for p in players) / club.player_count, 1)
                    club.total_value = sum(calculate_player_value(p) for p in players)
                    updated_count += 1
                else:
                    club.player_count = 0
                    club.avg_overall = 0.0
                    club.total_value = 0

            session.commit()
            print(f"Stored calculated stats for {updated_count} original clubs.")
        except Exception as e:
            print(f"Error calculating/storing club stats: {e}")
            session.rollback()
        finally:
            session.close()

    def _assign_default_lineups_and_specialists(self) -> None:
        """
        Assigns default starting lineups, substitutes, and specialist roles
        for each original club's tactics during initial database population.
        Includes fallbacks for specialist assignment if ideal candidates are missing.
        """
        session = self.session # Use the instance's session

        all_original_clubs = session.query(OriginalClub).options(
            joinedload(OriginalClub.default_tactics) # Eager load for modification
        ).all()
        total_updated = 0

        for club in all_original_clubs:
            if not club.default_tactics:
                print(f"Warning (Initial Setup): OriginalClub {club.club_name} (ID: {club.club_id}) missing default_tactics. Skipping.")
                continue
            tactics = club.default_tactics
            formation_enum_val = tactics.formation
            if not formation_enum_val:
                print(f"Warning (Initial Setup): OriginalClub {club.club_name} tactics has no formation. Skipping.")
                continue

            formation_str = formation_enum_val.value
            team_name = club.club_name

            # Generate lineup and substitutes (using OriginalPlayer IDs)
            # Assuming generate_default_lineup returns IDs from OriginalPlayer table here
            generated_lineup_list_of_dicts, generated_substitute_ids = self.generate_default_lineup(
                club_name=team_name, formation=formation_str
            )

            tactics.starting_players = json.dumps(generated_lineup_list_of_dicts)
            tactics.substitutes = json.dumps(generated_substitute_ids)

            # --- Assign Specialists using OriginalPlayer IDs ---
            starting_original_player_ids = [
                pid for slot in generated_lineup_list_of_dicts
                for pid in slot.values() if pid is not None
            ]

            # Initialize specialist IDs to None
            tactics.captain_id = None
            tactics.free_kick_taker_id = None
            tactics.penalty_taker_id = None
            tactics.corner_taker_id = None

            if starting_original_player_ids:
                # Fetch the OriginalPlayer objects for the generated starting lineup
                starting_original_players = session.query(OriginalPlayer).filter(
                    OriginalPlayer.player_id.in_(starting_original_player_ids)
                ).all()

                if starting_original_players:
                    # Captain = oldest OriginalPlayer in lineup
                    try:
                        tactics.captain_id = max(starting_original_players, key=lambda p: p.age or 0).player_id
                    except ValueError:  # Handles empty list just in case
                        print(f"ERROR (Initial Setup - {club.club_name}): No starters found for Captain.")

                    # --- Free Kick Taker ---
                    fk_candidates = [p for p in starting_original_players if
                                     is_attacker(p.position) or is_midfielder(p.position)]
                    if fk_candidates:
                        tactics.free_kick_taker_id = max(fk_candidates,key=lambda p: get_stat(p, 'free_kick_accuracy')).player_id
                    elif starting_original_players:  # Fallback 1: Best FK accuracy from any starter
                        print(f"WARN (Initial Setup - {club.club_name}): No ATK/MID found for FK taker. Using best overall starter.")
                        tactics.free_kick_taker_id = max(starting_original_players, key=lambda p: get_stat(p, 'free_kick_accuracy')).player_id


                    # --- Penalty Taker ---
                    pen_candidates = [p for p in starting_original_players if is_attacker(p.position)]
                    if pen_candidates:
                        tactics.penalty_taker_id = max(pen_candidates, key=lambda p: get_stat(p, 'penalties')).player_id
                    # Fallback 1: Use FK taker if assigned
                    elif tactics.free_kick_taker_id is not None:
                        print(f"WARN (Initial Setup - {club.club_name}): No ATK found for PEN taker. Using FK taker.")
                        tactics.penalty_taker_id = tactics.free_kick_taker_id
                    # Fallback 2: Use best penalty stat from any starter
                    elif starting_original_players:
                        print(f"WARN (Initial Setup - {club.club_name}): No ATK or FK taker for PEN taker. Using best overall starter.")
                        tactics.penalty_taker_id = max(starting_original_players,key=lambda p: get_stat(p, 'penalties')).player_id

                    # --- Corner Taker ---
                    corner_candidates = [p for p in starting_original_players if is_midfielder(p.position)]
                    if corner_candidates:
                        tactics.corner_taker_id = max(corner_candidates, key=lambda p: get_stat(p, 'crossing')).player_id
                    # Fallback 1: Use FK taker if assigned
                    elif tactics.free_kick_taker_id is not None:
                         print(f"WARN (Initial Setup - {club.club_name}): No MID found for CORNER taker. Using FK taker.")
                         tactics.corner_taker_id = tactics.free_kick_taker_id
                    # Fallback 2: Use best crossing stat from any starter
                    elif starting_original_players:
                        print(f"WARN (Initial Setup - {club.club_name}): No MID or FK taker for CORNER taker. Using best overall starter.")
                        tactics.corner_taker_id = max(starting_original_players, key=lambda p: get_stat(p, 'crossing')).player_id

            else:
                print(f"Warning (Initial Setup - {club.club_name}): No starting players generated, specialists set to None.")
                # Specialist IDs remain None as initialized

            total_updated += 1
        session.commit()
        print(f"Assigned default lineups and specialists with fallbacks for {total_updated} original clubs.")

    def create_tournament(self,
            name: str,
            creator_id: int | None, # User ID is now required from payload
            start_delay_sec: int,
            num_clubs: int,
            round_interval_sec: int
    ) -> Tournament: # Return the created Tournament object
        """
        Creates a new tournament, empty club slots, and round-robin matches.
        Uses its own session for thread safety.

        :param name: Name of the tournament
        :param creator_id: User ID of the creator
        :param start_delay_sec: Delay in seconds from now to when the tournament starts
        :param num_clubs: Total number of clubs in the tournament
        :param round_interval_sec: Delay in seconds between round simulations
        :return: The created Tournament object
        :raises ValueError: If input is invalid (e.g., num_clubs < 2)
        :raises Exception: For database errors.
        """
        if num_clubs < 2:
             raise ValueError("Tournament must have at least 2 clubs.")
        if start_delay_sec <= 0 or round_interval_sec <= 0:
             raise ValueError("Start delay and round interval must be positive.")

        session = SessionLocal() # Create a new session for this operation
        try:
            now = datetime.now(timezone.utc)
            start_time = now + timedelta(seconds=start_delay_sec)

            tournament = Tournament(
                name=name,
                created_by_user_id=creator_id,
                created_at=now,
                start_time=start_time,
                number_of_clubs=num_clubs,
                round_simulation_interval=round_interval_sec
            )
            session.add(tournament)
            session.flush() # Get the tournament_id

            # Create empty club slots
            generated_playable_clubs = []
            for _ in range(num_clubs):  # Only create slots for the specified number of clubs
                club = TournamentClub(
                    tournament_id=tournament.tournament_id,
                    is_ai_controlled=True,
                    user_id=None,
                    original_club_id=None,
                    club_name=None,
                    budget=0,
                )
                session.add(club)
                generated_playable_clubs.append(club)

            # Create the "Free Agents" club for this tournament
            free_agents_club_name = f"{FREE_AGENTS_CLUB_NAME_PREFIX} T{tournament.tournament_id}"
            free_agents_club = TournamentClub(
                tournament_id=tournament.tournament_id,
                is_ai_controlled=True,  # Always AI controlled
                user_id=None,
                original_club_id=None,  # Does not map to an OriginalClub
                club_name=free_agents_club_name,
                budget=0,  # No budget needed for this club
                # Set W/D/L/GS/GC/Pts to 0 or ensure defaults handle it
                wins=0, draws=0, losses=0, goals_scored=0, goals_conceded=0, points=-999
                # Make points very low so it's never in standings
            )
            session.add(free_agents_club)
            log_to_screen(
                f"Created Free Agents club '{free_agents_club_name}' for tournament {tournament.tournament_id}",
                self.logging_enabled)
            session.flush() # Get club_ids

            # Generate matches ONLY between PLAYABLE clubs
            playable_club_ids = [club.club_id for club in generated_playable_clubs]
            if len(playable_club_ids) >= 2:  # Check if there are enough playable clubs for matches
                matches = self._generate_round_robin_matches(playable_club_ids, tournament)
                for m in matches:
                    session.add(m)
            else:
                log_to_screen(
                    f"Not enough playable clubs ({len(playable_club_ids)}) to generate matches for tournament {tournament.tournament_id}.",
                    self.logging_enabled)

            session.commit()
            log_to_screen(f"Tournament '{name}' (ID: {tournament.tournament_id}) created with {num_clubs} playable slots and a Free Agents pool by user {creator_id}.",
                self.logging_enabled)
            return tournament # Return the SQLAlchemy object

        except Exception as e:
            session.rollback() # Rollback on any error
            log_to_screen(f"Error creating tournament '{name}': {e}", self.logging_enabled)
            raise # Re-raise the exception
        finally:
            session.close()

    def create_tournament_club(
            self,
            tournament_id: int,
            original_club_id: int,
            user_id: int | None = None,
    ) -> TournamentClub:
        """
        Fills an empty TournamentClub slot OR assigns a user to an existing AI slot
        in a tournament with a real club. Copies over tactics, training, and players.

        :param tournament_id: The tournament to join
        :param original_club_id: The original club to base this club on
        :param user_id: If provided, this will be a user-controlled club
        :return: The created/updated TournamentClub object
        :raises ValueError: If no slots available, original club invalid, or club already taken by *another* user/assigned AI.
        """
        # Use a session specific to this operation for thread safety
        session = SessionLocal()
        try:
            # Check if this original club is already assigned in this tournament
            existing_assignment = session.query(TournamentClub).filter_by(
                tournament_id=tournament_id,
                original_club_id=original_club_id
            ).first()
            if existing_assignment:
                 # If it exists and is assigned to someone else (or AI and user wants it) -> Error
                 if existing_assignment.user_id != user_id and existing_assignment.user_id is not None:
                      raise ValueError(f"Club {original_club_id} is already managed by another user in this tournament.")
                 elif existing_assignment.user_id is None and user_id is not None:
                     raise ValueError(f"Club {original_club_id} is currently assigned to AI in this tournament.")
                 elif existing_assignment.user_id == user_id:

                      raise ValueError("User already manages this club in the tournament.")


            # Find an available slot (unassigned original_club_id)
            club_slot = session.query(TournamentClub).filter(
                    TournamentClub.tournament_id == tournament_id,
                    TournamentClub.original_club_id.is_(None)
                ).order_by(TournamentClub.club_id).first() # Ensure consistent slot filling

            if not club_slot:
                # Check if the tournament is actually full
                tournament = session.query(Tournament).filter_by(tournament_id=tournament_id).first()
                if tournament:
                    filled_slots = session.query(TournamentClub).filter(
                        TournamentClub.tournament_id == tournament_id,
                        TournamentClub.original_club_id.isnot(None)
                    ).count()
                    if filled_slots >= tournament.number_of_clubs:
                        raise ValueError("No available club slots in this tournament (Tournament is full).")
                # If not full but no empty slot found, something is wrong
                raise ValueError("Inconsistency: Could not find an empty club slot.")

            original_club = session.query(OriginalClub).options(
                joinedload(OriginalClub.default_tactics),  # Eager load tactics/training
                joinedload(OriginalClub.default_training)
            ).filter_by(club_id=original_club_id).first()
            if not original_club:
                raise ValueError(f"Original club ID {original_club_id} does not exist.")

            # Check again if the original club ID was somehow assigned while user was selecting
            # This is a race condition check.
            already_assigned = session.query(TournamentClub).filter_by(
                tournament_id=tournament_id, original_club_id=original_club_id
            ).count() > 0
            if already_assigned:
                raise ValueError(f"Club {original_club.club_name} was assigned just now. Please choose another.")

            # --- Copy Tactics ---
            orig_tactics = original_club.default_tactics
            if not orig_tactics: raise ValueError("Original club is missing default tactics.")  # Should not happen
            tactics = ClubTactics(
                formation=orig_tactics.formation,
                play_style=orig_tactics.play_style,
                # Starting players/subs/roles filled after player ID mapping
            )
            session.add(tactics)
            session.flush()

            # --- Copy Training ---
            orig_training = original_club.default_training
            if not orig_training: raise ValueError("Original club is missing default training.")  # Should not happen
            training = ClubTraining(
                focus_area=orig_training.focus_area,
                intensity=orig_training.intensity
            )
            session.add(training)
            session.flush()

            # --- Update the Club Slot ---
            club_slot.original_club_id = original_club.club_id
            club_slot.user_id = user_id
            club_slot.club_name = original_club.club_name
            club_slot.is_ai_controlled = user_id is None
            club_slot.tactic_id = tactics.tactic_id
            club_slot.training_id = training.training_id
            club_slot.budget = original_club.default_budget
            # Reset stats
            club_slot.wins = 0
            club_slot.draws = 0
            club_slot.losses = 0
            club_slot.goals_scored = 0
            club_slot.goals_conceded = 0
            club_slot.points = 0

            # --- Copy Players and Calculate Value ---
            id_map = {}  # original_player_id -> tournament_player_id
            original_players = session.query(OriginalPlayer).filter_by(club_id=original_club.club_id).all()
            for p in original_players:
                # Calculate initial value using the helper function
                initial_value = calculate_player_value(p)

                tp = TournamentPlayer(
                    club_id=club_slot.club_id, name=p.name, nation=p.nation, team_name=club_slot.club_name,
                    position=p.position, alternative_positions=p.alternative_positions or "-",
                    preferred_foot=p.preferred_foot, height=p.height, weight=p.weight, age=p.age,
                    overall_rating=p.overall_rating, pace=p.pac, shooting=p.sho, passing=p.pas,
                    dribbling=p.dri, defense=p.defense, physical=p.phy, acceleration=p.acceleration,
                    sprint_speed=p.sprint_speed, positioning=p.positioning, finishing=p.finishing,
                    shot_power=p.shot_power, long_shots=p.long_shots, volleys=p.volleys, penalties=p.penalties,
                    vision=p.vision, crossing=p.crossing, free_kick_accuracy=p.free_kick_accuracy,
                    short_passing=p.short_passing, long_passing=p.long_passing, curve=p.curve, agility=p.agility,
                    balance=p.balance, reactions=p.reactions, ball_control=p.ball_control, composure=p.composure,
                    interceptions=p.interceptions, heading_accuracy=p.heading_accuracy, def_awareness=p.def_awareness,
                    standing_tackle=p.standing_tackle, sliding_tackle=p.sliding_tackle, jumping=p.jumping,
                    stamina=p.stamina, strength=p.strength, aggression=p.aggression, weak_foot=p.weak_foot,
                    skill_moves=p.skill_moves, play_style=p.play_style or "-", player_url=p.profile_url,
                    gk_diving=p.gk_diving, gk_handling=p.gk_handling, gk_kicking=p.gk_kicking,
                    gk_positioning=p.gk_positioning, gk_reflexes=p.gk_reflexes,
                    # --- Set Initial Value and Reset Status ---
                    value=initial_value,  # Assign calculated value
                    is_injured=False, injury_rounds=0, is_suspended=False, suspended_rounds=0,
                    yellow_card_count=0, has_yellow_card=False,
                    goals_scored=0, assists_given=0, received_yellow_cards=0, received_red_cards=0,
                    clean_sheets=0, matches_played=0, avg_rating=0.0, motm_count=0, growth=0,
                    fitness=100, form=50
                )
                session.add(tp)
                session.flush()
                id_map[p.player_id] = tp.player_id

            # --- Translate Tactics Player IDs ---
            new_starting_lineup_for_tournament_club = []  # Will be list of {"POS": tournament_player_id_or_none}
            try:
                # Load the list of dicts (e.g., [{"GK": 101}, {"RB": 102}])
                original_club_lineup_list_of_dicts = json.loads(orig_tactics.starting_players or "[]")
                for slot_dict in original_club_lineup_list_of_dicts:  # slot_dict is e.g. {"GK": 101}
                    if isinstance(slot_dict, dict) and len(slot_dict) == 1:
                        pos_name, original_player_id_in_slot = list(slot_dict.items())[0]

                        tournament_player_id_for_slot = None
                        if original_player_id_in_slot is not None:
                            tournament_player_id_for_slot = id_map.get(original_player_id_in_slot)
                            if tournament_player_id_for_slot is None:
                                print(
                                    f"Warning: Could not map original_player_id {original_player_id_in_slot} to tournament_player_id for pos {pos_name} in club {club_slot.club_name}")

                        new_starting_lineup_for_tournament_club.append({pos_name: tournament_player_id_for_slot})
                    else:
                        # Should not happen if original tactics are well-formed
                        print(f"Warning: Malformed slot_dict in original_tactics.starting_players: {slot_dict}")

            except (json.JSONDecodeError, TypeError) as e:
                print(
                    f"Warning: Could not parse original_club_lineup_list_of_dicts for club {club_slot.club_name}: {e}. JSON: {orig_tactics.starting_players}")
                # Fallback: create empty slots based on formation template if parsing fails
                from common.constants import FORMATION_TEMPLATES
                formation_str = tactics.formation.value  # TournamentClub's new tactics formation
                if formation_str in FORMATION_TEMPLATES:
                    for pos_name_in_template in FORMATION_TEMPLATES[formation_str]:
                        new_starting_lineup_for_tournament_club.append({pos_name_in_template: None})

            new_substitute_ids_for_tournament_club = []
            try:
                original_club_substitute_ids = json.loads(orig_tactics.substitutes or "[]")
                for original_sub_id in original_club_substitute_ids:
                    tournament_sub_id = id_map.get(original_sub_id)
                    if tournament_sub_id is not None:
                        new_substitute_ids_for_tournament_club.append(tournament_sub_id)
                    # Else: original sub ID couldn't be mapped (player might not exist in `id_map` if they weren't copied)
            except (json.JSONDecodeError, TypeError) as e:
                print(
                    f"Warning: Could not parse original_club_substitute_ids for club {club_slot.club_name}: {e}. JSON: {orig_tactics.substitutes}")

            tactics.starting_players = json.dumps(new_starting_lineup_for_tournament_club)
            tactics.substitutes = json.dumps(new_substitute_ids_for_tournament_club)

            # Translate specialist IDs
            tactics.captain_id = id_map.get(orig_tactics.captain_id)
            tactics.free_kick_taker_id = id_map.get(orig_tactics.free_kick_taker_id)
            tactics.penalty_taker_id = id_map.get(orig_tactics.penalty_taker_id)
            tactics.corner_taker_id = id_map.get(orig_tactics.corner_taker_id)

            session.commit()
            log_to_screen(f"Assigned original club {original_club.club_name} (ID: {original_club_id}) to tournament club {club_slot.club_id} for user {user_id} in tournament {tournament_id}",
                self.logging_enabled)
            return club_slot

        except Exception as e:
            session.rollback()
            log_to_screen(f"Error in create_tournament_club: {e}", self.logging_enabled)
            import traceback
            traceback.print_exc()  # Log full traceback on server for debugging
            raise  # Re-raise the caught exception

        finally:
            session.close()

    def _generate_round_robin_matches(self, club_ids: list[int], tournament) -> list[TournamentMatch]:
        """
        Generates all match records for a round-robin tournament where each club plays each other once.
        Uses greedy pairing to create fair, non-overlapping rounds.

        :param club_ids: List of TournamentClub IDs
        :param tournament: Tournament instance (used for timing)
        :return: List of TournamentMatch objects (not yet committed)
        """
        if len(club_ids) < 2:
            raise ValueError("At least two clubs are required to generate a fixture.")

        random.shuffle(club_ids)
        match_pairs = list(combinations(club_ids, 2))

        rounds: list[list[tuple[int, int]]] = []

        while match_pairs:
            round_matches = []
            used_teams = set()
            for match in match_pairs[:]:
                h, a = match
                if h not in used_teams and a not in used_teams:
                    round_matches.append((h, a))
                    used_teams.update((h, a))
                    match_pairs.remove(match)
            rounds.append(round_matches)

        matches: list[TournamentMatch] = []
        for round_number, match_list in enumerate(rounds, start=1):
            for home_id, away_id in match_list:
                match_time = tournament.start_time + timedelta(
                    seconds=(round_number - 1) * tournament.round_simulation_interval)
                matches.append(TournamentMatch(
                    tournament_id=tournament.tournament_id,
                    round_number=round_number,
                    match_time=match_time,
                    home_club_id=home_id,
                    away_club_id=away_id,
                    is_simulated=False
                ))

        return matches

    def generate_default_lineup(self, club_name: str, formation: str) -> tuple[list[dict], list[int]]:
        """
        Generates a realistic starting lineup and substitutes for a club based on the given formation.
        Output lineup as a list of {position, player_id} objects to support repeated positions.

        :param club_name: Name of the club
        :param formation: Formation string as defined in FORMATION_TEMPLATES
        :return: (starting_lineup, substitutes)
        """

        template = FORMATION_TEMPLATES[formation]
        selected_ids: set[int] = set()
        lineup: list[dict] = []

        # Get players from database
        players = (
            self.session.query(OriginalPlayer)
            .filter(OriginalPlayer.team_name == club_name)
            .all()
        )

        players_data = []
        for p_idx, p_obj in enumerate(players):
            # Defensive check for p_obj.position
            player_main_pos = ""
            if isinstance(p_obj.position, str):
                player_main_pos = p_obj.position
            else:
                print( f"WARNING DataManager.generate_default_lineup for {club_name}: Player {p_obj.name} (ID: {p_obj.player_id}, CSV index ~{p_idx}) has non-string main position: {p_obj.position} (type: {type(p_obj.position)}). Using empty string.")

            alt_pos_str = p_obj.alternative_positions if isinstance(p_obj.alternative_positions, str) else ""
            if not alt_pos_str or alt_pos_str == '-':  # Handle '-' as empty
                alt_pos_list = []
            else:
                alt_pos_list = [ap.strip() for ap in alt_pos_str.split(',') if ap.strip()]

            players_data.append({
                "player_id": p_obj.player_id,
                "position": player_main_pos,  # Use the validated/defaulted string
                "alt_positions": alt_pos_list,  # Already a list of strings
                "ovr": p_obj.overall_rating
            })


        for pos in template:
            # 1. Try exact match
            exact = [
                p for p in players_data
                if isinstance(p["position"], str) and p["position"].upper() == pos.upper()
                and p["player_id"] not in selected_ids
            ]
            # 2. Try alternative match
            if not exact:
                exact = [
                    p for p in players_data
                    if pos.upper() in [alt_p.upper() for alt_p in p["alt_positions"]] # Iterate and uppercase alt_p
                    and p["player_id"] not in selected_ids
                ]
            # 3. Fallback: best available
            if not exact:
                exact = [p for p in players_data if p["player_id"] not in selected_ids]

            best_player_for_slot_id = None
            if exact:
                best_player_obj = sorted(exact, key=lambda p_obj: p_obj["ovr"], reverse=True)[0]
                selected_ids.add(best_player_obj["player_id"])
                best_player_for_slot_id = best_player_obj["player_id"]

            lineup.append({pos: best_player_for_slot_id})

        # Substitutes = 7 best not in lineup
        substitutes = sorted(
            [p for p in players_data if p["player_id"] not in selected_ids],
            key=lambda p: p["ovr"],
            reverse=True
        )[:7]
        substitute_ids = [p["player_id"] for p in substitutes]


        return lineup, substitute_ids



    def get_players_by_team_name(self, team_name: Optional[str] = None, club_id: Optional[int] = None) -> List[OriginalPlayer]:
        """
        Retrieves all players associated with a given club_id or team_name (case-insensitive).
        If both are provided, club_id takes precedence.

        :param team_name: The name of the team (case-insensitive).
        :param club_id: The club ID.
        :return: List of OriginalPlayer instances.
        :raises ValueError: If neither club_id nor team_name is valid or found.
        :raises RuntimeError: If database query fails.
        """
        try:
            query = self.session.query(OriginalPlayer)

            if club_id is not None:
                # Validate club_id
                club = self.session.query(OriginalClub).filter_by(club_id=club_id).first()
                if not club:
                    raise ValueError(f"No team found with club_id={club_id}")
                query = query.filter(OriginalPlayer.club_id == club_id)
                label = f"club_id={club_id}"

            elif team_name:
                # Validate team_name case-insensitively
                club = (
                    self.session.query(OriginalClub)
                    .filter(func.lower(OriginalClub.club_name) == team_name.lower())
                    .first()
                )
                if not club:
                    raise ValueError(f"No team found with name '{team_name}'")

                query = query.filter(func.lower(OriginalPlayer.team_name) == team_name.lower())
                label = f"team_name='{team_name}'"

            else:
                raise ValueError("You must provide either a team_name or a club_id.")

            players = query.all()
            log_to_screen(f"Found {len(players)} player(s) for {label}.", self.logging_enabled)
            return players

        except SQLAlchemyError as e:
            raise RuntimeError(f"Database error while retrieving players: {e}")

    def get_match_simulation_data(self, match_id: int) -> MatchSimulationData:
        """
        Loads all the data required to simulate a match: tournament, clubs, tactics, training, and players.
        """
        match = self.session.query(TournamentMatch).options(
            joinedload(TournamentMatch.tournament),
            joinedload(TournamentMatch.home_club).joinedload(TournamentClub.tactics),
            joinedload(TournamentMatch.home_club).joinedload(TournamentClub.training),
            joinedload(TournamentMatch.away_club).joinedload(TournamentClub.tactics),
            joinedload(TournamentMatch.away_club).joinedload(TournamentClub.training),
        ).filter_by(match_id=match_id).one()

        tournament = match.tournament
        home_club = match.home_club
        away_club = match.away_club
        home_tactics = home_club.tactics
        away_tactics = away_club.tactics
        home_training = home_club.training
        away_training = away_club.training

        def extract_player_ids(tactics_obj: ClubTactics) -> set[int]:
            """
            Extracts all unique, non-None player IDs from the starting lineup and substitutes
            of a ClubTactics object.
            """
            ids = set()

            # Parse starting_players (list of {position: player_id_or_None})
            try:
                # Ensure "[]" as default if starting_players is None or empty string
                starters_list_of_dicts = json.loads(tactics_obj.starting_players or "[]")
                for slot_dict in starters_list_of_dicts:  # slot_dict is e.g. {"GK": 123} or {"CB": None}
                    if isinstance(slot_dict, dict) and len(slot_dict) == 1:
                        # player_id_in_slot can be an int or None
                        player_id_in_slot = list(slot_dict.values())[0]
                        if player_id_in_slot is not None:  # Only add actual player IDs
                            ids.add(player_id_in_slot)
            except (TypeError, json.JSONDecodeError) as e:
                log_to_screen(
                    f"Error parsing starting_players JSON ('{tactics_obj.starting_players}') for tactics {tactics_obj.tactic_id}: {e}",
                    self.logging_enabled)

            # Parse substitutes (list of player_ids, potentially including None if malformed, though unlikely)
            try:
                # Ensure "[]" as default if substitutes is None or empty string
                subs_list = json.loads(tactics_obj.substitutes or "[]")
                if isinstance(subs_list, list):
                    for player_id in subs_list:
                        if player_id is not None:  # Ensure substitutes are actual IDs
                            ids.add(player_id)
            except (TypeError, json.JSONDecodeError) as e:
                log_to_screen(
                    f"Error parsing substitutes JSON ('{tactics_obj.substitutes}') for tactics {tactics_obj.tactic_id}: {e}",
                    self.logging_enabled)

            return ids



        player_ids = extract_player_ids(home_tactics) | extract_player_ids(away_tactics)

        all_players = self.session.query(TournamentPlayer).filter(
            TournamentPlayer.player_id.in_(player_ids)
        ).all()

        return MatchSimulationData(
            match_id=match.match_id,
            home_club=home_club,
            away_club=away_club,
            tournament=tournament,
            round_number=match.round_number,
            home_tactics=home_tactics,
            away_tactics=away_tactics,
            home_training=home_training,
            away_training=away_training,
            all_players=all_players,
        )

    def perform_substitution(self, tactics_id: int, player_out_id: int, player_in_id: int) -> None:
        """
        Performs a substitution by replacing player_out_id with player_in_id in the starting lineup
        and removing player_in_id from the substitutes list.
        player_out_id becomes a reserve (not added back to subs list).
        """
        session = SessionLocal()  # Use local session
        try:
            tactics = session.query(ClubTactics).filter_by(tactic_id=tactics_id).first()
            if not tactics:
                raise ValueError(f"ClubTactics ID {tactics_id} not found.")

            try:
                starting_list_of_dicts = json.loads(tactics.starting_players or "[]")
                substitutes_ids_list = json.loads(tactics.substitutes or "[]")
                if not isinstance(substitutes_ids_list, list): substitutes_ids_list = []
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON format in tactics for substitution.")

            # Replace player_out_id with player_in_id in starters
            found_in_starters = False
            for i, slot_dict in enumerate(starting_list_of_dicts):
                current_pos, current_pid_in_slot = list(slot_dict.items())[0]
                if current_pid_in_slot == player_out_id:
                    starting_list_of_dicts[i] = {current_pos: player_in_id}
                    found_in_starters = True
                    break

            if not found_in_starters:
                # This could happen if the red-carded player was already subbed off for tactical reasons,
                # then gets a retrospective red card somehow (unlikely in this sim).
                # Or if player_out_id was incorrect.
                log_to_screen(
                    f"Warning: Player {player_out_id} not found in starting lineup for substitution in tactics {tactics_id}.",
                    self.logging_enabled)

            # Remove player_in_id from substitutes
            if player_in_id in substitutes_ids_list:
                substitutes_ids_list.remove(player_in_id)
            else:
                # This means player_in_id was not on the bench - e.g. an error or they were a reserve brought on.
                # This shouldn't happen if _ensure_valid_lineup correctly sources subs.
                log_to_screen(
                    f"Warning: Player {player_in_id} (subbing in) not found in substitutes list for tactics {tactics_id}.",
                    self.logging_enabled)


            # Update specialist roles if player_out_id held one
            roles_updated = False
            if tactics.captain_id == player_out_id:
                tactics.captain_id = player_in_id
                roles_updated = True
            if tactics.free_kick_taker_id == player_out_id:
                tactics.free_kick_taker_id = player_in_id
                roles_updated = True
            if tactics.penalty_taker_id == player_out_id:
                tactics.penalty_taker_id = player_in_id
                roles_updated = True
            if tactics.corner_taker_id == player_out_id:
                tactics.corner_taker_id = player_in_id
                roles_updated = True

            tactics.starting_players = json.dumps(starting_list_of_dicts)
            tactics.substitutes = json.dumps(substitutes_ids_list[:7])  # Cap subs list

            session.commit()
            log_to_screen(
                f"Substitution processed: {player_out_id} -> {player_in_id} in tactics #{tactics_id}. Roles updated: {roles_updated}",
                self.logging_enabled)
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error in perform_substitution for TacticID {tactics_id}: {e}", self.logging_enabled)
            raise
        finally:
            session.close()

    def mark_player_injured(self, player_id: int, injury_rounds: int) -> None:
        """
        Flags a tournament player as injured and sets the number of rounds they will miss.

        :param player_id: The ID of the player to mark as injured.
        :param injury_rounds: Number of upcoming rounds the player will be unavailable.
        """

        player = self.session.query(TournamentPlayer).filter_by(player_id=player_id).first()
        if not player:
            raise ValueError(f"TournamentPlayer ID {player_id} not found.")

        player.is_injured = True
        player.injury_rounds = injury_rounds

        self.session.commit()
        log_to_screen(f"Player #{player_id} marked as injured for {injury_rounds} rounds.")

    def apply_yellow_card(self, player_id: int) -> None:
        """
        Applies a yellow card to a tournament player.
        You can later expand this if you want two yellows to become a red.
        """

        player = self.session.query(TournamentPlayer).filter_by(player_id=player_id).first()
        if not player:
            raise ValueError(f"TournamentPlayer {player_id} not found")

        player.has_yellow_card = True
        player.yellow_card_count += 1

        self.session.commit()
        log_to_screen(f"Yellow card applied to player {player.name} (ID {player_id})")

    def apply_red_card(self, player_id: int, tactics_id: int) -> None:
        """
        Applies a red card to a player: marks them as suspended,
        and removes them from the starting eleven in the ClubTactics.
        The player is NOT added to the substitutes list.
        """
        session = SessionLocal()
        try:
            # Mark the player as suspended
            player = session.query(TournamentPlayer).filter_by(player_id=player_id).first()
            if not player:
                raise ValueError(f"TournamentPlayer {player_id} not found for red card.")

            player.is_suspended = True
            player.suspended_rounds = random.randint(1, 3)  # Example: 1-3 match ban
            player.received_red_cards = (player.received_red_cards or 0) + 1

            # Update tactics to remove the player from the starting eleven
            tactics = session.query(ClubTactics).filter_by(tactic_id=tactics_id).first()
            if not tactics:
                raise ValueError(f"ClubTactics {tactics_id} not found for red card processing.")

            try:
                starting_list_of_dicts = json.loads(tactics.starting_players or "[]")
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in starting_players for tactics {tactics_id}")

            found_and_removed = False
            new_starting_list = []
            for slot_dict in starting_list_of_dicts:
                current_pos, current_pid_in_slot = list(slot_dict.items())[0]
                if current_pid_in_slot == player_id:
                    new_starting_list.append({current_pos: None})  # Empty the slot
                    found_and_removed = True
                    log_to_screen(
                        f"Player {player.name} (ID: {player_id}) removed from starting XI (slot {current_pos}) due to red card in tactics {tactics_id}.",
                        self.logging_enabled)
                else:
                    new_starting_list.append(slot_dict)

            if found_and_removed:
                tactics.starting_players = json.dumps(new_starting_list)
                # DO NOT add the red-carded player to substitutes. They are out.

                # Clear specialist roles if the red-carded player held them
                if tactics.captain_id == player_id: tactics.captain_id = None
                if tactics.free_kick_taker_id == player_id: tactics.free_kick_taker_id = None
                if tactics.penalty_taker_id == player_id: tactics.penalty_taker_id = None
                if tactics.corner_taker_id == player_id: tactics.corner_taker_id = None

            session.commit()
            log_to_screen(
                f"Red card applied to player {player.name} (ID {player_id}). Suspended for {player.suspended_rounds} rounds.",
                self.logging_enabled)
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error applying red card for PlayerID {player_id}, TacticID {tactics_id}: {e}",
                          self.logging_enabled)
            raise
        finally:
            session.close()

    def save_match_result(
            self,
            match_id: int,
            home_goals: int,
            away_goals: int,
            events: list[dict]
    ) -> None:
        """
        Saves the result of a match including goals and all associated match events.

        :param match_id: ID of the match being saved
        :param home_goals: Final home team goal count
        :param away_goals: Final away team goal count
        :param events: List of match events as dictionaries
        """

        session = SessionLocal()  # Use a local session for this entire operation
        try:
            match = session.query(TournamentMatch).filter_by(match_id=match_id).first()
            if not match:
                log_to_screen(f"TournamentMatch {match_id} not found for saving result.", self.logging_enabled)
                raise ValueError(f"TournamentMatch {match_id} not found")

            match.home_goals = home_goals
            match.away_goals = away_goals
            # match.is_simulated is set by the scheduler after calling simulate

            # Clear old events if any
            session.query(TournamentMatchEvent).filter_by(match_id=match_id).delete(synchronize_session=False)

            # Insert new events
            for event_data in events:
                new_event = TournamentMatchEvent(
                    match_id=match_id,
                    minute=event_data["minute"],
                    event_type=MatchEventTypeEnum(event_data["event_type"]),
                    description=event_data["description"],
                    club_id=event_data["club_id"],
                    player_id=event_data["player_id"],
                )
                session.add(new_event)

            # --- Update Club Standings ---
            home_club = session.query(TournamentClub).filter_by(club_id=match.home_club_id).first()
            away_club = session.query(TournamentClub).filter_by(club_id=match.away_club_id).first()

            if not home_club or not away_club:
                log_to_screen(f"Error: Could not find home or away club for match {match_id} to update standings.",
                              self.logging_enabled)
                # Decide if this should raise an error or just log
            else:
                home_club.goals_scored = (home_club.goals_scored or 0) + home_goals
                home_club.goals_conceded = (home_club.goals_conceded or 0) + away_goals

                away_club.goals_scored = (away_club.goals_scored or 0) + away_goals
                away_club.goals_conceded = (away_club.goals_conceded or 0) + home_goals

                if home_goals > away_goals:  # Home win
                    home_club.wins = (home_club.wins or 0) + 1
                    home_club.points = (home_club.points or 0) + 3
                    away_club.losses = (away_club.losses or 0) + 1
                elif away_goals > home_goals:  # Away win
                    away_club.wins = (away_club.wins or 0) + 1
                    away_club.points = (away_club.points or 0) + 3
                    home_club.losses = (home_club.losses or 0) + 1
                else:  # Draw
                    home_club.draws = (home_club.draws or 0) + 1
                    home_club.points = (home_club.points or 0) + 1
                    away_club.draws = (away_club.draws or 0) + 1
                    away_club.points = (away_club.points or 0) + 1

                session.add(home_club)
                session.add(away_club)
                log_to_screen(
                    f"Standings updated for match {match_id}: Home Club {home_club.club_id}, Away Club {away_club.club_id}",
                    self.logging_enabled)

            session.commit()
            log_to_screen(
                f"Match result saved for match {match_id}: {home_goals}-{away_goals}, {len(events)} events recorded.",
                self.logging_enabled
            )
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error saving match result for match ID {match_id}: {e}", self.logging_enabled)
            import traceback
            traceback.print_exc()
            # Re-raise or handle as appropriate for the calling context (e.g., scheduler)
            raise
        finally:
            session.close()

    def regenerate_lineup_for_club(self, club_id: int, new_formation: FormationEnum) -> tuple[
        str, str, dict[str, int | None]]:
        """
        Generates a new default starting lineup, substitutes, and specialists
        for a TournamentClub based on its current players and a new formation.

        Args:
            club_id: The ID of the TournamentClub.
            new_formation: The FormationEnum for the new formation.

        Returns:
            A tuple containing:
            (new_starting_players_json, new_substitutes_json, new_specialists_dict)
            The specialists dict maps role names ('captain_id', etc.) to player IDs or None.
        """
        session = SessionLocal()  # Use a local session
        try:
            players = session.query(TournamentPlayer).filter(
                TournamentPlayer.club_id == club_id
            ).all()

            if not players:
                print(f"Warning: No players found for club {club_id} during lineup regeneration.")
                return "[]", "[]", {}  # Return empty lists/dict

            formation_str = new_formation.value
            if formation_str not in FORMATION_TEMPLATES:
                raise ValueError(f"Invalid formation string '{formation_str}' provided.")

            template = FORMATION_TEMPLATES[formation_str]
            selected_ids: set[int] = set()
            new_lineup_list_of_dicts: list[dict] = []

            # Prepare player data structure similar to generate_default_lineup
            players_data = []
            for p_obj in players:
                alt_pos_str = p_obj.alternative_positions if isinstance(p_obj.alternative_positions, str) else ""
                alt_pos_list = [ap.strip().upper() for ap in alt_pos_str.split(',') if
                                ap.strip()] if alt_pos_str != '-' else []

                players_data.append({
                    "player_id": p_obj.player_id,
                    "position": p_obj.position.upper() if isinstance(p_obj.position, str) else "",
                    "alt_positions": alt_pos_list,
                    "ovr": p_obj.overall_rating,
                    # Include stats needed for specialist selection
                    "age": p_obj.age,
                    "free_kick_accuracy": p_obj.free_kick_accuracy or 0,
                    "penalties": p_obj.penalties or 0,
                    "crossing": p_obj.crossing or 0,
                })

            # --- Generate Starting Lineup ---
            for pos in template:
                pos_upper = pos.upper()
                # Prioritize exact match, then alternative, then best available
                candidates = sorted(
                    [p for p in players_data if p["player_id"] not in selected_ids],
                    key=lambda p: (
                        2 if p["position"] == pos_upper else 1 if pos_upper in p["alt_positions"] else 0,
                        # Suitability score
                        p["ovr"]  # Then by overall rating
                    ),
                    reverse=True  # Higher suitability/OVR first
                )

                best_player_for_slot_id = None
                if candidates:
                    best_player_obj = candidates[0]
                    selected_ids.add(best_player_obj["player_id"])
                    best_player_for_slot_id = best_player_obj["player_id"]

                new_lineup_list_of_dicts.append({pos: best_player_for_slot_id})

            new_starting_players_json = json.dumps(new_lineup_list_of_dicts)

            # --- Generate Substitutes ---
            subs_candidates = sorted(
                [p for p in players_data if p["player_id"] not in selected_ids],
                key=lambda p: p["ovr"],
                reverse=True
            )
            new_substitute_ids = [p["player_id"] for p in subs_candidates[:7]]  # Max 7 subs
            new_substitutes_json = json.dumps(new_substitute_ids)

            # --- Assign Specialists based on the NEW lineup ---
            new_specialists: dict[str, int | None] = {
                "captain_id": None, "free_kick_taker_id": None,
                "penalty_taker_id": None, "corner_taker_id": None
            }
            starting_player_ids_in_new_lineup = selected_ids
            new_starters_data = [p for p in players_data if p["player_id"] in starting_player_ids_in_new_lineup]

            if new_starters_data:
                # Captain = oldest starter
                new_specialists["captain_id"] = max(new_starters_data, key=lambda p: p.get("age", 0))["player_id"]

                # --- Free Kick Taker ---
                fk_candidates = [p for p in new_starters_data if
                                 is_attacker(p.get("position", "")) or is_midfielder(p.get("position", ""))]
                if fk_candidates:
                    new_specialists["free_kick_taker_id"] = \
                    max(fk_candidates, key=lambda p: p.get("free_kick_accuracy", 0))["player_id"]
                else:
                    # Fallback: Best FK accuracy from any starter
                    print(
                        f"WARN (Club {club_id} Lineup Regen): No ATK/MID found for FK taker. Using best overall starter.")
                    new_specialists["free_kick_taker_id"] = \
                    max(new_starters_data, key=lambda p: p.get("free_kick_accuracy", 0))["player_id"]

                # --- Penalty Taker ---
                pen_candidates = [p for p in new_starters_data if is_attacker(p.get("position", ""))]
                if pen_candidates:
                    new_specialists["penalty_taker_id"] = max(pen_candidates, key=lambda p: p.get("penalties", 0))[
                        "player_id"]
                # Fallback 1: Use FK taker if exists
                elif new_specialists["free_kick_taker_id"] is not None:
                    print(f"WARN (Club {club_id} Lineup Regen): No ATK found for PEN taker. Using FK taker.")
                    new_specialists["penalty_taker_id"] = new_specialists["free_kick_taker_id"]
                # Fallback 2: Use best penalty stat from any starter
                else:
                    print(
                        f"WARN (Club {club_id} Lineup Regen): No ATK or FK taker for PEN taker. Using best overall starter.")
                    new_specialists["penalty_taker_id"] = max(new_starters_data, key=lambda p: p.get("penalties", 0))[
                        "player_id"]

                # --- Corner Taker ---
                corner_candidates = [p for p in new_starters_data if is_midfielder(p.get("position", ""))]
                if corner_candidates:
                    new_specialists["corner_taker_id"] = max(corner_candidates, key=lambda p: p.get("crossing", 0))[
                        "player_id"]
                # Fallback 1: Use FK taker if exists
                elif new_specialists["free_kick_taker_id"] is not None:
                    print(f"WARN (Club {club_id} Lineup Regen): No MID found for CORNER taker. Using FK taker.")
                    new_specialists["corner_taker_id"] = new_specialists["free_kick_taker_id"]
                # Fallback 2: Use best crossing stat from any starter
                else:
                    print(
                        f"WARN (Club {club_id} Lineup Regen): No MID or FK taker for CORNER taker. Using best overall starter.")
                    new_specialists["corner_taker_id"] = max(new_starters_data, key=lambda p: p.get("crossing", 0))[
                        "player_id"]

            else:  # No starters at all? Should not happen if players exist.
                print(f"ERROR (Club {club_id} Lineup Regen): No starters found in new lineup data!")

            # Return the calculated specialists along with lineup/subs JSON
            return new_starting_players_json, new_substitutes_json, new_specialists

        except Exception as e:
            print(f"Error regenerating lineup for club {club_id}: {e}")
            import traceback
            traceback.print_exc()
            # Return empty values on error to avoid breaking tactics update
            return "[]", "[]", {}
        finally:
            session.close()  # Close the local session

    def update_player_goal_stat(self, player_id: int):
        """Increments the goals_scored for a given TournamentPlayer."""
        session = SessionLocal()
        try:
            player = session.query(TournamentPlayer).filter_by(player_id=player_id).first()
            if player:
                player.goals_scored = (player.goals_scored or 0) + 1
                session.commit()
                log_to_screen(f"Player ID {player_id} goals updated to {player.goals_scored}.", self.logging_enabled)
            else:
                log_to_screen(f"Warning: Player ID {player_id} not found for goal stat update.", self.logging_enabled)
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error updating goal stat for player {player_id}: {e}", self.logging_enabled)
        finally:
            session.close()

    def update_player_assist_stat(self, player_id: int):
        """Increments the assists_given for a given TournamentPlayer."""
        session = SessionLocal()
        try:
            player = session.query(TournamentPlayer).filter_by(player_id=player_id).first()
            if player:
                player.assists_given = (player.assists_given or 0) + 1
                session.commit()
                log_to_screen(f"Player ID {player_id} assists updated to {player.assists_given}.", self.logging_enabled)
            else:
                log_to_screen(f"Warning: Player ID {player_id} not found for assist stat update.", self.logging_enabled)
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error updating assist stat for player {player_id}: {e}", self.logging_enabled)
        finally:
            session.close()

    def update_player_match_played(self, player_ids: List[int]):
        """Increments matches_played for a list of TournamentPlayer IDs."""
        if not player_ids:
            return
        session = SessionLocal()
        try:
            session.query(TournamentPlayer) \
                .filter(TournamentPlayer.player_id.in_(player_ids)) \
                .update({"matches_played": TournamentPlayer.matches_played + 1}, synchronize_session=False)
            session.commit()
            log_to_screen(f"Updated matches_played for players: {player_ids}", self.logging_enabled)
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error updating matches_played: {e}", self.logging_enabled)
        finally:
            session.close()

    def add_players_to_transfer_list_batch(self, tournament_id: int, listings_to_add: List[Dict[str, Any]]):
        """
        Adds multiple players to the transfer list for a tournament.
        Creates TournamentPlayer records for these players and assigns them to the tournament's Free Agents club.
        Skips players if a listing for their original_player_id equivalent already exists for this tournament.

        Args:
            tournament_id: The ID of the tournament.
            listings_to_add: A list of dictionaries, each with:
                             {'player_id': int (can be OriginalPlayer ID initially),
                              'asking_price': int,
                              'original_player_obj': OriginalPlayer (optional, needed if creating TournamentPlayer)}
        """
        if not listings_to_add:
            return

        session = SessionLocal()
        try:
            added_count = 0
            skipped_count = 0

            # Find the Free Agents club for this tournament
            free_agents_club_name_pattern = f"{FREE_AGENTS_CLUB_NAME_PREFIX} T{tournament_id}"
            free_agents_club = session.query(TournamentClub).filter_by(
                tournament_id=tournament_id,
                club_name=free_agents_club_name_pattern  # Use the specific name pattern
            ).first()

            if not free_agents_club:
                log_to_screen(
                    f"CRITICAL ERROR: Free Agents club not found for tournament {tournament_id}. Cannot list initial players.",
                    self.logging_enabled)
                session.rollback()  # Rollback if free agents club isn't found.
                return

            # Get OriginalPlayer IDs that are ALREADY represented by a TournamentPlayer in a TransferListing for this tournament
            # This requires joining through TournamentPlayer to check original_player_id
            existing_listed_original_player_ids = {
                tp.original_player_id
                for tp in session.query(TournamentPlayer)
                .join(TransferListing, TransferListing.player_id == TournamentPlayer.player_id)
                .filter(
                    TransferListing.tournament_id == tournament_id,
                    TournamentPlayer.original_player_id.isnot(None)  # Ensure we only consider TPs linked to an OP
                ).all()
            }

            log_to_screen(
                f"Tournament {tournament_id}: OriginalPlayer IDs already having a listing: {existing_listed_original_player_ids}",
                self.logging_enabled)

            for item in listings_to_add:
                original_player_id_from_item = item.get('player_id')  # This is the OriginalPlayer ID
                asking_price = item.get('asking_price')
                original_player_obj: Optional[OriginalPlayer] = item.get('original_player_obj')

                if not original_player_id_from_item or not asking_price or asking_price <= 0 or not original_player_obj:
                    log_to_screen(
                        f"Warning: Invalid data for transfer listing batch (missing IDs/price/object): {item}",
                        self.logging_enabled)
                    continue

                # Check if this OriginalPlayer is already effectively listed
                if original_player_id_from_item in existing_listed_original_player_ids:
                    log_to_screen(
                        f"Skipping OriginalPlayer {original_player_id_from_item}: already represented in transfer list for tournament {tournament_id}.",
                        self.logging_enabled)
                    skipped_count += 1
                    continue

                # Create the TournamentPlayer record, assigning to the Free Agents club
                p = original_player_obj
                initial_value = calculate_player_value(p)

                tp = TournamentPlayer(
                    club_id=free_agents_club.club_id,  # Assign to Free Agents club
                    original_player_id=p.player_id,  # Link to the original player
                    name=p.name, nation=p.nation,
                    team_name=free_agents_club.club_name,  # Team name is the Free Agents club name
                    position=p.position, alternative_positions=p.alternative_positions or "-",
                    preferred_foot=p.preferred_foot, height=p.height, weight=p.weight, age=p.age,
                    overall_rating=p.overall_rating, pace=p.pac, shooting=p.sho, passing=p.pas,
                    dribbling=p.dri, defense=p.defense, physical=p.phy, acceleration=p.acceleration,
                    sprint_speed=p.sprint_speed, positioning=p.positioning, finishing=p.finishing,
                    shot_power=p.shot_power, long_shots=p.long_shots, volleys=p.volleys, penalties=p.penalties,
                    vision=p.vision, crossing=p.crossing, free_kick_accuracy=p.free_kick_accuracy,
                    short_passing=p.short_passing, long_passing=p.long_passing, curve=p.curve, agility=p.agility,
                    balance=p.balance, reactions=p.reactions, ball_control=p.ball_control, composure=p.composure,
                    interceptions=p.interceptions, heading_accuracy=p.heading_accuracy, def_awareness=p.def_awareness,
                    standing_tackle=p.standing_tackle, sliding_tackle=p.sliding_tackle, jumping=p.jumping,
                    stamina=p.stamina, strength=p.strength, aggression=p.aggression, weak_foot=p.weak_foot,
                    skill_moves=p.skill_moves, play_style=p.play_style or "-", player_url=p.profile_url,
                    gk_diving=p.gk_diving, gk_handling=p.gk_handling, gk_kicking=p.gk_kicking,
                    gk_positioning=p.gk_positioning, gk_reflexes=p.gk_reflexes,
                    value=initial_value, is_injured=False, injury_rounds=0, is_suspended=False, suspended_rounds=0,
                    yellow_card_count=0, has_yellow_card=False, goals_scored=0, assists_given=0,
                    received_yellow_cards=0,
                    received_red_cards=0, clean_sheets=0, matches_played=0, avg_rating=0.0, motm_count=0, growth=0,
                    fitness=100, form=50
                )
                session.add(tp)
                session.flush()  # Get the new tournament_player_id

                new_listing = TransferListing(
                    tournament_id=tournament_id,
                    player_id=tp.player_id,  # Use the newly created TournamentPlayer ID
                    asking_price=asking_price,
                    status=TransferStatus.LISTED,
                    listed_at=datetime.now(timezone.utc)
                )
                session.add(new_listing)
                existing_listed_original_player_ids.add(
                    original_player_id_from_item)  # Track to avoid duplicates within the same batch
                added_count += 1

            if added_count > 0:
                session.commit()
                log_to_screen(
                    f"Created {added_count} TournamentPlayers (assigned to Free Agents club) and listed them for tournament {tournament_id}. Skipped {skipped_count} duplicates.",
                    self.logging_enabled)
            elif skipped_count > 0 and added_count == 0:
                log_to_screen(
                    f"No new players listed for tournament {tournament_id}. Skipped {skipped_count} duplicates.",
                    self.logging_enabled)
                # No commit needed if nothing was added.

        except Exception as e:
            session.rollback()
            log_to_screen(f"Error during batch transfer listing add for tournament {tournament_id}: {e}",
                          self.logging_enabled)
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def _recalculate_overall(self, player: TournamentPlayer) -> int:
        """
        Recalculates player overall. Ensures OVR doesn't decrease due to training.
        This is a simplified placeholder. A proper formula would be more complex,
        weighting key attributes based on position.
        """

        current_ovr = player.overall_rating

        if player.position == "GK":
            main_stats = [player.gk_diving, player.gk_handling, player.gk_kicking, player.gk_positioning,
                          player.gk_reflexes]
            secondary_stats = [player.reactions, player.jumping, player.strength]
            main_weight = 0.8
            secondary_weight = 0.2
        else:  # Outfield
            core_attrs_values = [player.pace, player.shooting, player.passing, player.dribbling, player.defense,
                                 player.physical]


            calc_stats = [s or 0 for s in
                          [player.pace, player.shooting, player.passing, player.dribbling, player.defense,
                           player.physical]]
            if not calc_stats or sum(calc_stats) == 0:
                return current_ovr  # Avoid division by zero, return current

            rough_new_ovr = int(round(sum(calc_stats) / len(calc_stats)))

            # Ensure OVR doesn't drop due to this rough calc, and doesn't exceed cap
            final_ovr = max(current_ovr, rough_new_ovr)  # Training should not decrease OVR
            final_ovr = min(99, final_ovr)  # Cap at 99
            final_ovr = max(1, final_ovr)  # Min 1

            return final_ovr

        calc_stats = []
        if player.position == "GK":
            calc_stats = [s or 0 for s in [player.gk_diving, player.gk_handling, player.gk_kicking, player.gk_reflexes,
                                           player.gk_positioning]]
        else:
            calc_stats = [s or 0 for s in
                          [player.pace, player.shooting, player.passing, player.dribbling, player.defense,
                           player.physical]]

        if not calc_stats or sum(calc_stats) == 0 or len(calc_stats) == 0:  # Check len(calc_stats) too
            return current_ovr

        rough_recalculated_ovr = int(round(sum(calc_stats) / len(calc_stats)))

        # Ensure OVR does not decrease. If recalc is higher, take it. Otherwise, keep current.
        new_potential_ovr = max(current_ovr, rough_recalculated_ovr)

        # If actual growth occurred (stats increased), and new_potential_ovr is not higher than current_ovr,
        # but still below 99, consider a small +1 increase. This needs a flag from training.
        # For now, this logic is safer:
        return min(99, new_potential_ovr)

    def apply_post_match_training(self, club_id: int):
        """Applies training effects (growth, fitness change) to players of a club."""
        session = SessionLocal()
        try:
            club = session.query(TournamentClub).options(
                joinedload(TournamentClub.training),
                joinedload(TournamentClub.players)  # Load players
            ).filter_by(club_id=club_id).first()

            if not club or not club.training or not club.players:
                log_to_screen(f"Cannot apply training: Club {club_id}, training settings, or players not found.",
                              self.logging_enabled)
                return

            intensity = club.training.intensity
            focus_area = club.training.focus_area

            players_updated = 0
            for player in club.players:
                player_updated = False
                original_ovr = player.overall_rating # Store original OVR

                # --- Fitness Update ---
                old_fitness = player.fitness or 100
                if intensity < 6:  # Recovery (Intensity 1-5)
                    fitness_gain = random.randint(8 - intensity, 20 - intensity * 2)  # Higher gain for lower intensity
                    new_fitness = old_fitness + fitness_gain
                elif intensity > 7:  # Fatigue (Intensity 8-10)
                    fitness_drop = random.randint(intensity - 6, intensity + 2)  # Higher drop for higher intensity
                    new_fitness = old_fitness - fitness_drop
                else:  # Stall/Slight Recovery (Intensity 6-7)
                    new_fitness = old_fitness + random.randint(-1, 4)

                new_fitness = max(30, min(100, new_fitness))  # Clamp fitness 30-100
                if new_fitness != old_fitness:
                    player.fitness = new_fitness
                    player_updated = True

                # --- OVR Growth Attempt ---
                grew_ovr = False
                if player.age < 32 and player.overall_rating < 99:  # Check OVR cap
                    base_growth_chance = (intensity * 1.2) / 100.0
                    if player.age <= 21:
                        age_mod = 1.8
                    else:
                        age_mod = 0.3

                    focus_mod = 1.0

                    final_growth_chance = base_growth_chance * age_mod * focus_mod

                    if random.random() < final_growth_chance:
                        # --- Increase OVR ---
                        player.overall_rating += 1
                        player.growth = (player.growth or 0) + 1  # Track growth points
                        player_updated = True
                        grew_ovr = True
                        log_to_screen(
                            f"Player {player.name} (Age: {player.age}) OVR grew: {original_ovr} -> {player.overall_rating}",
                            self.logging_enabled)

                        # --- Consequential Stat Increase ---
                        # If OVR grew, slightly boost 1-2 relevant stats
                        stats_to_potentially_improve = FOCUS_AREA_STATS.get(focus_area, [])
                        if not stats_to_potentially_improve: stats_to_potentially_improve = FOCUS_AREA_STATS[
                            TrainingFocusEnum.BALANCED]

                        num_stats_to_improve = random.randint(1, 2)
                        chosen_stats = random.sample(stats_to_potentially_improve,
                                                     min(num_stats_to_improve, len(stats_to_potentially_improve)))

                        stats_actually_improved = []
                        for stat_name in chosen_stats:
                            if hasattr(player, stat_name):
                                current_val = getattr(player, stat_name) or 0
                                if current_val < 99:  # Don't increase past 99
                                    setattr(player, stat_name, current_val + 1)
                                    stats_actually_improved.append(stat_name)
                        if stats_actually_improved:
                            log_to_screen(f"    -> Also improved stats: {stats_actually_improved}",
                                          self.logging_enabled)

                if player_updated:
                    players_updated += 1

            if players_updated > 0:
                session.commit()
                log_to_screen(
                    f"Applied training for club {club_id}. Intensity: {intensity}, Focus: {focus_area}. Players updated: {players_updated}",
                    self.logging_enabled)
            else:
                log_to_screen(f"Applied training for club {club_id}. No players updated.", self.logging_enabled)

        except Exception as e:
            session.rollback()
            log_to_screen(f"Error applying training for club {club_id}: {e}", self.logging_enabled)
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def update_player_stats_batch(self, player_stats_updates: dict[int, dict[str, any]]):
        """
        Updates various statistics for multiple players in a single transaction.

        Args:
            player_stats_updates: A dictionary where keys are player_ids and
                                  values are dictionaries of stat_name: new_value.
                                  Example: {
                                      101: {"goals_scored": 5, "matches_played": 10, "is_injured": True, "injury_rounds": 2},
                                      102: {"assists_given": 3, "matches_played": 10}
                                  }
        """
        if not player_stats_updates:
            log_to_screen("Batch player stats update skipped: No updates provided.", self.logging_enabled)
            return

        session = SessionLocal()
        try:
            updated_count = 0
            # Fetch all relevant players in one go for efficiency
            player_ids_to_update = list(player_stats_updates.keys())
            players_to_update = session.query(TournamentPlayer).filter(
                TournamentPlayer.player_id.in_(player_ids_to_update)
            ).all()

            player_map = {p.player_id: p for p in players_to_update}  # Map for quick access

            for player_id, updates in player_stats_updates.items():
                player = player_map.get(player_id)  # Get from map
                if player:
                    log_string_parts = []
                    for stat_name, new_value in updates.items():
                        if hasattr(player, stat_name):
                            setattr(player, stat_name, new_value)
                        else:
                            log_to_screen(
                                f"Warning: Player {player_id} has no attribute '{stat_name}' for batch update.",
                                self.logging_enabled)

                    if log_string_parts:  # Only log if something potentially changed
                        log_to_screen(f"Staged stat updates for Player ID {player_id}: {'; '.join(log_string_parts)}",
                                      self.logging_enabled)
                    updated_count += 1
                else:
                    log_to_screen(f"Warning: Player ID {player_id} not found for batch stat update.",
                                  self.logging_enabled)

            if updated_count > 0:
                session.commit()
                log_to_screen(f"Batch player stats update committed for {updated_count} players.", self.logging_enabled)
            else:
                log_to_screen("Batch player stats update: No players found or no actual changes needed.",
                              self.logging_enabled)

        except Exception as e:
            session.rollback()
            log_to_screen(f"Error during batch player stats update: {e}", self.logging_enabled)
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def list_existing_tournament_players_batch(self, tournament_id: int, listings_info: List[Dict[str, Any]]):
        """
        Adds existing TournamentPlayers to the transfer list.
        Skips players if they are already listed.

        Args:
            tournament_id: The ID of the tournament.
            listings_info: List of dicts, each {'tournament_player_id': int, 'asking_price': int}
        """
        if not listings_info:
            return

        session = SessionLocal()
        try:
            added_count = 0
            skipped_count = 0

            # Get TournamentPlayer IDs already listed
            existing_listed_tp_ids = {
                listing.player_id for listing in session.query(TransferListing.player_id) \
                    .filter_by(tournament_id=tournament_id).all()
            }

            for item in listings_info:
                tournament_player_id = item.get('tournament_player_id')
                asking_price = item.get('asking_price')

                if not tournament_player_id or not asking_price or asking_price <= 0:
                    log_to_screen(f"Warning: Invalid data for listing existing player: {item}", self.logging_enabled)
                    continue

                if tournament_player_id in existing_listed_tp_ids:
                    skipped_count += 1
                    continue

                # Verify the TournamentPlayer exists (optional, but good)
                player_exists = session.query(TournamentPlayer.player_id).filter_by(
                    player_id=tournament_player_id).first()
                if not player_exists:
                    log_to_screen(f"Warning: TournamentPlayer {tournament_player_id} not found for listing.",
                                  self.logging_enabled)
                    skipped_count += 1
                    continue

                new_listing = TransferListing(
                    tournament_id=tournament_id,
                    player_id=tournament_player_id,  # This is the TournamentPlayer.player_id
                    asking_price=asking_price,
                    status=TransferStatus.LISTED,
                    listed_at=datetime.now(timezone.utc)
                )
                session.add(new_listing)
                existing_listed_tp_ids.add(tournament_player_id)
                added_count += 1

            if added_count > 0:
                session.commit()

            if added_count > 0 or skipped_count > 0:
                log_to_screen(
                    f"Post-match transfer listing for T{tournament_id}: Added {added_count}, Skipped {skipped_count} (already listed/invalid).",
                    self.logging_enabled)

        except Exception as e:
            session.rollback()
            log_to_screen(f"Error listing existing tournament players for T{tournament_id}: {e}", self.logging_enabled)
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def update_club_tactics_raw(self, tactic_id: int, new_starters_json: str, new_subs_json: str):
        """
        Directly updates the starting_players and substitutes JSON strings for a tactic.
        Used by the simulator for auto-filling lineups.
        """
        session = SessionLocal()
        try:
            tactic = session.query(ClubTactics).filter_by(tactic_id=tactic_id).first()
            if tactic:
                tactic.starting_players = new_starters_json
                tactic.substitutes = new_subs_json
                session.commit()
                log_to_screen(f"Raw tactics updated for tactic_id {tactic_id}.", self.logging_enabled)
            else:
                log_to_screen(f"Warning: Tactic ID {tactic_id} not found for raw update.", self.logging_enabled)
        except Exception as e:
            session.rollback()
            log_to_screen(f"Error in update_club_tactics_raw for tactic_id {tactic_id}: {e}", self.logging_enabled)
        finally:
            session.close()

    def ensure_valid_squad_composition(self, club_id: int):
        """
        Checks and corrects the starting lineup and substitutes for a club.
        - Fills empty starter slots from best available subs/reserves.
        - Ensures exactly 7 substitutes are present (best available reserves fill gaps, worst subs removed if > 7).
        - Updates the ClubTactics record in the database.
        """
        session = SessionLocal()
        try:
            club = session.query(TournamentClub).options(
                joinedload(TournamentClub.tactics),
                joinedload(TournamentClub.players)  # Need players for selection
            ).filter_by(club_id=club_id).first()

            if not club or not club.tactics or not club.players:
                log_to_screen(f"Cannot validate squad composition: Club {club_id}, tactics, or players not found.",
                              self.logging_enabled)
                return

            tactics = club.tactics
            all_players_map = {p.player_id: p for p in club.players}

            try:
                starters_list_of_dicts = json.loads(tactics.starting_players or "[]")
                substitutes_ids_list = json.loads(tactics.substitutes or "[]")
                if not isinstance(substitutes_ids_list, list): substitutes_ids_list = []
            except (json.JSONDecodeError, TypeError):
                log_to_screen(f"Error parsing tactics JSON for squad validation (Club {club_id}). Rebuilding defaults.",
                              self.logging_enabled)
                # If JSON is corrupt, try regenerating lineup completely
                new_starters_json, new_subs_json, new_specs = self.regenerate_lineup_for_club(club_id,
                                                                                              tactics.formation)
                tactics.starting_players = new_starters_json
                tactics.substitutes = new_subs_json
                # Apply new specs (this might overwrite user choices, consider carefully)
                tactics.captain_id = new_specs.get("captain_id")
                tactics.free_kick_taker_id = new_specs.get("free_kick_taker_id")
                tactics.penalty_taker_id = new_specs.get("penalty_taker_id")
                tactics.corner_taker_id = new_specs.get("corner_taker_id")
                session.commit()
                return  # Regenerated, nothing more to do here

            from common.constants import FORMATION_TEMPLATES  # Local import
            formation_str = tactics.formation.value if tactics.formation else None
            if not formation_str or formation_str not in FORMATION_TEMPLATES:
                log_to_screen(f"Invalid formation for squad validation (Club {club_id}). Cannot proceed.",
                              self.logging_enabled)
                return  # Cannot validate without template

            formation_template = FORMATION_TEMPLATES[formation_str]

            lineup_changed = False

            # --- Ensure starters list matches template length ---
            if len(starters_list_of_dicts) != len(formation_template):
                # Rebuild structure as before
                log_to_screen(f"Fixing lineup length mismatch for Club {club_id}.", self.logging_enabled)
                temp_map = {list(slot.keys())[0].upper(): list(slot.values())[0] for slot in starters_list_of_dicts if
                            isinstance(slot, dict) and len(slot) == 1}
                starters_list_of_dicts = [{template_pos: temp_map.get(template_pos.upper())} for template_pos in
                                          formation_template]
                lineup_changed = True

            current_starter_ids = {list(slot.values())[0] for slot in starters_list_of_dicts if
                                   list(slot.values())[0] is not None}
            current_sub_ids = set(substitutes_ids_list)

            # Get available players (not starting, not injured/suspended)
            available_reserve_pool = []
            for p_id, player in all_players_map.items():
                if p_id not in current_starter_ids and p_id not in current_sub_ids:
                    if not player.is_injured and not player.is_suspended:
                        available_reserve_pool.append(player)

            available_subs_pool = []
            for sub_id in list(substitutes_ids_list):  # Iterate copy for safe removal
                player = all_players_map.get(sub_id)
                if player and not player.is_injured and not player.is_suspended:
                    available_subs_pool.append(player)
                else:  # Remove invalid sub
                    substitutes_ids_list.remove(sub_id)
                    lineup_changed = True

            available_subs_pool.sort(key=lambda p: (p.overall_rating or 0), reverse=True)
            available_reserve_pool.sort(key=lambda p: (p.overall_rating or 0), reverse=True)

            # --- Fill empty/invalid starter slots ---
            for i, slot_dict in enumerate(starters_list_of_dicts):
                slot_position_name = list(slot_dict.keys())[0]
                current_player_id_in_slot = list(slot_dict.values())[0]
                player_in_slot = all_players_map.get(current_player_id_in_slot)

                needs_replacement = False
                if player_in_slot is None or player_in_slot.is_injured or player_in_slot.is_suspended:
                    needs_replacement = True

                if needs_replacement:
                    # Prioritize available subs first, then reserves
                    replacement_pool = available_subs_pool + available_reserve_pool
                    replacement_found = False

                    # Find best fit by position
                    best_replacement = None
                    # Try same position
                    for p in replacement_pool:
                        if p.position.upper() == slot_position_name.upper():
                            best_replacement = p
                            break
                    # Try alt position
                    if not best_replacement:
                        for p in replacement_pool:
                            alt_pos_list = [ap.strip().upper() for ap in (p.alternative_positions or "").split(',') if
                                            ap.strip() and ap.strip() != '-']
                            if slot_position_name.upper() in alt_pos_list:
                                best_replacement = p
                                break
                    # Try highest OVR if no positional match
                    if not best_replacement and replacement_pool:
                        best_replacement = replacement_pool[0]  # Highest OVR available

                    if best_replacement:
                        log_to_screen(f"Club {club_id}: Filling slot {slot_position_name} with {best_replacement.name}",
                                      self.logging_enabled)
                        starters_list_of_dicts[i] = {slot_position_name: best_replacement.player_id}
                        lineup_changed = True
                        # Remove player from whichever pool they came from
                        if best_replacement in available_subs_pool:
                            available_subs_pool.remove(best_replacement)
                        if best_replacement in available_reserve_pool:
                            available_reserve_pool.remove(best_replacement)
                        # Remove from substitutes_ids_list if they were there
                        if best_replacement.player_id in substitutes_ids_list:
                            substitutes_ids_list.remove(best_replacement.player_id)

                        # Add the player previously in the slot (if any) to reserves if they are valid
                        if player_in_slot and not player_in_slot.is_injured and not player_in_slot.is_suspended:
                            if player_in_slot not in available_reserve_pool and player_in_slot.player_id not in substitutes_ids_list:
                                available_reserve_pool.append(player_in_slot)
                                available_reserve_pool.sort(key=lambda p: (p.overall_rating or 0),
                                                            reverse=True)  # Resort reserves

                    else:
                        log_to_screen(f"Club {club_id}: Could not find any replacement for slot {slot_position_name}.",
                                      self.logging_enabled)
                        # Slot remains empty or with invalid player

            # --- Ensure exactly 7 substitutes ---
            target_subs_count = 7
            current_sub_count = len(substitutes_ids_list)

            if current_sub_count < target_subs_count:
                # Need to add subs from reserves
                needed = target_subs_count - current_sub_count
                can_add = min(needed, len(available_reserve_pool))
                log_to_screen(f"Club {club_id}: Subs count {current_sub_count}, adding {can_add} from reserves.",
                              self.logging_enabled)
                for i in range(can_add):
                    player_to_add = available_reserve_pool.pop(0)  # Take best available reserve
                    substitutes_ids_list.append(player_to_add.player_id)
                    lineup_changed = True
            elif current_sub_count > target_subs_count:
                # Need to remove excess subs (remove lowest OVR first)
                to_remove_count = current_sub_count - target_subs_count
                log_to_screen(f"Club {club_id}: Subs count {current_sub_count}, removing lowest {to_remove_count}.",
                              self.logging_enabled)

                # Get subs as player objects to sort by OVR
                current_sub_players = []
                valid_sub_ids_temp = []
                for sub_id in substitutes_ids_list:
                    p = all_players_map.get(sub_id)
                    if p:
                        current_sub_players.append(p)
                        valid_sub_ids_temp.append(sub_id)
                substitutes_ids_list = valid_sub_ids_temp  # Clean list

                current_sub_players.sort(key=lambda p: (p.overall_rating or 0))  # Sort ascending by OVR

                # Remove the lowest OVR players
                ids_to_remove = {p.player_id for p in current_sub_players[:to_remove_count]}
                substitutes_ids_list = [pid for pid in substitutes_ids_list if pid not in ids_to_remove]
                lineup_changed = True

            if lineup_changed:
                tactics.starting_players = json.dumps(starters_list_of_dicts)
                tactics.substitutes = json.dumps(substitutes_ids_list)
                session.commit()
                log_to_screen(f"Squad composition validated and updated for Club {club_id}.", self.logging_enabled)
            else:
                log_to_screen(f"Squad composition validation: No changes needed for Club {club_id}.",
                              self.logging_enabled)

        except Exception as e:
            session.rollback()
            log_to_screen(f"Error validating squad composition for club {club_id}: {e}", self.logging_enabled)
            import traceback
            traceback.print_exc()
        finally:
            session.close()
