import pygame

class Button:
    """Represents a clickable button, potentially with text or an image."""

    def __init__(self, x: int, y: int, width: int, height: int,
                 font_size: int, active_color: tuple, inactive_color: tuple,
                 border_color: tuple, text_color: tuple, on_click,
                 text: str = "", image: pygame.Surface = None, min_width: int = 0):
        """
        Initializes the button.

        Args:
            x, y, width, height: Position and dimensions of the button.
            font_size: Size of the font for the text (ignored if image is provided).
            active_color: Background color when the button is active/hovered (or tint).
            inactive_color: Background color when the button is inactive.
            border_color: Color of the button's border.
            text_color: Color of the button's text (ignored if image is provided).
            on_click: The function or method to call when the button is clicked.
            text (str): The text to display on the button (if no image). Defaults to "".
            image (pygame.Surface): An optional image to display instead of text. Defaults to None.
            min_width (int): Minimum width for the button, especially useful for text buttons.
        """
        self.text = text
        self.image = image
        self.font = None
        self.font_size = font_size

        # --- Create Font if size is valid, even if text is initially empty ---
        if not self.image and self.font_size > 0:
            try:
                self.font = pygame.font.Font(None, self.font_size)
            except pygame.error as e:
                print(f"Error creating font for button (size {self.font_size}): {e}")
                self.font = None  # Ensure font is None on error
        # --- End Font Creation ---

        actual_width = width
        if self.image:
            self.rect = self.image.get_rect(topleft=(x, y))
            actual_width = self.rect.width  # Use image width
        elif self.text and self.font:
            # self.font = pygame.font.Font(None, font_size)
            text_width = self.font.size(self.text)[0] + 30  # Add padding
            actual_width = max(width, text_width, min_width)  # Use text width if larger than arg, ensure min_width
            self.rect = pygame.Rect(x, y, actual_width, height)
        else:  # No text, no image - use provided dimensions or min_width
            actual_width = max(width, min_width)
            self.rect = pygame.Rect(x, y, actual_width, height)

        self.active = False # State usually controlled by the screen (e.g., for selected options)
        self.hover = False # State for mouse hover visual feedback
        self.active_color = active_color
        self.inactive_color = inactive_color
        self.border_color = border_color
        self.text_color = text_color
        self.on_click = on_click # The function to call

    def draw(self, screen: pygame.Surface):
        """Draws the button onto the screen."""
        # Determine background color based on hover primarily, use active for selection indication
        current_bg_color = self.active_color if self.hover or self.active else self.inactive_color
        border_thickness = 3 if self.hover else 2
        # Use active color for border when selected OR hovered
        current_border_color = self.active_color if self.hover or self.active else self.border_color
        # --- Change text color when active/hovered ---
        current_text_color = (0, 0, 0) if self.hover or self.active else self.text_color # Black text when active/hovered

        if self.image:
            # --- Draw Image Button ---
            screen.blit(self.image, self.rect)
            pygame.draw.rect(screen, current_border_color, self.rect, border_thickness)
        else:
            # --- Draw Text Button ---
            if not isinstance(current_bg_color, (tuple, list)): current_bg_color = (100, 100, 100)
            if not isinstance(current_border_color, (tuple, list)): current_border_color = (200, 200, 200)
            if not isinstance(current_text_color, (tuple, list)): current_text_color = (255, 255, 255) # Fallback text color

            pygame.draw.rect(screen, current_bg_color, self.rect)
            pygame.draw.rect(screen, current_border_color, self.rect, border_thickness)

            if self.text and self.font:
                try:
                    # Use the determined text color
                    text_surf = self.font.render(self.text, True, current_text_color)
                    text_rect = text_surf.get_rect(center=self.rect.center)
                    screen.blit(text_surf, text_rect)
                except Exception as e:
                    print(f"Error rendering button text '{self.text}': {e}")
            else:
            # Conditional debug print - suppress the previous default message
                if not self.image and (not self.text or not self.font): # Only print if it's supposed to be a text button
                    print(f"Debug Button Draw: Not drawing text. Button Rect={self.rect}, Text='{self.text}', Font Exists={hasattr(self, 'font') and self.font is not None}")

    def check_click(self, pos: tuple[int, int]) -> bool:
        """
        Checks if the button was clicked at the given mouse position.
        Calls the on_click function if clicked.

        Args:
            pos: The (x, y) coordinates of the mouse click.

        Returns:
            True if the button was clicked, False otherwise.
        """
        if self.rect.collidepoint(pos):
            if self.on_click: # Ensure an action is defined
                self.on_click() # Execute the button's action
                return True
        return False

    def check_hover(self, pos: tuple[int, int]):
        """Updates the button's hover state based on mouse position."""
        self.hover = self.rect.collidepoint(pos)