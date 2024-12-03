# server.py
import getpass
import tkinter as tk
from tkinter import messagebox
import socket
import threading
import sys
import pygame
import pickle
import json
import time
from level import create_platforms
from player import Player
from constants import (
    PORT, TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    DEBUG_BAR_HEIGHT, BROADCAST_PORT, BROADCAST_INTERVAL
)
from network_utils import recvall
from server_commands import CommandProcessor
from rendering import (
    render_background, render_players, render_platforms,
    render_chat, render_debug_overlay
)
from debug_bar import DebugBar


def get_server_config_gui():
    """
    Opens a GUI window for server configuration and returns the settings.
    """
    config = {}

    def submit():
        try:
            config['server_name'] = server_name_entry.get()
            config['lobby_name'] = lobby_name_entry.get()
            config['port'] = int(port_entry.get())
            config['password_protected'] = password_var.get()
            config['password'] = password_entry.get() if password_var.get() else ''
            if not config['server_name'] or not config['lobby_name'] or (config['password_protected'] and not config['password']):
                raise ValueError("All fields must be filled out.")
            root.quit()
        except Exception as e:
            messagebox.showerror("Invalid Input", str(e))

    # Create the GUI window
    root = tk.Tk()
    root.title("Server Configuration")

    # Labels and input fields
    tk.Label(root, text="Server Name:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
    server_name_entry = tk.Entry(root)
    server_name_entry.insert(0, "")
    server_name_entry.grid(row=0, column=1, padx=10, pady=5)

    tk.Label(root, text="Lobby Name:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    lobby_name_entry = tk.Entry(root)
    lobby_name_entry.insert(0, "")
    lobby_name_entry.grid(row=1, column=1, padx=10, pady=5)

    tk.Label(root, text="Port:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
    port_entry = tk.Entry(root)
    port_entry.insert(0, str(PORT))
    port_entry.grid(row=2, column=1, padx=10, pady=5)

    password_var = tk.BooleanVar()
    password_var.set(False)
    tk.Checkbutton(root, text="Password Protect", variable=password_var).grid(row=3, column=0, columnspan=2, pady=5)

    tk.Label(root, text="Password:").grid(row=4, column=0, padx=10, pady=5, sticky="e")
    password_entry = tk.Entry(root, show="*")
    password_entry.grid(row=4, column=1, padx=10, pady=5)

    # Submit button
    submit_button = tk.Button(root, text="Start Server", command=submit)
    submit_button.grid(row=5, column=0, columnspan=2, pady=10)

    # Center the window
    root.eval('tk::PlaceWindow . center')

    # Run the GUI event loop
    root.mainloop()
    root.destroy()

    return config


class Server:
    """
    Server class to handle game logic and client connections.
    """

    def __init__(self):
        # Get server configuration from the GUI
        config = get_server_config_gui()
        self.server_name = config['server_name']
        self.lobby_name = config['lobby_name']
        self.port = config['port']
        self.password_protected = config['password_protected']
        self.password = config['password']

        self.players = {}  # {uuid: Player instance}
        self.lock = threading.Lock()
        self.clients = {}  # {conn: uuid}
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen()
        print(f"Server '{self.server_name}' started on port {self.port}, waiting for connections...")

        # Pygame initialization
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT + DEBUG_BAR_HEIGHT))
        pygame.display.set_caption("Server View")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)

        # Platforms
        self.platforms = create_platforms()

        # Initialize CommandProcessor
        self.command_processor = CommandProcessor(self)

        # Initialize DebugBar
        self.debug_bar = DebugBar(self)

        # FPS and player count display toggle
        self.show_fps = False
        self.show_ids = False  # Toggle showing UUIDs

        # Chat messages (for broadcast)
        self.chat_messages = []

        # Set of UUIDs of banned players
        self.banned_players = set()

    def add_debug_message(self, message):
        """
        Add a message to the debug messages list.

        :param message: The message string to add.
        """
        self.debug_bar.add_debug_message(message)

    def accept_clients(self):
        """
        Accept incoming client connections.
        """
        while True:
            conn, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def handle_client(self, conn, addr):
        """
        Handle communication with a connected client.
        """
        print(f"Connected: {addr}")

        # Receive initialization data (uuid, username and hat)
        try:
            data_length_bytes = recvall(conn, 4)
            if not data_length_bytes:
                print("Client disconnected before sending initialization data.")
                conn.close()
                return
            data_length = int.from_bytes(data_length_bytes, byteorder='big')
            data = recvall(conn, data_length)
            init_data = pickle.loads(data)
            client_uuid = init_data.get('uuid')
            username = init_data.get('username', 'Player')
            hat = init_data.get('hat', None)
        except Exception as e:
            print(f"Error receiving initialization data from {addr}: {e}")
            conn.close()
            return

        # Check if the player is banned
        if client_uuid in self.banned_players:
            self.add_debug_message(f"Banned player {username} attempted to connect.")
            # Send a message to the client indicating they are banned
            try:
                ban_message = {"ban": "You are banned from this server."}
                ban_data = pickle.dumps(ban_message)
                conn.sendall(len(ban_data).to_bytes(4, byteorder='big') + ban_data)
            except Exception as e:
                self.add_debug_message(f"Error sending ban message to client: {e}")
            conn.close()
            return

        with self.lock:
            if client_uuid in self.players:
                # Existing player
                player = self.players[client_uuid]
                if player.connected:
                    # There is already a client connected with this UUID
                    # Disconnect the existing client
                    existing_conn = None
                    for c, uuid in self.clients.items():
                        if uuid == client_uuid:
                            existing_conn = c
                            break
                    if existing_conn:
                        self.add_debug_message(f"Client with UUID {client_uuid} is already connected. Disconnecting the existing connection.")
                        existing_conn.close()
                        del self.clients[existing_conn]
                    # Proceed to connect the new client
                    player.connected = True
                    player.username = username
                    player.hat = hat
                    if hat:
                        player.load_hat_image(hat)
                    self.clients[conn] = client_uuid
                    self.add_debug_message(f"Player '{username}' reconnected with UUID {client_uuid}.")
                else:
                    # Player was disconnected, allow reconnection
                    player.connected = True
                    player.username = username
                    player.hat = hat
                    if hat:
                        player.load_hat_image(hat)
                    self.clients[conn] = client_uuid
                    self.add_debug_message(f"Player '{username}' reconnected with UUID {client_uuid}.")
            else:
                # New player
                player = Player(2.0, 10.0, 20, 20, username=username, hat=hat, uuid=client_uuid)
                player.speed = 300.0
                player.is_local_player = False
                self.players[client_uuid] = player
                self.clients[conn] = client_uuid
                self.add_debug_message(f"Player '{username}' connected from {addr} with UUID {client_uuid}.")

        # Send player's position to the client
        try:
            position_data = {
                'position': (player.grid_x, player.grid_y),
                'velocity_x': player.velocity_x,
                'velocity_y': player.velocity_y,
                'hat': player.hat,
                'username': player.username
            }
            serialized_data = pickle.dumps(position_data)
            data_length = len(serialized_data)
            conn.sendall(data_length.to_bytes(4, byteorder='big') + serialized_data)
        except Exception as e:
            print(f"Error sending position data to client: {e}")
            conn.close()
            return

        # Main loop to handle client data
        while True:
            try:
                data_length_bytes = conn.recv(4)
                if not data_length_bytes:
                    break
                data_length = int.from_bytes(data_length_bytes, byteorder='big')
                data = recvall(conn, data_length)
                if not data:
                    break
                client_data = pickle.loads(data)
                position = client_data.get('position')
                if position:
                    with self.lock:
                        player = self.players[self.clients[conn]]
                        if not player.frozen:
                            player.grid_x, player.grid_y = position
                            player.velocity_x = client_data.get('velocity_x', player.velocity_x)
                            player.velocity_y = client_data.get('velocity_y', player.velocity_y)
                            player.rect.x = int(player.grid_x * TILE_SIZE)
                            player.rect.y = int(player.grid_y * TILE_SIZE)
                            # Update gravity_direction
                            player.gravity_direction = client_data.get('gravity_direction', player.gravity_direction)

                self.broadcast_game_state()
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"Unexpected error with {addr}: {e}")
                break

        with self.lock:
            client_uuid = self.clients.get(conn)
            player = self.players.get(client_uuid)
            if player:
                self.add_debug_message(f"Player '{player.username}' disconnected.")
                player.connected = False
            if conn in self.clients:
                del self.clients[conn]
        conn.close()
        print(f"Disconnected: {addr}")

    def broadcast_server_info_multicast(self, server_name, lobby_name, port):
        """
        Broadcast server information to the network using multicast.
        """
        multicast_group = '224.0.0.1'  # Multicast group address
        multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Set TTL (Time-to-Live) to 255 to allow routing across subnets
        multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)

        server_info = {
            'server_name': server_name,
            'lobby_name': lobby_name,
            'port': port
        }

        while True:
            try:
                multicast_socket.sendto(pickle.dumps(server_info), (multicast_group, BROADCAST_PORT))
                print(f"Broadcasting server info: {server_name} at {multicast_group}:{BROADCAST_PORT}")
                time.sleep(BROADCAST_INTERVAL)  # Broadcast interval
            except Exception as e:
                print(f"Error broadcasting server info: {e}")
                break

        multicast_socket.close()

    def broadcast_game_state(self, target_clients=None):
        """
        Send updated game state (players and platforms) to all connected clients or specified clients.

        :param target_clients: Optional list of client sockets to send the game state to.
        """
        with self.lock:
            players_data = {uuid: player.serialize() for uuid, player in self.players.items()}
            platforms_data = [
                {
                    'grid_x': platform.grid_x,
                    'grid_y': platform.grid_y,
                    'width_in_tiles': platform.width_in_tiles,
                    'height_in_tiles': platform.height_in_tiles,
                    'platform_type': platform.platform_type,
                    'active': platform.active  # Include active state
                }
                for platform in self.platforms
            ]
            data = {
                'players': players_data,
                'platforms': platforms_data,
                'chat': self.chat_messages
            }
            serialized_data = pickle.dumps(data)
        data_length = len(serialized_data)
        data_to_send = data_length.to_bytes(4, byteorder='big') + serialized_data
        with self.lock:
            if target_clients is None:
                target_clients = list(self.clients.keys())
            for client in target_clients:
                try:
                    client.sendall(data_to_send)
                except Exception as e:
                    print(f"Error sending game state to client: {e}")
                    self.add_debug_message(f"Error sending game state to client: {e}")
                    client_uuid = self.clients.get(client)
                    client.close()
                    if client in self.clients:
                        del self.clients[client]
                    player = self.players.get(client_uuid)
                    if player:
                        player.connected = False

        # Clear chat messages after sending
        self.chat_messages.clear()

    def update(self, delta_time):
        """
        Update the server-side game state.
        """
        # Update platforms
        for platform in self.platforms:
            platform.update(delta_time)

        # Update players
        with self.lock:
            for player in self.players.values():
                if not player.connected:
                    continue

                # Process interactions with platforms
                self.check_player_platform_collisions(player, delta_time)

    def render_game(self):
        while True:
            delta_time = self.clock.tick(60) / 1000.0  # Convert to seconds

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    self.server_socket.close()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F3:
                        self.show_fps = not self.show_fps
                        self.show_ids = not self.show_ids  # Toggle showing UUIDs
                    else:
                        # Pass event to debug bar for handling
                        self.debug_bar.handle_event(event)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Pass event to debug bar for handling
                    self.debug_bar.handle_event(event)

            # Update game state
            self.update(delta_time)

            # Render the game
            render_background(self.screen)
            render_platforms(self.screen, self.platforms)

            # Render players with IDs and disconnected players
            with self.lock:
                render_players(
                    self.screen,
                    self.players,
                    None,  # local_player is None on the server
                    font=self.font,
                    show_ids=self.show_ids,
                    render_disconnected=True
                )

            # Render chat messages
            render_chat(self.screen, self.font, self.chat_messages)

            # Render debug messages and input
            self.debug_bar.render(self.screen)

            # Render FPS and player count if enabled
            if self.show_fps:
                with self.lock:
                    num_players = len([p for p in self.players.values() if p.connected])
                render_debug_overlay(self.screen, self.font, self.clock, num_players=num_players)

            # Update display
            pygame.display.flip()

    def check_player_platform_collisions(self, player, delta_time):
        for platform in self.platforms:
            if not platform.active:
                continue  # Skip inactive platforms
            if player.rect.colliderect(platform.rect):
                # Process platform effects
                if platform.platform_type == "breakable":
                    if platform.break_timer == 0:
                        platform.break_timer = delta_time
                elif platform.platform_type == "gravity":
                    if player.is_standing_on_platform(platform):
                        player.change_gravity(platform)

    def run(self):
        """
        Start the server and begin accepting clients.
        """
        threading.Thread(target=self.accept_clients, daemon=True).start()
        threading.Thread(target=self.broadcast_server_info_multicast, args=(self.server_name, self.lobby_name, self.port),
                         daemon=True).start()
        print("Server is running.")

        # Start the game rendering loop
        self.render_game()

def get_server_config():
    """
    Prompts the server administrator for configuration parameters.
    """
    print("Welcome to the Game Server Setup!")
    server_name = input("Enter server name (default: 'MyGameServer'): ") or 'MyGameServer'
    lobby_name = input("Enter lobby name (default: 'Default Lobby'): ") or 'Default Lobby'
    port_input = input(f"Enter port (default: {BROADCAST_PORT}): ")
    try:
        port = int(port_input) if port_input else BROADCAST_PORT
    except ValueError:
        print("Invalid port number. Using default.")
        port = BROADCAST_PORT
    password_protected_input = input("Password protect the server? (yes/no, default: no): ").lower() or 'no'
    password_protected = password_protected_input in ['yes', 'y']
    password = ''
    if password_protected:
        password = getpass.getpass("Enter password: ")
    return {
        'server_name': server_name,
        'lobby_name': lobby_name,
        'port': port,
        'password_protected': password_protected,
        'password': password
    }

if __name__ == "__main__":
    server = Server()
    server.run()
