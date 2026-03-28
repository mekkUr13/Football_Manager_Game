import threading
import time
from datetime import datetime, timezone
import random
import traceback
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from common.constants import DEFENDERS, ATTACKERS, MIDFIELDERS, FREE_AGENTS_CLUB_NAME_PREFIX
from common.utilities import log_to_screen
from server.database.db_session import SessionLocal
from server.database.models import Tournament, TournamentClub, OriginalClub, TournamentMatch, TournamentPlayer, \
    TransferListing, OriginalPlayer
from server.database.data_manager import DataManager
from server.simulation.match_simulator import MatchSimulator
from server.database.data_manager import calculate_player_value

# How often the scheduler checks for tasks (in seconds)
SCHEDULER_INTERVAL_SECONDS = 30  # Check every half minute


class GameScheduler:
    """
    Manages scheduled tasks for the game server, such as starting tournaments
    and simulating rounds. Runs in a separate thread.
    """

    def __init__(self, data_manager: DataManager):
        """
        Initializes the GameScheduler.

        Args:
            data_manager: An instance of DataManager to interact with the database.
        """
        self.data_manager = data_manager
        self.match_simulator = MatchSimulator(data_manager)  # Initialize MatchSimulator
        self.running = False
        self.thread: Optional[threading.Thread] = None
        print("GameScheduler initialized.")

    def _start_new_tournaments(self, session: Session):
        """
        Checks for tournaments that are due to start, fills remaining AI slots,
        and marks them as started.
        """
        print(f"[Scheduler] Checking for tournaments to start at {datetime.now(timezone.utc).isoformat()}...")
        now_utc = datetime.now(timezone.utc)

        # Find tournaments that should have started but haven't been marked as 'is_started'
        tournaments_to_start = session.query(Tournament) \
            .filter(Tournament.start_time <= now_utc, Tournament.is_started == False) \
            .options(joinedload(Tournament.clubs)) \
            .all()

        if not tournaments_to_start:
            print("[Scheduler] No new tournaments to start at this time.")
            return

        for tournament in tournaments_to_start:
            print(f"[Scheduler] Processing tournament '{tournament.name}' (ID: {tournament.tournament_id}) for start.")
            try:
                # Identify already assigned original club IDs in this tournament
                assigned_original_club_ids_in_tournament = {
                    tc.original_club_id for tc in tournament.clubs if tc.original_club_id is not None
                }
                print(f"[Scheduler] Tournament {tournament.name}: Assigned Original Club IDs: {assigned_original_club_ids_in_tournament}")

                # Get all available OriginalClub IDs
                all_possible_original_clubs = session.query(OriginalClub.club_id).all()
                all_possible_original_club_ids = {oc_id for (oc_id,) in all_possible_original_clubs}
                print( f"[Scheduler] Tournament {tournament.name}: All possible Original Club IDs: {all_possible_original_club_ids}")

                available_to_assign_original_club_ids = list(all_possible_original_club_ids - assigned_original_club_ids_in_tournament)
                random.shuffle(available_to_assign_original_club_ids)  # Shuffle for variety
                print(f"[Scheduler] Tournament {tournament.name}: Original Club IDs available for AI assignment: {available_to_assign_original_club_ids}")

                empty_slots_filled_count = 0
                free_agents_pool_name_for_this_tournament = f"{FREE_AGENTS_CLUB_NAME_PREFIX} T{tournament.tournament_id}"
                for slot in tournament.clubs:
                    # Crucial Check: Skip the Free Agents Pool from receiving an OriginalClub
                    if slot.club_name == free_agents_pool_name_for_this_tournament:
                        print(f"[Scheduler] Skipping OriginalClub assignment for Free Agents Pool '{slot.club_name}'.")
                        continue
                    if slot.original_club_id is None:  # This is an unassigned (empty AI) slot
                        if not available_to_assign_original_club_ids:
                            print(f"[Scheduler] Warning: No more unique OriginalClubs to assign to empty slot {slot.club_id} in tournament '{tournament.name}'. Slot remains empty.")
                            continue

                        chosen_original_club_id = available_to_assign_original_club_ids.pop(0)
                        print(
                            f"[Scheduler] Assigning OriginalClub ID {chosen_original_club_id} to empty slot {slot.club_id} in tournament '{tournament.name}'.")

                        # DataManager.create_tournament_club handles copying players, tactics, etc.
                        # It uses its own session, so don't pass the current scheduler's session.
                        self.data_manager.create_tournament_club(
                            tournament_id=tournament.tournament_id,
                            original_club_id=chosen_original_club_id,
                            user_id=None  # Assigning as AI
                        )
                        empty_slots_filled_count += 1

                if empty_slots_filled_count > 0:
                    print(f"[Scheduler] Filled {empty_slots_filled_count} empty AI slots for tournament '{tournament.name}'.")

                # --- START: Add Initial Transfer Listings ---
                print(f"[Scheduler] Populating initial transfer list for {tournament.name}...")

                # Get IDs of OriginalClubs PARTICIPATING in the tournament
                participating_original_club_ids = {
                    tc.original_club_id for tc in tournament.clubs if tc.original_club_id is not None
                }
                print(f"[Scheduler] Participating Original Club IDs: {participating_original_club_ids}")

                # Get OriginalPlayers whose clubs are NOT participating
                candidate_original_players = session.query(OriginalPlayer).filter(
                    OriginalPlayer.club_id.notin_(participating_original_club_ids)
                ).all()
                print(
                    f"[Scheduler] Found {len(candidate_original_players)} OriginalPlayers from non-participating clubs.")

                if candidate_original_players:
                    players_by_role = {"GK": [], "DEF": [], "MID": [], "ATK": []}
                    for p in candidate_original_players:
                        # Use OriginalPlayer position
                        pos_upper = p.position.upper() if p.position else ""
                        if pos_upper == "GK":
                            players_by_role["GK"].append(p)
                        elif pos_upper in DEFENDERS:
                            players_by_role["DEF"].append(p)
                        elif pos_upper in MIDFIELDERS:
                            players_by_role["MID"].append(p)
                        elif pos_upper in ATTACKERS:
                            players_by_role["ATK"].append(p)

                    listings_to_add = []
                    target_count_per_role = 5
                    for role_list in players_by_role.values():
                        random.shuffle(role_list)
                        # Take up to target_count_per_role players from this role
                        selected_for_role = role_list[:target_count_per_role]
                        for player_to_list in selected_for_role:
                            price_multiplier = random.uniform(0.95, 1.40)

                            player_value = calculate_player_value(player_to_list)
                            asking_price = int(round(player_value * price_multiplier / 1000) * 1000)
                            asking_price = max(1000, asking_price)

                            # Pass the OriginalPlayer ID and the object itself
                            listings_to_add.append({
                                "player_id": player_to_list.player_id,
                                "asking_price": asking_price,
                                "original_player_obj": player_to_list
                            })

                    if listings_to_add:
                        # Call DataManager method (uses its own session)
                        print(f"[Scheduler] Adding {len(listings_to_add)} initial transfer listings to the database. listings_to_add: {listings_to_add}")
                        self.data_manager.add_players_to_transfer_list_batch(tournament.tournament_id,
                                                                             listings_to_add)
                    else:
                        print(f"[Scheduler] No candidate players found from non-participating clubs for initial transfer list.")
                # --- END: Add Initial Transfer Listings ---

                tournament.is_started = True
                session.add(tournament)  # Ensure change is staged
                print(f"[Scheduler] Tournament '{tournament.name}' (ID: {tournament.tournament_id}) marked as started.")

            except Exception as e:
                print(f"[Scheduler] Error starting tournament '{tournament.name}' (ID: {tournament.tournament_id}): {e}")
                import traceback
                traceback.print_exc()
                # Don't rollback here, let the main loop handle session commit/rollback
                # Continue to the next tournament if one fails

        session.commit()  # Commit all changes for started tournaments at once

    def _simulate_due_rounds(self, session: Session):
        """
        Checks for active tournaments and simulates rounds/matches that are due.
        """
        print(f"[Scheduler] Checking for rounds to simulate at {datetime.now(timezone.utc).isoformat()}...")
        now_utc = datetime.now(timezone.utc)

        # Find matches that are due and not yet simulated, in started tournaments
        # Order by tournament and then by round, then match time to process sequentially
        matches_to_simulate = session.query(TournamentMatch) \
            .join(TournamentMatch.tournament) \
            .filter(
            Tournament.is_started == True,
            TournamentMatch.is_simulated == False,
            TournamentMatch.match_time <= now_utc
        ).order_by(TournamentMatch.tournament_id, TournamentMatch.round_number, TournamentMatch.match_time).all()

        if not matches_to_simulate:
            print("[Scheduler] No matches due for simulation at this time.")
            return

        processed_match_ids_this_tick = []  # Keep track to avoid double processing if scheduler runs fast

        current_tournament_id = None
        current_round_number = None
        for match in matches_to_simulate:
            if match.match_id in processed_match_ids_this_tick:
                continue
            if current_tournament_id != match.tournament_id or current_round_number != match.round_number:
                if current_tournament_id is not None:  # Log completion of previous round/tournament
                    print( f"[Scheduler] Finished processing simulations for Tournament ID {current_tournament_id}, Round {current_round_number}.")
                current_tournament_id = match.tournament_id
                current_round_number = match.round_number
                print(f"[Scheduler] Starting simulation for Tournament ID {current_tournament_id}, Round {current_round_number}.")

            print(f"[Scheduler] Validating squad composition for match {match.match_id}...")
            try:
                # Call validation for both clubs BEFORE simulation
                self.data_manager.ensure_valid_squad_composition(match.home_club_id)
                self.data_manager.ensure_valid_squad_composition(match.away_club_id)
                print(f"[Scheduler] Squad validation complete for match {match.match_id}.")
            except Exception as valid_err:
                print(
                    f"[Scheduler] CRITICAL Error validating squad composition before match {match.match_id}: {valid_err}. Skipping simulation.")
                # Consider how to handle this - skip match? Mark as error?
                continue  # Skip this match simulation if validation failed critically

            print(f"[Scheduler] Simulating match ID {match.match_id} (Home: {match.home_club_id} vs Away: {match.away_club_id}) scheduled for {match.match_time.isoformat()}")
            try:
                # The MatchSimulator uses its own DataManager which handles sessions for saving results.
                self.match_simulator.simulate(match.match_id)
                processed_match_ids_this_tick.append(match.match_id)

                # After simulation, mark the match as simulated in *this* session
                # The simulator's save_match_result only updates goals and events, not is_simulated directly on the object
                # So, fetch the match again or update the one in memory if safe (it is here)
                match.is_simulated = True
                session.add(match)  # Stage the change for commit
                print(f"[Scheduler] Match ID {match.match_id} simulated successfully.")

                # --- START: Add 2 Random Players to Transfer List (NEW LOGIC: from OriginalPlayer pool) ---
                try:
                    log_to_screen(
                        f"[Scheduler] Attempting to add 2 new OriginalPlayers to transfer list for T{match.tournament_id} after match.",
                        True)
                    # Get IDs of OriginalClubs PARTICIPATING in the tournament
                    participating_original_club_ids = {
                        tc.original_club_id
                        for tc in session.query(TournamentClub.original_club_id)
                        .filter(TournamentClub.tournament_id == match.tournament_id,
                                TournamentClub.original_club_id.isnot(None)).all()
                    }

                    # Get OriginalPlayer IDs that are ALREADY represented by a TournamentPlayer in a TransferListing for this tournament
                    existing_listed_original_player_ids = {
                        tp.original_player_id
                        for tp in session.query(TournamentPlayer)
                        .join(TransferListing, TransferListing.player_id == TournamentPlayer.player_id)
                        .filter(
                            TransferListing.tournament_id == match.tournament_id,
                            TournamentPlayer.original_player_id.isnot(None)
                        ).all()
                    }

                    # Candidate OriginalPlayers: not in a participating club AND not already effectively listed
                    candidate_original_players = session.query(OriginalPlayer).filter(
                        OriginalPlayer.club_id.notin_(participating_original_club_ids),
                        OriginalPlayer.player_id.notin_(existing_listed_original_player_ids)
                    ).all()

                    num_to_add = 2
                    if len(candidate_original_players) >= num_to_add:
                        players_to_list_orig_objs = random.sample(candidate_original_players, num_to_add)

                        listings_for_dm_initial_style = []
                        for op_obj in players_to_list_orig_objs:
                            price_multiplier = random.uniform(0.95, 1.40)
                            player_value = calculate_player_value(op_obj)  # calculate_player_value needs to be imported
                            asking_price = int(round(player_value * price_multiplier / 1000) * 1000)
                            asking_price = max(1000, asking_price)

                            listings_for_dm_initial_style.append({
                                "player_id": op_obj.player_id,  # This is OriginalPlayer ID
                                "asking_price": asking_price,
                                "original_player_obj": op_obj
                            })

                        if listings_for_dm_initial_style:
                            # Use the method for adding *new* OriginalPlayers as unattached TournamentPlayers
                            self.data_manager.add_players_to_transfer_list_batch(match.tournament_id,
                                                                                 listings_for_dm_initial_style)
                            log_to_screen(
                                f"[Scheduler] Added {len(listings_for_dm_initial_style)} new OriginalPlayers to transfer list after match {match.match_id}.")
                    else:
                        log_to_screen(
                            f"[Scheduler] Not enough unique OriginalPlayers available to add to transfer list after match {match.match_id}.",
                            True)

                except Exception as list_err:
                    print(
                        f"[Scheduler] Error adding new OriginalPlayers to transfer list after match {match.match_id}: {list_err}")
                    import traceback
                    traceback.print_exc()
                # --- END: Add 2 Random Players to Transfer List ---

                # --- START: Apply Post-Match Training ---
                try:
                    # Call DataManager method (uses its own session)
                    self.data_manager.apply_post_match_training(match.home_club_id)
                    self.data_manager.apply_post_match_training(match.away_club_id)
                    print(
                        f"[Scheduler] Applied post-match training for clubs {match.home_club_id} and {match.away_club_id}.")
                except Exception as train_err:
                    print(
                        f"[Scheduler] Error applying post-match training after match {match.match_id}: {train_err}")
                    # Don't rollback
                # --- END: Apply Post-Match Training ---
            except Exception as sim_err:
                print(f"[Scheduler] Error simulating match ID {match.match_id}: {sim_err}")
                import traceback
                traceback.print_exc()

        if current_tournament_id is not None:  # Log completion of the last processed round/tournament
            print(
                f"[Scheduler] Finished processing simulations for Tournament ID {current_tournament_id}, Round {current_round_number}.")

        try:
            session.commit()  # Commit 'is_simulated' changes and any other changes staged in this session
            print("[Scheduler] Committed simulation status updates.")
        except Exception as commit_err:
            print(f"[Scheduler] Error committing simulation status updates: {commit_err}")
            session.rollback()

    def _scheduler_loop(self):
        """
        The main loop for the scheduler thread.
        Periodically calls task functions.
        """
        print("[Scheduler] Scheduler loop started.")
        while self.running:
            session = SessionLocal()  # Create a new session for this iteration
            try:
                print("[Scheduler] -------- Tick --------")
                self._start_new_tournaments(session)
                self._simulate_due_rounds(session)
                # Add more scheduled tasks here in the future
            except Exception as e:
                print(f"[Scheduler] Critical error in scheduler loop: {e}")
                traceback.print_exc()
                session.rollback()  # Rollback any uncommitted changes from this tick
            finally:
                session.close()  # Always close the session
                print("[Scheduler] ------ End Tick ------")

            # Wait for the next interval
            # Check self.running frequently to allow quick shutdown
            for _ in range(SCHEDULER_INTERVAL_SECONDS):
                if not self.running:
                    break
                time.sleep(1)
        print("[Scheduler] Scheduler loop stopped.")

    def start(self):
        """Starts the scheduler in a new daemon thread."""
        if self.running:
            print("[Scheduler] Scheduler is already running.")
            return
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        print("[Scheduler] Scheduler thread started.")

    def stop(self):
        """Stops the scheduler thread."""
        print("[Scheduler] Stopping scheduler...")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=SCHEDULER_INTERVAL_SECONDS + 5)  # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            print("[Scheduler] Warning: Scheduler thread did not terminate gracefully.")
        else:
            print("[Scheduler] Scheduler thread stopped successfully.")
        self.thread = None