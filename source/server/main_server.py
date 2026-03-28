import socket
import threading
import json
from typing import Dict, Any, List
import hashlib
import os
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, asc, func

from common.constants import FREE_AGENTS_CLUB_NAME_PREFIX
from server.database.data_manager import DataManager
from server.database.models import TournamentClub, User, Tournament, TournamentPlayer, OriginalClub, TournamentMatch, TransferListing, TournamentMatchEvent
from server.database.db_session import SessionLocal
from server.scheduler import GameScheduler
from common.enums import TrainingFocusEnum, FormationEnum, PlayStyleEnum, TransferStatus

HOST = '127.0.0.1' # Local
# HOST = '0.0.0.0'   # Listen on all available network interfaces
PORT = 65432

try:
    data_manager = DataManager(logging_enabled=True)
    print("DataManager initialized successfully.")
except Exception as e:
    print(f"FATAL: Could not initialize DataManager: {e}")
    exit()

# --- Password Hashing ---
SALT_LENGTH = 16
def hash_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
    """Hashes a password with a salt. Generates salt if none provided."""
    if salt is None:
        salt = os.urandom(SALT_LENGTH)
    hasher = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hasher.hex(), salt

def verify_password(stored_hash: str, provided_password: str, salt: bytes) -> bool:
    """Verifies a provided password against a stored hash and salt."""
    hasher = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return hasher.hex() == stored_hash

# --- Request Handler Functions ---

def handle_register_user(payload: Dict[str, Any], session) -> Dict[str, Any]:
    username = payload.get('username')
    email = payload.get('email')
    password = payload.get('password')

    if not all([username, email, password]):
        raise ValueError("Missing username, email, or password")

    # Check if username or email exists
    existing_user = session.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        raise ValueError("Username or Email already exists.")

    hashed_pw, salt = hash_password(password)
    new_user = User(
        username=username,
        email=email,
        password_hash=f"{salt.hex()}${hashed_pw}" # Store salt and hash together
    )
    session.add(new_user)
    session.commit()
    print(f"Registered new user: {username}")
    return {"user_id": new_user.user_id, "username": new_user.username}

def handle_login_user(payload: Dict[str, Any], session) -> Dict[str, Any]:
    username = payload.get('username')
    password = payload.get('password')
    if not all([username, password]):
        raise ValueError("Missing username or password")

    user = session.query(User).filter(User.username == username).first()
    if not user or '$' not in user.password_hash: # Basic check for format
        raise ValueError("Invalid username or password.") # Generic error

    salt_hex, stored_hash = user.password_hash.split('$', 1)
    salt = bytes.fromhex(salt_hex)

    if verify_password(stored_hash, password, salt):
        print(f"User logged in: {username}")
        # Return minimal info needed by client
        return {"user_id": user.user_id, "username": user.username}
    else:
        raise ValueError("Invalid username or password.") # Generic error


def handle_get_user_clubs(payload: Dict[str, Any], session) -> List[Dict[str, Any]]:
    """Handles request to get clubs managed by a user."""
    user_id = payload.get('user_id')
    if not user_id:
        raise ValueError("Missing 'user_id'")

    # Fetch clubs associated with the user_id
    clubs = session.query(TournamentClub).options(
        joinedload(TournamentClub.tournament)  # Eager load tournament
    ).filter(
        TournamentClub.user_id == user_id
    ).all()

    # Convert each club object to a dictionary using its to_dict method
    # This prepares the data for JSON serialization.
    return [club.to_dict(include_tournament_name=True) for club in clubs]

def handle_get_squad(payload: Dict[str, Any], session) -> list[Dict[str, Any]]:
    """Handles request to get the squad for a specific tournament club."""
    club_id = payload.get('club_id')
    if not club_id:
        raise ValueError("Missing 'club_id' in payload for get_squad request.")

    # Query players, ensuring they belong to the specified tournament club ID
    players = session.query(TournamentPlayer).filter(
        TournamentPlayer.club_id == club_id
    ).order_by(
        TournamentPlayer.position,
        TournamentPlayer.overall_rating.desc()
    ).all()

    # Convert player objects to dictionaries for the response
    squad_data = [player.to_dict() for player in players]
    print(f"Retrieved squad data for club_id {club_id}, found {len(squad_data)} players.")
    return squad_data

def handle_get_available_leagues(payload: Dict[str, Any], session) -> List[Dict[str, Any]]:
    """Handles request to get leagues that are not full and haven't started."""
    now_utc = datetime.now(timezone.utc)
    print(f"SERVER TIME CHECK: Current server time (UTC): {now_utc.isoformat()}")

    leagues_query = session.query(Tournament)

    leagues = leagues_query.all()
    print(f"Found {len(leagues)} total tournaments in DB.")

    available_leagues_data = []
    for league in leagues:
        # --- DETAILED LOGGING ---
        start_time_utc = league.start_time
        has_started = False
        comparison_type_error = False
        try:
            # Make sure start_time_utc is timezone-aware (should be if stored correctly)
            if start_time_utc.tzinfo is None:
                 # If naive, assume it *was* UTC, make it aware for comparison
                 start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
                 tz_info = "NAIVE (assumed UTC)"
            else:
                 # If aware, ensure it's converted to UTC for comparison consistency
                 start_time_utc = start_time_utc.astimezone(timezone.utc)
                 tz_info = str(start_time_utc.tzinfo)

            has_started = start_time_utc <= now_utc # Check if start time is past or exactly now
            comparison_result = f"{start_time_utc.isoformat()} <= {now_utc.isoformat()} -> {has_started}"
        except TypeError as te:
            # This happens if comparing aware and naive datetimes
            comparison_result = f"TYPE ERROR comparing {start_time_utc} with {now_utc}"
            comparison_type_error = True
            has_started = True # Treat comparison error as "cannot determine, assume started" for safety
        except Exception as e:
             comparison_result = f"ERROR during comparison: {e}"
             has_started = True # Treat comparison error as "cannot determine, assume started" for safety
             tz_info = "ERROR"


        print(f"--- Checking League ID {league.tournament_id} ('{league.name}') ---")
        print(f"    DB Start Time: {league.start_time} (TZ Info: {tz_info})")
        print(f"    Comparison: {comparison_result}")
        # --- END DETAILED LOGGING ---

        if not has_started and not comparison_type_error:
            filled_slots = session.query(TournamentClub).filter(
                 TournamentClub.tournament_id == league.tournament_id,
                 TournamentClub.original_club_id.isnot(None)
            ).count()

            if filled_slots < league.number_of_clubs:
                league_dict = league.to_dict()
                league_dict['filled_slots'] = filled_slots
                available_leagues_data.append(league_dict)
                print(f"    Status: AVAILABLE (Slots: {filled_slots}/{league.number_of_clubs})")
            else:
                print(f"    Status: FULL (Slots: {filled_slots}/{league.number_of_clubs})")
        elif comparison_type_error:
             print(f"    Status: SKIPPED (Timezone comparison error)")
        else:
             print(f"    Status: SKIPPED (Already started)")


    print(f"Found {len(available_leagues_data)} available leagues meeting criteria.")
    return available_leagues_data

def handle_get_league_details(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request for details of a specific league, including club availability."""
    tournament_id = payload.get('tournament_id')
    if not tournament_id:
        raise ValueError("Missing 'tournament_id'")

    # Fetch the tournament/league itself
    league = session.query(Tournament).filter_by(tournament_id=tournament_id).first()
    if not league:
        raise ValueError(f"League with ID {tournament_id} not found.")

    # Fetch all club slots within this tournament, joining with User if user_id is present
    tournament_clubs = session.query(TournamentClub)\
        .options(joinedload(TournamentClub.user))\
        .filter_by(tournament_id=tournament_id)\
        .all()

    taken_original_club_ids = set()
    taken_clubs_details = []
    for tc in tournament_clubs:
        if tc.original_club_id: # Check if a slot is assigned to an original club
            taken_original_club_ids.add(tc.original_club_id)
            taken_clubs_details.append({
                 "original_club_id": tc.original_club_id,
                 "club_name": tc.club_name,
                 # Use the loaded user relationship if available
                 "taken_by": tc.user.username if tc.user else "AI",
                 "is_taken": True,
             })

    # Fetch all original clubs (potential candidates)
    # Consider optimizing this if there are thousands of original clubs
    all_original_clubs = session.query(OriginalClub).all()

    # Filter original clubs to find those not already taken in this specific tournament
    available_clubs_details = []
    for oc in all_original_clubs:
        if oc.club_id not in taken_original_club_ids:
            available_clubs_details.append({
                "original_club_id": oc.club_id,
                "club_name": oc.club_name,
                "is_taken": False,
                # --- Add new stats ---
                "avg_ovr": oc.avg_overall,
                "total_value": oc.total_value,
                "player_count": oc.player_count
            })

    available_clubs_details.sort(key=lambda x: x['club_name']) # Sort alphabetically

    # Structure the response
    return {
        "league": league.to_dict(), # Basic league info
        "taken_clubs": taken_clubs_details, # List of clubs taken in this league
        "available_clubs": available_clubs_details, # List of clubs available for this league
    }


def handle_create_tournament(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to create a new tournament."""
    name = payload.get('name')
    num_clubs = payload.get('num_clubs')
    start_delay_sec = payload.get('start_delay_sec')
    round_interval_sec = payload.get('round_interval_sec')
    creator_user_id = payload.get('creator_user_id')

    if not all([name, num_clubs, start_delay_sec, round_interval_sec, creator_user_id]):
         raise ValueError("Missing required fields for tournament creation.")

    try:
        # The DataManager method handles its own session and transactions
        new_tournament = data_manager.create_tournament(
            name=name,
            creator_id=creator_user_id,
            start_delay_sec=start_delay_sec,
            num_clubs=num_clubs,
            round_interval_sec=round_interval_sec
        )
        # Convert the returned SQLAlchemy object to a dictionary
        return new_tournament.to_dict()
    except ValueError as ve:
        raise ve # Propagate validation errors
    except Exception as e:
         print(f"Error during handle_create_tournament: {e}")
         import traceback
         traceback.print_exc()
         raise RuntimeError("Server failed to create the tournament.") # Generic error for client

def handle_join_league_club(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles a user joining a specific club in a league."""
    user_id = payload.get('user_id')
    tournament_id = payload.get('tournament_id')
    original_club_id = payload.get('original_club_id')

    if not all([user_id, tournament_id, original_club_id]):
        raise ValueError("Missing user_id, tournament_id, or original_club_id")

    # --- Perform Validations within the current session ---
    # 1. Max clubs check
    user_club_count = session.query(TournamentClub).filter_by(user_id=user_id).count()
    if user_club_count >= 3:
        raise ValueError("User already manages the maximum number of clubs (3).")

    # 2. League validity check
    league = session.query(Tournament).filter_by(tournament_id=tournament_id).first()
    if not league:
        raise ValueError(f"League with ID {tournament_id} not found.")

    league_start_time = league.start_time
    if league_start_time.tzinfo is None:
        # If naive, assume it's UTC and make it aware
        league_start_time_utc = league_start_time.replace(tzinfo=timezone.utc)
        print(
            f"DEBUG handle_join_league_club: Converted naive league start time {league_start_time} to aware UTC {league_start_time_utc.isoformat()}")
    else:
        # If already aware, ensure it's in UTC
        league_start_time_utc = league_start_time.astimezone(timezone.utc)
        print(
            f"DEBUG handle_join_league_club: League start time was already aware: {league_start_time_utc.isoformat()}")

    # Now compare the aware UTC start time with aware UTC now
    if league_start_time_utc <= datetime.now(timezone.utc):
        raise ValueError("Cannot join: League has already started.")

    # 3. Club availability check (ensure original_club_id is not already assigned *in this tournament*)
    existing_assignment = session.query(TournamentClub).filter_by(
        tournament_id=tournament_id,
        original_club_id=original_club_id
    ).first()
    if existing_assignment:
         raise ValueError("Selected club is already taken in this league.")

    # --- Perform Join using DataManager ---
    # data_manager.create_tournament_club handles finding an empty slot and assigning
    try:
         # This method should handle its own session/transaction internally for safety
         # It finds an empty slot and updates it with the provided details.
         newly_assigned_club = data_manager.create_tournament_club(
             tournament_id=tournament_id,
             original_club_id=original_club_id,
             user_id=user_id
             # session=session # Pass session ONLY if DataManager methods are designed to use it externally
         )
         print(f"User {user_id} joined club {original_club_id} in tournament {tournament_id}")
         # Return the details of the now-assigned club slot
         return newly_assigned_club.to_dict() # Convert the result to dict
    except ValueError as e:
         # Catch errors like "no slots available" or "original club not found" from DataManager
         raise ValueError(f"Failed to join club: {e}") # Propagate error message
    except Exception as e:
         # Catch unexpected database or other errors
         print(f"Unexpected error joining club: {e}")
         import traceback
         traceback.print_exc()
         raise RuntimeError("An internal server error occurred while joining the club.")


def handle_get_fixtures(payload: Dict[str, Any], session) -> List[Dict[str, Any]]:
    """Handles request to get the match fixtures for a given tournament."""
    tournament_id = payload.get('tournament_id')
    # Also need the club_id of the user to potentially highlight their matches
    user_club_id = payload.get('user_club_id') # Client needs to send this

    if not tournament_id:
        raise ValueError("Missing 'tournament_id' for fixtures request.")

    # Query matches, joining with clubs to get names
    matches = session.query(TournamentMatch)\
        .options(
            joinedload(TournamentMatch.home_club),
            joinedload(TournamentMatch.away_club)
        )\
        .filter(TournamentMatch.tournament_id == tournament_id)\
        .order_by(TournamentMatch.round_number, TournamentMatch.match_time)\
        .all()

    # Convert match objects to dictionaries, including club names
    fixtures_data = [match.to_dict(include_clubs=True) for match in matches]

    print(f"Retrieved {len(fixtures_data)} fixtures for tournament {tournament_id}.")
    return fixtures_data

def handle_get_club_tactics(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to get the tactics for a specific tournament club."""
    club_id = payload.get('club_id')
    if not club_id:
        raise ValueError("Missing 'club_id' in payload for get_club_tactics request.")

    # Query for the ClubTactics associated with the tournament club
    # Need to join TournamentClub to get to its tactic_id, then join ClubTactics
    tournament_club = session.query(TournamentClub).options(
        joinedload(TournamentClub.tactics)  # Eager load the tactics
    ).filter(
        TournamentClub.club_id == club_id
    ).first()

    if not tournament_club:
        raise ValueError(f"Tournament club with ID {club_id} not found.")

    if not tournament_club.tactics:
        print(f"Warning: Club {club_id} does not have tactics assigned. This might indicate an issue.")
        raise ValueError(f"Tactics not found for club ID {club_id}.")

    print(f"DEBUG SERVER: Club {club_id} Tactics - Formation: {tournament_club.tactics.formation.value if tournament_club.tactics.formation else 'None'}")
    print(f"DEBUG SERVER: Club {club_id} Tactics - Raw starting_players JSON: {tournament_club.tactics.starting_players}")
    print(f"DEBUG SERVER: Club {club_id} Tactics - Raw substitutes JSON: {tournament_club.tactics.substitutes}")

    # Convert tactics object to a dictionary for the response
    tactics_data = tournament_club.tactics.to_dict()
    print(f"DEBUG SERVER: Club {club_id} Tactics - Processed starting_player_ids_ordered: {tactics_data.get('starting_player_ids_ordered')}")
    print(f"Retrieved tactics data for club_id {club_id}.")
    return tactics_data


def handle_update_lineup_slot(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to update a player in a specific lineup slot."""
    club_id = payload.get('club_id')
    slot_index = payload.get('slot_index')  # 0-based index corresponding to formation template
    new_player_id = payload.get('new_player_id')  # Can be None to empty the slot

    if club_id is None or slot_index is None:  # new_player_id can be None
        raise ValueError("Missing required fields: club_id or slot_index.")
    if not isinstance(slot_index, int) or slot_index < 0:
        raise ValueError("Invalid slot_index.")
    if new_player_id is not None and not isinstance(new_player_id, int):
        raise ValueError("Invalid new_player_id.")

    # Find the club and its tactics
    tournament_club = session.query(TournamentClub).options(
        joinedload(TournamentClub.tactics)
    ).filter(
        TournamentClub.club_id == club_id
    ).first()

    if not tournament_club:
        raise ValueError(f"Club with ID {club_id} not found.")
    if not tournament_club.tactics:
        raise ValueError(f"Tactics not found for club ID {club_id}.")

    tactics = tournament_club.tactics
    formation_str = tactics.formation.value if tactics.formation else None

    if not formation_str:
        raise ValueError("Club tactics have no formation set.")

    # Get the template for the current formation
    from common.constants import FORMATION_TEMPLATES
    if formation_str not in FORMATION_TEMPLATES:
        raise ValueError(f"Formation '{formation_str}' is invalid or not found.")
    formation_template = FORMATION_TEMPLATES[formation_str]  # ["GK", "RB", ...]

    if slot_index >= len(formation_template):
        raise ValueError(
            f"slot_index {slot_index} is out of bounds for formation {formation_str} (length {len(formation_template)}).")

    # --- Load and Modify the starting_players JSON ---
    try:
        # Expecting [{"GK": id1}, {"RB": id2}, ...] format
        current_lineup_list = json.loads(tactics.starting_players or "[]")

        # Ensure the list has the correct length based on the template
        if len(current_lineup_list) != len(formation_template):
            print(
                f"Warning: Lineup length mismatch for club {club_id}. Stored: {len(current_lineup_list)}, Template: {len(formation_template)}. Attempting to fix.")
            # Rebuild structure based on template, trying to preserve existing IDs
            temp_map = {}
            for slot_dict in current_lineup_list:
                if isinstance(slot_dict, dict) and len(slot_dict) == 1:
                    pos_name, p_id = list(slot_dict.items())[0]
                    temp_map[pos_name.upper()] = p_id

            current_lineup_list = []
            for template_pos in formation_template:
                current_lineup_list.append({template_pos: temp_map.get(template_pos.upper())})

        # Now update the specific slot
        if slot_index < len(current_lineup_list):
            target_slot_dict = current_lineup_list[slot_index]  # e.g. {"RB": 102}
            if isinstance(target_slot_dict, dict) and len(target_slot_dict) == 1:
                position_name = list(target_slot_dict.keys())[0]  # Get the position name ("RB")
                # Update the value (player ID) for this position key
                current_lineup_list[slot_index] = {position_name: new_player_id}

                # --- Update substitutes list ---
                try:
                    subs_list = json.loads(tactics.substitutes or "[]")
                    if not isinstance(subs_list, list): subs_list = []

                    player_being_replaced = list(target_slot_dict.values())[0]  # Old player ID

                    # If the new player was a sub, remove them from subs
                    if new_player_id is not None and new_player_id in subs_list:
                        subs_list.remove(new_player_id)

                    # If the replaced player exists and is not the new player, add them to subs
                    if player_being_replaced is not None and player_being_replaced != new_player_id:
                        if player_being_replaced not in subs_list:
                            subs_list.append(player_being_replaced)

                    tactics.substitutes = json.dumps(subs_list)
                except (json.JSONDecodeError, TypeError):
                    print(f"Warning: Could not parse or update substitutes for club {club_id}")

            else:
                raise ValueError(f"Malformed lineup data at slot index {slot_index}.")
        else:
            # This case should be caught by the earlier length check, but added for safety
            raise ValueError(f"slot_index {slot_index} became invalid during processing.")

        # Save the modified list back to the tactics object
        tactics.starting_players = json.dumps(current_lineup_list)
        session.commit()
        print(f"Updated lineup slot {slot_index} for club {club_id} to player {new_player_id}")

        # Return the updated tactics or just success message
        return {"message": "Lineup slot updated successfully."}  # Keep response minimal

    except json.JSONDecodeError:
        session.rollback()
        raise ValueError("Failed to parse current lineup data.")
    except Exception as e:
        session.rollback()
        print(f"Error updating lineup slot: {e}")
        raise  # Re-raise other exceptions

def handle_swap_lineup_players(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to swap two players between starter/sub/reserve roles."""
    club_id = payload.get('club_id')
    # ID of the player selected FROM the list (the one to move INTO the lineup/sub spot)
    player_in_id = payload.get('player_in_id')
    # ID of the player being replaced (originally clicked in LineupScreen)
    player_out_id = payload.get('player_out_id')
    # Index of the starter slot being filled (None if replacing a sub)
    target_slot_index = payload.get('target_slot_index')

    if club_id is None or player_in_id is None or player_out_id is None:
        # target_slot_index can be None if player_out was a sub
        raise ValueError("Missing required fields: club_id, player_in_id, or player_out_id.")

    # --- Get Tactics and Parse ---
    club = session.query(TournamentClub).options(joinedload(TournamentClub.tactics)).filter_by(
        club_id=club_id).first()
    if not club or not club.tactics: raise ValueError(f"Club or tactics not found for ID {club_id}.")
    tactics = club.tactics
    try:
        starters_list_of_dicts = json.loads(tactics.starting_players or "[]")  # [{"GK": id1}, {"RB": id2}, ...]
        subs_list = json.loads(tactics.substitutes or "[]")  # [id7, id8, ...]
        if not isinstance(subs_list, list): subs_list = []
    except json.JSONDecodeError:
        raise ValueError("Failed to parse tactics JSON.")

    # --- Get Formation Template ---
    from common.constants import FORMATION_TEMPLATES
    formation_str = tactics.formation.value if tactics.formation else None
    if not formation_str or formation_str not in FORMATION_TEMPLATES: raise ValueError("Invalid formation.")
    formation_template = FORMATION_TEMPLATES[formation_str]

    # Ensure starter list matches template length (defensive check)
    if len(starters_list_of_dicts) != len(formation_template):
        raise ValueError("Lineup data length mismatch.")  # Or try to fix like before

    # --- Find current locations ---
    player_in_current_starter_slot = -1
    player_in_current_sub_index = -1
    player_out_current_starter_slot = -1
    player_out_current_sub_index = -1

    # Check starters
    for idx, slot_dict in enumerate(starters_list_of_dicts):
        current_pid = list(slot_dict.values())[0]
        if current_pid == player_in_id: player_in_current_starter_slot = idx
        if current_pid == player_out_id: player_out_current_starter_slot = idx

    # Check subs if not found in starters
    if player_in_current_starter_slot == -1:
        try:
            player_in_current_sub_index = subs_list.index(player_in_id)
        except ValueError:
            pass  # player_in is a reserve
    if player_out_current_starter_slot == -1:
        try:
            player_out_current_sub_index = subs_list.index(player_out_id)
        except ValueError:
            raise ValueError(
                f"Player Out ({player_out_id}) not found in starters or subs.")  # Should not happen based on context

    print(
        f"Swap Prep: PlayerIn ({player_in_id}): StarterSlot={player_in_current_starter_slot}, SubIndex={player_in_current_sub_index}")
    print(
        f"Swap Prep: PlayerOut ({player_out_id}): StarterSlot={player_out_current_starter_slot}, SubIndex={player_out_current_sub_index}")

    # --- Perform the Swap ---

    # 1. Place player_in into the target slot (either starter or sub)
    if target_slot_index is not None:  # Replacing a starter
        if target_slot_index != player_out_current_starter_slot:
            raise ValueError("Mismatch between target_slot_index and found player_out slot.")
        position_name = list(starters_list_of_dicts[target_slot_index].keys())[0]
        starters_list_of_dicts[target_slot_index] = {position_name: player_in_id}
        print(f"Placed PlayerIn {player_in_id} into starter slot {target_slot_index} ({position_name})")
    else:  # Replacing a sub (player_out was a sub)
        if player_out_current_sub_index == -1: raise ValueError("Cannot replace sub if player_out wasn't a sub.")
        subs_list[player_out_current_sub_index] = player_in_id
        print(f"Placed PlayerIn {player_in_id} into sub index {player_out_current_sub_index}")

    # 2. Remove player_in from its original location (if starter or sub)
    if player_in_current_starter_slot != -1:
        pos_name = list(starters_list_of_dicts[player_in_current_starter_slot].keys())[0]
        starters_list_of_dicts[player_in_current_starter_slot] = {pos_name: None}  # Empty the original slot
        print(f"Emptied PlayerIn's original starter slot {player_in_current_starter_slot}")
    elif player_in_current_sub_index != -1:
        # If player_in was placed into the slot player_out occupied, need careful removal
        if target_slot_index is None and player_out_current_sub_index == player_in_current_sub_index:
            # player_in replaced player_out in the subs list, removal already handled by assignment above.
            pass
        else:
            # Remove player_in from its original sub position
            # Need to find it again in case list was modified
            try:
                current_in_idx = subs_list.index(player_in_id)
                # Only remove if it wasn't the target slot we just filled
                if target_slot_index is not None or current_in_idx != player_out_current_sub_index:
                    del subs_list[current_in_idx]
                    print(f"Removed PlayerIn {player_in_id} from subs list")
            except ValueError:
                print(f"Warning: PlayerIn {player_in_id} was expected in subs but not found for removal.")
                pass  # Already removed or wasn't there

    # 3. Place player_out into the location vacated by player_in
    if player_in_current_starter_slot != -1:  # player_in was a starter, put player_out there
        pos_name = list(starters_list_of_dicts[player_in_current_starter_slot].keys())[0]
        starters_list_of_dicts[player_in_current_starter_slot] = {pos_name: player_out_id}
        print(f"Placed PlayerOut {player_out_id} into PlayerIn's old starter slot {player_in_current_starter_slot}")
    elif player_in_current_sub_index != -1:  # player_in was a sub, put player_out there (if not already placed)
        # Ensure player_out isn't already the player we just put in the subs list
        if target_slot_index is None and player_out_current_sub_index == player_in_current_sub_index:
            # player_in replaced player_out, player_out is now implicitly reserve.
            pass
        elif player_out_id not in subs_list:
            subs_list.append(player_out_id)  # Add player_out to end of subs
            print(f"Added PlayerOut {player_out_id} to subs list (replacing reserve PlayerIn)")

    roles_transferred = []
    # Only transfer roles IF player_out was a starter AND player_in is taking their place
    if player_out_current_starter_slot != -1 and target_slot_index == player_out_current_starter_slot:
        print(f"Checking roles for outgoing starter {player_out_id} being replaced by {player_in_id}")
        if tactics.captain_id == player_out_id:
            tactics.captain_id = player_in_id
            roles_transferred.append("Captain")
        if tactics.free_kick_taker_id == player_out_id:
            tactics.free_kick_taker_id = player_in_id
            roles_transferred.append("Free Kick Taker")
        if tactics.penalty_taker_id == player_out_id:
            tactics.penalty_taker_id = player_in_id
            roles_transferred.append("Penalty Taker")
        if tactics.corner_taker_id == player_out_id:
            tactics.corner_taker_id = player_in_id
            roles_transferred.append("Corner Taker")

        if roles_transferred:
            print(f"Transferred roles [{', '.join(roles_transferred)}] from {player_out_id} to {player_in_id}")

    # --- Save and Commit ---
    tactics.starting_players = json.dumps(starters_list_of_dicts)
    # Ensure subs list length constraint (e.g., max 7) if necessary - simple truncate for now
    max_subs = 7  # Or get from tournament settings
    tactics.substitutes = json.dumps(subs_list[:max_subs])

    session.commit()
    print(f"Swap successful for club {club_id}. Starters: {tactics.starting_players}, Subs: {tactics.substitutes}")
    return {"message": "Player swap successful."}

def handle_get_standings(payload: Dict[str, Any], session) -> List[Dict[str, Any]]:
    """
    Handles request to get the standings for a given tournament.
    Sorts clubs by points, wins, goals scored, goal difference, then name.
    """
    tournament_id = payload.get('tournament_id')
    if not tournament_id:
        raise ValueError("Missing 'tournament_id' for standings request.")

    free_agents_club_name_pattern_for_this_tournament = f"{FREE_AGENTS_CLUB_NAME_PREFIX} T{tournament_id}"

    # Query TournamentClubs for the specified tournament
    clubs_query = session.query(TournamentClub).filter(
        TournamentClub.tournament_id == tournament_id,
        TournamentClub.club_name.isnot(None),  # Only clubs that have been assigned a name
        TournamentClub.club_name != free_agents_club_name_pattern_for_this_tournament  # Exclude the Free Agents pool
    )

    # Apply sorting

    clubs = clubs_query.order_by(
        desc(TournamentClub.points),
        desc(TournamentClub.wins),
        desc(TournamentClub.goals_scored),
        desc(TournamentClub.goals_scored - TournamentClub.goals_conceded), # Goal Difference
        asc(TournamentClub.club_name) # Alphabetical by name as the last tie-breaker
    ).all()

    standings_data = []
    for rank, club in enumerate(clubs, 1): # rank starts from 1
        standings_data.append({
            "position": rank,
            "club_id": club.club_id, # Useful for client-side highlighting
            "club_name": club.club_name,
            "played": club.wins + club.draws + club.losses, # Calculated Played matches
            "wins": club.wins,
            "draws": club.draws,
            "losses": club.losses,
            "goals_scored": club.goals_scored,
            "goals_conceded": club.goals_conceded,
            "goal_difference": club.goals_scored - club.goals_conceded,
            "points": club.points,
        })

    print(f"Retrieved standings for tournament {tournament_id} with {len(standings_data)} clubs.")
    return standings_data

def handle_get_club_training(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to get the training settings for a specific tournament club."""
    club_id = payload.get('club_id')
    if not club_id:
        raise ValueError("Missing 'club_id' in payload for get_club_training request.")

    # Find the club and eagerly load its training settings
    tournament_club = session.query(TournamentClub).options(
        joinedload(TournamentClub.training)
    ).filter(
        TournamentClub.club_id == club_id
    ).first()

    if not tournament_club:
        raise ValueError(f"Tournament club with ID {club_id} not found.")

    if not tournament_club.training:
        # Should not happen if training is created with the club, but handle defensively
        print(f"Warning: Training settings not found for club {club_id}. Returning default.")
        return {"intensity": 3, "focus_area": TrainingFocusEnum.BALANCED.value} # Example defaults

    # Convert training object to a dictionary for the response
    training_data = tournament_club.training.to_dict()
    print(f"Retrieved training data for club_id {club_id}: {training_data}")
    return training_data

def handle_update_club_training(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to update training intensity or focus area."""
    club_id = payload.get('club_id')
    new_intensity = payload.get('intensity') # Optional
    new_focus_str = payload.get('focus_area') # Optional, sent as string value

    if club_id is None:
        raise ValueError("Missing 'club_id'.")
    if new_intensity is None and new_focus_str is None:
        raise ValueError("Must provide either 'intensity' or 'focus_area' to update.")

    # Find the club and its training settings
    tournament_club = session.query(TournamentClub).options(
        joinedload(TournamentClub.training)
    ).filter(
        TournamentClub.club_id == club_id
    ).first()

    if not tournament_club or not tournament_club.training:
        raise ValueError(f"Club or training settings not found for ID {club_id}.")

    training_settings = tournament_club.training
    updated_fields = []

    # Update Intensity
    if new_intensity is not None:
        try:
            intensity_val = int(new_intensity)
            if 1 <= intensity_val <= 10:
                if training_settings.intensity != intensity_val:
                    training_settings.intensity = intensity_val
                    updated_fields.append("intensity")
            else:
                raise ValueError("Intensity must be between 1 and 10.")
        except (ValueError, TypeError):
            raise ValueError("Invalid intensity value provided.")

    # Update Focus Area
    if new_focus_str is not None:
        try:
            # Convert string back to enum member
            new_focus_enum = TrainingFocusEnum(new_focus_str)
            if training_settings.focus_area != new_focus_enum:
                training_settings.focus_area = new_focus_enum
                updated_fields.append("focus_area")
        except ValueError:
            # This happens if the string doesn't match any enum value
            raise ValueError(f"Invalid focus_area value provided: {new_focus_str}")

    if not updated_fields:
        return {"message": "No changes detected."} # Nothing was actually updated

    try:
        session.commit()
        print(f"Updated training for club {club_id}: {', '.join(updated_fields)}")
        # Return the updated settings
        return training_settings.to_dict()
    except Exception as e:
        session.rollback()
        print(f"Error committing training update for club {club_id}: {e}")
        raise RuntimeError("Failed to save training settings.")

def handle_update_club_tactics(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles request to update club tactics: formation, playstyle, specialists."""
    club_id = payload.get('club_id')
    new_formation_str = payload.get('formation') # e.g., "4-4-2"
    new_playstyle_str = payload.get('play_style') # e.g., "balanced"
    new_captain_id = payload.get('captain_id')
    new_fk_taker_id = payload.get('free_kick_taker_id')
    new_pen_taker_id = payload.get('penalty_taker_id')
    new_corner_taker_id = payload.get('corner_taker_id')

    if club_id is None: raise ValueError("Missing 'club_id'.")

    new_formation_enum = None
    if new_formation_str:
        try:
            new_formation_enum = FormationEnum(new_formation_str)
        except ValueError:
            raise ValueError(f"Invalid formation value: {new_formation_str}")

    new_playstyle_enum = None
    if new_playstyle_str:
        try:
            new_playstyle_enum = PlayStyleEnum(new_playstyle_str)
        except ValueError:
            raise ValueError(f"Invalid play_style value: {new_playstyle_str}")

    # Fetch club and tactics
    club = session.query(TournamentClub).options(
        joinedload(TournamentClub.tactics)
    ).filter_by(club_id=club_id).first()

    if not club or not club.tactics:
        raise ValueError(f"Club or tactics not found for ID {club_id}.")

    tactics = club.tactics
    old_formation_enum = tactics.formation
    formation_changed = new_formation_enum is not None and new_formation_enum != old_formation_enum

    # --- Update Tactics Record ---
    if new_formation_enum:
        tactics.formation = new_formation_enum
    if new_playstyle_enum:
        tactics.play_style = new_playstyle_enum
    # Update specialists - Allow None values to clear a role
    if 'captain_id' in payload: tactics.captain_id = new_captain_id
    if 'free_kick_taker_id' in payload: tactics.free_kick_taker_id = new_fk_taker_id
    if 'penalty_taker_id' in payload: tactics.penalty_taker_id = new_pen_taker_id
    if 'corner_taker_id' in payload: tactics.corner_taker_id = new_corner_taker_id

    # --- Regenerate Lineup if Formation Changed ---
    if formation_changed:
        print(f"Formation changed for club {club_id} to {new_formation_enum.value}. Regenerating lineup...")
        # Use the DataManager helper
        new_starters_json, new_subs_json, new_specialists = data_manager.regenerate_lineup_for_club(
            club_id=club_id,
            new_formation=new_formation_enum
        )
        tactics.starting_players = new_starters_json
        tactics.substitutes = new_subs_json
        # Overwrite specialists with newly calculated defaults for the new formation
        tactics.captain_id = new_specialists.get("captain_id")
        tactics.free_kick_taker_id = new_specialists.get("free_kick_taker_id")
        tactics.penalty_taker_id = new_specialists.get("penalty_taker_id")
        tactics.corner_taker_id = new_specialists.get("corner_taker_id")
        print(f"Lineup regenerated. New default specialists assigned: {new_specialists}")

    try:
        session.commit()
        print(f"Successfully updated tactics for club {club_id}.")
        # Return the final state of the tactics after potential regeneration
        return tactics.to_dict()
    except Exception as e:
        session.rollback()
        print(f"Error committing tactics update for club {club_id}: {e}")
        raise RuntimeError("Failed to save tactics settings.")

def handle_get_transfer_list(payload: Dict[str, Any], session) -> List[Dict[str, Any]]:
    """
    Handles request to get the list of players available on the transfer market.
    Excludes players from the user's own active club.
    """
    tournament_id = payload.get('tournament_id')
    # active_club_id = payload.get('active_club_id')

    if not tournament_id:
        raise ValueError("Missing 'tournament_id' for transfer list request.")


    # Query TransferListing, join with TournamentPlayer
    # Filter by tournament_id
    listed_players_query = session.query(TransferListing, TournamentPlayer) \
        .join(TournamentPlayer, TransferListing.player_id == TournamentPlayer.player_id) \
        .filter(TransferListing.tournament_id == tournament_id)


    results = listed_players_query.all()

    transfer_list_data = []
    for listing, player in results:
        player_data = player.to_dict()  # Get base player data
        player_data['asking_price'] = listing.asking_price
        # 'club_id' in player_data already refers to player.club_id (listing club)
        transfer_list_data.append(player_data)

    print(f"Retrieved {len(transfer_list_data)} players for transfer list in tournament {tournament_id}.")
    return transfer_list_data


def handle_get_player_profile_details(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """
    Handles request to get detailed information for a specific player,
    including their transfer listing status if applicable.
    """
    player_id = payload.get('player_id')
    tournament_id = payload.get('tournament_id')  # For transfer status context

    if not player_id or not tournament_id:
        raise ValueError("Missing 'player_id' or 'tournament_id' for player profile request.")

    player = session.query(TournamentPlayer).filter_by(player_id=player_id).first()
    if not player:
        raise ValueError(f"Player with ID {player_id} not found.")

    player_data = player.to_dict()  # Base player details

    # Check transfer listing status specifically for this tournament
    listing = session.query(TransferListing).filter_by(
        player_id=player_id,
        tournament_id=tournament_id
    ).first()

    if listing:
        player_data['is_on_transfer_list'] = True
        player_data['asking_price'] = listing.asking_price
        player_data['listing_id'] = listing.listing_id  # Useful for remove action
    else:
        player_data['is_on_transfer_list'] = False
        player_data['asking_price'] = None
        player_data['listing_id'] = None

    # The 'club_name' in player_data from player.to_dict() is already the player's current team.
    print(f"Retrieved profile details for player {player_id} in tournament {tournament_id}.")
    return player_data


def handle_buy_player(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles a club buying a player from the transfer list."""
    buying_club_id = payload.get('buying_club_id')
    player_id_to_buy = payload.get('player_id')
    listing_id = payload.get('listing_id')  # The ID of the TransferListing record
    tournament_id = payload.get('tournament_id')  # Context for the transaction

    if not all([buying_club_id, player_id_to_buy, listing_id, tournament_id]):
        raise ValueError("Missing required fields for buying a player.")

    # --- Fetch relevant records ---
    buyer_club = session.query(TournamentClub).filter_by(club_id=buying_club_id, tournament_id=tournament_id).first()
    player_to_buy = session.query(TournamentPlayer).filter_by(player_id=player_id_to_buy).first()
    transfer_listing = session.query(TransferListing).filter_by(
        listing_id=listing_id,
        player_id=player_id_to_buy,
        tournament_id=tournament_id
    ).first()

    if not buyer_club:
        raise ValueError(f"Buying club with ID {buying_club_id} not found in tournament {tournament_id}.")
    if not player_to_buy:
        raise ValueError(f"Player with ID {player_id_to_buy} not found.")
    if not transfer_listing:
        raise ValueError(
            f"Transfer listing for player {player_id_to_buy} (listing ID {listing_id}) not found or already processed.")

    selling_club_id = player_to_buy.club_id
    if selling_club_id == buying_club_id:
        raise ValueError("Cannot buy a player from your own club.")

    seller_club = session.query(TournamentClub).filter_by(club_id=selling_club_id, tournament_id=tournament_id).first()
    if not seller_club:  # Should exist if player belongs to a club in the tournament
        raise ValueError(f"Selling club (ID {selling_club_id}) for player {player_id_to_buy} not found.")

    asking_price = transfer_listing.asking_price

    # --- Perform transaction ---
    if buyer_club.budget < asking_price:
        raise ValueError("Insufficient budget to buy this player.")

    # 1. Update budgets
    buyer_club.budget -= asking_price
    seller_club.budget += asking_price  # Seller gets the money

    # 2. Update player's club allegiance
    old_club_name = player_to_buy.team_name
    player_to_buy.club_id = buying_club_id
    player_to_buy.team_name = buyer_club.club_name  # Update team name on player record

    # 3. Remove the transfer listing
    session.delete(transfer_listing)


    try:
        session.commit()
        print(
            f"Player {player_id_to_buy} ({player_to_buy.name}) bought by club {buying_club_id} ({buyer_club.club_name}) from {old_club_name} for {asking_price}.")
        # Return updated budget for the buyer
        return {
            "message": "Player purchased successfully.",
            "updated_budget": buyer_club.budget,
            "bought_player_id": player_id_to_buy,
            "new_club_id_for_player": buying_club_id
        }
    except Exception as e:
        session.rollback()
        print(f"Error during buy_player commit: {e}")
        raise RuntimeError("Failed to finalize player purchase.")


def handle_list_player_for_transfer(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles a club listing one of their players for transfer."""
    club_id = payload.get('club_id')
    player_id_to_list = payload.get('player_id')
    asking_price = payload.get('asking_price')
    tournament_id = payload.get('tournament_id')

    if not all([club_id, player_id_to_list, asking_price, tournament_id]):
        raise ValueError("Missing required fields for listing a player.")

    try:
        price = int(asking_price)
        if price <= 0:
            raise ValueError("Asking price must be positive.")
    except ValueError:
        raise ValueError("Invalid asking price format.")

    # --- Validations ---
    player = session.query(TournamentPlayer).filter_by(player_id=player_id_to_list, club_id=club_id).first()
    if not player:
        raise ValueError(f"Player {player_id_to_list} not found in club {club_id}.")

    existing_listing = session.query(TransferListing).filter_by(
        player_id=player_id_to_list,
        tournament_id=tournament_id
    ).first()
    if existing_listing:
        raise ValueError(f"Player {player_id_to_list} is already on the transfer list in this tournament.")

    # Check squad size constraint: club's players count - club's transfer listed players count > 18
    current_player_count = session.query(TournamentPlayer).filter_by(club_id=club_id).count()
    current_listed_count = session.query(TransferListing) \
        .join(TournamentPlayer, TransferListing.player_id == TournamentPlayer.player_id) \
        .filter(TournamentPlayer.club_id == club_id, TransferListing.tournament_id == tournament_id) \
        .count()

    # If this player is listed, the number of non-listed players will be current_player_count - (current_listed_count + 1)
    if (current_player_count - (current_listed_count + 1)) < 18:  # Assuming 18 is the minimum non-listed squad
        raise ValueError("Cannot list more players. Minimum active squad size (18) would be breached.")

    # --- Create Listing ---
    new_listing = TransferListing(
        tournament_id=tournament_id,
        player_id=player_id_to_list,
        asking_price=price,
        status=TransferStatus.LISTED,  # Default status
        listed_at=datetime.now(timezone.utc)
    )
    session.add(new_listing)

    try:
        session.commit()
        print(f"Player {player_id_to_list} listed by club {club_id} for {price} in tournament {tournament_id}.")
        return {
            "message": "Player listed successfully.",
            "listing_id": new_listing.listing_id,
            "player_id": player_id_to_list,
            "asking_price": price
        }
    except Exception as e:
        session.rollback()
        print(f"Error committing player listing: {e}")
        raise RuntimeError("Failed to list player for transfer.")


def handle_remove_player_from_transfer_list(payload: Dict[str, Any], session) -> Dict[str, Any]:
    """Handles a club removing their player from the transfer list."""
    club_id = payload.get('club_id')  # Club initiating the removal (must own the player)
    player_id_to_remove = payload.get('player_id')
    listing_id = payload.get('listing_id')  # Specific listing to remove
    tournament_id = payload.get('tournament_id')

    if not all([club_id, player_id_to_remove, listing_id, tournament_id]):
        raise ValueError("Missing required fields for removing player from list.")

    # --- Find and Validate Listing ---
    listing = session.query(TransferListing) \
        .join(TournamentPlayer, TransferListing.player_id == TournamentPlayer.player_id) \
        .filter(
        TransferListing.listing_id == listing_id,
        TransferListing.player_id == player_id_to_remove,
        TransferListing.tournament_id == tournament_id,
        TournamentPlayer.club_id == club_id  # Ensure the club owns the player
    ).first()

    if not listing:
        raise ValueError(
            f"Transfer listing (ID {listing_id}) for player {player_id_to_remove} not found, or not owned by club {club_id}.")

    # --- Remove Listing ---
    session.delete(listing)
    try:
        session.commit()
        print(f"Player {player_id_to_remove} removed from transfer list by club {club_id}.")
        return {
            "message": "Player removed from transfer list successfully.",
            "player_id": player_id_to_remove
        }
    except Exception as e:
        session.rollback()
        print(f"Error committing removal from transfer list: {e}")
        raise RuntimeError("Failed to remove player from transfer list.")

def handle_get_tournament_details(payload: Dict[str, Any], session) -> Dict[str, Any]:
    tournament_id = payload.get('tournament_id')
    if not tournament_id:
        raise ValueError("Missing 'tournament_id'")

    tournament = session.query(Tournament).filter_by(tournament_id=tournament_id).first()
    if not tournament:
        raise ValueError(f"Tournament with ID {tournament_id} not found.")

    # Determine if finished: all matches for this tournament are simulated
    total_matches_in_tournament = session.query(TournamentMatch) \
        .filter_by(tournament_id=tournament_id).count()

    simulated_matches_in_tournament = session.query(TournamentMatch) \
        .filter_by(tournament_id=tournament_id, is_simulated=True).count()

    is_finished = False
    if total_matches_in_tournament > 0 and total_matches_in_tournament == simulated_matches_in_tournament:
        is_finished = True

    data = tournament.to_dict()
    data["is_finished"] = is_finished  # Add the calculated finished status
    # 'is_started' is already part of tournament model and to_dict() if you add it there.
    # If not, add it here:
    data["is_started"] = tournament.is_started

    return data


def handle_get_match_details(payload: Dict[str, Any], session) -> Dict[str, Any]:
    match_id = payload.get('match_id')
    if not match_id:
        raise ValueError("Missing 'match_id' for get_match_details request.")

    match = session.query(TournamentMatch).options(
        joinedload(TournamentMatch.home_club),  # For home_club_name
        joinedload(TournamentMatch.away_club),  # For away_club_name
        joinedload(TournamentMatch.events).joinedload(TournamentMatchEvent.player),  # For player name in events
        joinedload(TournamentMatch.events).joinedload(TournamentMatchEvent.club)  # For club name in events
    ).filter_by(match_id=match_id).first()

    if not match:
        raise ValueError(f"Match with ID {match_id} not found.")

    if not match.is_simulated:
        # Or return basic info but indicate not fully detailed yet
        raise ValueError(f"Match ID {match_id} has not been simulated yet. Details unavailable.")

    match_info = match.to_dict(include_clubs=True)  # Gets basic match data

    events_data = []
    for event_obj in match.events:
        event_dict = event_obj.to_dict()
        # Augment with player/club names if they exist for the event
        if event_obj.player:
            event_dict["player_name"] = event_obj.player.name
        if event_obj.club:
            event_dict["event_club_name"] = event_obj.club.club_name
        events_data.append(event_dict)

    # Sort events by minute
    events_data.sort(key=lambda e: e.get("minute", 0))

    return {
        "match_info": match_info,
        "events": events_data
    }

def handle_leave_club(payload: Dict[str, Any], session) -> Dict[str, Any]:
    user_id = payload.get('user_id')
    club_id_to_leave = payload.get('club_id')

    if not user_id or not club_id_to_leave:
        raise ValueError("Missing user_id or club_id.")

    # Find the specific club managed by this user
    club = session.query(TournamentClub).options(
        joinedload(TournamentClub.tournament) # Load tournament to check status
    ).filter_by(
        club_id=club_id_to_leave,
        user_id=user_id
    ).first()

    if not club:
        raise ValueError("Club not found or not managed by this user.")

    # --- Check if tournament is finished ---
    tournament = club.tournament
    if not tournament:
         raise RuntimeError(f"Tournament data missing for club {club_id_to_leave}.")

    total_matches = session.query(TournamentMatch).filter_by(tournament_id=tournament.tournament_id).count()
    simulated_matches = session.query(TournamentMatch).filter_by(tournament_id=tournament.tournament_id, is_simulated=True).count()
    is_finished = total_matches > 0 and total_matches == simulated_matches

    if not is_finished:
        raise ValueError("Cannot leave club: Tournament is still ongoing.")
    # --- End Check ---

    club_name = club.club_name # Store name before clearing


    club.user_id = None
    club.is_ai_controlled = True

    try:
        session.commit()
        print(f"User {user_id} left club {club_name} (ID: {club_id_to_leave}). Slot reverted to AI.")
        return {"message": "Successfully left club.", "left_club_name": club_name}
    except Exception as e:
        session.rollback()
        print(f"Error committing leave club for User {user_id}, Club {club_id_to_leave}: {e}")
        raise RuntimeError("Failed to save changes when leaving club.")

# --- Action Map ---
action_handler_map = {
    "register_user": handle_register_user,
    "login_user": handle_login_user,
    "get_user_clubs": handle_get_user_clubs,
    "get_squad": handle_get_squad,
    "get_available_leagues": handle_get_available_leagues,
    "get_league_details": handle_get_league_details,
    "join_league_club": handle_join_league_club,
    "create_tournament": handle_create_tournament,
    "get_fixtures": handle_get_fixtures,
    "get_club_tactics": handle_get_club_tactics,
    "update_lineup_slot": handle_update_lineup_slot,
    "swap_lineup_players": handle_swap_lineup_players,
    "get_standings": handle_get_standings,
    "get_club_training": handle_get_club_training,
    "update_club_training": handle_update_club_training,
    "update_club_tactics": handle_update_club_tactics,
    "get_transfer_list": handle_get_transfer_list,
    "get_player_profile_details": handle_get_player_profile_details,
    "buy_player": handle_buy_player,
    "list_player_for_transfer": handle_list_player_for_transfer,
    "remove_player_from_transfer_list": handle_remove_player_from_transfer_list,
    "get_tournament_details": handle_get_tournament_details,
    "get_match_details": handle_get_match_details,
    "leave_club": handle_leave_club,
}

# --- Client Handling Thread (mostly unchanged) ---
def handle_client(conn: socket.socket, addr):
    print(f"Connected by {addr}")
    session = SessionLocal() # New session per thread
    buffer = ""
    try:
        while True:
            data = conn.recv(4096) # Increased buffer size
            if not data:
                print(f"Client {addr} disconnected gracefully.")
                break

            buffer += data.decode('utf-8')

            while '\n' in buffer:
                message, buffer = buffer.split('\n', 1)
                if not message: continue # Skip empty messages if split results in empty string first

                print(f"Received from {addr}: {message[:200]}{'...' if len(message)>200 else ''}") # Log truncated message
                response = {"status": "error", "data": None, "message": "Invalid request"}

                try:
                    request = json.loads(message)
                    action = request.get("action")
                    payload = request.get("payload", {})

                    if action in action_handler_map:
                        handler = action_handler_map[action]
                        # Execute handler
                        result_data = handler(payload, session) # Pass session
                        response = {"status": "success", "data": result_data, "message": f"Action '{action}' success."}
                    else:
                        response["message"] = f"Unknown action: {action}"

                except json.JSONDecodeError:
                    response["message"] = "Invalid JSON received."
                except ValueError as ve: # Catch specific input/logic errors from handlers
                    response["message"] = f"Error: {ve}"
                    session.rollback() # Rollback DB changes on error
                except Exception as e:
                    response["message"] = f"Server Error: An unexpected error occurred." # Generic msg to client
                    session.rollback()
                    print(f"!!! Unhandled Error handling request from {addr} for action '{action}' !!!")
                    import traceback
                    traceback.print_exc() # Log detailed error on server

                # Send response back
                response_json = json.dumps(response) + '\n'
                conn.sendall(response_json.encode('utf-8'))
                # print(f"Sent to {addr}: {response_json.strip()}") # Less verbose logging

    except (socket.error, ConnectionResetError, BrokenPipeError) as e:
        print(f"Network error with {addr}: {e}")
    except Exception as e:
        print(f"Unexpected error in client handling loop for {addr}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"Closing connection to {addr}")
        session.close() # Ensure session is closed
        conn.close()

# --- Main Server Loop ---
def main():

    scheduler = GameScheduler(data_manager)
    scheduler.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Server listening on {HOST}:{PORT}...")

            while True:
                # Check if scheduler is still alive, restart if not
                if scheduler.thread is None or not scheduler.thread.is_alive():
                   print("Scheduler thread died. Restarting...")
                   scheduler.start()
                conn, addr = s.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                client_thread.start()

        except OSError as e:
             print(f"Error binding or listening on {HOST}:{PORT}: {e}")
        except KeyboardInterrupt:
             print("\nServer shutting down...")
        finally:
             print("Stopping scheduler...")
             scheduler.stop()
             print("Server stopped.")


if __name__ == '__main__':
    main()