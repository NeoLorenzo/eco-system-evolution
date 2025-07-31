# creatures.py (YOUR LOGIC, WITH FULL DEBUG MESSAGES)

import pygame
import constants as C
import random
import math
from quadtree import Rectangle
from genes import PlantGenes

def lerp_color(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(start + (end - start) * t) for start, end in zip(c1, c2))

class Creature:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.energy = C.CREATURE_INITIAL_ENERGY
        self.age = 0
        self.is_alive = True
        self.id = random.randint(C.CREATURE_ID_MIN, C.CREATURE_ID_MAX)
        print(f"DEBUG: Creature {self.id} created at ({x:.0f}, {y:.0f}). Initial Energy: {self.energy}")

    def die(self, world, cause):
        if self.is_alive:
            print(f"DEBUG: Creature {self.id} is dying from: {cause}")
            self.is_alive = False
            world.report_death(self)

    def can_reproduce(self):
        return self.energy >= C.CREATURE_REPRODUCTION_ENERGY_THRESHOLD

    def reproduce(self, world, quadtree):
        print(f"DEBUG ({self.id}): Attempting to reproduce.")
        self.energy -= C.CREATURE_REPRODUCTION_ENERGY_COST
        spread_area = Rectangle(self.x, self.y, C.PLANT_SEED_SPREAD_RADIUS_CM, C.PLANT_SEED_SPREAD_RADIUS_CM)
        neighbors_in_spread_area = quadtree.query(spread_area, [])
        best_location = None
        least_neighbors = float('inf')
        for i in range(C.PLANT_REPRODUCTION_ATTEMPTS):
            spawn_angle = random.uniform(0, 2 * math.pi)
            spawn_dist = random.uniform(0, C.PLANT_SEED_SPREAD_RADIUS_CM)
            candidate_x = self.x + spawn_dist * math.cos(spawn_angle)
            candidate_y = self.y + spawn_dist * math.sin(spawn_angle)
            is_valid = True
            current_neighbors = 0
            for neighbor in neighbors_in_spread_area:
                if isinstance(neighbor, Plant):
                    new_plant_personal_space = (1.0 * neighbor.genes.core_radius_factor) * C.PLANT_CORE_PERSONAL_SPACE_FACTOR
                    min_dist = new_plant_personal_space + neighbor.get_personal_space_radius()
                    dist_sq = (candidate_x - neighbor.x)**2 + (candidate_y - neighbor.y)**2
                    if dist_sq < min_dist**2:
                        is_valid = False
                        break
                    crowd_dist_sq = (candidate_x - neighbor.x)**2 + (candidate_y - neighbor.y)**2
                    if crowd_dist_sq < C.PLANT_CROWDED_RADIUS_CM**2:
                        current_neighbors += 1
            if not is_valid:
                continue
            if current_neighbors < least_neighbors:
                least_neighbors = current_neighbors
                best_location = (candidate_x, candidate_y)

        if best_location:
            print(f"DEBUG ({self.id}): Found a valid spawn location.")
            return Plant(world, best_location[0], best_location[1])
        
        print(f"DEBUG ({self.id}): Failed to find a valid spawn location.")
        self.energy += C.CREATURE_REPRODUCTION_ENERGY_COST
        return None

class Plant(Creature):
    def __init__(self, world, x, y):
        super().__init__(x, y)
        print(f"DEBUG ({self.id}): Initializing as a Plant.")
        self.genes = PlantGenes()
        self.radius = C.PLANT_INITIAL_RADIUS_CM
        self.root_radius = C.PLANT_INITIAL_ROOT_RADIUS_CM
        self.reproduction_cooldown = 0.0
        self.competition_factor = 1.0
        self.competition_update_accumulator = 0.0
        self.is_mature = self.check_if_mature()
        # This accumulator will store unprocessed simulation time.
        self.logic_update_accumulator = 0.0 # units: seconds

        self.elevation = world.environment.get_elevation(self.x, self.y)
        self.soil_type = self.get_soil_type(self.elevation)
        print(f"DEBUG ({self.id}): Environment check: Elevation={self.elevation:.2f}, Soil='{self.soil_type}'")
        
        if self.soil_type is None:
            print(f"DEBUG ({self.id}): Spawning on invalid terrain. Marking for death.")
            self.is_alive = False
            self.energy = 0
            return

        self.temperature = world.environment.get_temperature(self.x, self.y)
        self.humidity = world.environment.get_humidity(self.x, self.y)
        self.environment_eff = self.calculate_environment_efficiency(self.temperature, self.humidity)
        print(f"DEBUG ({self.id}): Caching env_eff: {self.environment_eff:.3f}")

    def check_if_mature(self):
        return self.radius >= self.genes.max_radius

    def get_core_radius(self):
        return self.radius * self.genes.core_radius_factor

    def get_personal_space_radius(self):
        return self.get_core_radius() * C.PLANT_CORE_PERSONAL_SPACE_FACTOR

    def get_soil_type(self, elevation):
        if C.TERRAIN_WATER_LEVEL <= elevation < C.TERRAIN_SAND_LEVEL: return "sand"
        elif C.TERRAIN_SAND_LEVEL <= elevation < C.TERRAIN_GRASS_LEVEL: return "grass"
        elif C.TERRAIN_GRASS_LEVEL <= elevation < C.TERRAIN_DIRT_LEVEL: return "dirt"
        else: return None

    def calculate_competition_factor(self, quadtree):
        competition_area = Rectangle(self.x, self.y, C.PLANT_COMPETITION_RADIUS_CM, C.PLANT_COMPETITION_RADIUS_CM)
        neighbors = quadtree.query(competition_area, [])
        total_competition_mass = 0
        for neighbor in neighbors:
            if neighbor is self: continue
            total_competition_mass += neighbor.radius**2
        competition_factor = 1 / (1 + total_competition_mass * C.PLANT_COMPETITION_MASS_FACTOR)
        return competition_factor

    def update(self, world, delta_time):
        if not self.is_alive: return

        # Age must always use the raw delta_time to reflect total elapsed sim time
        self.age += delta_time
        # Add the elapsed sim time to our accumulator
        self.logic_update_accumulator += delta_time

        # If not enough time has accumulated for even one logic tick, exit early.
        if self.logic_update_accumulator < C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS:
            return

        # --- REFACTORED LOGIC BLOCK ---
        # This block now runs only when enough time has accumulated.
        
        ticks_to_process = int(self.logic_update_accumulator // C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS)
        
        # --- NEW: Debug log to show how many ticks will be processed ---
        print(f"\n--- PLANT {self.id} LOGIC (Age: {self.age/C.SECONDS_PER_DAY:.1f} days) ---")
        print(f"  Accumulator: {self.logic_update_accumulator:.2f}s. Processing {ticks_to_process} tick(s) of {C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS}s each.")

        # Process the accumulated time in fixed chunks (internal ticks)
        for i in range(ticks_to_process):
            # The duration for this single, fixed-step calculation is now a constant.
            internal_tick = C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS
            
            # --- NEW: Debug log for the state of each internal tick ---
            if i < 3: # Only print the first few ticks to avoid spam
                 print(f"\n  - Internal Tick {i+1}/{ticks_to_process} (Duration: {internal_tick:.0f}s) -")
                 print(f"    State: Energy={self.energy:.2f}, Radius={self.radius:.2f}")

            # --- CORE BIOLOGY LOGIC (Calculations now use the fixed 'internal_tick') ---
            self.reproduction_cooldown = max(0, self.reproduction_cooldown - internal_tick)
            self.competition_update_accumulator += internal_tick
            
            if self.energy <= 0:
                self.die(world, "starvation")
                # If the plant dies, it shouldn't process more ticks.
                # We subtract the time we *did* process and exit.
                self.logic_update_accumulator -= internal_tick * (i + 1)
                print(f"  Plant {self.id} died mid-processing. Halting logic.")
                return

            if self.competition_update_accumulator >= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS:
                self.competition_factor = self.calculate_competition_factor(world.quadtree)
                self.competition_update_accumulator = 0.0

            max_soil_eff = self.genes.soil_efficiency.get(self.soil_type, 0)
            root_to_canopy_ratio = self.root_radius / (self.radius + 1)
            soil_eff = max_soil_eff * min(1.0, root_to_canopy_ratio * C.PLANT_ROOT_EFFICIENCY_FACTOR)
            aging_efficiency = math.exp(-(self.age / C.PLANT_EXPECTED_LIFESPAN_SECONDS))
            canopy_area = math.pi * self.radius**2
            root_area = math.pi * self.root_radius**2
            photosynthesis_gain = canopy_area * C.PLANT_PHOTOSYNTHESIS_PER_AREA * self.environment_eff * soil_eff * self.competition_factor * aging_efficiency * internal_tick
            metabolism_cost = (canopy_area + root_area) * C.PLANT_METABOLISM_PER_AREA * self.environment_eff * internal_tick
            net_energy_production = photosynthesis_gain - metabolism_cost

            self.energy += net_energy_production
            
            if i < 3:
                print(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net={net_energy_production:.4f}")

            if self.is_mature:
                if self.can_reproduce() and self.reproduction_cooldown <= 0 and not self.is_overcrowded(world.quadtree):
                    new_plant = self.reproduce(world, world.quadtree)
                    if new_plant:
                        world.add_newborn(new_plant)
                        self.reproduction_cooldown = C.PLANT_REPRODUCTION_COOLDOWN_SECONDS
            
            elif net_energy_production > 0:
                if i < 3: print(f"    Growth Check (Surplus of {net_energy_production:.4f} J):")
                added_biomass_area = net_energy_production / C.PLANT_BIOMASS_ENERGY_COST
                if i < 3: print(f"      - Surplus converts to {added_biomass_area:.4f} cm^2 of new biomass.")

                grows_canopy = (soil_eff >= self.environment_eff)
                if grows_canopy:
                    if i < 3: print(f"      - Decision: Growing CANOPY. Old Radius: {self.radius:.4f}")
                    new_canopy_area = canopy_area + added_biomass_area
                    self.radius = math.sqrt(new_canopy_area / math.pi)
                    if i < 3: print(f"      - New Radius: {self.radius:.4f}")
                else:
                    if i < 3: print(f"      - Decision: Growing ROOTS. Old Root Radius: {self.root_radius:.4f}")
                    new_root_area = root_area + added_biomass_area
                    self.root_radius = math.sqrt(new_root_area / math.pi)
                    if i < 3: print(f"      - New Root Radius: {self.root_radius:.4f}")
                
                if not self.is_mature and self.check_if_mature():
                    self.is_mature = True
                    print(f"DEBUG ({self.id}): State changed to MATURE at age {self.age/C.SECONDS_PER_DAY:.1f} days!")
            elif i < 3:
                print(f"    Growth Check (Deficit of {net_energy_production:.4f} J):")
                print(f"      - Decision: CANNOT GROW.")
        
        # --- END OF LOOP ---
        
        # After the loop, subtract the total time that was processed.
        total_time_processed = internal_tick * ticks_to_process
        self.logic_update_accumulator -= total_time_processed
        
        print(f"--- END LOGIC {self.id} --- Final Energy: {self.energy:.2f}, Radius: {self.radius:.2f}")
        print(f"  Remaining in accumulator: {self.logic_update_accumulator:.2f}s")

    # ... (rest of the Plant class is unchanged) ...
    def is_overcrowded(self, quadtree):
        search_area = Rectangle(self.x, self.y, C.PLANT_CROWDED_RADIUS_CM, C.PLANT_CROWDED_RADIUS_CM)
        neighbors = quadtree.query(search_area, [])
        return len(neighbors) > C.PLANT_MAX_NEIGHBORS

    def calculate_environment_efficiency(self, temperature, humidity):
        temp_diff = abs(temperature - self.genes.optimal_temperature)
        temp_eff = math.exp(-((temp_diff / self.genes.temperature_tolerance)**2))
        hum_diff = abs(humidity - self.genes.optimal_humidity)
        hum_eff = math.exp(-((hum_diff / self.genes.humidity_tolerance)**2))
        return temp_eff * hum_eff

    def draw(self, screen, camera):
        screen_pos = camera.world_to_screen(self.x, self.y)
        canopy_radius = camera.scale(self.radius)
        if canopy_radius >= 1:
            canopy_surface = pygame.Surface((canopy_radius * 2, canopy_radius * 2), pygame.SRCALPHA)
            health_ratio = min(1.0, max(0.0, self.energy / C.CREATURE_REPRODUCTION_ENERGY_THRESHOLD))
            canopy_color = lerp_color(C.COLOR_PLANT_CANOPY_SICKLY, C.COLOR_PLANT_CANOPY_HEALTHY, health_ratio)
            pygame.draw.circle(canopy_surface, canopy_color, (canopy_radius, canopy_radius), canopy_radius)
            screen.blit(canopy_surface, (screen_pos[0] - canopy_radius, screen_pos[1] - canopy_radius))
        core_radius = camera.scale(self.get_core_radius())
        if core_radius >= 1:
            pygame.draw.circle(screen, C.COLOR_PLANT_CORE, screen_pos, core_radius)

    def print_debug_report(self):
        days_old = self.age / C.SECONDS_PER_DAY
        print("\n--- PLANT ON-CLICK DEBUG REPORT ---")
        print(f"  Creature ID: {self.id}")
        print(f"  Age: {days_old:.2f} simulation days ({self.age:.0f} seconds)")
        maturity_progress = (self.radius / self.genes.max_radius) * 100
        print(f"  Maturity: {'Mature' if self.is_mature else 'Growing'} ({maturity_progress:.1f}%)")
        print(f"  - Canopy Radius: {self.radius:.2f} cm (Max: {self.genes.max_radius:.2f} cm)")
        print(f"  - Root Radius:   {self.root_radius:.2f} cm")
        repro_progress = (self.energy / C.CREATURE_REPRODUCTION_ENERGY_THRESHOLD) * 100
        print(f"  Reproduction Energy: {'Ready' if self.can_reproduce() else 'Saving'} ({repro_progress:.1f}%)")
        print(f"  - Stored Energy: {self.energy:.2f} J")
        print(f"  - Needed to Reproduce: {C.CREATURE_REPRODUCTION_ENERGY_THRESHOLD:.2f} J")
        print(f"  - Reproduction Cooldown: {self.reproduction_cooldown:.2f}s")
        print("-------------------------------------\n")

class Animal(Creature):
    # ... (Animal class is unchanged) ...
    def __init__(self, x, y):
        super().__init__(x, y)
        self.width = C.ANIMAL_INITIAL_WIDTH_CM
        self.height = C.ANIMAL_INITIAL_HEIGHT_CM
        self.color = C.COLOR_BLUE
        self.target_plant = None

    def find_closest_plant(self, quadtree):
        search_area = Rectangle(self.x, self.y, C.ANIMAL_SIGHT_RADIUS_CM, C.ANIMAL_SIGHT_RADIUS_CM)
        nearby_creatures = quadtree.query(search_area, [])
        closest_plant = None
        min_dist = float('inf')
        for plant in nearby_creatures:
            if isinstance(plant, Plant) and plant.is_alive:
                dist_sq = (self.x - plant.x)**2 + (self.y - plant.y)**2
                if dist_sq < min_dist:
                    min_dist = dist_sq
                    closest_plant = plant
        return closest_plant

    def update(self, world, delta_time):
        if not self.is_alive: return
        self.age += delta_time
        metabolism_cost = C.ANIMAL_METABOLISM_PER_SECOND * delta_time
        self.energy -= metabolism_cost
        if self.energy <= 0:
            self.die(world, "starvation")
            return

        if self.can_reproduce():
            spawn_pos = self.reproduce(world, world.quadtree)
            if spawn_pos:
                new_animal = Animal(spawn_pos[0], spawn_pos[1])
                world.add_newborn(new_animal)
        else:
            if self.target_plant and not self.target_plant.is_alive:
                self.target_plant = None
            if not self.target_plant:
                self.target_plant = self.find_closest_plant(world.quadtree)
            if self.target_plant:
                direction_x = self.target_plant.x - self.x
                direction_y = self.target_plant.y - self.y
                distance = math.sqrt(direction_x**2 + direction_y**2)
                move_dist = C.ANIMAL_SPEED_CM_PER_SEC * delta_time
                if distance < move_dist:
                    self.x = self.target_plant.x
                    self.y = self.target_plant.y
                else:
                    self.x += (direction_x / distance) * move_dist
                    self.y += (direction_y / distance) * move_dist
                if distance < self.width:
                    self.energy += C.ANIMAL_ENERGY_PER_PLANT
                    self.target_plant.die(world, "being eaten")
                    self.target_plant = None
            else:
                move_x = random.uniform(-1, 1)
                move_y = random.uniform(-1, 1)
                norm = math.sqrt(move_x**2 + move_y**2)
                if norm > 0:
                    move_dist = C.ANIMAL_SPEED_CM_PER_SEC * delta_time
                    self.x += (move_x / norm) * move_dist
                    self.y += (move_y / norm) * move_dist

    def draw(self, screen, camera):
        screen_pos = camera.world_to_screen(self.x, self.y)
        screen_width = camera.scale(self.width)
        screen_height = camera.scale(self.height)
        if screen_width >= 1 and screen_height >= 1:
            rect_to_draw = (screen_pos[0], screen_pos[1], screen_width, screen_height)
            pygame.draw.rect(screen, self.color, rect_to_draw)