# level.py

from platforms import Platforms

# Define platform configurations
PLATFORM_CONFIGS = [
    {"grid_x": 0, "grid_y": 29, "width_in_tiles": 40, "height_in_tiles": 1, "platform_type": "normal"},
    {"grid_x": 5, "grid_y": 22, "width_in_tiles": 3, "height_in_tiles": 1, "platform_type": "normal"},
    {"grid_x": 8, "grid_y": 11, "width_in_tiles": 2, "height_in_tiles": 1, "platform_type": "normal"},
    {"grid_x": 10, "grid_y": 16, "width_in_tiles": 5, "height_in_tiles": 1, "platform_type": "deadly"},
    {"grid_x": 20, "grid_y": 22, "width_in_tiles": 10, "height_in_tiles": 1, "platform_type": "gravity"},
    {"grid_x": 40, "grid_y": 22, "width_in_tiles": 1, "height_in_tiles": 10, "platform_type": "normal"},
]

def create_platforms():
    """
    Create and return a list of Platforms instances based on PLATFORM_CONFIGS.
    """
    platforms = []
    for config in PLATFORM_CONFIGS:
        grid_x = config["grid_x"]
        grid_y = config["grid_y"]
        width_in_tiles = config["width_in_tiles"]
        height_in_tiles = config["height_in_tiles"]
        platform_type = config.get("platform_type", "normal")

        for dx in range(width_in_tiles):
            for dy in range(height_in_tiles):
                platform = Platforms(
                    grid_x=grid_x + dx,
                    grid_y=grid_y + dy,
                    width_in_tiles=1,
                    height_in_tiles=1,
                    platform_type=platform_type
                )
                platforms.append(platform)
    return platforms

