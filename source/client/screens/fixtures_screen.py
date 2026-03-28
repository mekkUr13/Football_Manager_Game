import pygame
from client.screens.base_screen import BaseScreen
from client.data_models import ClientMatch
from typing import TYPE_CHECKING, List, Optional, Dict
import datetime as py_datetime

if TYPE_CHECKING:
    from client.game import Game

class FixturesScreen(BaseScreen):
    """
    Displays the match schedule (fixtures) for the currently active tournament.
    Highlights the user's team matches and shows results for simulated games.
    """
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.matches: List[ClientMatch] = []
        self.loading_state = "idle"
        self.error_message: Optional[str] = None
        # --- UI state adjustments ---
        self.scroll_offset_y = 0
        self.row_height = 45
        self.list_padding = 20
        self.item_spacing = 5
        self.title_height = 60
        self.header_height = 30
        self.padding = 20
        self.match_row_rects: List[pygame.Rect] = [] # To store clickable rects
        self.hovered_match_index: Optional[int] = None
        self.col_round_offset = 30  # Offset from main_rect.left
        self.col_home_offset = 90  # Offset from main_rect.left
        self.col_score_offset_from_center = 0  # Offset from main_rect.centerx
        self.col_away_offset_from_center = 70  # Offset from main_rect.centerx
        self.col_time_offset_from_right = 150  # Offset from main_rect.right


    def on_enter(self, data: Optional[Dict] = None):
        """Called when entering the screen. Fetches fixture data."""
        super().on_enter(data)
        self.matches = [] # Clear previous data
        self.scroll_offset_y = 0
        self.loading_state = "loading"
        self.error_message = None
        print("FixturesScreen: Entering screen, requesting fixtures...")

        # Use the game method which returns List[ClientMatch] or None
        match_list = self.game.request_fixtures_data()

        if match_list is not None:
            # Data should be sorted by round/time from server, but can resort if needed
            self.matches = match_list
            self.loading_state = "loaded"
            print(f"FixturesScreen: Successfully loaded {len(self.matches)} fixtures.")
        else:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("FIXTURES_LOAD_FAILED", "Failed to load fixtures.")
            print(f"FixturesScreen: Error loading fixtures: {self.error_message}")
        # No specific UI creation needed here beyond what BaseScreen provides

    def handle_event(self, event: pygame.event.Event):
        mouse_pos = pygame.mouse.get_pos()


        # --- Recalculate list_area_rect ---
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()
        button_width_const = self.constants.BUTTON_WIDTH
        margin_const = self.constants.BUTTON_MARGIN
        side_panel_width = button_width_const + 2 * margin_const
        main_rect = pygame.Rect(
            side_panel_width, margin_const,
            screen_w - 2 * side_panel_width,
            screen_h - 2 * margin_const
        )
        list_start_y = main_rect.top + self.padding + self.title_height + self.header_height
        list_area_height = main_rect.height - (list_start_y - main_rect.top) - self.padding
        list_area_rect = pygame.Rect(
            main_rect.left, list_start_y,
            main_rect.width, list_area_height
        )
        # --- End Recalculation ---

        # --- MOUSEMOTION: Update Hover Index ---
        if event.type == pygame.MOUSEMOTION:
            new_hover_index = None
            if self.loading_state == "loaded" and self.matches and list_area_rect.collidepoint(mouse_pos):
                # Iterate through all matches to find potential hover
                for i in range(len(self.matches)):
                    row_rect = self._get_row_rect(i, list_area_rect)

                    # Check visibility FIRST before collision
                    if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                        if row_rect.collidepoint(mouse_pos):
                            new_hover_index = i
                            break  # Found hover

            # Update hover state
            self.hovered_match_index = new_hover_index


        # --- MOUSEWHEEL: Handle Scrolling ---
        elif event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.matches:
                content_h = len(self.matches) * (self.row_height + self.item_spacing)
                visible_list_area_h = list_area_rect.height
                max_scroll = max(0, content_h - visible_list_area_h)
                self.scroll_offset_y -= event.y * self.row_height
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll))

        # --- MOUSEBUTTONDOWN: Handle Click ---
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            print( f"FixturesScreen Click: Pos={mouse_pos}, HoveredIndex={self.hovered_match_index}, LoadingState={self.loading_state}")  # Check again
            if self.loading_state == "loaded" and self.hovered_match_index is not None:
                hovered_row_rect = self._get_row_rect(self.hovered_match_index, list_area_rect)
                if hovered_row_rect.collidepoint(mouse_pos):  # Check if click is within list bounds
                    if 0 <= self.hovered_match_index < len(self.matches):
                        selected_match = self.matches[self.hovered_match_index]
                        if selected_match.is_simulated:
                            print(
                                f"FixturesScreen: Clicked on simulated match ID {selected_match.match_id}. Changing screen.")
                            # Ensure "MatchDetail" screen exists in Game.screens
                            if "MatchDetail" in self.game.screens:
                                self.game.change_screen("MatchDetail", data={"match_id": selected_match.match_id})
                            else:
                                print("Error: MatchDetail screen not found in game screens!")
                        else:
                            print(
                                f"FixturesScreen: Clicked on unsimulated match ID {selected_match.match_id}. No action.")
                    else:
                        print(
                            f"FixturesScreen Click Error: Hovered index {self.hovered_match_index} out of bounds (len {len(self.matches)}).")

    def draw(self, screen: pygame.Surface):
        # ... (Dynamically Calculate Main Content Area) ...
        screen_w = screen.get_width()
        screen_h = screen.get_height()
        button_width = self.constants.BUTTON_WIDTH
        margin = self.constants.BUTTON_MARGIN
        side_panel_width = button_width + 2 * margin
        main_rect = pygame.Rect(side_panel_width, margin, screen_w - 2 * side_panel_width, screen_h - 2 * margin)

        # Draw background panel
        pygame.draw.rect(screen, self.colors['panel'], main_rect)

        # ... (Draw Title) ...
        content_x_start = main_rect.left + self.padding
        content_y_start = main_rect.top + self.padding
        title = self.labels.get_text("FIXTURES")
        title_pos_y = content_y_start
        self.draw_text(screen, title, (main_rect.centerx, title_pos_y), self.font_large, self.colors['text_normal'],
                       center_x=True)

        # ... (Define List Area & Calculate Header Positions) ...
        list_start_y = title_pos_y + self.title_height  # Adjusted base Y for headers/list
        list_area_height = main_rect.height - (
                    list_start_y - main_rect.top) - self.padding * 2  # Space for headers and bottom padding
        list_area_rect = pygame.Rect(main_rect.left, list_start_y + self.header_height, main_rect.width,
                                     list_area_height - self.header_height)  # Actual list content area STARTS BELOW headers

        header_y = list_start_y  # Headers are drawn at list_start_y now
        header_round_x = main_rect.left + self.col_round_offset
        header_home_x = main_rect.left + self.col_home_offset
        header_score_x = main_rect.centerx + self.col_score_offset_from_center
        header_away_x = main_rect.centerx + self.col_away_offset_from_center
        header_time_x = main_rect.right - self.col_time_offset_from_right

        # --- Draw Headers ---
        self.draw_text(screen, self.labels.get_text("ROUND", "Rnd"), (header_round_x, header_y), self.font_medium,
                       self.colors['text_normal'])
        self.draw_text(screen, self.labels.get_text("HOME", "Home"), (header_home_x, header_y), self.font_medium,
                       self.colors['text_normal'])
        self.draw_text(screen, self.labels.get_text("SCORE", "Score"), (header_score_x, header_y), self.font_medium,
                       self.colors['text_normal'], center_x=True)
        self.draw_text(screen, self.labels.get_text("AWAY", "Away"), (header_away_x, header_y), self.font_medium,
                       self.colors['text_normal'])
        self.draw_text(screen, self.labels.get_text("TIME", "Time"), (header_time_x, header_y), self.font_medium,
                       self.colors['text_normal'])

        # --- Set Clipping for the actual list content area ---
        screen.set_clip(list_area_rect)

        # --- Draw Content ---
        self.match_row_rects.clear()

        # Define a DEBUG color for the hover rect outline
        DEBUG_HOVER_RECT_COLOR = (0, 100, 0)  # Dark green color

        if self.loading_state == "loaded" and self.matches:
            # ... (calculate visible index range) ...
            visible_start_index = int(self.scroll_offset_y // (self.row_height + self.item_spacing))
            visible_end_index = visible_start_index + int(
                list_area_rect.height // (self.row_height + self.item_spacing)) + 2
            visible_start_index = max(0, visible_start_index)
            visible_end_index = min(len(self.matches), visible_end_index)

            user_club_id = self.game.active_club_id
            for i in range(visible_start_index, visible_end_index):
                match_obj = self.matches[i]
                item_rect = self._get_row_rect(i, list_area_rect)  # Use helper
                self.match_row_rects.append(item_rect)

                if item_rect.bottom > list_area_rect.top and item_rect.top < list_area_rect.bottom:
                    is_hovered = (self.hovered_match_index == i)

                    # --- Determine bg/border colors ---
                    is_user_match = (user_club_id == match_obj.home_club_id or user_club_id == match_obj.away_club_id)
                    bg_color = (60, 60, 60)
                    if is_user_match: bg_color = (70, 70, 50)
                    if i % 2 != 0 and not is_user_match and not is_hovered:
                        bg_color = (bg_color[0] - 10, bg_color[1] - 10, bg_color[2] - 10)
                    border_color = self.colors['border']
                    border_thickness = 1
                    if is_hovered and match_obj.is_simulated:
                        r, g, b = bg_color
                        bg_color = (min(255, r + 20), min(255, g + 20), min(255, b + 20))
                        border_color = self.colors['active_button']
                        border_thickness = 2
                    # --- Draw row bg and border ---
                    pygame.draw.rect(screen, bg_color, item_rect)
                    pygame.draw.rect(screen, border_color, item_rect, border_thickness)

                    # --- Draw Fixture Details Text ---
                    text_y = item_rect.centery
                    text_color_default = self.colors['text_normal']
                    home_text_color = (255, 255, 150) if user_club_id == match_obj.home_club_id else text_color_default
                    away_text_color = (255, 255, 150) if user_club_id == match_obj.away_club_id else text_color_default
                    self.draw_text(screen, str(match_obj.round_number), (header_round_x, text_y), self.font_small,
                                   text_color_default, center_y=True)
                    self.draw_text(screen, match_obj.home_club_name or "?", (header_home_x, text_y), self.font_small,
                                   home_text_color, center_y=True)
                    if match_obj.is_simulated and match_obj.home_goals is not None and match_obj.away_goals is not None:
                        score_text = f"{match_obj.home_goals} - {match_obj.away_goals}"
                    else:
                        score_text = self.labels.get_text("VERSUS_SHORT", "vs")
                    self.draw_text(screen, score_text, (header_score_x, text_y), self.font_medium, text_color_default,
                                   center_x=True, center_y=True)
                    self.draw_text(screen, match_obj.away_club_name or "?", (header_away_x, text_y), self.font_small,
                                   away_text_color, center_y=True)
                    time_text = self.labels.get_formatted_datetime(match_obj.match_time_iso, "DATE_FORMAT_FIXTURE")
                    self.draw_text(screen, time_text, (header_time_x, text_y), self.font_small, text_color_default,
                                   center_y=True)

        # --- DEBUG: Draw the outline of the EXACT rect used for hover detection ---
        if self.hovered_match_index is not None:
            try:
                # Recalculate the rect for the hovered index using the SAME helper
                debug_rect = self._get_row_rect(self.hovered_match_index, list_area_rect)
                if debug_rect.colliderect(list_area_rect):
                    pygame.draw.rect(screen, DEBUG_HOVER_RECT_COLOR, debug_rect, 1)  # Draw dark green outline, 1px thick
            except IndexError:
                pass  # Ignore if index somehow becomes invalid between event handling and draw

        screen.set_clip(None)

        # --- Draw Scrollbar ---
        content_height = len(self.matches) * (self.row_height + self.item_spacing)
        if self.loading_state == "loaded" and content_height > (
                list_area_height - self.header_height):  # Compare with actual list content height
            scrollbar_h = max(20, list_area_rect.height * (list_area_rect.height / content_height))
            scrollbar_y = list_area_rect.top + (self.scroll_offset_y / content_height) * list_area_rect.height
            scrollbar_x = list_area_rect.right - 10
            scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)

    def _get_row_rect(self, index: int, list_area_rect: pygame.Rect) -> pygame.Rect:
        """
        Calculates the screen rectangle for a given row index based on
        the list area, scroll offset, row height, and item spacing.
        """
        # Calculate the top Y position of the row within the virtual scrollable content
        content_y = index * (self.row_height + self.item_spacing)

        # Adjust for the scroll offset and the list area's top position
        screen_y = list_area_rect.top + content_y - self.scroll_offset_y

        return pygame.Rect(list_area_rect.left, screen_y, list_area_rect.width, self.row_height)