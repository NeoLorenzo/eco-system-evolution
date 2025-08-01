#world.py

import pygame
from creatures import Plant, Animal
import constants as C
from camera import Camera
from environment import Environment
from ui import draw_loading_screen
from quadtree import QuadTree, Rectangle
from time_manager import TimeManager
import logger as log

class World:
    def __init__(self):
        log.log("Creating a new World...")
        self.camera = Camera()
        self.environment = Environment()
        self.plants = []
        self.animals = []
        self.newborns = []
        self.world_boundary = Rectangle(C.WORLD_WIDTH_CM / 2, C.WORLD_HEIGHT_CM / 2, C.WORLD_WIDTH_CM / 2, C.WORLD_HEIGHT_CM / 2)
        self.time_manager = TimeManager()
        
        self.quadtree = QuadTree(self.world_boundary, C.QUADTREE_CAPACITY)
        self.spatial_update_accumulator = 0.0
        
        # --- NEW: Add a tracker for the debug-focused creature ---
        self.debug_focused_creature_id = None
        
        self.last_log_time_seconds = 0.0 # RENAME for clarity
        self.plant_deaths_this_period = 0
        self.animal_deaths_this_period = 0
        self.plant_births_this_period = 0
        log.log("World created. Creature lists are empty.")

    def _rebuild_spatial_partition(self):
        """Creates a new quadtree and inserts all living creatures."""
        self.quadtree = QuadTree(self.world_boundary, C.QUADTREE_CAPACITY)
        all_creatures = self.plants + self.animals
        for creature in all_creatures:
            if creature.is_alive: # Only insert living creatures
                self.quadtree.insert(creature)

    def pre_generate_all_chunks(self, screen, font):
        """Generates all chunks for ALL view modes (Terrain, Temp, Humidity)."""
        log.log("Starting world pre-generation for all view modes...")
        total_chunks_x = int(C.WORLD_WIDTH_CM // C.CHUNK_SIZE_CM)
        total_chunks_y = int(C.WORLD_HEIGHT_CM // C.CHUNK_SIZE_CM)
        
        # We now have THREE maps to generate
        total_work = (total_chunks_x * total_chunks_y) * C.ENVIRONMENT_VIEW_MODE_COUNT
        work_done = 0

        # --- Loop 1: Generate Terrain ---
        # (Assumes starting view is 'terrain')
        for cx in range(total_chunks_x):
            for cy in range(total_chunks_y):
                pygame.event.pump()
                self.environment.generate_chunk_if_needed(cx, cy)
                work_done += 1
                if work_done % C.UI_LOADING_BAR_UPDATE_INTERVAL == 0:
                    draw_loading_screen(screen, font, work_done, total_work)
        
        # --- Loop 2: Generate Temperature ---
        self.environment.toggle_view_mode() # Switch to 'temperature'
        for cx in range(total_chunks_x):
            for cy in range(total_chunks_y):
                pygame.event.pump()
                self.environment.generate_chunk_if_needed(cx, cy)
                work_done += 1
                if work_done % C.UI_LOADING_BAR_UPDATE_INTERVAL == 0:
                    draw_loading_screen(screen, font, work_done, total_work)

        # --- Loop 3: Generate Humidity ---
        self.environment.toggle_view_mode() # Switch to 'humidity'
        for cx in range(total_chunks_x):
            for cy in range(total_chunks_y):
                pygame.event.pump()
                self.environment.generate_chunk_if_needed(cx, cy)
                work_done += 1
                if work_done % C.UI_LOADING_BAR_UPDATE_INTERVAL == 0 or work_done == total_work:
                    draw_loading_screen(screen, font, work_done, total_work)

        # IMPORTANT: Switch back to the default view mode ('terrain')
        self.environment.toggle_view_mode() 
        
        log.log(f"World pre-generation complete. {work_done} total chunk textures loaded.")

    def populate_world(self):
        log.log("Populating the world with initial creatures...")
        # Pass 'self' (the world instance) to the Plant constructor
        initial_plant = Plant(self, C.INITIAL_PLANT_POSITION[0], C.INITIAL_PLANT_POSITION[1])
        self.plants.append(initial_plant)
        # We can do the same for Animal later if we optimize it
        initial_animal = Animal(C.INITIAL_ANIMAL_POSITION[0], C.INITIAL_ANIMAL_POSITION[1])
        self.animals.append(initial_animal)
        log.log("World population complete.")

    def add_newborn(self, creature):
        self.newborns.append(creature)
        if isinstance(creature, Plant):
            self.plant_births_this_period += 1

    def report_death(self, creature):
        """A creature calls this method when it dies to be counted."""
        if isinstance(creature, Plant):
            self.plant_deaths_this_period += 1
        elif isinstance(creature, Animal):
            self.animal_deaths_this_period += 1

    def update(self, delta_time):
        if delta_time == 0: return
        
        # --- Tier 1: Spatial Partitioning (Slow Tick) ---
        self.spatial_update_accumulator += delta_time
        if self.spatial_update_accumulator >= C.SPATIAL_UPDATE_INTERVAL_SECONDS:
            self._rebuild_spatial_partition()
            self.spatial_update_accumulator = 0.0 # Reset accumulator

        # --- Tier 2: Individual Creature Logic (Fast Tick) ---
        # This logic runs on every single simulation tick.
        for plant in self.plants:
            plant.update(self, delta_time)
        for animal in self.animals:
            animal.update(self, delta_time)

        # --- Housekeeping (Now more efficient) ---
        dead_plants = [plant for plant in self.plants if not plant.is_alive]
        for plant in dead_plants:
            self.plants.remove(plant)

        dead_animals = [animal for animal in self.animals if not animal.is_alive]
        for animal in dead_animals:
            self.animals.remove(animal)

        for creature in self.newborns:
            if isinstance(creature, Plant):
                self.plants.append(creature)
            elif isinstance(creature, Animal):
                self.animals.append(creature)
        self.newborns.clear()

        # --- NEW: Population Statistics Logging ---
        if self.time_manager.total_sim_seconds - self.last_log_time_seconds >= C.UI_LOG_INTERVAL_SECONDS:
            self._print_population_statistics()
            self.last_log_time_seconds = self.time_manager.total_sim_seconds
            # Reset counters for the next period
            self.plant_births_this_period = 0
            self.plant_deaths_this_period = 0
            self.animal_deaths_this_period = 0

    def toggle_environment_view(self):
        self.environment.toggle_view_mode()
        self.camera.dirty = True

    def draw(self, screen):
        self.environment.draw(screen, self.camera)
        self.camera.draw_world_border(screen)
        for plant in self.plants:
            plant.draw(screen, self.camera)
        for animal in self.animals:
            animal.draw(screen, self.camera)
    
    def handle_click(self, screen_pos):
        """Handles a mouse click, printing a debug report and toggling focused logging."""
        world_x, world_y = self.camera.screen_to_world(screen_pos[0], screen_pos[1])

        # Check for clicked plants
        for plant in self.plants:
            dist_sq = (world_x - plant.x)**2 + (world_y - plant.y)**2
            if dist_sq <= plant.radius**2:
                log.log(f"Clicked on a plant at world coordinates ({int(plant.x)}, {int(plant.y)}).")
                
                # --- NEW: Toggle focused debug logging ---
                if self.debug_focused_creature_id == plant.id:
                    self.debug_focused_creature_id = None
                    log.log(f"DEBUG: Stopped focusing on Plant ID: {plant.id}. Detailed logs disabled.")
                else:
                    self.debug_focused_creature_id = plant.id
                    log.log(f"DEBUG: Now focusing on Plant ID: {plant.id}. Detailed logs enabled.")

                plant.print_debug_report()
                return
            
    def _print_population_statistics(self):
        """Prints a formatted summary of the world's population statistics."""
        current_day = self.time_manager.total_sim_seconds / C.SECONDS_PER_DAY
        log_period_days = C.UI_LOG_INTERVAL_SECONDS / C.SECONDS_PER_DAY
        
        log.log("\n--- Population Statistics ---")
        log.log(f"  > Report for Day {current_day:.1f} (covering the last {log_period_days:.1f} days)")
        log.log(f"  Living Plants: {len(self.plants):,}")
        log.log(f"  Living Animals: {len(self.animals):,}")
        log.log(f"  - Plant Births this Period: {self.plant_births_this_period:,}")
        log.log(f"  - Plant Deaths this Period: {self.plant_deaths_this_period:,}")
        log.log("---------------------------\n")