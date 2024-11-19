# client.py

import os
import subprocess

import pygame
import socket
import threading
import pickle
import sys
import uuid
import json
from player import Player
from level import create_platforms  # Import the platform creation function
from platforms import Platforms  # To create Platforms from received data
from constants import (
    HOST, PORT, TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_LIGHT_BLUE, COLOR_RED, COLOR_BLUE, COLOR_WHITE
)
from network_utils import recvall
from rendering import (
    render_background, render_players, render_platforms,
    render_chat, render_debug_overlay
)

def load_player_data():
    data_file = 'player_data.json'
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            data = json.load(f)
            return data.get('uuid'), data.get('username'), data.get('hat')
    else:
        return None, None, None

def save_player_data(player_uuid, username, hat):
    data_file = 'player_data.json'
    data = {
        'uuid': player_uuid,
        'username': username,
        'hat': hat
    }
    with open(data_file, 'w') as f:
        json.dump(data, f)

class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.width = width
        self.height = height

    def apply(self, target):
        return target.rect.move(-self.camera.x, -self.camera.y)

    def apply_rect(self, rect):
        return rect.move(-self.camera.x, -self.camera.y)

    def update(self, target):
        x = target.rect.centerx - SCREEN_WIDTH // 2
        y = target.rect.centery - SCREEN_HEIGHT // 2

        # Limit scrolling to the size of the game world (assuming world starts at 0,0)
        x = max(0, min(x, self.width - SCREEN_WIDTH))
        y = max(0, min(y, self.height - SCREEN_HEIGHT))

        self.camera = pygame.Rect(x, y, SCREEN_WIDTH, SCREEN_HEIGHT)

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Client View")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    # Load saved UUID and username
    player_uuid, username, selected_hat = load_player_data()

    # If no UUID, generate one
    if not player_uuid:
        player_uuid = str(uuid.uuid4())

    # If no username, prompt for username
    if not username:
        # Prompt for username
        username = ''
        input_active = True
        input_font = pygame.font.SysFont(None, 36)
        while input_active:
            screen.fill((0, 0, 0))
            prompt_text = input_font.render("Enter your username:", True, COLOR_WHITE)
            screen.blit(prompt_text, (SCREEN_WIDTH // 2 - prompt_text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
            username_text = input_font.render(username, True, COLOR_WHITE)
            screen.blit(username_text, (SCREEN_WIDTH // 2 - username_text.get_width() // 2, SCREEN_HEIGHT // 2))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        input_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        username = username[:-1]
                    else:
                        username += event.unicode

    # If no selected_hat, perform hat selection
    if selected_hat is None:
        # Hat selection
        hat_options = [None, 'hat1.png', 'hat2.png', 'hat3.png']
        hat_index = 0
        selecting_hat = True

        # Load hat images
        hats = []
        for hat_option in hat_options:
            if hat_option is None:
                hats.append(None)  # Represents "No Hat"
            else:
                try:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    hats_dir = os.path.join(base_dir, 'hats')
                    hat_path = os.path.join(hats_dir, hat_option)

                    original_image = pygame.image.load(hat_path).convert_alpha()

                    desired_hat_height = 80  # Adjust as needed

                    scale_factor = desired_hat_height / original_image.get_height()
                    new_width = int(original_image.get_width() * scale_factor)
                    new_height = int(original_image.get_height() * scale_factor)

                    hat_image_scaled = pygame.transform.scale(original_image, (new_width, new_height))

                    # Directly append the scaled image to the hats list
                    hats.append(hat_image_scaled)
                except Exception as e:
                    print(f"Error loading {hat_option}: {e}")
                    hats.append(None)

        while selecting_hat:
            screen.fill((0, 0, 0))
            prompt_text = input_font.render("Select your hat (Use Left/Right Arrows):", True, COLOR_WHITE)
            screen.blit(prompt_text, (SCREEN_WIDTH // 2 - prompt_text.get_width() // 2, SCREEN_HEIGHT // 2 - 100))

            # Display the current hat
            current_hat = hats[hat_index]
            if current_hat:
                hat_rect = current_hat.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                screen.blit(current_hat, hat_rect)
            elif hat_index != 0:
                error_text = input_font.render("Error loading hat image.", True, COLOR_WHITE)
                screen.blit(error_text, (SCREEN_WIDTH // 2 - error_text.get_width() // 2, SCREEN_HEIGHT // 2))

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        selecting_hat = False
                    elif event.key == pygame.K_LEFT:
                        hat_index = (hat_index - 1) % len(hats)
                    elif event.key == pygame.K_RIGHT:
                        hat_index = (hat_index + 1) % len(hats)

        selected_hat = hat_options[hat_index]

        # Save player data
        save_player_data(player_uuid, username, selected_hat)
    else:
        # Load the selected hat image
        pass  # The hat image will be loaded when initializing the Player

    # Initialize player with default position (will be updated from server)
    player = Player(2.0, 10.0, 20, 20, username=username, hat=selected_hat)
    player.is_local_player = True
    player.uuid = player_uuid

    # Initialize other variables
    platforms = []  # Start with an empty list; will be populated from server
    players = {}
    chat_messages = []
    show_debug_overlay = False

    # Connect to server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("Unable to connect to the server.")
        pygame.quit()
        sys.exit()

    # Send UUID, username, and hat to the server
    try:
        init_data = {'uuid': player_uuid, 'username': username, 'hat': selected_hat}
        init_data_serialized = pickle.dumps(init_data)
        data_length = len(init_data_serialized)
        server_socket.sendall(data_length.to_bytes(4, byteorder='big') + init_data_serialized)
    except Exception as e:
        print(f"Error sending initialization data: {e}")
        pygame.quit()
        sys.exit()

    # Receive player's position from the server
    try:
        data_length_bytes = recvall(server_socket, 4)
        if not data_length_bytes:
            print("Server closed the connection.")
            pygame.quit()
            sys.exit()
        data_length = int.from_bytes(data_length_bytes, byteorder='big')
        data = recvall(server_socket, data_length)
        position_data = pickle.loads(data)
        # Set the player's position
        player.grid_x, player.grid_y = position_data.get('position', (2.0, 10.0))
        player.rect.x = int(player.grid_x * TILE_SIZE)
        player.rect.y = int(player.grid_y * TILE_SIZE)
        player.velocity_x = position_data.get('velocity_x', 0.0)
        player.velocity_y = position_data.get('velocity_y', 0.0)
        player.hat = position_data.get('hat', player.hat)
        if player.hat:
            player.load_hat_image(player.hat)
        player.username = position_data.get('username', player.username)
    except Exception as e:
        print(f"Error receiving position data from server: {e}")
        pygame.quit()
        sys.exit()

    # Initialize camera
    camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

    def receive_game_state():
        while True:
            try:
                data_length_bytes = recvall(server_socket, 4)
                if not data_length_bytes:
                    print("Server closed the connection.")
                    break
                data_length = int.from_bytes(data_length_bytes, byteorder='big')
                data = recvall(server_socket, data_length)
                if data:
                    received_data = pickle.loads(data)
                    players_data = received_data.get('players', {})
                    platforms_data = received_data.get('platforms', [])
                    messages = received_data.get('chat', [])

                    with threading.Lock():
                        # Update platforms
                        platforms.clear()
                        for pdata in platforms_data:
                            platform = Platforms(
                                grid_x=pdata['grid_x'],
                                grid_y=pdata['grid_y'],
                                width_in_tiles=pdata['width_in_tiles'],
                                height_in_tiles=pdata['height_in_tiles'],
                                platform_type=pdata.get('platform_type', 'normal')
                            )
                            platform.active = pdata.get('active', True)
                            platforms.append(platform)

                        # Update players
                        for uuid, pdata in players_data.items():
                            if uuid == player_uuid:
                                # Update local player attributes (position handled separately)
                                player.update_attributes(pdata)
                            else:
                                if pdata.get('connected', False):
                                    if uuid not in players:
                                        players[uuid] = Player(
                                            pdata.get('position', (0, 0))[0],
                                            pdata.get('position', (0, 0))[1],
                                            20, 20,
                                            username=pdata.get('username', 'Player'),
                                            hat=pdata.get('hat', None)
                                        )
                                        players[uuid].is_local_player = False
                                        players[uuid].uuid = uuid
                                    else:
                                        players[uuid].grid_x, players[uuid].grid_y = pdata.get('position', (0, 0))
                                        players[uuid].rect.x = int(players[uuid].grid_x * TILE_SIZE)
                                        players[uuid].rect.y = int(players[uuid].grid_y * TILE_SIZE)
                                        players[uuid].update_attributes(pdata)
                                else:
                                    # Remove disconnected players
                                    if uuid in players:
                                        del players[uuid]

                        # Add new chat messages
                        chat_messages.extend(messages)

                        # Update camera dimensions based on level size
                        level_width = max(platform.rect.right for platform in platforms) if platforms else SCREEN_WIDTH
                        level_height = max(platform.rect.bottom for platform in platforms) if platforms else SCREEN_HEIGHT
                        camera.width = level_width
                        camera.height = level_height

                else:
                    print("No data received from server.")
            except Exception as e:
                print(f"Error receiving game state: {e}")
                pygame.quit()
                sys.exit()

    # Start a thread to receive game state
    recv_thread = threading.Thread(target=receive_game_state, daemon=True)
    recv_thread.start()

    def update(delta_time):
        # Handle input
        player.handle_input(delta_time)

        # Apply gravity
        player.apply_gravity(delta_time)

        # Update position
        player.update(platforms, players, delta_time)

        # Send updated position to server
        try:
            data = {
                'position': (player.grid_x, player.grid_y),
                'velocity_x': player.velocity_x,
                'velocity_y': player.velocity_y
            }
            serialized_data = pickle.dumps(data)
            data_length = len(serialized_data)
            server_socket.sendall(data_length.to_bytes(4, byteorder='big') + serialized_data)
        except Exception as e:
            print(f"Error sending data to server: {e}")
            pygame.quit()
            sys.exit()

    # Main game loop
    running = True
    while running:
        delta_time = clock.tick(60) / 1000.0  # Convert milliseconds to seconds
        delta_time = min(delta_time, 1/30)    # Cap delta_time to a maximum of 1/30 seconds

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    show_debug_overlay = not show_debug_overlay

        # Update game state
        update(delta_time)

        # Update camera
        camera.update(player)

        # Render the game
        render_background(screen)
        render_platforms(screen, platforms, camera)
        with threading.Lock():
            render_players(screen, players, player, font=font, camera=camera)
        render_chat(screen, font, chat_messages)

        # Display debug overlay if enabled
        if show_debug_overlay:
            render_debug_overlay(screen, font, clock)  # Do not pass num_players

        # Update display
        pygame.display.flip()

    # Clean up
    pygame.quit()
    server_socket.close()

if __name__ == "__main__":
    main()
