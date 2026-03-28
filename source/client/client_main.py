import pygame
import traceback
from client.game import Game

import sys
import os
from pathlib import Path

current_dir = Path(__file__).resolve().parent
source_root = current_dir.parent

sys.path.insert(0, str(source_root / "client"))
sys.path.insert(0, str(source_root / "common"))
sys.path.insert(0, str(source_root))

def main():
    """Initializes and runs the game client."""
    print("Starting MFS Client...")
    game = None # Initialize game to None
    try:
        game = Game()
        if game.running: # Check if Game initialized and connected correctly
             game.run()
    except Exception as e:
        print(f"\n--- An unexpected error occurred ---")
        print(f"Error: {e}")
        traceback.print_exc() # Print detailed traceback
        if game and game.network_client: # Try to disconnect if client exists
             print("Attempting disconnection...")
             game.network_client.disconnect()
        pygame.quit() # Ensure Pygame quits on crash
        input("Press Enter to exit.") # Keep console open

if __name__ == '__main__':
    main()