import pygame
from client.screens.base_screen import BaseScreen
from client.data_models import ClientStandingEntry
from typing import TYPE_CHECKING, List, Optional, Dict

if TYPE_CHECKING:
    from client.game import Game

class StandingsScreen(BaseScreen):
    """
    Displays the league standings for the currently active tournament.
    Shows club positions, points, wins, draws, losses, goals scored/against, and goal difference.
    """
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.standings: List[ClientStandingEntry] = []
        self.loading_state = "idle"  # idle, loading, loaded, error
        self.error_message: Optional[str] = None

        # UI state for the list
        self.scroll_offset_y: int = 0
        self.row_height: int = 35 # Height for each row in the table
        self.header_height: int = 30 # Height for the column header row
        self.title_height: int = 60 # Space for the screen title
        self.padding: int = 20 # Padding around the main content area

        # Column definitions: (Label Key, Attribute on ClientStandingEntry, X Offset, Width)
        # X Offsets are relative to the start of the main content area for the list.
        # Widths are approximate and can be tuned.
        col_padding = 10 # Space between columns
        current_x = self.padding # Start after initial padding

        self.columns = []
        # POS
        self.columns.append(("POS", 'position', current_x, 50))
        current_x += 50 + col_padding
        # Team
        self.columns.append(("COL_TEAM", 'club_name', current_x, 250)) # Wider for team names
        current_x += 250 + col_padding
        # Played
        self.columns.append(("COL_P", 'played', current_x, 40))
        current_x += 40 + col_padding
        # Wins
        self.columns.append(("COL_W", 'wins', current_x, 40))
        current_x += 40 + col_padding
        # Draws
        self.columns.append(("COL_D", 'draws', current_x, 40))
        current_x += 40 + col_padding
        # Losses
        self.columns.append(("COL_L", 'losses', current_x, 40))
        current_x += 40 + col_padding
        # Goals Scored
        self.columns.append(("COL_GS", 'goals_scored', current_x, 40))
        current_x += 40 + col_padding
        # Goals Against
        self.columns.append(("COL_GA", 'goals_conceded', current_x, 40))
        current_x += 40 + col_padding
        # Goal Difference
        self.columns.append(("COL_GD", 'goal_difference', current_x, 50))
        current_x += 50 + col_padding
        # Points
        self.columns.append(("COL_PTS", 'points', current_x, 50))


    def on_enter(self, data: Optional[Dict] = None):
        """Called when entering the screen. Fetches standings data."""
        super().on_enter(data)
        self.standings = []  # Clear previous data
        self.scroll_offset_y = 0
        self.loading_state = "loading"
        self.error_message = None
        print("StandingsScreen: Entering screen, requesting standings...")

        # Use the game method which returns List[ClientStandingEntry] or None
        standings_list = self.game.request_standings_data()

        if standings_list is not None:
            self.standings = standings_list
            self.loading_state = "loaded"
            print(f"StandingsScreen: Successfully loaded {len(self.standings)} entries.")
        else:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("STANDINGS_LOAD_FAILED")
            print(f"StandingsScreen: Error loading standings: {self.error_message}")

    def handle_event(self, event: pygame.event.Event):
        """Handles scrolling for the standings list."""
        if event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.standings:
                # Calculate scroll limits based on the dynamic main area
                main_rect = self._get_main_content_rect() # Helper to get current main area
                list_area_h = main_rect.height - self.title_height - self.header_height - (self.padding * 2)
                content_h = len(self.standings) * self.row_height # Total height of all rows
                max_scroll = max(0, content_h - list_area_h)

                self.scroll_offset_y -= event.y * self.row_height # Adjust scroll
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll)) # Clamp

    def _get_main_content_rect(self) -> pygame.Rect:
        """Helper function to calculate the main content area rectangle, similar to other screens."""
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
        """Draws the standings screen content within the dynamically calculated main area."""
        main_rect = self._get_main_content_rect()
        pygame.draw.rect(screen, self.colors['panel'], main_rect) # Draw panel background

        content_x_start = main_rect.left + self.padding
        content_y_start = main_rect.top + self.padding

        # --- Draw Title ---
        title_text = self.labels.get_text("STANDINGS_TITLE")
        title_pos_y = content_y_start + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

        # --- Define List Area & Draw Headers ---
        header_base_y = content_y_start + self.title_height
        list_start_y = header_base_y + self.header_height

        # Draw Column Headers relative to main_rect.left
        for label_key, attr_name, x_offset, col_width in self.columns:
            header_text = self.labels.get_text(label_key)
            # Adjust x_offset to be from main_rect.left, not self.padding
            header_pos_x = main_rect.left + x_offset # x_offset is already from main_rect start
            self.draw_text(screen, header_text, (header_pos_x, header_base_y + self.header_height // 2),
                           self.font_medium, self.colors['text_normal'], center_y=True)

        # --- List Area Clipping Rect ---
        list_area_height = main_rect.height - self.title_height - self.header_height - (self.padding * 2)
        list_area_rect = pygame.Rect(
            main_rect.left, list_start_y,
            main_rect.width, list_area_height
        )

        screen.set_clip(list_area_rect) # Set clipping for the list items

        current_y = list_area_rect.top - self.scroll_offset_y

        if self.loading_state == "loading":
            loading_text = self.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, list_area_rect.center, self.font_medium,
                           self.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error":
            error_text = self.error_message or self.labels.get_text("ERROR")
            self.draw_text(screen, error_text, list_area_rect.center, self.font_medium,
                           self.colors['error_text'], center_x=True, center_y=True)
        elif self.loading_state == "loaded":
            if not self.standings:
                empty_text = self.labels.get_text("NO_STANDINGS_DATA")
                self.draw_text(screen, empty_text, list_area_rect.center, self.font_medium,
                               self.colors['text_normal'], center_x=True, center_y=True)
            else:
                user_club_id = self.game.active_club_id
                for i, entry in enumerate(self.standings):
                    item_rect = pygame.Rect(list_area_rect.left, current_y, list_area_rect.width, self.row_height)

                    if item_rect.bottom > list_area_rect.top and item_rect.top < list_area_rect.bottom:
                        # --- Draw Row Background ---
                        is_user_club = (user_club_id == entry.club_id)
                        bg_color = (60, 60, 60) # Default row color
                        if is_user_club:
                            bg_color = (70, 70, 50) # Highlight user's club (e.g., yellowish)
                        if i % 2 != 0 and not is_user_club: # Alternate non-user rows
                            bg_color = (bg_color[0]-5, bg_color[1]-5, bg_color[2]-5)

                        pygame.draw.rect(screen, bg_color, item_rect)
                        pygame.draw.line(screen, (80, 80, 80), item_rect.bottomleft, item_rect.bottomright, 1) # Separator

                        # --- Draw Cell Data ---
                        text_y = item_rect.centery
                        text_color = self.colors['text_normal']
                        if is_user_club:
                            text_color = (255, 255, 150) # Brighter text for user's club

                        for label_key, attr_name, x_offset, col_width in self.columns:
                            cell_text = str(getattr(entry, attr_name, 'N/A'))
                            cell_x = main_rect.left + x_offset # x_offset is already relative to main_rect.left
                            # Center text in narrower columns (like P, W, D, L, GS, GA, GD, Pts)
                            center_in_col = col_width < 100
                            self.draw_text(screen, cell_text, (cell_x + (col_width // 2 if center_in_col else 5), text_y),
                                           self.font_small, text_color, center_x=center_in_col, center_y=True)

                    current_y += self.row_height # No item_spacing for tighter table look

        screen.set_clip(None) # Reset clipping

        # --- Draw Scrollbar ---
        content_height = len(self.standings) * self.row_height
        if self.loading_state == "loaded" and content_height > list_area_height:
            scrollbar_h = max(20, list_area_height * (list_area_height / content_height))
            scrollbar_y = list_area_rect.top + (self.scroll_offset_y / content_height) * list_area_height
            scrollbar_x = list_area_rect.right - 10 # Inside the dynamic list area
            scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)