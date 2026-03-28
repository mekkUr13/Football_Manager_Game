import pygame
from typing import Dict, Any, Optional, List, Tuple

from client.button import Button

from client.screens.base_screen import BaseScreen
from client.screens.match_detail_screen import MatchDetailScreen
from client.screens.squad_screen import SquadScreen
from client.screens.lineup_screen import LineupScreen
from client.screens.transfers_screen import TransfersScreen
from client.screens.training_screen import TrainingScreen
from client.screens.fixtures_screen import FixturesScreen
from client.screens.standings_screen import StandingsScreen
from client.screens.tactics_screen import TacticsScreen
from client.screens.player_select_screen import PlayerSelectScreen
from client.screens.tournament_creation_screen import TournamentCreationScreen
from client.screens.player_profile_screen import PlayerProfileScreen
from client.data_models import ClientPlayer, ClientClubInfo, ClientLeague, ClientLeagueDetail, ClientMatch, ClientStandingEntry, ClientTrainingSettings, ClientTacticsSettings, ClientTransferListedPlayer, ClientPlayerProfileData

from common import constants as const
from common.constants import ASSETS_PATH

from client.network_client import NetworkClient

from client.localization import Labels
from client.screens.login_screen import LoginScreen
from client.screens.settings_screen import SettingsScreen
from client.screens.main_menu_screen import MainMenuScreen
from client.screens.league_select_screen import LeagueSelectScreen
from client.screens.club_select_screen import ClubSelectScreen
from client.screens.game_menu_screen import GameMenuScreen

# Server address (should match server)
SERVER_HOST = '127.0.0.1' # Local
SERVER_PORT = 65432

class Game:
    """
    Main class for the Pygame client application.
    Manages game state, screens, events, drawing, and network communication.
    """

    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(400, 50)
        pygame.font.init()

        self.constants = const

        # --- Load Labels and Settings FIRST ---
        self.labels = Labels()  # Initialize labels/settings loader

        # --- Initial Display Mode ---
        self.current_screen_width = self.constants.SCREEN_WIDTH
        self.current_screen_height = self.constants.SCREEN_HEIGHT
        display_flags = 0  # Default to windowed
        if self.labels.get_setting("fullscreen", False):
            # Usage of SCALED for better compatibility if hardware resolution differs
            display_flags = pygame.FULLSCREEN | pygame.SCALED
            print("Starting in Fullscreen mode.")
        else:
            print("Starting in Windowed mode.")

        try:
            self.screen = pygame.display.set_mode(
                (self.current_screen_width, self.current_screen_height),
                display_flags
            )
            # Update dimensions after set_mode in case fullscreen changed them
            self.current_screen_width = self.screen.get_width()
            self.current_screen_height = self.screen.get_height()
        except pygame.error as e:
            print(f"Error setting initial display mode: {e}. Falling back to windowed.")
            display_flags = 0
            self.screen = pygame.display.set_mode(
                (self.constants.SCREEN_WIDTH, self.constants.SCREEN_HEIGHT),
                display_flags
            )
            self.current_screen_width = self.screen.get_width()
            self.current_screen_height = self.screen.get_height()

        pygame.display.set_caption(self.labels.get_text("APP_TITLE", "MFS"))

        self.clock = pygame.time.Clock()
        self.running = True


        # --- Assets & Fonts ---
        self.assets = {}  # Dictionary to store loaded assets
        self.load_assets()
        self.load_fonts()
        if not self.running: return

        # --- Network Client ---
        self.network_client = NetworkClient(SERVER_HOST, SERVER_PORT)
        # Connection attempt happens later, before main loop or in LoginScreen

        # --- User/Club Info (Set after login) ---
        self.user_id: Optional[int] = None
        self.username: Optional[str] = None
        self.user_clubs: List[ClientClubInfo] = []
        self.active_club_id: Optional[int] = None
        self.active_tournament_id: Optional[int] = None

        # --- Colors ---
        self.colors = {
            "background": const.COLOR_BACKGROUND, "text_normal": const.COLOR_TEXT_NORMAL,
            "panel": const.COLOR_PANEL, "border": const.BORDER_COLOR,
            "active_button": const.ACTIVE_COLOR, "inactive_button": const.INACTIVE_COLOR,
            "text_button": const.TEXT_COLOR, "input_bg": (200, 200, 200),
            "input_text": (0, 0, 0), "error_text": (255, 100, 100),
            "success_text": (100, 255, 100),
        }

        # --- Screens ---
        self.screens: Dict[str, BaseScreen] = {
            "Login": LoginScreen(self),
            "Settings": SettingsScreen(self),
            "MainMenu": MainMenuScreen(self),
            "LeagueSelect": LeagueSelectScreen(self),
            "ClubSelect": ClubSelectScreen(self),
            "GameMenu": GameMenuScreen(self),
            "Squad": SquadScreen(self),
            "Lineup": LineupScreen(self),
            "Transfers": TransfersScreen(self),
            "Training": TrainingScreen(self),
            "Fixtures": FixturesScreen(self),
            "Standings": StandingsScreen(self),
            "Tactics": TacticsScreen(self),
            "TournamentCreation": TournamentCreationScreen(self),
            "PlayerSelect": PlayerSelectScreen(self),
            "PlayerProfile": PlayerProfileScreen(self),
            "MatchDetail": MatchDetailScreen(self),
        }

        # --- Global Settings Button ---
        self.settings_button: Optional[Button] = None
        self.exit_button: Optional[Button] = None
        self._create_global_buttons()

        # Start state
        self.current_screen_name = "Login"
        self.active_screen: BaseScreen = self.screens[self.current_screen_name]
        self.requested_screen_change: Optional[tuple[str, Optional[Dict]]] = None

    def _create_global_buttons(self):
        """Creates the global UI buttons (Settings, Exit)."""
        # --- Settings Button ---
        settings_icon = self.assets.get('settings_icon')
        if settings_icon:
            icon_size = settings_icon.get_width()
            settings_x = self.constants.SCREEN_WIDTH - icon_size - self.constants.BUTTON_MARGIN  # Initial X
            self.settings_button = Button(
                x=settings_x, y=self.constants.BUTTON_MARGIN,
                width=icon_size, height=icon_size, image=settings_icon,
                active_color=self.colors['active_button'], inactive_color=(70, 70, 70),
                border_color=self.colors['border'], on_click=self.go_to_settings,
                font_size=0, text="", text_color=(0, 0, 0)
            )
            # Adjust X based on current screen width if needed (might be done in draw/update)
            self.settings_button.rect.right = self.screen.get_width() - self.constants.BUTTON_MARGIN
        else:  # Fallback text button
            settings_size = 40
            settings_x = self.constants.SCREEN_WIDTH - settings_size - self.constants.BUTTON_MARGIN
            self.settings_button = Button(text="SET", x=settings_x, y=self.constants.BUTTON_MARGIN, width=settings_size,
                                          height=settings_size, font_size=24, active_color=self.colors['active_button'],
                                          inactive_color=(70, 70, 70), border_color=self.colors['border'],
                                          text_color=self.colors['text_button'], on_click=self.go_to_settings)
            self.settings_button.rect.right = self.screen.get_width() - self.constants.BUTTON_MARGIN

        # --- Exit Button ---
        exit_size = self.constants.EXIT_BUTTON_SIZE
        exit_margin = self.constants.EXIT_BUTTON_MARGIN
        self.exit_button = Button(
            x=exit_margin, y=exit_margin,  # Top-left corner
            width=exit_size, height=exit_size,
            text="X",  # Simple X text
            font_size=int(exit_size * 0.8),  # Large font relative to button size
            active_color=self.constants.COLOR_EXIT_BG_HOVER,  # Hover color
            inactive_color=self.constants.COLOR_EXIT_BG_NORMAL,  # Normal color
            border_color=self.constants.COLOR_EXIT_BORDER,  # Border color
            text_color=self.constants.COLOR_EXIT_X,  # Text color
            on_click=self.quit_game  # Action to quit
        )

        # --- Refresh Button  ---
        self.refresh_button: Optional[Button] = None
        refresh_icon = self.assets.get('refresh_icon')
        icon_size_settings = self.settings_button.rect.width if self.settings_button else 32
        icon_size_refresh = 28  # As scaled

        if self.settings_button:
            refresh_x = self.settings_button.rect.left - icon_size_refresh - 10  # 10px spacing
        else:  # Fallback if settings button somehow doesn't exist
            refresh_x = self.screen.get_width() - icon_size_refresh - self.constants.BUTTON_MARGIN - icon_size_settings - 10

        if refresh_icon:
            self.refresh_button = Button(
                x=refresh_x, y=self.constants.BUTTON_MARGIN + (icon_size_settings - icon_size_refresh) // 2,
                # Align vertically
                width=icon_size_refresh, height=icon_size_refresh, image=refresh_icon,
                active_color=self.colors['active_button'], inactive_color=(70, 70, 70),
                border_color=self.colors['border'], on_click=self.refresh_current_screen,
                font_size=0, text="", text_color=(0, 0, 0)
            )
        else:  # Fallback text button
            self.refresh_button = Button(text="R", x=refresh_x, y=self.constants.BUTTON_MARGIN,
                                         width=icon_size_settings,
                                         height=icon_size_settings, font_size=24,
                                         active_color=self.colors['active_button'],
                                         inactive_color=(70, 70, 70), border_color=self.colors['border'],
                                         text_color=self.colors['text_button'], on_click=self.refresh_current_screen)

        if self.refresh_button:  # Ensure X is correct if settings button wasn't there
            self.refresh_button.rect.right = (self.settings_button.rect.left if self.settings_button else self.screen.get_width() - self.constants.BUTTON_MARGIN) - 10

    def _reposition_global_buttons(self):
        """Repositions global buttons based on current screen dimensions."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        # Settings Button (Top Right)
        if self.settings_button:
            self.settings_button.rect.right = screen_w - self.constants.BUTTON_MARGIN
            self.settings_button.rect.top = self.constants.BUTTON_MARGIN

        # Refresh Button (Left of Settings)
        if self.refresh_button:
            icon_size_settings = self.settings_button.rect.width if self.settings_button else 32
            self.refresh_button.rect.right = (self.settings_button.rect.left if self.settings_button else screen_w - self.constants.BUTTON_MARGIN) - 10
            self.refresh_button.rect.top = self.constants.BUTTON_MARGIN + ( icon_size_settings - self.refresh_button.rect.height) // 2

        # Exit Button (Top Left)
        if self.exit_button:
            self.exit_button.rect.topleft = (self.constants.EXIT_BUTTON_MARGIN, self.constants.EXIT_BUTTON_MARGIN)


    def apply_display_settings(self) -> bool:
        """
        Applies fullscreen/windowed mode based on saved settings.
        :returns: True if display settings were applied successfully, False otherwise.
        """
        print("Applying display settings...")
        is_fullscreen_setting = self.labels.get_setting("fullscreen", False)
        current_flags = self.screen.get_flags()
        is_currently_fullscreen = bool(current_flags & pygame.FULLSCREEN)

        success = True  # Assume success initially
        if is_fullscreen_setting != is_currently_fullscreen:
            print(f"Switching display mode to {'Fullscreen' if is_fullscreen_setting else 'Windowed'}...")
            target_size = (self.constants.SCREEN_WIDTH, self.constants.SCREEN_HEIGHT)
            new_flags = pygame.SCALED | pygame.FULLSCREEN if is_fullscreen_setting else 0

            try:
                new_screen = pygame.display.set_mode(target_size, new_flags)
                self.screen = new_screen
                self.current_screen_width = self.screen.get_width()
                self.current_screen_height = self.screen.get_height()
                print(f"Screen updated to: {self.current_screen_width}x{self.current_screen_height}, Flags={new_flags}")
                self._reposition_global_buttons()

                if self.active_screen and hasattr(self.active_screen, 'on_display_change'):
                    self.active_screen.on_display_change()
                elif self.active_screen and hasattr(self.active_screen, 'create_ui'):
                    print(f"Telling {self.current_screen_name} to recreate UI after display change.")
                    # Need to ensure create_ui handles potential state preservation if needed
                    self.active_screen.create_ui()
                    if hasattr(self.active_screen, '_update_button_states'): self.active_screen._update_button_states()


            except pygame.error as e:
                print(f"Error setting display mode: {e}")
                # Revert the setting in Labels
                self.labels.set_setting("fullscreen", is_currently_fullscreen)
                success = False  # Indicate failure
        else:
            print("Display mode already matches setting. No change needed.")

        return success  # Return success status



    def load_assets(self):
        """Loads graphical assets like icons and background images."""
        self.assets = {}  # Reset assets dictionary
        try:
            # Load game window icon
            icon_path = ASSETS_PATH / 'manager_icon3.png'
            if icon_path.exists():
                pygame_icon = pygame.image.load(icon_path).convert_alpha()
                pygame.display.set_icon(pygame_icon)
            else:
                print(f"Warning: Game icon file not found: '{icon_path}'")

            # Load background image
            bg_path = ASSETS_PATH / 'football_pitch_bg.jpg'
            if bg_path.exists():
                background_image = pygame.image.load(bg_path).convert()
                self.assets['background'] = pygame.transform.scale(background_image, (
                self.constants.SCREEN_WIDTH, self.constants.SCREEN_HEIGHT))
            else:
                print(f"Warning: Background file not found: '{bg_path}'")
                self.assets['background'] = None  # Fallback

            # --- Load Settings Icon ---
            settings_icon_path = ASSETS_PATH / 'settings_icon.png'
            if settings_icon_path.exists():
                settings_icon_img = pygame.image.load(settings_icon_path).convert_alpha()
                settings_icon_img = pygame.transform.smoothscale(settings_icon_img, (32, 32))
                self.assets['settings_icon'] = settings_icon_img
                print("Loaded settings icon.")
            else:
                print(f"Warning: Settings icon file not found: '{settings_icon_path}'")
                self.assets['settings_icon'] = None  # Fallback

            # --- Load Refresh Icon ---
            refresh_icon_path = ASSETS_PATH / 'refresh_icon.png'
            if refresh_icon_path.exists():
                refresh_icon_img = pygame.image.load(refresh_icon_path).convert_alpha()
                refresh_icon_img = pygame.transform.smoothscale(refresh_icon_img, (28, 28))  # Slightly smaller
                self.assets['refresh_icon'] = refresh_icon_img
                print("Loaded refresh icon.")
            else:
                print(f"Warning: Refresh icon file not found: '{refresh_icon_path}'")
                self.assets['refresh_icon'] = None

        except pygame.error as e:
            print(f"Error loading assets: {e}")
        except FileNotFoundError as e:  # Catch specific file not found errors if paths are wrong
            print(f"Asset file not found error: {e}")

    def load_fonts(self):
         try:
            self.fonts = {
                'button': pygame.font.Font(None, const.FONT_SIZE_BUTTON),
                'medium': pygame.font.Font(None, const.FONT_SIZE_MEDIUM),
                'large': pygame.font.Font(None, const.FONT_SIZE_LARGE),
                'small': pygame.font.Font(None, const.FONT_SIZE_SMALL),
            }
         except Exception as e:
             print(f"FATAL: Could not load fonts: {e}")
             self.running = False # Cannot run without fonts

    def change_screen(self, screen_name: str, data: Optional[Dict] = None):
        """
        Switches the active screen, calling on_exit and on_enter.
        Handles special logic for GameMenu sub-screens.

        Args:
            screen_name: The key of the screen to switch to in self.screens.
            data: Optional dictionary to pass to the new screen's on_enter method.
        """
        # Identify screens that are managed by GameMenuScreen
        # These are the views shown in the main panel when GameMenu is active.
        game_menu_sub_screens = {
            "Squad", "Lineup", "Tactics", "Transfers", "Training",
            "Fixtures", "Standings"
        }

        print(
            f"Game: change_screen initiated. Current: {self.current_screen_name}, Target: {screen_name}, Data: {data}")

        if screen_name in self.screens:
            target_game_menu = self.screens.get("GameMenu")
            if not isinstance(target_game_menu, GameMenuScreen):
                print("CRITICAL ERROR: GameMenuScreen not found or incorrect type.")
                return

            # Is the target screen one of GameMenu's sub-screens?
            if screen_name in game_menu_sub_screens:
                # Scenario 1: GameMenu is NOT currently the active screen.
                # This happens when coming from PlayerSelectScreen to Tactics,
                # or LoginScreen to GameMenu (though GameMenu would likely default to Squad).
                if self.active_screen != target_game_menu:
                    print(f"Game: Target '{screen_name}' is a sub-screen. Activating GameMenu first.")
                    if self.active_screen:
                        self.active_screen.on_exit()
                    self.current_screen_name = "GameMenu"  # Game's overall active screen becomes GameMenu
                    self.active_screen = target_game_menu
                    # GameMenu.on_enter will be responsible for calling its own change_sub_screen
                    # to display the correct initial sub-screen (e.g., 'Squad' by default, or 'Tactics' if data says so).
                    # The data passed here to GameMenu.on_enter is crucial.
                    self.active_screen.on_enter(data=data)  # Pass data to GameMenuScreen
                    # GameMenuScreen's on_enter will internally call change_sub_screen(screen_name, data)

                # Scenario 2: GameMenu IS already the active screen.
                # This happens when clicking navigation buttons within GameMenu (e.g., Squad -> Tactics).
                else:
                    print(f"Game: GameMenu is already active. Telling it to change sub-screen to: {screen_name}")
                    # We directly tell GameMenu to change its content.
                    # The 'data' here would typically be None if navigating via GameMenu's own buttons,
                    # OR it could be specific data if a GameMenu button needs to pass something to a sub-screen.
                    target_game_menu.change_sub_screen(screen_name, data_for_sub_screen=data)

            # --- Standard Screen Change Logic (for screens NOT managed by GameMenu) ---
            else:
                print(f"Game: Target '{screen_name}' is a standalone screen.")
                if self.active_screen:
                    self.active_screen.on_exit()
                self.current_screen_name = screen_name
                self.active_screen = self.screens[screen_name]
                self.active_screen.on_enter(data=data)
        else:
            print(f"Warning: Screen '{screen_name}' not found.")

    def request_screen_change(self, screen_name: str, data: Optional[Dict] = None):
        """Stores the request to change screen, processed at the end of the game loop."""
        print(f"Screen change requested to: {screen_name}")
        self.requested_screen_change = (screen_name, data)

    def run(self):
        if not self.running:
            pygame.quit()
            return

        # --- Initial Connection Attempt ---
        if not self.network_client.connect():
            # Show connection error on the initial Login screen before loop
            if isinstance(self.active_screen, LoginScreen):
                self.active_screen.set_message(self.labels.get_text("CONNECTION_FAILED", "Server connection failed."),
                                               is_error=True)
            else:  # Should not happen if starting on Login, but as fallback:
                print("FATAL: Could not connect to server on startup.")
                # Render a simple error message
                self.screen.fill(self.colors['background'])
                font = self.fonts['large']
                text_surf = font.render("Server Connection Failed", True, self.colors['error_text'])
                text_rect = text_surf.get_rect(center=(const.SCREEN_WIDTH // 2, const.SCREEN_HEIGHT // 2))
                self.screen.blit(text_surf, text_rect)
                pygame.display.flip()
                pygame.time.wait(3000)
                self.running = False  # Prevent loop start

        # Call on_enter for the initial screen (Login) AFTER checking connection
        if self.running and self.active_screen:
            try:
                self.active_screen.on_enter()
            except Exception as e:
                print(f"Error during initial on_enter for {self.current_screen_name}: {e}")
                self.running = False

        # --- Main Loop ---
        try:
            while self.running:
                dt = self.clock.tick(60) / 1000.0


                # --- Handle Pending Screen Change FIRST ---
                # Process screen change requests made in the *previous* frame's event handling
                if self.requested_screen_change:
                    target_screen, target_data = self.requested_screen_change
                    self.requested_screen_change = None  # Clear request
                    self.change_screen(target_screen, target_data)  # Perform the actual change
                    # Skip the rest of the loop for this frame to avoid event/update/draw on old screen
                    continue

                self.handle_events()
                self.update(dt)
                self.draw()
        finally:
            print("Game loop ended. Cleaning up...")
            self.network_client.disconnect()
            pygame.quit()


    def quit_game(self):
        """Sets the flag to stop the main game loop."""
        print("Exit button clicked. Quitting game.")
        self.running = False

    def go_to_settings(self):
        """Navigates to the Settings screen from anywhere."""
        # Always store the current screen to return to it
        if self.current_screen_name != "Settings":  # Avoid looping back to settings from itself
            print(f"Navigating to Settings from {self.current_screen_name}")
            self.change_screen("Settings", data={"previous_screen": self.current_screen_name})

    def handle_events(self):
        """Handles global events and passes others to the active screen."""
        mouse_pos = pygame.mouse.get_pos()
        # Update hover state for the global button first
        if self.settings_button: self.settings_button.check_hover(mouse_pos)
        if self.exit_button: self.exit_button.check_hover(mouse_pos)
        if self.refresh_button: self.refresh_button.check_hover(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return  # Exit event loop immediately on quit

            # --- Check Global Button Click First ---
            global_handled = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.exit_button and self.exit_button.check_click(event.pos):
                    global_handled = True  # Exit button handled globally
                elif self.settings_button and self.settings_button.check_click(event.pos):
                    global_handled = True  # Settings button handled globally

            # --- Pass event to active screen IF NOT handled globally ---
            if not global_handled and self.active_screen:
                self.active_screen.handle_event(event)

    def update(self, dt):
        if self.active_screen:
            self.active_screen.update(dt)  # Pass delta time

    def draw(self):
        """Draws the background, active screen, and global UI elements."""
        # Background
        bg_image = self.assets.get('background')
        if bg_image: self.screen.blit(bg_image, (0, 0))
        else: self.screen.fill(self.colors['background'])

        # Active screen draws its content
        if self.active_screen:
            self.active_screen.draw(self.screen)

        # --- Draw Global Buttons on Top ---
        if self.settings_button:
            # Ensure settings button X is correct for current screen width before drawing
            self.settings_button.rect.right = self.screen.get_width() - self.constants.BUTTON_MARGIN
            self.settings_button.draw(self.screen)
        if self.refresh_button:  # Draw refresh button
            if self.settings_button:  # Position relative to settings button
                self.refresh_button.rect.right = self.settings_button.rect.left - 10
                self.refresh_button.rect.centery = self.settings_button.rect.centery
            else:  # Fallback position if no settings button
                self.refresh_button.rect.right = self.screen.get_width() - self.constants.BUTTON_MARGIN - 42
                self.refresh_button.rect.top = self.constants.BUTTON_MARGIN
            self.refresh_button.draw(self.screen)
        if self.exit_button:
            self.exit_button.draw(self.screen)  # Draw the exit button

        pygame.display.flip()

    # --- User State Management ---
    def set_user_info(self, user_id: int, username: str):
        """Stores user info after successful login and fetches initial club data."""
        print(f"Setting user info: ID={user_id}, Username={username}")
        self.user_id = user_id
        self.username = username
        self.fetch_user_clubs() # Get the user's clubs immediately after login

    def fetch_user_clubs(self):
        """Fetches the list of clubs managed by the current user from the server."""
        if not self.user_id:
            print("Cannot fetch user clubs: User not logged in.")
            self.user_clubs = []
            return

        print(f"Requesting clubs for user_id: {self.user_id}")
        response = self.network_client.send_request("get_user_clubs", {"user_id": self.user_id})

        if response and response.get("status") == "success":
            clubs_data = response.get("data", [])
            # Convert list of dictionaries to list of ClientClubInfo objects
            self.user_clubs = [ClientClubInfo.from_dict(data) for data in clubs_data]
            print(f"Received and parsed {len(self.user_clubs)} clubs for user.")
        else:
            error_msg = response.get('message') if response else "No response fetching clubs"
            print(f"Error fetching user clubs: {error_msg}")
            self.user_clubs = [] # Reset on error

    def logout(self):
        """Resets user state and returns to the login screen."""
        print("Logging out.")
        self.user_id = None
        self.username = None
        self.user_clubs = []
        self.active_club_id = None
        self.active_tournament_id = None # Reset tournament context
        self.change_screen("Login")

    def set_active_club(self, club: ClientClubInfo):
        """Sets the currently managed club and its tournament context."""
        if club:
            print(f"Setting active club: {club.club_name} (ID: {club.club_id}), Tournament ID: {club.tournament_id}")
            self.active_club_id = club.club_id
            self.active_tournament_id = club.tournament_id
        else:
            print("Warning: Attempted to set active club with None.")
            self.active_club_id = None
            self.active_tournament_id = None

    # --- Game State Updates ---
    def user_joined_club(self):
        """Refreshes the user's club list after successfully joining."""
        print("User joined a new club. Refreshing club list.")
        self.fetch_user_clubs()
        # The MainMenuScreen's on_enter should handle updating its display

    # --- Data Request Methods ---
    # Screens will call these methods to get data via the network

    def request_squad_data(self) -> Optional[List[ClientPlayer]]:
        """
        Requests squad data for the active club and returns a list of ClientPlayer objects.
        """
        club_to_request = self.active_club_id
        if not club_to_request:
            print("Cannot request squad data: No active club selected.")
            return None
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request squad data: Not connected.")
            return None

        print(f"Requesting squad data for active club ID: {club_to_request}")
        response = self.network_client.send_request("get_squad", {"club_id": club_to_request})

        if response and response.get("status") == "success":
            squad_dict_list = response.get("data")
            if isinstance(squad_dict_list, list):
                # Convert dictionaries to ClientPlayer objects, passing labels for status derivation
                players = [ClientPlayer.from_dict(p_dict, self.labels) for p_dict in squad_dict_list]
                print(f"Received and parsed {len(players)} players.")
                return players
            else:
                print(f"Error: Received invalid squad data format from server: {type(squad_dict_list)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching squad data: {error_msg}")
            return None

    def request_available_leagues(self) -> Optional[List[ClientLeague]]:
        """Requests available leagues and returns a list of ClientLeague objects."""
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request available leagues: Not connected.")
            return None

        print("Requesting available leagues...")
        response = self.network_client.send_request("get_available_leagues")

        if response and response.get("status") == "success":
            leagues_data = response.get("data", [])
            leagues = [ClientLeague.from_dict(l_dict) for l_dict in leagues_data]
            print(f"Received and parsed {len(leagues)} available leagues.")
            # Sort leagues by name client-side if needed
            leagues.sort(key=lambda x: x.name)
            return leagues
        else:
            error_msg = response.get('message') if response else "No response"
            print(f"Error fetching available leagues: {error_msg}")
            return None

    def request_league_details(self, tournament_id: int) -> Optional[ClientLeagueDetail]:
        """Requests detailed info for a league, including club availability."""
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request league details: Not connected.")
            return None
        if not tournament_id:
            print("Cannot request league details: Invalid tournament_id.")
            return None

        print(f"Requesting details for league ID: {tournament_id}")
        response = self.network_client.send_request("get_league_details", {"tournament_id": tournament_id})

        if response and response.get("status") == "success":
            details_data = response.get("data")
            if details_data:
                league_details = ClientLeagueDetail.from_dict(details_data)
                print(f"Received details for league: {league_details.name}")
                return league_details
            else:
                print("Error: Received empty data for league details.")
                return None
        else:
            error_msg = response.get('message') if response else "No response"
            print(f"Error fetching league details: {error_msg}")
            return None

    def request_fixtures_data(self) -> Optional[List[ClientMatch]]:
        """Requests fixture data for the active tournament."""
        tournament_to_request = self.active_tournament_id
        if not tournament_to_request:
            print("Cannot request fixtures: No active tournament set.")
            return None
        if not self.active_club_id:
            # Need the user's club ID to potentially highlight matches,
            # even if the server doesn't strictly need it for filtering.
            print("Cannot request fixtures: No active club ID set.")
            return None

        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request fixtures: Not connected.")
            return None

        print(f"Requesting fixtures for tournament ID: {tournament_to_request}")
        response = self.network_client.send_request("get_fixtures", {
            "tournament_id": tournament_to_request,
            "user_club_id": self.active_club_id  # Send user's club ID
        })

        if response and response.get("status") == "success":
            fixtures_dict_list = response.get("data")
            if isinstance(fixtures_dict_list, list):
                # Convert dictionaries to ClientMatch objects
                matches = [ClientMatch.from_dict(m_dict) for m_dict in fixtures_dict_list]
                print(f"Received and parsed {len(matches)} fixtures.")
                return matches
            else:
                print(f"Error: Received invalid fixtures data format from server: {type(fixtures_dict_list)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching fixtures data: {error_msg}")
            return None

    def request_standings_data(self) -> Optional[List[ClientStandingEntry]]:
        """Requests standings data for the active tournament."""
        tournament_to_request = self.active_tournament_id
        if not tournament_to_request:
            print("Cannot request standings: No active tournament set.")
            return None

        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request standings: Not connected.")
            return None

        print(f"Requesting standings for tournament ID: {tournament_to_request}")
        response = self.network_client.send_request("get_standings", {
            "tournament_id": tournament_to_request
        })

        if response and response.get("status") == "success":
            standings_dict_list = response.get("data")
            if isinstance(standings_dict_list, list):
                # Convert dictionaries to ClientStandingEntry objects
                standings = [ClientStandingEntry.from_dict(s_dict) for s_dict in standings_dict_list]
                # The server already sorts, so no client-side sort needed here.
                print(f"Received and parsed {len(standings)} standing entries.")
                return standings
            else:
                print(f"Error: Received invalid standings data format from server: {type(standings_dict_list)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching standings data: {error_msg}")
            return None

    def request_club_tactics(self) -> Optional[Dict[str, Any]]:
        """
        Requests tactics data (formation, lineup) for the active club.
        Returns:
            A dictionary containing tactics data (e.g., formation string,
            starting_players JSON, substitutes JSON) or None on error.
        """
        club_to_request = self.active_club_id
        if not club_to_request:
            print("Cannot request club tactics: No active club selected.")
            return None
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request club tactics: Not connected.")
            return None

        print(f"Requesting tactics for active club ID: {club_to_request}")
        response = self.network_client.send_request("get_club_tactics", {"club_id": club_to_request})

        if response and response.get("status") == "success":
            tactics_data = response.get("data")
            if isinstance(tactics_data, dict):
                print(f"Received tactics data: {tactics_data.get('formation')}")
                return tactics_data
            else:
                print(f"Error: Received invalid tactics data format from server: {type(tactics_data)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching club tactics: {error_msg}")
            return None

    def request_update_lineup_slot(self, slot_index: int, new_player_id: Optional[int]) -> bool:
        """
        Sends a request to the server to update a specific lineup slot.

        Args:
            slot_index: The 0-based index of the lineup slot to update.
            new_player_id: The ID of the player to place in the slot, or None to empty it.

        Returns:
            True if the server confirmed the update, False otherwise.
        """
        club_id = self.active_club_id
        if not club_id:
            print("Cannot update lineup: No active club selected.")
            return False
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot update lineup: Not connected.")
            return False

        payload = {
            "club_id": club_id,
            "slot_index": slot_index,
            "new_player_id": new_player_id
        }
        print(f"Sending lineup update request: Slot={slot_index}, Player={new_player_id}, Club={club_id}")

        response = self.network_client.send_request("update_lineup_slot", payload)

        if response and response.get("status") == "success":
            print("Server confirmed lineup update.")
            return True
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error updating lineup slot: {error_msg}")
            return False

    def request_swap_lineup_players(self, player_in_id: int, player_out_id: int,
                                    target_slot_index: Optional[int]) -> bool:
        """
        Sends a request to the server to swap two players' roles.

        Args:
            player_in_id: ID of the player selected from the list.
            player_out_id: ID of the player originally clicked (being replaced).
            target_slot_index: The 0-based index of the starter slot being filled,
                               or None if player_out_id was a substitute.

        Returns:
            True if the server confirmed the swap, False otherwise.
        """
        club_id = self.active_club_id
        if not club_id:
            print("Cannot swap lineup players: No active club selected.")
            return False
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot swap lineup players: Not connected.")
            return False

        payload = {
            "club_id": club_id,
            "player_in_id": player_in_id,
            "player_out_id": player_out_id,
            "target_slot_index": target_slot_index  # Can be None
        }
        print(f"Sending player swap request: In={player_in_id}, Out={player_out_id}, TargetSlot={target_slot_index}")

        response = self.network_client.send_request("swap_lineup_players", payload)

        if response and response.get("status") == "success":
            print("Server confirmed player swap.")
            return True
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error swapping players: {error_msg}")
            # Optionally display error to user
            return False

    def request_training_settings(self) -> Optional[ClientTrainingSettings]:
        """Requests current training settings for the active club."""
        club_to_request = self.active_club_id
        if not club_to_request:
            print("Cannot request training settings: No active club selected.")
            return None

        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request training settings: Not connected.")
            return None

        print(f"Requesting training settings for club ID: {club_to_request}")
        response = self.network_client.send_request("get_club_training", {
            "club_id": club_to_request
        })

        if response and response.get("status") == "success":
            settings_dict = response.get("data")
            if isinstance(settings_dict, dict):
                settings = ClientTrainingSettings.from_dict(settings_dict)
                print(f"Received training settings: Intensity={settings.intensity}, Focus={settings.focus_area}")
                return settings
            else:
                print(f"Error: Received invalid training settings format: {type(settings_dict)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching training settings: {error_msg}")
            return None

    def request_update_training(self, intensity: Optional[int] = None, focus_area: Optional[str] = None) -> bool:
        """
        Sends updated training settings (intensity or focus area) to the server.

        Args:
            intensity: The new intensity value (1-10), if changing.
            focus_area: The string value of the new TrainingFocusEnum, if changing.

        Returns:
            True if the server confirmed the update, False otherwise.
        """
        club_id = self.active_club_id
        if not club_id:
            print("Cannot update training: No active club selected.")
            return False

        if not self.network_client or not self.network_client.is_connected:
            print("Cannot update training: Not connected.")
            return False

        if intensity is None and focus_area is None:
            print("Update training request skipped: No changes provided.")
            return False

        payload = {"club_id": club_id}
        if intensity is not None:
            payload["intensity"] = intensity
        if focus_area is not None:
            payload["focus_area"] = focus_area  # Send string value

        print(f"Sending training update request: {payload}")
        response = self.network_client.send_request("update_club_training", payload)

        if response and response.get("status") == "success":
            print("Server confirmed training update.")
            return True
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error updating training settings: {error_msg}")
            return False

    def request_update_club_tactics(self, new_settings: ClientTacticsSettings) -> bool:
        """
        Sends updated tactics settings (formation, playstyle, specialists) to the server.

        Args:
            new_settings: A ClientTacticsSettings object containing the desired state.

        Returns:
            True if the server confirmed the update, False otherwise.
        """
        club_id = self.active_club_id
        if not club_id:
            print("Cannot update tactics: No active club selected.")
            return False

        if not self.network_client or not self.network_client.is_connected:
            print("Cannot update tactics: Not connected.")
            return False

        # Create payload using the helper method in the dataclass
        payload = new_settings.to_payload_dict()
        payload["club_id"] = club_id  # Add club_id

        print(f"Sending tactics update request: {payload}")
        response = self.network_client.send_request("update_club_tactics", payload)

        if response and response.get("status") == "success":
            print("Server confirmed tactics update.")
            return True
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error updating tactics settings: {error_msg}")
            return False

    def request_transfer_list_data(self) -> Optional[List[ClientTransferListedPlayer]]:
        """Requests the transfer list for the active tournament, excluding user's own players."""
        tournament_to_request = self.active_tournament_id
        club_to_exclude = self.active_club_id

        if not tournament_to_request:
            print("Cannot request transfer list: No active tournament set.")
            return None
        if not club_to_exclude:
            print("Cannot request transfer list: No active club ID to exclude.")
            return None

        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request transfer list: Not connected.")
            return None

        print(f"Requesting transfer list for tournament {tournament_to_request}, excluding club {club_to_exclude}")
        payload = {
            "tournament_id": tournament_to_request,
            "active_club_id": club_to_exclude
        }
        response = self.network_client.send_request("get_transfer_list", payload)

        if response and response.get("status") == "success":
            listed_players_dict_list = response.get("data")
            if isinstance(listed_players_dict_list, list):
                # Convert dictionaries to ClientTransferListedPlayer objects
                # Pass self.labels for status derivation within from_dict
                players = [
                    ClientTransferListedPlayer.from_dict(p_dict, self.labels)
                    for p_dict in listed_players_dict_list
                ]
                print(f"Received and parsed {len(players)} players for the transfer list.")
                return players
            else:
                print(f"Error: Received invalid transfer list data format: {type(listed_players_dict_list)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching transfer list: {error_msg}")
            return None

    def request_player_profile_details(self, player_id: int) -> Optional[ClientPlayerProfileData]:
        """Requests detailed profile data for a specific player."""
        tournament_id = self.active_tournament_id
        if not player_id or not tournament_id:
            print("Cannot request player profile: Missing player_id or active_tournament_id.")
            return None
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request player profile: Not connected.")
            return None

        payload = {"player_id": player_id, "tournament_id": tournament_id}
        print(f"Requesting player profile for Player ID: {player_id}, Tournament ID: {tournament_id}")
        response = self.network_client.send_request("get_player_profile_details", payload)

        if response and response.get("status") == "success":
            player_data_dict = response.get("data")
            if isinstance(player_data_dict, dict):
                # Pass self.labels for status derivation and other parsing
                profile_data = ClientPlayerProfileData.from_dict(player_data_dict, self.labels)
                print(f"Received profile for {profile_data.name}")
                return profile_data
            else:
                print(f"Error: Received invalid player profile data format: {type(player_data_dict)}")
                return None
        else:
            error_msg = response.get('message') if response else "No response or network error"
            print(f"Error fetching player profile: {error_msg}")
            return None

    def request_buy_player(self, player_id: int, listing_id: int) -> Tuple[bool, str, Optional[int]]:
        """
        Requests to buy a player.
        Returns: (success_flag, message, new_budget_if_successful)
        """
        buying_club_id = self.active_club_id
        tournament_id = self.active_tournament_id

        if not all([buying_club_id, player_id, listing_id, tournament_id]):
            print("Buy request: Missing critical IDs.")
            return False, "Internal error: Missing IDs.", None
        if not self.network_client or not self.network_client.is_connected:
            return False, "Not connected to server.", None

        payload = {
            "buying_club_id": buying_club_id,
            "player_id": player_id,
            "listing_id": listing_id,
            "tournament_id": tournament_id
        }
        print(f"Requesting to buy player {player_id} (listing {listing_id}) for club {buying_club_id}")
        response = self.network_client.send_request("buy_player", payload)

        if response and response.get("status") == "success":
            msg = response.get("message", "Purchase successful.")
            updated_budget = response.get("data", {}).get("updated_budget")
            print(f"Buy successful: {msg}. New budget: {updated_budget}")
            # Update local budget if game state tracks it directly, or rely on screen refresh
            if updated_budget is not None and self.user_clubs:
                for club_info in self.user_clubs:
                    if club_info.club_id == buying_club_id:
                        club_info.budget = updated_budget
                        break
            return True, msg, updated_budget
        else:
            error_msg = response.get('message') if response else "Purchase failed. No server response."
            print(f"Buy failed: {error_msg}")
            return False, error_msg, None

    def request_list_player(self, player_id: int, asking_price: int) -> Tuple[bool, str, Optional[int]]:
        """
        Requests to list a player for transfer.
        Returns: (success_flag, message, listing_id_if_successful)
        """
        club_id = self.active_club_id
        tournament_id = self.active_tournament_id

        if not all([club_id, player_id, tournament_id]):
            return False, "Internal error: Missing IDs for listing.", None
        if asking_price <= 0:
            return False, "Asking price must be positive.", None
        if not self.network_client or not self.network_client.is_connected:
            return False, "Not connected to server.", None

        payload = {
            "club_id": club_id,
            "player_id": player_id,
            "asking_price": asking_price,
            "tournament_id": tournament_id
        }
        print(f"Requesting to list player {player_id} for {asking_price}")
        response = self.network_client.send_request("list_player_for_transfer", payload)

        if response and response.get("status") == "success":
            msg = response.get("message", "Player listed successfully.")
            listing_id = response.get("data", {}).get("listing_id")
            print(f"Listing successful: {msg}. Listing ID: {listing_id}")
            return True, msg, listing_id
        else:
            error_msg = response.get('message') if response else "Listing failed. No server response."
            print(f"Listing failed: {error_msg}")
            return False, error_msg, None

    def request_remove_from_list(self, player_id: int, listing_id: int) -> Tuple[bool, str]:
        """
        Requests to remove a player from the transfer list.
        Returns: (success_flag, message)
        """
        club_id = self.active_club_id
        tournament_id = self.active_tournament_id

        if not all([club_id, player_id, listing_id, tournament_id]):
            return False, "Internal error: Missing IDs for removal."
        if not self.network_client or not self.network_client.is_connected:
            return False, "Not connected to server."

        payload = {
            "club_id": club_id,
            "player_id": player_id,
            "listing_id": listing_id,
            "tournament_id": tournament_id
        }
        print(f"Requesting to remove player {player_id} (listing {listing_id}) from list.")
        response = self.network_client.send_request("remove_player_from_transfer_list", payload)

        if response and response.get("status") == "success":
            msg = response.get("message", "Player removed from list.")
            print(f"Removal successful: {msg}")
            return True, msg
        else:
            error_msg = response.get('message') if response else "Removal failed. No server response."
            print(f"Removal failed: {error_msg}")
            return False, error_msg

    def request_tournament_details(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """Requests basic details for a specific tournament."""
        if not self.network_client or not self.network_client.is_connected:
            print("Cannot request tournament details: Not connected.")
            return None
        if not tournament_id:
            print("Cannot request tournament details: Invalid tournament_id.")
            return None

        print(f"Requesting details for tournament ID: {tournament_id}")
        response = self.network_client.send_request("get_tournament_details", {"tournament_id": tournament_id})
        # This response should include 'is_started' and 'is_finished' flags from the server.
        return response  # Return the whole response dict

    def refresh_current_screen(self):
        """Reloads data for the current active screen by calling its on_enter method."""
        if self.active_screen and self.current_screen_name:
            screen_name_to_refresh = self.current_screen_name
            print(f"Game: Refresh button clicked. Calling on_enter directly for: {screen_name_to_refresh}")

            # Pass data indicating it's a refresh, which screens can use if needed
            refresh_data = {"is_refresh_request": True}

            if isinstance(self.active_screen, GameMenuScreen):
                 # Tell GameMenu it's a refresh and which sub-screen was active
                 print(f"Game: Telling GameMenuScreen to refresh itself (and sub-screen '{self.active_screen.active_sub_screen_name}').")
                 refresh_data["sub_screen_to_refresh"] = self.active_screen.active_sub_screen_name
                 refresh_data["data_for_forced_sub_screen"] = {"is_refresh_request": True} # Also tell sub-screen it's a refresh
                 self.active_screen.on_enter(data=refresh_data)
            else:
                 # For other screens, just call their on_enter
                 self.active_screen.on_enter(data=refresh_data)
        else:
            print("No active screen to refresh.")
