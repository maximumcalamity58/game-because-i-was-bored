# server_commands.py

import pickle  # Ensure pickle is imported for serialization
from constants import TILE_SIZE
from platforms import Platforms

class CommandProcessor:
    """
    Class to process server commands entered via the debug bar.
    """

    def __init__(self, server):
        self.server = server  # Reference to the Server instance
        # Define available commands
        self.commands = {
            'teleport': self.teleport_player,
            'setpos': self.teleport_player,
            'add': self.add_position,
            'kick': self.kick_player,
            'ban': self.ban_player,
            'unban': self.unban_player,
            'broadcast': self.broadcast_message,
            'set_speed': self.set_speed,
            'freeze': self.freeze_player,
            'unfreeze': self.unfreeze_player,
            'list': self.list_players,
            'make_platform': self.make_platform,
            'smite': self.smite_player,
            'launch': self.launch_player,
            'give_hat': self.give_hat,
            'change_gravity': self.change_gravity,
            'help': self.show_help,
        }

    def process_command(self, command_string):
        """
        Process a command entered by the server operator.
        """
        tokens = command_string.strip().split()
        if not tokens:
            return

        cmd = tokens[0].lower()
        args = tokens[1:]

        if cmd in self.commands:
            try:
                self.commands[cmd](args)
            except Exception as e:
                self.server.add_debug_message(f"Error executing command '{cmd}': {e}")
        else:
            self.server.add_debug_message(f"Unknown command: {cmd}. Type 'help' for a list of commands.")

    def get_commands(self):
        """
        Return a list of available command names.
        """
        return list(self.commands.keys())

    def get_player_by_identifier(self, identifier):
        """
        Retrieve a player by username or UUID.
        """
        with self.server.lock:
            # First, try to find by UUID
            if identifier in self.server.players:
                return self.server.players[identifier]
            # Then, try to find by username
            for player in self.server.players.values():
                if player.username == identifier:
                    return player
        return None

    def teleport_player(self, args):
        if len(args) != 3:
            self.server.add_debug_message("Usage: teleport [username/uuid] [x] [y]")
            return
        identifier = args[0]
        try:
            x = float(args[1])
            y = float(args[2])
        except ValueError:
            self.server.add_debug_message("Error: x and y must be numbers.")
            return
        player = self.get_player_by_identifier(identifier)
        if player:
            with self.server.lock:
                player.grid_x = x
                player.grid_y = y
                player.rect.x = int(x * TILE_SIZE)
                player.rect.y = int(y * TILE_SIZE)
            self.server.add_debug_message(f"Teleported {player.username} to ({x}, {y}).")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def add_position(self, args):
        if len(args) != 3:
            self.server.add_debug_message("Usage: add [username/uuid] [dx] [dy]")
            return
        identifier = args[0]
        try:
            dx = float(args[1])
            dy = float(args[2])
        except ValueError:
            self.server.add_debug_message("Invalid arguments. dx and dy must be numbers.")
            return
        player = self.get_player_by_identifier(identifier)
        if player:
            with self.server.lock:
                player.grid_x += dx
                player.grid_y += dy
                player.rect.x = int(player.grid_x * TILE_SIZE)
                player.rect.y = int(player.grid_y * TILE_SIZE)
            self.server.add_debug_message(f"Moved player {player.username} by ({dx}, {dy}). New position: ({player.grid_x}, {player.grid_y}).")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def kick_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: kick [username/uuid]")
            return
        identifier = args[0]
        player = self.get_player_by_identifier(identifier)
        if player:
            with self.server.lock:
                for conn, uuid in list(self.server.clients.items()):
                    if uuid == player.uuid:
                        try:
                            kick_message = {"kick": "You have been kicked from the server."}
                            kick_data = pickle.dumps(kick_message)
                            conn.sendall(len(kick_data).to_bytes(4, byteorder='big') + kick_data)
                        except Exception as e:
                            self.server.add_debug_message(f"Error sending kick message to client: {e}")
                        conn.close()
                        del self.server.clients[conn]
                        break
                player.connected = False
            self.server.add_debug_message(f"Kicked player {player.username}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def ban_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: ban [username/uuid]")
            return
        identifier = args[0]
        player = self.get_player_by_identifier(identifier)
        if player:
            # Add player UUID to banned_players set
            self.server.banned_players.add(player.uuid)
            # Kick the player if they are connected
            with self.server.lock:
                for conn, uuid in list(self.server.clients.items()):
                    if uuid == player.uuid:
                        try:
                            ban_message = {"ban": "You have been banned from the server."}
                            ban_data = pickle.dumps(ban_message)
                            conn.sendall(len(ban_data).to_bytes(4, byteorder='big') + ban_data)
                        except Exception as e:
                            self.server.add_debug_message(f"Error sending ban message to client: {e}")
                        conn.close()
                        del self.server.clients[conn]
                        break
                player.connected = False
            self.server.add_debug_message(f"Banned player {player.username}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def unban_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: unban [username/uuid]")
            return
        identifier = args[0]
        # Try to find the player to get the UUID
        player = self.get_player_by_identifier(identifier)
        uuid_to_unban = player.uuid if player else identifier
        if uuid_to_unban in self.server.banned_players:
            self.server.banned_players.remove(uuid_to_unban)
            self.server.add_debug_message(f"Unbanned player with UUID {uuid_to_unban}.")
        else:
            self.server.add_debug_message(f"No banned player found with identifier '{identifier}'.")

    def broadcast_message(self, args):
        if not args:
            self.server.add_debug_message("Usage: broadcast [message]")
            return
        message = ' '.join(args)
        self.server.chat_messages.append(("Server", message))
        self.server.add_debug_message(f"Broadcasted message: {message}")
        self.server.broadcast_game_state()

    def set_speed(self, args):
        if len(args) != 2:
            self.server.add_debug_message("Usage: set_speed [username/uuid] [speed]")
            return
        identifier = args[0]
        try:
            speed = float(args[1])
        except ValueError:
            self.server.add_debug_message("Error: speed must be a number.")
            return
        player = self.get_player_by_identifier(identifier)
        if player:
            player.speed = speed
            self.server.add_debug_message(f"Set speed of {player.username} to {speed}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def freeze_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: freeze [username/uuid]")
            return
        identifier = args[0]
        player = self.get_player_by_identifier(identifier)
        if player:
            player.frozen = True
            self.server.add_debug_message(f"Froze player {player.username}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def unfreeze_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: unfreeze [username/uuid]")
            return
        identifier = args[0]
        player = self.get_player_by_identifier(identifier)
        if player:
            player.frozen = False
            self.server.add_debug_message(f"Unfroze player {player.username}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def list_players(self, args):
        with self.server.lock:
            if not self.server.players:
                self.server.add_debug_message("No players are currently connected.")
            else:
                message = "Players:"
                for player in self.server.players.values():
                    status = "Connected" if player.connected else "Disconnected"
                    message += f"\nUUID: {player.uuid}, Username: {player.username}, Position: ({player.grid_x}, {player.grid_y}), Status: {status}"
                self.server.add_debug_message(message)

    def make_platform(self, args):
        if len(args) < 4 or len(args) > 5:
            self.server.add_debug_message("Usage: make_platform [x] [y] [width_in_tiles] [height_in_tiles] [platform_type]")
            return
        try:
            x = float(args[0])
            y = float(args[1])
            width_in_tiles = int(args[2])
            height_in_tiles = int(args[3])
            platform_type = args[4] if len(args) == 5 else "normal"
        except ValueError:
            self.server.add_debug_message("Error: x and y must be numbers. width_in_tiles and height_in_tiles must be integers.")
            return
        # Create a new platform
        new_platform = Platforms(
            grid_x=x,
            grid_y=y,
            width_in_tiles=width_in_tiles,
            height_in_tiles=height_in_tiles,
            platform_type=platform_type
        )
        with self.server.lock:
            self.server.platforms.append(new_platform)
        self.server.add_debug_message(f"Created new platform of type '{platform_type}' at ({x}, {y}) with size ({width_in_tiles}x{height_in_tiles}).")
        self.server.broadcast_game_state()

    def smite_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: smite [username/uuid]")
            return
        identifier = args[0]
        player = self.get_player_by_identifier(identifier)
        if player:
            # Simulate smiting by setting a high downward velocity
            player.velocity_y = 1000  # Arbitrary large value
            self.server.add_debug_message(f"Smote player {player.username}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def launch_player(self, args):
        if len(args) != 1:
            self.server.add_debug_message("Usage: launch [username/uuid]")
            return
        identifier = args[0]
        player = self.get_player_by_identifier(identifier)
        if player:
            # Move the player up slightly
            player.grid_y -= 0.5
            player.rect.y = int(player.grid_y * TILE_SIZE)
            # Launch the player upwards
            player.velocity_y = -1000  # Negative value to simulate upward force
            self.server.add_debug_message(f"Launched player {player.username} into the air.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def give_hat(self, args):
        if len(args) != 2:
            self.server.add_debug_message("Usage: give_hat [username/uuid] [hat_name]")
            return
        identifier = args[0]
        hat_name = args[1]
        player = self.get_player_by_identifier(identifier)
        if player:
            player.hat = hat_name
            player.load_hat_image(hat_name)
            self.server.add_debug_message(f"Gave hat '{hat_name}' to player {player.username}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def change_gravity(self, args):
        if len(args) != 2:
            self.server.add_debug_message("Usage: change_gravity [username/uuid] [direction]")
            return
        identifier = args[0]
        direction = args[1].lower()
        if direction not in ("up", "down", "left", "right"):
            self.server.add_debug_message("Error: direction must be one of 'up', 'down', 'left', 'right'.")
            return
        player = self.get_player_by_identifier(identifier)
        if player:
            player.gravity_direction = direction
            self.server.add_debug_message(f"Changed gravity for {player.username} to {direction}.")
            self.server.broadcast_game_state()
        else:
            self.server.add_debug_message(f"No player found with identifier '{identifier}'.")

    def show_help(self, args):
        help_message = (
            "Available commands:\n"
            "teleport [username/uuid] [x] [y] - Teleport a player to specified coordinates.\n"
            "add [username/uuid] [dx] [dy] - Add to a player's current position.\n"
            "kick [username/uuid] - Kick a player from the server.\n"
            "ban [username/uuid] - Ban a player from the server.\n"
            "unban [username/uuid] - Unban a player.\n"
            "broadcast [message] - Send a message to all players.\n"
            "set_speed [username/uuid] [speed] - Set the movement speed of a player.\n"
            "freeze [username/uuid] - Freeze a player.\n"
            "unfreeze [username/uuid] - Unfreeze a player.\n"
            "list - List all connected players.\n"
            "make_platform [x] [y] [width_in_tiles] [height_in_tiles] [platform_type] - Create a new platform of specified type.\n"
            "smite [username/uuid] - Strike a player with lightning.\n"
            "launch [username/uuid] - Launch a player into the air.\n"
            "give_hat [username/uuid] [hat_name] - Give a hat to a player.\n"
            "change_gravity [username/uuid] [direction] - Change the gravity direction for a player.\n"
            "help - Show this help message."
        )
        self.server.add_debug_message(help_message)
