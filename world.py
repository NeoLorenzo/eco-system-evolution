#world.py

import pygame
import numpy as np
from creatures import Plant, Animal
import constants as C
from camera import Camera
from environment import Environment
from ui import draw_loading_screen
from quadtree import QuadTree, Rectangle
from time_manager import TimeManager
from plant_manager import PlantManager
import logger as log

class World:
    def __init__(self):
        log.log("Creating a new World...")
        self.camera = Camera()
        self.environment = Environment()
        self.plant_manager = PlantManager()
        self.animals = []
        self.newborns = []
        self.graveyard = []
        self.world_boundary = Rectangle(C.WORLD_WIDTH_CM / 2, C.WORLD_HEIGHT_CM / 2, C.WORLD_WIDTH_CM / 2, C.WORLD_HEIGHT_CM / 2)
        self.time_manager = TimeManager()
        
        # --- The scheduler for plant logic updates ---
        self.plant_update_schedule = {}
        self.animal_update_schedule = {}

        self.quadtree = QuadTree(self.world_boundary, C.QUADTREE_CAPACITY)
        
        # --- Global Competition Grid System ---
        self.next_competition_update_time = 0.0 # The sim time at which the next global update will occur.
        grid_width = int(C.WORLD_WIDTH_CM // C.LIGHT_GRID_CELL_SIZE_CM)
        grid_height = int(C.WORLD_HEIGHT_CM // C.LIGHT_GRID_CELL_SIZE_CM)
        # The light grid stores the height of the tallest canopy in each cell.
        self.light_grid = np.zeros((grid_width, grid_height), dtype=np.float32)
        # The root grid stores the summed root radius of all plants in each cell, as a proxy for density.
        self.root_grid = np.zeros((grid_width, grid_height), dtype=np.float32)
        log.log(f"Competition grids initialized with size ({grid_width}x{grid_height}).")

        self.debug_focused_creature_id = None
        self.max_plant_radius = 0.0 # The radius of the largest plant in the world, in cm.
        
        self.last_log_time_seconds = 0.0
        self.plant_deaths_this_period = 0
        self.animal_deaths_this_period = 0
        self.plant_births_this_period = 0
        log.log("World created. Creature lists are empty.")

    # --- Method to schedule a plant's next logic update ---
    def schedule_plant_update(self, plant, delay_seconds):
        """
        Schedules a plant to have its update logic run after a certain delay.
        It groups plants into hourly buckets to process them together.
        """
        # Calculate the future time for the update
        future_time = self.time_manager.total_sim_seconds + delay_seconds
        
        # Round the time down to the nearest hour. This is the "key" for our schedule dictionary.
        # All plants updating in the same hour will be grouped together.
        schedule_key = int(future_time / C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS) * C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS
        
        # If this is the first plant scheduled for this exact hour, create a new list for it.
        if schedule_key not in self.plant_update_schedule:
            self.plant_update_schedule[schedule_key] = []
            
        # Add the plant to the list for its scheduled update time.
        self.plant_update_schedule[schedule_key].append(plant)

    def schedule_animal_update(self, animal, delay_seconds):
        future_time = self.time_manager.total_sim_seconds + delay_seconds
        schedule_key = int(future_time / C.ANIMAL_UPDATE_TICK_SECONDS) * C.ANIMAL_UPDATE_TICK_SECONDS
        if schedule_key not in self.animal_update_schedule:
            self.animal_update_schedule[schedule_key] = []
        self.animal_update_schedule[schedule_key].append(animal)

    def pre_generate_all_chunks(self, screen, font):
        """Generates all chunks for ALL view modes (Terrain, Temp, Humidity)."""
        log.log("Starting world pre-generation for all view modes...")
        total_chunks_x = int(C.WORLD_WIDTH_CM // C.CHUNK_SIZE_CM)
        total_chunks_y = int(C.WORLD_HEIGHT_CM // C.CHUNK_SIZE_CM)
        
        total_work = (total_chunks_x * total_chunks_y) * C.ENVIRONMENT_VIEW_MODE_COUNT
        work_done = 0

        self.environment.toggle_view_mode() 
        self.environment.toggle_view_mode() 
        for cx in range(total_chunks_x):
            for cy in range(total_chunks_y):
                pygame.event.pump()
                self.environment.generate_chunk_if_needed(cx, cy)
                work_done += 1
                if work_done % C.UI_LOADING_BAR_UPDATE_INTERVAL == 0:
                    draw_loading_screen(screen, font, work_done, total_work)
        
        self.environment.toggle_view_mode() 
        for cx in range(total_chunks_x):
            for cy in range(total_chunks_y):
                pygame.event.pump()
                self.environment.generate_chunk_if_needed(cx, cy)
                work_done += 1
                if work_done % C.UI_LOADING_BAR_UPDATE_INTERVAL == 0:
                    draw_loading_screen(screen, font, work_done, total_work)

        self.environment.toggle_view_mode() 
        for cx in range(total_chunks_x):
            for cy in range(total_chunks_y):
                pygame.event.pump()
                self.environment.generate_chunk_if_needed(cx, cy)
                work_done += 1
                if work_done % C.UI_LOADING_BAR_UPDATE_INTERVAL == 0 or work_done == total_work:
                    draw_loading_screen(screen, font, work_done, total_work)

        self.environment.toggle_view_mode() 
        
        log.log(f"World pre-generation complete. {work_done} total chunk textures loaded.")

    def populate_world(self):
        log.log("Populating the world with initial creatures...")
        initial_plant = Plant(self, C.INITIAL_PLANT_POSITION[0], C.INITIAL_PLANT_POSITION[1])
        self.plant_manager.add_plant(initial_plant)
        self.schedule_plant_update(initial_plant, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
        self.quadtree.insert(initial_plant)
        
        initial_animal = Animal(C.INITIAL_ANIMAL_POSITION[0], C.INITIAL_ANIMAL_POSITION[1])
        self.animals.append(initial_animal)
        self.schedule_animal_update(initial_animal, C.ANIMAL_UPDATE_TICK_SECONDS)
        self.quadtree.insert(initial_animal)
        log.log("World population complete.")

    def add_newborn(self, creature):
        self.newborns.append(creature)
        self.quadtree.insert(creature)
        
        if isinstance(creature, Plant):
            self.plant_births_this_period += 1
            self.schedule_plant_update(creature, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
        elif isinstance(creature, Animal):
            self.schedule_animal_update(creature, C.ANIMAL_UPDATE_TICK_SECONDS)

    def report_death(self, creature):
        """A creature calls this method when it dies to be counted."""
        self.graveyard.append(creature)
        self.quadtree.remove(creature)
        if isinstance(creature, Plant):
            self.plant_deaths_this_period += 1
        elif isinstance(creature, Animal):
            self.animal_deaths_this_period += 1

    def update_creature_in_quadtree(self, creature):
        """Removes and re-inserts a creature to update its position in the quadtree."""
        self.quadtree.remove(creature)
        self.quadtree.insert(creature)

    def _update_max_plant_radius(self):
        """
        Recalculates the largest plant radius in the world using NumPy for efficiency.
        """
        pm = self.plant_manager
        if pm.count == 0:
            self.max_plant_radius = 0.0
        else:
            # Use np.max on the radii array for a fast, vectorized operation.
            self.max_plant_radius = np.max(pm.arrays['radii'][:pm.count])

    def _populate_competition_grids(self):
        """Pass 1: Populate the light and root grids with data from all plants."""
        self.light_grid.fill(0)
        self.root_grid.fill(0)
        pm = self.plant_manager

        # Iterate by index over the NumPy arrays, the new source of truth.
        for i in range(pm.count):
            radius = pm.arrays['radii'][i]
            if radius <= 0: continue

            x, y = pm.arrays['positions'][i]
            height = pm.arrays['heights'][i]
            root_radius = pm.arrays['root_radii'][i]

            # --- Rasterize Canopy for Light Grid (Vectorized) ---
            min_gx = int(max(0, (x - radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gx = int(min(self.light_grid.shape[0] - 1, (x + radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            min_gy = int(max(0, (y - radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gy = int(min(self.light_grid.shape[1] - 1, (y + radius) / C.LIGHT_GRID_CELL_SIZE_CM))

            # Create a grid of coordinates for the bounding box of the plant
            gx_range = np.arange(min_gx, max_gx + 1)
            gy_range = np.arange(min_gy, max_gy + 1)
            gx_grid, gy_grid = np.meshgrid(gx_range, gy_range)

            # Calculate the world coordinates of the center of each grid cell
            cell_wx = (gx_grid + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM
            cell_wy = (gy_grid + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM

            # Find all cells within the plant's radius
            dist_sq = (x - cell_wx)**2 + (y - cell_wy)**2
            cells_inside_canopy_mask = dist_sq <= radius**2

            # Get the grid indices where the condition is true
            gx_indices = gx_grid[cells_inside_canopy_mask]
            gy_indices = gy_grid[cells_inside_canopy_mask]

            # Update the light grid using advanced indexing.
            # We take the maximum of the current value and the plant's height.
            current_max_heights = self.light_grid[gx_indices, gy_indices]
            self.light_grid[gx_indices, gy_indices] = np.maximum(current_max_heights, height)

            # --- Rasterize Roots for Root Grid (Vectorized) ---
            min_gx_root = int(max(0, (x - root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gx_root = int(min(self.root_grid.shape[0] - 1, (x + root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            min_gy_root = int(max(0, (y - root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gy_root = int(min(self.root_grid.shape[1] - 1, (y + root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))

            # Create a grid of coordinates for the bounding box of the roots
            gx_range_root = np.arange(min_gx_root, max_gx_root + 1)
            gy_range_root = np.arange(min_gy_root, max_gy_root + 1)
            gx_grid_root, gy_grid_root = np.meshgrid(gx_range_root, gy_range_root)

            # Calculate the world coordinates of the center of each grid cell
            cell_wx_root = (gx_grid_root + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM
            cell_wy_root = (gy_grid_root + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM

            # Find all cells within the plant's root radius
            dist_sq_root = (x - cell_wx_root)**2 + (y - cell_wy_root)**2
            cells_inside_roots_mask = dist_sq_root <= root_radius**2

            # Get the grid indices where the condition is true
            gx_indices_root = gx_grid_root[cells_inside_roots_mask]
            gy_indices_root = gy_grid_root[cells_inside_roots_mask]

            # Add the root radius to all covered cells using advanced indexing
            self.root_grid[gx_indices_root, gy_indices_root] += root_radius

    def _calculate_plant_competition(self):
        """Pass 2: Use the populated grids to calculate competition for each plant."""
        cell_area = C.LIGHT_GRID_CELL_SIZE_CM ** 2
        pm = self.plant_manager

        # Create temporary arrays to store the results of our calculations.
        shaded_canopy_areas = np.zeros(pm.count, dtype=np.float32)
        overlapped_root_areas = np.zeros(pm.count, dtype=np.float32)

        # Iterate by index to read from NumPy and write to the temporary arrays.
        for i in range(pm.count):
            radius = pm.arrays['radii'][i]
            if radius <= 0: continue

            x, y = pm.arrays['positions'][i]
            height = pm.arrays['heights'][i]
            root_radius = pm.arrays['root_radii'][i]

            # --- Calculate Shaded Area (Vectorized) ---
            min_gx = int(max(0, (x - radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gx = int(min(self.light_grid.shape[0] - 1, (x + radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            min_gy = int(max(0, (y - radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gy = int(min(self.light_grid.shape[1] - 1, (y + radius) / C.LIGHT_GRID_CELL_SIZE_CM))

            # Create a grid of coordinates for the bounding box of the plant
            gx_range = np.arange(min_gx, max_gx + 1)
            gy_range = np.arange(min_gy, max_gy + 1)
            gx_grid, gy_grid = np.meshgrid(gx_range, gy_range)

            # Calculate the world coordinates of the center of each grid cell
            cell_wx = (gx_grid + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM
            cell_wy = (gy_grid + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM

            # Find all cells within the plant's radius
            dist_sq = (x - cell_wx)**2 + (y - cell_wy)**2
            cells_inside_canopy_mask = dist_sq <= radius**2

            # Get the grid indices where the condition is true
            gx_indices = gx_grid[cells_inside_canopy_mask]
            gy_indices = gy_grid[cells_inside_canopy_mask]

            # From the cells inside the canopy, find which ones are shaded
            canopy_heights_on_grid = self.light_grid[gx_indices, gy_indices]
            shaded_cells_mask = height < canopy_heights_on_grid

            # The total shaded area is the number of shaded cells times the area of a cell
            num_shaded_cells = np.sum(shaded_cells_mask)
            shaded_canopy_areas[i] = num_shaded_cells * cell_area

            # --- Calculate Root Overlap (Vectorized) ---
            min_gx_root = int(max(0, (x - root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gx_root = int(min(self.root_grid.shape[0] - 1, (x + root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            min_gy_root = int(max(0, (y - root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))
            max_gy_root = int(min(self.root_grid.shape[1] - 1, (y + root_radius) / C.LIGHT_GRID_CELL_SIZE_CM))

            my_root_area = root_radius**2 * np.pi

            # Create a grid of coordinates for the bounding box of the roots
            gx_range_root = np.arange(min_gx_root, max_gx_root + 1)
            gy_range_root = np.arange(min_gy_root, max_gy_root + 1)
            gx_grid_root, gy_grid_root = np.meshgrid(gx_range_root, gy_range_root)

            # Calculate the world coordinates of the center of each grid cell
            cell_wx_root = (gx_grid_root + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM
            cell_wy_root = (gy_grid_root + 0.5) * C.LIGHT_GRID_CELL_SIZE_CM

            # Find all cells within the plant's root radius
            dist_sq_root = (x - cell_wx_root)**2 + (y - cell_wy_root)**2
            cells_inside_roots_mask = dist_sq_root <= root_radius**2

            # Get the grid indices where the condition is true
            gx_indices_root = gx_grid_root[cells_inside_roots_mask]
            gy_indices_root = gy_grid_root[cells_inside_roots_mask]

            # Get the total root pressure from the grid for all cells under this plant's roots
            total_pressures = self.root_grid[gx_indices_root, gy_indices_root]

            # Find which of these cells are actually being competed for
            competed_cells_mask = total_pressures > root_radius

            # Calculate the overlap ratio ONLY for the cells with competition
            competed_pressures = total_pressures[competed_cells_mask]
            overlap_ratios = (competed_pressures - root_radius) / competed_pressures

            # The total overlapped area is the sum of the ratios multiplied by the area of a cell
            overlapped_root_areas[i] = np.sum(overlap_ratios) * cell_area
            
            # Clamp values to be safe
            shaded_canopy_areas[i] = min(shaded_canopy_areas[i], radius**2 * np.pi)
            overlapped_root_areas[i] = min(overlapped_root_areas[i], my_root_area)

                # --- Final Assignment Step ---
        # Now, assign the calculated values from our temporary arrays.
        # Step 1: Bulk copy the results into the PlantManager's NumPy arrays.
        pm.arrays['overlapped_root_areas'][:pm.count] = overlapped_root_areas
        pm.arrays['shaded_canopy_areas'][:pm.count] = shaded_canopy_areas

        # Step 2: Assign values to the individual Python objects (this will be phased out later).
        for i in range(pm.count):
            pm.plants[i].shaded_canopy_area = shaded_canopy_areas[i]
            pm.plants[i].overlapped_root_area = overlapped_root_areas[i]

    def _process_housekeeping(self):
        """Handles adding newborns to the main lists and removing dead creatures."""
        # --- Housekeeping ---
        for dead_creature in self.graveyard:
            if isinstance(dead_creature, Plant):
                self.plant_manager.remove_plant(dead_creature)
            elif isinstance(dead_creature, Animal):
                if dead_creature in self.animals: self.animals.remove(dead_creature)
        self.graveyard.clear()

        # Process newborns
        for creature in self.newborns:
            if isinstance(creature, Plant):
                self.plant_manager.add_plant(creature)
            elif isinstance(creature, Animal):
                self.animals.append(creature)
        self.newborns.clear()

        # --- Population Statistics Logging & World State Update ---
        if self.time_manager.total_sim_seconds - self.last_log_time_seconds >= C.UI_LOG_INTERVAL_SECONDS:
            self._print_population_statistics()
            self.last_log_time_seconds = self.time_manager.total_sim_seconds
            self.plant_births_this_period = 0
            self.plant_deaths_this_period = 0
            self.animal_deaths_this_period = 0
        
        self._update_max_plant_radius()

    def update_in_bulk(self, large_delta_time):
        """
        Processes all scheduled events within a large time window efficiently.
        This is the new main entry point for simulation logic from main.py.
        """
        # --- Perform vectorized calculations once before the main loop ---
        self.plant_manager.update_aging_efficiencies()
        self.plant_manager.update_hydraulic_efficiencies()
        self.plant_manager.update_environmental_efficiencies(self.environment)
        self.plant_manager.update_soil_efficiencies()
        self.plant_manager.update_photosynthesis_gains()
        self.plant_manager.update_metabolism_costs(self.environment)

        start_time = self.time_manager.total_sim_seconds
        end_time = start_time + large_delta_time

        # --- Process global updates that fall within this time slice ---
        while self.next_competition_update_time < end_time:
            # Set the clock to the precise time of this global event to maintain temporal accuracy
            self.time_manager.total_sim_seconds = self.next_competition_update_time
            log.log(f"--- Performing Global Competition Update at Day {self.time_manager.total_sim_seconds / C.SECONDS_PER_DAY:.1f} ---")
            self._populate_competition_grids()
            self._calculate_plant_competition()
            # Schedule the next update
            self.next_competition_update_time += C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS
        
        # Restore the clock to where it was before we started processing individual events
        self.time_manager.total_sim_seconds = start_time

        # --- Continuously process individual creature events in a loop until the time window is filled ---
        while True:
            # Find the time of the very next scheduled event, if any
            next_plant_time = min(self.plant_update_schedule.keys()) if self.plant_update_schedule else float('inf')
            next_animal_time = min(self.animal_update_schedule.keys()) if self.animal_update_schedule else float('inf')
            next_event_time = min(next_plant_time, next_animal_time)

            # If the next event is outside our current time slice, stop processing for this frame.
            if next_event_time >= end_time:
                break

            # Set the world clock to the exact time of the current event
            self.time_manager.total_sim_seconds = next_event_time
            
            # Pop the creatures scheduled for this exact time from the schedule
            creatures_to_update = []
            if next_event_time in self.plant_update_schedule:
                creatures_to_update.extend(self.plant_update_schedule.pop(next_event_time))
            if next_event_time in self.animal_update_schedule:
                creatures_to_update.extend(self.animal_update_schedule.pop(next_event_time))

            # Process the creatures for this event time
            for creature in creatures_to_update:
                if creature.is_alive:
                    if isinstance(creature, Plant):
                        time_step = C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS
                        creature.update(self, time_step)
                        if creature.is_alive:
                            self.schedule_plant_update(creature, time_step)
                    elif isinstance(creature, Animal):
                        time_step = C.ANIMAL_UPDATE_TICK_SECONDS
                        creature.update(self, time_step)
                        if creature.is_alive:
                            self.schedule_animal_update(creature, time_step)
        
        # --- Finalize the time update and clean up ---
        self.time_manager.total_sim_seconds = end_time
        self._process_housekeeping()

    def toggle_environment_view(self):
        self.environment.toggle_view_mode()
        self.camera.dirty = True
        self.camera.zoom_changed = True

    def draw(self, screen):
        self.environment.draw(screen, self.camera)
        self.camera.draw_world_border(screen)
        for plant in self.plant_manager:
            plant.draw(screen, self.camera)
        for animal in self.animals:
            animal.draw(screen, self.camera)
    
    def handle_click(self, screen_pos):
        """Handles a mouse click, printing a debug report and toggling focused logging."""
        world_x, world_y = self.camera.screen_to_world(screen_pos[0], screen_pos[1])
        pm = self.plant_manager

        # Iterate by index over the NumPy arrays to perform the collision check.
        for i in range(pm.count):
            x, y = pm.arrays['positions'][i]
            radius = pm.arrays['radii'][i]
            dist_sq = (world_x - x)**2 + (world_y - y)**2
            if dist_sq <= radius**2:
                # Once a match is found, get the corresponding object for its ID.
                plant = pm.plants[i]
                log.log(f"Clicked on a plant at world coordinates ({int(x)}, {int(y)}).")
                
                if self.debug_focused_creature_id == plant.id:
                    self.debug_focused_creature_id = None
                    log.log(f"DEBUG: Stopped focusing on Plant ID: {plant.id}. Detailed logs disabled.")
                else:
                    self.debug_focused_creature_id = plant.id
                    log.log(f"DEBUG: Now focusing on Plant ID: {plant.id}. Detailed logs enabled.")
                return
            
    def _print_population_statistics(self):
        """Prints a formatted summary of the world's population statistics."""
        current_day = self.time_manager.total_sim_seconds / C.SECONDS_PER_DAY
        log_period_days = C.UI_LOG_INTERVAL_SECONDS / C.SECONDS_PER_DAY
        
        log.log("\n--- Population Statistics ---")
        log.log(f"  > Report for Day {current_day:.1f} (covering the last {log_period_days:.1f} days)")
        log.log(f"  Living Plants: {len(self.plant_manager):,}")
        log.log(f"  Living Animals: {len(self.animals):,}")
        log.log(f"  - Plant Births this Period: {self.plant_births_this_period:,}")
        log.log(f"  - Plant Deaths this Period: {self.plant_deaths_this_period:,}")
        log.log("---------------------------\n")