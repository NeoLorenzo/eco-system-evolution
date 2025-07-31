# environment.py

import pygame
import numpy as np
import noise
import constants as C
from numpy_noise import perlin_noise_2d

class Environment:
    def __init__(self):
        self.temp_seed = C.TEMP_NOISE_SEED
        self.terrain_seed = C.TERRAIN_NOISE_SEED
        self.humidity_seed = C.HUMIDITY_NOISE_SEED
        self.view_mode = "terrain"
        self.caches = { "terrain": {}, "temperature": {}, "humidity": {} }

        # --- NEW: Create the master permutation table ---
        p = np.arange(256, dtype=int)
        np.random.seed(self.terrain_seed) # Use a seed for reproducibility
        np.random.shuffle(p)
        self.p = np.stack([p, p]).flatten() # Store the flattened table

        print(f"Environment initialized with multi-cache rendering. Default view: {self.view_mode}")
    
    def get_temperature(self, x, y):
        """Calculates the temperature at a single world coordinate using the consistent NumPy noise."""
        # We must pass NumPy arrays, even for a single point
        wx_grid, wy_grid = np.array([x]), np.array([y])
        
        noise_value = perlin_noise_2d(
            self.p, (wx_grid + self.temp_seed) / C.NOISE_SCALE, (wy_grid + self.temp_seed) / C.NOISE_SCALE,
            octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
        )
        return (noise_value[0] + 1) / 2

    def get_elevation(self, x, y):
        """Calculates the elevation at a single world coordinate using the consistent NumPy noise."""
        wx_grid, wy_grid = np.array([x]), np.array([y])

        noise_value = perlin_noise_2d(
            self.p, wx_grid / C.NOISE_SCALE, wy_grid / C.NOISE_SCALE,
            octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
        )
        normalized_value = (noise_value[0] + 1) / 2
        return max(0.0, min(1.0, normalized_value ** C.TERRAIN_AMPLITUDE))

    def get_humidity(self, x, y):
        """Calculates the humidity at a single world coordinate using the consistent NumPy noise."""
        wx_grid, wy_grid = np.array([x]), np.array([y])

        noise_value = perlin_noise_2d(
            self.p, (wx_grid + self.humidity_seed) / C.NOISE_SCALE, (wy_grid + self.humidity_seed) / C.NOISE_SCALE,
            octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
        )
        return (noise_value[0] + 1) / 2

    # --- NEW VECTORIZED COLOR MAPPERS (For fast chunk generation) ---

    def _get_terrain_color_vectorized(self, elevation_values):
        """Vectorized version of get_terrain_color."""
        # Start with a black canvas
        colors = np.zeros((*elevation_values.shape, 3), dtype=np.uint8)
        
        # Define masks for each terrain type
        water_mask = elevation_values < C.TERRAIN_WATER_LEVEL
        sand_mask = (elevation_values >= C.TERRAIN_WATER_LEVEL) & (elevation_values < C.TERRAIN_SAND_LEVEL)
        grass_mask = (elevation_values >= C.TERRAIN_SAND_LEVEL) & (elevation_values < C.TERRAIN_GRASS_LEVEL)
        dirt_mask = (elevation_values >= C.TERRAIN_GRASS_LEVEL) & (elevation_values < C.TERRAIN_DIRT_LEVEL)
        mountain_mask = elevation_values >= C.TERRAIN_DIRT_LEVEL

        # Apply colors based on masks using NumPy broadcasting
        # For water, we interpolate between deep and shallow colors
        if np.any(water_mask):
            t = (elevation_values[water_mask] / C.TERRAIN_WATER_LEVEL)[..., np.newaxis]
            c1 = np.array(C.COLOR_DEEP_WATER)
            c2 = np.array(C.COLOR_SHALLOW_WATER)
            colors[water_mask] = (1 - t) * c1 + t * c2

        colors[sand_mask] = C.COLOR_SAND
        colors[grass_mask] = C.COLOR_GRASS
        colors[dirt_mask] = C.COLOR_DIRT
        colors[mountain_mask] = C.COLOR_MOUNTAIN
        
        return np.transpose(colors, (1, 0, 2)) # Transpose for correct pygame orientation

    def _get_temperature_color_vectorized(self, temp_values):
        """Vectorized version of get_temperature_color."""
        colors = np.zeros((*temp_values.shape, 3), dtype=np.uint8)
        
        # Define masks for each temperature range
        coldest_mask = temp_values < 0.25
        cold_mask = (temp_values >= 0.25) & (temp_values < 0.5)
        hot_mask = (temp_values >= 0.5) & (temp_values < 0.75)
        hottest_mask = temp_values >= 0.75

        # Apply colors using vectorized interpolation
        if np.any(coldest_mask):
            t = (temp_values[coldest_mask] / 0.25)[..., np.newaxis]
            colors[coldest_mask] = (1 - t) * np.array(C.COLOR_COLDEST) + t * np.array(C.COLOR_COLD)
        if np.any(cold_mask):
            t = ((temp_values[cold_mask] - 0.25) / 0.25)[..., np.newaxis]
            colors[cold_mask] = (1 - t) * np.array(C.COLOR_COLD) + t * np.array(C.COLOR_TEMPERATE)
        if np.any(hot_mask):
            t = ((temp_values[hot_mask] - 0.5) / 0.25)[..., np.newaxis]
            colors[hot_mask] = (1 - t) * np.array(C.COLOR_TEMPERATE) + t * np.array(C.COLOR_HOT)
        if np.any(hottest_mask):
            t = ((temp_values[hottest_mask] - 0.75) / 0.25)[..., np.newaxis]
            colors[hottest_mask] = (1 - t) * np.array(C.COLOR_HOT) + t * np.array(C.COLOR_HOTTEST)
            
        return np.transpose(colors, (1, 0, 2))

    def _get_humidity_color_vectorized(self, humidity_values):
        """Vectorized version of get_humidity_color."""
        colors = np.zeros((*humidity_values.shape, 3), dtype=np.uint8)
        t = humidity_values[..., np.newaxis]
        colors[:] = (1 - t) * np.array(C.COLOR_DRY) + t * np.array(C.COLOR_WET)
        return np.transpose(colors, (1, 0, 2))

    # --- CORE CHUNK GENERATION (Now using NumPy) ---

    def _generate_chunk_texture(self, chunk_x, chunk_y):
        """Generates the texture for a single chunk using a shared permutation table."""
        wx = np.linspace(chunk_x * C.CHUNK_SIZE_CM, (chunk_x + 1) * C.CHUNK_SIZE_CM, C.CHUNK_RESOLUTION)
        wy = np.linspace(chunk_y * C.CHUNK_SIZE_CM, (chunk_y + 1) * C.CHUNK_SIZE_CM, C.CHUNK_RESOLUTION)
        wx_grid, wy_grid = np.meshgrid(wx, wy)

        if self.view_mode == "terrain":
            # Pass the master permutation table 'self.p' into the function
            noise_values = perlin_noise_2d(
                self.p, wx_grid / C.NOISE_SCALE, wy_grid / C.NOISE_SCALE,
                octaves=C.NOISE_OCTAVES, persistence=C.NOISE_PERSISTENCE, lacunarity=C.NOISE_LACUNARITY
            )
            values = ((noise_values + 1) / 2) ** C.TERRAIN_AMPLITUDE
            color_array = self._get_terrain_color_vectorized(values)

        elif self.view_mode == "temperature":
            # Use coordinate offsets for different patterns
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

    # --- HELPER AND DRAWING METHODS (Unchanged) ---

    def toggle_view_mode(self):
        """Switches between 'terrain', 'temperature', and 'humidity' views."""
        if self.view_mode == "terrain": self.view_mode = "temperature"
        elif self.view_mode == "temperature": self.view_mode = "humidity"
        else: self.view_mode = "terrain"
        print(f"Event: View switched to '{self.view_mode}'.")

    def generate_chunk_if_needed(self, chunk_x, chunk_y):
        """Generates a chunk for the CURRENT view mode if it's not in its specific cache."""
        current_cache = self.caches[self.view_mode]
        if (chunk_x, chunk_y) not in current_cache:
            current_cache[(chunk_x, chunk_y)] = self._generate_chunk_texture(chunk_x, chunk_y)

    def draw(self, screen, camera):
        """Draws the visible chunks, ensuring they are generated if needed."""
        top_left_wx, top_left_wy = camera.screen_to_world(0, 0)
        bottom_right_wx, bottom_right_wy = camera.screen_to_world(C.SCREEN_WIDTH, C.SCREEN_HEIGHT)
        start_chunk_x = int(top_left_wx // C.CHUNK_SIZE_CM)
        end_chunk_x = int(bottom_right_wx // C.CHUNK_SIZE_CM)
        start_chunk_y = int(top_left_wy // C.CHUNK_SIZE_CM)
        end_chunk_y = int(bottom_right_wy // C.CHUNK_SIZE_CM)

        current_cache = self.caches[self.view_mode]

        for cx in range(start_chunk_x, end_chunk_x + 1):
            for cy in range(start_chunk_y, end_chunk_y + 1):
                self.generate_chunk_if_needed(cx, cy)
                
                chunk_texture = current_cache.get((cx, cy))
                if not chunk_texture: continue

                chunk_screen_pos = camera.world_to_screen(cx * C.CHUNK_SIZE_CM, cy * C.CHUNK_SIZE_CM)
                scaled_size = int(C.CHUNK_SIZE_CM * camera.zoom) + 2
                if scaled_size < 1: continue
                scaled_chunk = pygame.transform.scale(chunk_texture, (scaled_size, scaled_size))
                screen.blit(scaled_chunk, chunk_screen_pos)