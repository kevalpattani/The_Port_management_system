import pygame
import sys
import datetime
import random
import json
import requests # Import the requests library for API calls
import math # Import math for circular positioning
import time # For message polling timer
import collections # For deque

# --- Pygame Initialization ---
pygame.init()

# --- Constants ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
DARK_GREEN = (0, 120, 0)
LIGHT_GREEN = (0, 200, 0)
GREEN = (0, 255, 0) # Added GREEN
BLUE = (0, 0, 200)
LIGHT_GREY = (200, 200, 200)
DARK_GREY = (100, 100, 100)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)

# Port dimensions and positions
PORT_WIDTH = 300
PORT_HEIGHT = 280 # Adjusted for 7 terminals
TERMINAL_COUNT = 7
TERMINAL_HEIGHT = PORT_HEIGHT // TERMINAL_COUNT

# Control Panel (left side)
CONTROL_PANEL_X = 20
CONTROL_PANEL_Y = 20
CONTROL_PANEL_WIDTH = 280
CONTROL_PANEL_HEIGHT = SCREEN_HEIGHT - 40 # Almost full height

# Main Ocean/Simulation Area
OCEAN_START_X = CONTROL_PANEL_X + CONTROL_PANEL_WIDTH + 10 # Ocean starts right of control panel
OCEAN_WIDTH = SCREEN_WIDTH - OCEAN_START_X
OCEAN_HEIGHT = SCREEN_HEIGHT

# Center the port within the new ocean area
PORT_X = OCEAN_START_X + (OCEAN_WIDTH // 2) - (PORT_WIDTH // 2)
PORT_Y = SCREEN_HEIGHT // 2 - PORT_HEIGHT // 2

# Zone distances (from port's closest edge)
RED_ZONE_DIST_PX = 100
DARK_GREEN_ZONE_DIST_PX = 250
LIGHT_GREEN_ZONE_DIST_PX = 400

# Delete Zone (top-right corner of the *entire screen*)
DELETE_ZONE_RECT = pygame.Rect(SCREEN_WIDTH - 200, 0, 200, 100)

# --- API Configuration ---
# IMPORTANT: Replace this with the actual URL of your FastAPI server
# If running locally on the same machine: http://127.0.0.1:8000
# If running on a different machine on your local Wi-Fi (e.g., 172.16.3.228): http://172.16.3.228:8000
BASE_API_URL = "http://127.0.0.1:8000"
LOG_EVENT_API_URL = f"{BASE_API_URL}/log_event"
GET_MESSAGES_API_URL = f"{BASE_API_URL}/get_messages_for_pygame"

# --- Game Setup ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Advanced Port Simulation")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 24)
large_font = pygame.font.Font(None, 32)
title_font = pygame.font.Font(None, 48)

# --- Helper Functions ---
def interpolate_color(color1, color2, factor):
    """Interpolates between two RGB colors. Factor from 0.0 (color1) to 1.0 (color2)."""
    r = int(color1[0] + (color2[0] - color1[0]) * factor)
    g = int(color1[1] + (color2[1] - color1[1]) * factor)
    b = int(color1[2] + (color2[2] - color1[2]) * factor)
    return (r, g, b)

# Define a buffer zone around the port to ensure "open sea" is truly outside all gradient zones
OPEN_SEA_BUFFER = 50 # pixels beyond the light green zone
# These now refer to the actual ocean area bounds
MIN_OPEN_SEA_X = OCEAN_START_X + 50
MAX_OPEN_SEA_X = SCREEN_WIDTH - 50
MIN_OPEN_SEA_Y = 0 + 50
MAX_OPEN_SEA_Y = SCREEN_HEIGHT - 50

# Assuming a generic ship size for spawning, or pass it in
SHIP_WIDTH_FOR_SPAWN = 60
SHIP_HEIGHT_FOR_SPAWN = 30

def get_random_open_sea_position():
    """Returns a random (x, y) coordinate for a ship to be entirely within open sea."""
    while True:
        # Choose a random point within the ocean area bounds, with some margin for the ship size
        x = random.randint(MIN_OPEN_SEA_X, MAX_OPEN_SEA_X - SHIP_WIDTH_FOR_SPAWN)
        y = random.randint(MIN_OPEN_SEA_Y, MAX_OPEN_SEA_Y - SHIP_HEIGHT_FOR_SPAWN)
        
        # Calculate distance from the potential spawn point to the port center
        port_center_x = PORT_X + PORT_WIDTH // 2
        port_center_y = PORT_Y + PORT_HEIGHT // 2
        
        # Calculate distance from the *center* of the potential ship position to the port center
        ship_center_x = x + SHIP_WIDTH_FOR_SPAWN // 2
        ship_center_y = y + SHIP_HEIGHT_FOR_SPAWN // 2
        dist_to_port_center = ((ship_center_x - port_center_x)**2 + (ship_center_y - port_center_y)**2)**0.5

        # Ensure the point is outside the light green zone + buffer
        if dist_to_port_center > LIGHT_GREEN_ZONE_DIST_PX + OPEN_SEA_BUFFER:
            return x, y

# --- UI Element Classes ---

class Button:
    def __init__(self, x, y, width, height, text, color, hover_color, text_color=BLACK, action=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.action = action
        self.is_hovered = False

    def draw(self, surface):
        current_color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, current_color, self.rect, border_radius=5)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=5) # Border
        text_surface = font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered and self.action:
                return self.action() # Return action result for dialogs
        return False

class Dropdown:
    def __init__(self, x, y, width, height, options, default_text="Select Ship"):
        self.rect = pygame.Rect(x, y, width, height)
        self.selected_option = None
        self.is_open = False
        self.default_text = default_text
        self._options = [] # Internal storage for options
        self.option_rects = []
        self.set_options(options) # Initialize with options and build rects

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, new_options):
        self._options = new_options
        self._rebuild_option_rects() # Call helper method to rebuild rects

    def _rebuild_option_rects(self):
        """Rebuilds the list of rectangles for each dropdown option."""
        self.option_rects = []
        for i, option in enumerate(self._options):
            option_rect = pygame.Rect(self.rect.x, self.rect.y + self.rect.height * (i + 1), self.rect.width, self.rect.height)
            self.option_rects.append(option_rect)

    def set_options(self, new_options):
        # This method uses the property setter to ensure rebuild
        self.options = new_options

    def draw(self, surface):
        # Draw main button
        display_text = self.selected_option if self.selected_option else self.default_text
        pygame.draw.rect(surface, LIGHT_GREY, self.rect, border_radius=5)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=5)
        text_surface = font.render(display_text, True, BLACK)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

        # Draw dropdown arrow
        arrow_points = [
            (self.rect.right - 20, self.rect.centery - 5),
            (self.rect.right - 10, self.rect.centery - 5),
            (self.rect.right - 15, self.rect.centery + 5)
        ]
        pygame.draw.polygon(surface, BLACK, arrow_points)

        # Draw options if open
        if self.is_open:
            # Re-verify and rebuild if somehow out of sync (shouldn't happen with property setter)
            if len(self.options) != len(self.option_rects):
                 self._rebuild_option_rects()

            for i, option in enumerate(self.options):
                if i < len(self.option_rects): # Defensive check
                    option_rect = self.option_rects[i]
                else: # Fallback, though _rebuild_option_rects should prevent this
                    option_rect = pygame.Rect(self.rect.x, self.rect.y + self.rect.height * (i + 1), self.rect.width, self.rect.height)

                pygame.draw.rect(surface, WHITE, option_rect, border_radius=5)
                pygame.draw.rect(surface, BLACK, option_rect, 1, border_radius=5)
                option_text_surface = font.render(option, True, BLACK)
                option_text_rect = option_text_surface.get_rect(center=option_rect.center)
                surface.blit(option_text_surface, option_text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_open = not self.is_open
                return True # Event handled

            if self.is_open:
                for i, option_rect in enumerate(self.option_rects):
                    if option_rect.collidepoint(event.pos):
                        if i < len(self.options): # Defensive check
                            self.selected_option = self.options[i]
                            self.is_open = False
                            return True # Event handled
        return False # Event not handled by this dropdown

class TextInputBox:
    def __init__(self, x, y, width, height, font, initial_text='', text_color=BLACK, active_color=BLUE, inactive_color=LIGHT_GREY):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.color = inactive_color
        self.active_color = active_color
        self.inactive_color = inactive_color
        self.text_color = text_color
        self.text = initial_text
        self.txt_surface = font.render(self.text, True, self.text_color)
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = pygame.time.get_ticks()

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = not self.active
            else:
                self.active = False
            self.color = self.active_color if self.active else self.inactive_color
            self.cursor_timer = pygame.time.get_ticks() # Reset cursor blink
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                elif event.key == pygame.K_RETURN:
                    # Optional: what happens on Enter, here we do nothing specific
                    pass
                else:
                    self.text += event.unicode
                self.txt_surface = self.font.render(self.text, True, self.text_color)
                self.cursor_timer = pygame.time.get_ticks() # Reset cursor blink

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=5)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=5)
        
        # Blit the text.
        # Ensure text does not go out of bounds of the input box's fixed width
        text_rect_to_blit = self.txt_surface.get_rect(x=self.rect.x + 5, centery=self.rect.centery)
        surface.blit(self.txt_surface, text_rect_to_blit)
        
        # Draw cursor
        if self.active and (pygame.time.get_ticks() - self.cursor_timer) % 1000 < 500:
            cursor_x = self.rect.x + 5 + self.txt_surface.get_width()
            pygame.draw.line(surface, BLACK, (cursor_x, self.rect.y + 5), (cursor_x, self.rect.y + self.rect.height - 5), 2)

class AddShipDialog:
    def __init__(self, x, y, width, height, font, on_confirm_callback, on_cancel_callback):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.on_confirm_callback = on_confirm_callback
        self.on_cancel_callback = on_cancel_callback

        self.name_input = TextInputBox(x + 20, y + 60, 200, 30, font, initial_text='Ship Name')
        # Pre-fill arrival time with a reasonable future time for convenience
        default_arrival_time = (datetime.datetime.now() + datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')
        self.arrival_time_input = TextInputBox(x + 20, y + 130, 200, 30, font, initial_text=default_arrival_time)

        self.confirm_button = Button(x + width - 120, y + height - 40, 100, 30, "Confirm", LIGHT_GREEN, DARK_GREEN, action=self._confirm)
        self.cancel_button = Button(x + width - 230, y + height - 40, 100, 30, "Cancel", RED, (150,0,0), action=self._cancel)
        
        self.error_message = ""
        self.error_timer = 0

    def _confirm(self):
        ship_name = self.name_input.text.strip()
        arrival_time_str = self.arrival_time_input.text.strip()

        if not ship_name:
            self.error_message = "Ship name cannot be empty."
            self.error_timer = pygame.time.get_ticks()
            return False

        try:
            arrival_time = datetime.datetime.strptime(arrival_time_str, '%Y-%m-%d %H:%M')
            if self.on_confirm_callback:
                self.on_confirm_callback(ship_name, arrival_time)
            return True # Dialog confirmed and can close
        except ValueError:
            self.error_message = "Invalid time format (YYYY-MM-DD HH:MM)"
            self.error_timer = pygame.time.get_ticks()
            return False # Dialog stays open

    def _cancel(self):
        if self.on_cancel_callback:
            self.on_cancel_callback()
        return True # Dialog cancelled and can close

    def handle_event(self, event):
        self.name_input.handle_event(event)
        self.arrival_time_input.handle_event(event)
        
        if self.confirm_button.handle_event(event):
            return True # Event handled, potential close
        if self.cancel_button.handle_event(event):
            return True # Event handled, potential close
        return False # Event not handled in a way that closes the dialog

    def draw(self, surface):
        # Draw dialog background
        pygame.draw.rect(surface, WHITE, self.rect, border_radius=10)
        pygame.draw.rect(surface, BLACK, self.rect, 3, border_radius=10)

        title = large_font.render("Add New Ship", True, BLACK)
        surface.blit(title, (self.rect.x + 20, self.rect.y + 10))

        name_label = font.render("Ship Name:", True, BLACK)
        surface.blit(name_label, (self.rect.x + 20, self.rect.y + 40))
        self.name_input.draw(surface)

        time_label = font.render("Arrival Time (YYYY-MM-DD HH:MM):", True, BLACK)
        surface.blit(time_label, (self.rect.x + 20, self.rect.y + 110))
        self.arrival_time_input.draw(surface)

        self.confirm_button.draw(surface)
        self.cancel_button.draw(surface)

        if self.error_message:
            error_surface = font.render(self.error_message, True, RED)
            surface.blit(error_surface, (self.rect.x + 20, self.rect.y + self.rect.height - 60))
            if pygame.time.get_ticks() - self.error_timer > 3000: # Clear error after 3 seconds
                self.error_message = ""

# --- Emergency Message Dialog Class ---
class EmergencyMessageDialog:
    def __init__(self, x, y, width, height, font, on_send_callback, on_cancel_callback):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.on_send_callback = on_send_callback
        self.on_cancel_callback = on_cancel_callback

        self.message_input = TextInputBox(x + 20, y + 60, width - 40, 60, font, initial_text='')
        self.send_button = Button(x + width - 120, y + height - 40, 100, 30, "Send", RED, (150,0,0), action=self._send)
        self.cancel_button = Button(x + width - 230, y + height - 40, 100, 30, "Cancel", LIGHT_GREY, DARK_GREY, action=self._cancel)
        
        self.error_message = ""
        self.error_timer = 0

    def _send(self):
        message = self.message_input.text.strip()
        if not message: # Check if message is empty after stripping
            self.error_message = "Emergency message cannot be empty."
            self.error_timer = pygame.time.get_ticks()
            return False
        
        if self.on_send_callback:
            self.on_send_callback(message)
        return True # Dialog confirmed and can close

    def _cancel(self):
        if self.on_cancel_callback:
            self.on_cancel_callback()
        return True # Dialog cancelled and can close

    def handle_event(self, event):
        self.message_input.handle_event(event)
        
        if self.send_button.handle_event(event):
            return True
        if self.cancel_button.handle_event(event):
            return True
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, WHITE, self.rect, border_radius=10)
        pygame.draw.rect(surface, BLACK, self.rect, 3, border_radius=10)

        title = large_font.render("Send Emergency Message", True, BLACK)
        surface.blit(title, (self.rect.x + 20, self.rect.y + 10))

        message_label = font.render("Message:", True, BLACK)
        surface.blit(message_label, (self.rect.x + 20, self.rect.y + 40))
        self.message_input.draw(surface)

        self.send_button.draw(surface)
        self.cancel_button.draw(surface)

        if self.error_message:
            error_surface = font.render(self.error_message, True, RED)
            surface.blit(error_surface, (self.rect.x + 20, self.rect.y + self.rect.height - 60))
            if pygame.time.get_ticks() - self.error_timer > 3000: # Clear error after 3 seconds
                self.error_message = ""

# --- Ship Class ---
class Ship(pygame.sprite.Sprite):
    def __init__(self, ship_id, name, arrival_time, size, unloading_time, start_x, start_y, initial_speed=0):
        super().__init__()
        self.ship_id = ship_id
        self.name = name
        self.arrival_time = arrival_time # datetime object
        self.size = size # e.g., 'small', 'medium', 'large'
        self.unloading_time = unloading_time # hours (conceptual)
        self.image = pygame.Surface((60, 30))
        self.image.fill(BLUE)
        pygame.draw.rect(self.image, DARK_GREY, (0, 0, 60, 30), 2) # Border
        text_surface = font.render(f"ID:{self.ship_id}", True, WHITE)
        text_rect = text_surface.get_rect(center=(30, 15))
        self.image.blit(text_surface, text_rect)
        self.rect = self.image.get_rect(topleft=(start_x, start_y))

        self.original_pos = self.rect.topleft
        self.is_dragging = False
        self.offset_x = 0
        self.offset_y = 0

        self.current_speed_kmh = initial_speed # Fabricated speed in km/h
        self.current_zone = "Open Sea" # "Open Sea", "Light Green", "Dark Green", "Red Zone", "Parked"
        self.parked_terminal = None
        self.is_selected_for_edit = False # For UI editing
        self.last_dist_to_port_center = None # Track previous distance for movement direction
        self.movement_direction = None # "incoming", "outgoing", or None

    def draw(self, screen):
        screen.blit(self.image, self.rect)
        # Display ship name and speed near the ship
        name_text = font.render(f"{self.name}", True, BLACK)
        speed_text = font.render(f"{self.current_speed_kmh:.1f} km/h", True, BLACK)
        screen.blit(name_text, (self.rect.x, self.rect.y - 20))
        screen.blit(speed_text, (self.rect.x, self.rect.y + self.rect.height + 5))

        if self.is_selected_for_edit:
            pygame.draw.rect(screen, YELLOW, self.rect, 3) # Highlight if selected for edit

    def start_drag(self, mouse_pos):
        self.is_dragging = True
        self.offset_x = self.rect.x - mouse_pos[0]
        self.offset_y = self.rect.y - mouse_pos[1]
        # Store original position in case parking fails or for undocking
        self.original_pos = self.rect.topleft 


    def stop_drag(self):
        self.is_dragging = False

    def drag(self, mouse_pos):
        if self.is_dragging:
            self.rect.x = mouse_pos[0] + self.offset_x
            self.rect.y = mouse_pos[1] + self.offset_y # Corrected line
            self.update_speed_and_zone()

    def update_speed_and_zone(self):
        # Calculate distance to port's center
        port_center_x = PORT_X + PORT_WIDTH // 2
        port_center_y = PORT_Y + PORT_HEIGHT // 2
        
        dist_to_port_center = ((self.rect.centerx - port_center_x)**2 + \
                               (self.rect.centery - port_center_y)**2)**0.5

        prev_zone = self.current_zone
        
        # Determine movement direction based on distance change
        if self.last_dist_to_port_center is not None:
            if dist_to_port_center < self.last_dist_to_port_center - 1: # Moving closer (with a small threshold)
                self.movement_direction = "incoming"
            elif dist_to_port_center > self.last_dist_to_port_center + 1: # Moving farther (with a small threshold)
                self.movement_direction = "outgoing"
            else:
                self.movement_direction = None # Stationary or very slight movement

        # Only update zone and speed if not parked
        if self.current_zone != "Parked":
            if dist_to_port_center <= RED_ZONE_DIST_PX:
                self.current_zone = "Red Zone"
                if not self.is_dragging: # Only auto-adjust speed if not actively dragging
                    self.current_speed_kmh = min(self.current_speed_kmh, random.uniform(5, 15)) # Slow down
            elif dist_to_port_center <= DARK_GREEN_ZONE_DIST_PX:
                self.current_zone = "Dark Green Zone"
                if not self.is_dragging:
                    self.current_speed_kmh = min(self.current_speed_kmh, random.uniform(15, 30))
            elif dist_to_port_center <= LIGHT_GREEN_ZONE_DIST_PX:
                self.current_zone = "Light Green Zone"
                if not self.is_dragging:
                    self.current_speed_kmh = min(self.current_speed_kmh, random.uniform(30, 50))
            else:
                self.current_zone = "Open Sea"
                if not self.is_dragging:
                    self.current_speed_kmh = max(self.current_speed_kmh, random.uniform(40, 70)) # Speed up if far
        else: # If currently parked, no movement
            self.movement_direction = None

        # Simulate parking if collision with port AND was dragging AND not already parked
        port_rect = pygame.Rect(PORT_X, PORT_Y, PORT_WIDTH, PORT_HEIGHT)
        if port_rect.colliderect(self.rect) and self.is_dragging and self.current_zone != "Parked":
            # Attempt to park
            terminal = self.get_available_terminal()
            if terminal:
                self.current_zone = "Parked"
                self.current_speed_kmh = 0
                self.parked_terminal = terminal['id']
                self.rect.topleft = self.parked_terminal_position(terminal['id'])
                self.stop_drag() # Stop dragging once parked
                terminal['occupied_by'] = self.ship_id
                self.movement_direction = None # No movement when parked
                print(f"Ship {self.name} (ID:{self.ship_id}) parked at Terminal {self.parked_terminal}")
                self.send_api_data("docked", {"terminal_id": self.parked_terminal}) # API call for docking
            else:
                # No available terminal, can't park here
                print(f"No available terminal for Ship {self.name}. Cannot park.")
                # Snap back to previous position and stop dragging
                self.rect.topleft = self.original_pos
                self.stop_drag()
                # If it snaps back, its movement direction should revert to what it was before attempting to park
                # This requires more complex state, for now, just reset to None
                self.movement_direction = None


        # If zone changed, "send API data" (only if not parked, or if newly parked)
        if prev_zone != self.current_zone:
            # Only send zone_change if it's not the initial parking event
            # or if it's specifically transitioning *out* of parked state
            if self.current_zone != "Parked" or prev_zone == "Parked":
                self.send_api_data("zone_change")
                print(f"Ship {self.name} entered {self.current_zone}")


        self.last_dist_to_port_center = dist_to_port_center # Update last distance for next frame


    def get_available_terminal(self):
        # Find the nearest available terminal
        
        # Sort terminals by proximity to the ship's current position
        sorted_terminals = sorted(terminals_data, key=lambda t: ((self.rect.centery - (t['y'] + t['height']/2))**2)**0.5)

        for terminal in sorted_terminals:
            if terminal['occupied_by'] is None: # Check if available
                # Consider terminal capacity (not yet fully implemented for multiple ships per terminal)
                # For now, if capacity is 1, it's strictly one ship. If capacity > 1, it's effectively 1 ship still.
                # `occupied_by` would need to be a list. For now, it's binary.
                return terminal
        return None # No available terminal

    def parked_terminal_position(self, terminal_id):
        # Calculate the position to snap the ship to once parked
        for terminal in terminals_data:
            if terminal['id'] == terminal_id:
                # Place ship at the right edge of the terminal
                return (terminal['x'] + terminal['width'] - self.rect.width - 5,
                        terminal['y'] + terminal['height'] / 2 - self.rect.height / 2)
        return (0,0) # Should not happen

    def send_api_data(self, event_type, additional_data=None):
        """
        Sends ship event data to the FastAPI server.
        event_type: A string describing the type of event (e.g., "zone_change", "docked", "undocked", "ship_deleted", "emergency").
        additional_data: Optional dictionary for event-specific data.
        """
        payload = {
            "ship_id": self.ship_id,
            "ship_name": self.name,
            "current_zone": self.current_zone,
            "current_speed_kmh": round(self.current_speed_kmh, 1),
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type # e.g., "ship_deleted", "zone_change", "undocked"
        }
        if self.current_zone == "Parked" and self.parked_terminal: # Only add parked_terminal if actually parked
            payload["parked_terminal"] = self.parked_terminal
        
        if additional_data:
            payload.update(additional_data) # Add any specific data for the event

        try:
            response = requests.post(LOG_EVENT_API_URL, json=payload, timeout=1) # Added timeout
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            # print(f"API call successful for {event_type} (Ship ID: {self.ship_id}): {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"API call failed for {event_type} (Ship ID: {self.ship_id}): {e}")


# --- Game State Variables ---
all_sprites = pygame.sprite.Group()
active_ships = pygame.sprite.Group() # Group for ships currently on the map

selected_ship_on_map = None # The ship currently being dragged or selected for speed edit

# --- Terminal Data ---
terminals_data = []
for i in range(TERMINAL_COUNT):
    terminal_id = i + 1
    terminal_x = PORT_X
    terminal_y = PORT_Y + i * TERMINAL_HEIGHT
    capacity = 1 if terminal_id in [1, 2] else 1 # Simplified capacity for now
    terminals_data.append({
        'id': terminal_id,
        'x': terminal_x,
        'y': terminal_y,
        'width': PORT_WIDTH,
        'height': TERMINAL_HEIGHT,
        'capacity': capacity,
        'occupied_by': None # Ship ID if occupied
    })

# --- Ship Data Management ---
next_ship_id = 1
all_ship_data = [] # List of dictionaries holding all ship data (active or not)

# --- Function Definitions ---
def add_new_random_ship_data():
    """Generates and adds a new ship with random data."""
    global next_ship_id
    ship_name = f"Ship-{chr(64 + next_ship_id)}"
    arrival_time = datetime.datetime.now() + datetime.timedelta(hours=random.randint(1, 10), minutes=random.randint(0,59))
    ship_size = random.choice(['small', 'medium', 'large'])
    unloading_time = random.randint(4, 24)
    
    new_data = {
        "ship_id": next_ship_id,
        "name": ship_name,
        "arrival_time": arrival_time,
        "size": ship_size,
        "unloading_time": unloading_time,
        "initial_speed": random.uniform(40, 60) # Default speed when spawned
    }
    all_ship_data.append(new_data)
    next_ship_id += 1
    update_dropdown_options()

def add_custom_ship_data(name, arrival_time):
    """Adds a new ship with custom name and arrival time."""
    global next_ship_id
    new_data = {
        "ship_id": next_ship_id,
        "name": name,
        "arrival_time": arrival_time,
        "size": random.choice(['small', 'medium', 'large']), # Randomize other properties
        "unloading_time": random.randint(4, 24),
        "initial_speed": random.uniform(40, 60)
    }
    all_ship_data.append(new_data)
    next_ship_id += 1
    update_dropdown_options()
    print(f"Custom Ship '{name}' added. Arriving at {arrival_time.strftime('%Y-%m-%d %H:%M')}")


def update_dropdown_options():
    # Only include ships not currently active on the map in the dropdown
    active_ship_ids = {s.ship_id for s in active_ships}
    available_ships_for_dropdown = [s for s in all_ship_data if s['ship_id'] not in active_ship_ids]
    dropdown_options = [f"ID:{s['ship_id']} - {s['name']} (Arr: {s['arrival_time'].strftime('%H:%M')})" for s in available_ships_for_dropdown]
    ship_dropdown.set_options(dropdown_options) # Use the setter method

# --- UI Elements ---
# Add Ship Dialog (State management)
add_ship_dialog = None
is_add_ship_dialog_active = False

def activate_add_ship_dialog():
    global is_add_ship_dialog_active, add_ship_dialog
    is_add_ship_dialog_active = True
    add_ship_dialog = AddShipDialog(
        SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT // 2 - 120, 400, 240, font,
        on_confirm_add_ship, on_cancel_add_ship
    )
    return True # Indicates button action was handled

def on_confirm_add_ship(ship_name, arrival_time):
    global is_add_ship_dialog_active, add_ship_dialog
    add_custom_ship_data(ship_name, arrival_time)
    is_add_ship_dialog_active = False
    add_ship_dialog = None # Clear instance

def on_cancel_add_ship():
    global is_add_ship_dialog_active, add_ship_dialog
    is_add_ship_dialog_active = False
    add_ship_dialog = None # Clear instance

# --- Emergency Message Dialog State ---
emergency_message_dialog = None
is_emergency_dialog_active = False

# Unified emergency message handler
def on_send_emergency_message_unified(message_content):
    global is_emergency_dialog_active, emergency_message_dialog, selected_ship_on_map
    
    if selected_ship_on_map:
        # Ship-specific emergency
        selected_ship_on_map.send_api_data("emergency", {
            "message": message_content
        })
        print(f"Ship-specific emergency sent for {selected_ship_on_map.name}: {message_content}")
    else:
        # Global emergency
        payload = {
            "ship_id": 0, # Use 0 or a special ID for global messages
            "ship_name": "GLOBAL",
            "current_zone": "N/A",
            "current_speed_kmh": 0.0,
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": "emergency_global", # Distinct event type for global emergency
            "message": message_content
        }
        try:
            response = requests.post(LOG_EVENT_API_URL, json=payload, timeout=1)
            response.raise_for_status()
            print(f"Global Emergency API call successful: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Global Emergency API call failed: {e}")

    is_emergency_dialog_active = False
    emergency_message_dialog = None

def on_cancel_emergency_message():
    global is_emergency_dialog_active, emergency_message_dialog
    is_emergency_dialog_active = False
    emergency_message_dialog = None

# Function to activate the unified emergency dialog
def activate_unified_emergency_dialog():
    global is_emergency_dialog_active, emergency_message_dialog
    is_emergency_dialog_active = True
    emergency_message_dialog = EmergencyMessageDialog(
        SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT // 2 - 100, 400, 200, font,
        on_send_emergency_message_unified, on_cancel_emergency_message
    )
    return True


# UI Elements positions within the Control Panel
add_ship_button_y = CONTROL_PANEL_Y + large_font.get_height() + 30
add_ship_button = Button(CONTROL_PANEL_X + 15, add_ship_button_y, 120, 35, "Add New Ship", LIGHT_GREY, DARK_GREY, action=activate_add_ship_dialog)

ship_dropdown_y = add_ship_button.rect.y + add_ship_button.rect.height + 10
ship_dropdown = Dropdown(CONTROL_PANEL_X + 15, ship_dropdown_y, 250, 40, [])

# Removed the separate 'emergency_button' (Global)
# The 'emergency_button_edit_ship' will now be the unified button.


# Initial ships (now called after functions and UI elements are defined)
for _ in range(3): # Start with 3 ships
    add_new_random_ship_data()


# Edit panel for selected ship (global definition, positions will be updated dynamically)
speed_up_button = Button(0, 0, 80, 30, "+ Speed", GREEN, DARK_GREEN)
speed_down_button = Button(0, 0, 80, 30, "- Speed", RED, (150,0,0))
arrival_time_plus_button = Button(0, 0, 120, 30, "+ 20 Mins", YELLOW, ORANGE)
arrival_time_minus_button = Button(0, 0, 120, 30, "- 20 Mins", YELLOW, ORANGE)
remove_from_terminal_button = Button(0, 0, 90, 30, "Undock", BLUE, (0,0,150))
# Unified Emergency Button for Edit Ship Block (will also handle global if no ship selected)
emergency_button_unified = Button(0, 0, 100, 30, "Emergency", RED, (150,0,0), action=activate_unified_emergency_dialog)

# --- Pygame Message Display ---
pygame_message_queue = collections.deque() # Queue for messages from C client
MESSAGE_DISPLAY_DURATION = 5000 # milliseconds
last_message_display_time = 0
current_display_message = None

def display_pygame_message(message_text):
    global current_display_message, last_message_display_time
    current_display_message = message_text
    last_message_display_time = pygame.time.get_ticks()

def poll_for_c_client_messages():
    global pygame_message_queue
    try:
        response = requests.get(GET_MESSAGES_API_URL, timeout=1)
        response.raise_for_status()
        data = response.json()
        if data and data.get("messages"):
            for msg_entry in data["messages"]:
                source = msg_entry.get("source", "Unknown")
                timestamp = msg_entry.get("timestamp", "N/A")
                content = msg_entry.get("content", "No content")
                full_message = f"C-Client Message ({source} @ {timestamp}): {content}"
                pygame_message_queue.append(full_message)
                print(f"Pygame received new message for display: {full_message}")
    except requests.exceptions.RequestException as e:
        # print(f"Error polling for C client messages: {e}") # Suppress frequent errors
        pass # Keep silent if server is not reachable for messages

# Timer for polling C client messages
MESSAGE_POLL_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(MESSAGE_POLL_EVENT, 1000) # Poll every 1000ms (1 second)


# --- Game Loop ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == MESSAGE_POLL_EVENT:
            poll_for_c_client_messages()
            if pygame_message_queue and not current_display_message:
                display_pygame_message(pygame_message_queue.popleft())

        # If any dialog is active, only handle its events
        if is_add_ship_dialog_active and add_ship_dialog:
            if add_ship_dialog.handle_event(event):
                pass 
            continue # Skip other event processing while dialog is open
        
        if is_emergency_dialog_active and emergency_message_dialog:
            if emergency_message_dialog.handle_event(event):
                pass
            continue # Skip other event processing while dialog is open


        # Handle dropdown events
        if ship_dropdown.handle_event(event):
            if ship_dropdown.selected_option:
                # Find the selected ship data
                selected_id_str = ship_dropdown.selected_option.split(' ')[0].split(':')[1]
                selected_ship_data = next((s for s in all_ship_data if str(s['ship_id']) == selected_id_str), None)
                
                if selected_ship_data:
                    # Check if ship is already active on map
                    current_ship_on_map = next((s for s in active_ships if s.ship_id == selected_ship_data['ship_id']), None)

                    if not current_ship_on_map:
                        # Spawn the ship on the map at a random open sea position
                        spawn_x, spawn_y = get_random_open_sea_position()
                        new_ship = Ship(
                            selected_ship_data['ship_id'],
                            selected_ship_data['name'],
                            selected_ship_data['arrival_time'],
                            selected_ship_data['size'],
                            selected_ship_data['unloading_time'],
                            spawn_x, spawn_y, # Spawn location
                            selected_ship_data['initial_speed']
                        )
                        active_ships.add(new_ship)
                        all_sprites.add(new_ship)
                        
                        # Remove from all_ship_data and update dropdown
                        for i, s_data in enumerate(all_ship_data):
                            if s_data['ship_id'] == selected_ship_data['ship_id']:
                                all_ship_data.pop(i)
                                break
                        update_dropdown_options() # Refresh dropdown to reflect removal
                        ship_dropdown.selected_option = None # Clear selected option in dropdown

                        if selected_ship_on_map:
                            selected_ship_on_map.is_selected_for_edit = False
                        selected_ship_on_map = new_ship # Automatically select for dragging/editing
                        new_ship.is_selected_for_edit = True
                        print(f"Ship {new_ship.name} (ID:{new_ship.ship_id}) spawned for dragging at ({spawn_x}, {spawn_y}).")
                    else:
                        print(f"Ship {selected_ship_data['name']} (ID:{selected_ship_data['ship_id']}) is already on the map.")
                        # If already on map, just select it for editing
                        if selected_ship_on_map:
                            selected_ship_on_map.is_selected_for_edit = False
                        selected_ship_on_map = current_ship_on_map
                        selected_ship_on_map.is_selected_for_edit = True


        # Handle Add Ship button
        add_ship_button.handle_event(event)
        # The global emergency button is removed, its functionality is now merged into the unified one.


        # Handle mouse events for dragging ships
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left click
                # Check if an active ship is clicked for dragging/selection
                for ship in active_ships:
                    if ship.rect.collidepoint(event.pos):
                        if selected_ship_on_map:
                            selected_ship_on_map.is_selected_for_edit = False # Deselect previous
                        selected_ship_on_map = ship
                        selected_ship_on_map.is_selected_for_edit = True
                        selected_ship_on_map.start_drag(event.pos)
                        break
                else: # No ship clicked, deselect current IF NOT DRAGGING
                    if selected_ship_on_map and not selected_ship_on_map.is_dragging:
                        selected_ship_on_map.is_selected_for_edit = False
                        selected_ship_on_map = None


        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                if selected_ship_on_map and selected_ship_on_map.is_dragging:
                    selected_ship_on_map.stop_drag()
                    selected_ship_on_map.update_speed_and_zone() # Final update after drag

                    # Check for drag-to-delete
                    if DELETE_ZONE_RECT.colliderect(selected_ship_on_map.rect):
                        # Make API call for ship deletion
                        selected_ship_on_map.send_api_data("ship_deleted")

                        print(f"Ship {selected_ship_on_map.name} (ID:{selected_ship_on_map.ship_id}) deleted by drag-to-delete.")
                        # Remove from active_ships and all_sprites
                        active_ships.remove(selected_ship_on_map)
                        all_sprites.remove(selected_ship_on_map)
                        
                        # Remove from all_ship_data (if it was somehow still there)
                        for i, s_data in enumerate(all_ship_data):
                            if s_data['ship_id'] == selected_ship_on_map.ship_id:
                                all_ship_data.pop(i)
                                break
                        update_dropdown_options() # Refresh dropdown
                        
                        # Also release terminal if it was parked
                        for terminal in terminals_data:
                            if terminal['occupied_by'] == selected_ship_on_map.ship_id:
                                terminal['occupied_by'] = None
                                break
                        selected_ship_on_map = None # Deselect the deleted ship


        if event.type == pygame.MOUSEMOTION:
            if selected_ship_on_map and selected_ship_on_map.is_dragging:
                selected_ship_on_map.drag(event.pos)
            
            # Update button hover states
            add_ship_button.handle_event(event)
            # emergency_button.handle_event(event) # Removed global emergency button
            if selected_ship_on_map:
                speed_up_button.handle_event(event)
                speed_down_button.handle_event(event)
                arrival_time_plus_button.handle_event(event)
                arrival_time_minus_button.handle_event(event)
                remove_from_terminal_button.handle_event(event)
                emergency_button_unified.handle_event(event) # Now this handles both

        # Handle edit panel buttons (only if a ship is selected)
        if selected_ship_on_map:
            # Call handle_event for each button in the edit panel
            speed_up_button.handle_event(event)
            speed_down_button.handle_event(event)
            arrival_time_plus_button.handle_event(event)
            arrival_time_minus_button.handle_event(event)
            
            # Special handling for undock as it needs to access selected_ship_on_map directly
            if remove_from_terminal_button.handle_event(event):
                ship_to_undock = selected_ship_on_map
                if ship_to_undock and ship_to_undock.current_zone == "Parked":
                    print(f"Undocking selected ship {ship_to_undock.name} (ID:{ship_to_undock.ship_id}) from terminal {ship_to_undock.parked_terminal}")

                    # Make API call for leaving the terminal
                    ship_to_undock.send_api_data("undocked", {"terminal_id": ship_to_undock.parked_terminal})

                    # Release terminal
                    for terminal in terminals_data:
                        if terminal['occupied_by'] == ship_to_undock.ship_id:
                            terminal['occupied_by'] = None
                            break
                    
                    ship_to_undock.parked_terminal = None
                    ship_to_undock.current_zone = "Light Green Zone" # User requested "green area"
                    ship_to_undock.current_speed_kmh = random.uniform(40, 70) # Give it some speed
                    
                    # Place ship in the Light Green Zone (circular annulus)
                    port_center_x = PORT_X + PORT_WIDTH // 2
                    port_center_y = PORT_Y + PORT_HEIGHT // 2
                    
                    min_dist_for_green_zone = DARK_GREEN_ZONE_DIST_PX + 20 # Just outside dark green
                    max_dist_for_green_zone = LIGHT_GREEN_ZONE_DIST_PX - 20 # Just inside light green

                    # Randomly pick a distance within the light green zone range
                    # Ensure min_dist is less than max_dist to avoid errors if zones are too close
                    if min_dist_for_green_zone >= max_dist_for_green_zone:
                        # Fallback if zones overlap too much, pick a point near the center of the outer green zone
                        target_dist = (DARK_GREEN_ZONE_DIST_PX + LIGHT_GREEN_ZONE_DIST_PX) / 2
                    else:
                        target_dist = random.uniform(min_dist_for_green_zone, max_dist_for_green_zone)

                    # Randomly pick an angle (0 to 2*pi radians)
                    angle = random.uniform(0, 2 * math.pi)

                    # Calculate new coordinates
                    new_x = port_center_x + target_dist * math.cos(angle) - ship_to_undock.rect.width // 2
                    new_y = port_center_y + target_dist * math.sin(angle) - ship_to_undock.rect.height // 2
                    
                    # Ensure it stays within screen bounds (basic check for the whole ocean area)
                    # We use the OCEAN_START_X, OCEAN_WIDTH, SCREEN_HEIGHT for this
                    new_x = max(OCEAN_START_X, min(new_x, SCREEN_WIDTH - ship_to_undock.rect.width))
                    new_y = max(0, min(new_y, SCREEN_HEIGHT - ship_to_undock.rect.height))

                    ship_to_undock.rect.topleft = (new_x, new_y)
                    ship_to_undock.movement_direction = "outgoing" # Set direction for subsequent zone calls
                    ship_to_undock.send_api_data("zone_change") # Update status via API (now in light green)
                    
                    # Deselect the undocked ship
                    selected_ship_on_map.is_selected_for_edit = False
                    selected_ship_on_map = None
                else:
                    print("Selected ship is not parked, or no ship is selected.")
            
            emergency_button_unified.handle_event(event) # Now this handles both


    # --- Update Game State ---
    # Update ship zones and speeds if they are not being dragged
    for ship in active_ships:
        if not ship.is_dragging: # Only update automatically if not dragging
            ship.update_speed_and_zone()

    # --- Drawing ---
    # Draw the main ocean background
    pygame.draw.rect(screen, BLUE, (OCEAN_START_X, 0, OCEAN_WIDTH, OCEAN_HEIGHT))

    port_center_x = PORT_X + PORT_WIDTH // 2
    port_center_y = PORT_Y + PORT_HEIGHT // 2

    # Draw Gradient Zones (from outermost to innermost)
    # Light Green to Dark Green gradient (from LIGHT_GREEN_ZONE_DIST_PX down to DARK_GREEN_ZONE_DIST_PX)
    if LIGHT_GREEN_ZONE_DIST_PX > DARK_GREEN_ZONE_DIST_PX: # Ensure valid range
        for r in range(LIGHT_GREEN_ZONE_DIST_PX, DARK_GREEN_ZONE_DIST_PX -1, -5): # Step by 5 pixels
            factor = (r - DARK_GREEN_ZONE_DIST_PX) / (LIGHT_GREEN_ZONE_DIST_PX - DARK_GREEN_ZONE_DIST_PX)
            color = interpolate_color(DARK_GREEN, LIGHT_GREEN, factor) # interpolate from inner to outer color
            pygame.draw.circle(screen, color, (port_center_x, port_center_y), r, 0) # Filled circle

    # Dark Green to Red gradient (from DARK_GREEN_ZONE_DIST_PX down to RED_ZONE_DIST_PX)
    if DARK_GREEN_ZONE_DIST_PX > RED_ZONE_DIST_PX: # Ensure valid range
        for r in range(DARK_GREEN_ZONE_DIST_PX, RED_ZONE_DIST_PX -1, -5): # Step by 5 pixels
            factor = (r - RED_ZONE_DIST_PX) / (DARK_GREEN_ZONE_DIST_PX - RED_ZONE_DIST_PX) # Corrected line
            color = interpolate_color(RED, DARK_GREEN, factor) # interpolate from inner to outer color
            pygame.draw.circle(screen, color, (port_center_x, port_center_y), r, 0) # Filled circle

    # Red Zone core (filled)
    pygame.draw.circle(screen, RED, (port_center_x, port_center_y), RED_ZONE_DIST_PX, 0)

    # Zone Labels (can be drawn as outlines or above the gradients)
    light_green_label = font.render("Light Green Zone", True, BLACK)
    dark_green_label = font.render("Dark Green Zone", True, BLACK)
    red_label = font.render("Red Zone", True, WHITE) # White for red background
    
    screen.blit(light_green_label, (port_center_x - light_green_label.get_width() // 2, port_center_y - LIGHT_GREEN_ZONE_DIST_PX + 10))
    screen.blit(dark_green_label, (port_center_x - dark_green_label.get_width() // 2, port_center_y - DARK_GREEN_ZONE_DIST_PX + 10))
    screen.blit(red_label, (port_center_x - red_label.get_width() // 2, port_center_y - RED_ZONE_DIST_PX + 10))


    # Draw Port Area
    pygame.draw.rect(screen, DARK_GREY, (PORT_X, PORT_Y, PORT_WIDTH, PORT_HEIGHT), border_radius=10)
    port_title = title_font.render("Port Control", True, WHITE)
    screen.blit(port_title, (PORT_X + PORT_WIDTH // 2 - port_title.get_width() // 2, PORT_Y - 50))


    # Draw Terminals within the port
    for terminal in terminals_data:
        terminal_rect = pygame.Rect(terminal['x'], terminal['y'], terminal['width'], terminal['height'])
        
        # Color based on occupancy
        terminal_color = LIGHT_GREY
        if terminal['occupied_by'] is not None:
            terminal_color = (180, 50, 50) # Reddish if occupied
        
        pygame.draw.rect(screen, terminal_color, terminal_rect, border_radius=5)
        pygame.draw.rect(screen, BLACK, terminal_rect, 2, border_radius=5) # Terminal outline

        terminal_label = font.render(f"Terminal {terminal['id']}", True, BLACK)
        screen.blit(terminal_label, (terminal_rect.x + 10, terminal_rect.y + 5))
        
        capacity_label = font.render(f"Capacity: {terminal['capacity']}", True, BLACK)
        screen.blit(capacity_label, (terminal_rect.x + 10, terminal_rect.y + 25))

        if terminal['occupied_by']:
            occupied_ship_name = "N/A"
            for ship in active_ships:
                if ship.ship_id == terminal['occupied_by']:
                    occupied_ship_name = ship.name
                    break
            occupied_label = font.render(f"Occupied by: {occupied_ship_name}", True, BLACK)
            screen.blit(occupied_label, (terminal_rect.x + 10, terminal_rect.y + 45))


    # Draw active ships
    active_ships.draw(screen)

    # Draw Control Panel Background (fills the left side)
    pygame.draw.rect(screen, DARK_GREY, (CONTROL_PANEL_X, CONTROL_PANEL_Y, CONTROL_PANEL_WIDTH, CONTROL_PANEL_HEIGHT), border_radius=10)
    pygame.draw.rect(screen, BLACK, (CONTROL_PANEL_X, CONTROL_PANEL_Y, CONTROL_PANEL_WIDTH, CONTROL_PANEL_HEIGHT), 2, border_radius=10)
    
    panel_title = large_font.render("Control Panel", True, WHITE)
    screen.blit(panel_title, (CONTROL_PANEL_X + CONTROL_PANEL_WIDTH // 2 - panel_title.get_width() // 2, CONTROL_PANEL_Y + 10))

    # Draw UI elements within the control panel
    add_ship_button.draw(screen) 
    ship_dropdown.draw(screen) 
    # Removed the global emergency button here.

    # Draw Incoming Ships Timetable (now moved to the bottom section of the control panel)
    timetable_height = 200 # Fixed height for the timetable
    # Calculate y-position from the bottom of the control panel
    timetable_y = CONTROL_PANEL_Y + CONTROL_PANEL_HEIGHT - timetable_height - 10 # 10 pixels from bottom
    timetable_rect = pygame.Rect(CONTROL_PANEL_X + 10, timetable_y, CONTROL_PANEL_WIDTH - 20, timetable_height)
    pygame.draw.rect(screen, WHITE, timetable_rect, border_radius=10)
    pygame.draw.rect(screen, BLACK, timetable_rect, 2, border_radius=10)
    
    # Changed title to reflect active ships
    table_title = large_font.render("Active Ships on Ocean", True, BLACK)
    screen.blit(table_title, (timetable_rect.x + 10, timetable_rect.y + 10))

    y_offset = timetable_rect.y + 40
    
    # Filter for ships currently on the map (active_ships)
    # Iterate directly over active_ships sprite group
    active_ships_list = sorted(active_ships.sprites(), key=lambda s: s.name) # Sort by name for consistent display

    for i, ship in enumerate(active_ships_list[:5]): # Show top 5 active ships
        # Ensure text stays within bounds
        if y_offset + i * 25 < timetable_rect.y + timetable_rect.height - 20: 
            ship_info = f"ID:{ship.ship_id} {ship.name} (Zone: {ship.current_zone})"
            ship_text = font.render(ship_info, True, BLACK)
            screen.blit(ship_text, (timetable_rect.x + 10, y_offset + i * 25))
    
    # Draw edit panel if a ship is selected on the map (now also within control panel)
    if selected_ship_on_map:
        # Calculate edit panel position dynamically, above the timetable
        edit_panel_height = 180 # Increased height to accommodate new button
        edit_panel_y = timetable_rect.y - edit_panel_height - 10 # 10 pixels above timetable
        
        # Ensure it doesn't overlap with the dropdown or add ship button
        min_edit_panel_y = ship_dropdown.rect.y + ship_dropdown.rect.height + 10 # Adjusted to be below dropdown
        if edit_panel_y < min_edit_panel_y:
            edit_panel_y = min_edit_panel_y
            # If it's forced down, adjust its height if necessary to fit
            if edit_panel_y + edit_panel_height > timetable_rect.y - 5: # Ensure it doesn't touch timetable
                edit_panel_height = timetable_rect.y - 5 - edit_panel_y
                if edit_panel_height < 0: edit_panel_height = 0 # Prevent negative height


        edit_panel_rect = pygame.Rect(CONTROL_PANEL_X + 10, edit_panel_y, CONTROL_PANEL_WIDTH - 20, edit_panel_height)

        pygame.draw.rect(screen, WHITE, edit_panel_rect, border_radius=10)
        pygame.draw.rect(screen, BLACK, edit_panel_rect, 2, border_radius=10)
        
        panel_title = large_font.render(f"Edit Ship: {selected_ship_on_map.name}", True, BLACK)
        screen.blit(panel_title, (edit_panel_rect.x + 10, edit_panel_rect.y + 10))

        # Update button positions relative to the new edit_panel_rect
        speed_up_button.rect.topleft = (edit_panel_rect.x + 10, edit_panel_rect.y + 40)
        speed_down_button.rect.topleft = (edit_panel_rect.x + 100, edit_panel_rect.y + 40)
        arrival_time_plus_button.rect.topleft = (edit_panel_rect.x + 10, edit_panel_rect.y + 80)
        arrival_time_minus_button.rect.topleft = (edit_panel_rect.x + 140, edit_panel_rect.y + 80)
        remove_from_terminal_button.rect.topleft = (edit_panel_rect.x + 10, edit_panel_rect.y + 120) # Moved down
        emergency_button_unified.rect.topleft = (edit_panel_rect.x + 120, edit_panel_rect.y + 120) # Position for unified emergency button

        speed_up_button.draw(screen)
        speed_down_button.draw(screen)
        arrival_time_plus_button.draw(screen)
        arrival_time_minus_button.draw(screen)
        remove_from_terminal_button.draw(screen)
        emergency_button_unified.draw(screen) # Draw Unified Emergency Button
    else: # If no ship is selected, draw the unified emergency button in the main control panel area
        emergency_button_unified.rect.topleft = (CONTROL_PANEL_X + 15, ship_dropdown.rect.y + ship_dropdown.rect.height + 10)
        emergency_button_unified.draw(screen)


    # Draw Add Ship Dialog last, so it's on top
    if is_add_ship_dialog_active and add_ship_dialog:
        add_ship_dialog.draw(screen)
    
    # Draw Emergency Message Dialog last, so it's on top
    if is_emergency_dialog_active and emergency_message_dialog:
        emergency_message_dialog.draw(screen)

    # --- Draw C Client Message Popup ---
    if current_display_message:
        message_surface = large_font.render(current_display_message, True, BLACK)
        message_rect = message_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        
        # Background for the message
        bg_rect = message_rect.inflate(20, 10) # Add padding
        pygame.draw.rect(screen, YELLOW, bg_rect, border_radius=10)
        pygame.draw.rect(screen, BLACK, bg_rect, 2, border_radius=10)
        
        screen.blit(message_surface, message_rect)

        # Clear message after duration
        if pygame.time.get_ticks() - last_message_display_time > MESSAGE_DISPLAY_DURATION:
            current_display_message = None


    pygame.display.flip()
    clock.tick(FPS)

# --- Quit Pygame ---
pygame.quit()
sys.exit()
