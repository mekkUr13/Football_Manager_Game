import pygame
from client.screens.base_screen import BaseScreen
from client.data_models import ClientTransferListedPlayer
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple
from common.constants import ATTACKERS, MIDFIELDERS, DEFENDERS

if TYPE_CHECKING:
    from client.game import Game

# Define background colors for player rows
COLOR_USER_CLUB_PLAYER = (50, 70, 100)  # Blueish
COLOR_AFFORDABLE = (70, 100, 70)  # Greenish
COLOR_VALUE_AFFORDABLE = (100, 100, 70)  # Yellowish
COLOR_UNAFFORDABLE = (100, 70, 70)  # Reddish
COLOR_DEFAULT_ROW_ALT = (50, 50, 50)  # Alternating row default (darker)
COLOR_HOVER_BOOST = 30  # Brightness increase on hover


class TransfersScreen(BaseScreen):
    """
    Displays players available on the transfer market.
    Players are grouped by role and sorted. Background colors indicate affordability.
    """

    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.all_listed_players: List[ClientTransferListedPlayer] = []

        # Processed data for display: Dict[section_label, List[ClientTransferListedPlayer]]
        self.grouped_players: Dict[str, List[ClientTransferListedPlayer]] = {}

        self.loading_state: str = "idle"  # idle, loading, loaded, error
        self.error_message: Optional[str] = None
        self.active_club_budget: int = 0

        # UI state
        self.scroll_offset_y: int = 0
        self.row_height: int = 35
        self.header_height: int = 30
        self.section_label_height: int = 25  # Height for "Goalkeepers", "Defenders" labels
        self.title_height: int = 60
        self.padding: int = 20
        self.item_spacing: int = 3  # Small space between player rows
        self.hovered_row_info: Optional[Tuple[str, int]] = None  # (section_key, player_index_in_section)
        self.player_row_rects: List[pygame.Rect] = []  # For click detection later

        # Column definitions: (Label Key, Attribute on ClientTransferListedPlayer, X Offset, Width)
        # X Offsets are relative to the start of the main content area for the list.
        self.columns = [
            ("NAME", 'name', 20, 200),
            ("POS", 'position', 230, 60),
            ("OVR", 'overall_rating', 300, 50),
            ("AGE", 'age', 360, 50),
            ("VALUE", 'value', 420, 100),
            ("COL_ASKING_PRICE", 'asking_price', 530, 120),
            ("STATUS", 'status', 660, 100),  # Displays "Fit", "Inj (2r)", "Sus (1r)"
        ]

        # Section order for display
        self.section_order = ["SECTION_GOALKEEPERS", "SECTION_DEFENDERS", "SECTION_MIDFIELDERS", "SECTION_ATTACKERS"]

    def on_enter(self, data: Optional[Dict] = None):
        """Fetches transfer list data and processes it."""
        super().on_enter(data)
        self.all_listed_players = []
        self.grouped_players = {}
        self.scroll_offset_y = 0
        self.hovered_row_info = None
        self.player_row_rects = []
        self.loading_state = "loading"
        self.error_message = None

        # Get active club's budget
        self.active_club_budget = 0
        if self.game.active_club_id and self.game.user_clubs:
            active_club_info = next(
                (club for club in self.game.user_clubs if club.club_id == self.game.active_club_id), None
            )
            if active_club_info and hasattr(active_club_info, 'budget'):
                self.active_club_budget = active_club_info.budget

        print("TransfersScreen: Requesting transfer list data...")
        transfer_list = self.game.request_transfer_list_data()

        if transfer_list is not None:
            self.all_listed_players = transfer_list
            self._process_and_sort_players()
            self.loading_state = "loaded"
            print(f"TransfersScreen: Loaded and processed {len(self.all_listed_players)} players.")
        else:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("TRANSFER_LIST_LOAD_FAILED")
            print(f"TransfersScreen: {self.error_message}")

    def _get_player_role_group(self, position: str) -> str:
        """Categorizes a player's position into a display group."""
        pos_upper = position.upper()
        if pos_upper == "GK":
            return "SECTION_GOALKEEPERS"
        elif pos_upper in DEFENDERS:  # DEFENDERS constant should include "CB", "RB", "LB"
            return "SECTION_DEFENDERS"
        elif pos_upper in MIDFIELDERS:  # MIDFIELDERS constant: "CM", "CDM", "CAM", "LM", "RM"
            return "SECTION_MIDFIELDERS"
        elif pos_upper in ATTACKERS:  # ATTACKERS constant: "ST", "LW", "RW", "CF"
            return "SECTION_ATTACKERS"
        return "SECTION_ATTACKERS"  # Fallback, or could be "Other"

    def _process_and_sort_players(self):
        """Groups players by role and sorts them within each group."""
        self.grouped_players = {
            "SECTION_GOALKEEPERS": [],
            "SECTION_DEFENDERS": [],
            "SECTION_MIDFIELDERS": [],
            "SECTION_ATTACKERS": [],
        }

        for player in self.all_listed_players:
            role_group_key = self._get_player_role_group(player.position)
            if role_group_key in self.grouped_players:
                self.grouped_players[role_group_key].append(player)
            else:  # Should not happen if all positions are covered
                print(
                    f"Warning: Player {player.name} with position {player.position} did not fit a defined role group.")

        # Sort players within each group
        for group_key in self.grouped_players:
            # Sort criteria: Position (asc), Overall (desc), Asking Price (asc), Value (desc), Name (asc)
            self.grouped_players[group_key].sort(key=lambda p: (
                p.position,  # Primary: Position (e.g., "ST" before "RW")
                -p.overall_rating,  # Secondary: Overall (higher is better)
                p.asking_price,  # Tertiary: Asking Price (lower is better)
                -p.value,  # Quaternary: Value (higher is better, for tie-breaking expensive players)
                p.name  # Quinq: Name (alphabetical)
            ))

    def _get_row_background_color(self, player: ClientTransferListedPlayer, is_hovered: bool) -> Tuple[int, int, int]:
        """Determines the background color for a player row."""
        base_color = COLOR_UNAFFORDABLE  # Default to reddish

        if player.listing_club_id == self.game.active_club_id:  # Player from user's own club
            base_color = COLOR_USER_CLUB_PLAYER
        elif player.asking_price <= self.active_club_budget:
            base_color = COLOR_AFFORDABLE
        elif player.value <= self.active_club_budget:  # Asking price > budget, but value is affordable
            base_color = COLOR_VALUE_AFFORDABLE

        if is_hovered:
            r, g, b = base_color
            return (min(255, r + COLOR_HOVER_BOOST),
                    min(255, g + COLOR_HOVER_BOOST),
                    min(255, b + COLOR_HOVER_BOOST))
        return base_color

    def handle_event(self, event: pygame.event.Event):
        """Handles scrolling and hover for the transfer list."""
        mouse_pos = pygame.mouse.get_pos()
        previous_hover_info = self.hovered_row_info

        list_area_rect = self._get_list_area_rect()

        # --- Handle Mouse Motion for Row Hover ---
        if event.type == pygame.MOUSEMOTION:
            # Reset hover info ONLY if processing mouse motion
            self.hovered_row_info = None
            if self.loading_state == "loaded" and list_area_rect.collidepoint(mouse_pos):
                current_y_check = list_area_rect.top - self.scroll_offset_y
                found_hover = False
                for section_key_idx, section_key in enumerate(self.section_order):
                    players_in_section = self.grouped_players.get(section_key, [])

                    if players_in_section or (not players_in_section and section_key_idx < len(self.section_order) - 1):
                        current_y_check += self.section_label_height + self.item_spacing

                    if not players_in_section:
                        continue  # Skip to next section if this one is empty


                    for i, player in enumerate(players_in_section):
                        # Only create rect if it's potentially visible
                        if current_y_check + self.row_height > list_area_rect.top and current_y_check < list_area_rect.bottom:
                            row_rect = pygame.Rect(list_area_rect.left, current_y_check, list_area_rect.width,self.row_height)
                            if row_rect.collidepoint(mouse_pos):
                                self.hovered_row_info = (section_key, i)
                                found_hover = True
                                break
                        current_y_check += self.row_height + self.item_spacing
                    if found_hover: break

        # --- Handle Mouse Wheel ---
        elif event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.all_listed_players:
                total_content_height = 0
                for section_key in self.section_order:
                    players_in_section = self.grouped_players.get(section_key, [])
                    if players_in_section:
                        total_content_height += self.section_label_height + self.item_spacing
                        total_content_height += len(players_in_section) * (self.row_height + self.item_spacing)

                visible_list_area_h = list_area_rect.height
                max_scroll = max(0, total_content_height - visible_list_area_h)

                self.scroll_offset_y -= event.y * self.row_height  # Adjust scroll speed if needed
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll))

        # --- Handle Left Mouse Click ---
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            print( f"TransfersScreen: MOUSEBUTTONDOWN at {mouse_pos}. List area collides: {list_area_rect.collidepoint(mouse_pos)}. Hovered info: {self.hovered_row_info}, Loading state: {self.loading_state}")
            if self.loading_state == "loaded" and list_area_rect.collidepoint(mouse_pos):
                # Check if the click landed on a hovered row (identified by mouse motion)
                if self.hovered_row_info:
                    section_key, player_idx_in_section = self.hovered_row_info
                    try:
                        selected_player = self.grouped_players[section_key][player_idx_in_section]
                        print(f"TransfersScreen: Clicked on player: {selected_player.name} (ID: {selected_player.player_id})")
                        self.game.change_screen("PlayerProfile", data={
                            "player_id": selected_player.player_id,
                            "came_from": "Transfers"  # Pass context
                        })
                        return  # Click handled
                    except (KeyError, IndexError) as e:
                        print(f"Error accessing clicked player from grouped_players: {e}")
                        print(f"  Hovered info: {self.hovered_row_info}")
                        print(f"  Grouped_players keys: {list(self.grouped_players.keys())}")

    def _get_main_content_rect(self) -> pygame.Rect:
        """Helper to get the main panel rect, consistent with other screens."""
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

    def _get_list_area_rect(self) -> pygame.Rect:
        """Calculates the rectangle for the scrollable list content."""
        main_rect = self._get_main_content_rect()
        header_base_y = main_rect.top + self.padding + self.title_height
        list_start_y = header_base_y + self.header_height

        # Calculate available height for the list
        list_area_height = main_rect.height - (list_start_y - main_rect.top) - self.padding

        return pygame.Rect(
            main_rect.left, list_start_y,
            main_rect.width, list_area_height
        )

    def draw(self, screen: pygame.Surface):
        """Draws the transfer list screen."""
        main_rect = self._get_main_content_rect()
        pygame.draw.rect(screen, self.colors['panel'], main_rect)

        # --- Draw Title ---
        title_text = self.labels.get_text("TRANSFERS_TITLE")
        title_pos_y = main_rect.top + self.padding + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

        # --- Draw Column Headers ---
        header_base_y = main_rect.top + self.padding + self.title_height
        for label_key, attr_name, x_offset, col_width in self.columns:
            header_text = self.labels.get_text(label_key, label_key.replace("_", " ").title())
            header_pos_x = main_rect.left + x_offset
            self.draw_text(screen, header_text, (header_pos_x, header_base_y + self.header_height // 2),
                           self.font_medium, self.colors['text_normal'], center_y=True)

        list_area_rect = self._get_list_area_rect()
        screen.set_clip(list_area_rect)  # Set clipping for list items

        current_y = list_area_rect.top - self.scroll_offset_y
        self.player_row_rects = []  # Clear for current frame

        if self.loading_state == "loading":
            loading_text = self.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, list_area_rect.center, self.font_medium,
                           self.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error":
            error_text = self.error_message or self.labels.get_text("ERROR")
            self.draw_text(screen, error_text, list_area_rect.center, self.font_medium,
                           self.colors['error_text'], center_x=True, center_y=True)
        elif self.loading_state == "loaded":
            if not self.all_listed_players:
                empty_text = self.labels.get_text("TRANSFER_LIST_EMPTY")
                self.draw_text(screen, empty_text, list_area_rect.center, self.font_medium,
                               self.colors['text_normal'], center_x=True, center_y=True)
            else:
                for section_key_idx, section_key in enumerate(self.section_order):
                    players_in_section = self.grouped_players.get(section_key, [])
                    if not players_in_section:
                        continue

                    # --- Draw Section Label ---
                    section_label_rect = pygame.Rect(list_area_rect.left, current_y, list_area_rect.width,
                                                     self.section_label_height)
                    if section_label_rect.bottom > list_area_rect.top and section_label_rect.top < list_area_rect.bottom:
                        section_text = self.labels.get_text(section_key, section_key.replace("SECTION_", "").title())
                        # Simple background for section label
                        pygame.draw.rect(screen, (45, 45, 45), section_label_rect)
                        self.draw_text(screen, section_text,
                                       (section_label_rect.left + 10, section_label_rect.centery),
                                       self.font_medium, self.colors['text_normal'], center_y=True)
                    current_y += self.section_label_height + self.item_spacing

                    # --- Draw Player Rows in Section ---
                    for player_idx, player in enumerate(players_in_section):
                        is_hovered = self.hovered_row_info == (section_key, player_idx)
                        row_bg_color = self._get_row_background_color(player, is_hovered)

                        row_rect = pygame.Rect(list_area_rect.left, current_y, list_area_rect.width, self.row_height)
                        self.player_row_rects.append(row_rect)  # Store for click detection (if needed later)

                        if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                            pygame.draw.rect(screen, row_bg_color, row_rect)

                            border_color = self.colors['active_button'] if is_hovered else self.colors['border']
                            border_thickness = 2 if is_hovered else 1
                            pygame.draw.rect(screen, border_color, row_rect, border_thickness)

                            # Draw cell data
                            for col_label_key, col_attr_name, col_x_offset, col_width in self.columns:
                                cell_x = main_rect.left + col_x_offset
                                cell_text = ""
                                if col_attr_name == 'value' or col_attr_name == 'asking_price':
                                    value = getattr(player, col_attr_name, 0)
                                    currency_symbol = self.game.labels.get_currency_symbol()
                                    if value >= 1_000_000:
                                        cell_text = f"{currency_symbol}{value / 1_000_000:.1f}M"
                                    elif value >= 1_000:
                                        cell_text = f"{currency_symbol}{value / 1_000:.0f}K"
                                    else:
                                        cell_text = f"{currency_symbol}{value}"
                                else:
                                    cell_text = str(getattr(player, col_attr_name, '-'))

                                self.draw_text(screen, cell_text, (cell_x + 5, row_rect.centery),
                                               self.font_small, self.colors['text_normal'], center_y=True)
                        current_y += self.row_height + self.item_spacing

        screen.set_clip(None)  # Reset clipping

        # --- Draw Scrollbar ---
        total_content_height = 0
        for section_key in self.section_order:
            players_in_section = self.grouped_players.get(section_key, [])
            if players_in_section:
                total_content_height += self.section_label_height + self.item_spacing
                total_content_height += len(players_in_section) * (self.row_height + self.item_spacing)

        if self.loading_state == "loaded" and total_content_height > list_area_rect.height:
            scrollbar_h = max(20, list_area_rect.height * (list_area_rect.height / total_content_height))
            scrollbar_y_ratio = self.scroll_offset_y / total_content_height if total_content_height > 0 else 0
            scrollbar_y = list_area_rect.top + (scrollbar_y_ratio * list_area_rect.height)
            scrollbar_x = list_area_rect.right - 10
            scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)