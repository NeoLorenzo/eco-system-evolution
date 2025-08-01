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
        
        # --- NEW: The scheduler for plant logic updates ---
        # A dictionary where keys are future simulation times (in seconds)
        # and values are lists of plants to update at that time.
        self.plant_update_schedule = {}
        
        self.quadtree = QuadTree(self.world_boundary, C.QUADTREE_CAPACITY)
        self.spatial_update_accumulator = 0.0
        
        self.debug_focused_creature_id = None
        
        self.last_log_time_seconds = 0.0
        self.plant_deaths_this_period = 0
        self.animal_deaths_this_period = 0
        self.plant_births_this_period = 0
        log.log("World created. Creature lists are empty.")

    # --- NEW: Method to schedule a plant's next logic update ---
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

    def _rebuild_spatial_partition(self):
        """Creates a new quadtree and inserts all living creatures."""
        self.quadtree = QuadTree(self.world_boundary, C.QUADTREE_CAPACITY)
        all_creatures = self.plants + self.animals
        for creature in all_creatures:
            if creature.is_alive:
                self.quadtree.insert(creature)

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
        self.plants.append(initial_plant)
        # --- CHANGE: Schedule the first plant's update ---
        self.schedule_plant_update(initial_plant, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
        
        initial_animal = Animal(C.INITIAL_ANIMAL_POSITION[0], C.INITIAL_ANIMAL_POSITION[1])
        self.animals.append(initial_animal)
        log.log("World population complete.")

    def add_newborn(self, creature):
        self.newborns.append(creature)
        if isinstance(creature, Plant):
            self.plant_births_this_period += 1
            # --- CHANGE: Schedule the newborn plant's first update ---
            self.schedule_plant_update(creature, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)

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
            self.spatial_update_accumulator = 0.0

        # --- Tier 2: Scheduled Plant Logic (Fast Tick, Efficient) ---
        # --- MAJOR CHANGE: This replaces the inefficient loop ---
        
        # Get the key for the current time bucket (rounded down to the hour)
        current_time_key = int(self.time_manager.total_sim_seconds / C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS) * C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS
        
        # Check if there are any plants scheduled to be updated in this bucket
        if current_time_key in self.plant_update_schedule:
            # Get the list of plants and remove it from the schedule to prevent re-processing
            plants_to_update = self.plant_update_schedule.pop(current_time_key)
            
            for plant in plants_to_update:
                # A plant might have died since it was scheduled, so we double-check.
                if plant.is_alive:
                    # Call the plant's logic. It will run its full hourly cycle.
                    plant.update(self, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
                    # IMPORTANT: Re-schedule the plant for its next update in one hour.
                    self.schedule_plant_update(plant, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)

        # --- Tier 3: Animal Logic (Still runs every tick for now) ---
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

        # --- Population Statistics Logging (No Change) ---
        if self.time_manager.total_sim_seconds - self.last_log_time_seconds >= C.UI_LOG_INTERVAL_SECONDS:
            self._print_population_statistics()
            self.last_log_time_seconds = self.time_manager.total_sim_seconds
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

        for plant in self.plants:
            dist_sq = (world_x - plant.x)**2 + (world_y - plant.y)**2
            if dist_sq <= plant.radius**2:
                log.log(f"Clicked on a plant at world coordinates ({int(plant.x)}, {int(plant.y)}).")
                
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