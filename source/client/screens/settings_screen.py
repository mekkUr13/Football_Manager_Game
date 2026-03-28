import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from client.ui_elements import Checkbox
from typing import TYPE_CHECKING, Optional, List, Dict

if TYPE_CHECKING:
    from client.game import Game

class SettingsScreen(BaseScreen):
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.selected_language: str = self.game.labels.language
        self.selected_currency: str = self.game.labels.currency

        self.language_buttons: List[Button] = []
        self.currency_buttons: List[Button] = []
        self.back_button: Optional[Button] = None # To go back
        self.fullscreen_checkbox: Optional[Checkbox] = None

        # Store previous screen to return to
        self.previous_screen: Optional[str] = "MainMenu" # Default, updated in on_enter

        self.create_buttons()

    def on_enter(self, data: Optional[Dict] = None):
        """Called when the screen becomes active."""
        super().on_enter(data)
        # Get previous screen name if passed
        self.previous_screen = data.get("previous_screen", "MainMenu") if data else "MainMenu"
        # Reset selections to current game settings
        self.selected_language = self.game.labels.language
        self.selected_currency = self.game.labels.currency
        # Recreate buttons to ensure labels are in the correct current language
        self.create_buttons()
        # Update button active states
        self._update_button_states()
        if self.fullscreen_checkbox:
            self.fullscreen_checkbox.checked = self.game.labels.get_setting("fullscreen", False)


    def create_buttons(self):
        """Creates or recreates all buttons with current labels."""
        self.language_buttons = []
        self.currency_buttons = []

        y_start = 150 # Starting Y for the settings sections
        x_start_lang = 150 # X position for language options
        x_start_curr = self.game.screen.get_width() // 2 + 100 # X for currency
        btn_w, btn_h = 180, 40 # Button dimensions
        spacing = 15 # Vertical spacing between buttons

        # --- Language Buttons ---
        available_langs = self.game.labels.get_languages() # Gets codes like 'ENGLISH', 'MAGYAR'
        for i, lang_code in enumerate(available_langs):
             # Get the display name for the language (e.g., "English", "Magyar")
             display_name = self.game.labels.get_language_display_name(lang_code)
             btn = Button(
                 text=display_name, # Use the display name for the button text
                 x=x_start_lang, y=y_start + 50 + i * (btn_h + spacing), # Position below label
                 width=btn_w, height=btn_h, font_size=self.game.constants.FONT_SIZE_MEDIUM,
                 active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
                 border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
                 # Lambda stores the language *code* to be set
                 on_click=lambda lc=lang_code: self.select_language(lc)
             )
             # Store the language code with the button for state updates
             btn.lang_code = lang_code
             self.language_buttons.append(btn)

        # --- Currency Buttons ---
        available_currencies = self.game.labels.get_currencies() # Gets codes 'EUR', 'USD', etc.
        for i, curr_code in enumerate(available_currencies):
             # Display currency code and symbol (e.g., "EUR (€)")
             symbol = self.game.labels.currency_symbols.get(curr_code, '')
             display_text = f"{curr_code} ({symbol})" if symbol else curr_code
             btn = Button(
                 text=display_text,
                 x=x_start_curr, y=y_start + 50 + i * (btn_h + spacing), # Position below label
                 width=btn_w, height=btn_h, font_size=self.game.constants.FONT_SIZE_MEDIUM,
                 active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
                 border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
                 on_click=lambda cc=curr_code: self.select_currency(cc)
             )
             # Store the currency code with the button
             btn.curr_code = curr_code
             self.currency_buttons.append(btn)

        # --- Create Fullscreen Checkbox ---
        checkbox_y = y_start + 50 + max(len(available_langs), len(available_currencies)) * (btn_h + spacing) + 20
        checkbox_x = self.game.screen.get_width() // 2 - 100  # Adjust X as needed
        self.fullscreen_checkbox = Checkbox(
            checkbox_x, checkbox_y, 20,  # Checkbox size
            self.labels.get_text("FULLSCREEN", "Fullscreen"),  # Localized label
            self.font_medium,  # Font for label
            initial_checked=self.game.labels.get_setting("fullscreen", False)  # Initial state
        )

        # --- Back Button ---
        back_btn_y = self.game.screen.get_height() - 80
        back_btn_w = 200
        back_btn_x = (self.game.screen.get_width() - back_btn_w) // 2 # Center the back button

        self.back_button = Button(
             text=self.game.labels.get_text("BACK"), # Use localized text
             x=back_btn_x, y=back_btn_y, width=back_btn_w, height=50,
             font_size=self.game.constants.FONT_SIZE_BUTTON,
             active_color=self.game.colors['active_button'], inactive_color=self.game.colors['inactive_button'],
             border_color=self.game.colors['border'], text_color=self.game.colors['text_button'],
             on_click=self.go_back
        )

        # Ensure initial active states are correct
        self._update_button_states()

    def _update_button_states(self):
        """Sets the visual active state of buttons based on current selections."""
        # Ensure buttons have been created before trying to update them
        if not hasattr(self, 'language_buttons') or not hasattr(self, 'currency_buttons'):
            return

        for btn in self.language_buttons:
            # Check if the button instance has the lang_code attribute before comparing
            is_active = hasattr(btn, 'lang_code') and btn.lang_code == self.selected_language
            btn.active = is_active  # Set the active state used by draw

        for btn in self.currency_buttons:
            # Check if the button instance has the curr_code attribute before comparing
            is_active = hasattr(btn, 'curr_code') and btn.curr_code == self.selected_currency
            btn.active = is_active  # Set the active state used by draw

    def select_language(self, lang_code: str):
        """Called when a language button is clicked."""
        if self.selected_language != lang_code:
            self.selected_language = lang_code
            self.game.labels.set_language(lang_code)  # Apply language change to the game
            # Recreate buttons immediately to update all labels on the screen
            self.create_buttons()
            self._update_button_states()  # Ensure the newly created buttons reflect the selection

    def select_currency(self, curr_code: str):
        """Called when a currency button is clicked."""
        if self.selected_currency != curr_code:
            self.selected_currency = curr_code
            self.game.labels.set_currency(curr_code)  # Apply currency change to the game
            self._update_button_states()

    def go_back(self):
        """Requests navigation back to the previous screen."""
        print(f"SettingsScreen: Requesting navigation back to {self.previous_screen or 'MainMenu'}")
        # Instead of changing screen directly, tell the game loop to do it
        self.game.request_screen_change(self.previous_screen or "MainMenu")
    def toggle_fullscreen(self):
        """Handles toggling the fullscreen setting."""
        if self.fullscreen_checkbox:
            current_state = self.fullscreen_checkbox.get_value()
            # Update the setting in the Labels object (which also saves it)
            self.game.labels.set_setting("fullscreen", current_state)
            # Tell the Game object to apply the display change (set_mode)
            success = self.game.apply_display_settings()  # Make apply_display_settings return success/fail

            if success:
                print("SettingsScreen: Display mode changed, recreating UI elements...")
                # Recreate buttons with potentially new positions/labels
                self.create_buttons()
                # Ensure checkbox reflects the actual state AFTER potential apply failure
                self.fullscreen_checkbox.checked = self.game.labels.get_setting("fullscreen", False)
                self._update_button_states()
            else:
                # If applying failed, revert the checkbox state
                print("SettingsScreen: Failed to apply display settings, reverting checkbox.")
                self.fullscreen_checkbox.checked = not current_state  # Toggle back

    def handle_event(self, event: pygame.event.Event):
        """Handles input events for the settings screen."""
        # --- Add hover checks ---
        mouse_pos = pygame.mouse.get_pos()
        if self.fullscreen_checkbox: self.fullscreen_checkbox.check_hover(mouse_pos)
        all_buttons = self.language_buttons + self.currency_buttons + ([self.back_button] if self.back_button else [])
        for btn in all_buttons:
            if btn: btn.check_hover(mouse_pos)
        # --- End hover checks ---

        # Handle Checkbox Click
        checkbox_handled = False
        if self.fullscreen_checkbox and self.fullscreen_checkbox.handle_event(event):
            self.toggle_fullscreen()  # Call toggle logic when checkbox changes
            checkbox_handled = True

        # Handle Button Clicks (if not handled by checkbox)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = False
            for btn in self.language_buttons:
                if btn.check_click(event.pos): clicked = True; break
            if not clicked:
                for btn in self.currency_buttons:
                    if btn.check_click(event.pos): clicked = True; break
            if not clicked and self.back_button:
                self.back_button.check_click(event.pos)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_back()

    def draw(self, screen: pygame.Surface):
        """Draws the settings screen UI."""
        # --- Title ---
        title_text = self.game.labels.get_text("SETTINGS")
        self.draw_text(screen, title_text, (self.game.screen.get_width() // 2, 50),
                       self.font_large, self.game.colors['text_normal'], center_x=True)

        # --- Language Section Title ---
        lang_title_text = self.game.labels.get_text("LANGUAGE")
        # Position title above the buttons
        lang_title_x = self.language_buttons[0].rect.centerx if self.language_buttons else 150
        self.draw_text(screen, lang_title_text, (lang_title_x, 150),
                       self.font_medium, self.game.colors['text_normal'], center_x=True)

        # --- Currency Section Title ---
        curr_title_text = self.game.labels.get_text("CURRENCY")
        curr_title_x = self.currency_buttons[0].rect.centerx if self.currency_buttons else self.game.screen.get_width() // 2 + 100
        self.draw_text(screen, curr_title_text, (curr_title_x, 150),
                       self.font_medium, self.game.colors['text_normal'], center_x=True)


        # --- Draw Buttons ---
        # Buttons draw themselves, including hover/active states
        for btn in self.language_buttons:
             btn.draw(screen)
        for btn in self.currency_buttons:
             btn.draw(screen)
        if self.fullscreen_checkbox:
            self.fullscreen_checkbox.draw(screen)
        if self.back_button:
             self.back_button.draw(screen)