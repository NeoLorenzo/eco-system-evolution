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
    def __init__(self, x, y, initial_energy=C.CREATURE_INITIAL_ENERGY):
        self.x = x  # World coordinate, in centimeters (cm)
        self.y = y  # World coordinate, in centimeters (cm)
        self.energy = initial_energy  # Stored energy, in Joules (J)
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
        # Generic reproduction check, now only used by Animals.
        # Plants have their own more complex version of this method.
        return self.energy >= C.CREATURE_REPRODUCTION_ENERGY_COST

    def reproduce(self, world, quadtree):
        # This is now a placeholder and should be overridden by child classes
        # if they have specific reproduction logic (like Plant does).
        log.log(f"DEBUG ({self.id}): Generic reproduce() called. This should not happen for Plants.")
        return None

class Plant(Creature):
    def __init__(self, world, x, y, initial_energy=C.CREATURE_INITIAL_ENERGY):
        super().__init__(x, y, initial_energy)
        log.log(f"DEBUG ({self.id}): Initializing as a Plant.")
        self.genes = PlantGenes()
        self.radius = C.PLANT_INITIAL_RADIUS_CM # Canopy radius, in centimeters (cm)
        # Height is now an emergent property derived from the radius.
        self.height = self.radius * C.PLANT_RADIUS_TO_HEIGHT_FACTOR # Canopy height, in centimeters (cm)
        self.root_radius = C.PLANT_INITIAL_ROOT_RADIUS_CM # Root system radius, in centimeters (cm)
        self.reproductive_energy_stored = 0.0 # Energy invested in reproductive structures, in Joules (J)
        self.competition_factor = 1.0 # DEPRECATED, will be removed later.
        self.competition_update_accumulator = 0.0 # Time since last competition check, in seconds (s)
        self.has_reached_self_sufficiency = False # Has the plant ever had a positive energy balance?
        self.shaded_canopy_area = 0.0 # The area of our canopy shaded by neighbors, in cm^2
        self.overlapped_root_area = 0.0 # The area of our roots competing with neighbors, in cm^2

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

    def _calculate_circle_intersection_area(self, d, r1, r2):
        """Calculates the area of intersection of two circles."""
        if d <= 0: # Handle case where circles are concentric or d is invalid
            return math.pi * min(r1, r2)**2
        if d >= r1 + r2:
            return 0  # Circles do not intersect
        if d <= abs(r1 - r2):
            return math.pi * min(r1, r2)**2  # One circle is contained within the other

        r1_sq, r2_sq, d_sq = r1**2, r2**2, d**2
        
        # Formula for the area of intersection of two circles
        term1 = r1_sq * math.acos((d_sq + r1_sq - r2_sq) / (2 * d * r1))
        term2 = r2_sq * math.acos((d_sq + r2_sq - r1_sq) / (2 * d * r2))
        term3 = 0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))
        
        return term1 + term2 - term3

    def calculate_physical_overlap(self, quadtree):
        """Calculates the total geometric area of canopy and root overlap with neighbors."""
        total_shaded_canopy_area = 0
        total_overlapped_root_area = 0

        # --- OPTIMIZATION: Query for neighbors only ONCE ---
        # The search radius for canopy and root competition is the same, so we can reuse the result.
        search_area = Rectangle(self.x, self.y, C.PLANT_SEED_SPREAD_RADIUS_CM, C.PLANT_SEED_SPREAD_RADIUS_CM)
        neighbors = quadtree.query(search_area, [])

        for neighbor in neighbors:
            if neighbor is self or not isinstance(neighbor, Plant):
                continue

            dist = math.sqrt((self.x - neighbor.x)**2 + (self.y - neighbor.y)**2)

            # --- Canopy Competition (for light) ---
            # If we are taller or the same height, the neighbor cannot shade us.
            if self.height < neighbor.height:
                if dist < self.radius + neighbor.radius:
                    total_shaded_canopy_area += self._calculate_circle_intersection_area(dist, self.radius, neighbor.radius)

            # --- Root Competition (for water/nutrients) ---
            if dist < self.root_radius + neighbor.root_radius:
                total_overlapped_root_area += self._calculate_circle_intersection_area(dist, self.root_radius, neighbor.root_radius)

        # A plant's shaded area cannot exceed its own total area.
        my_canopy_area = math.pi * self.radius**2
        my_root_area = math.pi * self.root_radius**2
        
        return min(total_shaded_canopy_area, my_canopy_area), min(total_overlapped_root_area, my_root_area)

    def update(self, world, time_step):
        """
        Runs the core biological logic for a fixed time_step.
        This function is now only called by the world's scheduler.
        """
        if not self.is_alive: return

        self.age += time_step
        is_debug_focused = (world.debug_focused_creature_id == self.id)

        if is_debug_focused:
            log.log(f"\n--- PLANT {self.id} LOGIC (Age: {self.age/C.SECONDS_PER_DAY:.1f} days) ---")
            log.log(f"  Processing a single consolidated tick of {time_step:.2f}s.")
            log.log(f"    State: Energy={self.energy:.2f}, ReproEnergy={self.reproductive_energy_stored:.2f}, Radius={self.radius:.2f}, Height={self.height:.2f}, ShadedArea={self.shaded_canopy_area:.2f}")

        # --- CORE BIOLOGY LOGIC (Calculations now use time_step directly) ---
        self.competition_update_accumulator += time_step
        
        if self.competition_update_accumulator >= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS:
            log.log(f"DEBUG ({self.id}): Recalculating physical competition. Accumulator was {self.competition_update_accumulator:.1f}s.")
            self.shaded_canopy_area, self.overlapped_root_area = self.calculate_physical_overlap(world.quadtree)
            self.competition_update_accumulator %= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS

        max_soil_eff = self.genes.soil_efficiency.get(self.soil_type, 0)
        root_to_canopy_ratio = self.root_radius / (self.radius + 1)
        soil_eff = max_soil_eff * min(1.0, root_to_canopy_ratio * C.PLANT_ROOT_EFFICIENCY_FACTOR)
        aging_efficiency = math.exp(-(self.age / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))
        
        canopy_area = math.pi * self.radius**2
        root_area = math.pi * self.root_radius**2

        # --- NEW: Photosynthesis is based on EFFECTIVE (un-shaded) canopy area ---
        effective_canopy_area = max(0, canopy_area - self.shaded_canopy_area)
        photosynthesis_gain = effective_canopy_area * C.PLANT_PHOTOSYNTHESIS_PER_AREA * self.environment_eff * soil_eff * aging_efficiency * time_step
        
        # --- Metabolism cost is based on TOTAL biomass AREA (canopy area + root area) ---
        temp_difference = self.temperature - C.PLANT_RESPIRATION_REFERENCE_TEMP
        respiration_factor = C.PLANT_Q10_FACTOR ** (temp_difference / C.PLANT_Q10_INTERVAL_DIVISOR)
        metabolism_cost = (canopy_area + root_area) * C.PLANT_BASE_MAINTENANCE_RESPIRATION_PER_AREA * respiration_factor * time_step
        
        net_energy_production = photosynthesis_gain - metabolism_cost
        self.energy += net_energy_production

        if is_debug_focused:
            log.log(f"    Efficiencies: Env={self.environment_eff:.3f}, Soil={soil_eff:.3f}, Aging={aging_efficiency:.3f}")
            log.log(f"    Competition: ShadedCanopyArea={self.shaded_canopy_area:.2f}, OverlappedRootArea={self.overlapped_root_area:.2f}")
            log.log(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net={net_energy_production:.4f}")

        if self.energy <= 0:
            self.die(world, "starvation")
            if is_debug_focused: log.log(f"  Plant {self.id} died from starvation. Final Energy: {self.energy:.2f}")
            return

        if not self.has_reached_self_sufficiency and net_energy_production > 0:
            self.has_reached_self_sufficiency = True
            if is_debug_focused: log.log(f"    MILESTONE: Plant {self.id} has reached self-sufficiency!")

        # --- NEW: Unified Growth & Reproduction Investment Model ---
        investment_from_reserves = 0
        # A plant will always try to invest in growth as long as it's above its emergency reserves.
        if self.energy > C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE:
            desired_investment = (C.PLANT_GROWTH_INVESTMENT_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
            # How much can we actually take from reserves?
            available_from_reserves = self.energy - C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE
            # We take the smaller of what we want vs. what we have.
            investment_from_reserves = min(desired_investment, available_from_reserves)
            self.energy -= investment_from_reserves # Spend the energy from savings.

        # The total energy available for allocation is this tick's income plus any investment from savings.
        total_allocatable_energy = net_energy_production + investment_from_reserves
        growth_energy = 0

        if total_allocatable_energy > 0:
            reproductive_investment = total_allocatable_energy * C.PLANT_REPRODUCTIVE_INVESTMENT_RATIO
            self.reproductive_energy_stored += reproductive_investment
            growth_energy = total_allocatable_energy * (1 - C.PLANT_REPRODUCTIVE_INVESTMENT_RATIO)
            if is_debug_focused:
                log.log(f"    Allocation: Total pool of {total_allocatable_energy:.4f} J -> {reproductive_investment:.4f} J to repro, {growth_energy:.4f} J to growth.")
        elif is_debug_focused:
            log.log(f"    Allocation: No surplus energy or reserves to invest.")

        # --- Reproduction Logic ---
        if self.can_reproduce() and not self.is_overcrowded(world.quadtree):
            if is_debug_focused: log.log(f"    Reproduction Check: Conditions met. Attempting to spawn.")
            new_plant = self.reproduce(world, world.quadtree)
            if new_plant:
                world.add_newborn(new_plant)
                if is_debug_focused: log.log(f"    Reproduction SUCCESS. Energy remaining: {self.energy:.2f} J, ReproEnergy: {self.reproductive_energy_stored:.2f} J.")
        
        # --- Growth Logic (2D Area-Based Model) ---
        if growth_energy > 0:
            total_limitation = self.environment_eff + soil_eff
            if total_limitation > 0:
                # --- 1. Calculate total new area to be grown ---
                # The cost is for growing 2D area, not 3D volume.
                added_biomass_area = growth_energy / C.PLANT_BIOMASS_ENERGY_COST

                # --- 2. Allocate new area between canopy and roots ---
                # This logic is sound: invest more in roots if light/air is good, more in canopy if soil is good.
                canopy_alloc_factor = soil_eff / total_limitation
                root_alloc_factor = self.environment_eff / total_limitation
                
                added_canopy_area = added_biomass_area * canopy_alloc_factor
                added_root_area = added_biomass_area * root_alloc_factor

                # --- 3. Update radii from new areas ---
                new_canopy_area = canopy_area + added_canopy_area
                self.radius = math.sqrt(new_canopy_area / math.pi)
                
                new_root_area = root_area + added_root_area
                self.root_radius = math.sqrt(new_root_area / math.pi)

                # --- 4. Update height as an emergent property of the new radius ---
                self.height = self.radius * C.PLANT_RADIUS_TO_HEIGHT_FACTOR

                if is_debug_focused:
                    log.log(f"      - Growth Investment: {growth_energy:.2f} J -> {added_biomass_area:.2f} cm^2 total new area.")
                    log.log(f"      - Area Allocation: {added_canopy_area:.2f} cm^2 to Canopy, {added_root_area:.2f} cm^2 to Roots.")
                    log.log(f"      - New State: Radius={self.radius:.2f}, Height={self.height:.2f}, RootRadius={self.root_radius:.2f}")

            elif is_debug_focused:
                log.log(f"      - Decision: CANNOT GROW (Total limitation factor is zero).")
        
        if is_debug_focused:
            log.log(f"--- END LOGIC {self.id} --- Final Energy: {self.energy:.2f}, Radius: {self.radius:.2f}, Height={self.height:.2f}")

    def is_overcrowded(self, quadtree):
        search_area = Rectangle(self.x, self.y, C.PLANT_CROWDED_RADIUS_CM, C.PLANT_CROWDED_RADIUS_CM)
        neighbors = quadtree.query(search_area, [])
        return len(neighbors) > C.PLANT_MAX_NEIGHBORS

    def can_reproduce(self):
        """
        Overrides the base Creature method with more complex, realistic conditions for a Plant.
        A plant can reproduce if it is mature (has enough stored reproductive energy) AND
        has enough current energy to pay for both the fruit structure and the seed provisioning.
        """
        is_mature = self.reproductive_energy_stored >= C.PLANT_REPRODUCTION_MINIMUM_STORED_ENERGY
        total_current_cost = C.PLANT_FRUIT_STRUCTURAL_ENERGY_COST + C.PLANT_SEED_PROVISIONING_ENERGY
        has_enough_energy = self.energy >= total_current_cost
        return is_mature and has_enough_energy

    def reproduce(self, world, quadtree):
        """
        Overrides the base Creature method. Finds a valid spawn location and creates a new Plant
        with a specific provision of energy transferred from the parent.
        """
        
        # --- 1. Find a suitable location for the offspring ---
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

        # --- 2. If a location is found, pay the costs and create the new plant ---
        if best_location:
            log.log(f"DEBUG ({self.id}): Found a valid spawn location. Paying costs.")
            
            # Pay the dual energy costs
            self.energy -= (C.PLANT_FRUIT_STRUCTURAL_ENERGY_COST + C.PLANT_SEED_PROVISIONING_ENERGY)
            self.reproductive_energy_stored -= C.PLANT_REPRODUCTION_MINIMUM_STORED_ENERGY
            
            # Create the new plant, transferring the provisioned energy
            return Plant(world, best_location[0], best_location[1], initial_energy=C.PLANT_SEED_PROVISIONING_ENERGY)
        
        # --- 3. If no location is found, no costs are paid ---
        log.log(f"DEBUG ({self.id}): Failed to find a valid spawn location. No energy was lost.")
        return None

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