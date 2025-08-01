# creatures.py (YOUR LOGIC, WITH FULL DEBUG MESSAGES)

import pygame
import constants as C
import random
import math
from quadtree import Rectangle
from genes import PlantGenes
import logger as log

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
        log.log(f"DEBUG: Creature {self.id} created at ({x:.0f}, {y:.0f}). Initial Energy: {self.energy}")

    def die(self, world, cause):
        if self.is_alive:
            log.log(f"DEBUG: Creature {self.id} is dying from: {cause}")
            self.is_alive = False
            world.report_death(self)

    def can_reproduce(self):
        return self.energy >= C.CREATURE_REPRODUCTION_ENERGY_THRESHOLD

    def reproduce(self, world, quadtree):
        log.log(f"DEBUG ({self.id}): Attempting to reproduce.")
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
            log.log(f"DEBUG ({self.id}): Found a valid spawn location.")
            return Plant(world, best_location[0], best_location[1])
        
        log.log(f"DEBUG ({self.id}): Failed to find a valid spawn location.")
        self.energy += C.CREATURE_REPRODUCTION_ENERGY_COST
        return None

class Plant(Creature):
    def __init__(self, world, x, y):
        super().__init__(x, y)
        log.log(f"DEBUG ({self.id}): Initializing as a Plant.")
        self.genes = PlantGenes()
        self.radius = C.PLANT_INITIAL_RADIUS_CM
        self.root_radius = C.PLANT_INITIAL_ROOT_RADIUS_CM
        self.reproduction_cooldown = 0.0
        self.competition_factor = 1.0
        self.competition_update_accumulator = 0.0
        # This accumulator will store unprocessed simulation time.
        self.logic_update_accumulator = 0.0 # units: seconds

        self.elevation = world.environment.get_elevation(self.x, self.y)
        self.soil_type = self.get_soil_type(self.elevation)
        log.log(f"DEBUG ({self.id}): Environment check: Elevation={self.elevation:.2f}, Soil='{self.soil_type}'")
        
        if self.soil_type is None:
            log.log(f"DEBUG ({self.id}): Spawning on invalid terrain. Marking for death.")
            self.is_alive = False
            self.energy = 0
            return

        self.temperature = world.environment.get_temperature(self.x, self.y)
        self.humidity = world.environment.get_humidity(self.x, self.y)
        self.environment_eff = self.calculate_environment_efficiency(self.temperature, self.humidity)
        log.log(f"DEBUG ({self.id}): Caching env_eff: {self.environment_eff:.3f}")

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

        self.age += delta_time
        self.logic_update_accumulator += delta_time

        if self.logic_update_accumulator < C.PLANT_LOGIC_UPDATE_INTERVAL_SECONDS:
            return
        
        time_to_process = self.logic_update_accumulator
        self.logic_update_accumulator = 0.0

        is_debug_focused = (world.debug_focused_creature_id == self.id)

        if is_debug_focused:
            log.log(f"\n--- PLANT {self.id} LOGIC (Age: {self.age/C.SECONDS_PER_DAY:.1f} days) ---")
            log.log(f"  Processing a single consolidated tick of {time_to_process:.2f}s.")
            log.log(f"    State: Energy={self.energy:.2f}, Radius={self.radius:.2f}")

        # --- Store cooldown state BEFORE the tick ---
        was_ready_to_reproduce = self.reproduction_cooldown <= 0

        # --- CORE BIOLOGY LOGIC (Consolidated Calculation) ---
        self.reproduction_cooldown = max(0, self.reproduction_cooldown - time_to_process)
        self.competition_update_accumulator += time_to_process
        
        if self.competition_update_accumulator >= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS:
            self.competition_factor = self.calculate_competition_factor(world.quadtree)
            self.competition_update_accumulator %= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS

        max_soil_eff = self.genes.soil_efficiency.get(self.soil_type, 0)
        root_to_canopy_ratio = self.root_radius / (self.radius + 1)
        soil_eff = max_soil_eff * min(1.0, root_to_canopy_ratio * C.PLANT_ROOT_EFFICIENCY_FACTOR)
        aging_efficiency = math.exp(-(self.age / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))
        
        canopy_area = math.pi * self.radius**2
        root_area = math.pi * self.root_radius**2

        photosynthesis_gain = canopy_area * C.PLANT_PHOTOSYNTHESIS_PER_AREA * self.environment_eff * soil_eff * self.competition_factor * aging_efficiency * time_to_process
        metabolism_cost = (canopy_area + root_area) * C.PLANT_METABOLISM_PER_AREA * self.environment_eff * time_to_process
        net_energy_production = photosynthesis_gain - metabolism_cost
        
        self.energy += net_energy_production

        if is_debug_focused:
            log.log(f"    Efficiencies: Env={self.environment_eff:.3f}, Soil={soil_eff:.3f}, Aging={aging_efficiency:.3f}, Comp={self.competition_factor:.3f}")
            log.log(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net={net_energy_production:.4f}")

        if self.energy <= 0:
            self.die(world, "starvation")
            if is_debug_focused:
                log.log(f"  Plant {self.id} died from starvation. Final Energy: {self.energy:.2f}")
            return

        # --- NEW, CORRECTED REPRODUCTION LOGIC ---
        # A plant can only reproduce if its cooldown was ALREADY finished before this tick began.
        # This prevents it from using the massive time_to_process to instantly reset its own cooldown.
        if was_ready_to_reproduce and self.can_reproduce() and not self.is_overcrowded(world.quadtree):
            if is_debug_focused: log.log("    Reproduction Check: Was ready, has energy. Attempting to spawn.")
            new_plant = self.reproduce(world, world.quadtree)
            if new_plant:
                world.add_newborn(new_plant)
                # The cooldown is now set to its full duration. It will have to wait for
                # future ticks to reduce this again.
                self.reproduction_cooldown = C.PLANT_REPRODUCTION_COOLDOWN_SECONDS
        
        if net_energy_production > 0:
            if is_debug_focused: log.log(f"    Growth Check (Surplus of {net_energy_production:.4f} J):")
            added_biomass_area = net_energy_production / C.PLANT_BIOMASS_ENERGY_COST
            if is_debug_focused: log.log(f"      - Surplus converts to {added_biomass_area:.4f} cm^2 of new biomass.")

            grows_canopy = (soil_eff >= self.environment_eff)
            if grows_canopy:
                if is_debug_focused: log.log(f"      - Decision: Growing CANOPY. Old Radius: {self.radius:.4f}")
                new_canopy_area = canopy_area + added_biomass_area
                self.radius = math.sqrt(new_canopy_area / math.pi)
                if is_debug_focused: log.log(f"      - New Radius: {self.radius:.4f}")
            else:
                if is_debug_focused: log.log(f"      - Decision: Growing ROOTS. Old Root Radius: {self.root_radius:.4f}")
                new_root_area = root_area + added_biomass_area
                self.root_radius = math.sqrt(new_root_area / math.pi)
                if is_debug_focused: log.log(f"      - New Root Radius: {self.root_radius:.4f}")
        
        elif is_debug_focused:
            log.log(f"    Growth Check (Deficit of {net_energy_production:.4f} J):")
            log.log(f"      - Decision: CANNOT GROW.")
        
        if is_debug_focused:
            log.log(f"--- END LOGIC {self.id} --- Final Energy: {self.energy:.2f}, Radius: {self.radius:.2f}")

    # ... (rest of Plant class is unchanged) ...
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