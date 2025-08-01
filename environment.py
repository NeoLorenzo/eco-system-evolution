import pygame
import numpy as np
import noise
import constants as C
from numpy_noise import perlin_noise_2d
import logger as log

class Environment:
    def __init__(self):
        self.temp_seed = C.TEMP_NOISE_SEED
        self.terrain_seed = C.TERRAIN_NOISE_SEED
        self.humidity_seed = C.HUMIDITY_NOISE_SEED
        self.view_mode = "terrain"
        # This cache holds the original, full-resolution chunk surfaces.
        self.chunk_texture_cache = { "terrain": {}, "temperature": {}, "humidity": {} }
        
        # --- NEW: A cache to hold the SCALED chunk surfaces for the current zoom level. ---
        self.scaled_chunk_cache = {}

        p = np.arange(256, dtype=int)
        np.random.seed(self.terrain_seed)
        np.random.shuffle(p)
        self.p = np.stack([p, p]).flatten()

        log.log(f"Environment initialized with multi-cache rendering. Default view: {self.view_mode}")
    
    def get_temperature(self, x, y):
        wx_grid, wy_grid = np.array([x]), np.array([y])
        noise_value = perlin_noise_2d(
            self.p, (wx_grid + self.temp_seed) / C.NOISE_SCALE, (wy_grid + self.temp_seed) / C.NOISE_SCALE,
            octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
        )
        return (noise_value[0] + 1) / 2

    def get_elevation(self, x, y):
        wx_grid, wy_grid = np.array([x]), np.array([y])
        noise_value = perlin_noise_2d(
            self.p, wx_grid / C.NOISE_SCALE, wy_grid / C.NOISE_SCALE,
            octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
        )
        normalized_value = (noise_value[0] + 1) / 2
        return max(0.0, min(1.0, normalized_value ** C.TERRAIN_AMPLITUDE))

    def get_humidity(self, x, y):
        wx_grid, wy_grid = np.array([x]), np.array([y])
        noise_value = perlin_noise_2d(
            self.p, (wx_grid + self.humidity_seed) / C.NOISE_SCALE, (wy_grid + self.humidity_seed) / C.NOISE_SCALE,
            octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
        )
        return (noise_value[0] + 1) / 2

    def _get_terrain_color_vectorized(self, elevation_values):
        colors = np.zeros((*elevation_values.shape, 3), dtype=np.uint8)
        water_mask = elevation_values < C.TERRAIN_WATER_LEVEL
        sand_mask = (elevation_values >= C.TERRAIN_WATER_LEVEL) & (elevation_values < C.TERRAIN_SAND_LEVEL)
        grass_mask = (elevation_values >= C.TERRAIN_SAND_LEVEL) & (elevation_values < C.TERRAIN_GRASS_LEVEL)
        dirt_mask = (elevation_values >= C.TERRAIN_GRASS_LEVEL) & (elevation_values < C.TERRAIN_DIRT_LEVEL)
        mountain_mask = elevation_values >= C.TERRAIN_DIRT_LEVEL
        if np.any(water_mask):
            t = (elevation_values[water_mask] / C.TERRAIN_WATER_LEVEL)[..., np.newaxis]
            c1 = np.array(C.COLOR_DEEP_WATER)
            c2 = np.array(C.COLOR_SHALLOW_WATER)
            colors[water_mask] = (1 - t) * c1 + t * c2
        colors[sand_mask] = C.COLOR_SAND
        colors[grass_mask] = C.COLOR_GRASS
        colors[dirt_mask] = C.COLOR_DIRT
        colors[mountain_mask] = C.COLOR_MOUNTAIN
        return np.transpose(colors, (1, 0, 2))

    def _get_temperature_color_vectorized(self, temp_values):
        colors = np.zeros((*temp_values.shape, 3), dtype=np.uint8)
        coldest_mask = temp_values < C.TEMP_COLOR_THRESHOLD_COLD
        cold_mask = (temp_values >= C.TEMP_COLOR_THRESHOLD_COLD) & (temp_values < C.TEMP_COLOR_THRESHOLD_TEMPERATE)
        hot_mask = (temp_values >= C.TEMP_COLOR_THRESHOLD_TEMPERATE) & (temp_values < C.TEMP_COLOR_THRESHOLD_HOT)
        hottest_mask = temp_values >= C.TEMP_COLOR_THRESHOLD_HOT
        if np.any(coldest_mask):
            t = (temp_values[coldest_mask] / C.TEMP_COLOR_THRESHOLD_COLD)[..., np.newaxis]
            colors[coldest_mask] = (1 - t) * np.array(C.COLOR_COLDEST) + t * np.array(C.COLOR_COLD)
        if np.any(cold_mask):
            t = ((temp_values[cold_mask] - C.TEMP_COLOR_THRESHOLD_COLD) / C.TEMP_COLOR_THRESHOLD_COLD)[..., np.newaxis]
            colors[cold_mask] = (1 - t) * np.array(C.COLOR_COLD) + t * np.array(C.COLOR_TEMPERATE)
        if np.any(hot_mask):
            t = ((temp_values[hot_mask] - C.TEMP_COLOR_THRESHOLD_TEMPERATE) / C.TEMP_COLOR_THRESHOLD_COLD)[..., np.newaxis]
            colors[hot_mask] = (1 - t) * np.array(C.COLOR_TEMPERATE) + t * np.array(C.COLOR_HOT)
        if np.any(hottest_mask):
            t = ((temp_values[hottest_mask] - C.TEMP_COLOR_THRESHOLD_HOT) / C.TEMP_COLOR_THRESHOLD_COLD)[..., np.newaxis]
            colors[hottest_mask] = (1 - t) * np.array(C.COLOR_HOT) + t * np.array(C.COLOR_HOTTEST)
        return np.transpose(colors, (1, 0, 2))

    def _get_humidity_color_vectorized(self, humidity_values):
        colors = np.zeros((*humidity_values.shape, 3), dtype=np.uint8)
        t = humidity_values[..., np.newaxis]
        colors[:] = (1 - t) * np.array(C.COLOR_DRY) + t * np.array(C.COLOR_WET)
        return np.transpose(colors, (1, 0, 2))

    def _generate_chunk_texture(self, chunk_x, chunk_y):
        wx = np.linspace(chunk_x * C.CHUNK_SIZE_CM, (chunk_x + 1) * C.CHUNK_SIZE_CM, C.CHUNK_RESOLUTION)
        wy = np.linspace(chunk_y * C.CHUNK_SIZE_CM, (chunk_y + 1) * C.CHUNK_SIZE_CM, C.CHUNK_RESOLUTION)
        wx_grid, wy_grid = np.meshgrid(wx, wy)
        if self.view_mode == "terrain":
            noise_values = perlin_noise_2d(
                self.p, wx_grid / C.NOISE_SCALE, wy_grid / C.NOISE_SCALE,
                octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
            )
            values = ((noise_values + 1) / 2) ** C.TERRAIN_AMPLITUDE
            color_array = self._get_terrain_color_vectorized(values)
        elif self.view_mode == "temperature":
            noise_values = perlin_noise_2d(
                self.p, (wx_grid + self.temp_seed) / C.NOISE_SCALE, (wy_grid + self.temp_seed) / C.NOISE_SCALE,
                octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
            )
            values = (noise_values + 1) / 2
            color_array = self._get_temperature_color_vectorized(values)
        else: # humidity
            noise_values = perlin_noise_2d(
                self.p, (wx_grid + self.humidity_seed) / C.NOISE_SCALE, (wy_grid + self.humidity_seed) / C.NOISE_SCALE,
                octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
            )
            values = (noise_values + 1) / 2
            color_array = self._get_humidity_color_vectorized(values)
        return pygame.surfarray.make_surface(color_array)

    def toggle_view_mode(self):
        """Switches view and clears the scaled cache, as it's now invalid."""
        if self.view_mode == "terrain": self.view_mode = "temperature"
        elif self.view_mode == "temperature": self.view_mode = "humidity"
        else: self.view_mode = "terrain"
        # --- NEW: Clear the scaled cache because the view mode changed.
        self.scaled_chunk_cache.clear()
        log.log(f"Event: View switched to '{self.view_mode}'. Scaled chunk cache cleared.")

    def generate_chunk_if_needed(self, chunk_x, chunk_y):
        """Generates a chunk for the CURRENT view mode if it's not in the main texture cache."""
        current_cache = self.chunk_texture_cache[self.view_mode]
        if (chunk_x, chunk_y) not in current_cache:
            current_cache[(chunk_x, chunk_y)] = self._generate_chunk_texture(chunk_x, chunk_y)

    # --- MAJOR CHANGE: The draw method is now much more efficient. ---
    def draw(self, screen, camera):
        """Draws the visible chunks, using a cache for scaled surfaces."""
        # --- NEW: If zoom changed, the entire scaled cache is invalid. Clear it. ---
        if camera.zoom_changed:
            self.scaled_chunk_cache.clear()
            camera.zoom_changed = False # Reset the flag

        top_left_wx, top_left_wy = camera.screen_to_world(0, 0)
        bottom_right_wx, bottom_right_wy = camera.screen_to_world(C.SCREEN_WIDTH, C.SCREEN_HEIGHT)
        start_chunk_x = int(top_left_wx // C.CHUNK_SIZE_CM)
        end_chunk_x = int(bottom_right_wx // C.CHUNK_SIZE_CM)
        start_chunk_y = int(top_left_wy // C.CHUNK_SIZE_CM)
        end_chunk_y = int(bottom_right_wy // C.CHUNK_SIZE_CM)

        # Get the cache for the original, full-resolution textures for the current view mode.
        current_texture_cache = self.chunk_texture_cache[self.view_mode]
        
        # Calculate the required scaled size once.
        scaled_size = int(C.CHUNK_SIZE_CM * camera.zoom) + C.CHUNK_RENDER_OVERLAP_PIXELS
        if scaled_size < 1: return

        for cx in range(start_chunk_x, end_chunk_x + 1):
            for cy in range(start_chunk_y, end_chunk_y + 1):
                # Ensure the base texture is generated.
                self.generate_chunk_if_needed(cx, cy)
                
                chunk_key = (cx, cy)
                
                # --- NEW CACHING LOGIC ---
                # Check if a pre-scaled version of this chunk is in our scaled cache.
                if chunk_key in self.scaled_chunk_cache:
                    # If yes, use it directly.
                    scaled_chunk = self.scaled_chunk_cache[chunk_key]
                else:
                    # If no, get the original texture...
                    original_texture = current_texture_cache.get(chunk_key)
                    if not original_texture: continue
                    
                    # ...perform the EXPENSIVE scale operation ONCE...
                    scaled_chunk = pygame.transform.scale(original_texture, (scaled_size, scaled_size))
                    
                    # ...and SAVE the result in the scaled cache for next time.
                    self.scaled_chunk_cache[chunk_key] = scaled_chunk
                
                # Blit the (now cached) scaled chunk to the screen.
                chunk_screen_pos = camera.world_to_screen(cx * C.CHUNK_SIZE_CM, cy * C.CHUNK_SIZE_CM)
                screen.blit(scaled_chunk, chunk_screen_pos)