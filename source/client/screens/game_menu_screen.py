from datetime import datetime, timezone

import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from client.game import Game

class GameMenuScreen(BaseScreen):
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.buttons: List[Button] = []
        self.active_sub_screen_name: str = "Squad" # Default content view
        self.active_club_budget: Optional[int] = None # To store the current club's budget
        self.tournament_status_str: str = "" # Placeholder for tournament status
        self.create_navigation_buttons() # Create buttons on init
        self.leave_club_button: Optional[Button] = None
        self.show_leave_confirmation: bool = False
        self.confirmation_message: str = ""
        self.confirmation_dialog_rect = pygame.Rect(0, 0, 0, 0)
        self.confirm_yes_button: Optional[Button] = None
        self.confirm_no_button: Optional[Button] = None

    def on_enter(self, data: Optional[Dict] = None):
        super().on_enter(data)

        data_from_previous = data or {}  # Ensure data is a dict

        print(
            f"GameMenuScreen.on_enter called. Current active_sub_screen: {self.active_sub_screen_name}, Received data: {data_from_previous}")

        if not self.game.active_club_id:
            print("Error: Entered GameMenu without an active club. Returning to MainMenu.")
            self.game.change_screen("MainMenu")
            return

        # Always update these displays when GameMenu is entered/refreshed
        self._update_and_format_budget_display()
        self._fetch_and_format_tournament_status()
        self.create_navigation_buttons()

        sub_screen_to_activate = self.active_sub_screen_name  # Default to current
        data_for_sub_screen_to_use = None  # By default, pass original data

        if "is_refresh_request" in data_from_previous and "force_sub_screen" in data_from_previous:
            # This is a refresh request specifically for GameMenu telling it to refresh a sub-screen
            sub_screen_to_activate = data_from_previous["force_sub_screen"]
            data_for_sub_screen_to_use = data_from_previous.get("data_for_forced_sub_screen",
                                                                {"is_refresh_request": True})
            print(
                f"GameMenu.on_enter: Refreshing forced sub-screen: {sub_screen_to_activate} with data {data_for_sub_screen_to_use}")
        elif "returning_to_tactics_session" in data_from_previous:
            sub_screen_to_activate = "Tactics"
            data_for_sub_screen_to_use = data_from_previous  # Pass original data through
            print(f"GameMenu.on_enter: Returning to Tactics. Data: {data_for_sub_screen_to_use}")
        elif "force_sub_screen" in data_from_previous:  # Generic force_sub_screen without full refresh context
            sub_screen_to_activate = data_from_previous["force_sub_screen"]
            data_for_sub_screen_to_use = data_from_previous.get("data_for_forced_sub_screen")
            # If just forcing, pass original data if available
            print(f"GameMenu.on_enter: Forcing sub-screen: {sub_screen_to_activate}. Data: {data_for_sub_screen_to_use}")
        else:
            # Default entry or simple re-entry, keep current sub-screen active
            # and pass along any general data GameMenuScreen received.
            data_for_sub_screen_to_use = data_from_previous
            print(
                f"GameMenu.on_enter: Defaulting to sub-screen: {sub_screen_to_activate}. Data: {data_for_sub_screen_to_use}")

        self.active_sub_screen_name = sub_screen_to_activate  # Update active sub-screen name *before* calling change_sub_screen
        self.change_sub_screen(self.active_sub_screen_name, data_for_sub_screen=data_for_sub_screen_to_use)


    def create_navigation_buttons(self):
        """Creates the main navigation buttons using localized text."""
        self.buttons = []
        const = self.game.constants
        labels = self.game.labels

        # Define button keys and their corresponding screen names/actions
        # These keys MUST match the keys in button_function_map AND labels_dict
        button_defs_left = [
             ("SQUAD", "Squad"),
             ("LINEUP", "Lineup"),
             ("TRANSFERS", "Transfers"),
             ("TACTICS", "Tactics")
        ]
        button_defs_right = [
            ("MAIN_MENU", "MainMenu"),
            ("FIXTURES", "Fixtures"),
            ("STANDINGS", "Standings"),
            ("TRAINING", "Training")
        ]

        # --- Increase Top Margin ---
        start_y_offset = const.BUTTON_MARGIN + 40

        # Create left-side buttons
        for i, (label_key, screen_name_or_action) in enumerate(button_defs_left):
             button_text = labels.get_text(label_key)
             action = self.get_button_action(label_key, screen_name_or_action)
             if action:
                 button = Button(
                     text=button_text,
                     x=const.BUTTON_MARGIN,
                     y=start_y_offset + i * (const.BUTTON_HEIGHT + const.BUTTON_MARGIN),
                     width=const.BUTTON_WIDTH, height=const.BUTTON_HEIGHT, font_size=const.FONT_SIZE_BUTTON,
                     active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
                     border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
                     on_click=action
                 )
                 self.buttons.append(button)

        # Create right-side buttons
        for i, (label_key, screen_name_or_action) in enumerate(button_defs_right):
            button_text = labels.get_text(label_key)
            action = self.get_button_action(label_key, screen_name_or_action)
            if action:
                 button = Button(
                    text=button_text,
                    x=self.game.screen.get_width() - const.BUTTON_WIDTH - const.BUTTON_MARGIN,
                    y=start_y_offset + i * (const.BUTTON_HEIGHT + const.BUTTON_MARGIN),
                    width=const.BUTTON_WIDTH, height=const.BUTTON_HEIGHT, font_size=const.FONT_SIZE_BUTTON,
                    active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
                    border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
                    on_click=action
                 )
                 self.buttons.append(button)

            # --- Leave Club Button ---
            self.leave_club_button = None  # Reset
            if self._is_tournament_finished():  # Only create if finished
                const = self.game.constants
                # Position it below the status indicator
                status_panel_height = 35  # From _draw_status_indicator
                budget_panel_height = 40
                budget_y = 0
                tactics_button = next((btn for btn in self.buttons if btn.text == self.game.labels.get_text("TACTICS")),
                                      None)
                if tactics_button:
                    budget_y = tactics_button.rect.bottom + 20
                else:
                    budget_y = const.BUTTON_MARGIN + 4 * (const.BUTTON_HEIGHT + const.BUTTON_MARGIN) + 20
                status_y = budget_y + budget_panel_height + 10

                leave_btn_y = status_y + status_panel_height + 15  # Below status
                leave_btn_x = const.BUTTON_MARGIN
                leave_btn_width = const.BUTTON_WIDTH
                leave_btn_height = 40

                self.leave_club_button = Button(
                    text=self.labels.get_text("BUTTON_LEAVE_CLUB"),
                    x=leave_btn_x, y=leave_btn_y,
                    width=leave_btn_width, height=leave_btn_height,
                    font_size=const.FONT_SIZE_MEDIUM,
                    active_color=(200, 80, 80),  # Reddish active
                    inactive_color=(150, 50, 50),  # Darker Red inactive
                    border_color=self.colors['border'],
                    text_color=self.colors['text_button'],
                    on_click=self._initiate_leave_club
                )

    def _initiate_leave_club(self):
        """Shows confirmation dialog for leaving."""
        if not self.game.active_club_id: return
        # Get active club name
        active_club_info = next((c for c in self.game.user_clubs if c.club_id == self.game.active_club_id), None)
        club_name = active_club_info.club_name if active_club_info else "this club"

        msg = self.labels.get_text("CONFIRM_LEAVE_CLUB").format(club_name=club_name)
        self._create_confirmation_dialog_ui(msg, self._execute_leave_club)

    def _execute_leave_club(self):
        """Sends leave request to server."""
        self.show_leave_confirmation = False  # Hide dialog
        if not self.game.active_club_id or not self.game.user_id: return

        club_id_to_leave = self.game.active_club_id
        user_id = self.game.user_id

        print(f"Requesting to leave club {club_id_to_leave} for user {user_id}")
        response = self.game.network_client.send_request(
            "leave_club",
            {"user_id": user_id, "club_id": club_id_to_leave}
        )

        if response and response.get("status") == "success":
            left_club_name = response.get("data", {}).get("left_club_name", "the club")
            print(f"Successfully left club {left_club_name}")
            # Reset active club state in game
            self.game.active_club_id = None
            self.game.active_tournament_id = None
            # Go back to Main Menu, which will re-fetch user clubs
            self.game.change_screen("MainMenu")
        else:
            error_msg = response.get('message') if response else "No response"
            fail_msg = self.labels.get_text("LEAVE_CLUB_FAILED").format(error=error_msg)
            print(f"Failed to leave club: {error_msg}")

    def _create_confirmation_dialog_ui(self, message: str, yes_action: callable):
        """Creates UI for the confirmation dialog (similar to PlayerProfileScreen)."""
        self.confirmation_message = message
        self.confirm_action_callback = yes_action  # Store action for Yes button

        dialog_w, dialog_h = 450, 180
        dialog_x = (self.game.screen.get_width() - dialog_w) // 2
        dialog_y = (self.game.screen.get_height() - dialog_h) // 2
        self.confirmation_dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)

        btn_w, btn_h = 100, 40
        btn_y = dialog_y + dialog_h - btn_h - 20
        spacing = 30

        self.confirm_no_button = Button(
            x=dialog_x + (dialog_w // 2) - btn_w - spacing // 2,
            y=btn_y, width=btn_w, height=btn_h,
            text=self.game.labels.get_text("BUTTON_NO", "No"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._cancel_confirmation
        )
        self.confirm_yes_button = Button(
            x=dialog_x + (dialog_w // 2) + spacing // 2,
            y=btn_y, width=btn_w, height=btn_h,
            text=self.game.labels.get_text("BUTTON_YES", "Yes"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._execute_confirmation_callback  # Renamed for clarity
        )
        self.show_leave_confirmation = True

    def _cancel_confirmation(self):
        self.show_leave_confirmation = False
        self.confirm_yes_button = None
        self.confirm_no_button = None

    def _execute_confirmation_callback(self):
        if self.confirm_action_callback:
            self.confirm_action_callback()
        self._cancel_confirmation()  # Hide dialog after action attempt

    def get_button_action(self, label_key: str, screen_name_or_action: str):
         """Creates the lambda function for button clicks."""
         target_screen = screen_name_or_action

         # Special case for Main Menu button
         if target_screen == "MainMenu":
              return lambda: self.game.change_screen("MainMenu")
         else:
              # Default action is to change the sub-screen content
              return lambda screen=target_screen: self.change_sub_screen(screen)

    def change_sub_screen(self, screen_name: str, data_for_sub_screen: Optional[Dict] = None):
        """Changes the content displayed in the main area, passing data if provided."""
        print(f"GameMenu: Changing sub-screen to {screen_name} with data: {data_for_sub_screen}")
        self.active_sub_screen_name = screen_name

        if screen_name in self.game.screens:
            # Call on_enter for the target sub-screen, passing the data.
            self.game.screens[screen_name].on_enter(data=data_for_sub_screen)
        else:
            print(f"Warning: Sub-screen '{screen_name}' not found in game screens.")




    def handle_event(self, event: pygame.event.Event):
        # --- Handle Confirmation Dialog First ---
        if self.show_leave_confirmation:
            mouse_pos = pygame.mouse.get_pos()
            if self.confirm_yes_button: self.confirm_yes_button.check_hover(mouse_pos)
            if self.confirm_no_button: self.confirm_no_button.check_hover(mouse_pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.confirm_yes_button and self.confirm_yes_button.check_click(mouse_pos): return
                if self.confirm_no_button and self.confirm_no_button.check_click(mouse_pos): return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self._cancel_confirmation(); return
                if event.key == pygame.K_RETURN: self._execute_confirmation_callback(); return
            return  # Absorb all events while confirmation is shown

        # --- Hover checks ---
        mouse_pos = pygame.mouse.get_pos()
        for btn in self.buttons:
            btn.check_hover(mouse_pos)
        if self.leave_club_button: # Check leave button hover
            self.leave_club_button.check_hover(mouse_pos)
        # --- End hover checks ---
        # Handle side button clicks
        clicked_nav = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
             for btn in self.buttons:
                 if btn.check_click(event.pos):
                      clicked_nav = True
                      break
             if not clicked_nav and self.leave_club_button:  # Check leave button click
                if self.leave_club_button.check_click(event.pos):
                    clicked_nav = True  # Treat leave as handled


        # If a nav button wasn't clicked, pass event to the active sub-screen
        if not clicked_nav:
            active_sub_screen = self.game.screens.get(self.active_sub_screen_name)
            if active_sub_screen:
                active_sub_screen.handle_event(event)

        # Pass other events (like scrolling, keyboard) ONLY to the active sub-screen
        elif 'clicked_nav' not in locals() or not clicked_nav: # Ensure check happens only if MOUSEBUTTONDOWN didn't handle nav
            if self.active_sub_screen_name in self.game.screens:
                 self.game.screens[self.active_sub_screen_name].handle_event(event)


        if event.type == pygame.KEYDOWN:
             if event.key == pygame.K_ESCAPE:
                 self.game.change_screen("MainMenu")

    def _draw_budget_indicator(self, screen: pygame.Surface):
        """Draws the styled budget indicator."""
        const = self.game.constants

        # Find the "Tactics" button to position below it
        tactics_button = None
        for btn in self.buttons:
            if btn.text == self.game.labels.get_text("TACTICS"):
                tactics_button = btn
                break

        if not tactics_button:
            # Fallback position if Tactics button isn't found (should not happen)
            budget_y = const.BUTTON_MARGIN + 4 * (const.BUTTON_HEIGHT + const.BUTTON_MARGIN) + 20
        else:
            budget_y = tactics_button.rect.bottom + 20  # 20px below Tactics button

        budget_x = const.BUTTON_MARGIN
        budget_width = const.BUTTON_WIDTH  # Same width as nav buttons
        budget_height = 40  # Slightly shorter than nav buttons

        panel_rect = pygame.Rect(budget_x, budget_y, budget_width, budget_height)

        # Panel Style
        panel_bg_color = (40, 40, 40)  # Darker than main panel, but lighter than background
        panel_border_color = self.game.colors['border']

        pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=5)
        pygame.draw.rect(screen, panel_border_color, panel_rect, 2, border_radius=5)  # Border

        # Text Content
        budget_label_text = self.game.labels.get_text("BUDGET_LABEL", "Budget") + ":"

        # Draw Label (Left aligned)
        label_x_pos = panel_rect.left + 10
        self.draw_text(screen, budget_label_text,
                       (label_x_pos, panel_rect.centery),
                       self.font_small, self.colors['text_normal'],
                       center_y=True)

        # Draw Formatted Budget Value (Right aligned within the remaining space)
        # Calculate width of the label to position the value
        label_width = self.font_small.size(budget_label_text)[0]
        value_x_pos = panel_rect.right - 10  # Right padding for value

        # Render value text separately to get its width for right alignment
        value_surface = self.font_small.render(self.formatted_budget_str, True, self.colors['text_normal'])
        value_rect = value_surface.get_rect(midright=(value_x_pos, panel_rect.centery))

        # Ensure value doesn't overlap label (simple clip if it does)
        if value_rect.left < label_x_pos + label_width + 5:  # 5px spacing
            value_rect.left = label_x_pos + label_width + 5
            # If it's too long, it will just be clipped by the panel_rect if not handled explicitly

        screen.blit(value_surface, value_rect)

    def update(self, dt):
        # Update the active sub-screen
        if self.active_sub_screen_name in self.game.screens:
             self.game.screens[self.active_sub_screen_name].update(dt)


    def draw(self, screen: pygame.Surface):
        # Draw the active sub-screen's content in the main area
        # The sub-screen's draw method should handle drawing only in its designated area
        if self.active_sub_screen_name in self.game.screens:
             # The sub-screen (e.g., SquadScreen) is expected to draw within the main area rect
             self.game.screens[self.active_sub_screen_name].draw(screen)
        else:
             # Placeholder if sub-screen doesn't exist
              self.draw_text(screen, f"{self.active_sub_screen_name} View (Not Implemented)",
                            (self.game.screen.get_width() // 2, self.game.screen.get_height() // 2),
                            self.font_large, self.game.colors['text_normal'], center_x=True)

        for button in self.buttons:
            is_active_button = False
            try:
                active_label_key = self.active_sub_screen_name.upper()
                is_active_button = (button.text == self.game.labels.get_text(active_label_key))
            except Exception:
                is_active_button = False
            button.active = is_active_button
            button.draw(screen)

        # Draw the budget indicator
        self._draw_budget_indicator(screen)
        self._draw_status_indicator(screen)

        # --- Draw Leave Club Button (only if it exists) ---
        if self.leave_club_button:
            self.leave_club_button.draw(screen)

        # --- Draw Confirmation Dialog ---
        if self.show_leave_confirmation:
            # Optional: Dim background
            dim_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            dim_overlay.fill((0, 0, 0, 150))
            screen.blit(dim_overlay, (0, 0))
            # Draw dialog box
            pygame.draw.rect(screen, (40, 40, 50), self.confirmation_dialog_rect, border_radius=10)
            pygame.draw.rect(screen, self.colors['active_button'], self.confirmation_dialog_rect, 2,
                             border_radius=10)
            # Draw message (handle multi-line if needed)
            self.draw_text(screen, self.confirmation_message,
                           (self.confirmation_dialog_rect.centerx, self.confirmation_dialog_rect.top + 50),
                           self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)
            # Draw buttons
            if self.confirm_yes_button: self.confirm_yes_button.draw(screen)
            if self.confirm_no_button: self.confirm_no_button.draw(screen)

    def _update_and_format_budget_display(self):
        """Fetches the active club's budget and formats it for display."""
        self.active_club_budget = None  # Reset
        self.formatted_budget_str = self.game.labels.get_text("LOADING", "Loading...")  # Default text

        if self.game.active_club_id and self.game.user_clubs:
            active_club_info = next(
                (club_info for club_info in self.game.user_clubs if club_info.club_id == self.game.active_club_id),
                None
            )
            if active_club_info and hasattr(active_club_info, 'budget'):
                self.active_club_budget = active_club_info.budget
                budget_value = active_club_info.budget
                currency_symbol = self.game.labels.get_currency_symbol()

                # Format budget value (e.g., 1.2M, 500K, or 1,234,567)
                if budget_value >= 1_000_000_000:  # Billions
                    val_str = f"{budget_value / 1_000_000_000:.2f}B"
                elif budget_value >= 1_000_000:  # Millions
                    val_str = f"{budget_value / 1_000_000:.1f}M"
                elif budget_value >= 1_000:  # Thousands
                    val_str = f"{budget_value / 1_000:.0f}K"
                else:
                    val_str = f"{budget_value:,}"  # Full number with commas

                self.formatted_budget_str = f"{currency_symbol}{val_str}"
            else:
                self.formatted_budget_str = f"{self.game.labels.get_currency_symbol()} N/A"
                if not active_club_info:
                    print(f"GameMenuScreen: Active club ID {self.game.active_club_id} not found in user_clubs.")
                elif not hasattr(active_club_info, 'budget'):
                    print(
                        f"GameMenuScreen: Active club info for ID {self.game.active_club_id} is missing 'budget' attribute.")

        else:
            self.formatted_budget_str = f"{self.game.labels.get_currency_symbol()} ---"
            if not self.game.active_club_id:
                print("GameMenuScreen: No active club ID set to fetch budget.")
            if not self.game.user_clubs:
                print("GameMenuScreen: No user clubs loaded to fetch budget from.")

    def _fetch_and_format_tournament_status(self):
        """Fetches the active tournament's status and formats it."""
        self.tournament_status_str = self.game.labels.get_text("LOADING", "Loading...")
        if not self.game.active_tournament_id:
            self.tournament_status_str = "N/A"
            return

        response = self.game.request_tournament_details(self.game.active_tournament_id)  # NEW game method needed

        if response and response.get("status") == "success":
            tour_data = response.get("data", {})
            is_started = tour_data.get("is_started", False)
            start_time_iso = tour_data.get("start_time")
            is_finished = tour_data.get("is_finished", False)  # Server needs to provide this

            if is_finished:
                self.tournament_status_str = self.game.labels.get_text("STATUS_FINISHED")
            elif is_started:
                self.tournament_status_str = self.game.labels.get_text("STATUS_ONGOING")
            else:
                # Check if start_time has passed, but not yet marked started (should be rare with scheduler)
                try:
                    start_dt = datetime.fromisoformat(start_time_iso.replace('Z', '+00:00'))
                    if start_dt <= datetime.now(timezone.utc):
                        self.tournament_status_str = self.game.labels.get_text(
                            "STATUS_ONGOING")  # Or "Processing Start"
                    else:
                        self.tournament_status_str = self.game.labels.get_text("STATUS_STARTING")
                except:
                    self.tournament_status_str = self.game.labels.get_text("STATUS_STARTING")  # Fallback
        else:
            self.tournament_status_str = "Error"

    def _is_tournament_finished(self) -> bool:
        """Checks if the current tournament is finished (needs server call)."""
        if not self.game.active_tournament_id:
            return False
        # This relies on the status fetched in _fetch_and_format_tournament_status
        return self.tournament_status_str == self.game.labels.get_text("STATUS_FINISHED")

    def _draw_status_indicator(self, screen: pygame.Surface):
        """Draws the styled tournament status indicator below budget."""
        const = self.game.constants

        # Position below the budget indicator
        budget_panel_height = 40  # From _draw_budget_indicator
        budget_y = 0
        tactics_button = next((btn for btn in self.buttons if btn.text == self.game.labels.get_text("TACTICS")), None)
        if tactics_button:
            budget_y = tactics_button.rect.bottom + 20
        else:  # Fallback
            budget_y = const.BUTTON_MARGIN + 4 * (const.BUTTON_HEIGHT + const.BUTTON_MARGIN) + 20

        status_y = budget_y + budget_panel_height + 10  # 10px below budget panel

        status_x = const.BUTTON_MARGIN
        status_width = const.BUTTON_WIDTH
        status_height = 35  # Slightly smaller

        panel_rect = pygame.Rect(status_x, status_y, status_width, status_height)
        panel_bg_color = (40, 40, 40)
        panel_border_color = self.game.colors['border']

        pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=5)
        pygame.draw.rect(screen, panel_border_color, panel_rect, 2, border_radius=5)

        status_label_text = self.game.labels.get_text("LABEL_STATUS") + ":"
        label_x_pos = panel_rect.left + 10
        self.draw_text(screen, status_label_text,
                       (label_x_pos, panel_rect.centery),
                       self.font_small, self.colors['text_normal'],
                       center_y=True)

        value_x_pos = panel_rect.right - 10
        value_surface = self.font_small.render(self.tournament_status_str, True, self.colors['text_normal'])
        value_rect = value_surface.get_rect(midright=(value_x_pos, panel_rect.centery))
        screen.blit(value_surface, value_rect)
