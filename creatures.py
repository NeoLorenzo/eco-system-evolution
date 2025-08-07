# creatures.py

import pygame
import constants as C
import random
import numpy as np
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
        angle = random.uniform(0, 2 * np.pi)
        # Place it somewhere within the canopy, not just at the edge
        radius = random.uniform(0, parent_plant.radius) 
        self.relative_x = radius * np.cos(angle)
        self.relative_y = radius * np.sin(angle)
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
        self.index = -1 # Will be set by the PlantManager upon registration.
        
        # --- Life Cycle State ---
        self.life_stage = "seed" # Start as a seed
        
        # Physical properties are 0 until sprouting.
        self.radius = 0 # Canopy radius, in centimeters (cm)
        self.height = 0 # Canopy height, in centimeters (cm)
        self.root_radius = 0 # Root system radius, in centimeters (cm)
        self.core_radius = 0 # Structural core radius, in centimeters (cm)
        
        # --- Dynamic Morphology ---
        # Each plant has its own shape factor, which it adapts based on shade.
        self.radius_to_height_factor = C.PLANT_RADIUS_TO_HEIGHT_FACTOR

        self.reproductive_energy_stored = 0.0 # Energy invested in reproductive structures, in Joules (J)
        self.reproductive_organs = [] # List to hold flower/fruit objects
        self.competition_factor = 1.0 # DEPRECATED, will be removed later.
        self.competition_update_accumulator = 0.0 # Time since last competition check, in seconds (s)
        self.has_reached_self_sufficiency = False # Has the plant ever had a positive energy balance?
        self.shaded_canopy_area = 0.0 # The area of our canopy shaded by neighbors, in cm^2
        self.overlapped_root_area = 0.0 # The area of our roots competing with neighbors, in cm^2
        self.core_growth_since_crush_check = 0.0 # Accumulated core radius growth for crush check, in cm
        self.last_graph_log_time = -1.0 # The sim time of the last data log for graphing.

        self.elevation = world.environment.get_elevation(self.x, self.y)  # Cached elevation, unitless [0, 1]
        self.soil_type = self.get_soil_type(self.elevation)  # Type of soil at location (e.g., "sand", "grass")
        
        if self.soil_type is None:
            log.log(f"DEBUG ({self.id}): Seed landed on invalid terrain. Marking for death.")
            self.is_alive = False
            self.energy = 0
            return

        self.temperature = world.environment.get_temperature(self.x, self.y)
        self.humidity = world.environment.get_humidity(self.x, self.y)
        # self.environment_eff is now removed. The value is calculated in bulk by PlantManager.

    def get_personal_space_radius(self):
        return self.core_radius * C.PLANT_CORE_PERSONAL_SPACE_FACTOR

    def get_soil_type(self, elevation):
        if C.TERRAIN_WATER_LEVEL <= elevation < C.TERRAIN_SAND_LEVEL: return "sand"
        elif C.TERRAIN_SAND_LEVEL <= elevation < C.TERRAIN_GRASS_LEVEL: return "grass"
        elif C.TERRAIN_GRASS_LEVEL <= elevation < C.TERRAIN_DIRT_LEVEL: return "dirt"
        else: return None

    def _patch_all_rates_after_sprout(self, world):
        """
        Calculates all vital rates for this plant immediately after sprouting
        and patches them into the PlantManager's NumPy arrays. This overcomes
        the issue of using stale data from the last bulk update.
        """
        pm = world.plant_manager
        idx = self.index

        # 1. Aging Efficiency
        pm.arrays['aging_efficiencies'][idx] = np.exp(-(self.age / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))

        # 2. Hydraulic Efficiency
        pm.arrays['hydraulic_efficiencies'][idx] = np.exp(-(self.height / C.PLANT_MAX_HYDRAULIC_HEIGHT_CM))

        # 3. Environmental Efficiency
        temp = self.temperature # Already cached on the plant object
        hum = self.humidity   # Already cached on the plant object
        temp_diff = np.abs(temp - self.genes.optimal_temperature)
        temp_eff = np.exp(-((temp_diff / self.genes.temperature_tolerance)**2))
        hum_diff = np.abs(hum - self.genes.optimal_humidity)
        hum_eff = np.exp(-((hum_diff / self.genes.humidity_tolerance)**2))
        environmental_efficiency = temp_eff * hum_eff
        pm.arrays['environmental_efficiencies'][idx] = environmental_efficiency

        # 4. Soil Efficiency (replaces the old, single patch)
        max_soil_eff = self.genes.soil_efficiency.get(self.soil_type, 0)
        root_to_canopy_ratio = self.root_radius / (self.radius + 1)
        ratio_modifier = min(1.0, root_to_canopy_ratio * C.PLANT_ROOT_EFFICIENCY_FACTOR)
        # At sprouting, there is no root competition.
        root_competition_eff = 1.0
        soil_efficiency = max_soil_eff * ratio_modifier * root_competition_eff
        pm.arrays['soil_efficiencies'][idx] = soil_efficiency

        # 5. Metabolism Cost
        canopy_area = np.pi * self.radius**2
        root_area = np.pi * self.root_radius**2
        core_area = np.pi * self.core_radius**2
        total_area = canopy_area + root_area + core_area
        temp_difference = temp - C.PLANT_RESPIRATION_REFERENCE_TEMP
        respiration_factor = C.PLANT_Q10_FACTOR ** (temp_difference / C.PLANT_Q10_INTERVAL_DIVISOR)
        metabolism_cost_per_second = total_area * C.PLANT_BASE_MAINTENANCE_RESPIRATION_PER_AREA * respiration_factor
        pm.arrays['metabolism_costs_per_second'][idx] = metabolism_cost_per_second
        pm.arrays['canopy_areas'][idx] = canopy_area # Also patch the cached canopy area

        # 6. Photosynthesis Gain
        # At sprouting, there is no shade.
        effective_canopy_area = canopy_area
        aging_efficiency = pm.arrays['aging_efficiencies'][idx]
        hydraulic_efficiency = pm.arrays['hydraulic_efficiencies'][idx]
        photosynthesis_gain_per_second = (effective_canopy_area *
                                          C.PLANT_PHOTOSYNTHESIS_PER_AREA *
                                          environmental_efficiency *
                                          soil_efficiency *
                                          aging_efficiency *
                                          hydraulic_efficiency)
        pm.arrays['photosynthesis_gains_per_second'][idx] = photosynthesis_gain_per_second

    def _update_seed(self, world, time_step, is_debug_focused):
        """Logic for when the plant is a dormant seed."""
        pm = world.plant_manager
        # --- 1. Dormancy Metabolism ---
        dormancy_cost = (C.PLANT_DORMANCY_METABOLISM_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
        self.energy -= dormancy_cost
        pm.arrays['energies'][self.index] = self.energy

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
                pm.arrays['energies'][self.index] = self.energy
                self.life_stage = "seedling"
                self.radius = C.PLANT_SPROUT_RADIUS_CM
                self.root_radius = C.PLANT_SPROUT_RADIUS_CM
                self.core_radius = C.PLANT_SPROUT_CORE_RADIUS_CM
                self.height = self.radius * self.radius_to_height_factor # Use instance variable
                
                # Update all manager arrays with new seedling values
                pm.arrays['heights'][self.index] = self.height
                pm.arrays['radii'][self.index] = self.radius
                pm.arrays['root_radii'][self.index] = self.root_radius
                pm.arrays['core_radii'][self.index] = self.core_radius

                # --- NEW COMPREHENSIVE PATCH ---
                # Immediately calculate and patch all vital rates for the new seedling
                # to prevent it from using stale (zero) data from the last bulk update.
                self._patch_all_rates_after_sprout(world)

                if is_debug_focused:
                    log.log(f"DEBUG ({self.id}): Sprouted! Patched all initial rates to prevent observer effect bug.")

            elif is_debug_focused:
                log.log(f"DEBUG ({self.id}): Conditions met to sprout, but not enough energy ({self.energy:.2f} < {C.PLANT_SPROUTING_ENERGY_COST}).")
        elif is_debug_focused:
            log.log(f"DEBUG ({self.id}): Seed remains dormant. Temp OK: {temp_ok} (is {self.temperature:.2f}), Humidity OK: {humidity_ok} (is {self.humidity:.2f}).")

    def _calculate_energy_balance(self, world, time_step, is_debug_focused):
        """
        Calculates net energy production based on environmental factors and competition.
        This includes photosynthesis, metabolism, and dynamic morphology adaptation.
        Returns:
            - net_energy_production (float): The net energy gain/loss for this tick, in Joules.
            - photosynthesis_gain (float): The gross energy produced, in Joules.
            - metabolism_cost (float): The gross energy consumed, in Joules.
            - canopy_area (float): The calculated canopy area, in cm^2.
            - root_area (float): The calculated root area, in cm^2.
            - core_area (float): The calculated core area, in cm^2.
        """
        # --- 1. Calculate current physical state ---
        canopy_area = np.pi * self.radius**2
        root_area = np.pi * self.root_radius**2
        core_area = np.pi * self.core_radius**2

        # --- 2. Adapt morphology based on competition ---
        shade_ratio = (self.shaded_canopy_area / canopy_area) if canopy_area > 0 else 0
        if is_debug_focused:
            root_overlap_percent = (self.overlapped_root_area / root_area * 100) if root_area > 0 else 0
            log.log(f"    Competition: Shaded Area={self.shaded_canopy_area:.2f} ({shade_ratio*100:.1f}%), Root Overlap={self.overlapped_root_area:.2f} ({root_overlap_percent:.1f}%)")

        target_factor = C.PLANT_RADIUS_TO_HEIGHT_FACTOR + (C.PLANT_MAX_SHADE_RADIUS_TO_HEIGHT_FACTOR - C.PLANT_RADIUS_TO_HEIGHT_FACTOR) * shade_ratio
        self.radius_to_height_factor += (target_factor - self.radius_to_height_factor) * C.PLANT_MORPHOLOGY_ADAPTATION_RATE
        
        if is_debug_focused and abs(target_factor - self.radius_to_height_factor) > 0.01:
            log.log(f"    Morphology: Shade Ratio={shade_ratio:.2f}. Adjusting R/H Factor from {self.radius_to_height_factor:.2f} towards {target_factor:.2f}.")

        # --- 3. Calculate all efficiency multipliers ---
        # Get pre-calculated efficiencies from the PlantManager's NumPy arrays.
        soil_eff = world.plant_manager.arrays['soil_efficiencies'][self.index]
        aging_efficiency = world.plant_manager.arrays['aging_efficiencies'][self.index]
        hydraulic_efficiency = world.plant_manager.arrays['hydraulic_efficiencies'][self.index]
        
        # --- 4. Calculate energy gain (Photosynthesis) ---
        # Look up the pre-calculated gain rate and scale it by the time step.
        photosynthesis_gain_per_second = world.plant_manager.arrays['photosynthesis_gains_per_second'][self.index]
        photosynthesis_gain = photosynthesis_gain_per_second * time_step
        
        # --- 5. Calculate energy loss (Metabolism) ---
        metabolism_cost_per_second = world.plant_manager.arrays['metabolism_costs_per_second'][self.index]
        metabolism_cost = metabolism_cost_per_second * time_step
        
        if is_debug_focused:
            # Re-calculate effective_canopy_area here just for the debug log.
            # The main calculation now uses the pre-computed value.
            shaded_canopy_area = world.plant_manager.arrays['shaded_canopy_areas'][self.index]
            effective_canopy_area = max(0, canopy_area - shaded_canopy_area)

            environmental_efficiency = world.plant_manager.arrays['environmental_efficiencies'][self.index]
            log.log(f"    Energy Calc: Effective Canopy={effective_canopy_area:.2f} (Total: {canopy_area:.2f})")
            # The 'Root Comp Eff' is now implicitly included in the 'Soil' efficiency value.
            
            # Recalculate self-shading eff here just for the log, as it's not stored in the manager.
            canopy_depth = self.radius * C.PLANT_CANOPY_DEPTH_TO_RADIUS_RATIO
            self_shading_eff = 1.0 / (1.0 + (canopy_depth / C.PLANT_CANOPY_HALF_EFFICIENCY_DEPTH_CM))
            log.log(f"    Efficiencies: Env={environmental_efficiency:.3f}, Soil={soil_eff:.3f}, Aging={aging_efficiency:.3f}, Hydraulic={hydraulic_efficiency:.3f}, Self-Shade={self_shading_eff:.3f}")

        net_energy_production = photosynthesis_gain - metabolism_cost
        
        return net_energy_production, photosynthesis_gain, metabolism_cost, canopy_area, root_area, core_area

    def _process_self_pruning(self, energy_deficit, canopy_area, root_area, core_area, world, time_step, is_debug_focused):
        """
        Handles the shedding of biomass when a plant has an energy deficit.
        This reduces the plant's size to lower its metabolic costs.
        Returns the new net_energy_production, which is always 0 after pruning.
        """
        total_sheddable_area = canopy_area + root_area + core_area
        metabolism_cost_per_second = world.plant_manager.arrays['metabolism_costs_per_second'][self.index]

        if total_sheddable_area > 0:
            maintenance_cost_per_area_tick = (metabolism_cost_per_second / total_sheddable_area) * time_step
        else:
            maintenance_cost_per_area_tick = 0

        if maintenance_cost_per_area_tick > 0:
            area_to_shed = (energy_deficit / maintenance_cost_per_area_tick) * C.PLANT_PRUNING_EFFICIENCY
            
            if total_sheddable_area > 0:
                canopy_fraction = canopy_area / total_sheddable_area
                root_fraction = root_area / total_sheddable_area
                core_fraction = core_area / total_sheddable_area
                
                shed_canopy_area = area_to_shed * canopy_fraction
                shed_root_area = area_to_shed * root_fraction
                shed_core_area = area_to_shed * core_fraction

                if is_debug_focused:
                    log.log(f"    PRUNING: Energy deficit of {energy_deficit:.4f} J. Shedding {area_to_shed:.2f} cm^2 of total biomass.")
                    log.log(f"      - Old Radii: Canopy={self.radius:.2f}, Core={self.core_radius:.2f}. Shedding {shed_canopy_area:.2f} (canopy), {shed_core_area:.2f} (core) cm^2.")

                new_canopy_area = max(0, canopy_area - shed_canopy_area)
                new_root_area = max(0, root_area - shed_root_area)
                new_core_area = max(0, core_area - shed_core_area)
                
                self.radius = np.sqrt(new_canopy_area / np.pi)
                self.root_radius = np.sqrt(new_root_area / np.pi)
                self.core_radius = np.sqrt(new_core_area / np.pi)
                self.height = self.radius * self.radius_to_height_factor

                pm = world.plant_manager
                pm.arrays['heights'][self.index] = self.height
                pm.arrays['radii'][self.index] = self.radius
                pm.arrays['root_radii'][self.index] = self.root_radius
                pm.arrays['core_radii'][self.index] = self.core_radius

                if is_debug_focused:
                    log.log(f"      - New Radii: Canopy={self.radius:.2f}, Core={self.core_radius:.2f}.")

        # By pruning, the plant has "paid" its energy deficit for this tick with biomass.
        # We return 0 to prevent a "double penalty" (losing biomass AND stored energy).
        return 0

    def _allocate_surplus_energy(self, net_energy_production, canopy_area, root_area, core_area, world, time_step, is_debug_focused):
        """
        Handles the investment of surplus energy into reproduction and growth.
        """
        # 1. Mature plants invest in creating flowers.
        # --- TEMPORARY DEBUG FLAG TO DISABLE REPRODUCTION ---
        if self.life_stage == "mature" and False:
            desired_repro_investment = (C.PLANT_REPRODUCTIVE_INVESTMENT_J_PER_HOUR / C.SECONDS_PER_HOUR) * time_step
            available_for_repro = max(0, self.energy - C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE)
            actual_repro_investment = min(desired_repro_investment, available_for_repro)

            if actual_repro_investment > 0:
                pm = world.plant_manager
                self.energy -= actual_repro_investment
                pm.arrays['energies'][self.index] = self.energy
                self.reproductive_energy_stored += actual_repro_investment
                pm.arrays['reproductive_energies_stored'][self.index] = self.reproductive_energy_stored
                
                num_new_flowers = int(self.reproductive_energy_stored // C.PLANT_FLOWER_ENERGY_COST)
                max_flowers = int(canopy_area * C.PLANT_MAX_FLOWERS_PER_CANOPY_AREA)
                allowed_new_flowers = max(0, max_flowers - len(self.reproductive_organs))
                num_new_flowers = min(num_new_flowers, allowed_new_flowers)

                if num_new_flowers > 0:
                    cost_of_flowers = num_new_flowers * C.PLANT_FLOWER_ENERGY_COST
                    self.reproductive_energy_stored -= cost_of_flowers
                    pm.arrays['reproductive_energies_stored'][self.index] = self.reproductive_energy_stored
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
            world.plant_manager.arrays['energies'][self.index] = self.energy

        growth_energy = max(0, net_energy_production) + investment_from_reserves

        if is_debug_focused:
            if growth_energy > 0:
                log.log(f"    Allocation (Growth): Total pool {growth_energy:.4f} J available for growth.")
            else:
                log.log(f"    Allocation: No surplus energy or reserves to invest in growth.")
        
        if growth_energy > 0:
            core_investment = 0
            canopy_root_investment = 0

            if canopy_area > 1.0:
                current_ratio = core_area / canopy_area
                
                if current_ratio < C.PLANT_IDEAL_CORE_TO_CANOPY_AREA_RATIO:
                    core_investment = growth_energy
                    if is_debug_focused:
                        log.log(f"    Allocation (Structural): RECOVERY MODE. Ratio={current_ratio:.4f} is below ideal {C.PLANT_IDEAL_CORE_TO_CANOPY_AREA_RATIO:.4f}.")
                        log.log(f"    Allocation (Structural): Investing 100% of growth energy ({growth_energy:.4f} J) into Core.")
                
                else:
                    core_investment = growth_energy * C.PLANT_STABLE_CORE_INVESTMENT_RATIO
                    canopy_root_investment = growth_energy * (1.0 - C.PLANT_STABLE_CORE_INVESTMENT_RATIO)
                    if is_debug_focused:
                        log.log(f"    Allocation (Structural): Normal Growth. Investing {core_investment:.4f} J in Core, {canopy_root_investment:.4f} J in Canopy/Roots.")

            else:
                core_investment = growth_energy * C.PLANT_STABLE_CORE_INVESTMENT_RATIO
                canopy_root_investment = growth_energy * (1.0 - C.PLANT_STABLE_CORE_INVESTMENT_RATIO)

            soil_eff = world.plant_manager.arrays['soil_efficiencies'][self.index]
            environmental_efficiency = world.plant_manager.arrays['environmental_efficiencies'][self.index]
            total_limitation = environmental_efficiency + soil_eff
            if total_limitation > 0:
                old_core_radius = self.core_radius

                if core_investment > 0:
                    added_core_area = core_investment / C.PLANT_CORE_BIOMASS_ENERGY_COST
                    new_core_area = (np.pi * self.core_radius**2) + added_core_area
                    self.core_radius = np.sqrt(new_core_area / np.pi)
                    world.plant_manager.arrays['core_radii'][self.index] = self.core_radius

                if canopy_root_investment > 0:
                    added_biomass_area = canopy_root_investment / C.PLANT_BIOMASS_ENERGY_COST
                    canopy_alloc_factor = soil_eff / total_limitation
                    root_alloc_factor = environmental_efficiency / total_limitation
                    added_canopy_area = added_biomass_area * canopy_alloc_factor
                    added_root_area = added_biomass_area * root_alloc_factor
                    
                    new_canopy_area = canopy_area + added_canopy_area
                    self.radius = np.sqrt(new_canopy_area / np.pi)
                    world.plant_manager.arrays['radii'][self.index] = self.radius

                    new_root_area = root_area + added_root_area
                    self.root_radius = np.sqrt(new_root_area / np.pi)
                    world.plant_manager.arrays['root_radii'][self.index] = self.root_radius

                    self.height = self.radius * self.radius_to_height_factor
                    world.plant_manager.arrays['heights'][self.index] = self.height
                
                if is_debug_focused:
                    log.log(f"      - Growth: New Radius={self.radius:.2f}, New Core Radius={self.core_radius:.2f}")

                if self.core_radius > old_core_radius:
                    self.core_growth_since_crush_check += self.core_radius - old_core_radius
                    
                    if self.core_growth_since_crush_check >= C.PLANT_CRUSH_CHECK_GROWTH_THRESHOLD_CM:
                        search_area = Rectangle(self.x, self.y, self.core_radius, self.core_radius)
                        neighbors = world.quadtree.query(search_area, [])
                        for neighbor in neighbors:
                            if neighbor is self or not isinstance(neighbor, Plant) or not neighbor.is_alive:
                                continue
                            
                            dist_sq = (self.x - neighbor.x)**2 + (self.y - neighbor.y)**2
                            if dist_sq < self.core_radius**2:
                                neighbor_is_debug_focused = (world.debug_focused_creature_id == neighbor.id)
                                if is_debug_focused or neighbor_is_debug_focused:
                                    log.log(f"DEATH ({neighbor.id}): Crushed by the growing core of Plant ID {self.id}.")
                                neighbor.die(world, "core_crush")
                        
                        self.core_growth_since_crush_check = 0.0

            elif is_debug_focused:
                log.log(f"      - Decision: CANNOT GROW (Total limitation factor is zero).")

    def _update_growing_plant(self, world, time_step, is_debug_focused):
        """Unified logic for seedlings and mature plants."""
        if is_debug_focused:
            log.log(f" State ({self.life_stage}): Energy={self.energy:.2f}, ReproEnergy={self.reproductive_energy_stored:.2f}, Radius={self.radius:.2f}, Height={self.height:.2f}")

        # --- 1. CORE BIOLOGY: Calculate Net Energy ---
        net_energy_production, photosynthesis_gain, metabolism_cost, canopy_area, root_area, core_area = self._calculate_energy_balance(world, time_step, is_debug_focused)

        # --- 2. Graphing Data Collection ---
        if is_debug_focused and world.time_manager.total_sim_seconds >= self.last_graph_log_time + C.GRAPHING_DATA_LOG_INTERVAL_SECONDS:
            # We log the net energy per hour for better readability on the graph
            net_energy_per_hour = net_energy_production / (time_step / C.SECONDS_PER_HOUR)
            world.graphing_manager.add_data_point(
                world.time_manager.total_sim_seconds, 
                net_energy_per_hour,
                self.height,
                self.radius,
                canopy_area,
                root_area,
                core_area
            )
            self.last_graph_log_time = world.time_manager.total_sim_seconds

        # --- 3. Branch Logic: Handle Energy Deficit OR Surplus ---
        if net_energy_production < 0:

            # --- STATE: ENERGY DEFICIT ---
            # A plant with a deficit has two options:
            # 1. Use its stored energy reserves (the "grace period" for seedlings).
            # 2. If reserves are low, prune biomass as a last resort.
            if self.energy > C.PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE:
                # Option 1: Cover the deficit from reserves. The net production remains negative
                # and will be subtracted from self.energy in the next step.
                if is_debug_focused:
                    log.log(f"    DEFICIT: Covering deficit of {abs(net_energy_production):.4f} J from reserves.")
            else:
                # Option 2: Reserves are low. Prune to survive.
                energy_deficit = abs(net_energy_production)
                net_energy_production = self._process_self_pruning(energy_deficit, canopy_area, root_area, core_area, world, time_step, is_debug_focused)
                # After pruning, check for catastrophic biomass loss.
                if self.radius < 0.1: # If the plant has pruned itself to nothing
                    if is_debug_focused: log.log(f"DEATH ({self.id}): Plant pruned itself into non-existence.")
                    self.die(world, "pruning_collapse")
                    return # End update immediately
        else:
            # --- STATE: ENERGY SURPLUS ---
            # A plant only allocates to growth/reproduction if it has a surplus.
            self._allocate_surplus_energy(net_energy_production, canopy_area, root_area, core_area, world, time_step, is_debug_focused)

        # --- 3. Update Stored Energy & Check for Starvation ---
        # Note: self.energy is only modified by _allocate_surplus_energy (spending reserves)
        # or by adding the net_energy_production from photosynthesis.
        self.energy += net_energy_production
        world.plant_manager.arrays['energies'][self.index] = self.energy

        if is_debug_focused:
            log.log(f"    Energy: Gained={photosynthesis_gain:.4f}, Lost={metabolism_cost:.4f}, Net (Post-Pruning/Allocation)={net_energy_production:.4f}")

        if self.energy <= 0:
            self.die(world, "starvation")
            if is_debug_focused: log.log(f"  Plant {self.id} ({self.life_stage}) died from starvation. Final Energy: {self.energy:.2f}")
            return

        # --- 4. Update Life Stage ---
        if not self.has_reached_self_sufficiency and net_energy_production > 0:
            self.has_reached_self_sufficiency = True
            self.life_stage = "mature"
            if is_debug_focused: log.log(f"    MILESTONE ({self.id}): Seedling reached self-sufficiency and is now mature!")

    def update(self, world, time_step):
        if not self.is_alive: return

        self.age += time_step
        # --- Update the master 'ages' array in the manager ---
        world.plant_manager.arrays['ages'][self.index] = self.age
        
        is_debug_focused = (world.debug_focused_creature_id == self.id)

        if is_debug_focused:
            log.log(f"\n--- PLANT {self.id} LOGIC (Age: {self.age/C.SECONDS_PER_DAY:.1f} days, Stage: {self.life_stage}) ---")
            log.log(f"  Processing tick of {time_step:.2f}s.")

        if self.life_stage == "seed":
            self._update_seed(world, time_step, is_debug_focused)
        else:  # "seedling" or "mature"
            self._update_growing_plant(world, time_step, is_debug_focused)

        # --- Update and manage reproductive organs ---
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
                                world.plant_manager.arrays['energies'][self.index] = self.energy
                                world.add_newborn(new_seed)
                        else:
                            if is_debug_focused: log.log(f"    REPRODUCTION: Fruit dropped, but not enough energy to provision a seed. Aborting further dispersal.")
                            break # Stop trying to disperse if we're out of energy
                        self.reproductive_organs.remove(fruit)
                elif is_debug_focused:
                    log.log(f"    REPRODUCTION: Fruits are ready to drop, but plant lacks energy to provision a seed ({self.energy:.2f} < {C.PLANT_SEED_PROVISIONING_ENERGY}).")

        # This check happens at the very end of the update, after all growth and pruning.
        if self.is_alive and self.life_stage != "seed":
            final_canopy_area = np.pi * self.radius**2
            if final_canopy_area > 1.0: # Only check for non-trivial plants
                final_core_area = np.pi * self.core_radius**2
                final_ratio = final_core_area / final_canopy_area
                if final_ratio < C.PLANT_MIN_CORE_TO_CANOPY_RATIO:
                    if is_debug_focused:
                        log.log(f"DEATH ({self.id}): Plant collapsed under its own weight. Core/Canopy Ratio was {final_ratio:.4f} (Min: {C.PLANT_MIN_CORE_TO_CANOPY_RATIO:.4f}).")
                    self.die(world, "structural_failure")

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
        dist_from_center = np.sqrt(vec_x**2 + vec_y**2)

        # Normalize the vector and scale it by the parent's full radius to find the drop point on the circumference
        if dist_from_center > 0:
            drop_x = self.x + (vec_x / dist_from_center) * self.radius
            drop_y = self.y + (vec_y / dist_from_center) * self.radius
        else: # If fruit grew at the exact center, pick a random edge point
            angle = random.uniform(0, 2 * np.pi)
            drop_x = self.x + self.radius * np.cos(angle)
            drop_y = self.y + self.radius * np.sin(angle)

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
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        roll_distance = C.PLANT_SEED_ROLL_BASE_DISTANCE_CM
        
        if magnitude > 0.001: # Avoid division by zero and tiny movements
            roll_dir_x = grad_x / magnitude
            roll_dir_y = grad_y / magnitude
            roll_distance += magnitude * C.PLANT_SEED_ROLL_DISTANCE_FACTOR
        else: # On flat ground, roll in a random direction
            angle = random.uniform(0, 2 * np.pi)
            roll_dir_x = np.cos(angle)
            roll_dir_y = np.sin(angle)

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
            
        # --- Draw flowers and fruits ---
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
                distance = np.sqrt(direction_x**2 + direction_y**2)
                
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
                norm = np.sqrt(move_x**2 + move_y**2)
                if norm > 0:
                    move_dist = C.ANIMAL_SPEED_CM_PER_SEC * time_step
                    self.x += (move_x / norm) * move_dist
                    self.y += (move_y / norm) * move_dist
                    moved = True # The animal moved

        if moved:
            world.update_creature_in_quadtree(self)

    def draw(self, screen, camera):
        screen_pos = camera.world_to_screen(self.x, self.y)
        screen_width = camera.scale(self.width)
        screen_height = camera.scale(self.height)
        if screen_width >= 1 and screen_height >= 1:
            rect_to_draw = (screen_pos[0], screen_pos[1], screen_width, screen_height)
            pygame.draw.rect(screen, self.color, rect_to_draw)