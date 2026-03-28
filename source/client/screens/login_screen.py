import pygame
from client.screens.base_screen import BaseScreen
from client.ui_elements import InputBox, Checkbox
from client.button import Button
from typing import TYPE_CHECKING, Optional, Dict
import re

if TYPE_CHECKING:
    from client.game import Game

class LoginScreen(BaseScreen):

    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.mode = "login"  # Can be "login" or "register"
        self.message: Optional[str] = None  # For displaying feedback (errors/success)
        self.is_error_message: bool = False  # Determines the color of the message

        # --- UI Element Configuration ---
        inp_w, inp_h = 300, 40  # Input box width and height
        inp_x = (self.game.screen.get_width() - inp_w) // 2  # Center input boxes horizontally
        inp_y_start = 180  # Starting Y position for the first input box
        input_spacing = 15  # Vertical space between input boxes
        checkbox_size = 16
        checkbox_offset_y = (inp_h - checkbox_size) // 2

        # --- Input Boxes ---
        self.input_username = InputBox(
            inp_x, inp_y_start, inp_w, inp_h, self.font_medium,
            placeholder=self.game.labels.get_text("USERNAME")
        )
        pw_y = inp_y_start + inp_h + input_spacing
        self.input_password = InputBox(
            inp_x, pw_y, inp_w, inp_h, self.font_medium,
            placeholder=self.game.labels.get_text("PASSWORD"),
            is_password=True
        )
        # Confirm Password (Register Mode Only)
        confirm_pw_y = pw_y + inp_h + input_spacing
        self.input_password_confirm = InputBox(inp_x, confirm_pw_y, inp_w, inp_h, self.font_medium,
                                               placeholder=self.labels.get_text("CONFIRM_PASSWORD"), is_password=True)
        # Email (Register Mode Only)
        email_y = confirm_pw_y + inp_h + input_spacing
        self.input_email = InputBox(inp_x, email_y, inp_w, inp_h, self.font_medium,
                                    placeholder=self.labels.get_text("EMAIL"))

        # Keep track of inputs
        self.inputs = [self.input_username, self.input_password, self.input_password_confirm, self.input_email]
        # --- Checkboxes ---
        checkbox_x = inp_x + inp_w + 15  # Position checkbox to the right of inputs
        self.checkbox_show_password = Checkbox(
            checkbox_x, pw_y + checkbox_offset_y, checkbox_size,
            self.labels.get_text("SHOW_PASSWORD"), self.font_small
        )

        # --- Buttons ---
        btn_w, btn_h = 140, 50  # Button dimensions
        # Calculate Y position based on the last potentially visible input box
        btn_y = email_y + inp_h + 30
        btn_spacing = 20  # Horizontal space between Login/Register buttons

        # Login Button (Initially positioned for login mode)
        self.button_login = Button(
            text=self.game.labels.get_text("LOGIN"),
            x=inp_x + (inp_w - (2 * btn_w + btn_spacing)) // 2,  # Centered below inputs
            y=btn_y,  # Will be adjusted in _update_button_visibility
            width=btn_w, height=btn_h, font_size=self.game.constants.FONT_SIZE_BUTTON,
            active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
            border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
            on_click=self.attempt_login
        )
        # Register Button (Initially positioned relative to Login button)
        self.button_register = Button(
            text=self.game.labels.get_text("REGISTER"),
            x=self.button_login.rect.right + btn_spacing,
            y=btn_y,  # Will be adjusted
            width=btn_w, height=btn_h, font_size=self.game.constants.FONT_SIZE_BUTTON,
            active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
            border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
            on_click=self.attempt_register
        )
        # Button to toggle between Login and Register modes
        self.button_switch_mode = Button(
            text="",  # Text set dynamically based on mode
            x=inp_x,  # Align with input boxes
            y=self.button_login.rect.bottom + 10,  # Below the main action buttons
            width=inp_w, height=30, font_size=self.game.constants.FONT_SIZE_SMALL,
            active_color=self.game.colors['active_button'], inactive_color=(60, 60, 60),  # Darker inactive
            border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
            on_click=self.switch_mode
        )
        # Adjust initial positioning
        self.button_login.rect.y = btn_y
        self.button_register.rect.y = btn_y
        self.button_switch_mode.rect.y = btn_y + btn_h + 15  # Below action button

        # Keep track of all buttons
        self.buttons = [self.button_login, self.button_register, self.button_switch_mode]

        # Set initial visibility and positioning based on default mode ("login")
        self._update_button_visibility()

    def _update_button_visibility(self):
        """Adjusts positions and text of buttons based on login/register mode."""
        if not all(self.buttons): return

        btn_spacing = 20
        inp_w = self.input_username.rect.width
        inp_x = self.input_username.rect.x

        # --- Center the PAIR of Buttons Logic ---
        btn_w_login = self.button_login.rect.width
        btn_w_register = self.button_register.rect.width

        # Determine which button is the primary action button for positioning
        primary_btn = self.button_login if self.mode == "login" else self.button_register

        if self.mode == "login":
            # Center Login button, position Register relative (even if invisible)
            # Calculate start X so login button is centered under input
            login_btn_x = inp_x + (inp_w - btn_w_login) // 2
            self.button_login.rect.x = login_btn_x
            # Set register X for consistency if needed elsewhere, relative to login
            self.button_register.rect.x = self.button_login.rect.right + btn_spacing
        else:  # register mode
            # Center Register button, position Login relative
            register_btn_x = inp_x + (inp_w - btn_w_register) // 2
            self.button_register.rect.x = register_btn_x
            # Set login X relative to register
            self.button_login.rect.x = self.button_register.rect.x - btn_w_login - btn_spacing  # To the left

        # --- Set Y Positions ---
        last_input_bottom = 0
        if self.mode == "login":
            last_input_bottom = self.input_password.rect.bottom
            self.button_login.rect.y = last_input_bottom + 30
            self.button_register.rect.y = self.button_login.rect.y  # Align Y
            self.button_switch_mode.rect.y = self.button_login.rect.bottom + 15
            self.button_switch_mode.text = self.labels.get_text("NEED_ACCOUNT")
        else:  # register mode
            last_input_bottom = self.input_email.rect.bottom
            self.button_register.rect.y = last_input_bottom + 30
            self.button_login.rect.y = self.button_register.rect.y  # Align Y
            self.button_switch_mode.rect.y = self.button_register.rect.bottom + 15
            self.button_switch_mode.text = self.labels.get_text("HAVE_ACCOUNT")

        # Position the switch mode button centered under the input area as well
        if self.button_switch_mode:
            self.button_switch_mode.rect.centerx = inp_x + inp_w // 2

        # Update checkbox position
        if self.input_password and self.checkbox_show_password:
            self.checkbox_show_password.rect.centery = self.input_password.rect.centery
            self.checkbox_show_password.label_rect.centery = self.input_password.rect.centery



    def switch_mode(self):
        """Toggles between login and register modes."""
        self.mode = "register" if self.mode == "login" else "login"
        self.message = None
        # Clear fields when switching mode
        self.clear_fields()
        self._update_button_visibility()
        # Deactivate all inputs and activate the first one (username)
        for inp in self.inputs:
             if inp: inp.active = False
        if self.inputs[0]:
             self.inputs[0].active = True
             self.inputs[0].color_border = self.inputs[0].color_active
             self.inputs[0].txt_surface = self.inputs[0]._render_text_surface()


    def set_message(self, msg: str, is_error: bool = False):
        self.message = msg
        self.is_error_message = is_error

    def attempt_login(self):
         username = self.input_username.get_text()
         password = self.input_password.get_text()
         if not username or not password:
             self.set_message(self.game.labels.get_text("FIELD_REQUIRED"), is_error=True)
             return

         print(f"Attempting login for user: {username}")
         self.set_message(self.game.labels.get_text("LOADING"), is_error=False)
         response = self.game.network_client.send_request(
             "login_user",
             {"username": username, "password": password}
         )

         if response and response.get("status") == "success":
             user_data = response.get("data")
             print(f"Login successful: {user_data}")
             self.game.set_user_info(user_data['user_id'], user_data['username'])
             self.game.change_screen("MainMenu") # Go to main menu on success
         else:
             error_msg = response.get('message') if response else "No response"
             print(f"Login failed: {error_msg}")
             self.set_message(self.game.labels.get_text("LOGIN_FAILED", f"Login Failed: {error_msg}"), is_error=True)


    def attempt_register(self):
         username = self.input_username.get_text()
         password = self.input_password.get_text()
         password_confirm = self.input_password_confirm.get_text()
         email = self.input_email.get_text()

         if not all([username, password, password_confirm, email]):
             self.set_message(self.game.labels.get_text("FIELD_REQUIRED"), is_error=True)
             return

         # --- Check Password Match ---
         if password != password_confirm:
             self.set_message(self.game.labels.get_text("PASSWORDS_DONT_MATCH"), is_error=True)
             return

         # --- Basic Email Format Check (Regex) ---
         email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
         if not re.match(email_regex, email):
             self.set_message(self.labels.get_text("INVALID_EMAIL_FORMAT"), is_error=True)
             return
         # --- End Email Check ---

         print(f"Attempting registration for user: {username}, email: {email}")
         self.set_message(self.game.labels.get_text("LOADING"), is_error=False)
         response = self.game.network_client.send_request(
             "register_user",
             {"username": username, "password": password, "email": email}
         )

         if response and response.get("status") == "success":
             print("Registration successful")
             self.set_message(self.game.labels.get_text("REGISTRATION_SUCCESS"), is_error=False)
             # Switch back to login mode after successful registration
             self.switch_mode()
             # Clear fields
         else:
             error_msg = response.get('message') if response else "No response"
             print(f"Registration failed: {error_msg}")
             fail_msg = self.labels.get_text("REGISTRATION_FAILED").format(error=error_msg)
             self.set_message(fail_msg, is_error=True)

    def handle_event(self, event: pygame.event.Event):
        # --- Handle Checkbox First ---
        checkbox_handled = self.checkbox_show_password.handle_event(event)
        if checkbox_handled:
            # Toggle password visibility for both fields
            show = self.checkbox_show_password.get_value()
            self.input_password.is_password = not show
            self.input_password_confirm.is_password = not show
            # Force re-render of password fields
            self.input_password.txt_surface = self.input_password._render_text_surface()
            self.input_password_confirm.txt_surface = self.input_password_confirm._render_text_surface()
            return  # Checkbox handled the click

        # --- Hover Checks ---
        mouse_pos = pygame.mouse.get_pos()
        visible_elements = [self.input_username, self.input_password]
        if self.mode == "register":
            visible_elements.extend([self.input_password_confirm, self.input_email])
        visible_elements.append(self.checkbox_show_password)
        if self.mode == "login":
            visible_elements.append(self.button_login)
        else:
            visible_elements.append(self.button_register)
        visible_elements.append(self.button_switch_mode)

        for element in visible_elements:
            if hasattr(element, 'check_hover'): element.check_hover(mouse_pos)
        # --- End Hover ---

        # Handle input fields (only visible ones)
        input_handled = False
        for box in self.inputs:
            is_visible = (box == self.input_username or
                          box == self.input_password or
                          (self.mode == "register" and (
                                      box == self.input_password_confirm or box == self.input_email)))
            if is_visible:
                box.handle_event(event)
                if box.active and event.type == pygame.KEYDOWN: input_handled = True

        # Handle button clicks if not handled by inputs/checkbox
        if not input_handled and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode == "login":
                if self.button_login and self.button_login.check_click(event.pos): pass
            else:  # register mode
                if self.button_register and self.button_register.check_click(event.pos): pass
            # Switch mode button always checkable
            if self.button_switch_mode and self.button_switch_mode.check_click(event.pos): pass

            # Handle keyboard (Return, Tab) if not handled by InputBox
            if not input_handled and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if self.mode == "login":
                        self.attempt_login()
                    else:
                        self.attempt_register()
                elif event.key == pygame.K_TAB:
                    # Determine which input fields are currently relevant based on mode
                    visible_inputs = [self.input_username, self.input_password]
                    if self.mode == "register":
                        visible_inputs.extend([self.input_password_confirm, self.input_email])

                    # Find the currently active input *within the visible list*
                    active_indices_in_visible = [i for i, box in enumerate(visible_inputs) if box.active]

                    current_visible_index = -1
                    if active_indices_in_visible:
                        current_visible_index = active_indices_in_visible[0]
                        # Deactivate the current input
                        visible_inputs[current_visible_index].active = False

                    # Calculate the index of the next input within the visible list
                    next_visible_index = (current_visible_index + 1) % len(visible_inputs)

                    # Activate the next input
                    next_input_box = visible_inputs[next_visible_index]
                    next_input_box.active = True
                    # Select all text in the newly activated box for easy replacement
                    next_input_box.selection_start = 0
                    next_input_box.cursor_pos = len(next_input_box.text)
                    next_input_box._ensure_cursor_visible()  # Make sure cursor/selection is visible

                    # Update colors and rendering for all potentially visible inputs
                    all_potentially_visible = [self.input_username, self.input_password,
                                               self.input_password_confirm, self.input_email]
                    for box in all_potentially_visible:
                        if box:  # Check if box was initialized
                            box.color_border = box.color_active if box.active else box.color_inactive
                            # Re-render needed in case placeholder should show/hide
                            box.txt_surface = box._render_text_surface()

                    input_handled = True  # Tab key handled

    def update(self, dt):
         # Update input boxes (for cursor blink)
        for box in self.inputs:
             box.update(dt)

    def draw(self, screen: pygame.Surface):
        """Draws the login screen UI."""
        # --- Draw Title ---
        title_text = self.game.labels.get_text("LOGIN" if self.mode == "login" else "REGISTER")
        self.draw_text(screen, title_text, (self.game.screen.get_width() // 2, 100),
                       self.font_large, self.colors['text_normal'], center_x=True)

        # --- Draw Inputs (based on mode) ---
        self.input_username.draw(screen)
        self.input_password.draw(screen)
        if self.mode == "register":
            self.input_password_confirm.draw(screen)
            self.input_email.draw(screen)

        # --- Draw Checkbox ---
        self.checkbox_show_password.draw(screen)

        # --- Explicitly Draw Buttons based on Mode ---
        # Ensure buttons are not None before drawing
        if self.mode == "login":
            if self.button_login:
                self.button_login.draw(screen)
        else:  # register mode
            if self.button_register:
                self.button_register.draw(screen)

        # Always draw switch mode button if exists
        if self.button_switch_mode:
            # print(f"Drawing Switch Button ({self.button_switch_mode.text}) at {self.button_switch_mode.rect}") # Debug print
            self.button_switch_mode.draw(screen)

        # --- Draw Message ---
        if self.message:
            msg_color = self.colors['error_text'] if self.is_error_message else self.colors['success_text']
            # Position message below the lowest element (switch button or inputs)
            lowest_y = 0
            if self.button_switch_mode:
                lowest_y = self.button_switch_mode.rect.bottom
            elif self.mode == "register" and self.input_email:
                lowest_y = self.input_email.rect.bottom
            elif self.input_password:
                lowest_y = self.input_password.rect.bottom

            msg_y = lowest_y + 25  # Add some padding below the lowest element
            self.draw_text(screen, self.message, (self.game.screen.get_width() // 2, msg_y),
                           self.font_medium, msg_color, center_x=True)

    def on_enter(self, data: Optional[Dict] = None):
        """Called when the Login screen becomes active."""
        super().on_enter(data)
        self.message = None
        self.is_error_message = False

        # --- Reset Labels/Placeholders based on current language ---
        if self.input_username: self.input_username.update_placeholder(self.labels.get_text("USERNAME"))
        if self.input_password: self.input_password.update_placeholder(self.labels.get_text("PASSWORD"))
        if self.input_password_confirm: self.input_password_confirm.update_placeholder(self.labels.get_text("CONFIRM_PASSWORD"))
        if self.input_email: self.input_email.update_placeholder(self.labels.get_text("EMAIL"))
        if self.checkbox_show_password: self.checkbox_show_password.update_label(self.labels.get_text("SHOW_PASSWORD"))
        if self.button_login: self.button_login.text = self.labels.get_text("LOGIN")
        if self.button_register: self.button_register.text = self.labels.get_text("REGISTER")
        # Switch mode button text is handled by _update_button_visibility

        # Clear input fields when entering screen (ensures clean state)
        self.clear_fields()

        # Reset mode to login when entering
        self.mode = "login"
        self._update_button_visibility() # This also updates switch mode button text

    def clear_fields(self):
        """Helper method to clear all input fields."""
        if hasattr(self, 'input_username') and self.input_username: self.input_username.update_text("")
        if hasattr(self, 'input_password') and self.input_password: self.input_password.update_text("")
        if hasattr(self,
                   'input_password_confirm') and self.input_password_confirm: self.input_password_confirm.update_text(
            "")
        if hasattr(self, 'input_email') and self.input_email: self.input_email.update_text("")

