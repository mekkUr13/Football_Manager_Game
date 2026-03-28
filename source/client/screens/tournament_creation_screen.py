import pygame
from client.screens.base_screen import BaseScreen
from client.ui_elements import InputBox
from client.button import Button
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from client.game import Game

class TournamentCreationScreen(BaseScreen):
    """Screen for creating a new league/tournament."""
    def __init__(self, game: 'Game'):
        """Initializes the TournamentCreationScreen."""
        super().__init__(game)
        self.message: Optional[str] = None
        self.is_error_message: bool = False

        inp_w, inp_h = 400, 40
        inp_x = (self.game.screen.get_width() - inp_w) // 2
        inp_y_start = 150
        spacing = inp_h + 15

        # --- Create Input Boxes (Use placeholders initially) ---
        # Placeholders will be updated in on_enter
        self.input_name = InputBox(inp_x, inp_y_start, inp_w, inp_h, self.font_medium, placeholder="...")
        self.input_num_clubs = InputBox(inp_x, inp_y_start + spacing, inp_w, inp_h, self.font_medium, placeholder="...")
        self.input_start_delay = InputBox(inp_x, inp_y_start + 2 * spacing, inp_w, inp_h, self.font_medium,
                                          placeholder="...")
        self.input_round_interval = InputBox(inp_x, inp_y_start + 3 * spacing, inp_w, inp_h, self.font_medium,
                                             placeholder="...")
        self.inputs = [self.input_name, self.input_num_clubs, self.input_start_delay, self.input_round_interval]

        # Buttons
        btn_w = 150
        btn_y = self.input_round_interval.rect.bottom + 40
        btn_spacing = 30
        btn_x_start = (self.game.screen.get_width() - (2 * btn_w + btn_spacing)) // 2
        # Base position, might be adjusted after creation
        cancel_x_base = (self.game.screen.get_width() - (2 * btn_w + btn_spacing)) // 2
        create_x_base = cancel_x_base + btn_w + btn_spacing

        self.button_cancel = Button(
            text="...", x=cancel_x_base, y=btn_y,
            width=btn_w, height=50, font_size=self.constants.FONT_SIZE_BUTTON,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self.cancel_creation, min_width=btn_w
        )
        self.button_create = Button(
            text="...", x=create_x_base, y=btn_y,
            width=btn_w, height=50, font_size=self.constants.FONT_SIZE_BUTTON,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self.confirm_creation, min_width=btn_w
        )
        self.buttons = [self.button_cancel, self.button_create]

        # --- Adjust Button Positions After Creation ---
        if self.button_cancel and self.button_create:
            total_pair_width = self.button_cancel.rect.width + btn_spacing + self.button_create.rect.width
            pair_start_x = (self.game.screen.get_width() - total_pair_width) // 2
            self.button_cancel.rect.x = pair_start_x
            self.button_create.rect.x = self.button_cancel.rect.right + btn_spacing

    def on_enter(self, data: Optional[Dict] = None):
        """Called when screen becomes active. Sets labels and clears fields."""
        super().on_enter(data)
        # Clear fields and message
        for inp in self.inputs:
            if inp: inp.update_text("")
            inp.scroll_offset_x = 0
        self.message = None

        # --- Update Placeholders and Button Text ---
        if self.input_name: self.input_name.update_placeholder(self.labels.get_text("TOURNAMENT_NAME"))
        if self.input_num_clubs: self.input_num_clubs.update_placeholder(self.labels.get_text("NUMBER_OF_CLUBS"))
        if self.input_start_delay: self.input_start_delay.update_placeholder(
            self.labels.get_text("START_DELAY_HOURS_FLOAT", "Start Delay (Hours, e.g., 1 or 0.1 for 6m)"))
        if self.input_round_interval: self.input_round_interval.update_placeholder(
            self.labels.get_text("ROUND_INTERVAL_HOURS_FLOAT", "Time Between Rounds (Hours, e.g., 24 or 0.5)"))
        if self.button_cancel: self.button_cancel.text = self.labels.get_text("CANCEL")
        if self.button_create: self.button_create.text = self.labels.get_text("CREATE")

    def set_message(self, msg: str, is_error: bool = False):
        self.message = msg
        self.is_error_message = is_error

    def validate_input(self) -> Optional[Dict[str, Any]]:
        """Validate input fields and return payload dict or None."""
        name = self.input_name.get_text().strip()
        num_clubs_str = self.input_num_clubs.get_text().strip()
        start_delay_str = self.input_start_delay.get_text().strip()
        round_interval_str = self.input_round_interval.get_text().strip()

        if not name:
            self.set_message("Tournament Name is required.", is_error=True)
            return None

        try:
            num_clubs = int(num_clubs_str)
            # Basic validation - must be even and >= 4
            if num_clubs < 4 or num_clubs % 2 != 0:
                 raise ValueError("Number of clubs must be an even number >= 4.")
        except ValueError:
            self.set_message("Invalid number of clubs (must be an even number >= 4).", is_error=True)
            return None

        try:
            start_delay_hours = float(start_delay_str)
            if start_delay_hours <= 0:
                raise ValueError(self.labels.get_text("INVALID_START_DELAY_POSITIVE","Start delay must be a positive number of hours."))
            start_delay_sec = int(start_delay_hours * 3600) # Convert to seconds
        except ValueError:
            self.set_message("Invalid start delay (must be a positive number of hours).", is_error=True)
            return None

        try:
            round_interval_hours = float(round_interval_str)
            if round_interval_hours <= 0:
                raise ValueError(self.labels.get_text("INVALID_ROUND_INTERVAL_POSITIVE","Round interval must be a positive number of hours."))
            round_interval_sec = int(round_interval_hours * 3600)  # Convert to integer seconds
        except ValueError as e:
            if "could not convert string to float" in str(e).lower():
                self.set_message(self.labels.get_text("INVALID_ROUND_INTERVAL_FORMAT","Invalid round interval format. Use numbers (e.g., 24 or 0.1)."),
                                 is_error=True)
            else:
                self.set_message(str(e), is_error=True)
            return None

        return {
            "name": name,
            "num_clubs": num_clubs,
            "start_delay_sec": start_delay_sec,
            "round_interval_sec": round_interval_sec,
            "creator_user_id": self.game.user_id # Add creator ID
        }

    def confirm_creation(self):
        self.message = None # Clear previous message
        payload = self.validate_input()

        if not payload:
            return # Validation failed, message already set

        if not self.game.user_id:
             self.set_message("Error: Not logged in.", is_error=True)
             return

        self.set_message(self.game.labels.get_text("LOADING"), is_error=False)
        response = self.game.network_client.send_request("create_tournament", payload)

        if response and response.get("status") == "success":
             tournament_data = response.get("data", {})
             tour_name = tournament_data.get("name", payload['name']) # Use returned name if available
             success_msg = self.game.labels.get_text("CREATE_TOURNAMENT_SUCCESS").format(name=tour_name)
             print(success_msg)
             # Go back to league select, which should now show the new league after refresh
             self.game.change_screen("LeagueSelect")
        else:
             error_msg = response.get('message') if response else "No response"
             fail_msg = self.game.labels.get_text("CREATE_TOURNAMENT_FAILED").format(error=error_msg)
             print(f"Tournament creation failed: {error_msg}")
             self.set_message(fail_msg, is_error=True)


    def cancel_creation(self):
         self.game.change_screen("LeagueSelect")


    def handle_event(self, event: pygame.event.Event):
        # --- Hover check ---
        mouse_pos = pygame.mouse.get_pos()
        # Check hover for input boxes too if they have a visual hover state
        for box in self.inputs:
            if hasattr(box, 'check_hover'): box.check_hover(mouse_pos)
        # Check hover for buttons
        for btn in self.buttons:
            if btn: btn.check_hover(mouse_pos)
        # --- End hover check ---
        input_handled = False
        for box in self.inputs:
            box.handle_event(event)
            if box.active and event.type == pygame.KEYDOWN: input_handled = True

        if not input_handled and event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for btn in self.buttons:
                    if btn: btn.check_click(event.pos)

        if event.type == pygame.KEYDOWN:
             if event.key == pygame.K_ESCAPE:
                 self.cancel_creation()
             elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                  self.confirm_creation()
             elif event.key == pygame.K_TAB:
                  # Basic Tab cycling between input fields
                  active_indices = [i for i, box in enumerate(self.inputs) if box.active]
                  next_index = 0
                  if active_indices:
                      current_active_index = active_indices[0]
                      self.inputs[current_active_index].active = False
                      next_index = (current_active_index + 1) % len(self.inputs)
                  self.inputs[next_index].active = True
                  # Update colors and rendering for all inputs
                  for i, inp in enumerate(self.inputs):
                       inp.color = inp.color_active if i == next_index else inp.color_inactive
                       inp.txt_surface = inp._render_text_surface()


    def update(self, dt: float):
        for box in self.inputs:
            box.update(dt)


    def draw(self, screen: pygame.Surface):
         # Title
        title = self.game.labels.get_text("TOURNAMENT_CREATION")
        self.draw_text(screen, title, (self.game.screen.get_width() // 2, 50),
                       self.font_large, self.game.colors['text_normal'], center_x=True)

        # Draw Input Boxes
        for box in self.inputs:
            box.draw(screen)

        # Draw Buttons
        for btn in self.buttons:
             btn.draw(screen)

         # Draw Message
        if self.message:
            msg_color = self.game.colors['error_text'] if self.is_error_message else self.game.colors['success_text']
            msg_y = self.button_create.rect.bottom + 20
            self.draw_text(screen, self.message, (self.game.screen.get_width() // 2, msg_y),
                           self.font_medium, msg_color, center_x=True)