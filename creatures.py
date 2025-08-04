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

class ReproductiveOrgan:
    """A simple data class to represent a flower or a fruit on a plant."""
    def __init__(self, parent_plant):
        self.type = "flower" # Can be "flower" or "fruit"
        self.age = 0 # Age of the organ, in seconds (s)
        
        # Position is relative to the parent plant's center, on its canopy
        angle = random.uniform(0, 2 * math.pi)
        # Place it somewhere within the canopy, not just at the edge
        radius = random.uniform(0, parent_plant.radius) 
        self.relative_x = radius * math.cos(angle)
        self.relative_y = radius * math.sin(angle)
        self.world_x = parent_plant.x + self.relative_x
        self.world_y = parent_plant.y + self.relative_y

    def update(self, time_step):
        self.age += time_step
        if self.type == "flower" and self.age > C.PLANT_FLOWER_LIFESPAN_SECONDS:
            self.type = "fruit"
            self.age = 0 # Reset age for the fruit stage

    def is_ready_to_drop(self):
        return self.type == "fruit" and self.age > C.PLANT_FRUIT_LIFESPAN_SECONDS

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
        
        # --- NEW: Dynamic Morphology ---
        # Each plant has its own shape factor, which it adapts based on shade.
        self.radius_to_height_factor = C.PLANT_RADIUS_TO_HEIGHT_FACTOR

        self.reproductive_energy_stored = 0.0 # Energy invested in reproductive structures, in Joules (J)
        self.reproductive_organs = [] # NEW: List to hold flower/fruit objects
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
        search_area = Rectangle(self.x, self.y, C.PLANT_COMPETITION_SEARCH_RADIUS_CM, C.PLANT_COMPETITION_SEARCH_RADIUS_CM)
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
                self.height = self.radius * self.radius_to_height_factor # Use instance variable
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

        shade_ratio = (self.shaded_canopy_area / canopy_area) if canopy_area > 0 else 0

        if is_debug_focused:
            root_overlap_percent = (self.overlapped_root_area / root_area * 100) if root_area > 0 else 0
            log.log(f"    Competition: Shaded Area={self.shaded_canopy_area:.2f} ({shade_ratio*100:.1f}%), Root Overlap={self.overlapped_root_area:.2f} ({root_overlap_percent:.1f}%)")

        # --- NEW: Shade Avoidance Response (Dynamic Morphology) ---
        # The plant adjusts its shape based on how much shade it's in.
        # It interpolates between its base shape and its max "skinny" shape.
        target_factor = C.PLANT_RADIUS_TO_HEIGHT_FACTOR + (C.PLANT_MAX_SHADE_RADIUS_TO_HEIGHT_FACTOR - C.PLANT_RADIUS_TO_HEIGHT_FACTOR) * shade_ratio
        
        # Slowly move the current factor towards the target factor.
        self.radius_to_height_factor += (target_factor - self.radius_to_height_factor) * C.PLANT_MORPHOLOGY_ADAPTATION_RATE
        
        if is_debug_focused and abs(target_factor - self.radius_to_height_factor) > 0.01:
            log.log(f"    Morphology: Shade Ratio={shade_ratio:.2f}. Adjusting R/H Factor from {self.radius_to_height_factor:.2f} towards {target_factor:.2f}.")

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

        # --- NEW: Self-Pruning Logic ---
        # If the plant has an energy deficit, it sheds biomass to reduce maintenance costs
        # instead of just passively starving. This creates an emergent maximum size.
        if net_energy_production < 0:
            energy_deficit = abs(net_energy_production)
            
            # Calculate the cost to maintain 1 cm^2 of biomass for this tick.
            maintenance_cost_per_area_tick = C.PLANT_BASE_MAINTENANCE_RESPIRATION_PER_AREA * respiration_factor * time_step

            if maintenance_cost_per_area_tick > 0:
                # Calculate the total area of biomass that needs to be shed to offset the deficit.
                area_to_shed = (energy_deficit / maintenance_cost_per_area_tick) * C.PLANT_PRUNING_EFFICIENCY
                
                # Shed area proportionally from canopy and roots (non-core biomass).
                total_sheddable_area = canopy_area + root_area
                if total_sheddable_area > 0:
                    canopy_shed_fraction = canopy_area / total_sheddable_area
                    
                    shed_canopy_area = area_to_shed * canopy_shed_fraction
                    shed_root_area = area_to_shed * (1.0 - canopy_shed_fraction)

                    if is_debug_focused:
                        log.log(f"    PRUNING: Energy deficit of {energy_deficit:.4f} J. Shedding {area_to_shed:.2f} cm^2 of biomass.")
                        log.log(f"      - Old Radius: {self.radius:.2f} (Area: {canopy_area:.2f}). Shedding {shed_canopy_area:.2f} cm^2.")

                    # Calculate new areas and radii, ensuring they don't go below zero.
                    new_canopy_area = max(0, canopy_area - shed_canopy_area)
                    new_root_area = max(0, root_area - shed_root_area)
                    self.radius = math.sqrt(new_canopy_area / math.pi)
                    self.root_radius = math.sqrt(new_root_area / math.pi)
                    self.height = self.radius * self.radius_to_height_factor # Use instance variable

                    if is_debug_focused:
                        log.log(f"      - New Radius: {self.radius:.2f} (Area: {new_canopy_area:.2f}).")

            # By pruning, the plant has "paid" its energy deficit for this tick with biomass.
            # We set net production to zero to prevent a "double penalty" (losing biomass AND stored energy).
            net_energy_production = 0

        self.energy += net_energy_production

        if is_debug_focused:
            log.log(f"    Efficiencies: Env={self.environment_eff:.3f}, Soil={soil_eff:.3f}, Aging={aging_efficiency:.3f}, Hydraulic={hydraulic_efficiency:.3f}")
            log.log(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net (Post-Pruning)={net_energy_production:.4f}")

        if self.energy <= 0:
            self.die(world, "starvation")
            if is_debug_focused: log.log(f"  Plant {self.id} ({self.life_stage}) died from starvation. Final Energy: {self.energy:.2f}")
            return

        if not self.has_reached_self_sufficiency and net_energy_production > 0:
            self.has_reached_self_sufficiency = True
            self.life_stage = "mature" # Transition from seedling to mature
            if is_debug_focused: log.log(f"    MILESTONE ({self.id}): Seedling reached self-sufficiency and is now mature!")

        # --- REVISED ENERGY ALLOCATION LOGIC ---
        # 1. Mature plants invest in creating flowers.
        if self.life_stage == "mature":
            desired_repro_investment = (C.PLANT_REPRODUCTIVE_INVESTMENT_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
            available_for_repro = max(0, self.energy - C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE)
            actual_repro_investment = min(desired_repro_investment, available_for_repro)

            if actual_repro_investment > 0:
                self.energy -= actual_repro_investment
                self.reproductive_energy_stored += actual_repro_investment
                
                # Check if we can create new flowers
                num_new_flowers = int(self.reproductive_energy_stored // C.PLANT_FLOWER_ENERGY_COST)
                max_flowers = int(canopy_area * C.PLANT_MAX_FLOWERS_PER_CANOPY_AREA)
                allowed_new_flowers = max(0, max_flowers - len(self.reproductive_organs))
                num_new_flowers = min(num_new_flowers, allowed_new_flowers)

                if num_new_flowers > 0:
                    cost_of_flowers = num_new_flowers * C.PLANT_FLOWER_ENERGY_COST
                    self.reproductive_energy_stored -= cost_of_flowers
                    for _ in range(num_new_flowers):
                        self.reproductive_organs.append(ReproductiveOrgan(self))
                    if is_debug_focused:
                        log.log(f"    Allocation (Reproductive): Invested {actual_repro_investment:.4f} J. Stored ReproEnergy: {self.reproductive_energy_stored:.2f} J. Creating {num_new_flowers} new flowers.")
                elif is_debug_focused:
                    log.log(f"    Allocation (Reproductive): Invested {actual_repro_investment:.4f} J. Stored ReproEnergy: {self.reproductive_energy_stored:.2f} J. (Max flowers reached or not enough energy for one).")

        # 2. Remaining surplus and reserves are allocated to growth.
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

        # NOTE: The old reproduction check is removed from here.
        # Dispersal is now handled in the main update method based on fruit state.
        
        if growth_energy > 0:
            # --- DYNAMIC CORE GROWTH ALLOCATION ---
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
                    self.height = self.radius * self.radius_to_height_factor # Use instance variable
                
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
                            #if is_debug_focused:
                                #log.log(f"      - Crush Check: vs Neighbor {neighbor.id}. Dist^2={dist_sq:.2f}, My Core Radius^2={self.core_radius**2:.2f}")
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

        # --- NEW: Update and manage reproductive organs ---
        if self.is_alive and self.life_stage == "mature":
            fruits_to_drop = []
            for organ in self.reproductive_organs:
                organ.update(time_step)
                if organ.is_ready_to_drop():
                    fruits_to_drop.append(organ)
            
            if fruits_to_drop:
                # Check if we have enough provisioning energy for at least one seed
                if self.energy >= C.PLANT_SEED_PROVISIONING_ENERGY:
                    for fruit in fruits_to_drop:
                        # Attempt to disperse a seed for each dropped fruit
                        # We must re-check energy each time, as we might run out
                        if self.energy >= C.PLANT_SEED_PROVISIONING_ENERGY:
                            new_seed = self._disperse_seed(world, fruit, is_debug_focused)
                            if new_seed:
                                self.energy -= C.PLANT_SEED_PROVISIONING_ENERGY
                                world.add_newborn(new_seed)
                        else:
                            if is_debug_focused: log.log(f"    REPRODUCTION: Fruit dropped, but not enough energy to provision a seed. Aborting further dispersal.")
                            break # Stop trying to disperse if we're out of energy
                        self.reproductive_organs.remove(fruit)
                elif is_debug_focused:
                    log.log(f"    REPRODUCTION: Fruits are ready to drop, but plant lacks energy to provision a seed ({self.energy:.2f} < {C.PLANT_SEED_PROVISIONING_ENERGY}).")

        if is_debug_focused:
            log.log(f"--- END LOGIC {self.id} --- Final Energy: {self.energy:.2f}")

    def _disperse_seed(self, world, fruit, is_debug_focused):
        """
        Handles the 'fall and roll' physics for a dropped fruit to find a new seed location.
        This is the core of the new emergent dispersal system.
        """
        # 1. Determine the starting point of the roll (the "Fall and Bounce" model)
        # The fruit grew at fruit.world_x/y, but it falls and tumbles to the edge of the canopy.
        origin_x, origin_y = fruit.world_x, fruit.world_y

        # Vector from parent's center to the fruit's growth spot
        vec_x = origin_x - self.x
        vec_y = origin_y - self.y
        dist_from_center = math.sqrt(vec_x**2 + vec_y**2)

        # Normalize the vector and scale it by the parent's full radius to find the drop point on the circumference
        if dist_from_center > 0:
            drop_x = self.x + (vec_x / dist_from_center) * self.radius
            drop_y = self.y + (vec_y / dist_from_center) * self.radius
        else: # If fruit grew at the exact center, pick a random edge point
            angle = random.uniform(0, 2 * math.pi)
            drop_x = self.x + self.radius * math.cos(angle)
            drop_y = self.y + self.radius * math.sin(angle)

        # 2. Determine slope at the drop point
        # Sample elevation at and around the drop point to find the steepest downhill gradient
        e_center = world.environment.get_elevation(drop_x, drop_y)
        e_north = world.environment.get_elevation(drop_x, drop_y - 10)
        e_south = world.environment.get_elevation(drop_x, drop_y + 10)
        e_east = world.environment.get_elevation(drop_x + 10, drop_y)
        e_west = world.environment.get_elevation(drop_x - 10, drop_y)

        grad_y = e_north - e_south # Positive means downhill is South
        grad_x = e_west - e_east  # Positive means downhill is East

        # 3. Calculate roll distance and direction
        magnitude = math.sqrt(grad_x**2 + grad_y**2)
        roll_distance = C.PLANT_SEED_ROLL_BASE_DISTANCE_CM
        
        if magnitude > 0.001: # Avoid division by zero and tiny movements
            roll_dir_x = grad_x / magnitude
            roll_dir_y = grad_y / magnitude
            roll_distance += magnitude * C.PLANT_SEED_ROLL_DISTANCE_FACTOR
        else: # On flat ground, roll in a random direction
            angle = random.uniform(0, 2 * math.pi)
            roll_dir_x = math.cos(angle)
            roll_dir_y = math.sin(angle)

        final_x = drop_x + roll_dir_x * roll_distance
        final_y = drop_y + roll_dir_y * roll_distance

        if is_debug_focused:
            log.log(f"    REPRODUCTION: Fruit dropped from parent {self.id}. Origin: ({origin_x:.1f}, {origin_y:.1f}) -> Drop Point: ({drop_x:.1f}, {drop_y:.1f}). Slope: {magnitude:.4f}. Roll Dist: {roll_distance:.1f}cm. Final Pos: ({final_x:.1f}, {final_y:.1f}).")

        # 4. Validate the final location
        final_elevation = world.environment.get_elevation(final_x, final_y)
        if final_elevation < C.TERRAIN_WATER_LEVEL:
            if is_debug_focused: log.log(f"      - Dispersal FAILED: Seed landed in water.")
            return None

        search_area = Rectangle(final_x, final_y, C.PLANT_CORE_PERSONAL_SPACE_FACTOR, C.PLANT_CORE_PERSONAL_SPACE_FACTOR)
        neighbors = world.quadtree.query(search_area, [])
        for neighbor in neighbors:
            if isinstance(neighbor, Plant):
                dist_sq = (final_x - neighbor.x)**2 + (final_y - neighbor.y)**2
                if dist_sq < neighbor.get_personal_space_radius()**2:
                    if is_debug_focused: log.log(f"      - Dispersal FAILED: Seed landed too close to neighbor {neighbor.id}'s core.")
                    return None
        
        # 5. Create the new seed if the location is valid
        if is_debug_focused: log.log(f"      - Dispersal SUCCESS: Creating new seed.")
        return Plant(world, final_x, final_y, initial_energy=C.PLANT_SEED_PROVISIONING_ENERGY)
        e_north = world.environment.get_elevation(start_x, start_y - 10)
        e_south = world.environment.get_elevation(start_x, start_y + 10)
        e_east = world.environment.get_elevation(start_x + 10, start_y)
        e_west = world.environment.get_elevation(start_x - 10, start_y)

        grad_y = e_north - e_south # Positive means downhill is South
        grad_x = e_west - e_east  # Positive means downhill is East

        # 2. Calculate roll distance and direction
        magnitude = math.sqrt(grad_x**2 + grad_y**2)
        roll_distance = C.PLANT_SEED_ROLL_BASE_DISTANCE_CM
        
        if magnitude > 0.001: # Avoid division by zero and tiny movements
            # Roll direction is the inverse of the gradient (downhill)
            roll_dir_x = grad_x / magnitude
            roll_dir_y = grad_y / magnitude
            # Roll distance is proportional to the steepness (magnitude of the gradient)
            roll_distance += magnitude * C.PLANT_SEED_ROLL_DISTANCE_FACTOR
        else: # On flat ground, roll in a random direction
            angle = random.uniform(0, 2 * math.pi)
            roll_dir_x = math.cos(angle)
            roll_dir_y = math.sin(angle)

        final_x = start_x + roll_dir_x * roll_distance
        final_y = start_y + roll_dir_y * roll_distance

        if is_debug_focused:
            log.log(f"    REPRODUCTION: Fruit dropped from parent {self.id}. Start Pos: ({start_x:.1f}, {start_y:.1f}). Slope: {magnitude:.4f}. Roll Dist: {roll_distance:.1f}cm. Final Pos: ({final_x:.1f}, {final_y:.1f}).")

        # 3. Validate the final location
        # Check if it's in a valid biome (not water)
        final_elevation = world.environment.get_elevation(final_x, final_y)
        if final_elevation < C.TERRAIN_WATER_LEVEL:
            if is_debug_focused: log.log(f"      - Dispersal FAILED: Seed landed in water.")
            return None

        # Check if the location is overcrowded by other plants' cores
        search_area = Rectangle(final_x, final_y, C.PLANT_CORE_PERSONAL_SPACE_FACTOR, C.PLANT_CORE_PERSONAL_SPACE_FACTOR)
        neighbors = world.quadtree.query(search_area, [])
        for neighbor in neighbors:
            if isinstance(neighbor, Plant):
                dist_sq = (final_x - neighbor.x)**2 + (final_y - neighbor.y)**2
                if dist_sq < neighbor.get_personal_space_radius()**2:
                    if is_debug_focused: log.log(f"      - Dispersal FAILED: Seed landed too close to neighbor {neighbor.id}'s core.")
                    return None
        
        # 4. Create the new seed if the location is valid
        if is_debug_focused: log.log(f"      - Dispersal SUCCESS: Creating new seed.")
        return Plant(world, final_x, final_y, initial_energy=C.PLANT_SEED_PROVISIONING_ENERGY)

    def can_reproduce(self):
        # This method is now effectively deprecated and replaced by the fruit-dropping mechanism.
        # It can be removed or left for future animal-specific logic.
        return False

    def calculate_environment_efficiency(self, temperature, humidity):
        temp_diff = abs(temperature - self.genes.optimal_temperature)
        temp_eff = math.exp(-((temp_diff / self.genes.temperature_tolerance)**2))
        hum_diff = abs(humidity - self.genes.optimal_humidity)
        hum_eff = math.exp(-((hum_diff / self.genes.humidity_tolerance)**2))
        return temp_eff * hum_eff

    def draw(self, screen, camera):
        screen_pos = camera.world_to_screen(self.x, self.y)

        if self.life_stage == "seed":
            # Draw a small, visible marker for seeds
            pygame.draw.circle(screen, C.COLOR_PLANT_SEED, screen_pos, 2)
            return

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
            
        # --- NEW: Draw flowers and fruits ---
        for organ in self.reproductive_organs:
            organ_pos = camera.world_to_screen(self.x + organ.relative_x, self.y + organ.relative_y)
            organ_radius = 2 # Fixed pixel size for visibility
            color = C.COLOR_PLANT_FLOWER if organ.type == "flower" else C.COLOR_PLANT_FRUIT
            pygame.draw.circle(screen, color, organ_pos, organ_radius)

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