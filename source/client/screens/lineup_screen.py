import pygame
import json
from client.screens.base_screen import BaseScreen
from client.data_models import ClientPlayer
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from common.constants import FORMATION_TEMPLATES

if TYPE_CHECKING:
    from client.game import Game

COLOR_MATCH_PRIMARY = (100, 220, 100)  # Green
COLOR_MATCH_SECONDARY = (220, 220, 100) # Yellow
COLOR_MISMATCH = (220, 100, 100)   # Red
COLOR_EMPTY_SLOT = (150, 150, 150) # Grey for empty slots


class LineupScreen(BaseScreen):
    """
    Displays the current lineup for the active club, allowing player changes.
    """

    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.loading_state: str = "idle"  # idle, loading, loaded, error
        self.error_message: Optional[str] = None

        # Data for the lineup
        self.squad: List[ClientPlayer] = []
        self.formation_string: Optional[str] = None  # e.g., "4-4-2"
        self.formation_template: List[str] = []  # e.g., ["GK", "RB", ...]
        self.starting_player_ids_by_slot: List[
            Optional[int]] = []  # Player ID for each slot in formation_template order
        self.substitute_player_ids: List[int] = []

        # Processed data for display
        self.lineup_display_data: List[Dict[str, Any]] = []  # Each dict: {lineup_pos, player_obj, color}
        self.subs_display_data: List[Dict[str, Any]] = []

        # UI elements for the list
        self.scroll_offset_y: int = 0
        self.row_height: int = 40
        self.header_height: int = 30
        self.title_height: int = 60
        self.padding: int = 20
        self.item_spacing: int = 5

        # Column definitions (Label Key, X Pos Offset, Width)
        # These are offsets from the start of the main content area for the list.
        self.columns = [
            ("POS", 20, 80),         # Lineup Position (GK, ST, CM etc.)
            ("NAME", 110, 250),      # Player Name
            ("OVR", 370, 60),        # Player Overall
            ("PLAYER_POS", 440, 80), # Player's Primary Position
            ("ALT_POS", 530, 150)    # Player's Alternative Positions
        ]
        # Rects for clickable rows (for player selection later)
        self.lineup_row_rects: List[pygame.Rect] = []  # Starters only
        self.sub_row_rects: List[pygame.Rect] = []
        self.hovered_starter_index: Optional[int] = None
        self.hovered_sub_index: Optional[int] = None

    def on_enter(self, data: Optional[Dict] = None):
        """Fetches squad and tactics data when entering the screen."""
        super().on_enter(data)
        self.loading_state = "loading"
        self.error_message = None
        self.squad = []
        self.formation_string = None
        self.formation_template = []
        self.starting_player_ids_by_slot = []
        self.substitute_player_ids = []
        self.lineup_display_data = []
        self.scroll_offset_y = 0

        print("LineupScreen: Fetching data...")

        # 1. Fetch Squad Data
        squad_list = self.game.request_squad_data()
        if squad_list is None:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("SQUAD_LOAD_FAILED", "Failed to load squad.")
            print(f"LineupScreen: {self.error_message}")
            return
        self.squad = squad_list

        # 2. Fetch Club Tactics
        tactics_data = self.game.request_club_tactics()
        if tactics_data is None:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("TACTICS_LOAD_FAILED", "Failed to load tactics.")
            print(f"LineupScreen: {self.error_message}")
            return

        print(f"DEBUG CLIENT: Received tactics_data: {tactics_data}")
        self.formation_string = tactics_data.get('formation')
        starting_players_json = tactics_data.get('starting_players', "[]")
        substitutes_json = tactics_data.get('substitutes', "[]")

        if not self.formation_string:
            self.loading_state = "error"
            self.error_message = "Formation data missing from tactics."
            print(f"LineupScreen: {self.error_message}")
            return

        # Process fetched data
        self._process_lineup_data(tactics_data)
        self.loading_state = "loaded"
        print(f"LineupScreen: Data loaded. Formation: {self.formation_string}, {len(self.lineup_display_data)} starters.")

    def _process_lineup_data(self, tactics_data: Dict[str, Any]):
        """
        Processes raw tactics and squad data into a displayable format.
        Expects tactics_data to contain 'formation', 'starting_player_ids_ordered',
        and 'substitute_player_ids'.
        """
        self.lineup_display_data = []  # Reset starters
        self.subs_display_data = []  # Reset subs
        self.formation_string = tactics_data.get('formation')
        if not self.formation_string:
            self.error_message = "Formation data missing from tactics."
            self.loading_state = "error"
            print(f"LineupScreen: {self.error_message}")
            return

        try:
            self.formation_template = FORMATION_TEMPLATES.get(self.formation_string, [])
            if not self.formation_template:
                raise ValueError(f"Formation '{self.formation_string}' not found in templates.")
        except Exception as e:
            self.error_message = f"Error processing formation: {e}"
            self.loading_state = "error"
            print(f"LineupScreen: {self.error_message}")
            return

        # Create a quick lookup for players by ID
        player_map = {p.player_id: p for p in self.squad}

        print(f"DEBUG CLIENT: Player map keys: {list(player_map.keys())}")  # See available TournamentPlayer IDs

        # Get the ordered list of player IDs for starters and subs
        self.starting_player_ids_by_slot = tactics_data.get('starting_player_ids_ordered', [])
        self.substitute_player_ids = tactics_data.get('substitute_player_ids', [])
        print(f"DEBUG CLIENT: starting_player_ids_by_slot from server: {self.starting_player_ids_by_slot}")

        # --- Process Starters ---
        if not isinstance(self.starting_player_ids_by_slot, list):
            # ... (error handling for starters) ...
            self.starting_player_ids_by_slot = [None] * len(self.formation_template) if self.formation_template else []

        if len(self.starting_player_ids_by_slot) < len(self.formation_template):
            # ... (padding logic for starters) ...
            self.starting_player_ids_by_slot.extend(
                [None] * (len(self.formation_template) - len(self.starting_player_ids_by_slot)))
        elif len(self.starting_player_ids_by_slot) > len(self.formation_template):
            # ... (truncating logic for starters) ...
            self.starting_player_ids_by_slot = self.starting_player_ids_by_slot[:len(self.formation_template)]

        for i, template_pos_name in enumerate(self.formation_template):
            player_id_in_slot = self.starting_player_ids_by_slot[i] if i < len(
                self.starting_player_ids_by_slot) else None
            player_obj = player_map.get(player_id_in_slot) if player_id_in_slot is not None else None

            color = COLOR_EMPTY_SLOT
            if player_obj:
                player_primary_pos = player_obj.position.upper()
                alt_pos_str = player_obj.alternative_positions if isinstance(player_obj.alternative_positions,
                                                                             str) else ""
                player_alt_pos_list = [p.strip().upper() for p in alt_pos_str.split(',') if p.strip()]

                if template_pos_name.upper() == player_primary_pos:
                    color = COLOR_MATCH_PRIMARY
                elif template_pos_name.upper() in player_alt_pos_list:
                    color = COLOR_MATCH_SECONDARY
                else:
                    color = COLOR_MISMATCH

            self.lineup_display_data.append({
                "lineup_pos_name": template_pos_name,  # Use template position for starters
                "player_obj": player_obj,
                "color_code": color,
            })

        # --- Process Substitutes ---
        if not isinstance(self.substitute_player_ids, list):
            print(f"LineupScreen: Warning - Invalid format for substitute player IDs, skipping subs.")
            self.substitute_player_ids = []

        for sub_player_id in self.substitute_player_ids:
            player_obj = player_map.get(sub_player_id)
            if player_obj:
                # Subs always get the same "SUB" position label and color
                self.subs_display_data.append({
                    "lineup_pos_name": self.game.labels.get_text("SUB", "SUB"),  # Use "SUB" or localized version
                    "player_obj": player_obj,
                    "color_code": (50, 50, 100)  # Distinct color for subs (e.g., dark blue)
                })
            else:
                print(f"Warning: Substitute player ID {sub_player_id} not found in squad map.")

    def handle_event(self, event: pygame.event.Event):
        """Handles scrolling for the lineup list and future interactions."""
        mouse_pos = pygame.mouse.get_pos()  # Get mouse position for hover/click check
        self.hovered_starter_index = None  # Reset hover each frame
        self.hovered_sub_index = None  # Reset hover each frame

        # --- Calculate list area and total content height  ---
        list_area_rect = self._get_list_area_rect()
        starters_height = len(self.lineup_display_data) * (self.row_height + self.item_spacing)
        subs_label_height = self.header_height if self.subs_display_data else 0
        subs_height = len(self.subs_display_data) * (self.row_height + self.item_spacing)
        total_content_height = starters_height + subs_label_height + subs_height
        visible_list_area_h = list_area_rect.height
        max_scroll = max(0, total_content_height - visible_list_area_h)

        # --- Handle Mouse Wheel ---
        if event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded":
                self.scroll_offset_y -= event.y * self.row_height
                self.scroll_offset_y = max(0,min(self.scroll_offset_y, max_scroll))  # Clamp using calculated max_scroll

        # --- Handle Left Mouse Click (Starters and Subs) ---
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.loading_state == "loaded":
                # Check Starters
                for i, row_rect in enumerate(self.lineup_row_rects):
                    if i < len(self.lineup_display_data) and row_rect.collidepoint(mouse_pos):
                        clicked_slot_data = self.lineup_display_data[i]
                        lineup_pos_name = clicked_slot_data["lineup_pos_name"]
                        current_player = clicked_slot_data["player_obj"]
                        current_player_id = current_player.player_id if current_player else None
                        slot_index = i

                        print(
                            f"Clicked STARTER slot index {slot_index}: Pos={lineup_pos_name}, CurrentPlayerID={current_player_id}")
                        context_data = {
                            "slot_index": slot_index,  # Identify the starter slot
                            "lineup_position_name": lineup_pos_name,
                            "current_player_id": current_player_id,
                            "is_sub_slot": False,  # Flag this is a starter slot
                            "all_starter_ids": [pid for pid in self.starting_player_ids_by_slot if pid is not None],
                            "all_sub_ids": self.substitute_player_ids,  # Pass subs too
                            "return_screen": "Lineup"
                        }
                        self.game.change_screen("PlayerSelect", data=context_data)
                        return

                # Check Subs
                for i, row_rect in enumerate(self.sub_row_rects):
                    if i < len(self.subs_display_data) and row_rect.collidepoint(mouse_pos):
                        clicked_sub_data = self.subs_display_data[i]
                        sub_player = clicked_sub_data["player_obj"]  # Should always exist if row drawn
                        current_player_id = sub_player.player_id

                        print(f"Clicked SUB slot index {i}: CurrentPlayerID={current_player_id}")
                        context_data = {
                            "slot_index": None,  # No specific starter slot index
                            "lineup_position_name": None,  # No specific target position (can select any starter)
                            "current_player_id": current_player_id,  # ID of the sub being replaced
                            "is_sub_slot": True,  # Flag this is a sub slot
                            "all_starter_ids": [pid for pid in self.starting_player_ids_by_slot if pid is not None],
                            "all_sub_ids": self.substitute_player_ids,
                            "return_screen": "Lineup"
                        }
                        self.game.change_screen("PlayerSelect", data=context_data)
                        return

        # --- Handle Mouse Motion for Hover Effect (Starters and Subs) ---
        elif event.type == pygame.MOUSEMOTION:
            if self.loading_state == "loaded":
                if list_area_rect.collidepoint(mouse_pos):
                    # Check Starters Hover
                    for i, row_rect in enumerate(self.lineup_row_rects):
                        if i < len(self.lineup_display_data) and row_rect.collidepoint(mouse_pos):
                            self.hovered_starter_index = i
                            return  # Found hover, exit

                    # Check Subs Hover
                    for i, row_rect in enumerate(self.sub_row_rects):
                        if i < len(self.subs_display_data) and row_rect.collidepoint(mouse_pos):
                            self.hovered_sub_index = i
                            return  # Found hover, exit

    def draw(self, screen: pygame.Surface):
        """Draws the lineup screen."""
        # --- Dynamically Calculate Main Content Area ---
        screen_w = screen.get_width()
        screen_h = screen.get_height()
        button_width_const = self.constants.BUTTON_WIDTH
        margin_const = self.constants.BUTTON_MARGIN
        side_panel_width = button_width_const + 2 * margin_const

        main_rect = pygame.Rect(
            side_panel_width, margin_const,
            screen_w - 2 * side_panel_width,
            screen_h - 2 * margin_const
        )
        pygame.draw.rect(screen, self.game.colors['panel'], main_rect)  # Draw panel background

        content_x_start = main_rect.left + self.padding
        content_y_start = main_rect.top + self.padding

        # --- Draw Title ---
        title_text = self.game.labels.get_text("LINEUP", "Lineup")
        if self.formation_string:
            title_text += f" ({self.formation_string})"
        title_pos_y = content_y_start + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.game.colors['text_normal'], center_x=True, center_y=True)

        # --- Define List Area and Draw Headers ---
        header_base_y = content_y_start + self.title_height
        list_start_y = header_base_y + self.header_height

        # Draw Column Headers relative to main_rect.left
        for label_key, x_offset, col_width in self.columns:
            header_text = self.game.labels.get_text(label_key, label_key.replace("_", " ").title())
            header_pos_x = main_rect.left + x_offset  # Adjusted to be relative to main_rect
            self.draw_text(screen, header_text, (header_pos_x, header_base_y + self.header_height // 2),
                           self.font_medium, self.game.colors['text_normal'], center_y= True)

        # --- List Area Clipping Rect ---
        list_area_rect = self._get_list_area_rect()

        # --- Set Clipping ---
        screen.set_clip(list_area_rect)

        # --- Calculate Heights ---
        starters_height = len(self.lineup_display_data) * (self.row_height + self.item_spacing)
        subs_label_height = self.header_height if self.subs_display_data else 0  # Only add height if subs exist
        subs_height = len(self.subs_display_data) * (self.row_height + self.item_spacing)
        total_content_height = starters_height + subs_label_height + subs_height

        current_y = list_area_rect.top - self.scroll_offset_y
        self.lineup_row_rects = []  # Reset for click detection
        self.sub_row_rects = [] # Reset for click detection

        if self.loading_state == "loading":
            loading_text = self.game.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, list_area_rect.center, self.font_medium,
                           self.game.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error":
            error_text = self.error_message or self.game.labels.get_text("ERROR")
            self.draw_text(screen, error_text, list_area_rect.center, self.font_medium,
                           self.game.colors['error_text'], center_x=True, center_y=True)
        elif self.loading_state == "loaded":
            # --- Draw Starters ---
            for i, item_data in enumerate(self.lineup_display_data):
                player = item_data["player_obj"]
                lineup_pos_name = item_data["lineup_pos_name"]  # Template position
                color_code = item_data["color_code"]

                row_rect_x = list_area_rect.left + (self.padding // 4)
                row_rect_width = list_area_rect.width - (self.padding // 2)
                row_rect = pygame.Rect(row_rect_x, current_y, row_rect_width, self.row_height)
                self.lineup_row_rects.append(row_rect)  # Store rect for starters

                if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                    is_hovered = self.hovered_starter_index == i
                    bg_color = color_code
                    border_color = self.game.colors['border']
                    border_thickness = 1
                    if is_hovered:
                        r, g, b = bg_color
                        bg_color = (min(255, r + 30), min(255, g + 30), min(255, b + 30))
                        border_color = self.game.colors['active_button']
                        border_thickness = 2

                    pygame.draw.rect(screen, bg_color, row_rect, border_radius=3)
                    pygame.draw.rect(screen, border_color, row_rect, border_thickness, border_radius=3)

                    # Draw Cell Data (Position, Name, OVR, Player Pos, Alt Pos)
                    self._draw_player_row(screen, main_rect, row_rect, item_data, is_starter=True)

                current_y += self.row_height + self.item_spacing

            # --- Draw Substitutes Label ---
            if self.subs_display_data:
                label_y = list_area_rect.top - self.scroll_offset_y + starters_height + (self.padding // 2)
                label_rect = pygame.Rect(list_area_rect.left, label_y, list_area_rect.width, self.header_height)
                if label_rect.bottom > list_area_rect.top and label_rect.top < list_area_rect.bottom:
                    subs_text = self.game.labels.get_text("SUBSTITUTES", "Substitutes")
                    self.draw_text(screen, subs_text, (main_rect.centerx, label_rect.centery),
                                   self.font_medium, self.game.colors['text_normal'], center_x=True, center_y=True)
                current_y = label_y + self.header_height  # Update current_y for subs

            # --- Draw Substitutes ---
            # Start drawing subs below the label
            for i, item_data in enumerate(self.subs_display_data):
                player = item_data["player_obj"]
                # Use the processed "SUB" text
                lineup_pos_name = item_data["lineup_pos_name"]
                color_code = item_data["color_code"]  # Specific sub color

                row_rect_x = list_area_rect.left + (self.padding // 4)
                row_rect_width = list_area_rect.width - (self.padding // 2)
                row_rect = pygame.Rect(row_rect_x, current_y, row_rect_width, self.row_height)
                self.sub_row_rects.append(row_rect)

                if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                    is_hovered = self.hovered_sub_index == i  # Use sub hover index
                    # Determine bg/border for subs (maybe different hover?)
                    bg_color = color_code
                    border_color = self.game.colors['border']
                    border_thickness = 1
                    if is_hovered:
                        r, g, b = bg_color
                        bg_color = (min(255, r + 30), min(255, g + 30), min(255, b + 30))
                        border_color = self.game.colors['active_button']
                        border_thickness = 2

                    pygame.draw.rect(screen, bg_color, row_rect, border_radius=3)
                    pygame.draw.rect(screen, border_color, row_rect, border_thickness, border_radius=3)

                    self._draw_player_row(screen, main_rect, row_rect, item_data, is_starter=False)

                current_y += self.row_height + self.item_spacing


        # --- Reset Clipping ---
        screen.set_clip(None)

        # --- Draw Scrollbar ---
        visible_list_area_h = list_area_rect.height
        if self.loading_state == "loaded" and total_content_height > visible_list_area_h:
            scrollbar_h = max(20, visible_list_area_h * (visible_list_area_h / total_content_height))
            scrollbar_y_ratio = self.scroll_offset_y / total_content_height if total_content_height > 0 else 0
            scrollbar_y = list_area_rect.top + (scrollbar_y_ratio * visible_list_area_h)
            scrollbar_x = list_area_rect.right - 10
            scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)


    def _draw_player_row(self, screen, main_rect, row_rect, item_data, is_starter):
        """Helper method to draw the contents of a player row (starter or sub)."""
        player = item_data["player_obj"]
        # Use specific lineup position for starters, or predefined "SUB" for subs
        display_pos_name = item_data["lineup_pos_name"]

        # Column 1: Display Position (Lineup Pos or "SUB")
        pos_text_x = main_rect.left + self.columns[0][1]
        self.draw_text(screen, display_pos_name, (pos_text_x, row_rect.centery),
                       self.font_small, self.game.colors['text_normal'], center_y=True)

        # Column 2: Player Name
        name_text_x = main_rect.left + self.columns[1][1]
        player_name = player.name if player else self.game.labels.get_text("EMPTY_SLOT", "- Empty -")
        self.draw_text(screen, player_name, (name_text_x, row_rect.centery),
                       self.font_small, self.game.colors['text_normal'], center_y=True)

        # Column 3: Player OVR
        ovr_text_x = main_rect.left + self.columns[2][1]
        player_ovr = str(player.overall_rating) if player else "-"
        self.draw_text(screen, player_ovr, (ovr_text_x, row_rect.centery),
                       self.font_small, self.game.colors['text_normal'], center_y=True)

        # Column 4: Player's Primary Position
        player_pos_text_x = main_rect.left + self.columns[3][1]
        player_primary_pos = player.position if player else "-"
        self.draw_text(screen, player_primary_pos, (player_pos_text_x, row_rect.centery),
                       self.font_small, self.game.colors['text_normal'], center_y=True)

        # Column 5: Player's Alternative Positions
        alt_pos_text_x = main_rect.left + self.columns[4][1]
        alt_pos_str = "-"
        if player and isinstance(player.alternative_positions, str):
            cleaned_alt_pos = player.alternative_positions.strip()
            if cleaned_alt_pos and cleaned_alt_pos != "-":
                alt_pos_str = cleaned_alt_pos
        self.draw_text(screen, alt_pos_str, (alt_pos_text_x, row_rect.centery),
                       self.font_small, self.game.colors['text_normal'], center_y=True)

    def _get_list_area_rect(self) -> pygame.Rect:
        """Helper function to calculate the list display area rectangle."""
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()
        button_width_const = self.game.constants.BUTTON_WIDTH
        margin_const = self.game.constants.BUTTON_MARGIN
        side_panel_width = button_width_const + 2 * margin_const

        main_rect = pygame.Rect(
            side_panel_width, margin_const,
            screen_w - 2 * side_panel_width,
            screen_h - 2 * margin_const
        )
        content_y_start = main_rect.top + self.padding
        header_base_y = content_y_start + self.title_height
        list_start_y = header_base_y + self.header_height

        return pygame.Rect(
            main_rect.left,
            list_start_y,
            main_rect.width,
            main_rect.height - (list_start_y - main_rect.top) - self.padding
        )