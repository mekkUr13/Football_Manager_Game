import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from client.data_models import ClientTacticsSettings, ClientPlayer
from common.enums import FormationEnum, PlayStyleEnum
from typing import TYPE_CHECKING, Optional, Dict, List, Any

if TYPE_CHECKING:
    from client.game import Game

class TacticsScreen(BaseScreen):
    """
    Screen for viewing and adjusting club tactics (formation, play style, roles).
    Changes are staged locally and applied only when the 'Apply' button is pressed.
    """
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.loading_state: str = "idle"  # idle, loading, loaded, error
        self.error_message: Optional[str] = None
        self.success_message: Optional[str] = None
        self.message_timer: float = 0.0

        # Data state
        self.server_settings: Optional[ClientTacticsSettings] = None # Last saved state
        self.local_settings: Optional[ClientTacticsSettings] = None # Current potentially unsaved state
        self.squad_map: Dict[int, ClientPlayer] = {} # Map player ID to player object
        self.current_starters_ids: List[int] = [] # List of IDs for current starters
        self.loaded_club_id: Optional[int] = None

        # Options for cycling
        self.formation_options: List[str] = [f.value for f in FormationEnum]
        self.playstyle_options: List[str] = [p.value for p in PlayStyleEnum]
        self.current_formation_index: int = 0
        self.current_playstyle_index: int = 0

        self.has_unsaved_changes: bool = False

        # UI Elements
        self.role_buttons: Dict[str, Button] = {} # e.g., {"captain": Button, "fk_taker": Button}
        self.formation_prev_button: Optional[Button] = None
        self.formation_next_button: Optional[Button] = None
        self.playstyle_prev_button: Optional[Button] = None
        self.playstyle_next_button: Optional[Button] = None
        self.apply_button: Optional[Button] = None

        # Layout constants
        self.padding = 20
        self.title_height = 60
        self.section_spacing = 50
        self.item_spacing = 15
        self.button_height = 40

    def on_enter(self, data: Optional[Dict] = None):
        """
        Fetches data if entering for a new club or first time.
        Preserves local state if returning from PlayerSelectScreen for the same club.
        """
        super().on_enter(data)  # data is passed from change_screen

        current_active_club_id = self.game.active_club_id
        data_from_previous = data or {}  # Ensure data_from_previous is a dict
        is_refresh = data_from_previous.get("is_refresh_request", False)

        print(f"TacticsScreen.on_enter: Called. Current active club ID: {current_active_club_id}")
        print(f"TacticsScreen.on_enter: Data from previous screen: {data_from_previous}")
        print(f"TacticsScreen.on_enter: Current self.loaded_club_id: {self.loaded_club_id}")
        print(f"TacticsScreen.on_enter: self.local_settings is None? {self.local_settings is None}")
        if self.local_settings:
            print(f"TacticsScreen.on_enter: Existing local_settings.formation: {self.local_settings.formation}")
            print(f"TacticsScreen.on_enter: Existing local_settings.captain_id: {self.local_settings.captain_id}")

        is_returning_from_player_select = data_from_previous.get("returning_to_tactics_session", False)
        print(f"TacticsScreen.on_enter: Is returning from player select? {is_returning_from_player_select}")

        should_reload_data = True  # Default to reload

        if is_refresh:
            print("TacticsScreen.on_enter: Refresh request, will reload from server.")
        elif is_returning_from_player_select and \
           self.local_settings is not None and \
           self.loaded_club_id == current_active_club_id:
            # This path should be taken when returning from PlayerSelect for a role change
            print(f"TacticsScreen.on_enter: Path A - Preserving local_settings for club {self.loaded_club_id}.")
            should_reload_data = False
            # UI elements need to reflect the (potentially modified by callback) local_settings
            if not self.apply_button:  # A proxy to check if UI was created
                self._create_ui()
            self._update_role_button_texts()
            self._check_for_unsaved_changes()
        else:
            # This path means we are either entering for the first time, the club changed,
            # or something in the condition above failed (e.g., local_settings was None).
            if not is_returning_from_player_select:
                print("TacticsScreen.on_enter: Path B - Not returning from player select.")
            if self.local_settings is None:
                print("TacticsScreen.on_enter: Path B - self.local_settings is None.")
            if self.loaded_club_id != current_active_club_id:
                print(f"TacticsScreen.on_enter: Path B - Club ID mismatch (loaded: {self.loaded_club_id}, current: {current_active_club_id}).")
            print("TacticsScreen.on_enter: Path B - Decided to reload data.")
            # should_reload_data remains True


        if should_reload_data:
            print("TacticsScreen.on_enter: Reloading data from server...")
            self.loading_state = "loading"
            self.error_message = None
            self.success_message = None  # Clear success message on full reload
            self.server_settings = None
            self.local_settings = None # Crucial: Reset local_settings before reload
            self.squad_map = {}
            self.current_starters_ids = []
            self.has_unsaved_changes = False
            self.loaded_club_id = current_active_club_id # Store the ID we are loading for

            tactics_data_dict = self.game.request_club_tactics()
            if tactics_data_dict is None:
                self.loading_state = "error"
                self.error_message = self.labels.get_text("TACTICS_LOAD_FAILED")
                self._create_ui()
                return

            squad_list = self.game.request_squad_data()
            if squad_list is None:
                self.loading_state = "error"
                if not self.error_message: self.error_message = self.labels.get_text("SQUAD_LOAD_FAILED")
                self._create_ui()
                return

            try:
                self.server_settings = ClientTacticsSettings.from_dict(tactics_data_dict)
                self.local_settings = ClientTacticsSettings.from_dict(tactics_data_dict) # Start local as copy
                print(f"TacticsScreen.on_enter (after reload): self.local_settings.captain_id: {self.local_settings.captain_id if self.local_settings else 'None'}")
            except Exception as e:
                print(f"ERROR processing tactics data after reload: {e}")
                self.loading_state = "error"
                self.error_message = "Error processing tactics data."
                self._create_ui()
                return

            self.squad_map = {p.player_id: p for p in squad_list}
            if self.local_settings:
                self.current_starters_ids = [pid for pid in self.local_settings.starting_player_ids_ordered if pid is not None]
                try:
                    self.current_formation_index = self.formation_options.index(self.local_settings.formation)
                except (ValueError, TypeError, AttributeError):
                    self.current_formation_index = 0
                    if self.local_settings: self.local_settings.formation = self.formation_options[0]
                try:
                    self.current_playstyle_index = self.playstyle_options.index(self.local_settings.play_style)
                except (ValueError, TypeError, AttributeError):
                    self.current_playstyle_index = 0
                    if self.local_settings: self.local_settings.play_style = self.playstyle_options[0]

            self.loading_state = "loaded"
            print("TacticsScreen.on_enter: Data reloaded successfully.")
            self._create_ui() # This calls _update_role_button_texts and _update_apply_button_state

        # This final print helps to see the state of captain_id after on_enter logic
        if self.local_settings:
            print(f"TacticsScreen.on_enter (End): self.local_settings.captain_id: {self.local_settings.captain_id}")
        else:
            print("TacticsScreen.on_enter (End): self.local_settings is None.")


    def _create_ui(self):
        """Creates/Recreates UI elements based on current state."""
        self.role_buttons = {} # Clear existing buttons

        main_rect = self._get_main_content_rect()
        center_x = main_rect.centerx
        current_y = main_rect.top + self.padding + self.title_height + self.item_spacing

        # --- Formation Selector ---
        label_text = self.labels.get_text("LABEL_FORMATION")
        self.draw_text(pygame.display.get_surface(), label_text, (center_x, current_y), self.font_medium, self.colors['text_normal'], center_x=True)
        current_y += 30 # Space for label

        selector_width = 250
        arrow_btn_size = self.button_height
        selector_center_y = current_y + arrow_btn_size // 2

        self.formation_prev_button = Button(
            x=center_x - selector_width // 2 - arrow_btn_size - self.item_spacing,
            y=current_y, width=arrow_btn_size, height=arrow_btn_size, text="<", font_size=24,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=lambda: self._cycle_option('formation', -1)
        )
        self.formation_next_button = Button(
            x=center_x + selector_width // 2 + self.item_spacing,
            y=current_y, width=arrow_btn_size, height=arrow_btn_size, text=">", font_size=24,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=lambda: self._cycle_option('formation', 1)
        )
        current_y += arrow_btn_size + self.section_spacing

        # --- Play Style Selector ---
        label_text = self.labels.get_text("LABEL_PLAY_STYLE")
        self.draw_text(pygame.display.get_surface(), label_text, (center_x, current_y), self.font_medium, self.colors['text_normal'], center_x=True)
        current_y += 30

        selector_center_y = current_y + arrow_btn_size // 2
        self.playstyle_prev_button = Button(
            x=center_x - selector_width // 2 - arrow_btn_size - self.item_spacing,
            y=current_y, width=arrow_btn_size, height=arrow_btn_size, text="<", font_size=24,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=lambda: self._cycle_option('playstyle', -1)
        )
        self.playstyle_next_button = Button(
            x=center_x + selector_width // 2 + self.item_spacing,
            y=current_y, width=arrow_btn_size, height=arrow_btn_size, text=">", font_size=24,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=lambda: self._cycle_option('playstyle', 1)
        )
        current_y += arrow_btn_size + self.section_spacing

        # --- Specialist Role Buttons ---
        role_section_start_x = main_rect.left + 50
        role_button_width = 250
        roles = [
            ("captain", "LABEL_CAPTAIN"),
            ("free_kick_taker", "LABEL_FK_TAKER"),
            ("penalty_taker", "LABEL_PEN_TAKER"),
            ("corner_taker", "LABEL_CORNER_TAKER")
        ]

        # Recalculate label width based on longest actual label text for better alignment
        longest_label_text = ""
        for _, label_key in roles:
            text = self.labels.get_text(label_key) + ":"
            if self.font_medium.size(text)[0] > self.font_medium.size(longest_label_text)[0]:
                longest_label_text = text
        role_label_width = self.font_medium.size(longest_label_text)[0] + 10 # Add padding
        # Give a bit more space between label and button
        button_start_x = role_section_start_x + role_label_width + self.item_spacing * 3  # Increased spacing
        current_y = self.playstyle_next_button.rect.bottom + self.section_spacing if self.playstyle_next_button else main_rect.centery  # Get Y pos robustly

        for role_key, label_key in roles:
            label_text = self.labels.get_text(label_key)
            label_x = role_section_start_x + role_label_width
            label_pos = (label_x, current_y + self.button_height // 2)

            button_x = role_section_start_x + role_label_width + self.item_spacing * 2
            role_player_id_attr = f"{role_key}_id"
            print(f"DEBUG Create UI - RoleKey: {role_key}, AttrName: {role_player_id_attr}")
            role_player_id = None
            if self.local_settings:
                try:
                    role_player_id = getattr(self.local_settings, role_player_id_attr, None)
                except AttributeError:  # Catch if the attribute somehow doesn't exist (shouldn't happen now)
                    print(f"Warning: Attribute '{role_player_id_attr}' not found in local_settings.")
                    role_player_id = None

            player_name = self._get_player_name(role_player_id)
            print(f"DEBUG Create UI - RoleKey: {role_key}, Fetched ID: {role_player_id}")

            btn = Button(
                x=button_start_x, y=current_y, width=role_button_width, height=self.button_height,
                text=player_name, font_size=self.constants.FONT_SIZE_MEDIUM,
                active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
                border_color=self.colors['border'], text_color=self.colors['text_button'],
                on_click=lambda r=role_key: self._select_role_player(r)
            )
            self.role_buttons[role_key] = btn
            current_y += self.button_height + self.item_spacing * 2 # More spacing between roles

        # --- Apply Button ---
        apply_btn_width = 200
        apply_btn_x = main_rect.centerx - apply_btn_width // 2
        apply_btn_y = main_rect.bottom - self.button_height - self.padding

        self.apply_button = Button(
            x=apply_btn_x, y=apply_btn_y, width=apply_btn_width, height=self.button_height + 10, # Slightly taller
            text=self.labels.get_text("BUTTON_APPLY_CHANGES"), font_size=self.constants.FONT_SIZE_BUTTON,
            active_color=self.colors['active_button'], inactive_color=(100, 100, 100), # Greyed out when inactive
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._apply_changes
        )
        # Initial state is inactive
        self.apply_button.active = False

        # Update button text after creation
        self._update_role_button_texts()
        self._update_apply_button_state() # Set initial enabled/disabled state

    def _get_player_name(self, player_id: Optional[int]) -> str:
        """Gets player name from ID, returns default text if not found or None."""
        if player_id is None:
            return self.labels.get_text("ROLE_NOT_SET")
        player = self.squad_map.get(player_id)
        return player.name if player else f"ID: {player_id} (?)"

    def _update_role_button_texts(self):
        """Updates the text on the role buttons based on local_settings."""
        if not self.local_settings:
            print("TacticsScreen._update_role_button_texts: self.local_settings is None. Cannot update button texts.")
            return
        print(f"TacticsScreen._update_role_button_texts: Updating texts. Current captain_id in local_settings: {self.local_settings.captain_id}")
        for role_key, button in self.role_buttons.items():
            attribute_name = f"{role_key}_id" # Construct attribute name
            player_id = getattr(self.local_settings, attribute_name, None)
            player_name = self._get_player_name(player_id)
            print(f"  Role: {role_key}, Attr: {attribute_name}, ID: {player_id}, Name: '{player_name}'")
            button.text = player_name

    def _cycle_option(self, option_type: str, direction: int):
        """Cycles through formation or playstyle options."""
        if not self.local_settings: return

        if option_type == 'formation':
            options = self.formation_options
            current_index = self.current_formation_index
            new_index = (current_index + direction) % len(options)
            self.current_formation_index = new_index
            self.local_settings.formation = options[new_index]
            print(f"Formation changed locally to: {self.local_settings.formation}")
        elif option_type == 'playstyle':
            options = self.playstyle_options
            current_index = self.current_playstyle_index
            new_index = (current_index + direction) % len(options)
            self.current_playstyle_index = new_index
            self.local_settings.play_style = options[new_index]
            print(f"Playstyle changed locally to: {self.local_settings.play_style}")
        else:
            return

        self._check_for_unsaved_changes()

    def _select_role_player(self, role_key: str):
        """Initiates player selection for a specific role."""
        if not self.local_settings or not self.current_starters_ids:
             print("Warning: Cannot select role player - settings or starters not loaded.")
             return

        role_label = self.labels.get_text(f"LABEL_{role_key.upper()}", role_key.replace("_"," ").title())
        title = self.labels.get_text("PLAYER_SELECT_STARTERS_ONLY").format(role_name=role_label)

        context_data = {
            "return_screen": "Tactics",
            "filter_player_ids": self.current_starters_ids, # Only show starters
            # Pass the callback function with the role_key bound
            "on_player_selected_callback": lambda pid: self._handle_role_player_selected(role_key, pid),
            "title_override": title,
            "returning_to_tactics_session": True,
            "role_to_set": role_key # Pass role context
        }
        print(f"Changing to PlayerSelect for role: {role_key}")
        self.game.change_screen("PlayerSelect", data=context_data)

    def _handle_role_player_selected(self, role_key: str, player_id: int):
        """Callback function executed when a player is selected for a role."""
        print(f"TacticsScreen._handle_role_player_selected: For role '{role_key}' with player_id '{player_id}'")
        if self.local_settings:
            attribute_name = f"{role_key}_id"

            old_value = getattr(self.local_settings, attribute_name, 'ATTRIBUTE_NOT_FOUND')
            print(
                f"TacticsScreen._handle_role_player_selected: Value of '{attribute_name}' BEFORE setattr: {old_value}")

            setattr(self.local_settings, attribute_name, player_id)

            new_value = getattr(self.local_settings, attribute_name, 'ATTRIBUTE_STILL_NOT_FOUND')
            print(f"TacticsScreen._handle_role_player_selected: Value of '{attribute_name}' AFTER setattr: {new_value}")

            print("TacticsScreen._handle_role_player_selected: Calling _update_role_button_texts()...")
            self._update_role_button_texts()
            print("TacticsScreen._handle_role_player_selected: Calling _check_for_unsaved_changes()...")
            self._check_for_unsaved_changes()
        else:
            print(
                "TacticsScreen._handle_role_player_selected: Error - self.local_settings is None. Cannot update role.")

    def _check_for_unsaved_changes(self):
        """Compares local settings to server settings and updates the flag."""
        if not self.local_settings or not self.server_settings:
            self.has_unsaved_changes = False
            print("DEBUG Change Check: local_settings or server_settings is None. has_unsaved_changes = False")
            self._update_apply_button_state()
            return

        local_payload = self.local_settings.to_payload_dict()
        server_payload = self.server_settings.to_payload_dict()

        are_equal = (local_payload == server_payload)
        if not are_equal:
            self.has_unsaved_changes = True
            diff_keys = [key for key in local_payload if local_payload.get(key) != server_payload.get(key)]
            diff_keys.extend([key for key in server_payload if key not in local_payload and server_payload.get(
                key) is not None])  # Keys in server but not local
            print(f"DEBUG Change Check: Dictionaries DIFFER. Unsaved changes = True. Differing keys: {diff_keys}")
        else:
            self.has_unsaved_changes = False
            print("DEBUG Change Check: Dictionaries are IDENTICAL. Unsaved changes = False.")

        self._update_apply_button_state()

    def _update_apply_button_state(self):
        """Enables/disables the Apply button based on unsaved changes."""
        if self.apply_button:
            self.apply_button.active = self.has_unsaved_changes # Visually enable/disable

    def _apply_changes(self):
        """Sends the local changes to the server."""
        if not self.has_unsaved_changes or not self.local_settings:
            print("Apply changes called, but no unsaved changes.")
            return

        print("Applying changes...")
        self.loading_state = "loading" # Show loading indicator potentially
        self.error_message = None
        self.success_message = None

        self.draw(pygame.display.get_surface())
        pygame.display.flip()

        success = self.game.request_update_club_tactics(self.local_settings)

        if success:
            self.success_message = self.labels.get_text("TACTICS_UPDATE_SUCCESS")
            self.message_timer = 3.0
            # Important: Re-fetch data from server as lineup might have changed
            print("Tactics applied successfully. Re-fetching data...")
            self.local_settings = None
            self.has_unsaved_changes = False
            self.on_enter() # This will reset state and reload fresh data
        else:
            self.error_message = self.labels.get_text("TACTICS_UPDATE_FAILED")
            self.message_timer = 5.0
            # Keep local changes, user can try again or discard by leaving
            self.loading_state = "loaded" # Reset loading state on error
            self._update_apply_button_state()

    def handle_event(self, event: pygame.event.Event):
        """Handles input events for the tactics screen."""
        mouse_pos = pygame.mouse.get_pos()

        # --- Hover Checks ---
        all_buttons = list(self.role_buttons.values()) + \
                      [self.formation_prev_button, self.formation_next_button,
                       self.playstyle_prev_button, self.playstyle_next_button,
                       self.apply_button]
        for btn in all_buttons:
            if btn: btn.check_hover(mouse_pos)

        # --- Button Clicks ---
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = False
            # Check cycle buttons
            if self.formation_prev_button and self.formation_prev_button.check_click(event.pos): clicked = True
            if not clicked and self.formation_next_button and self.formation_next_button.check_click(event.pos): clicked = True
            if not clicked and self.playstyle_prev_button and self.playstyle_prev_button.check_click(event.pos): clicked = True
            if not clicked and self.playstyle_next_button and self.playstyle_next_button.check_click(event.pos): clicked = True
            # Check role buttons
            if not clicked:
                for btn in self.role_buttons.values():
                    if btn.check_click(event.pos): clicked = True; break
            # Check Apply button (only if active)
            if not clicked and self.apply_button and self.has_unsaved_changes:
                 if self.apply_button.check_click(event.pos): clicked = True

        # --- Keyboard ---
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.change_screen("GameMenu") # Go back to the main game menu view


    def update(self, dt: float):
        """Updates message timers."""
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.success_message = None
                self.error_message = None

    def _get_main_content_rect(self) -> pygame.Rect:
        """Helper function to calculate the main content area rectangle."""
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()
        button_width_const = self.constants.BUTTON_WIDTH
        margin_const = self.constants.BUTTON_MARGIN
        side_panel_width = button_width_const + 2 * margin_const

        return pygame.Rect(
            side_panel_width, margin_const,
            screen_w - 2 * side_panel_width,
            screen_h - 2 * margin_const
        )

    def draw(self, screen: pygame.Surface):
        """Draws the tactics screen."""
        main_rect = self._get_main_content_rect()
        pygame.draw.rect(screen, self.colors['panel'], main_rect)

        # --- Draw Title ---
        title_text = self.labels.get_text("TACTICS_TITLE")
        title_pos_y = main_rect.top + self.padding + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

        if self.loading_state == "loading":
            loading_text = self.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, main_rect.center, self.font_medium,
                           self.colors['text_normal'], center_x=True, center_y=True)
            return # Don't draw controls while loading/applying
        elif self.loading_state == "error":
             error_text = self.error_message or self.labels.get_text("TACTICS_LOAD_FAILED")
             self.draw_text(screen, error_text, main_rect.center, self.font_medium,
                           self.colors['error_text'], center_x=True, center_y=True)
             return # Don't draw controls if initial load failed

        # If loading finished (loaded state)
        center_x = main_rect.centerx
        current_y = main_rect.top + self.padding + self.title_height + self.item_spacing

        # --- Formation Selector ---
        label_text = self.labels.get_text("LABEL_FORMATION")
        label_pos_y = current_y + 10 # Adjust label position slightly
        self.draw_text(screen, label_text, (center_x, label_pos_y), self.font_medium, self.colors['text_normal'], center_x=True)
        current_y += 30 # Move down past label

        # Draw the current formation text
        formation_text = self.local_settings.formation if self.local_settings else "N/A"
        selector_width = 250 # Width reserved for the text display
        formation_text_rect = pygame.Rect(center_x - selector_width // 2, current_y, selector_width, self.button_height)
        pygame.draw.rect(screen, (40,40,40), formation_text_rect)
        pygame.draw.rect(screen, self.colors['border'], formation_text_rect, 1)
        self.draw_text(screen, formation_text, formation_text_rect.center, self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)

        if self.formation_prev_button: self.formation_prev_button.draw(screen)
        if self.formation_next_button: self.formation_next_button.draw(screen)
        current_y += self.button_height + self.section_spacing

        # --- Play Style Selector ---
        label_text = self.labels.get_text("LABEL_PLAY_STYLE")
        label_pos_y = current_y + 10
        self.draw_text(screen, label_text, (center_x, label_pos_y), self.font_medium, self.colors['text_normal'], center_x=True)
        current_y += 30

        playstyle_text = "N/A"
        if self.local_settings and self.local_settings.play_style:
            # Localize the playstyle enum value
            style_key = f"STYLE_{self.local_settings.play_style.upper()}"
            playstyle_text = self.labels.get_text(style_key, self.local_settings.play_style.replace("_", " ").title())

        playstyle_text_rect = pygame.Rect(center_x - selector_width // 2, current_y, selector_width, self.button_height)
        pygame.draw.rect(screen, (40,40,40), playstyle_text_rect)
        pygame.draw.rect(screen, self.colors['border'], playstyle_text_rect, 1)
        self.draw_text(screen, playstyle_text, playstyle_text_rect.center, self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)

        if self.playstyle_prev_button: self.playstyle_prev_button.draw(screen)
        if self.playstyle_next_button: self.playstyle_next_button.draw(screen)
        current_y += self.button_height + self.section_spacing

        # --- Specialist Roles ---
        main_rect = self._get_main_content_rect()
        role_section_start_x = main_rect.left + 50
        roles_config = [
             ("captain", "LABEL_CAPTAIN"), ("free_kick_taker", "LABEL_FK_TAKER"),
             ("penalty_taker", "LABEL_PEN_TAKER"), ("corner_taker", "LABEL_CORNER_TAKER")]
        longest_label_text = ""
        for _, label_key in roles_config:
            text = self.labels.get_text(label_key) + ":"
            if self.font_medium.size(text)[0] > self.font_medium.size(longest_label_text)[0]:
                longest_label_text = text
        role_label_width = self.font_medium.size(longest_label_text)[0] + 10
        role_start_y = self.role_buttons.get("captain").rect.y if self.role_buttons.get("captain") else main_rect.centery  # Fallback Y

        # Get the calculated button start X from where create_ui placed the first button
        button_start_x_for_align = self.role_buttons.get("captain").rect.x if self.role_buttons.get("captain") else role_section_start_x + role_label_width + self.item_spacing * 3

        for role_key, label_key in roles_config:
            button = self.role_buttons.get(role_key)
            if button:
                # Draw Label aligned with the button
                label_text = self.labels.get_text(label_key) + ":"
                # Position label text to the left of the button
                label_x = button.rect.left - self.item_spacing  # Space before button
                label_pos = (label_x, button.rect.centery)

                text_surf = self.font_medium.render(label_text, True, self.colors['text_normal'])
                text_rect = text_surf.get_rect(midright=label_pos) # Set midright anchor
                screen.blit(text_surf, text_rect)

                # Draw the button itself
                button.draw(screen)


        # --- Draw Apply Button ---
        if self.apply_button:
            # Explicitly set inactive color if no changes
            if not self.has_unsaved_changes:
                 self.apply_button.inactive_color = (100, 100, 100) # Darker gray when disabled
                 self.apply_button.active = False # Ensure internal state matches
            else:
                 # Use the standard inactive color if it becomes active again
                 self.apply_button.inactive_color = self.colors['inactive_button']
                 self.apply_button.active = True # Ensure internal state matches

            self.apply_button.draw(screen)

        # --- Draw Feedback Messages ---
        message_y = (self.apply_button.rect.top if self.apply_button else main_rect.bottom) - 30
        if self.message_timer > 0:
            msg_text = self.error_message or self.success_message
            msg_color = self.colors['error_text'] if self.error_message else self.colors['success_text']
            if msg_text:
                self.draw_text(screen, msg_text, (main_rect.centerx, message_y),
                               self.font_medium, msg_color, center_x=True, center_y=True)