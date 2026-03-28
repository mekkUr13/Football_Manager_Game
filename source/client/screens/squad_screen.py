import pygame
from client.screens.base_screen import BaseScreen
from client.data_models import ClientPlayer
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from client.game import Game


class SquadScreen(BaseScreen):
    """
    Displays the list of players for the currently active club.
    Player rows are clickable to view player profiles.
    """

    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.players: List[ClientPlayer] = []
        self.scroll_offset_y = 0
        self.row_height = 35
        self.header_height = 30
        self.title_height = 60
        self.padding = 20
        self.item_spacing = 3  # Space between rows

        self.loading_state = "idle"
        self.error_message: Optional[str] = None

        self.columns = [
            ("NAME", 'name', 20, 220),
            ("POS", 'position', 250, 70),
            ("AGE", 'age', 330, 50),
            ("OVR", 'overall_rating', 390, 50),
            ("VALUE", 'value', 450, 120),
            ("STATUS", 'status', 580, 120),
        ]

        self.player_row_rects: List[pygame.Rect] = []  # To store rects of drawn rows
        self.hovered_row_index: Optional[int] = None

    def on_enter(self, data: Optional[Dict] = None):
        super().on_enter(data)
        self.players = []
        self.scroll_offset_y = 0
        self.hovered_row_index = None
        self.player_row_rects = []
        self.loading_state = "loading"
        self.error_message = None
        print(f"{self.__class__.__name__}: Requesting fresh data...")

        squad_list = self.game.request_squad_data()

        if squad_list is not None:
            self.players = squad_list
            self.players.sort(key=lambda p: (-p.overall_rating, p.name))
            self.loading_state = "loaded"
            print(f"SquadScreen: Loaded {len(self.players)} players.")
        else:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("SQUAD_LOAD_FAILED")
            print(f"SquadScreen: {self.error_message}")

    def handle_event(self, event: pygame.event.Event):
        mouse_pos = pygame.mouse.get_pos()

        # Always reset hover before processing new mouse position
        previous_hover_index = self.hovered_row_index

        list_area_rect = self._get_list_area_rect()

        # --- Handle Mouse Motion for Row Hover ---
        if event.type == pygame.MOUSEMOTION:
            # Reset hover index ONLY if processing mouse motion
            self.hovered_row_index = None
            if self.loading_state == "loaded" and list_area_rect.collidepoint(mouse_pos):
                # Check against stored player_row_rects
                # This assumes draw() has been called at least once for current self.players
                current_y_check = list_area_rect.top - self.scroll_offset_y
                for i, player in enumerate(self.players):
                    if current_y_check + self.row_height > list_area_rect.top and \
                            current_y_check < list_area_rect.bottom:
                        row_rect = pygame.Rect(list_area_rect.left, current_y_check, list_area_rect.width,self.row_height)
                        if row_rect.collidepoint(mouse_pos):
                            self.hovered_row_index = i
                            break
                    current_y_check += self.row_height + self.item_spacing
                    # if current_y_check goes beyond list_area_rect.bottom, no need to check further rows
                    if current_y_check >= list_area_rect.bottom:
                        break


        # --- Handle Mouse Wheel Scrolling ---
        elif event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.players:
                content_h = len(self.players) * (self.row_height + self.item_spacing)
                visible_list_area_h = list_area_rect.height
                max_scroll = max(0, content_h - visible_list_area_h)

                self.scroll_offset_y -= event.y * self.row_height
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll))

        # --- Handle Left Mouse Click on Player Row ---
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            print( f"SquadScreen: MOUSEBUTTONDOWN at {mouse_pos}. List area collides: {list_area_rect.collidepoint(mouse_pos)}. Hovered index: {self.hovered_row_index}, Loading state: {self.loading_state}")
            # Check if the click happened within the list area and if a row was hovered
            if self.loading_state == "loaded" and \
               list_area_rect.collidepoint(mouse_pos) and \
               self.hovered_row_index is not None: # Check if a row is actually hovered

                if 0 <= self.hovered_row_index < len(self.players):
                    selected_player = self.players[self.hovered_row_index]
                    print(f"SquadScreen: Clicked on player: {selected_player.name} (ID: {selected_player.player_id})")
                    self.game.change_screen("PlayerProfile", data={
                        "player_id": selected_player.player_id,
                        "came_from": "Squad"
                    })
                    return

    def _get_main_content_rect(self) -> pygame.Rect:
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
        main_rect = self._get_main_content_rect()
        header_base_y = main_rect.top + self.padding + self.title_height
        list_start_y = header_base_y + self.header_height
        list_area_height = main_rect.height - (list_start_y - main_rect.top) - self.padding
        return pygame.Rect(
            main_rect.left, list_start_y,
            main_rect.width, list_area_height
        )

    def draw(self, screen: pygame.Surface):
        main_rect = self._get_main_content_rect()
        pygame.draw.rect(screen, self.colors['panel'], main_rect)

        # --- Draw Title ---
        title_text = self.game.labels.get_text("SQUAD")
        title_pos_y = main_rect.top + self.padding + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

        # --- Draw Column Headers ---
        header_base_y = main_rect.top + self.padding + self.title_height
        for label_key, attr_name, x_offset, col_width in self.columns:
            header_text = self.game.labels.get_text(label_key, label_key)
            header_pos_x = main_rect.left + x_offset
            self.draw_text(screen, header_text, (header_pos_x, header_base_y + self.header_height // 2),
                           self.font_medium, self.colors['text_normal'], center_y=True)

        list_area_rect = self._get_list_area_rect()
        screen.set_clip(list_area_rect)

        current_y = list_area_rect.top - self.scroll_offset_y
        self.player_row_rects.clear()  # Clear for current frame

        if self.loading_state == "loading":
            loading_text = self.game.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, list_area_rect.center, self.font_medium,
                           self.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error":
            error_text = self.error_message or self.game.labels.get_text("ERROR")
            self.draw_text(screen, error_text, list_area_rect.center, self.font_medium,
                           self.colors['error_text'], center_x=True, center_y=True)
        elif self.loading_state == "loaded":
            if not self.players:
                empty_text = self.game.labels.get_text("SQUAD_EMPTY")
                self.draw_text(screen, empty_text, list_area_rect.center, self.font_medium,
                               self.colors['text_normal'], center_x=True, center_y=True)
            else:
                for i, player_obj in enumerate(self.players):
                    row_rect = pygame.Rect(list_area_rect.left, current_y, list_area_rect.width, self.row_height)
                    self.player_row_rects.append(row_rect)  # Store rect for click detection

                    if row_rect.bottom > list_area_rect.top and row_rect.top < list_area_rect.bottom:
                        is_hovered = (self.hovered_row_index == i)

                        bg_color = (60, 60, 60)  # Default
                        if i % 2 != 0: bg_color = (50, 50, 50)  # Alternating
                        if is_hovered:
                            r, g, b = bg_color
                            bg_color = (min(255, r + 30), min(255, g + 30), min(255, b + 30))

                        pygame.draw.rect(screen, bg_color, row_rect)
                        border_color = self.colors['active_button'] if is_hovered else self.colors['border']
                        border_thickness = 2 if is_hovered else 1
                        pygame.draw.rect(screen, border_color, row_rect, border_thickness)

                        # Draw Cell Data
                        for col_label_key, col_attr_name, col_x_offset, col_width in self.columns:
                            cell_x = main_rect.left + col_x_offset
                            cell_text = ""
                            try:
                                if col_attr_name == 'value':
                                    value = getattr(player_obj, col_attr_name, 0)
                                    currency_symbol = self.game.labels.get_currency_symbol()
                                    if value >= 1_000_000:
                                        cell_text = f"{currency_symbol}{value / 1_000_000:.1f}M"
                                    elif value >= 1_000:
                                        cell_text = f"{currency_symbol}{value / 1_000:.0f}K"
                                    else:
                                        cell_text = f"{currency_symbol}{value:,}"
                                else:
                                    cell_text = str(getattr(player_obj, col_attr_name, 'N/A'))
                            except AttributeError:
                                cell_text = "Error"

                            self.draw_text(screen, cell_text, (cell_x + 5, row_rect.centery),
                                           self.font_small, self.colors['text_normal'], center_y=True)
                    current_y += self.row_height + self.item_spacing

        screen.set_clip(None)

        # --- Draw Scrollbar ---
        content_height = len(self.players) * (self.row_height + self.item_spacing)
        if self.loading_state == "loaded" and content_height > list_area_rect.height:
            scrollbar_h = max(20, list_area_rect.height * (list_area_rect.height / content_height))
            scrollbar_y_ratio = self.scroll_offset_y / content_height if content_height > 0 else 0
            scrollbar_y = list_area_rect.top + (scrollbar_y_ratio * list_area_rect.height)
            scrollbar_x = list_area_rect.right - 10
            scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)