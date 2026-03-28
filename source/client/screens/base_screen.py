import pygame
from typing import TYPE_CHECKING, Optional, Dict

if TYPE_CHECKING:
    from client.game import Game

class BaseScreen:
    """
    Base class for all game screens (views).

    Each screen handles its own events, updates, and drawing logic.
    It provides common attributes like fonts and helper methods.
    """
    def __init__(self, game: 'Game'):
        """
        Initializes the base screen.

        Args:
            game: The main Game object, providing access to shared resources
                  like the screen surface, network client, constants, fonts,
                  labels, and colors.
        """
        self.game = game
        # Store frequently used resources for convenience
        self.font_medium = game.fonts['medium']
        self.font_large = game.fonts['large']
        self.font_small = game.fonts['small']
        self.colors = game.colors
        self.labels = game.labels
        self.constants = game.constants

    def handle_event(self, event: pygame.event.Event):
        """
        Processes a single Pygame event. Subclasses should override this
        to handle specific inputs relevant to the screen.

        Args:
            event: The Pygame event object to process.
        """
        # Default behavior: do nothing. Subclasses implement specific handling.
        pass

    def update(self, dt: float):
        """
        Updates the screen's state. Called once per frame.
        Subclasses can override this for animations, timers, or other
        time-dependent logic.

        Args:
            dt: Delta time in seconds since the last frame update.
        """
        # Default behavior: do nothing. Subclasses implement updates if needed.
        pass

    def draw(self, screen: pygame.Surface):
        """
        Draws the screen's contents onto the provided surface.
        Subclasses MUST override this method to render their UI.

        Args:
            screen: The Pygame screen surface (from self.game.screen) to draw onto.
        """
        # Default implementation: Draw the screen's class name as a placeholder
        # Subclasses should replace this with their actual drawing code.
        screen_name = self.__class__.__name__
        try:
            text_surf = self.font_large.render(screen_name, True, self.colors['text_normal'])
            text_rect = text_surf.get_rect(center=(self.game.screen.get_width() // 2, self.game.screen.get_height() // 2))
            screen.blit(text_surf, text_rect)
        except pygame.error as e:
            print(f"Error rendering default text for {screen_name}: {e}")
        except AttributeError:
             print(f"Error: Fonts or constants not properly initialized in {screen_name}?")


    def on_enter(self, data: Optional[Dict] = None):
        """
        Called when this screen becomes the active screen.
        Useful for initializing state, loading data, or resetting elements
        when the screen is entered. Subclasses can override this.

        Args:
            data (Optional[Dict]): An optional dictionary containing data passed
                                   from the previous screen or game state change.
        """
        # Base implementation just prints a message.
        # It accepts 'data' but doesn't use it here.
        print(f"Entering screen: {self.__class__.__name__}")
        # Subclasses can use 'data' if needed:
        # if data:
        #     some_value = data.get('key')
        pass

    def on_exit(self):
        """
        Called when this screen is no longer the active screen.
        Useful for saving state, cleaning up resources, or performing actions
        before transitioning away from the screen. Subclasses can override this.
        """
        # Default behavior: do nothing. Subclasses implement cleanup if needed.
        pass

    # --- Helper method for drawing text consistently with outline ---
    def draw_text(self, surface: pygame.Surface, text: str, position: tuple[int, int],
                  font: pygame.font.Font, color: tuple[int, int, int],
                  center_x: bool = False, center_y: bool = False,
                  antialias: bool = True,
                  outline_color: Optional[tuple[int, int, int]] = None,  # Optional outline color override
                  outline_thickness: int = 1):  # Outline thickness in pixels
        """
        Renders and draws text onto a surface with optional centering and outline.

        Args:
            surface: The Pygame surface to draw on.
            text: The string to render.
            position: The (x, y) coordinates for the top-left corner (or center if specified).
            font: The Pygame font object to use.
            color: The RGB tuple representing the main text color.
            center_x: If True, centers the text horizontally at position[0].
            center_y: If True, centers the text vertically at position[1].
            antialias: If True, renders text with antialiasing (smoother).
            outline_color (Optional): Color for the text outline. Defaults to constants.COLOR_TEXT_OUTLINE.
            outline_thickness (int): Pixel offset for the outline effect.
        """
        try:
            # Use default outline color if none provided
            if outline_color is None:
                outline_color = self.colors.get('text_outline', (0, 0, 0))  # Fallback to black

            # Render the main text surface
            text_surface = font.render(str(text), antialias, color)
            text_rect = text_surface.get_rect()

            # Adjust position based on centering flags
            if center_x:
                text_rect.centerx = position[0]
            else:
                text_rect.x = position[0]
            if center_y:
                text_rect.centery = position[1]
            else:
                text_rect.y = position[1]

            # --- Draw Outline/Shadow ---
            if outline_thickness > 0 and outline_color != color:
                # Render the outline text surface
                outline_surface = font.render(str(text), antialias, outline_color)
                # Define offsets for the outline (e.g., 4 directions for 1px outline)
                offsets = []
                for dx in range(-outline_thickness, outline_thickness + 1, outline_thickness):
                    for dy in range(-outline_thickness, outline_thickness + 1, outline_thickness):
                        if dx != 0 or dy != 0:  # Don't draw outline at the exact same spot
                            offsets.append((dx, dy))
                # Blit the outline surface at each offset position *behind* the main text
                for dx, dy in offsets:
                    outline_rect = text_rect.move(dx, dy)
                    surface.blit(outline_surface, outline_rect)
            # --- End Outline ---

            # Draw the main text surface on top
            surface.blit(text_surface, text_rect)

        except AttributeError as e:
            print(f"Error in draw_text: Font '{font}' might not be a valid Pygame font object. {e}")
        except pygame.error as e:
            print(f"Pygame error drawing text '{text}': {e}")
        except Exception as e:
            print(f"Unexpected error drawing text '{text}': {e}")