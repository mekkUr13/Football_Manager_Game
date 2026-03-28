import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from client.data_models import ClientClubInfo
from typing import TYPE_CHECKING, List, Optional, Dict

if TYPE_CHECKING:
    from client.game import Game

class MainMenuScreen(BaseScreen):
    """
    Main menu screen shown after login. Displays user's club slots
    and allows starting a new career or selecting an existing club.
    """
    def __init__(self, game: 'Game'):
        super().__init__(game)
        # Stores ClientClubInfo objects or None for empty slots
        self.club_slots: List[Optional[ClientClubInfo]] = [None, None, None]
        self.club_buttons: List[Button] = []
        self.logout_button: Optional[Button] = None
        # Call create_ui_elements here, it will be updated by on_enter
        self.create_ui_elements()

    def on_enter(self, data: Optional[Dict] = None):
        """Called when the screen becomes active. Fetches user clubs."""
        super().on_enter(data)
        # This ensures the display is up-to-date after login or joining a club.
        self.game.fetch_user_clubs()
        self.update_club_slots() # Populate self.club_slots with fresh data
        # Refresh button text in case language changed in settings
        self.create_ui_elements() # Recreate buttons to potentially update text/state

    def create_ui_elements(self):
         """Creates the buttons for club slots."""
         self.club_buttons = []
         slot_width = 350
         slot_height = 150
         total_width = 3 * slot_width + 2 * 50 # 50px spacing between slots
         start_x = (self.game.screen.get_width() - total_width) // 2
         slot_y = 250 # Y position of the club slots

         # Create placeholder buttons for each slot
         for i in range(3):
             x = start_x + i * (slot_width + 50)
             # The text and appearance will be set dynamically in draw() based on club_slots
             btn = Button(
                 text="", # Dynamic text
                 x=x, y=slot_y, width=slot_width, height=slot_height,
                 font_size=self.game.constants.FONT_SIZE_LARGE, # Base font size
                 active_color=self.game.colors['active_button'],
                 inactive_color=self.game.colors['inactive_button'],
                 border_color=self.game.colors['border'],
                 text_color=self.game.colors['text_button'],
                 # Pass the index to the click handler
                 on_click=lambda index=i: self.handle_slot_click(index)
             )
             self.club_buttons.append(btn)

         # --- Create Logout Button ---
         logout_btn_w = 150
         logout_btn_h = 50
         logout_btn_x = self.constants.BUTTON_MARGIN  # Use constant margin
         logout_btn_y = self.game.screen.get_height() - logout_btn_h - self.constants.BUTTON_MARGIN  # Bottom margin

         self.logout_button = Button(
             text=self.labels.get_text("LOGOUT", "Logout"),  # Use localized text
             x=logout_btn_x, y=logout_btn_y,
             width=logout_btn_w, height=logout_btn_h,
             font_size=self.constants.FONT_SIZE_BUTTON,
             active_color=self.colors['active_button'],
             inactive_color=(100, 50, 50),
             border_color=self.colors['border'],
             text_color=self.colors['text_button'],
             on_click=self.game.logout,  # Call game's logout method directly
             min_width=logout_btn_w  # Ensure minimum width
         )
         # --- End Logout Button ---

         # Update the actual slot data after creating button structures
         self.update_club_slots()


    def update_club_slots(self):
         """Populates self.club_slots based on the game's current user_clubs list."""
         self.club_slots = [None] * 3 # Reset all slots to empty
         # Fill slots with ClientClubInfo objects from game.user_clubs
         for i, club_info in enumerate(self.game.user_clubs[:3]): # Limit to 3 slots
             if i < len(self.club_slots): # Ensure index is within bounds
                 self.club_slots[i] = club_info
         # The visual update happens in the draw method based on self.club_slots


    def handle_slot_click(self, index: int):
         """Handles clicks on one of the three club slots."""
         if 0 <= index < len(self.club_slots):
             clicked_club_info = self.club_slots[index]
             if clicked_club_info:
                 # Existing club selected - go to GameMenu for this club
                 print(f"Selected existing club: {clicked_club_info.club_name} (ID: {clicked_club_info.club_id})")
                 # Set the active club context in the game state
                 self.game.set_active_club(clicked_club_info)
                 # Navigate to the main game screen
                 self.game.change_screen("GameMenu")
             else:
                 # Empty slot clicked - start the "New Club" process
                 print("Selected 'New Club' slot.")
                 # Check if the user can create/join another club
                 if len(self.game.user_clubs) >= 3:
                      print(self.game.labels.get_text("MAX_CLUBS_REACHED", "Maximum number of clubs (3) reached."))
                 else:
                      # Navigate to the screen where the user selects a league
                      self.game.change_screen("LeagueSelect")
         else:
             print(f"Warning: Invalid slot index clicked: {index}")

    def handle_event(self, event: pygame.event.Event):
        """Handles user input events for the main menu."""
        # --- Hover check for buttons ---
        mouse_pos = pygame.mouse.get_pos()
        for btn in self.club_buttons:
            btn.check_hover(mouse_pos)
        if self.logout_button: self.logout_button.check_hover(mouse_pos)
        # --- End hover check ---

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # Left click
            clicked = False
            # Check clicks on club slot buttons
            for btn in self.club_buttons:
                if btn.check_click(event.pos): # Button's on_click calls handle_slot_click
                    clicked = True
                    break
            # Check click on logout button
            if not clicked and self.logout_button:
                if self.logout_button.check_click(event.pos): clicked = True

        if event.type == pygame.KEYDOWN:
             if event.key == pygame.K_ESCAPE:
                  print("Escape pressed on Main Menu. Logging out.") # Or prompt user
                  self.game.logout()


    def draw(self, screen: pygame.Surface):
         """Draws the main menu screen, including club slots."""
         # --- Draw Title ---
         # Example: Welcome message including username if available
         welcome_text = self.game.labels.get_text("WELCOME_MAIN_MENU", "Select a Club or Start a New Career")
         if self.game.username:
              # Personalize the welcome message slightly
              welcome_text = f"{self.game.labels.get_text('WELCOME', 'Welcome')}, {self.game.username}!"
         title_y = 100 # Adjust as needed
         self.draw_text(screen, welcome_text, (self.game.screen.get_width() // 2, title_y),
                        self.font_large, self.game.colors['text_normal'], center_x=True)
         subtitle_y = title_y + 50
         self.draw_text(screen, self.game.labels.get_text("SELECT_OR_NEW", "Select a club slot below:"),
                        (self.game.screen.get_width() // 2, subtitle_y),
                        self.font_medium, self.game.colors['text_normal'], center_x=True)

         # --- Draw Club Slots/Buttons ---
         for i, btn in enumerate(self.club_buttons):
             club_info = self.club_slots[i]

             # Check hover state regardless of slot type
             btn.check_hover(pygame.mouse.get_pos())  # Update hover state for border effect

             if club_info and club_info.club_name:
                 # --- Draw FILLED Slot Manually ---
                 # Determine colors based on hover
                 bg_color = self.colors['active_button'] if btn.hover else self.colors['inactive_button']
                 border_color = self.colors['active_button'] if btn.hover else self.colors['border']
                 border_thickness = 3 if btn.hover else 2

                 # Draw background and border manually
                 pygame.draw.rect(screen, bg_color, btn.rect)
                 pygame.draw.rect(screen, border_color, btn.rect, border_thickness)

                 # Club Name (Large font) - Position slightly higher
                 self.draw_text(screen, club_info.club_name,
                                (btn.rect.centerx, btn.rect.centery - 15),  # Move name up
                                self.font_large, self.colors['text_button'], center_x=True)

                 # --- Display League Name (Smaller Font) ---
                 if club_info.tournament_name:
                     self.draw_text(screen, club_info.tournament_name,
                                    (btn.rect.centerx, btn.rect.centery + 20),  # Position below name
                                    self.font_medium, self.colors['text_button'], center_x=True)  # Use medium font
             else:
                 # --- Draw EMPTY Slot using Button.draw ---
                 btn.inactive_color = (50, 90, 50)  # Dark Greenish
                 btn.text = self.labels.get_text("NEW_CLUB", "New Club")  # Set text
                 btn.draw(screen)  # Let the button draw itself

         # --- Draw Logout Button ---
         if self.logout_button:
             self.logout_button.draw(screen)