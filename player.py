# player.py

import pygame
import os
from constants import TILE_SIZE, GRAVITY, INITIAL_JUMP_VELOCITY, MAX_FALL_SPEED, JUMP_HOLD_TIME

class Player:
    """
    Class representing a player in the game.
    """

    def __init__(self, x, y, width, height, username='Player', hat=None, uuid=None):
        self.grid_x = x
        self.grid_y = y
        self.width = width
        self.height = height
        self.username = username
        self.hat = hat
        self.hat_image = None
        if self.hat:
            self.load_hat_image(self.hat)
        self.velocity_y = 0.0
        self.velocity_x = 0.0
        self.is_jumping = False
        self.on_ground = False
        self.jump_time = 0.0
        self.rect = pygame.Rect(int(self.grid_x * TILE_SIZE), int(self.grid_y * TILE_SIZE), width, height)
        self.speed = 300  # Pixels per second
        self.frozen = False
        self.received_position_update = False
        self.is_local_player = False
        self.uuid = uuid
        self.connected = True
        self.gravity_direction = "down"  # Default gravity direction

    def load_hat_image(self, hat):
        """
        Load and scale the hat image from the hats directory.
        """
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            hats_dir = os.path.join(base_dir, 'hats')
            hat_path = os.path.join(hats_dir, hat)
            original_image = pygame.image.load(hat_path).convert_alpha()

            # Define desired hat height
            desired_hat_height = self.height
            scale_factor = desired_hat_height / original_image.get_height()
            new_width = int(original_image.get_width() * scale_factor)
            new_height = int(original_image.get_height() * scale_factor)
            self.hat_image = pygame.transform.scale(original_image, (new_width, new_height))
        except Exception as e:
            print(f"Error loading hat image '{hat}': {e}")
            self.hat_image = None

    def handle_input(self, delta_time):
        if self.frozen:
            self.velocity_x = 0
            self.velocity_y = 0
            return

        keys = pygame.key.get_pressed()

        # Movement keys
        if self.gravity_direction in ("down", "up"):
            # Horizontal movement
            if keys[pygame.K_a]:
                self.velocity_x = -self.speed
            elif keys[pygame.K_d]:
                self.velocity_x = self.speed
            else:
                self.velocity_x = 0
        else:
            # Vertical movement when gravity is left or right
            if keys[pygame.K_w]:
                self.velocity_y = -self.speed
            elif keys[pygame.K_s]:
                self.velocity_y = self.speed
            else:
                self.velocity_y = 0

        # Jumping
        if keys[pygame.K_SPACE]:
            if self.on_ground and not self.is_jumping:
                self.is_jumping = True
                self.jump_time = 0.0
                self.on_ground = False

                # Set initial jump velocity opposite to gravity
                if self.gravity_direction == "down":
                    self.velocity_y = -INITIAL_JUMP_VELOCITY
                elif self.gravity_direction == "up":
                    self.velocity_y = INITIAL_JUMP_VELOCITY
                elif self.gravity_direction == "left":
                    self.velocity_x = INITIAL_JUMP_VELOCITY
                elif self.gravity_direction == "right":
                    self.velocity_x = -INITIAL_JUMP_VELOCITY

            if self.is_jumping and self.jump_time < JUMP_HOLD_TIME:
                self.jump_time += delta_time
        else:
            if self.is_jumping:
                self.is_jumping = False
                self.jump_time = 0.0

    def apply_gravity(self, delta_time):
        gravity_effect = GRAVITY
        if self.is_jumping and self.jump_time < JUMP_HOLD_TIME:
            gravity_effect *= (1 - ((self.jump_time / JUMP_HOLD_TIME) * 1.5))  # Reduce gravity while jumping

        if self.gravity_direction == "down":
            self.velocity_y += gravity_effect * delta_time
            self.velocity_y = min(self.velocity_y, MAX_FALL_SPEED)
        elif self.gravity_direction == "up":
            self.velocity_y -= gravity_effect * delta_time
            self.velocity_y = max(self.velocity_y, -MAX_FALL_SPEED)
        elif self.gravity_direction == "left":
            self.velocity_x -= gravity_effect * delta_time
            self.velocity_x = max(self.velocity_x, -MAX_FALL_SPEED)
        elif self.gravity_direction == "right":
            self.velocity_x += gravity_effect * delta_time
            self.velocity_x = min(self.velocity_x, MAX_FALL_SPEED)

    def update(self, platforms, other_players, delta_time):
        if self.received_position_update:
            self.received_position_update = False  # Reset the flag
            # Optionally smooth position correction here

        self.handle_input(delta_time)

        # Apply gravity
        self.apply_gravity(delta_time)

        # Update position
        if self.gravity_direction in ("down", "up"):
            # Vertical gravity
            # Move horizontally first
            self.grid_x += self.velocity_x * delta_time / TILE_SIZE
            self.rect.x = int(self.grid_x * TILE_SIZE)

            # Check horizontal collisions
            self.check_collision_with_platforms(platforms, direction="horizontal", delta_time=delta_time)
            self.check_collision_with_players(other_players, direction="horizontal")

            # Move vertically
            self.grid_y += self.velocity_y * delta_time / TILE_SIZE
            self.rect.y = int(self.grid_y * TILE_SIZE)

            # Check vertical collisions
            self.check_collision_with_platforms(platforms, direction="vertical", delta_time=delta_time)
            self.check_collision_with_players(other_players, direction="vertical")
        else:
            # Horizontal gravity
            # Move vertically first
            self.grid_y += self.velocity_y * delta_time / TILE_SIZE
            self.rect.y = int(self.grid_y * TILE_SIZE)

            # Check vertical collisions
            self.check_collision_with_platforms(platforms, direction="vertical", delta_time=delta_time)
            self.check_collision_with_players(other_players, direction="vertical")

            # Move horizontally
            self.grid_x += self.velocity_x * delta_time / TILE_SIZE
            self.rect.x = int(self.grid_x * TILE_SIZE)

            # Check horizontal collisions
            self.check_collision_with_platforms(platforms, direction="horizontal", delta_time=delta_time)
            self.check_collision_with_players(other_players, direction="horizontal")

    def check_collision_with_platforms(self, platforms, direction, delta_time):
        for platform in platforms:
            if not platform.active:
                continue  # Skip inactive platforms
            if self.rect.colliderect(platform.rect):
                # Handle collision response
                if platform.platform_type == "deadly":
                    self.respawn()
                    return  # Exit collision checking for this frame

                if direction == "horizontal":
                    if self.velocity_x > 0:
                        self.rect.right = platform.rect.left
                    elif self.velocity_x < 0:
                        self.rect.left = platform.rect.right
                    self.grid_x = self.rect.x / TILE_SIZE
                    self.velocity_x = 0
                elif direction == "vertical":
                    if self.velocity_y > 0:
                        self.rect.bottom = platform.rect.top
                    elif self.velocity_y < 0:
                        self.rect.top = platform.rect.bottom
                    self.grid_y = self.rect.y / TILE_SIZE
                    self.velocity_y = 0

                    # Determine if on ground based on gravity direction
                    if self.gravity_direction == "down" and self.rect.bottom == platform.rect.top:
                        self.on_ground = True
                    elif self.gravity_direction == "up" and self.rect.top == platform.rect.bottom:
                        self.on_ground = True
                    elif self.gravity_direction == "right" and self.rect.left == platform.rect.right:
                        self.on_ground = True
                    elif self.gravity_direction == "left" and self.rect.right == platform.rect.left:
                        self.on_ground = True

                # Process platform effects
                if platform.platform_type == "breakable":
                    platform.break_timer += delta_time
                    if platform.break_timer >= 1:
                        platform.active = False
                        platform.break_timer = 0
                elif platform.platform_type == "gravity":
                    # Always change gravity when colliding with a gravity platform
                    self.change_gravity(platform)

    def respawn(self):
        """
        Respawn the player at the starting position.
        """
        self.grid_x, self.grid_y = 0.0, 0.0  # Example respawn coordinates
        self.rect.x = int(self.grid_x * TILE_SIZE)
        self.rect.y = int(self.grid_y * TILE_SIZE)
        self.velocity_x = 0
        self.velocity_y = 0
        self.gravity_direction = "down"
        self.on_ground = False

    def is_standing_on_platform(self, platform):
        """
        Check if the player is standing on the platform relative to gravity.
        """
        if self.gravity_direction == "down":
            return self.rect.bottom == platform.rect.top and self.velocity_y >= 0
        elif self.gravity_direction == "up":
            return self.rect.top == platform.rect.bottom and self.velocity_y <= 0
        elif self.gravity_direction == "left":
            return self.rect.left == platform.rect.right and self.velocity_x <= 0
        elif self.gravity_direction == "right":
            return self.rect.right == platform.rect.left and self.velocity_x >= 0
        return False

    def check_collision_with_players(self, players, direction):
        """
        Check and handle collisions with other players.
        """
        for uuid, other in players.items():
            if other.uuid == self.uuid or not other.connected:
                continue  # Skip self and disconnected players
            if self.rect.colliderect(other.rect):
                if direction == "horizontal":
                    if self.velocity_x > 0:
                        self.rect.right = other.rect.left
                    elif self.velocity_x < 0:
                        self.rect.left = other.rect.right
                    self.grid_x = self.rect.x / TILE_SIZE
                    self.velocity_x = 0
                elif direction == "vertical":
                    if self.velocity_y > 0:
                        self.rect.bottom = other.rect.top
                    elif self.velocity_y < 0:
                        self.rect.top = other.rect.bottom
                    self.grid_y = self.rect.y / TILE_SIZE
                    self.velocity_y = 0

    def change_gravity(self, platform):
        dx = self.rect.centerx - platform.rect.centerx
        dy = self.rect.centery - platform.rect.centery

        if abs(dx) > abs(dy):
            if dx > 0:
                new_gravity = "left"
            else:
                new_gravity = "right"
        else:
            if dy > 0:
                new_gravity = "up"
            else:
                new_gravity = "down"

        if self.gravity_direction != new_gravity:
            self.gravity_direction = new_gravity
            self.on_ground = False  # Reset on_ground status
            # Reset velocity along the new gravity axis
            if new_gravity in ("down", "up"):
                self.velocity_y = 0
            else:
                self.velocity_x = 0

    def serialize(self):
        """
        Serialize the player's data for network transmission.
        """
        return {
            'position': (self.grid_x, self.grid_y),
            'velocity_x': self.velocity_x,
            'velocity_y': self.velocity_y,
            'speed': self.speed,
            'frozen': self.frozen,
            'username': self.username,
            'hat': self.hat,
            'uuid': self.uuid,
            'connected': self.connected,
            'gravity_direction': self.gravity_direction
        }

    def update_attributes(self, data):
        """
        Update the player's attributes based on received data.
        """
        self.speed = data.get('speed', self.speed)
        self.frozen = data.get('frozen', self.frozen)
        self.gravity_direction = data.get('gravity_direction', self.gravity_direction)
        if not self.is_local_player:
            self.velocity_x = data.get('velocity_x', self.velocity_x)
            self.velocity_y = data.get('velocity_y', self.velocity_y)
            self.grid_x, self.grid_y = data.get('position', (self.grid_x, self.grid_y))
            self.rect.x = int(self.grid_x * TILE_SIZE)
            self.rect.y = int(self.grid_y * TILE_SIZE)
        new_hat = data.get('hat', self.hat)
        if new_hat != self.hat:
            self.hat = new_hat
            if self.hat:
                self.load_hat_image(self.hat)
            else:
                self.hat_image = None
        self.username = data.get('username', self.username)
