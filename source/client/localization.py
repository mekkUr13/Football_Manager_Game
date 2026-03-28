import json
from typing import Any, Optional

from common.constants import ROOT_PATH
import datetime as py_datetime
from datetime import timezone

DEFAULT_LANGUAGE = "ENGLISH"
DEFAULT_CURRENCY = "EUR"
SETTINGS_FILE = ROOT_PATH / "settings.json"
DEFAULT_FULLSCREEN = False

# --- Language Data ---
labels_dict = {
    "ENGLISH": {
        "SETTINGS": "Settings",
        "BACK": "Back",
        "CONFIRM": "Confirm",
        "CANCEL": "Cancel",
        "ERROR": "Error",
        "SUCCESS": "Success",
        "LOADING": "Loading...",
        "PAGE": "Page",
        "SELECT": "Select",
        "LOGIN": "Login",
        "REGISTER": "Register",
        "USERNAME": "Username",
        "PASSWORD": "Password",
        "CONFIRM_PASSWORD": "Confirm Password",
        "SHOW_PASSWORD": "Show Password",
        "EMAIL": "Email",
        "MAIN_MENU": "Main Menu",
        "NEW_CLUB": "New Club",
        "SELECT_LEAGUE": "Select League",
        "SELECT_CLUB": "Select Club",
        "AVAILABLE_LEAGUES": "Available Leagues (Not Full / Not Started)",
        "LEAGUE_DETAILS": "League Details",
        "JOIN_CLUB": "Join Club",
        "TAKEN_CLUBS": "Taken Clubs",
        "AVAILABLE_CLUBS": "Available Clubs",
        "CHOOSE_CLUB": "Choose a Club:",
        "WELCOME": "Welcome",
        "SELECT_OR_NEW": "Select a team   :",

        # Settings Screen
        "LANGUAGE": "Language",
        "CURRENCY": "Currency",
        "APPLY_SETTINGS": "Apply Settings",

        "CREATE_LEAGUE": "Create New League",
        "TOURNAMENT_CREATION": "Create New Tournament",
        "TOURNAMENT_NAME": "Tournament Name",
        "NUMBER_OF_CLUBS": "Number of Clubs (e.g., 4, 6, 8...)",
        "START_DELAY_HOURS": "Start Delay (Hours from now)",
        "ROUND_INTERVAL_HOURS": "Time Between Rounds (Hours)",
        "CREATE": "Create",
        "INVALID_INPUT": "Invalid input. Please check values.",
        "CREATE_TOURNAMENT_SUCCESS": "Tournament '{name}' created successfully!",
        "CREATE_TOURNAMENT_FAILED": "Failed to create tournament: {error}",
        "CONNECTION_FAILED": "Server connection failed.",
        "NEED_ACCOUNT": "Need an account? Register",
        "HAVE_ACCOUNT": "Already have an account? Login",
        "SQUAD_EMPTY": "Squad is empty.",
        "INJURED": "Inj",
        "SUSPENDED": "Sus",
        "FIT": "Fit",
        "NAME": "Name",
        "POS": "Pos",
        "AGE": "Age",
        "OVR": "OVR",
        "VALUE": "Value",
        "STATUS": "Status",
        "FULLSCREEN": "Fullscreen",
        "SUBSTITUTES": "Substitutes",
        "SUB": "SUB",

        # Game Menu Buttons
        "SQUAD": "Squad",
        "LINEUP": "Lineup",
        "TRANSFERS": "Transfers",
        "TRAINING": "Training",
        "FIXTURES": "Fixtures",
        "STANDINGS": "Standings",
        "NEWS": "News",
        "TACTICS": "Tactics",

        # Login/Register Specific
        "LOGIN_FAILED": "Login Failed: Invalid credentials or server error.",
        "REGISTRATION_SUCCESS": "Registration Successful! You can now log in.",
        "REGISTRATION_FAILED": "Registration Failed: Username/Email may be taken or server error.",
        "PASSWORDS_DONT_MATCH": "Passwords do not match.",
        "FIELD_REQUIRED": "Field required.",

        # Club Joining
        "JOIN_SUCCESS": "Successfully joined club!",
        "JOIN_FAILED": "Failed to join club. It might be taken or an error occurred.",
        "MAX_CLUBS_REACHED": "Maximum number of clubs (3) reached.",

        "WELCOME_MAIN_MENU": "Select a Club or Start a New Career",

        "LANG_ENGLISH": "English",
        "LANG_MAGYAR": "Magyar",

        "VERSUS_SHORT": "vs",

        "ROUND": "Round",
        "HOME": "Home",
        "SCORE": "Score",
        "AWAY": "Away",
        "TIME": "Time",

        "STAT_AVG_OVR": "Avg. OVR:",
        "STAT_VALUE": "Value:",
        "STAT_PLAYERS": "Players:",
        "MONTHS_SHORT": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],

        "APP_TITLE": "MFS",
        "SLOTS_LABEL": "Slots:",
        "DATE_FORMAT_SHORT": "Starts: %Y-%m-%d %H:%M %Z",
        "DATE_FORMAT_FIXTURE": "%b %d, %H:%M %Z",

        "NO_LEAGUES_FOUND": "No leagues available.",
        "INVALID_DATE": "Érvénytelen idő",
        "LEAGUES_LOAD_FAILED": "Failed to load leagues.",
        "SELECT_CLUB_FIRST": "Please select an available club!",
        "INTERNAL_ERROR": "Internal error.",
        "LEAGUE_DETAIL_FAILED": "Failed to load league details.",
        "JOINING_CLUB": "Joining...",
        "NO_RESPONSE": "No response from server",
        "CLUB_JUST_TAKEN": "This club has just been taken!",
        "SEARCH_CLUB": "Search Club...",
        "SQUAD_LOAD_FAILED": "Failed to load squad.",
        "NO_FIXTURES": "No fixtures loaded.",
        "FIXTURES_LOAD_FAILED": "Failed to load fixtures.",

        "TACTICS_LOAD_FAILED": "Failed to load club tactics.",
        "LINEUP_EMPTY": "Lineup not set or formation empty.",
        "EMPTY_SLOT": "- Empty -",
        "POS_PERFECT": "Perfect",
        "POS_GOOD": "Good",
        "POS_POOR": "Poor",
        "POS_EMPTY": "Empty",
        "SUITABILITY" : "Suitability",
        "LOGOUT": "Logout",

        "PLAYER_POS": "Player Pos",
        "ALT_POS": "Alt. Pos",

        "SELECT_PLAYER": "Select Player",
        "NO_PLAYERS_AVAILABLE": "No eligible players available.",
        "PLAYER_POS_SHORT": "Pos",
        "REPLACE_SUB": "Replace Substitute",
        "LINEUP_UPDATE_FAILED": "Failed to update lineup.",
        "ROLE": "Role",
        "ROLE_STARTER": "Starter",
        "ROLE_SUB": "Sub",
        "ROLE_RESERVE": "Reserve",

        "STANDINGS_TITLE": "Standings",
        "STANDINGS_LOAD_FAILED": "Failed to load standings.",
        "NO_STANDINGS_DATA": "No standings data available.",
        "COL_TEAM": "Team",
        "COL_P": "P", # Played
        "COL_GS": "GS", # Goals Scored
        "COL_GA": "GA", # Goals Against
        "COL_GD": "GD", # Goal Difference
        "COL_W": "W",   # Wins
        "COL_D": "D",   # Draws
        "COL_L": "L",   # Losses
        "COL_PTS": "Pts", # Points

        # Training Screen
        "TRAINING_TITLE": "Training Settings",
        "TRAINING_LOAD_FAILED": "Failed to load training settings.",
        "TRAINING_UPDATE_FAILED": "Failed to update training settings.",
        "TRAINING_UPDATE_SUCCESS": "Training settings updated.",
        "LABEL_INTENSITY": "Intensity",
        "LABEL_FOCUS_AREA": "Focus Area",
        # Focus Area Names (match enum values but localized/formatted)
        "FOCUS_BALANCED": "Balanced",
        "FOCUS_ATTACK": "Attack",
        "FOCUS_DEFENSE": "Defense",
        "FOCUS_STAMINA": "Stamina",
        "FOCUS_TACTICAL": "Tactical",
        "FOCUS_TECHNICAL": "Technical",
        "FOCUS_MENTALITY": "Mentality",
        "FOCUS_PHYSICAL": "Physical",

        # Tactics Screen
        "TACTICS_TITLE": "Tactics",
        "TACTICS_UPDATE_FAILED": "Failed to update tactics.",
        "TACTICS_UPDATE_SUCCESS": "Tactics updated successfully.",
        "LABEL_FORMATION": "Formation",
        "LABEL_PLAY_STYLE": "Play Style",
        "LABEL_CAPTAIN": "Captain",
        "LABEL_FK_TAKER": "Free Kick Taker",
        "LABEL_PEN_TAKER": "Penalty Taker",
        "LABEL_CORNER_TAKER": "Corner Taker",
        "BUTTON_APPLY_CHANGES": "Apply Changes",
        "ROLE_NOT_SET": "- Not Set -",
        "SELECT_ROLE_PLAYER": "Select {role_name}",  # Placeholder for role
        "PLAYER_SELECT_STARTERS_ONLY": "Select Starter for {role_name}",  # Title for player select
        # Play Style Names (match enum values but localized/formatted)
        "STYLE_DEFENSIVE": "Defensive",
        "STYLE_BALANCED": "Balanced",
        "STYLE_ATTACKING": "Attacking",
        "STYLE_HIGH_PRESS": "High Press",
        "STYLE_COUNTER_ATTACK": "Counter Attack",
        "STYLE_POSSESSION": "Possession",
        "STYLE_WIDE": "Wide",
        "STYLE_NARROW": "Narrow",

        "BUDGET_LABEL": "Budget",

        "TRANSFERS_TITLE": "Transfer Market",
        "COL_ASKING_PRICE": "Asking Price",
        "SECTION_GOALKEEPERS": "Goalkeepers",
        "SECTION_DEFENDERS": "Defenders",
        "SECTION_MIDFIELDERS": "Midfielders",
        "SECTION_ATTACKERS": "Attackers",
        "TRANSFER_LIST_EMPTY": "Transfer list is currently empty.",
        "TRANSFER_LIST_LOAD_FAILED": "Failed to load transfer list.",

        "PLAYER_PROFILE_TITLE": "Player Profile",
        "ATTR_CLUB": "Club",
        "ATTR_PREFERRED_FOOT": "Preferred Foot",
        "ATTR_WEAK_FOOT": "Weak Foot",
        "ATTR_SKILL_MOVES": "Skill Moves",
        "ATTR_ALT_POSITIONS": "Alt. Positions",
        "ATTR_HEIGHT": "Height",
        "ATTR_WEIGHT": "Weight",
        "ATTR_FITNESS": "Fitness",
        "ATTR_FORM": "Form",
        "ATTR_PLAY_STYLES": "Play Styles",
        "ATTR_YELLOW_CARDS": "Yellow Cards",
        "ATTR_RED_CARDS": "Red Cards",
        "ATTR_GOALS": "Goals",
        "ATTR_ASSISTS": "Assists",
        "ATTR_CLEAN_SHEETS": "Clean Sheets",
        "ATTR_MATCHES_PLAYED": "Matches Played",
        "ATTR_AVG_RATING": "Avg. Rating",
        "ATTR_MOTM": "MOTM Awards",
        "ATTR_GROWTH": "Growth",
        # Base Attributes (Outfield)
        "BASE_ATTR_PACE": "Pace",
        "BASE_ATTR_SHOOTING": "Shooting",
        "BASE_ATTR_PASSING": "Passing",
        "BASE_ATTR_DRIBBLING": "Dribbling",
        "BASE_ATTR_DEFENSE": "Defense",
        "BASE_ATTR_PHYSICAL": "Physical",
        # Base Attributes (Goalkeeper)
        "BASE_ATTR_DIVING": "Diving",
        "BASE_ATTR_HANDLING": "Handling",
        "BASE_ATTR_KICKING": "Kicking",
        "BASE_ATTR_REFLEXES": "Reflexes",
        "BASE_ATTR_SPEED_GK": "Speed",
        "BASE_ATTR_POSITIONING_GK": "Positioning",
        # Buttons
        "BUTTON_BUY_PLAYER": "Buy Player",
        "BUTTON_LIST_FOR_TRANSFER": "List for Transfer",
        "BUTTON_REMOVE_FROM_LIST": "Remove from List",
        "BUTTON_YES": "Yes",
        "BUTTON_NO": "No",
        # Confirmation Messages
        "CONFIRM_BUY_PLAYER": "Are you sure you want to buy {player_name} for {currency_symbol}{asking_price_formatted}?",
        "CONFIRM_LIST_PLAYER": "Are you sure you want to list {player_name} for transfer?",
        "CONFIRM_REMOVE_PLAYER_LISTING": "Are you sure you want to remove {player_name} from the transfer list?",
        # Transfer Action Feedback
        "TRANSFER_ACTION_SUCCESS": "{action} successful.", # e.g., "Player purchase successful."
        "TRANSFER_ACTION_FAILED": "{action} failed: {error}",
        "PLAYER_PURCHASE": "Player purchase",
        "PLAYER_LISTING": "Player listing",
        "PLAYER_LISTING_REMOVAL": "Player listing removal",
        "ERROR_INSUFFICIENT_BUDGET": "Insufficient budget to buy this player.",
        "ERROR_CANNOT_LIST_MORE_PLAYERS": "Cannot list more players. Minimum squad size (18 active players) must be maintained.",
        "ERROR_PLAYER_NOT_FOUND": "Player details could not be loaded.",
        "INPUT_ASKING_PRICE": "Enter Asking Price:",
        "INVALID_ASKING_PRICE": "Invalid asking price. Must be a positive number.",
        "NATION" : "Nationality",
        "CLUB_UNATTACHED": "Unattached",
        "RIGHT": "Right",
        "LEFT": "Left",
        "Enter amount...": "Enter amount...",

        "TOURNAMENT_NAME_REQUIRED": "Tournament Name is required.",
        "INVALID_NUM_CLUBS": "Number of clubs must be an even number between 2 and 32.", # Example range
        "INVALID_START_DELAY_POSITIVE": "Start delay must be a positive number of hours.",
        "INVALID_START_DELAY_FORMAT": "Invalid start delay format. Use numbers (e.g., 1 or 0.5).",
        "INVALID_ROUND_INTERVAL_POSITIVE": "Round interval must be a positive number of hours.",
        "INVALID_ROUND_INTERVAL_FORMAT": "Invalid round interval format. Use numbers (e.g., 24 or 0.1).",
        "START_DELAY_HOURS_FLOAT": "Start Delay (Hours, e.g., 1 or 0.1 for 6m)",
        "ROUND_INTERVAL_HOURS_FLOAT": "Time Between Rounds (Hours, e.g., 24 or 0.5)",
        "CLUB_FREE_AGENTS": "Free Agents",

        "LABEL_STATUS": "Status",
        "STATUS_STARTING": "Starting Soon",
        "STATUS_ONGOING": "Ongoing",
        "STATUS_FINISHED": "Finished",

        "BUTTON_LEAVE_CLUB": "Leave Club",
        "CONFIRM_LEAVE_CLUB": "Are you sure you want to leave {club_name}? This is irreversible.",
        "LEAVE_CLUB_SUCCESS": "You have left {club_name}.",
        "LEAVE_CLUB_FAILED": "Failed to leave club: {error}",

    },
    "MAGYAR": {
        # General UI
        "APP_TITLE": "MFS",
        "SETTINGS": "Beállítások",
        "BACK": "Vissza",
        "CONFIRM": "Megerősítés",
        "CANCEL": "Mégse",
        "ERROR": "Hiba",
        "SUCCESS": "Siker",
        "LOADING": "Töltés...",
        "PAGE": "Oldal",
        "SELECT": "Kiválaszt",
        "LOGIN": "Bejelentkezés",
        "REGISTER": "Regisztráció",
        "USERNAME": "Felhasználónév",
        "PASSWORD": "Jelszó",
        "CONFIRM_PASSWORD": "Jelszó Megerősítése",
        "SHOW_PASSWORD": "Jelszó Mutatása",
        "INVALID_EMAIL_FORMAT": "Érvénytelen email formátum.",
        "EMAIL": "E-mail",
        "MAIN_MENU": "Főmenü",
        "NEW_CLUB": "Új Klub",
        "SELECT_LEAGUE": "Bajnokság Választása",
        "SELECT_CLUB": "Klub Választása",
        "AVAILABLE_LEAGUES": "Elérhető Bajnokságok (Nem telt meg / Nem kezdődött el)",
        "LEAGUE_DETAILS": "Bajnokság Részletei",
        "JOIN_CLUB": "Csatlakozás a Klubhoz",
        "TAKEN_CLUBS": "Foglalt Klubok",
        "AVAILABLE_CLUBS": "Elérhető Klubok",
        "CHOOSE_CLUB": "Válassz egy Klubot:",

        # Settings Screen
        "LANGUAGE": "Nyelv",
        "CURRENCY": "Pénznem",
        "APPLY_SETTINGS": "Beállítások Alkalmazása",
        "LANG_ENGLISH": "English",  # Label for the English option
        "LANG_MAGYAR": "Magyar",  # Label for the Magyar option

        # Game Menu Buttons
        "SQUAD": "Keret",
        "LINEUP": "Felállás",
        "TRANSFERS": "Átigazolások",
        "TRAINING": "Edzés",
        "FIXTURES": "Meccsek",
        "STANDINGS": "Tabella",
        "NEWS": "Hírek",
        "TACTICS": "Taktika",

        # Login/Register Specific
        "LOGIN_FAILED": "Sikertelen bejelentkezés: Érvénytelen adatok vagy szerverhiba.",
        "REGISTRATION_SUCCESS": "Sikeres regisztráció! Most már bejelentkezhetsz.",
        "REGISTRATION_FAILED": "Sikertelen regisztráció: A felhasználónév/e-mail foglalt lehet vagy szerverhiba történt.",
        "PASSWORDS_DONT_MATCH": "A jelszavak nem egyeznek.",
        "FIELD_REQUIRED": "Mező kitöltése kötelező.",

        # Club Joining
        "JOIN_SUCCESS": "Sikeresen csatlakozott a klubhoz!",
        "JOIN_FAILED": "Nem sikerült csatlakozni a klubhoz. Lehet, hogy foglalt vagy hiba történt.",
        "MAX_CLUBS_REACHED": "Elérte a maximális klubok számát (3).",

        "WELCOME_MAIN_MENU": "Válassz Klubot vagy Kezdj Új Karriert",

        "CREATE_LEAGUE": "Új Bajnokság Létrehozása",
        "TOURNAMENT_CREATION": "Új Bajnokság Létrehozása",
        "TOURNAMENT_NAME": "Bajnokság Neve",
        "NUMBER_OF_CLUBS": "Klubok Száma (pl. 4, 6, 8...)",
        "START_DELAY_HOURS": "Kezdési Késleltetés (Óra mostantól)",
        "ROUND_INTERVAL_HOURS": "Körök Közti Idő (Óra)",
        "CREATE": "Létrehozás",
        "INVALID_INPUT": "Érvénytelen bemenet. Ellenőrizd az értékeket.",
        "CREATE_TOURNAMENT_SUCCESS": "A(z) '{name}' bajnokság sikeresen létrehozva!",
        "CREATE_TOURNAMENT_FAILED": "Bajnokság létrehozása sikertelen: {error}",
        "CONNECTION_FAILED": "Szerverkapcsolati hiba.",
        "NEED_ACCOUNT": "Nincs fiókod? Regisztrálj",
        "HAVE_ACCOUNT": "Van már fiókod? Jelentkezz be",
        "SQUAD_EMPTY": "A keret üres.",
        "INJURED": "Sér",
        "SUSPENDED": "Eltilt",
        "FIT": "Fitt",
        "NAME": "Név",
        "POS": "Poz",
        "AGE": "Kor",
        "OVR": "Ért",
        "VALUE": "Érték",
        "STATUS": "Állapot",

        "SLOTS_LABEL": "Hely:",
        "DATE_FORMAT_SHORT": "Kezdés: %Y.%m.%d %H:%M %Z",
        "DATE_FORMAT_FIXTURE": "%b %d, %H:%M %Z",
        "MONTHS_SHORT": ["Jan", "Feb", "Márc", "Ápr", "Máj", "Jún", "Júl", "Aug", "Szept", "Okt", "Nov", "Dec"],
        "INVALID_DATE": "Érvénytelen idő",
        "NO_LEAGUES_FOUND": "Nincs elérhető bajnokság.",
        "LEAGUES_LOAD_FAILED": "Bajnokságok betöltése sikertelen.",
        "SELECT_CLUB_FIRST": "Kérlek, válassz egy elérhető klubot!",
        "INTERNAL_ERROR": "Belső hiba.",
        "LEAGUE_DETAIL_FAILED": "Bajnokság részleteinek betöltése sikertelen.",
        "JOINING_CLUB": "Csatlakozás...",
        "NO_RESPONSE": "Nincs válasz a szervertől",
        "CLUB_JUST_TAKEN": "Ezt a klubot épp most foglalták el!",
        "ROUND": "Ford.",
        "HOME": "Hazai",
        "SCORE": "Eredmény",
        "AWAY": "Vendég",
        "TIME": "Idő",
        "VERSUS_SHORT": "vs",
        "NO_FIXTURES": "Nincsenek betöltött mérkőzések.",
        "FIXTURES_LOAD_FAILED": "Mérkőzések betöltése sikertelen.",
        "SQUAD_LOAD_FAILED": "Keret betöltése sikertelen.",
        "SEARCH_CLUB": "Klub keresése...", # For search bar placeholder
        "WELCOME": "Üdvözöllek",
        "SELECT_OR_NEW": "Válassz egy csapatot  :",

        "STAT_AVG_OVR": "Átlag Értékelés:",
        "STAT_VALUE": "Összérték:",
        "STAT_PLAYERS": "Játékosok:",
        "LOGOUT": "Kijelentkezés",

        "TACTICS_LOAD_FAILED": "Klub taktika betöltése sikertelen.",
        "LINEUP_EMPTY": "Felállás nincs beállítva vagy üres a formáció.",
        "EMPTY_SLOT": "- Üres -",
        "POS_PERFECT": "Tökéletes",
        "POS_GOOD": "Jó",
        "POS_POOR": "Gyenge",
        "POS_EMPTY": "Üres",
        "SUITABILITY" : "Alkalmasság",
        "FULLSCREEN": "Teljes képernyő",

        "PLAYER_POS": "Játékos P.",
        "ALT_POS": "Alt. Poz",
        "SELECT_PLAYER": "Játékos Választása",
        "NO_PLAYERS_AVAILABLE": "Nincs elérhető játékos.",
        "PLAYER_POS_SHORT": "Poz",
        "SUBSTITUTES": "Cserék",
        "SUB": "CSER",
        "REPLACE_SUB": "Csere Lecserélése",
        "LINEUP_UPDATE_FAILED": "Felállás frissítése sikertelen.",
        "ROLE": "Szerep",
        "ROLE_STARTER": "Kezdő",
        "ROLE_SUB": "Csere",
        "ROLE_RESERVE": "Tartalék",

        "STANDINGS_TITLE": "Tabella",
        "STANDINGS_LOAD_FAILED": "Tabella betöltése sikertelen.",
        "NO_STANDINGS_DATA": "Nincs elérhető tabella adat.",
        "COL_TEAM": "Csapat",
        "COL_P": "M",  # Played / Meccs
        "COL_GS": "RG",  # Goals Scored / Rúgott Gól
        "COL_GA": "KG",  # Goals Against / Kapott Gól
        "COL_GD": "GK",  # Goal Difference / Gólkülönbség
        "COL_W": "GY",  # Wins / Győzelem
        "COL_D": "D",  # Draws / Döntetlen
        "COL_L": "V",  # Losses / Vereség
        "COL_PTS": "P",  # Points / Pont

        # Training Screen
        "TRAINING_TITLE": "Edzés Beállítások",
        "TRAINING_LOAD_FAILED": "Edzés beállítások betöltése sikertelen.",
        "TRAINING_UPDATE_FAILED": "Edzés beállítások frissítése sikertelen.",
        "TRAINING_UPDATE_SUCCESS": "Edzés beállítások frissítve.",
        "LABEL_INTENSITY": "Intenzitás",
        "LABEL_FOCUS_AREA": "Fókusz Terület",
        # Focus Area Names
        "FOCUS_BALANCED": "Kiegyensúlyozott",
        "FOCUS_ATTACK": "Támadás",
        "FOCUS_DEFENSE": "Védekezés",
        "FOCUS_STAMINA": "Állóképesség",
        "FOCUS_TACTICAL": "Taktikai",
        "FOCUS_TECHNICAL": "Technikai",
        "FOCUS_MENTALITY": "Mentális",
        "FOCUS_PHYSICAL": "Fizikai",

        # Tactics Screen
        "TACTICS_TITLE": "Taktika",
        "TACTICS_UPDATE_FAILED": "Taktika frissítése sikertelen.",
        "TACTICS_UPDATE_SUCCESS": "Taktika sikeresen frissítve.",
        "LABEL_FORMATION": "Felállás",
        "LABEL_PLAY_STYLE": "Játékstílus",
        "LABEL_CAPTAIN": "Csapatkapitány",
        "LABEL_FK_TAKER": "Szabadrúgásrúgó",
        "LABEL_PEN_TAKER": "Büntetőrúgó",
        "LABEL_CORNER_TAKER": "Szögletrúgó",
        "BUTTON_APPLY_CHANGES": "Változtatások Alkalmazása",
        "ROLE_NOT_SET": "- Nincs Beállítva -",
        "SELECT_ROLE_PLAYER": "{role_name} Kiválasztása", # Placeholder for role
        "PLAYER_SELECT_STARTERS_ONLY": "Kezdő Játékos Választása: {role_name}", # Title for player select
        # Play Style Names
        "STYLE_DEFENSIVE": "Védekező",
        "STYLE_BALANCED": "Kiegyensúlyozott",
        "STYLE_ATTACKING": "Támadó",
        "STYLE_HIGH_PRESS": "Letámadás",
        "STYLE_COUNTER_ATTACK": "Kontratámadás",
        "STYLE_POSSESSION": "Labdabirtoklás",
        "STYLE_WIDE": "Szélső játék",
        "STYLE_NARROW": "Szűk játék",

        "BUDGET_LABEL": "Költségvetés",

        "TRANSFERS_TITLE": "Átigazolási Piac",
        "COL_ASKING_PRICE": "Kikiáltási Ár",
        "SECTION_GOALKEEPERS": "Kapusok",
        "SECTION_DEFENDERS": "Védők",
        "SECTION_MIDFIELDERS": "Középpályások",
        "SECTION_ATTACKERS": "Támadók",
        "TRANSFER_LIST_EMPTY": "Az átigazolási lista jelenleg üres.",
        "TRANSFER_LIST_LOAD_FAILED": "Az átigazolási lista betöltése sikertelen.",

        "PLAYER_PROFILE_TITLE": "Játékos Profil",
        "ATTR_CLUB": "Klub",
        "ATTR_PREFERRED_FOOT": " Erősebbik Láb",
        "ATTR_WEAK_FOOT": "Gyengébbik Láb",
        "ATTR_SKILL_MOVES": "Trükkmozdulat",
        "ATTR_ALT_POSITIONS": "Alternatív Poz.",
        "ATTR_HEIGHT": "Magasság",
        "ATTR_WEIGHT": "Súly",
        "ATTR_FITNESS": "Erőnlét",
        "ATTR_FORM": "Forma",
        "ATTR_PLAY_STYLES": "Stílus",
        "ATTR_YELLOW_CARDS": "Sárga Lapok",
        "ATTR_RED_CARDS": "Piros Lapok",
        "ATTR_GOALS": "Gólok",
        "ATTR_ASSISTS": "Gólpasszok",
        "ATTR_CLEAN_SHEETS": "Kapott Gól Nélküli Meccsek",
        "ATTR_MATCHES_PLAYED": "Játszott Meccsek",
        "ATTR_AVG_RATING": "Átlag Értékelés",
        "ATTR_MOTM": "Meccs Embere Díjak",
        "ATTR_GROWTH": "Fejlődés",
        # Base Attributes (Outfield)
        "BASE_ATTR_PACE": "Gyorsaság",
        "BASE_ATTR_SHOOTING": "Lövés",
        "BASE_ATTR_PASSING": "Passzolás",
        "BASE_ATTR_DRIBBLING": "Cselezés",
        "BASE_ATTR_DEFENSE": "Védekezés",
        "BASE_ATTR_PHYSICAL": "Fizikum",
        # Base Attributes (Goalkeeper)
        "BASE_ATTR_DIVING": "Vetődés",
        "BASE_ATTR_HANDLING": "Labdafogás",
        "BASE_ATTR_KICKING": "Kirúgás",
        "BASE_ATTR_REFLEXES": "Reflexek",
        "BASE_ATTR_SPEED_GK": "Sebesség",
        "BASE_ATTR_POSITIONING_GK": "Helyezkedés",
        # Buttons
        "BUTTON_BUY_PLAYER": "Játékos Megvétele",
        "BUTTON_LIST_FOR_TRANSFER": "Listázás a Piacra",
        "BUTTON_REMOVE_FROM_LIST": "Eltávolítás a Listáról",
        "BUTTON_YES": "Igen",
        "BUTTON_NO": "Nem",
        # Confirmation Messages
        "CONFIRM_BUY_PLAYER": "Megveszed {player_name} játékost {currency_symbol}{asking_price_formatted} áron?",
        "CONFIRM_LIST_PLAYER": "Biztosan piacra teszed {player_name} játékost?",
        "CONFIRM_REMOVE_PLAYER_LISTING": "Biztosan eltávolítod {player_name} játékost a piacról?",
        # Transfer Action Feedback
        "TRANSFER_ACTION_SUCCESS": "{action} sikeres.",
        "TRANSFER_ACTION_FAILED": "{action} sikertelen: {error}",
        "PLAYER_PURCHASE": "Játékos vásárlás",
        "PLAYER_LISTING": "Játékos listázása",
        "PLAYER_LISTING_REMOVAL": "Játékos eltávolítása a listáról",
        "ERROR_INSUFFICIENT_BUDGET": "Nincs elég keret a játékos megvásárlásához.",
        "ERROR_CANNOT_LIST_MORE_PLAYERS": "Nem listázhatsz több játékost. Legalább 18 aktív játékosnak kell maradnia a keretben.",
        "ERROR_PLAYER_NOT_FOUND": "A játékos részletei nem töltődtek be.",
        "INPUT_ASKING_PRICE": "Add meg a kikiáltási árat:",
        "INVALID_ASKING_PRICE": "Érvénytelen kikiáltási ár. Pozitív számnak kell lennie.",
        "NATION" : "Nemzetiség",
        "CLUB_UNATTACHED": "Klub Nélküli",
        "RIGHT": "Jobb",
        "LEFT": "Bal",
        "Enter amount...": "Add meg az összeget...",

        "TOURNAMENT_NAME_REQUIRED": "A Bajnokság neve kötelező.",
        "INVALID_NUM_CLUBS": "A csapatok száma 2 és 32 között kell legyen.",
        "INVALID_START_DELAY_POSITIVE": "Kezdési késleltetésnek pozitív számnak kell lennie.",
        "INVALID_START_DELAY_FORMAT": "Érvénytelen kezdési késleltetés formátum. Használj számokat (pl. 1 vagy 0.5).",
        "INVALID_ROUND_INTERVAL_POSITIVE": "Időköznek pozitív számnak kell lennie.",
        "INVALID_ROUND_INTERVAL_FORMAT": "Érvénytelen időköz formátum. Használj számokat (pl. 24 vagy 0.5).",
        "START_DELAY_HOURS_FLOAT": "Kezdési Késleltetés (Órák, pl. 24 vagy 0.5)",
        "ROUND_INTERVAL_HOURS_FLOAT": "Körök Közti Idő (Órák, pl. 24 vagy 0.5)",
        "CLUB_FREE_AGENTS": "Szabadon igazolható",

        "LABEL_STATUS": "Állapot",
        "STATUS_STARTING": "Hamarosan Kezdődik",
        "STATUS_ONGOING": "Folyamatban",
        "STATUS_FINISHED": "Befejezve",

        "BUTTON_LEAVE_CLUB": "Klub Elhagyása",
        "CONFIRM_LEAVE_CLUB": "Biztosan elhagyod a(z) {club_name} klubot? Ez nem vonható vissza.",
        "LEAVE_CLUB_SUCCESS": "Elhagytad a(z) {club_name} klubot.",
        "LEAVE_CLUB_FAILED": "Klub elhagyása sikertelen: {error}",
    }
}

class Labels:
    def __init__(self):
        self.language = DEFAULT_LANGUAGE
        self.currency = DEFAULT_CURRENCY
        self.fullscreen = DEFAULT_FULLSCREEN
        self.currency_symbols = { "EUR": "€", "GBP": "£", "USD": "$", "HUF": "Ft" }
        self.currency_symbol = self.currency_symbols.get(self.currency, self.currency)
        self.load_settings()

    def load_settings(self):
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    # Language
                    loaded_lang = settings.get("language", DEFAULT_LANGUAGE)
                    self.language = loaded_lang if loaded_lang in labels_dict else DEFAULT_LANGUAGE
                    # Currency
                    loaded_curr = settings.get("currency", DEFAULT_CURRENCY)
                    supported_currencies = self.get_currencies()
                    self.currency = loaded_curr if loaded_curr in supported_currencies else DEFAULT_CURRENCY
                    self.currency_symbol = self.currency_symbols.get(self.currency, self.currency)
                    # Fullscreen (ensure it's a boolean)
                    self.fullscreen = bool(settings.get("fullscreen", DEFAULT_FULLSCREEN))

                    print(f"Loaded settings: Lang={self.language}, Curr={self.currency}, Fullscreen={self.fullscreen}")
            else:
                 print("Settings file not found, using defaults.")
                 self.save_settings() # Create default file
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading settings: {e}. Using defaults.")
            self.language = DEFAULT_LANGUAGE
            self.currency = DEFAULT_CURRENCY
            self.fullscreen = DEFAULT_FULLSCREEN
            self.currency_symbol = self.currency_symbols.get(self.currency, self.currency)

    def save_settings(self):
        settings = {
            "language": self.language,
            "currency": self.currency,
            "fullscreen": self.fullscreen # Save fullscreen state
        }
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
            print(f"Saved settings: Lang={self.language}, Curr={self.currency}, Fullscreen={self.fullscreen}")
        except IOError as e:
            print(f"Error saving settings: {e}")

    def set_setting(self, key: str, value: Any):
        """Sets a specific setting and saves all settings."""
        if hasattr(self, key):
            setattr(self, key, value)
            print(f"Setting '{key}' set to {value}")
            self.save_settings()  # Save changes immediately
        else:
            print(f"Warning: Attempted to set unknown setting '{key}'")

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Gets a specific setting value."""
        return getattr(self, key, default)

    def set_language(self, lang_code: str):
        if lang_code in labels_dict:
            if self.language != lang_code:
                self.language = lang_code
                print(f"Language set to {lang_code}")
                self.save_settings()
        else:
            print(f"Warning: Language '{lang_code}' not found.")

    def set_currency(self, currency_code: str):
        if currency_code in self.currency_symbols:
            if self.currency != currency_code:
                self.currency = currency_code
                self.currency_symbol = self.currency_symbols.get(self.currency, self.currency)
                print(f"Currency set to {currency_code} ({self.currency_symbol})")
                self.save_settings()
        else:
            print(f"Warning: Currency code '{currency_code}' not supported.")

    def get_text(self, key: str, default: str = None) -> str:
        """Gets the localized text for a key."""
        lang_dict = labels_dict.get(self.language, {})
        text = lang_dict.get(key)
        # Fallback to default language (ENGLISH) if key not found in current
        if text is None and self.language != DEFAULT_LANGUAGE:
            default_lang_dict = labels_dict.get(DEFAULT_LANGUAGE, {})
            text = default_lang_dict.get(key)

        # Fallback to provided default or the key itself if not found anywhere
        if text is None:
            text = default if default is not None else key
            print(f"Warning: Missing translation key '{key}' for language '{self.language}'")

        return text

    def get_language_display_name(self, lang_code: str) -> str:
        """Gets the display name for a language code (e.g., 'English', 'Magyar')."""
        # Assumes keys like LANG_ENGLISH, LANG_MAGYAR exist in the dicts
        key = f"LANG_{lang_code.upper()}"
        # Get the display name using the currently selected language for translation
        return self.get_text(key, lang_code)  # Fallback to code if label not found

    def get_languages(self) -> list[str]:
        """Returns a list of available language codes."""
        return list(labels_dict.keys())

    def get_currencies(self) -> list[str]:
        """Returns the list of supported currency codes."""
        # Use keys from the symbol map as supported codes
        return list(self.currency_symbols.keys())

    def get_currency_symbol(self) -> str:
        """Returns the symbol for the currently selected currency."""
        return self.currency_symbol

    def get_formatted_datetime(self, iso_string: str, format_key: str) -> str:
        """
        Formats an ISO datetime string (assumed UTC from server) into the user's LOCAL time zone
        according to a localized format string.
        """
        try:
            # 1. Parse ISO string into a UTC-aware datetime object
            utc_dt_obj: Optional[py_datetime.datetime] = None
            if iso_string:
                 # Ensure the input string is treated as UTC
                if not iso_string.endswith('Z') and '+' not in iso_string and '-' not in iso_string[10:]:
                    dt_str_to_parse = iso_string + 'Z' # Assume UTC if no timezone info
                else:
                    dt_str_to_parse = iso_string.replace('Z', '+00:00') # Standardize Z to offset

                utc_dt_obj = py_datetime.datetime.fromisoformat(dt_str_to_parse)
                # Ensure it's actually UTC, convert if it had another offset parsed
                utc_dt_obj = utc_dt_obj.astimezone(timezone.utc)

            if utc_dt_obj is None:
                raise ValueError("Input ISO string was empty or invalid.")

            # 2. Convert UTC datetime to local system timezone
            local_dt_obj = utc_dt_obj.astimezone() # Convert to local timezone

            # 3. Get the strftime format string from labels
            format_str = self.get_text(format_key, "%Y-%m-%d %H:%M %Z") # Provide a safe default with timezone

            # 4. Format the *local* datetime object
            formatted_date = local_dt_obj.strftime(format_str)

            # --- Manual Month Replacement if %b was used ---
            # This needs to use the local_dt_obj for correct month index
            if "%b" in format_str:
                 month_names_key = "MONTHS_SHORT"
                 month_names = self.get_text(month_names_key, None)
                 # Fallback logic for month names
                 if month_names is None or not isinstance(month_names, list) or len(month_names) != 12:
                      month_names = labels_dict.get(DEFAULT_LANGUAGE, {}).get(month_names_key, [])
                 if len(month_names) != 12:
                      month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

                 # Use the month from the *local* datetime object
                 english_abbr_in_string = local_dt_obj.strftime("%b") # Get standard abbr generated by strftime
                 localized_abbr = month_names[local_dt_obj.month - 1] # Get correct localized name
                 # Replace the standard abbreviation in the potentially already partially localized string
                 formatted_date = formatted_date.replace(english_abbr_in_string, localized_abbr, 1)

            # No need to manually append "UTC" anymore
            return formatted_date

        except ValueError as e:
            print(f"ValueError formatting datetime '{iso_string}' with key '{format_key}': {e}")
            return self.get_text("INVALID_DATE", "Invalid Time")
        except Exception as e:
            print(f"Error formatting datetime '{iso_string}' with key '{format_key}': {e}")
            return "???"