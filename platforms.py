# platforms.py

import pygame
from constants import TILE_SIZE, COLOR_GREEN, COLOR_BLUE

class Platforms:
    """
    Class representing a platform in the game.
    """

    def __init__(self, grid_x, grid_y, width_in_tiles, height_in_tiles, platform_type="normal"):
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.width_in_tiles = width_in_tiles
        self.height_in_tiles = height_in_tiles
        self.platform_type = platform_type
        self.rect = pygame.Rect(
            int(grid_x * TILE_SIZE),
            int(grid_y * TILE_SIZE),
            int(width_in_tiles * TILE_SIZE),
            int(height_in_tiles * TILE_SIZE)
        )
        # Additional attributes for different platform types
        self.active = True  # For breakable and deadly platforms
        self.break_timer = 0  # Timer for breakable platforms
        self.respawn_timer = 0  # Timer for respawning

    def update(self, delta_time):
        if self.platform_type == "breakable":
            if not self.active:
                self.respawn_timer += delta_time
                if self.respawn_timer >= 5:
                    self.active = True
                    self.respawn_timer = 0
            elif self.break_timer > 0:
                self.break_timer += delta_time
                if self.break_timer >= 1:
                    self.active = False
                    self.break_timer = 0
        elif self.platform_type == "deadly" and not self.active:
            self.respawn_timer += delta_time
            if self.respawn_timer >= 1:
                self.active = True
                self.respawn_timer = 0

    def render(self, screen, camera=None):
        if not self.active:
            return  # Do not render inactive platforms

        if self.platform_type == "normal":
            color = COLOR_GREEN
        elif self.platform_type == "breakable":
            color = (139, 69, 19)  # Brown color
        elif self.platform_type == "gravity":
            color = COLOR_BLUE
        elif self.platform_type == "deadly":
            color = (255, 0, 0)  # Red color for deadly platforms
        else:
            color = COLOR_GREEN  # Default color for unknown types

        adjusted_rect = camera.apply_rect(self.rect) if camera else self.rect
        pygame.draw.rect(screen, color, adjusted_rect)
