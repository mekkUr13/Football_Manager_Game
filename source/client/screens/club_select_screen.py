import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from client.data_models import ClientLeagueDetail, ClientClubDetail
from client.ui_elements import InputBox
from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from client.game import Game

class ClubSelectScreen(BaseScreen):
    """
    Screen for selecting an available club within a chosen league.
    Displays lists of taken and available clubs.
    """
    def __init__(self, game: 'Game'):
        super().__init__(game)
        # ... (league_id, league_details, selected_club, loading_state, message) ...
        self.league_id: Optional[int] = None
        self.league_details: Optional[ClientLeagueDetail] = None
        self.selected_club: Optional[ClientClubDetail] = None
        self.loading_state = "idle"
        self.message: Optional[str] = None
        self.is_error_message: bool = False

        # Buttons
        self.back_button: Optional[Button] = None
        self.confirm_button: Optional[Button] = None

        # --- Add Search Input ---
        self.search_input: Optional[InputBox] = None
        self.search_term: str = ""

        # UI state for lists
        self.taken_scroll_y = 0
        self.available_scroll_y = 0
        self.row_height = 30
        self.list_item_spacing = 4
        self.list_padding = 20
        self.column_width = (self.game.screen.get_width() - 3 * self.list_padding) // 2
        self.available_club_rects: List[pygame.Rect] = []
        # Store the filtered list for drawing
        self.filtered_available_clubs: List[ClientClubDetail] = []


    def on_enter(self, data: Optional[Dict] = None):
         """Called when entering the screen. Fetches league details."""
         super().on_enter(data)
         # --- Use data if provided, otherwise keep existing ID ---
         new_league_id = data.get("league_id") if data else None
         if new_league_id is not None:
             self.league_id = new_league_id  # Update if new ID is passed
         # --- End league_id handling ---
         # self.league_details = None # Reset details
         self.selected_club = None # Reset selection
         self.message = None # Clear feedback message
         self.loading_state = "idle" # Reset loading state
         self.taken_scroll_y = 0
         self.available_scroll_y = 0
         self.search_term = "" # Reset search term
         self.filtered_available_clubs = [] # Reset filtered list

         if not self.league_id:
             print("ClubSelectScreen: Error - No league_id provided.")
             self.loading_state = "error"
             self.message = self.game.labels.get_text("INTERNAL_ERROR", "Internal Error: League ID missing.")
             self.is_error_message = True
             self.create_ui() # Create buttons even on error to allow going back
             return

         self.loading_state = "loading"
         print(f"ClubSelectScreen: Requesting details for league ID: {self.league_id}")

         # Use game method to fetch details, returns ClientLeagueDetail or None
         fetched_details = self.game.request_league_details(self.league_id)

         if fetched_details:
             self.league_details = fetched_details
             # Sort available clubs by name (server might do this, but ensures consistency)
             self.league_details.available_clubs.sort(key=lambda c: c.club_name)
             self._filter_available_clubs()
             self.loading_state = "loaded"
             print(f"ClubSelectScreen: Loaded details for '{self.league_details.name}'.")
         else:
             self.loading_state = "error"
             self.message = self.game.labels.get_text("LEAGUE_DETAIL_FAILED", "Error loading league details.")
             self.is_error_message = True
             print(f"ClubSelectScreen: {self.message}")

         self.create_ui() # Create buttons based on loaded state


    def create_ui(self):
         """Creates the Back and Confirm buttons."""
         btn_y = self.game.screen.get_height() - 70
         btn_w = 150
         spacing = 20
         self.back_button = Button(
             text=self.game.labels.get_text("BACK"), x=spacing, y=btn_y,
             width=btn_w, height=50, font_size=self.game.constants.FONT_SIZE_BUTTON,
             active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
             border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
             on_click=self.go_back
         )
         # Confirm button should only be active if a club is selected and available
         self.confirm_button = Button(
             text=self.game.labels.get_text("JOIN_CLUB"),
             x=self.game.screen.get_width() - btn_w - spacing, y=btn_y,
             width=btn_w, height=50, font_size=self.game.constants.FONT_SIZE_BUTTON,
             active_color=self.game.colors['active_button'],
             # Start inactive until a club is selected
             inactive_color=(100, 100, 100), # Darker gray when disabled
             border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
             on_click=self.confirm_selection,
             min_width=btn_w,  # Ensure minimum width
         )
         # self.confirm_button.rect.x = self.game.screen.get_width() - self.confirm_button.rect.width - spacing
         if self.confirm_button:
             self.confirm_button.rect.x = self.game.screen.get_width() - self.confirm_button.rect.width - spacing
         # List items are drawn dynamically
         # --- Create Search Input Box ---
         title_y = 50  # Y position of main title
         list_titles_y = title_y + 60  # Y position of "Taken"/"Available" titles
         list_start_y = list_titles_y + 35  # Y position where list items start

         # Position search box *below* the "Available Clubs" title
         search_box_y = list_titles_y + 5
         search_box_width = self.column_width - 20
         search_box_x = self.list_padding * 2 + self.column_width + 10

         self.search_input = InputBox(
             search_box_x, search_box_y, search_box_width, 35,
             self.font_small,
             placeholder=self.game.labels.get_text("SEARCH_CLUB", "Search Club...")
         )

    def _filter_available_clubs(self):
        """Filters the available clubs based on the current search term."""
        if self.league_details is None:
            self.filtered_available_clubs = []
            return

        if not self.search_term:
            # If search is empty, show all available clubs
            self.filtered_available_clubs = self.league_details.available_clubs[:]  # Copy list
        else:
            # Perform case-insensitive substring search
            term_lower = self.search_term.lower()
            self.filtered_available_clubs = [
                club for club in self.league_details.available_clubs
                if term_lower in club.club_name.lower()
            ]
        # Reset scroll position when filter changes
        self.available_scroll_y = 0
        # Reset selection if selected club is filtered out
        if self.selected_club and self.selected_club not in self.filtered_available_clubs:
            self.selected_club = None

    def select_club(self, club: ClientClubDetail):
         """Called when an available club is clicked."""
         if club and not club.is_taken:
             self.selected_club = club
             self.message = None # Clear previous messages
             print(f"ClubSelectScreen: Tentatively selected club: {club.club_name} (ID: {club.original_club_id})")
             # Update confirm button state (make it look active) - handled in draw
         else:
             print("ClubSelectScreen: Cannot select a taken club.")
             self.selected_club = None # Ensure nothing is selected if a taken one was somehow clicked


    def confirm_selection(self):
         """Attempts to join the selected club via a server request."""
         if not self.selected_club:
             self.message = self.game.labels.get_text("SELECT_CLUB_FIRST", "Please select an available club first.")
             self.is_error_message = True
             return
         if not self.game.user_id or not self.league_id:
              self.message = self.game.labels.get_text("INTERNAL_ERROR", "Internal error: Missing user or league ID.")
              self.is_error_message = True
              return
         # This is a client-side check; server performs the definitive check.
         if self.selected_club.is_taken:
             self.message = self.game.labels.get_text("CLUB_JUST_TAKEN", "Sorry, that club was just taken!")
             self.is_error_message = True
             self.selected_club = None # Reset selection
             return

         self.loading_state = "joining" # Indicate processing state
         self.message = self.game.labels.get_text("JOINING_CLUB", "Joining club...")
         self.is_error_message = False

         # Send request to the server
         response = self.game.network_client.send_request(
             "join_league_club",
             {
                 "user_id": self.game.user_id,
                 "tournament_id": self.league_id,
                 # Send the original_club_id of the selected ClientClubDetail object
                 "original_club_id": self.selected_club.original_club_id
             }
         )

         self.loading_state = "loaded" # Reset state after response

         if response and response.get("status") == "success":
              print("ClubSelectScreen: Successfully joined club.")
              # Server confirmation is the source of truth
              self.message = self.game.labels.get_text("JOIN_SUCCESS")
              self.is_error_message = False
              self.game.user_joined_club() # Notify game state (fetches user clubs)
              # Navigate back to Main Menu after success
              self.game.change_screen("MainMenu")
         else:
              # Handle failure
              print("DEBUG: Join Club request failed or returned error status.")
              error_msg = response.get('message') if response else self.game.labels.get_text("NO_RESPONSE", "No response from server")
              print(f"ClubSelectScreen: Failed to join club: {error_msg}")
              self.message = self.game.labels.get_text("JOIN_FAILED", "Join Failed:") + f" {error_msg}"
              self.is_error_message = True
              # Reset selection as the attempt failed
              self.selected_club = None
              # Optional: Refresh league details again to see updated status
              self.on_enter({"league_id": self.league_id})


    def go_back(self):
        """Returns to the League Selection screen."""
        self.game.change_screen("LeagueSelect")


    def handle_event(self, event: pygame.event.Event):

        mouse_pos = pygame.mouse.get_pos()
        if self.back_button: self.back_button.check_hover(mouse_pos)
        # --- Handle Search Input First ---
        search_updated = False
        if self.search_input:
            original_text = self.search_input.text
            self.search_input.handle_event(event)
            # Check if text actually changed
            if self.search_input.text != original_text:
                self.search_term = self.search_input.get_text()
                self._filter_available_clubs() # Refilter the list
                search_updated = True # Flag that search input handled the event

        # --- Handle Mouse Clicks (if not handled by search input) ---
        if not search_updated and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked_handled = False
            # Check bottom buttons
            if self.back_button and self.back_button.check_click(event.pos): clicked_handled = True
            if not clicked_handled and self.confirm_button and self.selected_club and self.confirm_button.check_click(event.pos): clicked_handled = True

            # Check clicks on FILTERED available clubs list items
            if not clicked_handled and self.loading_state == "loaded":
                for i, rect in enumerate(self.available_club_rects):
                    # Make sure the rect corresponds to a club in the *filtered* list
                    if rect.collidepoint(event.pos) and i < len(self.filtered_available_clubs):
                         self.select_club(self.filtered_available_clubs[i])
                         clicked_handled = True
                         break # Found click target

        # --- Handle Mouse Wheel Scrolling ---
        elif event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            # Define screen areas (adjust as needed)
            list_start_y = 120
            list_height = self.game.screen.get_height() - list_start_y - 100
            bottom_buttons_y = self.game.screen.get_height() - 70  # Approx Y where bottom buttons start

            taken_list_rect = pygame.Rect(self.list_padding, list_start_y, self.column_width, list_height)
            available_list_rect = pygame.Rect(self.list_padding * 2 + self.column_width, list_start_y,
                                              self.column_width, list_height)

            # Prioritize scrolling the list the mouse is directly hovering over
            scrolled = False
            if taken_list_rect.collidepoint(mouse_pos) and self.league_details:
                content_h = len(self.league_details.taken_clubs) * (self.row_height + self.list_item_spacing)
                max_scroll = max(0, content_h - taken_list_rect.height)
                self.taken_scroll_y -= event.y * self.row_height
                self.taken_scroll_y = max(0, min(self.taken_scroll_y, max_scroll))
                scrolled = True
            elif available_list_rect.collidepoint(mouse_pos) and self.league_details:
                content_h = len(self.filtered_available_clubs) * (
                            self.row_height + 15 + self.list_item_spacing)  # Use correct item height
                max_scroll = max(0, content_h - available_list_rect.height)
                self.available_scroll_y -= event.y * self.row_height
                self.available_scroll_y = max(0, min(self.available_scroll_y, max_scroll))
                scrolled = True

            # If not hovering over a specific list, but above the bottom buttons, scroll the available list
            elif not scrolled and mouse_pos[1] < bottom_buttons_y and self.league_details:
                content_h = len(self.filtered_available_clubs) * (self.row_height + 15 + self.list_item_spacing)
                max_scroll = max(0, content_h - available_list_rect.height)  # Use available list height
                self.available_scroll_y -= event.y * self.row_height
                self.available_scroll_y = max(0, min(self.available_scroll_y, max_scroll))

        # Handle keyboard input (Escape)
        elif event.type == pygame.KEYDOWN:
             # Allow escape only if search input is not active
             if event.key == pygame.K_ESCAPE and (not self.search_input or not self.search_input.active):
                 self.go_back()
             # Prevent Tab from escaping search input if needed (or handle focus change)

    def update(self, dt):
        """Update elements like input box cursor."""
        if self.search_input:
            self.search_input.update(dt)

    def draw(self, screen: pygame.Surface):
         """Draws the club selection screen."""
         # --- Draw Title ---
         league_name = self.league_details.name if self.league_details else '...'
         title = self.game.labels.get_text("SELECT_CLUB") + f" ({league_name})"
         title_y = 50
         self.draw_text(screen, title, (self.game.screen.get_width() // 2, title_y),
                        self.font_large, self.game.colors['text_normal'], center_x=True)

         # --- Define List Areas ---
         list_titles_y = title_y + 60  # Define Y position for list titles explicitly
         list_start_y = list_titles_y + 35
         list_height = self.game.screen.get_height() - list_start_y - 100 # Leave space for bottom buttons

         taken_list_rect = pygame.Rect(self.list_padding, list_start_y, self.column_width, list_height)
         available_list_rect = pygame.Rect(self.list_padding * 2 + self.column_width, list_start_y, self.column_width, list_height)

         # --- Draw List Titles ---
         taken_title = self.labels.get_text("TAKEN_CLUBS")
         self.draw_text(screen, taken_title, (taken_list_rect.centerx, list_titles_y),  # Use list_titles_y
                        self.font_medium, self.colors['text_normal'], center_x=True)

         available_list_title_x = self.list_padding * 2 + self.column_width + self.column_width // 2  # Center X for available title
         available_title = self.labels.get_text("AVAILABLE_CLUBS")
         self.draw_text(screen, available_title, (available_list_title_x, list_titles_y),  # Use list_titles_y
                        self.font_medium, self.colors['text_normal'], center_x=True)


         # --- Draw Search Box ---
         search_box_drawn_y = 0
         if self.search_input:
             # Position search box below the available list title
             self.search_input.rect.top = list_titles_y + 30  # Below title + padding
             self.search_input.rect.left = self.list_padding * 2 + self.column_width + 10  # Align with list column
             self.search_input.draw(screen)
             search_box_drawn_y = self.search_input.rect.bottom + 10
         else:
             search_box_drawn_y = list_start_y  # Fallback if no search box

         # --- Adjust Available List Y Start and Height ---
         available_list_start_y = search_box_drawn_y  # List starts below search box
         available_list_height = self.game.screen.get_height() - available_list_start_y - 100  # Remaining height
         available_list_rect = pygame.Rect(
             self.list_padding * 2 + self.column_width,
             available_list_start_y,  # Use calculated start Y
             self.column_width,
             available_list_height  # Use calculated height
         )

         # --- Draw Content based on Loading State ---
         if self.loading_state == "loading":
             loading_text = self.game.labels.get_text("LOADING")
             center_x = self.game.screen.get_width() // 2
             center_y = list_start_y + list_height // 2
             self.draw_text(screen, loading_text, (center_x, center_y), self.font_medium,
                            self.game.colors['text_normal'], center_x=True, center_y=True)
         elif self.loading_state == "error":
             error_text = self.message or self.game.labels.get_text("ERROR")
             center_x = self.game.screen.get_width() // 2
             center_y = list_start_y + list_height // 2
             self.draw_text(screen, error_text, (center_x, center_y), self.font_medium,
                            self.game.colors['error_text'], center_x=True, center_y=True)
         elif self.loading_state == "loaded" and self.league_details:
             # --- Draw Taken Clubs List ---
             screen.set_clip(taken_list_rect)
             current_y_taken = taken_list_rect.top - self.taken_scroll_y
             for i, club in enumerate(self.league_details.taken_clubs):
                 item_rect = pygame.Rect(taken_list_rect.left + 5, current_y_taken, taken_list_rect.width - 10, self.row_height)
                 if item_rect.bottom > taken_list_rect.top and item_rect.top < taken_list_rect.bottom:
                     bg_color = (70, 60, 60) # Reddish tint for taken
                     if i % 2 != 0: bg_color = (65, 55, 55)
                     pygame.draw.rect(screen, bg_color, item_rect, border_radius=3)
                     # Draw Club Name
                     self.draw_text(screen, club.club_name, (item_rect.left + 10, item_rect.centery),
                                    self.font_small, (180, 180, 180), center_y=True) # Greyed out text
                     # Draw Taken By Info
                     taken_by_text = f"({club.taken_by or 'AI'})"
                     taken_by_width = self.font_small.size(taken_by_text)[0]
                     self.draw_text(screen, taken_by_text, (item_rect.right - taken_by_width - 10, item_rect.centery),
                                    self.font_small, (180, 180, 180), center_y=True)
                 current_y_taken += self.row_height + self.list_item_spacing
             screen.set_clip(None) # Reset clip


             # --- Draw Available Clubs List ---
             screen.set_clip(available_list_rect)
             current_y_available = available_list_rect.top - self.available_scroll_y
             self.available_club_rects = []
             for i, club in enumerate(self.filtered_available_clubs):
                 # Use a slightly taller row height to fit more info
                 current_row_height = self.row_height + 15
                 item_rect = pygame.Rect(available_list_rect.left + 5, current_y_available,
                                         available_list_rect.width - 10, current_row_height)
                 if item_rect.bottom > available_list_rect.top and item_rect.top < available_list_rect.bottom:
                     is_selected = (self.selected_club and self.selected_club.original_club_id == club.original_club_id)
                     is_hovering = item_rect.collidepoint(pygame.mouse.get_pos())
                     # ... (determine bg_color) ...
                     if is_selected:
                         bg_color = self.game.colors['active_button']
                     elif is_hovering:
                         bg_color = (70, 90, 70)
                     else:
                         bg_color = (60, 80, 60)
                     if i % 2 != 0 and not is_hovering and not is_selected: bg_color = (55, 75, 55)

                     pygame.draw.rect(screen, bg_color, item_rect, border_radius=3)
                     text_color = self.game.colors['text_button'] if is_selected else self.game.colors['text_normal']

                     # --- Draw Club Info ---
                     name_y = item_rect.top + 8  # Position name near top
                     stats_y = name_y + 18  # Position stats below name

                     # Club Name
                     self.draw_text(screen, club.club_name, (item_rect.left + 10, name_y),
                                    self.font_small, text_color)  # Maybe font_medium?

                     # Draw Stats (Avg OVR, Value, Count) in smaller font
                     stats_parts = []
                     if club.avg_ovr is not None:
                         stats_parts.append(f"{self.labels.get_text('STAT_AVG_OVR')} {club.avg_ovr:.1f}")
                     if club.total_value is not None:
                         currency_symbol = self.labels.get_currency_symbol()
                         if club.total_value >= 1_000_000:
                             val_str = f"{club.total_value / 1_000_000:.1f}M"
                         elif club.total_value >= 1_000:
                             val_str = f"{club.total_value / 1_000:.0f}K"
                         else:
                             val_str = f"{club.total_value}"
                         stats_parts.append(f"{self.labels.get_text('STAT_VALUE')} {currency_symbol}{val_str}")
                     if club.player_count is not None:
                         stats_parts.append(f"{self.labels.get_text('STAT_PLAYERS')} {club.player_count}")

                     stats_text = "  ".join(stats_parts)  # Join parts with spaces

                     self.draw_text(screen, stats_text, (item_rect.left + 10, stats_y),
                                    self.font_small, text_color)

                     self.available_club_rects.append(item_rect)
                 else:
                     self.available_club_rects.append(pygame.Rect(0, 0, 0, 0))

                 current_y_available += current_row_height + self.list_item_spacing  # Use adjusted height
             screen.set_clip(None)

             # --- Draw Scrollbars (Optional) ---
             # Scrollbar for taken list
             taken_content_h = len(self.league_details.taken_clubs) * (self.row_height + self.list_item_spacing)
             if taken_content_h > taken_list_rect.height:
                 scrollbar_h = max(15, taken_list_rect.height * (taken_list_rect.height / taken_content_h))
                 scrollbar_y = taken_list_rect.top + (self.taken_scroll_y / taken_content_h) * taken_list_rect.height
                 pygame.draw.rect(screen, (100, 100, 100), (taken_list_rect.right + 2, scrollbar_y, 6, scrollbar_h), border_radius=3)
             # Scrollbar for available list
             avail_content_h = len(self.filtered_available_clubs) * (self.row_height + 15 + self.list_item_spacing)
             if avail_content_h > available_list_rect.height:
                 scrollbar_h = max(15, available_list_rect.height * (available_list_rect.height / avail_content_h))
                 scrollbar_y = available_list_rect.top + (self.available_scroll_y / avail_content_h) * available_list_rect.height
                 pygame.draw.rect(screen, (100, 100, 100), (available_list_rect.right + 2, scrollbar_y, 6, scrollbar_h), border_radius=3)


         # --- Draw Buttons ---
         if self.back_button: self.back_button.draw(screen)
         if self.confirm_button:
             # Make confirm button visually active/inactive based on selection
             self.confirm_button.active = bool(self.selected_club) # Visually active if selected
             # Optionally change inactive color based on selection state
             self.confirm_button.inactive_color = self.game.colors['inactive_button'] if self.selected_club else (100, 100, 100)
             self.confirm_button.draw(screen)

         # --- Draw Message Area ---
         if self.message:
             msg_color = self.game.colors['error_text'] if self.is_error_message else self.game.colors['success_text']
             if self.loading_state == "joining": msg_color = self.game.colors['text_normal'] # Neutral color while joining
             msg_y = self.back_button.rect.top - 30 # Position above buttons
             self.draw_text(screen, self.message, (self.game.screen.get_width() // 2, msg_y),
                            self.font_medium, msg_color, center_x=True)