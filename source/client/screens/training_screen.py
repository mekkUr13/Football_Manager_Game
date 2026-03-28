import pygame
from client.screens.base_screen import BaseScreen
from client.button import Button
from client.data_models import ClientTrainingSettings
from common.enums import TrainingFocusEnum
from typing import TYPE_CHECKING, List, Optional, Dict

if TYPE_CHECKING:
    from client.game import Game

class TrainingScreen(BaseScreen):
    """
    Screen for viewing and adjusting club training settings (intensity and focus area).
    """
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.padding: int = 20  # Consistent padding
        self.title_height: int = 60  # Space for the screen title
        self.settings: Optional[ClientTrainingSettings] = None
        self.loading_state = "idle"  # idle, loading, loaded, error
        self.error_message: Optional[str] = None
        self.success_message: Optional[str] = None
        self.message_timer: float = 0.0 # Timer to fade messages

        # UI Elements
        self.focus_buttons: List[Button] = []
        self.intensity_minus_button: Optional[Button] = None
        self.intensity_plus_button: Optional[Button] = None

        # Store current values locally for UI interaction
        self.current_intensity: int = 3 # Default/initial
        self.current_focus: str = TrainingFocusEnum.BALANCED.value # Default/initial

        # Layout constants within the screen
        self.section_padding = 60
        self.button_spacing = 15

    def on_enter(self, data: Optional[Dict] = None):
        """Fetches current training settings when entering the screen."""
        super().on_enter(data)
        self.loading_state = "loading"
        self.error_message = None
        self.success_message = None
        self.settings = None
        print("TrainingScreen: Entering screen, requesting training settings...")

        fetched_settings = self.game.request_training_settings()

        if fetched_settings:
            self.settings = fetched_settings
            self.current_intensity = self.settings.intensity
            self.current_focus = self.settings.focus_area
            self.loading_state = "loaded"
            print(f"TrainingScreen: Loaded settings: Intensity={self.current_intensity}, Focus={self.current_focus}")
        else:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("TRAINING_LOAD_FAILED")
            print(f"TrainingScreen: Error loading settings: {self.error_message}")
            # Keep defaults for current_intensity/focus if load fails

        # Create UI elements after attempting to load data
        self._create_ui()

    def _create_ui(self):
        """Creates the buttons for focus areas and intensity adjustment."""
        self.focus_buttons = [] # Clear existing buttons

        # Dynamically calculate main content area rect
        main_rect = self._get_main_content_rect()

        # --- Intensity Controls ---
        intensity_label_y = main_rect.top + self.padding + 60
        intensity_controls_y = intensity_label_y + 40
        intensity_controls_center_x = main_rect.centerx

        btn_size = 40 # Square buttons for +/-
        num_display_width = 80 # Space to display the number

        self.intensity_minus_button = Button(
            x=intensity_controls_center_x - num_display_width // 2 - btn_size - self.button_spacing,
            y=intensity_controls_y - btn_size // 2,
            width=btn_size, height=btn_size,
            text="-", font_size=30,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=lambda: self._change_intensity(-1)
        )
        self.intensity_plus_button = Button(
            x=intensity_controls_center_x + num_display_width // 2 + self.button_spacing,
            y=intensity_controls_y - btn_size // 2,
            width=btn_size, height=btn_size,
            text="+", font_size=30,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=lambda: self._change_intensity(1)
        )

        # --- Focus Area Buttons ---
        focus_label_y = intensity_controls_y + btn_size + self.section_padding
        focus_buttons_start_y = focus_label_y + 40
        focus_btn_width = 180
        focus_btn_height = 45

        # Arrange focus buttons in columns (e.g., 2 columns)
        num_cols = 2
        button_x_positions = []
        col_width_total = (num_cols * focus_btn_width) + ((num_cols - 1) * self.button_spacing)
        start_x = main_rect.centerx - col_width_total // 2
        for i in range(num_cols):
            button_x_positions.append(start_x + i * (focus_btn_width + self.button_spacing))

        # Get all enum members
        focus_options = list(TrainingFocusEnum)

        for i, focus_enum in enumerate(focus_options):
            col_index = i % num_cols
            row_index = i // num_cols
            btn_x = button_x_positions[col_index]
            btn_y = focus_buttons_start_y + row_index * (focus_btn_height + self.button_spacing)

            # Get localized display name (e.g., FOCUS_ATTACK -> "Attack")
            focus_key = f"FOCUS_{focus_enum.name}" # Assumes key format like FOCUS_ENUMNAME
            display_text = self.labels.get_text(focus_key, focus_enum.name.replace("_", " ").title())

            btn = Button(
                x=btn_x, y=btn_y, width=focus_btn_width, height=focus_btn_height,
                text=display_text, font_size=self.constants.FONT_SIZE_MEDIUM,
                active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
                border_color=self.colors['border'], text_color=self.colors['text_button'],
                on_click=lambda focus=focus_enum.value: self._select_focus(focus) # Pass enum string value
            )
            # Store the enum value with the button for state checking
            btn.focus_value = focus_enum.value
            self.focus_buttons.append(btn)

        # Update button active states based on current selection
        self._update_button_states()

    def _update_button_states(self):
        """Sets the visual active state of focus buttons."""
        for btn in self.focus_buttons:
            is_active = hasattr(btn, 'focus_value') and btn.focus_value == self.current_focus
            btn.active = is_active # Button's draw method uses this

    def _select_focus(self, focus_value: str):
        """Handles clicking a focus area button."""
        if self.current_focus == focus_value:
            return # No change

        print(f"Selected new focus: {focus_value}")
        self.current_focus = focus_value
        self.loading_state = "loading" # Indicate update in progress
        self.error_message = None
        self.success_message = None

        success = self.game.request_update_training(focus_area=self.current_focus)

        self.loading_state = "loaded" # Reset state after attempt
        if success:
            self.settings.focus_area = self.current_focus # Update local cache
            self.success_message = self.labels.get_text("TRAINING_UPDATE_SUCCESS")
            self.message_timer = 3.0 # Show message for 3 seconds
        else:
            self.error_message = self.labels.get_text("TRAINING_UPDATE_FAILED")
            self.message_timer = 5.0 # Show error longer
            # Revert local state if update failed? Best practice is to refetch,
            # but for now, we'll just show error. Let's revert the selection visually.
            if self.settings:
                 self.current_focus = self.settings.focus_area
            else: # If initial load failed, revert to default
                 self.current_focus = TrainingFocusEnum.BALANCED.value

        self._update_button_states() # Update button highlighting

    def _change_intensity(self, delta: int):
        """Handles clicking the intensity +/- buttons."""
        new_intensity = self.current_intensity + delta
        # Clamp value between 1 and 10
        new_intensity = max(1, min(10, new_intensity))

        if self.current_intensity == new_intensity:
            return # No change

        print(f"Changed intensity to: {new_intensity}")
        self.current_intensity = new_intensity
        self.loading_state = "loading" # Indicate update in progress
        self.error_message = None
        self.success_message = None

        success = self.game.request_update_training(intensity=self.current_intensity)

        self.loading_state = "loaded" # Reset state after attempt
        if success:
            self.settings.intensity = self.current_intensity # Update local cache
            self.success_message = self.labels.get_text("TRAINING_UPDATE_SUCCESS")
            self.message_timer = 3.0 # Show message for 3 seconds
        else:
            self.error_message = self.labels.get_text("TRAINING_UPDATE_FAILED")
            self.message_timer = 5.0 # Show error longer
             # Revert local state if update failed
            if self.settings:
                 self.current_intensity = self.settings.intensity
            else: # If initial load failed, revert to default
                 self.current_intensity = 3

        # No need to update button states here, just the displayed value

    def handle_event(self, event: pygame.event.Event):
        """Handles input events for the training screen."""
        # --- Hover checks ---
        mouse_pos = pygame.mouse.get_pos()
        all_buttons = self.focus_buttons + ([self.intensity_minus_button, self.intensity_plus_button])
        for btn in all_buttons:
            if btn: btn.check_hover(mouse_pos)

        # Handle button clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = False
            for btn in self.focus_buttons:
                if btn and btn.check_click(event.pos): clicked = True; break
            if not clicked and self.intensity_minus_button:
                if self.intensity_minus_button.check_click(event.pos): clicked = True
            if not clicked and self.intensity_plus_button:
                if self.intensity_plus_button.check_click(event.pos): clicked = True

    def update(self, dt: float):
        """Updates message timers."""
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.success_message = None
                self.error_message = None # Clear messages when timer expires

    def _get_main_content_rect(self) -> pygame.Rect:
        """Helper function to calculate the main content area rectangle."""
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

    def draw(self, screen: pygame.Surface):
        """Draws the training screen."""
        main_rect = self._get_main_content_rect()
        pygame.draw.rect(screen, self.colors['panel'], main_rect) # Draw panel background

        # --- Draw Title ---
        title_text = self.labels.get_text("TRAINING_TITLE")
        title_pos_y = main_rect.top + self.padding + self.title_height // 2
        self.draw_text(screen, title_text, (main_rect.centerx, title_pos_y),
                       self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

        if self.loading_state == "loading":
            loading_text = self.labels.get_text("LOADING")
            self.draw_text(screen, loading_text, main_rect.center, self.font_medium,
                           self.colors['text_normal'], center_x=True, center_y=True)
            return # Don't draw controls while loading

        # --- Draw Intensity Section ---
        intensity_label_y = main_rect.top + self.padding + 60
        intensity_controls_y = intensity_label_y + 40
        intensity_controls_center_x = main_rect.centerx

        intensity_label_text = self.labels.get_text("LABEL_INTENSITY")
        self.draw_text(screen, intensity_label_text, (intensity_controls_center_x, intensity_label_y),
                       self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)

        # Draw the intensity value
        self.draw_text(screen, str(self.current_intensity), (intensity_controls_center_x, intensity_controls_y),
                       self.font_large, self.colors['text_normal'], center_x=True, center_y=True)

        # Draw +/- buttons
        if self.intensity_minus_button: self.intensity_minus_button.draw(screen)
        if self.intensity_plus_button: self.intensity_plus_button.draw(screen)

        # --- Draw Focus Area Section ---
        focus_label_y = intensity_controls_y + (self.intensity_plus_button.rect.height if self.intensity_plus_button else 40) + self.section_padding
        focus_buttons_start_y = focus_label_y + 40 # Used in _create_ui for positioning

        focus_label_text = self.labels.get_text("LABEL_FOCUS_AREA")
        self.draw_text(screen, focus_label_text, (main_rect.centerx, focus_label_y),
                       self.font_medium, self.colors['text_normal'], center_x=True, center_y=True)

        # Draw focus buttons (button.draw handles active state visual)
        for btn in self.focus_buttons:
            btn.draw(screen)

        # --- Draw Feedback Messages ---
        message_y = main_rect.bottom - 40 # Position near bottom of panel
        if self.message_timer > 0:
            if self.error_message:
                self.draw_text(screen, self.error_message, (main_rect.centerx, message_y),
                               self.font_medium, self.colors['error_text'], center_x=True, center_y=True)
            elif self.success_message:
                self.draw_text(screen, self.success_message, (main_rect.centerx, message_y),
                               self.font_medium, self.colors['success_text'], center_x=True, center_y=True)
        elif self.loading_state == "error" and self.error_message: # Show persistent load error
             self.draw_text(screen, self.error_message, (main_rect.centerx, message_y),
                           self.font_medium, self.colors['error_text'], center_x=True, center_y=True)