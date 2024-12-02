# rendering.py

import pygame
from constants import (
    COLOR_LIGHT_BLUE, COLOR_GREEN, COLOR_RED, COLOR_BLUE,
    COLOR_WHITE, COLOR_BLACK, SCREEN_WIDTH, SCREEN_HEIGHT, DEBUG_BAR_HEIGHT
)

def wrap_text(text, font, max_width):
    """
    Wrap text to fit within a specified width based on pixel measurements.

    :param text: The text string to wrap.
    :param font: The Pygame font object.
    :param max_width: The maximum width in pixels.
    :return: A list of wrapped lines.
    """
    lines = []
    # Split the text by newline characters
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue
        # Split paragraph into words
        words = paragraph.split(' ')
        current_line = ''
        for word in words:
            test_line = f"{current_line} {word}".strip()
            # Measure the width of the test_line
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                # If adding the new word exceeds max_width, append the current_line and start a new one
                if current_line:
                    lines.append(current_line)
                current_line = word
        # Append the last line in the paragraph
        if current_line:
            lines.append(current_line)
    return lines

def render_background(screen):
    """
    Render the background color.
    """
    screen.fill(COLOR_LIGHT_BLUE)

def render_player(screen, player, is_local_player, camera=None, transparent=False):
    """
    Render a player onto the screen.
    """
    color = COLOR_RED if is_local_player else COLOR_BLUE
    adjusted_rect = camera.apply(player) if camera else player.rect
    if transparent:
        surface = pygame.Surface((player.rect.width, player.rect.height), pygame.SRCALPHA)
        color = (*color[:3], 100)  # Set transparency
        pygame.draw.rect(surface, color, surface.get_rect())
        screen.blit(surface, adjusted_rect.topleft)
    else:
        pygame.draw.rect(screen, color, adjusted_rect)

    # Render the hat if available
    if player.hat_image:
        hat_rect = player.hat_image.get_rect(midbottom=adjusted_rect.center)
        screen.blit(player.hat_image, hat_rect)

def render_player_id(screen, player, font, show_ids=None, camera=None):
    """
    Render the player's username and ID above their head.
    """
    adjusted_rect = camera.apply(player) if camera else player.rect
    if player.username:
        if show_ids and player.uuid:
            id_text = font.render(f"{player.username}:{player.uuid}", True, COLOR_BLACK)
        else:
            id_text = font.render(f"{player.username}", True, COLOR_BLACK)
        text_rect = id_text.get_rect(center=(adjusted_rect.centerx, adjusted_rect.top - 20))
        screen.blit(id_text, text_rect)

def render_players(screen, players_dict, local_player, font=None, show_ids=None, render_disconnected=False, camera=None):
    """
    Render all players onto the screen.
    """
    local_player_uuid = local_player.uuid if local_player else None
    if local_player is not None:
        render_player(screen, local_player, True, camera)
        render_player_id(screen, local_player, font, show_ids=show_ids, camera=camera)
    for uuid, player in players_dict.items():
        if local_player_uuid and uuid == local_player_uuid:
            continue  # Skip rendering the local player again
        if not render_disconnected and not player.connected:
            continue
        render_player(screen, player, False, camera, transparent=not player.connected)
        render_player_id(screen, player, font, show_ids=show_ids, camera=camera)

def render_platforms(screen, platforms, camera=None):
    """
    Render all platforms onto the screen, optimizing by grouping adjacent tiles of the same type.
    """
    # Group platforms by type and position
    platform_groups = {}
    for platform in platforms:
        if not platform.active:
            continue
        key = platform.platform_type
        if key not in platform_groups:
            platform_groups[key] = []
        platform_groups[key].append(platform)

    for platform_type, platform_list in platform_groups.items():
        # Get the color for the platform type
        color = get_platform_color(platform_type)

        for platform in platform_list:
            # Adjust the platform's rectangle based on the camera
            adjusted_rect = camera.apply_rect(platform.rect) if camera else platform.rect
            pygame.draw.rect(screen, color, adjusted_rect)

def get_platform_color(platform_type):
    """
    Return the color associated with a platform type.
    """
    if platform_type == "normal":
        return COLOR_GREEN
    elif platform_type == "breakable":
        return (139, 69, 19)  # Brown color
    elif platform_type == "gravity":
        return COLOR_BLUE
    elif platform_type == "deadly":
        return (255, 0, 0)
    else:
        return COLOR_GREEN  # Default color for unknown types

def render_chat(screen, font, chat_messages):
    """
    Render chat messages onto the screen.
    """
    y_offset = SCREEN_HEIGHT - 100  # Adjust as needed
    for message in chat_messages[-5:]:  # Show last 5 messages
        chat_surface = font.render(message, True, COLOR_WHITE)
        screen.blit(chat_surface, (10, y_offset))
        y_offset += 20

def render_debug_overlay(screen, font, clock, num_players=None):
    """
    Render the debug overlay (FPS and optionally player count).
    """
    fps = clock.get_fps()
    fps_text = font.render(f"FPS: {int(fps)}", True, COLOR_WHITE)
    screen.blit(fps_text, (10, 10))

    if num_players is not None:
        players_text = font.render(f"Players: {num_players}", True, COLOR_WHITE)
        screen.blit(players_text, (10, 30))

def render_debug_bar(screen, font, input_text, command_history, debug_messages, scroll_offset, cursor_position, selection_start=None, selection_end=None):
    """
    Render the debug bar for the server, including input text and debug messages.

    :param screen: The Pygame screen surface.
    :param font: The Pygame font object.
    :param input_text: The current input text from the server operator.
    :param command_history: List of past commands entered.
    :param debug_messages: List of debug messages to display.
    :param scroll_offset: The current scroll offset for debug messages.
    :param cursor_position: The current cursor position in the input text.
    :param selection_start: The start index of the text selection.
    :param selection_end: The end index of the text selection.
    """
    # Draw the debug bar background
    pygame.draw.rect(
        screen,
        (50, 50, 50),
        pygame.Rect(0, SCREEN_HEIGHT, SCREEN_WIDTH, DEBUG_BAR_HEIGHT)
    )

    # Define areas within the debug bar
    input_box = pygame.Rect(10, SCREEN_HEIGHT + 10, SCREEN_WIDTH - 20, 30)
    pygame.draw.rect(screen, COLOR_WHITE, input_box)

    # Render the input text with selection
    if selection_start is not None and selection_end is not None and selection_start != selection_end:
        # Ensure selection indices are in order
        sel_start = min(selection_start, selection_end)
        sel_end = max(selection_start, selection_end)
        # Render text before selection
        before_sel = input_text[:sel_start]
        before_surface = font.render(before_sel, True, COLOR_BLACK)
        screen.blit(before_surface, (input_box.x + 5, input_box.y + 5))
        x_offset = input_box.x + 5 + before_surface.get_width()
        # Render selected text with highlight
        selected_text = input_text[sel_start:sel_end]
        selected_surface = font.render(selected_text, True, COLOR_BLACK)
        # Create a rectangle for the selection highlight
        selection_rect = pygame.Rect(x_offset, input_box.y + 5, selected_surface.get_width(), font.get_height())
        pygame.draw.rect(screen, (173, 216, 230), selection_rect)  # Light blue highlight
        screen.blit(selected_surface, (x_offset, input_box.y + 5))
        x_offset += selected_surface.get_width()
        # Render text after selection
        after_sel = input_text[sel_end:]
        after_surface = font.render(after_sel, True, COLOR_BLACK)
        screen.blit(after_surface, (x_offset, input_box.y + 5))
    else:
        # No selection, render the whole text
        txt_surface = font.render(input_text, True, COLOR_BLACK)
        screen.blit(txt_surface, (input_box.x + 5, input_box.y + 5))

    # Calculate cursor x-position
    cursor_x = input_box.x + 5 + font.size(input_text[:cursor_position])[0]
    cursor_y = input_box.y + 5

    # Draw the text cursor
    cursor_visible = (pygame.time.get_ticks() // 500) % 2 == 0  # Blink every 500ms
    if cursor_visible:
        cursor_rect = pygame.Rect(cursor_x, cursor_y, 2, font.get_height())
        pygame.draw.rect(screen, COLOR_BLACK, cursor_rect)

    # Render debug messages above the input box
    # Define the area for debug messages
    debug_area = pygame.Rect(10, SCREEN_HEIGHT + 50, SCREEN_WIDTH - 20, DEBUG_BAR_HEIGHT - 60)
    # Clip the drawing to the debug_area
    screen.set_clip(debug_area)

    # Calculate total message height considering wrapped lines
    line_height = font.get_height() + 2
    total_lines = 0
    for message in debug_messages[-100:]:
        wrapped_lines = wrap_text(message, font, debug_area.width)
        total_lines += len(wrapped_lines)

    total_message_height = total_lines * line_height
    max_scroll = max(0, total_message_height - debug_area.height)
    scroll_offset = min(scroll_offset, max_scroll)
    scroll_offset = max(0, scroll_offset)

    # Calculate the starting y position based on scroll_offset
    y_start = debug_area.y + 5 - scroll_offset

    # Iterate through debug_messages and handle newlines and wrapping
    for message in debug_messages[-100:]:
        wrapped_lines = wrap_text(message, font, debug_area.width)
        for line in wrapped_lines:
            message_surface = font.render(line, True, COLOR_WHITE)
            screen.blit(message_surface, (debug_area.x, y_start))
            y_start += line_height
            # Check if we've exceeded the debug_area's height
            if y_start > debug_area.bottom:
                break  # Stop rendering further messages
        if y_start > debug_area.bottom:
            break  # Stop rendering further messages

    # Remove clipping
    screen.set_clip(None)

    # Draw scroll indicators if necessary
    if scroll_offset > 0:
        arrow_surface = font.render("^", True, COLOR_WHITE)
        screen.blit(arrow_surface, (debug_area.right - 20, debug_area.y + 5))
    if scroll_offset < max_scroll:
        arrow_surface = font.render("v", True, COLOR_WHITE)
        screen.blit(arrow_surface, (debug_area.right - 20, debug_area.bottom - 25))
