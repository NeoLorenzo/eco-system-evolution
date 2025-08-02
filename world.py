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
        self.graveyard = []
        self.world_boundary = Rectangle(C.WORLD_WIDTH_CM / 2, C.WORLD_HEIGHT_CM / 2, C.WORLD_WIDTH_CM / 2, C.WORLD_HEIGHT_CM / 2)
        self.time_manager = TimeManager()
        
        # --- NEW: The scheduler for plant logic updates ---
        # A dictionary where keys are future simulation times (in seconds)
        # and values are lists of plants to update at that time.
        self.plant_update_schedule = {}
        self.animal_update_schedule = {}

        self.quadtree = QuadTree(self.world_boundary, C.QUADTREE_CAPACITY)
        
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
        self.plants.append(initial_plant)
        self.schedule_plant_update(initial_plant, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
        # --- CHANGE: Insert into quadtree ONCE at birth ---
        self.quadtree.insert(initial_plant)
        
        initial_animal = Animal(C.INITIAL_ANIMAL_POSITION[0], C.INITIAL_ANIMAL_POSITION[1])
        self.animals.append(initial_animal)
        self.schedule_animal_update(initial_animal, C.ANIMAL_UPDATE_TICK_SECONDS)
        # --- CHANGE: Insert into quadtree ONCE at birth ---
        self.quadtree.insert(initial_animal)
        log.log("World population complete.")

    def add_newborn(self, creature):
        self.newborns.append(creature)
        # --- CHANGE: Insert into quadtree IMMEDIATELY for correct interaction checks. ---
        self.quadtree.insert(creature)
        
        if isinstance(creature, Plant):
            self.plant_births_this_period += 1
            self.schedule_plant_update(creature, C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
        elif isinstance(creature, Animal):
            self.schedule_animal_update(creature, C.ANIMAL_UPDATE_TICK_SECONDS)

    def report_death(self, creature):
        """A creature calls this method when it dies to be counted."""
        self.graveyard.append(creature)
        # --- CHANGE: Remove from quadtree ONCE at death ---
        self.quadtree.remove(creature)
        if isinstance(creature, Plant):
            self.plant_deaths_this_period += 1
        elif isinstance(creature, Animal):
            self.animal_deaths_this_period += 1

    def update_creature_in_quadtree(self, creature):
        """Removes and re-inserts a creature to update its position in the quadtree."""
        self.quadtree.remove(creature)
        self.quadtree.insert(creature)

    def _process_housekeeping(self):
        """Handles adding newborns to the main lists and removing dead creatures."""
        # --- Housekeeping ---
        for dead_creature in self.graveyard:
            if isinstance(dead_creature, Plant):
                if dead_creature in self.plants: self.plants.remove(dead_creature)
            elif isinstance(dead_creature, Animal):
                if dead_creature in self.animals: self.animals.remove(dead_creature)
        self.graveyard.clear()

        # Process newborns
        for creature in self.newborns:
            if isinstance(creature, Plant):
                self.plants.append(creature)
            elif isinstance(creature, Animal):
                self.animals.append(creature)
            # Note: The quadtree insertion is now done in add_newborn()
        self.newborns.clear()

        # --- Population Statistics Logging ---
        if self.time_manager.total_sim_seconds - self.last_log_time_seconds >= C.UI_LOG_INTERVAL_SECONDS:
            self._print_population_statistics()
            self.last_log_time_seconds = self.time_manager.total_sim_seconds
            self.plant_births_this_period = 0
            self.plant_deaths_this_period = 0
            self.animal_deaths_this_period = 0

    def update_in_bulk(self, large_delta_time):
        """
        Processes all scheduled events within a large time window efficiently.
        This is the new main entry point for simulation logic from main.py.
        """
        start_time = self.time_manager.total_sim_seconds
        end_time = start_time + large_delta_time

        # --- Step 1: Gather all events within the time window ---
        events = {}
        
        # Gather plant events
        plant_keys_to_process = [t for t in self.plant_update_schedule.keys() if start_time <= t < end_time]
        for t in plant_keys_to_process:
            if t not in events: events[t] = []
            events[t].extend(self.plant_update_schedule.pop(t))

        # Gather animal events
        animal_keys_to_process = [t for t in self.animal_update_schedule.keys() if start_time <= t < end_time]
        for t in animal_keys_to_process:
            if t not in events: events[t] = []
            events[t].extend(self.animal_update_schedule.pop(t))

        # --- Step 2: Process events in strict chronological order ---
        sorted_event_times = sorted(events.keys())

        for event_time in sorted_event_times:
            # Set the world clock to the exact time of the current event
            self.time_manager.total_sim_seconds = event_time
            
            creatures_to_update = events[event_time]
            for creature in creatures_to_update:
                if creature.is_alive:
                    # Determine the correct time step for this creature's update
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

        # --- Step 3: Finalize the time update and clean up ---
        self.time_manager.total_sim_seconds = end_time
        self._process_housekeeping()

    def toggle_environment_view(self):
        self.environment.toggle_view_mode()
        self.camera.dirty = True
        self.camera.zoom_changed = True

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