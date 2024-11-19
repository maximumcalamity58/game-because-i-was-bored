# debug_bar.py

import pygame
from constants import SCREEN_WIDTH, DEBUG_BAR_HEIGHT
from rendering import wrap_text
from server_commands import CommandProcessor

class DebugBar:
    def __init__(self, server):
        self.server = server
        self.font = server.font
        self.input_text = ''
        self.command_history = []
        self.command_history_offset = 0
        self.debug_messages = []
        self.debug_scroll_offset = 0

        # Text cursor position
        self.cursor_position = 0
        self.selection_start = None  # Start index of text selection
        self.selection_end = None    # End index of text selection

        # Tab completion variables
        self.autocomplete_options = []
        self.autocomplete_index = -1

    def add_debug_message(self, message):
        """
        Add a message to the debug messages list.

        :param message: The message string to add.
        """
        self.debug_messages.append(message)
        # Limit the number of debug messages to prevent overflow
        if len(self.debug_messages) > 100:
            self.debug_messages.pop(0)

        # Adjust scroll offset to show the latest messages
        line_height = self.font.get_height() + 2
        total_lines = 0
        for msg in self.debug_messages:
            wrapped = wrap_text(msg, self.font, SCREEN_WIDTH - 20)
            total_lines += len(wrapped)
        total_message_height = total_lines * line_height
        debug_area_height = DEBUG_BAR_HEIGHT - 60
        max_scroll = max(0, total_message_height - debug_area_height)
        self.debug_scroll_offset = max_scroll

    def handle_event(self, event):
        """
        Handle Pygame events for the debug bar.

        :param event: The Pygame event to handle.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Process the command and clear input
                self.server.command_processor.process_command(self.input_text)
                self.add_debug_message(f"> {self.input_text}")  # Echo the command
                self.command_history.append(self.input_text)
                self.input_text = ''
                self.command_history_offset = len(self.command_history)
                self.cursor_position = 0
                self.selection_start = None
                self.selection_end = None
                # Reset autocomplete
                self.autocomplete_options = []
                self.autocomplete_index = -1
            elif event.key == pygame.K_TAB:
                # Handle Tab autocompletion
                self.handle_autocomplete()
            else:
                # Reset autocomplete on any other key press
                self.autocomplete_options = []
                self.autocomplete_index = -1

                # Handle other key presses
                self.handle_key_press(event)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = pygame.mouse.get_pos()
                with self.server.lock:
                    for player in self.server.players.values():
                        if player.rect.collidepoint(mouse_pos):
                            if self.input_text and not self.input_text.endswith(' '):
                                self.input_text += ' '
                            self.input_text += player.uuid
                            self.cursor_position = len(self.input_text)
                            self.selection_start = None
                            self.selection_end = None
                            self.add_debug_message(f"Selected player {player.username} (UUID: {player.uuid})")
                            break
            elif event.button == 4:  # Scroll up
                self.debug_scroll_offset = max(0, self.debug_scroll_offset - 20)
            elif event.button == 5:  # Scroll down
                line_height = self.font.get_height() + 2
                total_lines = 0
                for message in self.debug_messages:
                    wrapped_lines = wrap_text(message, self.font, SCREEN_WIDTH - 20)
                    total_lines += len(wrapped_lines)
                total_message_height = total_lines * line_height
                debug_area_height = DEBUG_BAR_HEIGHT - 60
                max_scroll = max(0, total_message_height - debug_area_height)
                self.debug_scroll_offset = min(max_scroll, self.debug_scroll_offset + 20)

    def handle_key_press(self, event):
        """
        Handle key presses for text input and navigation.

        :param event: The Pygame KEYDOWN event.
        """
        if event.key == pygame.K_BACKSPACE:
            if self.selection_start is not None and self.selection_end is not None:
                # Delete selected text
                sel_start = min(self.selection_start, self.selection_end)
                sel_end = max(self.selection_start, self.selection_end)
                self.input_text = self.input_text[:sel_start] + self.input_text[sel_end:]
                self.cursor_position = sel_start
                self.selection_start = None
                self.selection_end = None
            elif event.mod & pygame.KMOD_CTRL:
                # Ctrl+Backspace: Delete word before cursor
                if self.cursor_position > 0:
                    # Find the position of the previous space
                    prev_space = self.input_text.rfind(' ', 0, self.cursor_position - 1)
                    if prev_space == -1:
                        # No space found, delete from start
                        self.input_text = self.input_text[self.cursor_position:]
                        self.cursor_position = 0
                    else:
                        # Delete from prev_space+1 to cursor_position
                        self.input_text = self.input_text[:prev_space + 1] + self.input_text[self.cursor_position:]
                        self.cursor_position = prev_space + 1
            else:
                if self.cursor_position > 0:
                    self.input_text = self.input_text[:self.cursor_position - 1] + self.input_text[self.cursor_position:]
                    self.cursor_position -= 1
            # Clear selection
            self.selection_start = None
            self.selection_end = None
        elif event.key == pygame.K_DELETE:
            if self.selection_start is not None and self.selection_end is not None:
                # Delete selected text
                sel_start = min(self.selection_start, self.selection_end)
                sel_end = max(self.selection_start, self.selection_end)
                self.input_text = self.input_text[:sel_start] + self.input_text[sel_end:]
                self.cursor_position = sel_start
                self.selection_start = None
                self.selection_end = None
            elif event.mod & pygame.KMOD_CTRL:
                # Ctrl+Delete: Delete word after cursor
                next_space = self.input_text.find(' ', self.cursor_position)
                if next_space == -1:
                    # No space found, delete to end
                    self.input_text = self.input_text[:self.cursor_position]
                else:
                    # Delete from cursor_position to next_space
                    self.input_text = self.input_text[:self.cursor_position] + self.input_text[next_space + 1:]
            else:
                if self.cursor_position < len(self.input_text):
                    self.input_text = self.input_text[:self.cursor_position] + self.input_text[self.cursor_position + 1:]
            # Clear selection
            self.selection_start = None
            self.selection_end = None
        elif event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
            # Ctrl+A: Select all text
            self.selection_start = 0
            self.selection_end = len(self.input_text)
            self.cursor_position = len(self.input_text)
        elif event.key == pygame.K_LEFT:
            if event.mod & pygame.KMOD_CTRL:
                # Ctrl+Left: Move cursor to the start of the previous word
                if self.cursor_position > 0:
                    # Move back to the previous non-space character
                    pos = self.cursor_position - 1
                    while pos > 0 and self.input_text[pos] == ' ':
                        pos -= 1
                    # Move back to the start of the word
                    while pos > 0 and self.input_text[pos - 1] != ' ':
                        pos -= 1
                    self.cursor_position = pos
            else:
                if self.cursor_position > 0:
                    self.cursor_position -= 1
            if event.mod & pygame.KMOD_SHIFT:
                # Update selection
                if self.selection_start is None:
                    self.selection_start = self.cursor_position + 1
                self.selection_end = self.cursor_position
            else:
                # Clear selection
                self.selection_start = None
                self.selection_end = None
        elif event.key == pygame.K_RIGHT:
            if event.mod & pygame.KMOD_CTRL:
                # Ctrl+Right: Move cursor to the start of the next word
                if self.cursor_position < len(self.input_text):
                    # Move forward to the next non-space character
                    pos = self.cursor_position
                    while pos < len(self.input_text) and self.input_text[pos] == ' ':
                        pos += 1
                    # Move forward to the end of the word
                    while pos < len(self.input_text) and self.input_text[pos] != ' ':
                        pos += 1
                    self.cursor_position = pos
            else:
                if self.cursor_position < len(self.input_text):
                    self.cursor_position += 1
            if event.mod & pygame.KMOD_SHIFT:
                # Update selection
                if self.selection_start is None:
                    self.selection_start = self.cursor_position - 1
                self.selection_end = self.cursor_position
            else:
                # Clear selection
                self.selection_start = None
                self.selection_end = None
        elif event.key == pygame.K_HOME:
            self.cursor_position = 0
            if event.mod & pygame.KMOD_SHIFT:
                # Update selection
                if self.selection_start is None:
                    self.selection_start = len(self.input_text)
                self.selection_end = self.cursor_position
            else:
                # Clear selection
                self.selection_start = None
                self.selection_end = None
        elif event.key == pygame.K_END:
            self.cursor_position = len(self.input_text)
            if event.mod & pygame.KMOD_SHIFT:
                # Update selection
                if self.selection_start is None:
                    self.selection_start = 0
                self.selection_end = self.cursor_position
            else:
                # Clear selection
                self.selection_start = None
                self.selection_end = None
        elif event.key == pygame.K_UP:
            # Navigate up in command history
            if self.command_history and self.command_history_offset > 0:
                self.command_history_offset -= 1
                self.input_text = self.command_history[self.command_history_offset]
                self.cursor_position = len(self.input_text)
                self.selection_start = None
                self.selection_end = None
        elif event.key == pygame.K_DOWN:
            # Navigate down in command history
            if self.command_history and self.command_history_offset < len(self.command_history) - 1:
                self.command_history_offset += 1
                self.input_text = self.command_history[self.command_history_offset]
                self.cursor_position = len(self.input_text)
                self.selection_start = None
                self.selection_end = None
            else:
                self.command_history_offset = len(self.command_history)
                self.input_text = ''
                self.cursor_position = 0
                self.selection_start = None
                self.selection_end = None
        elif event.key == pygame.K_PAGEUP:
            # Scroll up in debug messages
            self.debug_scroll_offset = max(0, self.debug_scroll_offset - 20)
        elif event.key == pygame.K_PAGEDOWN:
            # Scroll down in debug messages
            line_height = self.font.get_height() + 2
            total_lines = 0
            for message in self.debug_messages:
                wrapped_lines = wrap_text(message, self.font, SCREEN_WIDTH - 20)
                total_lines += len(wrapped_lines)
            total_message_height = total_lines * line_height
            debug_area_height = DEBUG_BAR_HEIGHT - 60
            max_scroll = max(0, total_message_height - debug_area_height)
            self.debug_scroll_offset = min(max_scroll, self.debug_scroll_offset + 20)
        else:
            # Handle printable character inputs
            if event.unicode and not event.mod & pygame.KMOD_CTRL:
                if self.selection_start is not None and self.selection_end is not None:
                    # Replace selected text
                    sel_start = min(self.selection_start, self.selection_end)
                    sel_end = max(self.selection_start, self.selection_end)
                    self.input_text = self.input_text[:sel_start] + event.unicode + self.input_text[sel_end:]
                    self.cursor_position = sel_start + len(event.unicode)
                    self.selection_start = None
                    self.selection_end = None
                else:
                    self.input_text = self.input_text[:self.cursor_position] + event.unicode + self.input_text[self.cursor_position:]
                    self.cursor_position += len(event.unicode)
                # Clear selection
                self.selection_start = None
                self.selection_end = None

    def handle_autocomplete(self):
        """
        Handle tab autocompletion in the command input box.
        """
        # Get the current input text up to the cursor position
        current_text = self.input_text[:self.cursor_position]

        # If we don't have autocomplete options yet, generate them
        if not self.autocomplete_options:
            # Split the input text to get the last word (partial command)
            parts = current_text.split()
            if parts:
                partial_command = parts[-1]
                # Get all possible commands from the CommandProcessor
                available_commands = self.server.command_processor.get_commands()
                # Filter commands that start with the partial_command
                self.autocomplete_options = [cmd for cmd in available_commands if cmd.startswith(partial_command)]
                self.autocomplete_index = 0
                if self.autocomplete_options:
                    # Replace the partial command with the first autocomplete option
                    parts[-1] = self.autocomplete_options[self.autocomplete_index]
                    new_text = ' '.join(parts)
                    self.input_text = new_text + self.input_text[self.cursor_position:]
                    self.cursor_position = len(new_text)
            else:
                # If no partial command, list all commands
                self.autocomplete_options = self.server.command_processor.get_commands()
                self.autocomplete_index = 0
                if self.autocomplete_options:
                    self.input_text = self.autocomplete_options[self.autocomplete_index] + self.input_text[self.cursor_position:]
                    self.cursor_position = len(self.autocomplete_options[self.autocomplete_index])
        else:
            # Cycle through autocomplete options
            self.autocomplete_index = (self.autocomplete_index + 1) % len(self.autocomplete_options)
            parts = self.input_text[:self.cursor_position].split()
            if parts:
                # Replace the last word with the new option
                parts[-1] = self.autocomplete_options[self.autocomplete_index]
                new_text = ' '.join(parts)
                self.input_text = new_text + self.input_text[self.cursor_position:]
                self.cursor_position = len(new_text)
            else:
                # No existing text, insert the new option
                self.input_text = self.autocomplete_options[self.autocomplete_index] + self.input_text[self.cursor_position:]
                self.cursor_position = len(self.autocomplete_options[self.autocomplete_index])

    def render(self, screen):
        """
        Render the debug bar and messages.

        :param screen: The Pygame screen surface to render on.
        """
        # Render debug messages and input
        from rendering import render_debug_bar  # Import here to avoid circular imports
        render_debug_bar(
            screen,
            self.font,
            self.input_text,
            self.command_history,
            self.debug_messages,
            self.debug_scroll_offset,
            self.cursor_position,  # Pass the cursor position
            self.selection_start,
            self.selection_end
        )
