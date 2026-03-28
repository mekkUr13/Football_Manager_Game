from server.database.data_manager import DataManager
from common.enums import MatchEventTypeEnum
from typing import List, Literal, Optional
from server.database.models import TournamentClub, ClubTactics, TournamentPlayer
from server.simulation.schemas import ClubSimulationStats, MatchSimulationData
from server.simulation.utils import choose_event_type, avg, get_weighted_injury_duration
from common.constants import ATTACKERS, MIDFIELDERS, DEFENDERS
from common.utilities import log_to_screen
import json
from math import sqrt
import random


EXTRA_TIME_WEIGHTS = {
    0: 0.03,
    1: 0.13,
    2: 0.13,
    3: 0.33,
    4: 0.10,
    5: 0.09,
    6: 0.06,
    7: 0.04,
    8: 0.03,
    9: 0.03,
    10: 0.03,
}

EVENT_THRESHOLD = 0.30  # 30% chance to generate an event


class MatchSimulator:
    """
    MatchSimulator is responsible for simulating a single football match between two tournament clubs.

    This class encapsulates the match flow logic, including:
    - Fetching data via a provided DataManager (clubs, players, training, tactics, etc.)
    - Simulating two halves of gameplay
    - Generating match events such as goals, fouls, injuries
    - Recording the final score and returning or storing the results
    """

    def __init__(self, data_manager: DataManager):
        """
        Initializes the MatchSimulator with a reference to the DataManager.
        This simulator instance can be reused to simulate multiple matches.

        :param data_manager: The central interface to all data operations (read/write).
        """
        self.data_manager = data_manager

        # Internal state (re-initialized before every match simulation)
        self.events: list[dict] = []
        self.home_goals: int = 0
        self.away_goals: int = 0
        self.match_data: MatchSimulationData | None = None
        self.home_stats: ClubSimulationStats | None = None
        self.away_stats: ClubSimulationStats | None = None
        self._player_map: dict | None = None
        self.player_performance_scores: dict[int, float] = {}

    def _compute_club_stats(self) -> None:
        """
        Computes and stores strength metrics for both clubs involved in the match.
        Stores the results in `self.home_stats` and `self.away_stats`.
        """
        # Collect input tuples: (players, target_attr_name)
        teams = [
            (self.match_data.home_tactics.starting_players, "home_stats"),
            (self.match_data.away_tactics.starting_players, "away_stats"),
        ]

        for encoded_eleven, attr_name in teams:  # encoded_eleven is ClubTactics.starting_players JSON string
            atk, mid, deff, ratings, fitness, form = [], [], [], [], [], []

            try:
                # Ensure "[]" as default if encoded_eleven (starting_players string) is None or empty
                parsed_list_of_dicts = json.loads(encoded_eleven or "[]")
            except json.JSONDecodeError:
                # Log or raise a more specific error if needed
                print(f"Error: Invalid starting_eleven JSON for {attr_name}. Data: '{encoded_eleven}'")
                parsed_list_of_dicts = []

            correct_primary = 0
            correct_secondary = 0  # Tracks players in alternative positions correctly

            for slot_dict in parsed_list_of_dicts:  # slot_dict is e.g. {"GK": 101}
                if not (isinstance(slot_dict, dict) and len(slot_dict) == 1):
                    # Log warning for malformed slot and skip it
                    print(f"Warning: Malformed slot encountered in _compute_club_stats for {attr_name}: {slot_dict}")
                    continue

                # Extract position from slot (e.g., "GK") and player ID (e.g., 101 or None)
                # Example: slot_dict = {"GK": 123}
                # position_from_slot will be "GK"
                # player_id_from_slot will be 123 (or None if {"GK": null})
                position_from_slot, player_id_from_slot = list(slot_dict.items())[0]

                player = self._player_map.get(player_id_from_slot)
                if player is None:  # Slot is empty or player ID not found in map
                    continue

                ratings.append(player.overall_rating)
                fitness.append(player.fitness)
                form.append(player.form)

                # Compare the tactical position (position_from_slot) with the player's natural and alternative positions
                player_natural_pos_upper = player.position.upper() if isinstance(player.position, str) else ""
                slot_pos_upper = position_from_slot.upper() if isinstance(position_from_slot, str) else ""

                alt_pos_str = player.alternative_positions if isinstance(player.alternative_positions, str) else ""
                alt_pos_list = [p.strip().upper() for p in alt_pos_str.split(',') if p.strip() and p.strip() != '-']

                if slot_pos_upper == player_natural_pos_upper:
                    correct_primary += 1
                elif slot_pos_upper in alt_pos_list:
                    correct_secondary += 1

                # Categorize for strength calculation using tactical position from slot
                if slot_pos_upper in ATTACKERS:
                    atk.append(player.overall_rating)
                elif slot_pos_upper in MIDFIELDERS:
                    mid.append(player.overall_rating)
                elif slot_pos_upper in DEFENDERS:
                    deff.append(player.overall_rating)

            base_team_strength = avg(ratings)
            fitness = avg(fitness)
            form = avg(form)
            pos_score = (correct_primary + 0.5 * (correct_secondary - correct_primary)) / 11
            atk, mid, deff = avg(atk) if atk else 0, avg(mid) if mid else 0, avg(deff) if deff else 0
            avg_pos = (atk + mid + deff) / 3
            std_dev = sqrt(((atk - avg_pos) ** 2 + (mid - avg_pos) ** 2 + (deff - avg_pos) ** 2) / 3)
            penalty = min(std_dev / 25, 1.0)
            balance_score = max(0.0, (avg_pos / 100) * (1.0 - penalty))

            overall_team_strength = (0.30 * (base_team_strength / 100) +
                                     0.15 * (fitness / 100) +
                                     0.15 * (form / 100) +
                                     0.20 * pos_score +
                                     0.20 * balance_score) * 100

            setattr(self, attr_name, ClubSimulationStats(
                base_team_strength=base_team_strength,
                base_atk_strength=atk,
                base_mid_strength=mid,
                base_def_strength=deff,
                fitness_level=fitness,
                form=form,
                correct_primary_positions=correct_primary,
                correct_secondary_positions=correct_secondary,
                overall_team_strength=overall_team_strength,
            ))

    def simulate(self, match_id: int) -> None:
        """
        Simulates a single match using provided match ID.
        Fetches data from the DataManager, performs simulation,
        and stores the result via DataManager.

       :param match_id: ID of the match to simulate.
        """
        self.match_data = self.data_manager.get_match_simulation_data(match_id)
        self._player_map = {player.player_id: player for player in self.match_data.all_players}

        log_to_screen(f"Validating lineup for Home Club: {self.match_data.home_club.club_name} (ID: {self.match_data.home_club.club_id})",
            True)
        self._ensure_valid_lineup(self.match_data.home_tactics, self.match_data.home_club.club_id)
        log_to_screen(f"Validating lineup for Away Club: {self.match_data.away_club.club_name} (ID: {self.match_data.away_club.club_id})",
            True)
        self._ensure_valid_lineup(self.match_data.away_tactics, self.match_data.away_club.club_id)

        # Internal state for the simulation
        self.events = []
        self.home_goals = 0
        self.away_goals = 0
        self.player_performance_scores = {} # Reset for each match

        self._compute_club_stats()

        self.simulate_half(is_first_half=True)
        self.simulate_half(is_first_half=False)

        players_stats_to_update = {}  # Dict: player_id -> {stat_name: new_value}
        highest_rating_so_far = -1.0
        motm_player_id = None

        # --- Update matches_played for all involved players ---
        player_ids_in_match = set()
        try:
            home_starters_list = json.loads(self.match_data.home_tactics.starting_players or "[]")
            for slot in home_starters_list:
                player_id = list(slot.values())[0]
                if player_id is not None:
                    player_ids_in_match.add(player_id)

            home_subs_list = json.loads(self.match_data.home_tactics.substitutes or "[]")
            for player_id in home_subs_list:  # This is the list of subs *available at start*
                if player_id is not None:
                    pass  # This logic needs refinement if only *played* subs count.

            # Similar logic for away team
            away_starters_list = json.loads(self.match_data.away_tactics.starting_players or "[]")
            for slot in away_starters_list:
                player_id = list(slot.values())[0]
                if player_id is not None:
                    player_ids_in_match.add(player_id)


            # Collect starters from the initial tactics
            initial_starters_ids = set()
            for team_tactics_str in [self.match_data.home_tactics.starting_players,
                                     self.match_data.away_tactics.starting_players]:
                lineup = json.loads(team_tactics_str or "[]")
                for slot in lineup:
                    pid = list(slot.values())[0]
                    if pid is not None:
                        initial_starters_ids.add(pid)

            # Collect players subbed IN from events
            subbed_in_ids = set()
            for event_dict in self.events:
                if event_dict["event_type"] == MatchEventTypeEnum.SUBSTITUTION:
                    # Assuming player_id in SUBSTITUTION event is the player coming IN
                    if event_dict["player_id"] is not None:
                        subbed_in_ids.add(event_dict["player_id"])

            players_who_played_ids = list(initial_starters_ids.union(subbed_in_ids))

            for player_id in players_who_played_ids:
                player_obj = self._player_map.get(player_id)
                if player_obj:
                    # Calculate Match Rating (Example Logic)
                    base_rating = 6.0
                    performance_score = self.player_performance_scores.get(player_id, 0)
                    match_rating = base_rating + (performance_score * 0.25)  # Adjust multiplier
                    match_rating = round(max(4.0, min(10.0, match_rating)), 1)  # Clamp and round

                    # Calculate New Average Rating
                    old_avg = player_obj.avg_rating or 0.0
                    old_matches = player_obj.matches_played or 0  # Use value before increment
                    new_avg_rating = ((old_avg * old_matches) + match_rating) / (old_matches + 1)
                    new_avg_rating = round(new_avg_rating, 2)

                    # Calculate New Form (Example Logic)
                    form_change = 0
                    if match_rating >= 8.0:
                        form_change = random.randint(7, 15)
                    elif match_rating >= 7.0:
                        form_change = random.randint(3, 8)
                    elif match_rating >= 6.0:
                        form_change = random.randint(-3, 3)
                    elif match_rating >= 5.0:
                        form_change = random.randint(-8, -3)
                    else:
                        form_change = random.randint(-15, -7)
                    new_form = (player_obj.form or 50) + form_change
                    new_form = max(0, min(100, new_form))  # Clamp form 0-100

                    # Calculate New Fitness (Example Logic)
                    fitness_drop = random.randint(6, 14)
                    new_fitness = (player_obj.fitness or 100) - fitness_drop
                    new_fitness = max(20, min(100, new_fitness))  # Clamp fitness (e.g., min 20)

                    # Prepare update dict for this player
                    updates = {
                        "matches_played": old_matches + 1,
                        "goals_scored": player_obj.goals_scored,
                        "assists_given": player_obj.assists_given,
                        "avg_rating": new_avg_rating,
                        "form": new_form,
                        "fitness": new_fitness,
                        # Include card/injury status from in-memory object
                        "is_injured": player_obj.is_injured,
                        "injury_rounds": player_obj.injury_rounds,
                        "is_suspended": player_obj.is_suspended,
                        "suspended_rounds": player_obj.suspended_rounds,
                        "has_yellow_card": False if not player_obj.is_suspended else player_obj.has_yellow_card,
                        # Reset yellow if not suspended
                        "received_yellow_cards": player_obj.received_yellow_cards,
                        "received_red_cards": player_obj.received_red_cards,
                        "motm_count": player_obj.motm_count or 0,  # Start with current count
                        "clean_sheets": player_obj.clean_sheets or 0  # Start with current count
                    }
                    players_stats_to_update[player_id] = updates

                    # Check for MOTM
                    if match_rating > highest_rating_so_far:
                        highest_rating_so_far = match_rating
                        motm_player_id = player_id
                    elif match_rating == highest_rating_so_far:
                        # Tie-breaker (e.g., prefer scorer, then assister, then random?) - simple random tie-break for now
                        if random.choice([True, False]):
                            motm_player_id = player_id

                # Update MOTM count and record event
            if motm_player_id and motm_player_id in players_stats_to_update:
                players_stats_to_update[motm_player_id]["motm_count"] += 1
                motm_player_obj = self._player_map.get(motm_player_id)
                if motm_player_obj:
                    self.record_event(minute=90,  # Record MOTM at end of match
                                      event_type=MatchEventTypeEnum.MOTM,  # Need to add MOTM to enum
                                      description=f"{motm_player_obj.name} is the Man of the Match!",
                                      club_id=motm_player_obj.club_id,
                                      player_id=motm_player_id)
                    log_to_screen(f"Man of the Match: {motm_player_obj.name} ({highest_rating_so_far})", True)

            # Update Clean Sheets
            home_gk_and_defs_ids = set()
            away_gk_and_defs_ids = set()
            # Identify starting GKs and Defenders for both teams
            for team_tactics_str, player_set in [(self.match_data.home_tactics.starting_players, home_gk_and_defs_ids),
                                                 (self.match_data.away_tactics.starting_players, away_gk_and_defs_ids)]:
                lineup = json.loads(team_tactics_str or "[]")
                for slot in lineup:
                    pos, pid = list(slot.items())[0]
                    if pid is not None and (pos.upper() == "GK" or pos.upper() in DEFENDERS):
                        # Check if this player was NOT subbed OFF (simple check: are they in final participated list?)
                        if pid in players_who_played_ids:
                            player_set.add(pid)

            if self.away_goals == 0:  # Home team clean sheet
                for pid in home_gk_and_defs_ids:
                    if pid in players_stats_to_update:
                        players_stats_to_update[pid]["clean_sheets"] += 1
                log_to_screen(f"Home team clean sheet recorded for players: {home_gk_and_defs_ids}", True)

            if self.home_goals == 0:  # Away team clean sheet
                for pid in away_gk_and_defs_ids:
                    if pid in players_stats_to_update:
                        players_stats_to_update[pid]["clean_sheets"] += 1
                log_to_screen(f"Away team clean sheet recorded for players: {away_gk_and_defs_ids}", True)


        except Exception as e:
            log_to_screen(f"Error processing player IDs for matches_played update: {e}", True)

        print(f"Match simulation completed: {self.match_data.home_club.club_name} {self.home_goals}:{self.away_goals} {self.match_data.away_club.club_name}")
        self.data_manager.save_match_result(
            match_id=match_id,
            home_goals=self.home_goals,
            away_goals=self.away_goals,
            events=self.events,
        )
        # --- Update Player Statistics in Batch ---
        if players_stats_to_update:
            self.data_manager.update_player_stats_batch(players_stats_to_update)

    def simulate_half(self, is_first_half: bool) -> None:
        """
        Simulates one half of a football match by stepping through random minutes
        and generating events probabilistically, weighted by team strength.

        :param is_first_half: Boolean flag indicating whether this is the first or second half.
        """
        extra_time = random.choices(
            population=list(EXTRA_TIME_WEIGHTS.keys()),
            weights=list(EXTRA_TIME_WEIGHTS.values()),
            k=1
        )[0]
        start_minute = 0 if is_first_half else 46
        end_minute = 45 if is_first_half else 90 + extra_time

        for minute in range(start_minute, end_minute + 1):
            if minute == start_minute:
                self.record_event(
                    minute,
                    MatchEventTypeEnum.KICKOFF,
                    "The referee blows the whistle to start the half.",
                )
                log_to_screen(f"{self.match_data.home_club.club_name} - {self.match_data.away_club.club_name}")
                log_to_screen(f"Kick-off for the {'first' if is_first_half else 'second'} half!")

            elif minute == end_minute:
                if is_first_half:
                    self.record_event(
                        minute,
                        MatchEventTypeEnum.HALFTIME,
                        "The referee signals half-time.",
                    )
                    log_to_screen("Half-time!")
                    log_to_screen(f"Score at half-time: {self.match_data.home_club.club_name} {self.home_goals}:{self.away_goals} {self.match_data.away_club.club_name}")
                else:
                    self.record_event(
                        minute,
                        MatchEventTypeEnum.FULLTIME,
                        "The referee signals full-time.",
                    )
                    log_to_screen("Full-time!")
                    log_to_screen(f"Final Score: {self.match_data.home_club.club_name} {self.home_goals}:{self.away_goals} {self.match_data.away_club.club_name}")

            if random.random() < EVENT_THRESHOLD:
                base_event = choose_event_type()
                team = self._choose_team()
                attacking_club = self.match_data.home_club if team == "home" else self.match_data.away_club
                attacking_tactics = self.match_data.home_tactics if team == "home" else self.match_data.away_tactics
                defending_club = self.match_data.away_club if team == "home" else self.match_data.home_club
                defending_tactics = self.match_data.away_tactics if team == "home" else self.match_data.home_tactics

                self._resolve_event_chain(minute, base_event, attacking_club, defending_club, attacking_tactics, defending_tactics )






    def _choose_team(self) -> Literal["home", "away"]:
        home_strength = self.home_stats.overall_team_strength
        away_strength = self.away_stats.overall_team_strength
        total = home_strength + away_strength
        return "home" if random.random() < (home_strength / total) else "away"

    def _increment_score(self, team: Literal["home", "away"], scorer_id: int) -> None:
        if team == "home":
            self.home_goals += 1
        else:
            self.away_goals += 1

        scorer_player_obj = self._player_map.get(scorer_id)
        if scorer_player_obj:
            self.data_manager.update_player_goal_stat(scorer_id)
            scorer_player_obj.goals_scored += 1
        else:
            log_to_screen(f"Warning: Scorer with ID {scorer_id} not found in player map to update goal stat.", True)

    def _adjust_performance(self, player_id: Optional[int], points: float):
        if player_id is not None:
            self.player_performance_scores[player_id] = self.player_performance_scores.get(player_id, 0) + points

    def _resolve_event_chain(
            self,
            minute: int,
            base_event: MatchEventTypeEnum,
            attacking_club: TournamentClub,
            defending_club: TournamentClub,
            attacking_tactics: ClubTactics,
            defending_tactics: ClubTactics,
            injured_player: Optional[TournamentPlayer] = None,
            goalkeeper: Optional[TournamentPlayer] = None

    ) -> None:
        """
        Resolves the event chain based on the base event type.
        """
        if base_event == MatchEventTypeEnum.CHANCE:
            log_to_screen(f"[{minute}'] CHANCE for {attacking_club.club_name}")

            shooter = self._select_weighted_attacker(attacking_tactics)
            if not shooter:
                log_to_screen(f"[{minute}'] No shooter available for {attacking_club.club_name}")
                return

            # 13% chance of offside
            if random.random() < 0.13:
                self.record_event(minute, MatchEventTypeEnum.OFFSIDE, f"{shooter.name} caught offside.",
                                  attacking_club.club_id, shooter.player_id)
                log_to_screen(f"[{minute}'] Offside called against {attacking_club.club_name}")
                return

            self.record_event(
                minute,
                MatchEventTypeEnum.CHANCE,
                f"{shooter.name} takes a shot for {attacking_club.club_name}",
                club_id=attacking_club.club_id,
                player_id=shooter.player_id
            )
            log_to_screen(f"[{minute}'] {shooter.name} attempts a shot for {attacking_club.club_name}")

            goalkeeper = self._find_goalkeeper(defending_tactics)
            if not goalkeeper:
                log_to_screen(f"[{minute}'] No goalkeeper found for {defending_club.club_name}")
                return

            # Calculate scoring probability
            base_skill_diff = (shooter.shooting or 50) - (goalkeeper.overall_rating or 50)
            normalized_diff = max(-1, min(1, base_skill_diff / 40.0))
            base_scoring_chance = 0.15 + (normalized_diff * 0.10)
            scoring_chance = base_scoring_chance * random.uniform(0.7, 1.1)
            scoring_chance = max(0.02, min(scoring_chance, 0.55)) # Clamp probability
            log_to_screen(
                f"[{minute}'] Shooting vs GK: {shooter.shooting} vs {goalkeeper.overall_rating} → {scoring_chance:.2f}")
            if random.random() < scoring_chance:
                # Goal scored
                self._adjust_performance(shooter.player_id, 3.0)
                self._increment_score("home" if attacking_club.club_id == self.match_data.home_club.club_id else "away", shooter.player_id)
                self.record_event(minute, MatchEventTypeEnum.GOAL,
                                  f"{shooter.name} scores for {attacking_club.club_name}!", attacking_club.club_id,
                                  shooter.player_id)
                log_to_screen(f"[{minute}'] GOAL! {shooter.name} scores for {attacking_club.club_name}")
                if attacking_club.club_id == self.match_data.home_club.club_id:
                    log_to_screen(f"[{minute}'] {attacking_club.club_name} {self.home_goals}:{self.away_goals} {defending_club.club_name}")
                else:
                    log_to_screen(f"[{minute}'] {defending_club.club_name} {self.home_goals}:{self.away_goals} {attacking_club.club_name}")

                # 90% chance of assist
                if random.random() < 0.9:
                    assister = self._select_assister(attacking_tactics, shooter.player_id)
                    if assister:
                        self.record_event(minute, MatchEventTypeEnum.ASSIST, f"{assister.name} assisted the goal.",
                                          attacking_club.club_id, assister.player_id)
                        log_to_screen(f"[{minute}'] Assist by {assister.name}")
                        self.data_manager.update_player_assist_stat(assister.player_id)
                        assister_obj_in_map = self._player_map.get(assister.player_id)
                        if assister_obj_in_map:
                            assister_obj_in_map.assists_given += 1
                        self._adjust_performance(assister.player_id, 1.5)
                else:
                    log_to_screen(f"[{minute}'] No assist recorded for the goal.")
                return
            else:
                # Save by goalkeeper
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.SAVE,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics,
                    goalkeeper= goalkeeper
                )

        if base_event == MatchEventTypeEnum.SAVE:
                # Save by goalkeeper
                self.record_event(minute, MatchEventTypeEnum.SAVE,
                                  f"{goalkeeper.name} makes a save for {defending_club.club_name}.",
                                  defending_club.club_id, goalkeeper.player_id)
                log_to_screen(f"[{minute}'] SAVE by {goalkeeper.name}")
                self._adjust_performance(goalkeeper.player_id, 0.75)
                # Decide next event
                next_event_roll = random.random()
                if next_event_roll < 0.10:
                    # Rebound chance
                    log_to_screen(f"[{minute}'] Rebound chance for {attacking_club.club_name}")
                    self.record_event(
                        minute,
                        MatchEventTypeEnum.REBOUND,
                        f"{attacking_club.club_name} gets a rebound opportunity",
                        club_id=attacking_club.club_id
                    )
                    self._resolve_event_chain(minute, MatchEventTypeEnum.CHANCE, attacking_club, defending_club,
                                              attacking_tactics, defending_tactics)
                elif next_event_roll < 0.40:
                    # Corner kick
                    log_to_screen(f"[{minute}'] Corner kick for {attacking_club.club_name}")
                    self._resolve_event_chain(minute, MatchEventTypeEnum.CORNER_KICK, attacking_club, defending_club, attacking_tactics, defending_tactics)

                else:
                    # Kickoff
                    self.record_event(minute, MatchEventTypeEnum.GOAL_KICK, "The match resumes with a goal kick.", None)
                    log_to_screen(f"[{minute}'] Match resumes with a goal kick")
                return

        elif base_event == MatchEventTypeEnum.CORNER_KICK:
            self.record_event(
                minute,
                MatchEventTypeEnum.CORNER_KICK,
                f"{attacking_club.club_name} takes a corner kick.",
                attacking_club.club_id
            )
            log_to_screen(f"[{minute}'] {attacking_club.club_name} takes a corner kick")

            outcome_roll = random.random()

            if outcome_roll < 0.70:
                log_to_screen(f"[{minute}'] Cross from corner creates a chance!")
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.CHANCE,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics
                )

            elif outcome_roll < 0.90:
                self.record_event(
                    minute,
                    MatchEventTypeEnum.GOAL_KICK,
                    f"{defending_club.club_name} clears the danger and wins a goal kick.",
                    club_id=defending_club.club_id
                )
                log_to_screen(f"[{minute}'] Cleared! {defending_club.club_name} wins a goal kick.")

            elif outcome_roll < 0.95:
                log_to_screen(f"[{minute}'] Penalty awarded to {attacking_club.club_name} after a box incident!")
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.PENALTY,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics
                )

            else:
                log_to_screen(f"[{minute}'] Foul near the box — free kick for {attacking_club.club_name}")
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.FREE_KICK,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics
                )
            return

        elif base_event == MatchEventTypeEnum.FOUL:
            self.record_event(minute, MatchEventTypeEnum.FOUL, f"Foul committed by {defending_club.club_name}.",
                              club_id=defending_club.club_id)
            log_to_screen(f"[{minute}'] Foul by {defending_club.club_name}")

            # 13% chance of injury caused by the foul
            if random.random() < 0.13:
                log_to_screen(f"[{minute}'] Foul leads to an injury for {attacking_club.club_name}")
                self._resolve_event_chain(minute, MatchEventTypeEnum.INJURY, attacking_club, defending_club,
                                          attacking_tactics, defending_tactics)
                return

            outcome_roll = random.random()

            if outcome_roll < 0.10:
                log_to_screen(f"[{minute}'] Referee points to the spot — penalty for {attacking_club.club_name}")
                self._resolve_event_chain(minute, MatchEventTypeEnum.PENALTY, attacking_club, defending_club,
                                          attacking_tactics, defending_tactics)
            elif outcome_roll < 0.80:
                log_to_screen(f"[{minute}'] Free kick awarded to {attacking_club.club_name}")
                self._resolve_event_chain(minute, MatchEventTypeEnum.FREE_KICK, attacking_club, defending_club,
                                          attacking_tactics, defending_tactics)
            else:
                self.record_event(minute, MatchEventTypeEnum.MISTAKE,
                                  f"The referee lets it play — {attacking_club.club_name} wanted the foul!",
                                  club_id=None)
                log_to_screen(f"[{minute}'] Referee lets it go — no foul given")

        elif base_event == MatchEventTypeEnum.INJURY:
            # Pick a random non-GK player
            try:
                parsed = json.loads(attacking_tactics.starting_players)
                field_players = [
                    self._player_map.get(player_id)
                    for slot in parsed
                    for _, player_id in slot.items()
                    if self._player_map.get(player_id) and self._player_map[player_id].position != "GK"
                ]
                injured = random.choice(field_players) if field_players else None
            except Exception as e:
                log_to_screen(f"[{minute}'] Error during injury player selection: {e}")
                return

            if not injured:
                log_to_screen(f"[{minute}'] No eligible player to injure on {attacking_club.club_name}")
                return

            injury_rounds = get_weighted_injury_duration()
            self.data_manager.mark_player_injured(injured.player_id, injury_rounds)

            self.record_event(
                minute,
                MatchEventTypeEnum.INJURY,
                f"{injured.name} is injured and may need to be subbed off.",
                club_id=attacking_club.club_id,
                player_id=injured.player_id
            )
            log_to_screen(f"[{minute}'] Injury! {injured.name} is out for {injury_rounds} rounds.")

            self._resolve_event_chain(
                minute,
                MatchEventTypeEnum.SUBSTITUTION,
                attacking_club,
                defending_club,
                attacking_tactics,
                defending_tactics,
                injured_player=injured
            )
            return


        elif base_event == MatchEventTypeEnum.SUBSTITUTION and injured_player:
            log_to_screen(f"[{minute}'] Substitution needed for {injured_player.name} ({injured_player.position})")
            tactics = attacking_tactics
            try:
                starting = json.loads(tactics.starting_players)
                substitutes = json.loads(tactics.substitutes)
            except json.JSONDecodeError:
                log_to_screen(f"[{minute}'] Invalid tactics JSON — substitution aborted")
                return
            desired_position = None
            for slot in starting:
                for pos, pid in slot.items():
                    if pid == injured_player.player_id:
                        desired_position = pos
                        break
                if desired_position:
                    break
            if not desired_position:
                log_to_screen(f"[{minute}'] Could not determine position of injured player.")
                return
            eligible_subs = [
                self._player_map[pid]
                for pid in substitutes
                if pid in self._player_map and
                   not self._player_map[pid].is_injured and
                   not self._player_map[pid].is_suspended
            ]
            if not eligible_subs:
                log_to_screen(f"[{minute}'] No healthy substitutes available for {attacking_club.club_name}")
                return
            same_pos = [p for p in eligible_subs if p.position == desired_position]
            secondary_pos = [p for p in eligible_subs if desired_position in p.alternative_positions]
            if same_pos:
                sub = max(same_pos, key=lambda p: p.overall_rating)
            elif secondary_pos:
                sub = max(secondary_pos, key=lambda p: p.overall_rating)
            else:
                sub = max(eligible_subs, key=lambda p: p.overall_rating)
            self.data_manager.perform_substitution(
                tactics_id=tactics.tactic_id,
                player_out_id=injured_player.player_id,
                player_in_id=sub.player_id
            )
            self.record_event(
                minute,
                MatchEventTypeEnum.SUBSTITUTION,
                f"{attacking_club.club_name} makes a substitution: {sub.name} replaces injured {injured_player.name}",
                club_id=attacking_club.club_id,
                player_id=sub.player_id
            )
            log_to_screen(f"[{minute}'] {sub.name} comes in for injured {injured_player.name}")
            return

        elif base_event == MatchEventTypeEnum.FREE_KICK:
            foul_committer = self._select_foul_committer(defending_tactics, 1, 2, 4, 7)

            if foul_committer:
                roll = random.random()
                if roll < 0.03:
                    self.record_event(
                        minute,
                        MatchEventTypeEnum.RED_CARD,
                        f"{foul_committer.name} is sent off for {defending_club.club_name}!",
                        club_id=defending_club.club_id,
                        player_id=foul_committer.player_id
                    )
                    self.data_manager.apply_red_card(foul_committer.player_id, defending_tactics.tactic_id)
                    log_to_screen(f"[{minute}'] RED CARD! {foul_committer.name} is sent off!")
                    self._adjust_performance(foul_committer.player_id, -2.0)

                elif roll < 0.33:
                    if foul_committer.has_yellow_card:
                        # Second yellow = red
                        self.record_event(
                            minute,
                            MatchEventTypeEnum.RED_CARD,
                            f"{foul_committer.name} is shown a second yellow — and is sent off!",
                            club_id=defending_club.club_id,
                            player_id=foul_committer.player_id
                        )
                        # Update in-memory object for batch update later
                        foul_committer.is_suspended = True
                        foul_committer.suspended_rounds = random.randint(1, 3)  # Or a fixed value for 2 yellows
                        foul_committer.received_red_cards = (foul_committer.received_red_cards or 0) + 1
                        # Still count this as a yellow card received for stats
                        foul_committer.received_yellow_cards = (foul_committer.received_yellow_cards or 0) + 1
                        self.data_manager.apply_red_card(foul_committer.player_id, defending_tactics.tactic_id)
                        log_to_screen(f"[{minute}'] SECOND YELLOW! {foul_committer.name} is sent off!")
                        self._adjust_performance(foul_committer.player_id, -2.0)
                    else:
                        self.record_event(
                            minute,
                            MatchEventTypeEnum.YELLOW_CARD,
                            f"{foul_committer.name} is shown a yellow card.",
                            club_id=defending_club.club_id,
                            player_id=foul_committer.player_id
                        )
                        # Update in-memory object
                        foul_committer.has_yellow_card = True
                        foul_committer.yellow_card_count = (foul_committer.yellow_card_count or 0) + 1
                        foul_committer.received_yellow_cards = (foul_committer.received_yellow_cards or 0) + 1
                        self.data_manager.apply_yellow_card(foul_committer.player_id)
                        log_to_screen(f"[{minute}'] Yellow card for {foul_committer.name}")
                        self._adjust_performance(foul_committer.player_id, -0.5)

                else:
                    log_to_screen(f"[{minute}'] Foul by {foul_committer.name}, no card issued.")
            else:
                log_to_screen(f"[{minute}'] Foul committed — player could not be identified.")

            fk_taker_id = attacking_tactics.free_kick_taker_id
            fk_taker = self._player_map.get(fk_taker_id)

            if not fk_taker:
                log_to_screen(f"[{minute}'] No valid free kick taker found for {attacking_club.club_name}")
                return

            goalkeeper = self._find_goalkeeper(defending_tactics)
            if not goalkeeper:
                log_to_screen(f"[{minute}'] No goalkeeper found for {defending_club.club_name}")
                return

            self.record_event(
                minute,
                MatchEventTypeEnum.FREE_KICK,
                f"{fk_taker.name} lines up a free kick for {attacking_club.club_name}",
                club_id=attacking_club.club_id,
                player_id=fk_taker.player_id
            )
            log_to_screen(f"[{minute}'] {fk_taker.name} prepares to strike the free kick")

            # Calculate scoring chance
            atk = fk_taker.free_kick_accuracy / 100
            defn = goalkeeper.overall_rating / 100
            base_chance = atk * (1 - defn)
            score_chance = 0.03 + (base_chance * 0.43)
            score_chance *= random.uniform(0.8, 1.2)
            score_chance = max(0.01, min(score_chance, 0.40))  # Clamp

            log_to_screen(
                f"[{minute}'] FK accuracy vs GK: {fk_taker.free_kick_accuracy} vs {goalkeeper.overall_rating} → {score_chance:.2%} goal chance")

            roll = random.random()
            if roll < score_chance:
                self._increment_score("home" if attacking_club.club_id == self.match_data.home_club.club_id else "away", fk_taker.player_id)
                self.record_event(
                    minute,
                    MatchEventTypeEnum.GOAL,
                    f"{fk_taker.name} scores a stunning free kick for {attacking_club.club_name}!",
                    club_id=attacking_club.club_id,
                    player_id=fk_taker.player_id
                )
                log_to_screen(f"[{minute}'] GOAL! {fk_taker.name} puts it past {goalkeeper.name}")
                return

            # Not scored — divide the remaining chance
            remaining = 1.0 - score_chance
            half = remaining / 2

            if roll < score_chance + half:
                # SAVE
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.SAVE,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics,
                    goalkeeper=goalkeeper
                )
            else:
                # GOAL KICK
                self.record_event(
                    minute,
                    MatchEventTypeEnum.GOAL_KICK,
                    f"{defending_club.club_name} prepares for a goal kick.",
                    club_id=defending_club.club_id
                )
                log_to_screen(f"[{minute}'] Goal kick awarded to {defending_club.club_name}")
                return

        elif base_event == MatchEventTypeEnum.PENALTY:
            foul_committer = self._select_foul_committer(defending_tactics, 1, 2, 4, 7)

            if foul_committer:
                roll = random.random()
                if roll < 0.13:
                    self.record_event(
                        minute,
                        MatchEventTypeEnum.RED_CARD,
                        f"{foul_committer.name} is sent off for {defending_club.club_name}!",
                        club_id=defending_club.club_id,
                        player_id=foul_committer.player_id
                    )
                    # Update in-memory object
                    foul_committer.is_suspended = True
                    foul_committer.suspended_rounds = random.randint(1, 3)
                    foul_committer.received_red_cards = (foul_committer.received_red_cards or 0) + 1
                    self.data_manager.apply_red_card(foul_committer.player_id, defending_tactics.tactic_id)
                    log_to_screen(f"[{minute}'] RED CARD! {foul_committer.name} is sent off!")
                    self._adjust_performance(foul_committer.player_id, -2.0)

                elif roll < 0.69:
                    if foul_committer.has_yellow_card:
                        # Second yellow = red
                        self.record_event(
                            minute,
                            MatchEventTypeEnum.RED_CARD,
                            f"{foul_committer.name} is shown a second yellow — and is sent off!",
                            club_id=defending_club.club_id,
                            player_id=foul_committer.player_id
                        )
                        # Update in-memory object for batch update later
                        foul_committer.is_suspended = True
                        foul_committer.suspended_rounds = random.randint(1, 3)  # Or a fixed value for 2 yellows
                        foul_committer.received_red_cards = (foul_committer.received_red_cards or 0) + 1
                        # Still count this as a yellow card received for stats
                        foul_committer.received_yellow_cards = (foul_committer.received_yellow_cards or 0) + 1
                        self.data_manager.apply_red_card(foul_committer.player_id, defending_tactics.tactic_id)
                        log_to_screen(f"[{minute}'] SECOND YELLOW! {foul_committer.name} is sent off!")
                        self._adjust_performance(foul_committer.player_id, -2.0)
                    else:
                        self.record_event(
                            minute,
                            MatchEventTypeEnum.YELLOW_CARD,
                            f"{foul_committer.name} is shown a yellow card.",
                            club_id=defending_club.club_id,
                            player_id=foul_committer.player_id
                        )
                        foul_committer.has_yellow_card = True
                        foul_committer.yellow_card_count = (foul_committer.yellow_card_count or 0) + 1
                        foul_committer.received_yellow_cards = (foul_committer.received_yellow_cards or 0) + 1
                        self.data_manager.apply_yellow_card(foul_committer.player_id)
                        log_to_screen(f"[{minute}'] Yellow card for {foul_committer.name}")
                        self._adjust_performance(foul_committer.player_id, -0.5)

                else:
                    log_to_screen(f"[{minute}'] Foul by {foul_committer.name}, no card issued.")
            else:
                log_to_screen(f"[{minute}'] Foul committed — player could not be identified.")


            pk_taker_id = attacking_tactics.penalty_taker_id
            pk_taker = self._player_map.get(pk_taker_id)

            if not pk_taker:
                log_to_screen(f"[{minute}'] No valid penalty taker found for {attacking_club.club_name}")
                return

            goalkeeper = self._find_goalkeeper(defending_tactics)
            if not goalkeeper:
                log_to_screen(f"[{minute}'] No goalkeeper found for {defending_club.club_name}")
                return

            self.record_event(
                minute,
                MatchEventTypeEnum.PENALTY,
                f"{pk_taker.name} steps up to take the penalty for {attacking_club.club_name}",
                club_id=attacking_club.club_id,
                player_id=pk_taker.player_id
            )
            log_to_screen(f"[{minute}'] Penalty for {attacking_club.club_name}. {pk_taker.name} steps up.")

            atk = pk_taker.penalties / 100
            defn = goalkeeper.overall_rating / 100
            skill_diff_factor = (atk - defn) * 0.15
            base_pk_rate = 0.78
            score_chance = base_pk_rate + skill_diff_factor
            score_chance = max(0.50, min(score_chance, 0.95))  # Clamp between 50% and 95%

            log_to_screen(
                f"[{minute}'] Penalty stat vs GK: {pk_taker.penalties} vs {goalkeeper.overall_rating} → {score_chance:.2%} chance")
            roll = random.random()
            if roll < score_chance:
                self._increment_score("home" if attacking_club.club_id == self.match_data.home_club.club_id else "away", pk_taker.player_id)
                self.record_event(
                    minute,
                    MatchEventTypeEnum.GOAL,
                    f"{pk_taker.name} scores the penalty for {attacking_club.club_name}!",
                    club_id=attacking_club.club_id,
                    player_id=pk_taker.player_id
                )
                log_to_screen(f"[{minute}'] GOAL! {pk_taker.name} buries the penalty.")

            # Not scored — divide the remaining chance
            remaining = 1.0 - score_chance
            eighty = remaining * 0.80

            if roll < score_chance + eighty:
                # SAVE
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.SAVE,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics,
                    goalkeeper=goalkeeper
                )
            else:
                # GOAL KICK
                self.record_event(
                    minute,
                    MatchEventTypeEnum.GOAL_KICK,
                    f"{defending_club.club_name} prepares for a goal kick.",
                    club_id=defending_club.club_id
                )
                log_to_screen(f"[{minute}'] Goal kick awarded to {defending_club.club_name}")
                return
        elif base_event == MatchEventTypeEnum.THROW_IN:
            self.record_event(
                minute,
                MatchEventTypeEnum.THROW_IN,
                f"{attacking_club.club_name} takes a throw-in.",
                club_id=attacking_club.club_id
            )
            log_to_screen(f"[{minute}'] Throw-in for {attacking_club.club_name}")

            if random.random() < 0.5:
                log_to_screen(f"[{minute}'] Quick throw — creates a chance for {attacking_club.club_name}")
                self._resolve_event_chain(
                    minute,
                    MatchEventTypeEnum.CHANCE,
                    attacking_club,
                    defending_club,
                    attacking_tactics,
                    defending_tactics
                )
            else:
                log_to_screen(f"[{minute}'] No danger from the throw-in")
                return

    def _select_weighted_attacker(self, tactics: ClubTactics) -> Optional[TournamentPlayer]:
        """
        Selects a player to attempt a shot based on position weights.
        """
        try:
            # Ensure "[]" as default
            parsed_list_of_dicts = json.loads(tactics.starting_players or "[]")
            players = []
            weights = []
            for slot_dict in parsed_list_of_dicts:  # slot_dict is {"POS": player_id}
                if not (isinstance(slot_dict, dict) and len(slot_dict) == 1):
                    log_to_screen(f"Warning: Malformed slot encountered in _select_weighted_attacker: {slot_dict}",
                                  True)
                    continue

                # Extract player ID from the value
                player_id_from_slot = list(slot_dict.values())[0]

                player = self._player_map.get(player_id_from_slot)
                if player:  # Only consider slots with actual players
                    position_upper = player.position.upper() if isinstance(player.position, str) else ""
                    if position_upper == "GK":  # Don't select GK as shooter
                        continue
                    elif position_upper in DEFENDERS:
                        weight = 1
                    elif position_upper in MIDFIELDERS:
                        weight = 3
                    elif position_upper in ATTACKERS:
                        weight = 6
                    else:
                        weight = 1  # Default for unknown/other positions
                    players.append(player)
                    weights.append(weight)

            if players:  # Check if any eligible players were found
                return random.choices(players, weights=weights, k=1)[0]

        except (json.JSONDecodeError, TypeError) as e:
            log_to_screen(f"Error parsing JSON or processing weighted attacker selection: {e}", True)
            return None
        except Exception as e:  # Catch other potential errors during selection
            log_to_screen(f"Error selecting weighted attacker: {e}", True)
            return None
        return None  # Explicitly return None if no players found or error occurred

    def _find_goalkeeper(self, tactics: ClubTactics) -> Optional[TournamentPlayer]:
        """
        Finds the goalkeeper from the given tactics.
        """
        try:
            # Ensure "[]" as default
            parsed_list_of_dicts = json.loads(tactics.starting_players or "[]")
            for slot_dict in parsed_list_of_dicts:  # slot_dict is {"POS": player_id}
                if not (isinstance(slot_dict, dict) and len(slot_dict) == 1):
                    continue

                # Extract player ID from the value
                player_id_from_slot = list(slot_dict.values())[0]

                player = self._player_map.get(player_id_from_slot)
                # Check if player exists and if their *actual* position is GK
                if player and isinstance(player.position, str) and player.position.upper() == "GK":
                    return player

        except (json.JSONDecodeError, TypeError) as e:
            log_to_screen(f"Error parsing JSON in _find_goalkeeper: {e}", True)
            return None
        except Exception as e:
            log_to_screen(f"Error finding goalkeeper: {e}", True)
            return None

        return None  # Explicitly return None if GK not found or error

    def _select_assister(self, tactics: ClubTactics, scorer_id: int) -> Optional[TournamentPlayer]:
        """
        Selects an assisting player different from the scorer.
        """
        try:
            # Ensure "[]" as default
            parsed_list_of_dicts = json.loads(tactics.starting_players or "[]")
            candidates = []
            for slot_dict in parsed_list_of_dicts:  # slot_dict is {"POS": player_id}
                if not (isinstance(slot_dict, dict) and len(slot_dict) == 1):
                    continue

                # Extract player ID from the value
                player_id_from_slot = list(slot_dict.values())[0]

                # Only consider actual players who are not the scorer
                if player_id_from_slot is not None and player_id_from_slot != scorer_id:
                    player = self._player_map.get(player_id_from_slot)
                    if player:  # Ensure player exists in map
                        candidates.append(player)

            if candidates:
                return random.choice(candidates)

        except (json.JSONDecodeError, TypeError) as e:
            log_to_screen(f"Error parsing JSON in _select_assister: {e}", True)
            return None
        except Exception as e:
            log_to_screen(f"Error selecting assister: {e}", True)
            return None

        return None  # Explicitly return None if no candidates found or error

    def record_event(
        self,
        minute: int,
        event_type: MatchEventTypeEnum,
        description: str,
        club_id: int | None = None,
        player_id: int | None = None,
    ) -> None:
        """
        Records a new event in the internal event list.

        :param minute: Minute the event occurred.
        :param event_type: Enum representing the type of event.
        :param description: Human-readable summary of the event.
        :param club_id: The club responsible for the event.
        :param player_id: The player involved (optional).
        """

        self.events.append({
            "minute": minute,
            "event_type": event_type,
            "description": description,
            "club_id": club_id,
            "player_id": player_id,
        })

    def _select_foul_committer(
            self,
            tactics: ClubTactics,
            weight_gk: int,
            weight_att: int,
            weight_mid: int,
            weight_def: int
    ) -> Optional[TournamentPlayer]:
        """
        Selects a player from the defending team who committed the foul.
        Position weights are passed as arguments to allow dynamic tuning.
        """
        try:
            # Ensure "[]" as default if starting_players is None or empty string
            parsed_list_of_dicts = json.loads(tactics.starting_players or "[]")
        except (json.JSONDecodeError, TypeError) as e:
            log_to_screen(f"Error parsing starting_players JSON in _select_foul_committer for tactics {tactics.tactic_id}: {e}", True)
            return None

        players = []
        weights = []

        for slot_dict in parsed_list_of_dicts: # slot_dict is e.g. {"GK": 101}
            if not (isinstance(slot_dict, dict) and len(slot_dict) == 1):
                log_to_screen(f"Warning: Malformed slot encountered in _select_foul_committer: {slot_dict}", True)
                continue

            # Extract player_id from the slot dictionary's value
            # The key (position name) is not used for selection here, only the player ID
            player_id_from_slot = list(slot_dict.values())[0]

            player = self._player_map.get(player_id_from_slot)
            if not player: # Slot might be empty (player_id_from_slot is None) or ID not in map
                continue

            # Determine weight based on player's actual position
            player_actual_pos_upper = player.position.upper() if isinstance(player.position, str) else ""

            current_weight = 1 # Default weight
            if player_actual_pos_upper == "GK":
                current_weight = weight_gk
            elif player_actual_pos_upper in ATTACKERS: # ATTACKERS should be uppercase set
                current_weight = weight_att
            elif player_actual_pos_upper in MIDFIELDERS: # MIDFIELDERS should be uppercase set
                current_weight = weight_mid
            elif player_actual_pos_upper in DEFENDERS: # DEFENDERS should be uppercase set (includes GK)
                current_weight = weight_def

            players.append(player)
            weights.append(current_weight)

        if not players:
            return None

        return random.choices(players, weights=weights, k=1)[0]

    def _ensure_valid_lineup(self, club_tactics: ClubTactics, club_id_for_log: int):
        """
        Checks the starting lineup for empty slots or invalid players (injured/suspended)
        and attempts to fill them from available substitutes. Updates the ClubTactics in DB.
        """
        try:
            starters_list_of_dicts = json.loads(club_tactics.starting_players or "[]")
            substitutes_ids = json.loads(club_tactics.substitutes or "[]")
            if not isinstance(substitutes_ids, list): substitutes_ids = []
        except (json.JSONDecodeError, TypeError) as e:
            log_to_screen(f"Error parsing tactics for lineup validation (Club {club_id_for_log}): {e}", True)
            return False  # Indicate failure

        from common.constants import FORMATION_TEMPLATES  # Local import if not at top level
        formation_str = club_tactics.formation.value if club_tactics.formation else None
        if not formation_str or formation_str not in FORMATION_TEMPLATES:
            log_to_screen(f"Invalid or missing formation for lineup validation (Club {club_id_for_log})", True)
            return False

        formation_template = FORMATION_TEMPLATES[formation_str]
        lineup_changed = False

        # Ensure starters_list_of_dicts matches template length (defensive)
        if len(starters_list_of_dicts) != len(formation_template):
            log_to_screen(f"Warning: Lineup length mismatch for club {club_id_for_log}. Rebuilding based on template.",
                          True)
            temp_map = {}
            for slot_dict_item in starters_list_of_dicts:
                if isinstance(slot_dict_item, dict) and len(slot_dict_item) == 1:
                    pos_name, p_id_val = list(slot_dict_item.items())[0]
                    temp_map[pos_name.upper()] = p_id_val

            starters_list_of_dicts = []
            for template_pos_item in formation_template:
                starters_list_of_dicts.append({template_pos_item: temp_map.get(template_pos_item.upper())})
            lineup_changed = True  # Structure changed

        current_starter_ids = {list(slot.values())[0] for slot in starters_list_of_dicts if
                               list(slot.values())[0] is not None}

        available_subs = []
        for sub_id in substitutes_ids:
            player_obj = self._player_map.get(sub_id)
            if player_obj and not player_obj.is_injured and not player_obj.is_suspended and sub_id not in current_starter_ids:
                available_subs.append(player_obj)

        # Sort available subs (e.g., by OVR, then by suitability for a position)
        available_subs.sort(key=lambda p: (p.overall_rating or 0), reverse=True)

        for i, slot_dict in enumerate(starters_list_of_dicts):
            slot_position_name = list(slot_dict.keys())[0]
            current_player_id_in_slot = list(slot_dict.values())[0]

            player_in_slot = self._player_map.get(current_player_id_in_slot)

            needs_replacement = False
            if player_in_slot is None:  # Slot is empty
                needs_replacement = True
                log_to_screen(f"Club {club_id_for_log}: Slot {slot_position_name} is empty.", True)
            elif player_in_slot.is_injured or player_in_slot.is_suspended:
                needs_replacement = True
                log_to_screen(
                    f"Club {club_id_for_log}: Player {player_in_slot.name} in {slot_position_name} is unavailable (Inj/Sus).",
                    True)

            if needs_replacement:
                replacement_found = False
                # Try to find a suitable sub (best OVR for position, then alt pos, then any)
                best_sub_for_slot = None
                # Tier 1: Same position
                for sub_player in available_subs:
                    if sub_player.position.upper() == slot_position_name.upper():
                        best_sub_for_slot = sub_player
                        break
                # Tier 2: Alternative position
                if not best_sub_for_slot:
                    for sub_player in available_subs:
                        alt_pos_list = [p.strip().upper() for p in (sub_player.alternative_positions or "").split(',')
                                        if p.strip() and p.strip() != '-']
                        if slot_position_name.upper() in alt_pos_list:
                            best_sub_for_slot = sub_player
                            break
                # Tier 3: Any available sub if no positional match
                if not best_sub_for_slot and available_subs:
                    best_sub_for_slot = available_subs[0]  # Highest OVR available sub

                if best_sub_for_slot:
                    log_to_screen(
                        f"Club {club_id_for_log}: Replacing slot {slot_position_name} with sub {best_sub_for_slot.name} (ID: {best_sub_for_slot.player_id}).",
                        True)
                    starters_list_of_dicts[i] = {slot_position_name: best_sub_for_slot.player_id}
                    # Remove the sub from available_subs list and also from the main substitutes_ids list
                    available_subs.remove(best_sub_for_slot)
                    if best_sub_for_slot.player_id in substitutes_ids:
                        substitutes_ids.remove(best_sub_for_slot.player_id)

                    # If the player being replaced was a valid player (not None), add them to subs if not already there
                    if player_in_slot and player_in_slot.player_id not in substitutes_ids:
                        substitutes_ids.append(player_in_slot.player_id)

                    lineup_changed = True
                    replacement_found = True
                else:
                    log_to_screen(
                        f"Club {club_id_for_log}: No suitable sub found for slot {slot_position_name}. Slot remains as is (potentially empty/invalid).",
                        True)

        if lineup_changed:
            club_tactics.starting_players = json.dumps(starters_list_of_dicts)
            club_tactics.substitutes = json.dumps(substitutes_ids[:7])  # Ensure subs list is capped
            # This change needs to be committed. DataManager method will handle it.
            self.data_manager.update_club_tactics_raw(club_tactics.tactic_id, club_tactics.starting_players,
                                                      club_tactics.substitutes)
            log_to_screen(
                f"Club {club_id_for_log}: Lineup automatically adjusted and saved due to empty/invalid slots.", True)
            return True
        return False  # No changes made
