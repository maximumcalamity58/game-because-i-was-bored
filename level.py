# level.py

import json
from platforms import Platforms

def create_platforms():
    """
    Create and return a list of Platforms instances based on 'level_data.json'.
    """
    with open('level_data.json', 'r') as f:
        platform_configs = json.load(f)

    platforms = []
    for config in platform_configs:
        platform = Platforms(
            grid_x=config["grid_x"],
            grid_y=config["grid_y"],
            width_in_tiles=config["width_in_tiles"],
            height_in_tiles=config["height_in_tiles"],
            platform_type=config.get("platform_type", "normal")
        )
        platforms.append(platform)
    return platforms
