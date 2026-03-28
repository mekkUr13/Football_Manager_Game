import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from client.data_models import ClientLeague
from typing import TYPE_CHECKING, Optional, List, Dict, Any
import datetime as py_datetime

if TYPE_CHECKING:
    from client.game import Game

class LeagueSelectScreen(BaseScreen):
    """
    Screen for selecting an available league (tournament) to join.
    Displays a scrollable list of leagues fetched from the server.
    """
    def __init__(self, game: 'Game'):
        """Initializes the LeagueSelectScreen."""
        super().__init__(game)
        # Store league data as a list of ClientLeague objects
        self.leagues: List[ClientLeague] = []
        self.loading_state = "idle" # Tracks data loading: idle, loading, error, loaded
        self.error_message: Optional[str] = None # Stores error messages for display
        self.back_button: Optional[Button] = None
        self.create_button: Optional[Button] = None

        # UI state for the list display
        self.scroll_offset_y = 0      # Current vertical scroll position of the list
        self.row_height = 45          # Height of each league item in the list
        self.list_padding = 100       # Horizontal padding for the list area
        self.item_spacing = 5         # Vertical space between list items
        self.title_height = 80        # Space reserved for the screen title
        self.bottom_button_height = 70 # Space reserved for bottom buttons

        # Cache list item rects for efficient click detection
        self.list_item_rects: List[pygame.Rect] = []

    def on_enter(self, data: Optional[Dict] = None):
        """Called when entering the screen. Fetches available leagues from the server."""
        super().on_enter(data) # Call base class method
        self.leagues = [] # Clear previous league data
        self.scroll_offset_y = 0 # Reset scroll position
        self.loading_state = "loading" # Set state to loading
        self.error_message = None # Clear previous errors
        print("LeagueSelectScreen: Entering screen, requesting available leagues...")

        # Use the game's method to fetch data, which returns List[ClientLeague] or None
        league_list = self.game.request_available_leagues()

        if league_list is not None:
            self.leagues = league_list # Store the list of ClientLeague objects
            self.loading_state = "loaded"
            print(f"LeagueSelectScreen: Successfully loaded {len(self.leagues)} available leagues.")
        else:
            # Handle failure to load leagues
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("LEAGUES_LOAD_FAILED", "Failed to load leagues.")
            print(f"LeagueSelectScreen: Error loading leagues: {self.error_message}")

        # Create UI elements like buttons after attempting data load
        self.create_ui()

    def create_ui(self):
        """Creates the static UI elements like Back and Create League buttons."""
        # Calculate button positions dynamically based on screen height
        btn_y = self.game.screen.get_height() - self.bottom_button_height + 10 # Position buttons within the bottom reserved space
        btn_w = 200 # Width for the buttons
        spacing = 30 # Spacing between buttons and screen edges

        # Back Button (Positioned on the left)
        self.back_button = Button(
            text=self.game.labels.get_text("BACK"),
            x=spacing,
            y=btn_y,
            width=btn_w, height=50, font_size=self.game.constants.FONT_SIZE_BUTTON,
            active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
            border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
            on_click=self.go_back # Assign the go_back method to be called on click
        )

        # Create League Button (Positioned on the right)
        self.create_button = Button(
            text=self.game.labels.get_text("CREATE_LEAGUE"),
            x=self.game.screen.get_width() - btn_w - spacing - 69,
            y=btn_y,
            width=btn_w, height=50, font_size=self.game.constants.FONT_SIZE_BUTTON,
            active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
             border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
            on_click=self.go_to_create_tournament, min_width=btn_w
        )

    def select_league(self, league: ClientLeague):
         """Handles the action when a league is selected from the list."""
         print(f"LeagueSelectScreen: Selected league '{league.name}' (ID: {league.tournament_id})")
         # Navigate to the Club Selection screen, passing the chosen league's ID
         self.game.change_screen("ClubSelect", data={"league_id": league.tournament_id})

    def go_to_create_tournament(self):
        """Navigates to the Tournament Creation screen."""
        print("LeagueSelectScreen: Navigating to Tournament Creation screen.")
        self.game.change_screen("TournamentCreation")

    def go_back(self):
        """Navigates back to the Main Menu screen."""
        print("LeagueSelectScreen: Navigating back to Main Menu.")
        self.game.change_screen("MainMenu")

    def handle_event(self, event: pygame.event.Event):
        """Handles user input events for the league selection screen."""
        # --- Hover check ---
        mouse_pos = pygame.mouse.get_pos()
        if self.back_button: self.back_button.check_hover(mouse_pos)
        if self.create_button: self.create_button.check_hover(mouse_pos)
        # --- End hover check ---

        # Handle mouse clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # Left mouse button
             clicked_handled = False
             # Check bottom buttons first
             if self.back_button and self.back_button.check_click(event.pos):
                 clicked_handled = True
             if not clicked_handled and self.create_button and self.create_button.check_click(event.pos):
                 clicked_handled = True

             # If no button was clicked, check clicks on list items
             if not clicked_handled and self.loading_state == "loaded":
                 for i, rect in enumerate(self.list_item_rects):
                     if rect.collidepoint(event.pos):
                         if i < len(self.leagues): # Ensure index is valid
                             self.select_league(self.leagues[i])
                             clicked_handled = True
                             break # Stop checking once an item is clicked

        # Handle mouse wheel scrolling for the league list
        elif event.type == pygame.MOUSEWHEEL:
            if self.loading_state == "loaded" and self.leagues:
                # Calculate scroll limits based on content height and view area
                list_area_h = self.game.screen.get_height() - self.title_height - self.bottom_button_height
                content_h = len(self.leagues) * (self.row_height + self.item_spacing)
                max_scroll = max(0, content_h - list_area_h)

                # Adjust scroll offset based on wheel movement (inverted direction feels more natural)
                self.scroll_offset_y -= event.y * self.row_height
                # Clamp the scroll offset within valid bounds [0, max_scroll]
                self.scroll_offset_y = max(0, min(self.scroll_offset_y, max_scroll))

        # Handle keyboard input
        elif event.type == pygame.KEYDOWN:
             if event.key == pygame.K_ESCAPE:
                 self.go_back() # Allow escaping back to main menu


    def draw(self, screen: pygame.Surface):
        """Draws the league selection screen."""
        # --- Draw Title ---
        title = self.game.labels.get_text("SELECT_LEAGUE")
        self.draw_text(screen, title, (self.game.screen.get_width() // 2, self.title_height // 2),
                       self.font_large, self.game.colors['text_normal'], center_x=True, center_y=True)

        # --- Define List Area ---
        list_area_y = self.title_height
        list_area_height = self.game.screen.get_height() - self.title_height - self.bottom_button_height
        list_area_rect = pygame.Rect(
            self.list_padding, list_area_y,
            self.game.screen.get_width() - 2 * self.list_padding,
            list_area_height
        )


        # --- Set Clipping for List Items ---
        screen.set_clip(list_area_rect)

        # --- Draw Content based on Loading State ---
        self.list_item_rects = [] # Clear previous rects before drawing
        current_y = list_area_rect.top - self.scroll_offset_y # Start drawing from top, adjusted by scroll

        if self.loading_state == "loading":
            loading_text = self.game.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, list_area_rect.center, self.font_medium,
                           self.game.colors['text_normal'], center_x=True, center_y=True)
        elif self.loading_state == "error":
            error_text = self.error_message or self.game.labels.get_text("ERROR")
            self.draw_text(screen, error_text, list_area_rect.center, self.font_medium,
                           self.game.colors['error_text'], center_x=True, center_y=True)
        elif self.loading_state == "loaded":
            if not self.leagues:
                empty_text = self.game.labels.get_text("NO_LEAGUES_FOUND", "No available leagues found.")
                self.draw_text(screen, empty_text, list_area_rect.center, self.font_medium,
                               self.game.colors['text_normal'], center_x=True, center_y=True)
            else:
                # Iterate through ClientLeague objects and draw each item
                for i, league in enumerate(self.leagues):
                    item_rect = pygame.Rect(
                        list_area_rect.left + 10, # Small internal padding
                        current_y,
                        list_area_rect.width - 20, # Adjust width for padding
                        self.row_height
                    )
                    # Only draw if the item is within the visible list area
                    if item_rect.bottom > list_area_rect.top and item_rect.top < list_area_rect.bottom:
                        # Determine background color (e.g., alternating or hover)
                        is_hovering = item_rect.collidepoint(pygame.mouse.get_pos())
                        bg_color = (70, 70, 90) if is_hovering else (60, 60, 80)
                        if i % 2 != 0 and not is_hovering: # Alternate row color slightly
                             bg_color = (55, 55, 75)

                        pygame.draw.rect(screen, bg_color, item_rect, border_radius=5)

                        # Draw league information inside the item rect
                        text_y = item_rect.centery
                        # League Name
                        self.draw_text(screen, league.name,
                                       (item_rect.left + 15, text_y),
                                       self.font_medium, self.game.colors['text_normal'], center_y=True)
                        # Slots Info
                        slots_text = self.game.labels.get_text("SLOTS_LABEL", "Slots:") + f" {league.filled_slots}/{league.number_of_clubs}"
                        slots_width = self.font_small.size(slots_text)[0]
                        self.draw_text(screen, slots_text,
                                       (item_rect.centerx, text_y), # Center horizontally approx
                                       self.font_small, self.game.colors['text_normal'], center_y=True)
                        # Start Time (Formatted)
                        start_time_text = self.labels.get_formatted_datetime(league.start_time_iso, "DATE_FORMAT_SHORT")
                        start_time_width = self.font_small.size(start_time_text)[0]
                        self.draw_text(screen, start_time_text,
                                       (item_rect.right - start_time_width - 15, text_y),
                                       self.font_small, self.game.colors['text_normal'], center_y=True)

                        # Store the screen rect for click detection
                        self.list_item_rects.append(item_rect)
                    else:
                         # Add a placeholder rect if not drawn, to keep indices aligned
                         self.list_item_rects.append(pygame.Rect(0,0,0,0))


                    # Move Y position for the next item
                    current_y += self.row_height + self.item_spacing

        # --- Reset Clipping ---
        screen.set_clip(None)

        # --- Draw Scrollbar (if needed) ---
        content_height = len(self.leagues) * (self.row_height + self.item_spacing)
        if self.loading_state == "loaded" and content_height > list_area_rect.height:
            scrollbar_h = max(20, list_area_rect.height * (list_area_rect.height / content_height))
            scrollbar_y = list_area_rect.top + (self.scroll_offset_y / content_height) * list_area_rect.height
            scrollbar_x = list_area_rect.right + 5 # Position slightly outside the list rect
            scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            pygame.draw.rect(screen, (100, 100, 100), scrollbar_rect, border_radius=4)


        # --- Draw Bottom Buttons ---
        if self.back_button: self.back_button.draw(screen)
        if self.create_button: self.create_button.draw(screen)