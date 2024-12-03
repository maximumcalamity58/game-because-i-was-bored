import os
import pygame
import uuid
import json
from player import Player
from platforms import Platforms
from constants import (
    BROADCAST_PORT, TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_LIGHT_BLUE
)
from network_utils import recvall
from rendering import (
    render_background, render_players, render_platforms,
    render_chat, render_debug_overlay
)

import tkinter as tk
import threading
import sys
import socket
import struct
import pickle
import queue

def discover_servers_multicast(server_queue, stop_event, timeout=5):
    """
    Discover available servers by listening for multicast messages.
    Sends discovered servers to a queue for GUI updates.
    """
    multicast_group = '224.0.0.1'  # Multicast group address (commonly used address)
    port = BROADCAST_PORT  # Same port as before
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Allow reusing the address and sending broadcast messages
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Bind to the port to listen for multicast messages
    multicast_socket.bind(('', port))

    # Tell the socket to join the multicast group
    group = socket.inet_aton(multicast_group)  # Convert IP address to binary format
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)  # Bind the multicast group to any local address
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # Set timeout for waiting for multicast messages
    multicast_socket.settimeout(timeout)

    print("Searching for servers via multicast...")

    try:
        while not stop_event.is_set():
            try:
                data, addr = multicast_socket.recvfrom(1024)
                server_info = pickle.loads(data)
                server_info['address'] = addr[0]
                server_queue.put(server_info)  # Add to queue for GUI updates
                print(f"Discovered server: {server_info['server_name']} at {addr[0]}")
            except socket.timeout:
                # Timeout after waiting for responses
                pass
    finally:
        multicast_socket.close()


def select_server_gui():
    """
    Create a tkinter GUI to display and select a server, with manual refresh and dynamic updates.
    """
    servers = []
    selected_server = {}
    stop_event = threading.Event()  # Event to signal the discovery thread to stop
    server_queue = queue.Queue()    # Queue for communicating discovered servers

    def start_search():
        """
        Start the server discovery thread.
        """
        stop_event.clear()  # Ensure the event is reset for a fresh search
        threading.Thread(target=discover_servers_multicast, args=(server_queue, stop_event), daemon=True).start()

    def update_server_list():
        """
        Update the server list from the queue.
        """
        while not server_queue.empty():
            server_info = server_queue.get()
            if server_info not in servers:
                servers.append(server_info)
                server_listbox.insert(tk.END, f"{server_info['server_name']} ({server_info['address']}:{server_info['port']})")

    def refresh_servers():
        """
        Clear the current list and restart the search.
        """
        servers.clear()
        server_listbox.delete(0, tk.END)
        start_search()

    def select_server(event=None):
        """
        Select a server from the list and close the GUI.
        """
        selection = server_listbox.curselection()
        if selection:
            index = selection[0]
            selected_server.update(servers[index])
            stop_event.set()  # Stop the discovery thread
            root.destroy()

    def poll_queue():
        """
        Poll the server queue periodically to update the GUI.
        """
        update_server_list()
        if not stop_event.is_set():
            root.after(100, poll_queue)  # Schedule the next poll

    # Initialize tkinter window
    root = tk.Tk()
    root.title("Select a Server")

    tk.Label(root, text="Discovered Servers:").pack(pady=5)

    server_listbox = tk.Listbox(root, width=50, height=10)
    server_listbox.pack(pady=5)
    server_listbox.bind("<Double-1>", select_server)

    tk.Button(root, text="Refresh", command=refresh_servers).pack(pady=5)
    tk.Button(root, text="Connect", command=select_server).pack(pady=10)

    # Start the server discovery process
    start_search()

    # Poll the server queue for updates
    root.after(100, poll_queue)

    # Open the GUI
    root.mainloop()

    if not selected_server:
        sys.exit("No server selected.")

    return selected_server

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

        x = max(0, min(x, self.width - SCREEN_WIDTH))
        y = max(0, min(y, self.height - SCREEN_HEIGHT))

        self.camera = pygame.Rect(x, y, SCREEN_WIDTH, SCREEN_HEIGHT)

def main():
    # Step 1: Open server selection GUI
    selected_server = select_server_gui()

    # Step 2: Connect to the selected server
    print(f"Connecting to server {selected_server['server_name']} at {selected_server['address']}:{selected_server['port']}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.connect((selected_server['address'], selected_server['port']))
    except ConnectionRefusedError:
        print("Unable to connect to the server.")
        sys.exit()

    # Step 3: Initialize pygame after server selection
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Client View")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    # Step 4: Load player data
    print("Loading player data...")  # Debugging
    player_uuid, username, selected_hat = load_player_data()

    # Generate a UUID if not present
    if not player_uuid:
        player_uuid = str(uuid.uuid4())

    # Prompt for username if not set
    if not username:
        username = ''
        input_font = pygame.font.SysFont(None, 36)
        input_active = True
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

    # Exit if no server is selected
    if not selected_server:
        print("No server selected. Exiting.")
        pygame.quit()
        sys.exit()

    print(f"Connecting to server {selected_server['server_name']} at {selected_server['address']}:{selected_server['port']}")

    # Connect to the selected server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.connect((selected_server['address'], selected_server['port']))
    except ConnectionRefusedError:
        print("Unable to connect to the server.")
        pygame.quit()
        sys.exit()

    # Send initialization data to the server
    try:
        init_data = {'uuid': player_uuid, 'username': username, 'hat': selected_hat}
        init_data_serialized = pickle.dumps(init_data)
        data_length = len(init_data_serialized)
        server_socket.sendall(data_length.to_bytes(4, byteorder='big') + init_data_serialized)
    except Exception as e:
        print(f"Error sending initialization data: {e}")
        pygame.quit()
        sys.exit()

    player = Player(2.0, 10.0, 20, 20, username=username, hat=selected_hat)
    player.is_local_player = True
    player.uuid = player_uuid

    platforms = []
    players = {}
    chat_messages = []
    show_debug_overlay = False

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

                        for uuid, pdata in players_data.items():
                            if uuid == player_uuid:
                                player.update_attributes(pdata)
                                player.grid_x, player.grid_y = pdata.get('position', (0, 0))
                                player.rect.x = int(player.grid_x * TILE_SIZE)
                                player.rect.y = int(player.grid_y * TILE_SIZE)
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
                                    if uuid in players:
                                        del players[uuid]

                        chat_messages.extend(messages)

                        level_width = max(platform.rect.right for platform in platforms) if platforms else SCREEN_WIDTH
                        level_height = max(platform.rect.bottom for platform in platforms) if platforms else SCREEN_HEIGHT
                        camera.width = level_width
                        camera.height = level_height
            except Exception as e:
                print(f"Error receiving game state: {e}")
                pygame.quit()
                sys.exit()

    recv_thread = threading.Thread(target=receive_game_state, daemon=True)
    recv_thread.start()

    def update(delta_time):
        player.handle_input(delta_time)
        player.apply_gravity(delta_time)
        player.update(platforms, players, delta_time)

        try:
            data = {
                'position': (player.grid_x, player.grid_y),
                'velocity_x': player.velocity_x,
                'velocity_y': player.velocity_y,
                'gravity_direction': player.gravity_direction
            }
            serialized_data = pickle.dumps(data)
            data_length = len(serialized_data)
            server_socket.sendall(data_length.to_bytes(4, byteorder='big') + serialized_data)
        except Exception as e:
            print(f"Error sending data to server: {e}")
            pygame.quit()
            sys.exit()

    running = True
    while running:
        delta_time = clock.tick(60) / 1000.0
        delta_time = min(delta_time, 1 / 30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    show_debug_overlay = not show_debug_overlay

        update(delta_time)
        camera.update(player)

        render_background(screen)
        render_platforms(screen, platforms, camera)
        with threading.Lock():
            render_players(screen, players, player, font=font, camera=camera)
        render_chat(screen, font, chat_messages)

        if show_debug_overlay:
            render_debug_overlay(screen, font, clock)

        pygame.display.flip()

    pygame.quit()
    server_socket.close()

if __name__ == "__main__":
    main()
