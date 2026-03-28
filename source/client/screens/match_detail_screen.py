import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button

from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from client.game import Game


class MatchDetailScreen(BaseScreen):
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.match_info: Optional[Dict[str, Any]] = None
        self.match_events: List[Dict[str, Any]] = []  # List of event dicts

        self.loading_state = "idle"
        self.error_message: Optional[str] = None

        # UI state
        self.scroll_offset_y = 0
        self.event_row_height = 25  # Height for each event line
        self.padding = 20
        self.title_height = 80  # For match header
        self.item_spacing = 2
        self.back_button = None  # Will be created in on_enter

    def on_enter(self, data: Optional[Dict] = None):
        super().on_enter(data)
        self.match_info = None
        self.match_events = []
        self.scroll_offset_y = 0
        self.loading_state = "loading"
        self.error_message = None

        match_id_to_load = data.get("match_id") if data else None
        if not match_id_to_load:
            self.loading_state = "error"
            self.error_message = "Match ID missing."
            self._create_ui()
            return

        print(f"MatchDetailScreen: Requesting details for match ID {match_id_to_load}")
        response = self.game.network_client.send_request("get_match_details", {"match_id": match_id_to_load})

        if response and response.get("status") == "success":
            full_data = response.get("data", {})
            self.match_info = full_data.get("match_info")
            self.match_events = full_data.get("events", [])
            self.loading_state = "loaded"
            print(f"MatchDetailScreen: Loaded {len(self.match_events)} events for match.")
        else:
            self.loading_state = "error"
            self.error_message = response.get("message", "Failed to load match details.")
            print(f"MatchDetailScreen: Error - {self.error_message}")

        self._create_ui()

    def _create_ui(self):
        # Back Button
        btn_x = self.padding
        btn_y = self.game.screen.get_height() - 50 - self.padding
        self.back_button = self.game.labels.get_text("BACK")  # Get localized text
        self.back_button = Button(
            text=self.game.labels.get_text("BACK"), x=btn_x, y=btn_y,
            width=150, height=40, font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self.go_back
        )

    def go_back(self):
        self.game.change_screen("Fixtures")

    def handle_event(self, event: pygame.event.Event):
        if self.back_button:
            self.back_button.check_hover(pygame.mouse.get_pos())
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.back_button.check_click(event.pos):
                    return  # Handled

        # --- Recalculation of list_area_rect ---
        header_section_height = self.padding + self.title_height + self.padding
        bottom_section_height = self.padding + 40 + self.padding
        available_list_height = self.game.screen.get_height() - header_section_height - bottom_section_height
        list_area_rect = pygame.Rect(
            self.padding, header_section_height,
            self.game.screen.get_width() - 2 * self.padding,
            available_list_height
        )
        # --- End Recalculation ---


        if event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.match_events:
                # Calculate total content height including spacing
                num_events = len(self.match_events)
                content_h = (num_events * self.event_row_height) + (max(0, num_events - 1) * self.item_spacing)

                visible_list_area_h = list_area_rect.height # Use calculated height

                max_scroll = max(0, content_h - visible_list_area_h)

                self.scroll_offset_y -= event.y * self.event_row_height * 1.5 # Scroll speed

                # Clamp the scroll offset
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll)) # Clamping uses correct max_scroll

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.go_back()

    def draw(self, screen: pygame.Surface):
        screen.fill(self.colors['background'])  # Or draw game background image

        # --- Calculate Heights ---
        header_section_height = self.padding + self.title_height + self.padding  # Space above list
        bottom_section_height = self.padding + 40 + self.padding  # Space below list (for button)
        available_list_height = screen.get_height() - header_section_height - bottom_section_height

        header_y = self.padding + self.title_height // 2
        if self.loading_state == "loading":
            self.draw_text(screen, "Loading Match Details...", (screen.get_width() // 2, header_y),
                           self.font_large, self.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error" or not self.match_info:
            err_msg = self.error_message or "Match details unavailable."
            self.draw_text(screen, err_msg, (screen.get_width() // 2, header_y),
                           self.font_medium, self.colors['error_text'], center_x=True, center_y=True)
        else:
            # Draw Match Header (Team vs Team, Score)
            home_name = self.match_info.get('home_club_name', 'Home')
            away_name = self.match_info.get('away_club_name', 'Away')
            home_goals = self.match_info.get('home_goals', 0)
            away_goals = self.match_info.get('away_goals', 0)

            header_text = f"{home_name}  {home_goals} - {away_goals}  {away_name}"
            self.draw_text(screen, header_text, (screen.get_width() // 2, header_y),
                           self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

            # Draw Events List
            list_start_y = header_section_height
            list_area_rect = pygame.Rect(
                self.padding, list_start_y,
                screen.get_width() - 2 * self.padding,
                available_list_height
            )

            screen.set_clip(list_area_rect)
            # Calculate total content height INSIDE draw for scrollbar
            num_events = len(self.match_events)
            content_h = (num_events * self.event_row_height) + (max(0, num_events - 1) * self.item_spacing)

            current_event_y = list_area_rect.top - self.scroll_offset_y

            for event_data in self.match_events:
                minute = event_data.get('minute', '')
                desc = event_data.get('description', 'Unknown event')
                event_type_str = event_data.get('event_type', '').replace("_", " ").title()

                # Simple formatting, can be much nicer
                event_text = f"[{minute}'] {event_type_str}: {desc}"
                if "player_name" in event_data:
                    event_text += f" ({event_data['player_name']})"
                if "event_club_name" in event_data and event_data.get(
                        "player_name") is None:  # If club event without specific player
                    event_text += f" ({event_data['event_club_name']})"

                row_rect = pygame.Rect(list_area_rect.left + 5, current_event_y,
                                       list_area_rect.width - 10, self.event_row_height)

                if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                    self.draw_text(screen, event_text, (row_rect.left, row_rect.centery),
                                   self.font_small, self.colors['text_normal'], center_y=True)

                current_event_y += self.event_row_height + self.item_spacing
            screen.set_clip(None)

            # --- Scrollbar calculation ---
            if content_h > list_area_rect.height:
                max_scroll = max(0, content_h - list_area_rect.height)

                scrollbar_h = max(20, list_area_rect.height * (list_area_rect.height / content_h))
                scrollbar_y_ratio = self.scroll_offset_y / content_h if content_h > 0 else 0
                scrollbar_y = list_area_rect.top + (scrollbar_y_ratio * list_area_rect.height)
                scrollbar_x = list_area_rect.right + 2  # Slightly outside
                scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
                pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)

        if self.back_button:
            # Ensure back button is positioned correctly relative to screen bottom
            self.back_button.rect.bottom = screen.get_height() - self.padding
            self.back_button.draw(screen)