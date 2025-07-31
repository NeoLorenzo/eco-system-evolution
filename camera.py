#camera.py

import pygame
import constants as C

class Camera:
    def __init__(self):
        self.x = C.WORLD_WIDTH_CM / 2
        self.y = C.WORLD_HEIGHT_CM / 2
        self.zoom = 1.0
        self.dirty = True
        print(f"Camera initialized at world coordinates ({self.x:.0f}, {self.y:.0f}) with zoom {self.zoom:.2f}")

    def world_to_screen(self, world_x, world_y):
        screen_x = (world_x - self.x) * self.zoom + C.SCREEN_WIDTH / 2
        screen_y = (world_y - self.y) * self.zoom + C.SCREEN_HEIGHT / 2
        return int(screen_x), int(screen_y)

    def screen_to_world(self, screen_x, screen_y):
        """Converts a point from screen coordinates to world coordinates."""
        world_x = (screen_x - C.SCREEN_WIDTH / 2) / self.zoom + self.x
        world_y = (screen_y - C.SCREEN_HEIGHT / 2) / self.zoom + self.y
        return world_x, world_y

    def scale(self, value):
        return int(value * self.zoom)

    def pan(self, dx, dy):
        """Pans the camera and clamps its position to the world boundaries."""
        self.x += dx / self.zoom
        self.y += dy / self.zoom

        # Calculate the visible half-width and half-height in world coordinates
        visible_half_width = (C.SCREEN_WIDTH / 2) / self.zoom
        visible_half_height = (C.SCREEN_HEIGHT / 2) / self.zoom

        # Clamp X coordinate
        self.x = max(visible_half_width, self.x)
        self.x = min(C.WORLD_WIDTH_CM - visible_half_width, self.x)

        # Clamp Y coordinate
        self.y = max(visible_half_height, self.y)
        self.y = min(C.WORLD_HEIGHT_CM - visible_half_height, self.y)

        self.dirty = True

    def zoom_in(self):
        """Zooms in, clamping to a maximum zoom level."""
        self.zoom *= (1 + C.CAMERA_ZOOM_SPEED)
        self.zoom = min(self.zoom, C.CAMERA_MAX_ZOOM) # Clamp to max zoom
        self.dirty = True

    def zoom_out(self):
        """Zooms out, clamping to a minimum zoom level."""
        self.zoom *= (1 - C.CAMERA_ZOOM_SPEED)
        self.zoom = max(self.zoom, C.CAMERA_MIN_ZOOM) # Clamp to min zoom
        self.dirty = True

    def draw_world_border(self, screen):
        start_x, start_y = self.world_to_screen(0, 0)
        width = self.scale(C.WORLD_WIDTH_CM)
        height = self.scale(C.WORLD_HEIGHT_CM)
        border_rect = pygame.Rect(start_x, start_y, width, height)
        pygame.draw.rect(screen, C.COLOR_BLACK, border_rect, 1)