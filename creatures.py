# creatures.py

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
        self.x = x  # World coordinate, in centimeters (cm)
        self.y = y  # World coordinate, in centimeters (cm)
        self.energy = C.CREATURE_INITIAL_ENERGY  # Stored energy, in Joules (J)
        self.age = 0  # Age of the creature, in seconds (s)
        self.is_alive = True
        self.id = random.randint(C.CREATURE_ID_MIN, C.CREATURE_ID_MAX)
        log.log(f"DEBUG: Creature {self.id} created at ({x:.0f}, {y:.0f}). Initial Energy: {self.energy}")

    def die(self, world, cause):
        if self.is_alive:
            log.log(f"DEBUG: Creature {self.id} is dying from: {cause}")
            self.is_alive = False
            world.report_death(self)

    def can_reproduce(self):
        # A creature can reproduce if it has stored enough energy to pay the full cost of a new offspring.
        return self.energy >= C.CREATURE_REPRODUCTION_ENERGY_COST

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
        
        log.log(f"DEBUG ({self.id}): Failed to find a valid spawn location. Reproductive energy was lost.")
        # The energy cost is now a sunk cost and is NOT refunded.
        return None

class Plant(Creature):
    def __init__(self, world, x, y):
        super().__init__(x, y)
        log.log(f"DEBUG ({self.id}): Initializing as a Plant.")
        self.genes = PlantGenes()
        self.radius = C.PLANT_INITIAL_RADIUS_CM  # Canopy radius, in centimeters (cm)
        self.root_radius = C.PLANT_INITIAL_ROOT_RADIUS_CM  # Root system radius, in centimeters (cm)
        self.competition_factor = 1.0  # Efficiency multiplier based on nearby plants, unitless [0, 1]
        self.competition_update_accumulator = 0.0  # Time since last competition check, in seconds (s)
        self.has_reached_self_sufficiency = False # Has the plant ever had a positive energy balance?

        self.elevation = world.environment.get_elevation(self.x, self.y)  # Cached elevation, unitless [0, 1]
        self.soil_type = self.get_soil_type(self.elevation)  # Type of soil at location (e.g., "sand", "grass")
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
        # --- Canopy Competition (for light) ---
        canopy_search_area = Rectangle(self.x, self.y, self.radius, self.radius)
        canopy_neighbors = quadtree.query(canopy_search_area, [])
        total_canopy_competition_mass = 0
        for neighbor in canopy_neighbors:
            if neighbor is self or not isinstance(neighbor, Plant): continue
            # Check for physical overlap based on radius
            dist_sq = (self.x - neighbor.x)**2 + (self.y - neighbor.y)**2
            if dist_sq < (self.radius + neighbor.radius)**2:
                total_canopy_competition_mass += neighbor.radius**2
        canopy_competition_factor = 1 / (1 + total_canopy_competition_mass * C.PLANT_COMPETITION_MASS_FACTOR)

        # --- Root Competition (for water/nutrients) ---
        root_search_area = Rectangle(self.x, self.y, self.root_radius, self.root_radius)
        root_neighbors = quadtree.query(root_search_area, [])
        total_root_competition_mass = 0
        for neighbor in root_neighbors:
            if neighbor is self or not isinstance(neighbor, Plant): continue
            # Check for physical overlap based on root radius
            dist_sq = (self.x - neighbor.x)**2 + (self.y - neighbor.y)**2
            if dist_sq < (self.root_radius + neighbor.root_radius)**2:
                total_root_competition_mass += neighbor.root_radius**2
        root_competition_factor = 1 / (1 + total_root_competition_mass * C.PLANT_COMPETITION_MASS_FACTOR)

        return canopy_competition_factor, root_competition_factor

    # --- MAJOR CHANGE: The update logic is now much cleaner. ---
    def update(self, world, time_step):
        """
        Runs the core biological logic for a fixed time_step.
        This function is now only called by the world's scheduler.
        """
        if not self.is_alive: return

        # The time_step is now a fixed value (e.g., 3600 seconds) passed by the scheduler.
        self.age += time_step

        is_debug_focused = (world.debug_focused_creature_id == self.id)

        if is_debug_focused:
            log.log(f"\n--- PLANT {self.id} LOGIC (Age: {self.age/C.SECONDS_PER_DAY:.1f} days) ---")
            log.log(f"  Processing a single consolidated tick of {time_step:.2f}s.")
            log.log(f"    State: Energy={self.energy:.2f}, Radius={self.radius:.2f}, RootRadius={self.root_radius:.2f}")

        # --- CORE BIOLOGY LOGIC (Calculations now use time_step directly) ---
        self.competition_update_accumulator += time_step
        
        canopy_competition, root_competition = 1.0, 1.0
        if self.competition_update_accumulator >= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS:
            canopy_competition, root_competition = self.calculate_competition_factor(world.quadtree)
            # The overall competition factor is the product of both pressures
            self.competition_factor = canopy_competition * root_competition
            self.competition_update_accumulator %= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS

        max_soil_eff = self.genes.soil_efficiency.get(self.soil_type, 0)
        root_to_canopy_ratio = self.root_radius / (self.radius + 1)
        soil_eff = max_soil_eff * min(1.0, root_to_canopy_ratio * C.PLANT_ROOT_EFFICIENCY_FACTOR)
        aging_efficiency = math.exp(-(self.age / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))
        
        canopy_area = math.pi * self.radius**2
        root_area = math.pi * self.root_radius**2

        # Photosynthesis is now only limited by ABOVE-GROUND (canopy) competition for light.
        photosynthesis_gain = canopy_area * C.PLANT_PHOTOSYNTHESIS_PER_AREA * self.environment_eff * soil_eff * canopy_competition * aging_efficiency * time_step
        # Metabolism (survival cost) is based on the plant's total size and local competition, but is NOT reduced by poor weather.
        metabolism_cost = (canopy_area + root_area) * C.PLANT_METABOLISM_PER_AREA * self.competition_factor * time_step
        net_energy_production = photosynthesis_gain - metabolism_cost
        
        self.energy += net_energy_production

        if is_debug_focused:
            log.log(f"    Efficiencies: Env={self.environment_eff:.3f}, Soil={soil_eff:.3f}, Aging={aging_efficiency:.3f}")
            log.log(f"    Competition: Canopy={canopy_competition:.3f}, Root={root_competition:.3f}, Combined={self.competition_factor:.3f}")
            log.log(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net={net_energy_production:.4f}")

        if self.energy <= 0:
            self.die(world, "starvation")
            if is_debug_focused:
                log.log(f"  Plant {self.id} died from starvation. Final Energy: {self.energy:.2f}")
            return

        # --- MILESTONE CHECK: Has the plant become self-sufficient? ---
        if not self.has_reached_self_sufficiency and net_energy_production > 0:
            self.has_reached_self_sufficiency = True
            if is_debug_focused:
                log.log(f"    MILESTONE: Plant {self.id} has reached self-sufficiency!")

        # --- Reproduction Logic ---
        # A plant can reproduce only if it has a NET ENERGY SURPLUS from this tick,
        # has stored enough total energy to create a seed, and is not overcrowded.
        # The "cooldown" is now an emergent property of how long it takes to save this energy.
        if net_energy_production > 0 and self.can_reproduce() and not self.is_overcrowded(world.quadtree):
            if is_debug_focused: log.log(f"    Reproduction Check: Net surplus, has {self.energy:.2f} J energy. Attempting to spawn.")
            new_plant = self.reproduce(world, world.quadtree)
            if new_plant:
                world.add_newborn(new_plant)
                # No cooldown to set. The energy cost itself is the cooldown.
                if is_debug_focused: log.log(f"    Reproduction SUCCESS. Energy remaining: {self.energy:.2f} J.")
        
                # --- Growth Logic ---
        growth_energy = 0
        # CASE 1: The plant has a net energy surplus. It can always grow.
        if net_energy_production > 0:
            growth_energy = net_energy_production
            if is_debug_focused: log.log(f"    Growth Check (Surplus of {net_energy_production:.4f} J): Investing surplus.")

        # CASE 2: The plant has a deficit, but is still a "seedling" that has never been self-sufficient.
        elif not self.has_reached_self_sufficiency:
            if self.energy > C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE:
                investment_per_second = C.PLANT_GROWTH_INVESTMENT_J_PER_HOUR / C.SECONDS_PER_HOUR
                investment_amount = investment_per_second * time_step
                available_investment_energy = self.energy - C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE
                investment_amount = min(investment_amount, available_investment_energy)

                if investment_amount > 0:
                    growth_energy = investment_amount
                    self.energy -= investment_amount # Pay for the growth from our reserves.
                    if is_debug_focused: log.log(f"    Growth Check (Deficit of {net_energy_production:.4f} J): Investing {investment_amount:.4f} J from reserves (Seedling).")
                elif is_debug_focused:
                    log.log(f"    Growth Check (Deficit of {net_energy_production:.4f} J): Cannot invest, reserves too low.")
            else:
                 if is_debug_focused:
                    log.log(f"    Growth Check (Deficit of {net_energy_production:.4f} J): CANNOT GROW (Reserves below threshold).")
        
        # CASE 3: The plant has a deficit and is "mature" (has been self-sufficient before). It cannot grow.
        else:
            if is_debug_focused:
                log.log(f"    Growth Check (Deficit of {net_energy_production:.4f} J): CANNOT GROW (Mature plant, no energy surplus).")

        if growth_energy > 0:
            total_added_biomass = growth_energy / C.PLANT_BIOMASS_ENERGY_COST
            if is_debug_focused: log.log(f"      - Investment converts to {total_added_biomass:.4f} cm^2 of new biomass.")

            # Proportional Growth Allocation: The plant allocates resources to whichever system is less efficient.
            total_limitation = self.environment_eff + soil_eff
            if total_limitation > 0:
                canopy_alloc_factor = soil_eff / total_limitation
                root_alloc_factor = self.environment_eff / total_limitation

                added_canopy_area = total_added_biomass * canopy_alloc_factor
                added_root_area = total_added_biomass * root_alloc_factor

                if is_debug_focused:
                    log.log(f"      - Proportional Allocation: {canopy_alloc_factor*100:.1f}% to Canopy, {root_alloc_factor*100:.1f}% to Roots.")
                    log.log(f"      - Growing CANOPY. Old Radius: {self.radius:.4f}, Adding Area: {added_canopy_area:.4f}")
                
                new_canopy_area = canopy_area + added_canopy_area
                self.radius = math.sqrt(new_canopy_area / math.pi)
                if is_debug_focused: log.log(f"      - New Radius: {self.radius:.4f}")

                if is_debug_focused:
                    log.log(f"      - Growing ROOTS. Old Root Radius: {self.root_radius:.4f}, Adding Area: {added_root_area:.4f}")
                
                new_root_area = root_area + added_root_area
                self.root_radius = math.sqrt(new_root_area / math.pi)
                if is_debug_focused: log.log(f"      - New Root Radius: {self.root_radius:.4f}")
            elif is_debug_focused:
                log.log(f"      - Decision: CANNOT GROW (Total limitation factor is zero).")
        
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
            health_ratio = min(1.0, max(0.0, self.energy / C.CREATURE_REPRODUCTION_ENERGY_COST))
            canopy_color = lerp_color(C.COLOR_PLANT_CANOPY_SICKLY, C.COLOR_PLANT_CANOPY_HEALTHY, health_ratio)
            pygame.draw.circle(canopy_surface, canopy_color, (canopy_radius, canopy_radius), canopy_radius)
            screen.blit(canopy_surface, (screen_pos[0] - canopy_radius, screen_pos[1] - canopy_radius))
        core_radius = camera.scale(self.get_core_radius())
        if core_radius >= 1:
            pygame.draw.circle(screen, C.COLOR_PLANT_CORE, screen_pos, core_radius)

class Animal(Creature):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.width = C.ANIMAL_INITIAL_WIDTH_CM  # Width of the animal, in centimeters (cm)
        self.height = C.ANIMAL_INITIAL_HEIGHT_CM  # Height of the animal, in centimeters (cm)
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

    # --- MAJOR CHANGE: The update logic now uses a fixed time_step ---
    def update(self, world, time_step):
        """
        Runs the core biological logic for a fixed time_step.
        This function is now only called by the world's scheduler.
        """
        if not self.is_alive: return

        self.age += time_step
        metabolism_cost = C.ANIMAL_METABOLISM_PER_SECOND * time_step
        self.energy -= metabolism_cost
        if self.energy <= 0:
            self.die(world, "starvation")
            return
        
        # --- CHANGE: Track if the animal moved this tick ---
        moved = False

        if self.can_reproduce():
            # Note: Animal reproduction logic is simple and doesn't create newborns yet.
            # We can improve this later.
            self.energy -= C.CREATURE_REPRODUCTION_ENERGY_COST 
        else:
            if self.target_plant and not self.target_plant.is_alive:
                self.target_plant = None
            if not self.target_plant:
                self.target_plant = self.find_closest_plant(world.quadtree)
            
            if self.target_plant:
                direction_x = self.target_plant.x - self.x
                direction_y = self.target_plant.y - self.y
                distance = math.sqrt(direction_x**2 + direction_y**2)
                
                # Use the fixed time_step for movement
                move_dist = C.ANIMAL_SPEED_CM_PER_SEC * time_step
                
                if distance < move_dist:
                    self.x = self.target_plant.x
                    self.y = self.target_plant.y
                    # Eating logic
                    self.energy += C.ANIMAL_ENERGY_PER_PLANT
                    self.target_plant.die(world, "being eaten")
                    self.target_plant = None
                else:
                    self.x += (direction_x / distance) * move_dist
                    self.y += (direction_y / distance) * move_dist
                moved = True # The animal moved
            else:
                # Random wandering
                move_x = random.uniform(-1, 1)
                move_y = random.uniform(-1, 1)
                norm = math.sqrt(move_x**2 + move_y**2)
                if norm > 0:
                    move_dist = C.ANIMAL_SPEED_CM_PER_SEC * time_step
                    self.x += (move_x / norm) * move_dist
                    self.y += (move_y / norm) * move_dist
                    moved = True # The animal moved

    # --- CHANGE: If the animal moved, tell the world to update the quadtree ---
        if moved:
            world.update_creature_in_quadtree(self)

    def draw(self, screen, camera):
        screen_pos = camera.world_to_screen(self.x, self.y)
        screen_width = camera.scale(self.width)
        screen_height = camera.scale(self.height)
        if screen_width >= 1 and screen_height >= 1:
            rect_to_draw = (screen_pos[0], screen_pos[1], screen_width, screen_height)
            pygame.draw.rect(screen, self.color, rect_to_draw)