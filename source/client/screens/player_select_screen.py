import pygame
from client.screens.base_screen import BaseScreen
from client.data_models import ClientPlayer
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Callable
from client.button import Button

if TYPE_CHECKING:
    from client.game import Game

COLOR_MATCH_PRIMARY = (100, 220, 100)  # Greenish
COLOR_MATCH_SECONDARY = (220, 220, 100) # Yellowish
COLOR_MISMATCH = (220, 100, 100)   # Reddish
COLOR_DEFAULT_ROW = (60, 60, 60)      # Default background
COLOR_DEFAULT_ROW_ALT = (50, 50, 50)  # Default alternating row


class PlayerSelectScreen(BaseScreen):
    """
    Screen for selecting a player from a provided list.
    Used for lineup changes or assigning tactical roles.
    """

    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.loading_state: str = "idle"
        self.error_message: Optional[str] = None
        self.title_override: Optional[str] = None # Allow custom title

        # Context received from the previous screen
        self.context: Dict[str, Any] = {}
        self.return_screen: str = "Lineup" # Default screen to go back to
        self.on_player_selected_callback: Optional[Callable[[int], None]] = None # Callback function
        self.filter_player_ids: Optional[List[int]] = None # Optional list of IDs to display

        # Data
        self.full_squad: List[ClientPlayer] = [] # needed for fallback/names
        self.display_players: List[ClientPlayer] = [] # Players filtered and sorted for display

        # --- Role Selection Specific Context ---
        self.role_to_set: Optional[str] = None # e.g., "captain", "fk_taker"

        # --- Lineup Selection Specific Context ---
        self.slot_index: Optional[int] = None
        self.lineup_position_name: Optional[str] = None
        self.current_player_id: Optional[int] = None
        self.is_sub_slot: bool = False
        self.all_starter_ids: List[int] = []
        self.all_sub_ids: List[int] = []
        # --- End Lineup Context ---


        # UI state
        self.scroll_offset_y: int = 0
        self.row_height: int = 40
        self.header_height: int = 30
        self.title_height: int = 60
        self.padding: int = 20
        self.item_spacing: int = 5
        self.hovered_row_index: Optional[int] = None
        self.player_row_rects: List[pygame.Rect] = []

        # Columns (can be simplified if only showing name/pos/ovr for role selection)
        self.columns = [
            ("NAME", 'name', 20, 250),
            ("POS", 'position', 280, 80),
            ("OVR", 'overall_rating', 370, 50),
            ("ROLE", 'role', 430, 90), # Role might still be useful context
            ("STATUS", 'status', 530, 90),
            ("VALUE", 'value', 630, 120),
        ]

        self.back_button: Optional[Button] = None # Use Button class now


    def on_enter(self, data: Optional[Dict] = None):
        """Receives context, fetches squad, filters, and sorts players."""
        super().on_enter(data)
        self.loading_state = "loading"
        self.error_message = None
        self.context = data or {}
        self.scroll_offset_y = 0
        self.hovered_row_index = None
        self.player_row_rects = []
        self.display_players = [] # Reset display list

        # --- Extract Core Context ---
        self.return_screen = self.context.get("return_screen", "Lineup")
        self.on_player_selected_callback = self.context.get("on_player_selected_callback")
        self.filter_player_ids = self.context.get("filter_player_ids") # List of IDs to show, or None
        self.title_override = self.context.get("title_override") # Custom title

        # --- Role Context ---
        self.role_to_set = self.context.get("role_to_set")

        # --- Lineup Context ---
        self.slot_index = self.context.get("slot_index")
        self.lineup_position_name = self.context.get("lineup_position_name")
        self.current_player_id = self.context.get("current_player_id")
        self.is_sub_slot = self.context.get("is_sub_slot", False)
        self.all_starter_ids = self.context.get("all_starter_ids", [])
        self.all_sub_ids = self.context.get("all_sub_ids", [])

        # Basic validation
        if not self.return_screen:
             self.loading_state = "error"; self.error_message = "Missing return screen context."
             print(f"PlayerSelectScreen Error: {self.error_message}"); return

        # Fetch the full squad (needed to get player objects from IDs)
        squad_list = self.game.request_squad_data()
        if squad_list is None:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("SQUAD_LOAD_FAILED")
            print(f"PlayerSelectScreen: {self.error_message}")
            return
        self.full_squad = squad_list
        squad_map = {p.player_id: p for p in self.full_squad} # Create map for easy lookup

        # Filter and sort players
        self._prepare_player_list(squad_map)

        # Create UI elements
        self._create_ui()

        self.loading_state = "loaded"
        print( f"PlayerSelectScreen: Prepared list of {len(self.display_players)} players.")


    def _create_ui(self):
        """Creates UI elements like the back button."""
        main_rect = self._get_panel_rect() # Use a helper for the panel area
        btn_w, btn_h = 150, 45
        self.back_button = Button(
            x=main_rect.left + self.padding,
            y=main_rect.bottom - btn_h - self.padding,
            width=btn_w, height=btn_h,
            text=self.labels.get_text("BACK"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self.go_back
        )

    def _prepare_player_list(self, squad_map: Dict[int, ClientPlayer]):
        """
        Filters and sorts players based on context (filter_player_ids or lineup logic).
        """
        self.display_players = []
        candidates = []

        if self.filter_player_ids is not None:
            # If a specific list of IDs is provided (e.g., for role selection from starters)
            print(f"Filtering based on provided IDs: {self.filter_player_ids}")
            for player_id in self.filter_player_ids:
                player = squad_map.get(player_id)
                # Ensure player exists and is eligible (not injured/suspended)
                if player and not player.is_injured and not player.is_suspended:
                    candidates.append(player)
            # Sort primarily by Overall for role selection
            candidates.sort(key=lambda p: p.overall_rating, reverse=True)

        else:
            # --- Fallback/Original Lineup Logic ---
            print(f"Filtering for lineup change. Excluding ID: {self.current_player_id}")
            target_pos_upper = self.lineup_position_name.upper() if self.lineup_position_name else None

            for p in self.full_squad:
                if (not p.is_injured and not p.is_suspended and p.player_id != self.current_player_id):
                    candidates.append(p)

            def sort_key_lineup(player: ClientPlayer):
                suitability_score = 0
                if target_pos_upper:
                    player_pos_upper = player.position.upper()
                    alt_pos_str = player.alternative_positions if isinstance(player.alternative_positions, str) else ""
                    player_alt_list = [ap.strip().upper() for ap in alt_pos_str.split(',') if ap.strip()]
                    if player_pos_upper == target_pos_upper: suitability_score = 2
                    elif target_pos_upper in player_alt_list: suitability_score = 1
                return -suitability_score, -player.overall_rating

            candidates.sort(key=sort_key_lineup)
            # --- End Fallback Logic ---

        self.display_players = candidates
        print(f"Final display list size: {len(self.display_players)}")


    def handle_event(self, event: pygame.event.Event):
        """Handles events for player selection."""
        mouse_pos = pygame.mouse.get_pos()

        # Handle back button first
        if self.back_button:
            self.back_button.check_hover(mouse_pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.back_button.check_click(event.pos):
                    # When clicking back button directly, DO NOT pass the tactics session flag
                    self.go_back()
                    return

        # Reset hover index for player rows
        self.hovered_row_index = None

        # --- Handle Mouse Motion for Row Hover ---
        if event.type == pygame.MOUSEMOTION:
             if self.loading_state == "loaded":
                 list_area_rect = self._get_list_area_rect()
                 if list_area_rect.collidepoint(mouse_pos):
                     for i, row_rect in enumerate(self.player_row_rects):
                         # Ensure index is valid for the *displayed* players
                         if i < len(self.display_players) and row_rect.collidepoint(mouse_pos):
                             self.hovered_row_index = i
                             break # Found hover, exit loop

        # --- Handle Mouse Wheel ---
        elif event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.display_players:
                list_area_rect = self._get_list_area_rect()
                content_h = len(self.display_players) * (self.row_height + self.item_spacing)
                visible_list_area_h = list_area_rect.height
                max_scroll = max(0, content_h - visible_list_area_h)

                self.scroll_offset_y -= event.y * self.row_height
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll))

        # --- Handle Left Click on Player Row ---
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check player row clicks (only if Back button wasn't clicked)
            if self.loading_state == "loaded":
                list_area_rect = self._get_list_area_rect()
                if list_area_rect.collidepoint(mouse_pos): # Click must be within list area
                    for i, row_rect in enumerate(self.player_row_rects):
                        if i < len(self.display_players) and row_rect.collidepoint(mouse_pos):
                            selected_player = self.display_players[i]
                            print(f"PlayerSelectScreen: Selected player {selected_player.name} (ID: {selected_player.player_id})")

                            # --- Use the CALLBACK if provided (for Role selection) ---
                            if self.on_player_selected_callback:
                                print("Calling on_player_selected_callback...")
                                try:
                                    # Pass necessary info back (just player ID for roles)
                                    self.on_player_selected_callback(selected_player.player_id)
                                    self.go_back(data_to_pass_back={"returning_to_tactics_session": True})  # Go back after callback executed successfully
                                except Exception as e:
                                     print(f"Error executing player selection callback: {e}")
                                     self.error_message = "Callback error." # Show generic error
                                     self.loading_state = "error"
                                return # Callback handled

                            # --- Fallback/Original Lineup Swap Logic ---
                            # --- Lineup Change Logic (No ID filter, not role selection) ---
                            elif not self.filter_player_ids:
                                success = False

                                if self.is_sub_slot:
                                    # Replacing a substitute with another player from reserves/squad list
                                    print(
                                        f"Executing lineup SUB swap: PlayerIn={selected_player.player_id}, PlayerOut={self.current_player_id}, TargetSlot=None (Sub slot)")
                                    success = self.game.request_swap_lineup_players(
                                        player_in_id=selected_player.player_id,
                                        player_out_id=self.current_player_id,
                                        # current_player_id is the sub being replaced
                                        target_slot_index=None  # Indicate it's a sub being managed
                                    )
                                elif self.current_player_id is None and self.slot_index is not None:
                                    # Filling an EMPTY STARTER slot
                                    print(
                                        f"Executing lineup slot FILL: PlayerIn={selected_player.player_id}, TargetSlot={self.slot_index}")
                                    success = self.game.request_update_lineup_slot(
                                        slot_index=self.slot_index,
                                        new_player_id=selected_player.player_id
                                    )
                                elif self.current_player_id is not None and self.slot_index is not None:
                                    # SWAPPING an existing STARTER with another player
                                    print(
                                        f"Executing lineup STARTER swap: PlayerIn={selected_player.player_id}, PlayerOut={self.current_player_id}, TargetSlot={self.slot_index}")
                                    success = self.game.request_swap_lineup_players(
                                        player_in_id=selected_player.player_id,
                                        player_out_id=self.current_player_id,
                                        target_slot_index=self.slot_index
                                    )
                                else:
                                    print("PlayerSelectScreen: Unhandled lineup change scenario.")
                                    self.error_message = "Internal error: Unhandled lineup change."

                                if success:
                                    self.go_back()  # Go back to LineupScreen which should re-fetch
                                else:
                                    self.error_message = self.game.labels.get_text("LINEUP_UPDATE_FAILED")
                                    # self.loading_state = "error" # Or just show message
                                return
                            else:
                                print("Warning: Player clicked but no callback and not in lineup swap mode.")
                            return


    def go_back(self, data_to_pass_back: Optional[Dict] = None):
        """Navigates back to the screen specified in context, optionally passing data."""
        print(f"PlayerSelectScreen: Navigating back to {self.return_screen} with data: {data_to_pass_back}")
        # Return screen's on_enter should handle necessary refreshes
        self.game.change_screen(self.return_screen, data=data_to_pass_back)

    def update(self, dt: float):
        """Updates the screen state."""
        pass # Nothing time-dependent yet

    def _get_panel_rect(self) -> pygame.Rect:
        """Helper to get the main panel rect, similar to other screens."""
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()
        panel_margin_x = 80 # Slightly smaller margins?
        panel_margin_y = 40
        return pygame.Rect(
            panel_margin_x, panel_margin_y,
            screen_w - 2 * panel_margin_x,
            screen_h - 2 * panel_margin_y
        )


    def _get_list_area_rect(self) -> pygame.Rect:
        """Helper function to calculate the list display area rectangle."""
        main_rect = self._get_panel_rect()
        content_y_start = main_rect.top + self.padding
        header_base_y = content_y_start + self.title_height
        list_start_y = header_base_y + self.header_height

        bottom_reserved_space = 70 # Space for back button
        available_h = main_rect.height - (list_start_y - main_rect.top) - self.padding - bottom_reserved_space

        return pygame.Rect(
            main_rect.left, list_start_y,
            main_rect.width, available_h
        )

    def draw(self, screen: pygame.Surface):
        """Draws the player selection screen."""
        # --- Background Dimming ---
        dim_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        dim_surface.fill((0, 0, 0, 180))
        screen.blit(dim_surface, (0, 0))

        # --- Main Panel ---
        main_rect = self._get_panel_rect()
        pygame.draw.rect(screen, self.game.colors['panel'], main_rect)

        content_x_start = main_rect.left + self.padding
        content_y_start = main_rect.top + self.padding

        # --- Draw Title ---
        if self.title_override:
            title_text = self.title_override
        elif self.role_to_set:
            role_label = self.labels.get_text(f"LABEL_{self.role_to_set.upper()}", self.role_to_set.replace("_"," ").title())
            title_text = self.labels.get_text("PLAYER_SELECT_STARTERS_ONLY").format(role_name=role_label)
        elif self.is_sub_slot:
            title_text = self.labels.get_text("REPLACE_SUB")
        else:
            title_text = self.labels.get_text("SELECT_PLAYER")
            if self.lineup_position_name: title_text += f" ({self.lineup_position_name})"

        title_pos_y = content_y_start + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.game.colors['text_normal'], center_x=True, center_y=True)

        # --- Define List Area and Draw Headers ---
        header_base_y = content_y_start + self.title_height
        list_start_y = header_base_y + self.header_height

        for label_key, attr_name, x_offset, col_width in self.columns:
            header_text = self.labels.get_text(label_key)
            header_pos_x = main_rect.left + x_offset
            self.draw_text(screen, header_text, (header_pos_x, header_base_y + self.header_height // 2),
                           self.font_medium, self.colors['text_normal'], center_y=True)

        list_area_rect = self._get_list_area_rect()
        screen.set_clip(list_area_rect) # Set clipping

        current_y = list_area_rect.top - self.scroll_offset_y
        self.player_row_rects = [] # Reset for click detection

        if self.loading_state == "loading":
            loading_text = self.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, list_area_rect.center, self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error":
            error_text = self.error_message or self.labels.get_text("ERROR")
            self.draw_text(screen, error_text, list_area_rect.center, self.font_medium, self.colors['error_text'], center_x=True, center_y=True)
        elif self.loading_state == "loaded":
            if not self.display_players:
                empty_text = self.labels.get_text("NO_PLAYERS_AVAILABLE")
                self.draw_text(screen, empty_text, list_area_rect.center, self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)
            else:
                # --- Draw Player Rows ---
                target_pos_upper = self.lineup_position_name.upper() if self.lineup_position_name else None
                for i, player in enumerate(self.display_players):
                    base_row_color = COLOR_DEFAULT_ROW
                    # Apply suitability coloring ONLY if changing a lineup position
                    if target_pos_upper:
                        player_pos_upper = player.position.upper()
                        alt_pos_str = player.alternative_positions if isinstance(player.alternative_positions,
                                                                                 str) else ""
                        player_alt_list = [ap.strip().upper() for ap in alt_pos_str.split(',') if ap.strip()]

                        if player_pos_upper == target_pos_upper:
                            base_row_color = COLOR_MATCH_PRIMARY  # Greenish tint
                        elif target_pos_upper in player_alt_list:
                            base_row_color = COLOR_MATCH_SECONDARY  # Yellowish tint
                        else:
                            base_row_color = COLOR_MISMATCH  # Reddish tint for mismatch

                    # Add alternating row shading
                    row_color = base_row_color
                    if i % 2 != 0:
                        r, g, b = row_color
                        row_color = (max(0, r - 10), max(0, g - 10), max(0, b - 10))

                    # Hover effect
                    border_color = self.game.colors['border']
                    border_thickness = 1
                    if self.hovered_row_index == i:
                        r, g, b = row_color
                        row_color = (min(255, r + 30), min(255, g + 30), min(255, b + 30))
                        border_color = self.game.colors['active_button']
                        border_thickness = 2

                    # Calculate row rect
                    row_rect_x = list_area_rect.left + (self.padding // 4)
                    row_rect_width = list_area_rect.width - (self.padding // 2)
                    row_rect = pygame.Rect(row_rect_x, current_y, row_rect_width, self.row_height)
                    self.player_row_rects.append(row_rect)

                    # Draw if visible
                    if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                        pygame.draw.rect(screen, row_color, row_rect, border_radius=3)
                        pygame.draw.rect(screen, border_color, row_rect, border_thickness, border_radius=3)

                        # --- Determine Player Role Text (Use robust check) ---
                        player_role_text = self.labels.get_text("ROLE_RESERVE", "RES")  # Default
                        # Check if context provides starter/sub lists (lineup mode)
                        if self.all_starter_ids or self.all_sub_ids:
                            if player.player_id in self.all_starter_ids:
                                player_role_text = self.labels.get_text("ROLE_STARTER", "STA")
                            elif player.player_id in self.all_sub_ids:
                                player_role_text = self.labels.get_text("ROLE_SUB", "SUB")
                        # Check if context provides filtered IDs (role mode - implies starter)
                        elif self.filter_player_ids and player.player_id in self.filter_player_ids:
                            player_role_text = self.labels.get_text("ROLE_STARTER", "STA")
                        # --- End Determine Player Role ---

                        # Draw cell data using self.columns info
                        for label_key, attr_or_special_key, x_offset, col_width in self.columns:
                            cell_x = main_rect.left + x_offset
                            cell_text = ""
                            if attr_or_special_key == 'role':
                                cell_text = player_role_text
                            elif attr_or_special_key == 'value':
                                value = getattr(player, attr_or_special_key, None)
                                currency_symbol = self.game.labels.get_currency_symbol()
                                cell_text = f"{currency_symbol}{value:,}" if value is not None else "-"
                            else:
                                cell_text = str(getattr(player, attr_or_special_key, '-'))

                            self.draw_text(screen, cell_text, (cell_x + 5, row_rect.centery),
                                           self.font_small, self.game.colors['text_normal'], center_y=True)

                    current_y += self.row_height + self.item_spacing

        screen.set_clip(None) # Reset clipping

        # --- Draw Scrollbar ---
        if self.loading_state == "loaded" and self.display_players:
            content_h = len(self.display_players) * (self.row_height + self.item_spacing)
            visible_list_area_h = list_area_rect.height
            if content_h > visible_list_area_h:
                scrollbar_h = max(20, visible_list_area_h * (visible_list_area_h / content_h))
                scrollbar_y_ratio = self.scroll_offset_y / content_h if content_h > 0 else 0
                scrollbar_y = list_area_rect.top + (scrollbar_y_ratio * visible_list_area_h)
                scrollbar_x = list_area_rect.right - 10
                scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
                pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)

        # --- Draw Back Button ---
        if self.back_button:
            self.back_button.draw(screen)