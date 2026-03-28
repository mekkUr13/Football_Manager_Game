from common.utilities import get_base_path
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent.parent
# ASSETS_PATH = ROOT_PATH / 'assets'
ASSETS_PATH = get_base_path() / "assets"
DATA_PATH = ROOT_PATH / 'data'

# --- UI Constants ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Button settings
BUTTON_WIDTH = 200
BUTTON_HEIGHT = 50
BUTTON_MARGIN = 20
ACTIVE_COLOR = (255, 200, 0)  # Yellowish
INACTIVE_COLOR = (80, 80, 80)    # Dark Grey
BORDER_COLOR = (200, 200, 200)  # Light Grey
TEXT_COLOR = (255, 255, 255)  # White
FONT_SIZE_BUTTON = 30
FONT_SIZE_MEDIUM = 24
FONT_SIZE_LARGE = 36
FONT_SIZE_SMALL = 18

# Colors
COLOR_BACKGROUND = (30, 30, 30) # Very Dark Grey
COLOR_TEXT_NORMAL = (240, 240, 245)  # Off-white
COLOR_TEXT_OUTLINE = (10, 10, 10) # Dark color for the outline/shadow
COLOR_PANEL = (50, 50, 50) # Dark Grey Panel Background
COLOR_BORDER = BORDER_COLOR # Alias for consistency if needed elsewhere

EXIT_BUTTON_SIZE = 32 # Size for the square exit button
EXIT_BUTTON_MARGIN = 10 # Margin from top-left corner
COLOR_EXIT_BG_NORMAL = (180, 40, 40) # Dark Red
COLOR_EXIT_BG_HOVER = (220, 60, 60) # Brighter Red on hover
COLOR_EXIT_X = (255, 255, 255) # White 'X'
COLOR_EXIT_BORDER = (50, 0, 0)   # Very Dark Red Border

# Layout
SIDE_PANEL_WIDTH = BUTTON_WIDTH + 2 * BUTTON_MARGIN
MAIN_AREA_X = SIDE_PANEL_WIDTH
MAIN_AREA_Y = BUTTON_MARGIN
MAIN_AREA_WIDTH = SCREEN_WIDTH - 2 * SIDE_PANEL_WIDTH
MAIN_AREA_HEIGHT = SCREEN_HEIGHT - 2 * BUTTON_MARGIN
# --- End UI Constants ---


FORMATION_TEMPLATES = {
    "4-4-2": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"],
    "4-3-3": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "CM", "RW", "ST", "LW"],
    "3-4-3": ["GK", "CB", "CB", "CB", "RM", "CM", "CM", "LM", "RW", "ST", "LW"],
    "5-2-1-2": ["GK", "RB", "CB", "CB", "CB", "LB", "CM", "CM", "CAM", "ST", "ST"],
}

ATTACKERS = {"ST", "LW", "RW"}
MIDFIELDERS = {"CM", "CDM", "CAM", "LM", "RM"}
DEFENDERS = {"CB", "RB", "LB", "GK"}

FREE_AGENTS_CLUB_NAME_PREFIX = "Unattached Players Pool" # New constant