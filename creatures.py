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

    def die(self, world, cause):
        if self.is_alive:
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
        self.genes = PlantGenes()
        
        # --- NEW: Life Cycle State ---
        self.life_stage = "seed" # Start as a seed
        
        # Physical properties are 0 until sprouting.
        self.radius = 0 # Canopy radius, in centimeters (cm)
        self.height = 0 # Canopy height, in centimeters (cm)
        self.root_radius = 0 # Root system radius, in centimeters (cm)
        self.core_radius = 0 # Structural core radius, in centimeters (cm)
        
        self.reproductive_energy_stored = 0.0 # Energy invested in reproductive structures, in Joules (J)
        self.competition_factor = 1.0 # DEPRECATED, will be removed later.
        self.competition_update_accumulator = 0.0 # Time since last competition check, in seconds (s)
        self.has_reached_self_sufficiency = False # Has the plant ever had a positive energy balance?
        self.shaded_canopy_area = 0.0 # The area of our canopy shaded by neighbors, in cm^2
        self.overlapped_root_area = 0.0 # The area of our roots competing with neighbors, in cm^2

        self.elevation = world.environment.get_elevation(self.x, self.y)  # Cached elevation, unitless [0, 1]
        self.soil_type = self.get_soil_type(self.elevation)  # Type of soil at location (e.g., "sand", "grass")
        
        if self.soil_type is None:
            log.log(f"DEBUG ({self.id}): Seed landed on invalid terrain. Marking for death.")
            self.is_alive = False
            self.energy = 0
            return

        self.temperature = world.environment.get_temperature(self.x, self.y)
        self.humidity = world.environment.get_humidity(self.x, self.y)
        self.environment_eff = self.calculate_environment_efficiency(self.temperature, self.humidity)

    def get_personal_space_radius(self):
        return self.core_radius * C.PLANT_CORE_PERSONAL_SPACE_FACTOR

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

    def _update_seed(self, world, time_step, is_debug_focused):
        """Logic for when the plant is a dormant seed."""
        # --- 1. Dormancy Metabolism ---
        dormancy_cost = (C.PLANT_DORMANCY_METABOLISM_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
        self.energy -= dormancy_cost

        if self.energy <= 0:
            if is_debug_focused: log.log(f"DEBUG ({self.id}): Seed ran out of energy.")
            self.die(world, "dormancy_failure")
            return

        # --- 2. Check Germination Conditions ---
        temp_ok = C.GERMINATION_MIN_TEMP <= self.temperature <= C.GERMINATION_MAX_TEMP
        humidity_ok = self.humidity >= C.GERMINATION_HUMIDITY_THRESHOLD
        
        if temp_ok and humidity_ok:
            if self.energy >= C.PLANT_SPROUTING_ENERGY_COST:
                self.energy -= C.PLANT_SPROUTING_ENERGY_COST
                self.life_stage = "seedling"
                self.radius = C.PLANT_SPROUT_RADIUS_CM
                self.root_radius = C.PLANT_SPROUT_RADIUS_CM
                self.core_radius = C.PLANT_SPROUT_CORE_RADIUS_CM
                self.height = self.radius * C.PLANT_RADIUS_TO_HEIGHT_FACTOR
            elif is_debug_focused:
                log.log(f"DEBUG ({self.id}): Conditions met to sprout, but not enough energy ({self.energy:.2f} < {C.PLANT_SPROUTING_ENERGY_COST}).")
        elif is_debug_focused:
            log.log(f"DEBUG ({self.id}): Seed remains dormant. Temp OK: {temp_ok} (is {self.temperature:.2f}), Humidity OK: {humidity_ok} (is {self.humidity:.2f}).")

    def _update_growing_plant(self, world, time_step, is_debug_focused):
        """Unified logic for seedlings and mature plants."""
        if is_debug_focused:
            log.log(f" State ({self.life_stage}): Energy={self.energy:.2f}, ReproEnergy={self.reproductive_energy_stored:.2f}, Radius={self.radius:.2f}, Height={self.height:.2f}")

# --- CORE BIOLOGY LOGIC (Calculations now use time_step directly) ---
        self.competition_update_accumulator += time_step
        if self.competition_update_accumulator >= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS:
            if is_debug_focused: log.log(f"DEBUG ({self.id}): Recalculating physical competition.")
            self.shaded_canopy_area, self.overlapped_root_area = self.calculate_physical_overlap(world.quadtree)
            self.competition_update_accumulator %= C.PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS

        canopy_area = math.pi * self.radius**2
        root_area = math.pi * self.root_radius**2

        if is_debug_focused:
            shade_percent = (self.shaded_canopy_area / canopy_area * 100) if canopy_area > 0 else 0
            root_overlap_percent = (self.overlapped_root_area / root_area * 100) if root_area > 0 else 0
            log.log(f"    Competition: Shaded Area={self.shaded_canopy_area:.2f} ({shade_percent:.1f}%), Root Overlap={self.overlapped_root_area:.2f} ({root_overlap_percent:.1f}%)")

        # --- NEW: Calculate root competition efficiency ---
        effective_root_area = max(0, root_area - self.overlapped_root_area)
        root_competition_eff = effective_root_area / root_area if root_area > 0 else 0

        max_soil_eff = self.genes.soil_efficiency.get(self.soil_type, 0)
        root_to_canopy_ratio = self.root_radius / (self.radius + 1)
                # --- CHANGE: Soil efficiency is now penalized by root competition ---
        soil_eff = max_soil_eff * min(1.0, root_to_canopy_ratio * C.PLANT_ROOT_EFFICIENCY_FACTOR) * root_competition_eff
        aging_efficiency = math.exp(-(self.age / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))
        # --- NEW: Calculate hydraulic efficiency based on height ---
        hydraulic_efficiency = math.exp(-(self.height / C.PLANT_MAX_HYDRAULIC_HEIGHT_CM))
        
        effective_canopy_area = max(0, canopy_area - self.shaded_canopy_area)
        
        if is_debug_focused:
            log.log(f"    Energy Calc: Effective Canopy={effective_canopy_area:.2f} (Total: {canopy_area:.2f})")
            log.log(f"    Efficiencies: Env={self.environment_eff:.3f}, Soil={soil_eff:.3f} (Root Comp Eff: {root_competition_eff:.3f}), Aging={aging_efficiency:.3f}, Hydraulic={hydraulic_efficiency:.3f}")

        photosynthesis_gain = effective_canopy_area * C.PLANT_PHOTOSYNTHESIS_PER_AREA * self.environment_eff * soil_eff * aging_efficiency * hydraulic_efficiency * time_step 
        
        temp_difference = self.temperature - C.PLANT_RESPIRATION_REFERENCE_TEMP
        respiration_factor = C.PLANT_Q10_FACTOR ** (temp_difference / C.PLANT_Q10_INTERVAL_DIVISOR)
        core_area = math.pi * self.core_radius**2 # Calculate the area of the structural core
        metabolism_cost = (canopy_area + root_area + core_area) * C.PLANT_BASE_MAINTENANCE_RESPIRATION_PER_AREA * respiration_factor * time_step
        
        net_energy_production = photosynthesis_gain - metabolism_cost
        self.energy += net_energy_production

        if is_debug_focused:
            log.log(f"    Efficiencies: Env={self.environment_eff:.3f}, Soil={soil_eff:.3f}, Aging={aging_efficiency:.3f}, Hydraulic={hydraulic_efficiency:.3f}")
            log.log(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net={net_energy_production:.4f}")

        if self.energy <= 0:
            self.die(world, "starvation")
            if is_debug_focused: log.log(f"  Plant {self.id} ({self.life_stage}) died from starvation. Final Energy: {self.energy:.2f}")
            return

        if not self.has_reached_self_sufficiency and net_energy_production > 0:
            self.has_reached_self_sufficiency = True
            self.life_stage = "mature" # Transition from seedling to mature
            if is_debug_focused: log.log(f"    MILESTONE ({self.id}): Seedling reached self-sufficiency and is now mature!")

        # --- NEW: REVISED ENERGY ALLOCATION LOGIC ---
        # Mature plants first prioritize storing energy for reproduction.
        if self.life_stage == "mature":
            desired_repro_investment = (C.PLANT_REPRODUCTIVE_INVESTMENT_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
            # Can only invest if it doesn't drop below critical energy reserves.
            available_for_repro = max(0, self.energy - C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE)
            actual_repro_investment = min(desired_repro_investment, available_for_repro)

            if actual_repro_investment > 0:
                self.energy -= actual_repro_investment
                self.reproductive_energy_stored += actual_repro_investment
                if is_debug_focused:
                    log.log(f"    Allocation (Reproductive): Invested {actual_repro_investment:.4f} J into storage. New ReproEnergy: {self.reproductive_energy_stored:.2f} J.")

        # Second, remaining surplus and reserves are allocated to growth.
        investment_from_reserves = 0
        if self.energy > C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE:
            desired_investment = (C.PLANT_GROWTH_INVESTMENT_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
            available_from_reserves = self.energy - C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE
            investment_from_reserves = min(desired_investment, available_from_reserves)
            self.energy -= investment_from_reserves

        # The energy available for growth is the net production plus any amount taken from reserves.
        growth_energy = max(0, net_energy_production) + investment_from_reserves

        if is_debug_focused:
            if growth_energy > 0:
                log.log(f"    Allocation (Growth): Total pool {growth_energy:.4f} J available for growth.")
            else:
                log.log(f"    Allocation: No surplus energy or reserves to invest in growth.")

        if self.life_stage == "mature" and self.can_reproduce() and not self.is_overcrowded(world.quadtree):
            if is_debug_focused: log.log(f"    Reproduction Check: Conditions met. Attempting to spawn.")
            new_plant = self.reproduce(world, world.quadtree)
            if new_plant:
                world.add_newborn(new_plant)
                if is_debug_focused: log.log(f"    Reproduction SUCCESS. ReproEnergy: {self.reproductive_energy_stored:.2f} J.")
        
        if growth_energy > 0:
            # --- NEW: DYNAMIC CORE GROWTH ALLOCATION ---
            # The plant first determines if it needs to invest in its core for stability.
            core_investment = 0
            canopy_root_investment = growth_energy
            
            # Avoid division by zero for brand new plants
            if canopy_area > 1.0:
                current_ratio = (math.pi * self.core_radius**2) / canopy_area
                deficit = C.PLANT_IDEAL_CORE_TO_CANOPY_AREA_RATIO - current_ratio
                
                # If the plant is "top heavy", it must invest in its core.
                if deficit > 0:
                    # The priority is a value from 0-1 indicating how urgently we need to grow the core.
                    structural_priority = min(1.0, deficit / C.PLANT_IDEAL_CORE_TO_CANOPY_AREA_RATIO)
                    core_investment = growth_energy * structural_priority
                    canopy_root_investment = growth_energy - core_investment
                    if is_debug_focused:
                        log.log(f"    Allocation (Structural): Core/Canopy Ratio={current_ratio:.4f} (Ideal: {C.PLANT_IDEAL_CORE_TO_CANOPY_AREA_RATIO:.4f}), Deficit={deficit:.4f}")
                        log.log(f"    Allocation (Structural): Priority={structural_priority:.2f}. Investing {core_investment:.4f} J in Core, {canopy_root_investment:.4f} J in Canopy/Roots.")

            total_limitation = self.environment_eff + soil_eff
            if total_limitation > 0:
                old_core_radius = self.core_radius

                # 1. Grow the Core
                if core_investment > 0:
                    # --- CHANGE: Use the new, more expensive constant for core growth ---
                    added_core_area = core_investment / C.PLANT_CORE_BIOMASS_ENERGY_COST
                    new_core_area = (math.pi * self.core_radius**2) + added_core_area
                    self.core_radius = math.sqrt(new_core_area / math.pi)

                # 2. Grow Canopy and Roots with remaining energy
                if canopy_root_investment > 0:
                    added_biomass_area = canopy_root_investment / C.PLANT_BIOMASS_ENERGY_COST
                    canopy_alloc_factor = soil_eff / total_limitation
                    root_alloc_factor = self.environment_eff / total_limitation
                    added_canopy_area = added_biomass_area * canopy_alloc_factor
                    added_root_area = added_biomass_area * root_alloc_factor
                    
                    new_canopy_area = canopy_area + added_canopy_area
                    self.radius = math.sqrt(new_canopy_area / math.pi)
                    new_root_area = root_area + added_root_area
                    self.root_radius = math.sqrt(new_root_area / math.pi)
                    self.height = self.radius * C.PLANT_RADIUS_TO_HEIGHT_FACTOR
                
                if is_debug_focused:
                    log.log(f"      - Growth: New Radius={self.radius:.2f}, New Core Radius={self.core_radius:.2f}")

                # --- OPTIMIZATION: Crush check uses the new independent core_radius ---
                if self.core_radius > old_core_radius:
                    search_area = Rectangle(self.x, self.y, self.core_radius, self.core_radius)
                    neighbors = world.quadtree.query(search_area, [])
                    for neighbor in neighbors:
                        if neighbor is self or not isinstance(neighbor, Plant) or not neighbor.is_alive:
                            continue
                        
                        if neighbor.radius < self.core_radius:
                            dist_sq = (self.x - neighbor.x)**2 + (self.y - neighbor.y)**2
                            if is_debug_focused:
                                log.log(f"      - Crush Check: vs Neighbor {neighbor.id}. Dist^2={dist_sq:.2f}, My Core Radius^2={self.core_radius**2:.2f}")
                            if dist_sq < self.core_radius**2:
                                neighbor_is_debug_focused = (world.debug_focused_creature_id == neighbor.id)
                                if is_debug_focused or neighbor_is_debug_focused:
                                    log.log(f"DEATH ({neighbor.id}): Crushed by the growing core of Plant ID {self.id}.")
                                neighbor.die(world, "core_crush")

            elif is_debug_focused:
                log.log(f"      - Decision: CANNOT GROW (Total limitation factor is zero).")

    def update(self, world, time_step):
        if not self.is_alive: return

        self.age += time_step
        is_debug_focused = (world.debug_focused_creature_id == self.id)

        if is_debug_focused:
            log.log(f"\n--- PLANT {self.id} LOGIC (Age: {self.age/C.SECONDS_PER_DAY:.1f} days, Stage: {self.life_stage}) ---")
            log.log(f"  Processing tick of {time_step:.2f}s.")

        if self.life_stage == "seed":
            self._update_seed(world, time_step, is_debug_focused)
        else:  # "seedling" or "mature"
            self._update_growing_plant(world, time_step, is_debug_focused)
        
        if is_debug_focused:
            log.log(f"--- END LOGIC {self.id} --- Final Energy: {self.energy:.2f}")

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
        # --- NEW: Must be in the 'mature' life stage to reproduce ---
        is_biologically_mature = self.life_stage == "mature"
        has_stored_energy = self.reproductive_energy_stored >= C.PLANT_REPRODUCTION_MINIMUM_STORED_ENERGY
        total_current_cost = C.PLANT_FRUIT_STRUCTURAL_ENERGY_COST + C.PLANT_SEED_PROVISIONING_ENERGY
        has_enough_energy = self.energy >= total_current_cost
        return is_biologically_mature and has_stored_energy and has_enough_energy

    def reproduce(self, world, quadtree):
        """
        Overrides the base Creature method. Finds a valid spawn location and creates a new Plant
        with a specific provision of energy transferred from the parent.
        This method is heavily optimized to reduce quadtree queries.
        """
        is_debug_focused = (world.debug_focused_creature_id == self.id)

        # --- 1. Find a suitable location for the offspring (HIGHLY OPTIMIZED) ---
        # Step A: Perform ONE query to get all potential neighbors in the entire seed spread area.
        search_area = Rectangle(self.x, self.y, C.PLANT_SEED_SPREAD_RADIUS_CM, C.PLANT_SEED_SPREAD_RADIUS_CM)
        neighbors = [p for p in quadtree.query(search_area, []) if isinstance(p, Plant) and p is not self]

        best_location = None
        
        # Step B: Try to find a spot with zero neighbors first. This is the ideal case.
        for _ in range(C.PLANT_REPRODUCTION_ATTEMPTS):
            spawn_angle = random.uniform(0, 2 * math.pi)
            spawn_dist = random.uniform(0, C.PLANT_SEED_SPREAD_RADIUS_CM)
            candidate_x = self.x + spawn_dist * math.cos(spawn_angle)
            candidate_y = self.y + spawn_dist * math.sin(spawn_angle)

            is_valid = True
            for neighbor in neighbors:
                # Check if the candidate point is inside the neighbor's personal space.
                # This is the crucial bug fix.
                dist_sq = (candidate_x - neighbor.x)**2 + (candidate_y - neighbor.y)**2
                if dist_sq < neighbor.get_personal_space_radius()**2:
                    is_valid = False
                    break # Collision detected, this candidate is invalid.
            
            if is_valid:
                best_location = (candidate_x, candidate_y)
                break # Found a perfect spot, no need to search further.

        # --- 2. If a location is found, pay the costs and create the new plant ---
        if best_location:
            if is_debug_focused: log.log(f"DEBUG ({self.id}): Found a valid spawn location at ({best_location[0]:.1f}, {best_location[1]:.1f}). Paying costs.")
            
            # Pay the dual energy costs
            self.energy -= (C.PLANT_FRUIT_STRUCTURAL_ENERGY_COST + C.PLANT_SEED_PROVISIONING_ENERGY)
            self.reproductive_energy_stored -= C.PLANT_REPRODUCTION_MINIMUM_STORED_ENERGY
            
            # Create the new plant, transferring the provisioned energy
            return Plant(world, best_location[0], best_location[1], initial_energy=C.PLANT_SEED_PROVISIONING_ENERGY)
        
        # --- 3. If no location is found, no costs are paid ---
        if is_debug_focused: log.log(f"DEBUG ({self.id}): Failed to find a valid spawn location. No energy was lost.")
        return None

    def calculate_environment_efficiency(self, temperature, humidity):
        temp_diff = abs(temperature - self.genes.optimal_temperature)
        temp_eff = math.exp(-((temp_diff / self.genes.temperature_tolerance)**2))
        hum_diff = abs(humidity - self.genes.optimal_humidity)
        hum_eff = math.exp(-((hum_diff / self.genes.humidity_tolerance)**2))
        return temp_eff * hum_eff

    def draw(self, screen, camera):
        if self.life_stage == "seed":
            return

        screen_pos = camera.world_to_screen(self.x, self.y)
        canopy_radius = camera.scale(self.radius)
        if canopy_radius >= 1:
            canopy_surface = pygame.Surface((canopy_radius * 2, canopy_radius * 2), pygame.SRCALPHA)
            health_ratio = min(1.0, max(0.0, self.energy / C.CREATURE_REPRODUCTION_ENERGY_COST))
            canopy_color = lerp_color(C.COLOR_PLANT_CANOPY_SICKLY, C.COLOR_PLANT_CANOPY_HEALTHY, health_ratio)
            pygame.draw.circle(canopy_surface, canopy_color, (canopy_radius, canopy_radius), canopy_radius)
            screen.blit(canopy_surface, (screen_pos[0] - canopy_radius, screen_pos[1] - canopy_radius))
        core_radius = camera.scale(self.core_radius)
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