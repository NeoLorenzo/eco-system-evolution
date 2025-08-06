# plant_manager.py
import numpy as np
import constants as C
import logger as log

def calculate_environment_efficiency(temperature, humidity, genes):
    """Calculates environmental efficiency based on temperature and humidity."""
    temp_diff = np.abs(temperature - genes.optimal_temperature)
    temp_eff = np.exp(-((temp_diff / genes.temperature_tolerance)**2))
    hum_diff = np.abs(humidity - genes.optimal_humidity)
    hum_eff = np.exp(-((hum_diff / genes.humidity_tolerance)**2))
    return temp_eff * hum_eff

class PlantManager:
    """
    A dedicated class to manage all plant-related data and operations.
    This is being refactored to use NumPy arrays for performance.
    """
    def __init__(self):
        self.plants = []
        initial_capacity = 1000
        self.capacity = initial_capacity
        self.count = 0

        self.arrays = {
            'ages': np.zeros(initial_capacity, dtype=np.float64),
            'heights': np.zeros(initial_capacity, dtype=np.float32),
            'radii': np.zeros(initial_capacity, dtype=np.float32),
            'root_radii': np.zeros(initial_capacity, dtype=np.float32),
            'core_radii': np.zeros(initial_capacity, dtype=np.float32),
            'energies': np.zeros(initial_capacity, dtype=np.float64),
            'reproductive_energies_stored': np.zeros(initial_capacity, dtype=np.float64),
            'positions': np.zeros((initial_capacity, 2), dtype=np.float32),
            'soil_type_ids': np.zeros(initial_capacity, dtype=np.int8), # Stores soil type as an integer ID
            'overlapped_root_areas': np.zeros(initial_capacity, dtype=np.float32), # From competition calculation
            'shaded_canopy_areas': np.zeros(initial_capacity, dtype=np.float32), # From competition calculation
            'aging_efficiencies': np.ones(initial_capacity, dtype=np.float32),
            'hydraulic_efficiencies': np.ones(initial_capacity, dtype=np.float32),
            'environmental_efficiencies': np.ones(initial_capacity, dtype=np.float32),
            'soil_efficiencies': np.ones(initial_capacity, dtype=np.float32),
            'metabolism_costs_per_second': np.zeros(initial_capacity, dtype=np.float32),
            'canopy_areas': np.zeros(initial_capacity, dtype=np.float32), # Caches the result of pi * r^2
        }

    def add_plant(self, plant):
        """Adds a new plant, linking it to the NumPy arrays via its index."""
        if self.count == self.capacity:
            self._grow_capacity()

        plant.index = self.count
        self.plants.append(plant)

        # Add the plant's attributes to the NumPy arrays at its new index.
        self.arrays['ages'][self.count] = plant.age
        self.arrays['heights'][self.count] = plant.height
        self.arrays['radii'][self.count] = plant.radius
        self.arrays['root_radii'][self.count] = plant.root_radius
        self.arrays['core_radii'][self.count] = plant.core_radius
        self.arrays['energies'][self.count] = plant.energy
        self.arrays['reproductive_energies_stored'][self.count] = plant.reproductive_energy_stored
        self.arrays['positions'][self.count] = (plant.x, plant.y)
        
        # Look up the soil type string from the plant and store its corresponding ID.
        soil_id = C.PLANT_SOIL_TYPE_TO_ID[plant.soil_type]
        self.arrays['soil_type_ids'][self.count] = soil_id

        # Explicitly set the initial energy in the array upon registration.
        # This makes the array's state correct from the very first moment.
        self.arrays['energies'][self.count] = plant.energy

        self.count += 1

    def _grow_capacity(self):
        """Doubles the capacity of all NumPy arrays within the self.arrays dictionary."""
        new_capacity = self.capacity * 2
        log.log(f"DEBUG: PlantManager growing from {self.capacity} to {new_capacity}")

        for key, arr in self.arrays.items():
            # Special handling for 2D arrays like 'positions'
            if arr.ndim == 2:
                new_shape = (new_capacity, arr.shape[1])
                self.arrays[key] = np.resize(arr, new_shape)
            else:
                self.arrays[key] = np.resize(arr, new_capacity)
        
        self.capacity = new_capacity

    def update_aging_efficiencies(self):
        """
        Calculates aging efficiency for ALL plants in a single vectorized operation.
        """
        live_ages = self.arrays['ages'][:self.count]
        self.arrays['aging_efficiencies'][:self.count] = np.exp(-(live_ages / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))

    def update_hydraulic_efficiencies(self):
        """
        Calculates hydraulic efficiency for ALL plants in a single vectorized operation.
        This is based on the plant's height.
        """
        live_heights = self.arrays['heights'][:self.count]
        self.arrays['hydraulic_efficiencies'][:self.count] = np.exp(-(live_heights / C.PLANT_MAX_HYDRAULIC_HEIGHT_CM))

    def update_environmental_efficiencies(self, environment):
        """
        Calculates environmental efficiency for ALL plants in a single vectorized operation.
        """
        if self.count == 0: return

        positions = self.arrays['positions'][:self.count]
        x_coords = positions[:, 0]
        y_coords = positions[:, 1]

        temperatures = environment.get_temperatures_vectorized(x_coords, y_coords)
        humidities = environment.get_humidities_vectorized(x_coords, y_coords)

        # This is a placeholder for gene data. For now, we assume all plants have the same genes.
        # This will need to be refactored later when genetics become variable.
        from genes import PlantGenes
        temp_genes = PlantGenes()

        temp_diff = np.abs(temperatures - temp_genes.optimal_temperature)
        temp_eff = np.exp(-((temp_diff / temp_genes.temperature_tolerance)**2))
        hum_diff = np.abs(humidities - temp_genes.optimal_humidity)
        hum_eff = np.exp(-((hum_diff / temp_genes.humidity_tolerance)**2))
        
        self.arrays['environmental_efficiencies'][:self.count] = temp_eff * hum_eff

    def update_soil_efficiencies(self):
        """
        Calculates soil nutrient uptake efficiency for ALL plants in a single vectorized operation.
        """
        if self.count == 0: return

        # Get slices of the arrays for all living plants
        live_indices = slice(0, self.count)
        soil_ids = self.arrays['soil_type_ids'][live_indices]
        radii = self.arrays['radii'][live_indices]
        root_radii = self.arrays['root_radii'][live_indices]

        # --- Step 1: Get the base efficiency from the soil type ---
        # This is a fast, vectorized lookup. It uses the array of soil_ids
        # to grab the corresponding efficiency value from the constants array.
        max_soil_effs = C.PLANT_SOIL_ID_TO_EFFICIENCY[soil_ids]

        # --- Step 2: Calculate the root-to-canopy ratio modifier ---
        # We add 1 to the radius to avoid division by zero for new seedlings.
        root_to_canopy_ratios = root_radii / (radii + 1)
        ratio_modifier = np.minimum(1.0, root_to_canopy_ratios * C.PLANT_ROOT_EFFICIENCY_FACTOR)

        # --- Step 3: Calculate the root competition modifier ---
        # We add a very small number (epsilon) to the denominator to prevent division by zero
        # for plants that might have zero root area.
        root_areas = np.pi * root_radii**2
        overlapped_areas = self.arrays['overlapped_root_areas'][live_indices]
        effective_root_areas = np.maximum(0, root_areas - overlapped_areas)
        root_competition_eff = effective_root_areas / (root_areas + 1e-9) # Add epsilon for safety

        # --- Step 4: Combine all factors ---
        final_soil_eff = max_soil_effs * ratio_modifier * root_competition_eff

        # Store the final results back into the main array
        self.arrays['soil_efficiencies'][live_indices] = final_soil_eff

    def update_metabolism_costs(self, environment):
        """
        Calculates the metabolic energy cost per second for ALL plants
        in a single vectorized operation.
        """
        if self.count == 0: return

        # Get slices of the arrays for all living plants
        positions = self.arrays['positions'][:self.count]
        radii = self.arrays['radii'][:self.count]
        root_radii = self.arrays['root_radii'][:self.count]
        core_radii = self.arrays['core_radii'][:self.count]

        # Get temperatures for all plants at once using the new vectorized method
        temperatures = environment.get_temperatures_vectorized(positions[:, 0], positions[:, 1])

        # Perform calculations for ALL plants at once
        canopy_areas = np.pi * radii**2
        self.arrays['canopy_areas'][:self.count] = canopy_areas # Cache the result
        root_areas = np.pi * root_radii**2
        core_areas = np.pi * core_radii**2
        total_areas = canopy_areas + root_areas + core_areas

        temp_differences = temperatures - C.PLANT_RESPIRATION_REFERENCE_TEMP
        respiration_factors = C.PLANT_Q10_FACTOR ** (temp_differences / C.PLANT_Q10_INTERVAL_DIVISOR)

        metabolism_per_second = total_areas * C.PLANT_BASE_MAINTENANCE_RESPIRATION_PER_AREA * respiration_factors

        # Store the final results back into the main array
        self.arrays['metabolism_costs_per_second'][:self.count] = metabolism_per_second

    def remove_plant(self, plant_to_remove):
        """
        Removes a plant efficiently using the 'swap and pop' method.
        
        !!! CRITICAL CHECKLIST FOR FUTURE MODIFICATIONS !!!
        If you add a new NumPy array to this class, you MUST add it
        to the swap block below to prevent data corruption.
        Current arrays to swap:
        - ages, heights, radii, root_radii, core_radii, energies,
        - reproductive_energies_stored, positions, aging_efficiencies,
        - hydraulic_efficiencies, metabolism_costs_per_second, canopy_areas
        """
        if plant_to_remove.index >= self.count or self.plants[plant_to_remove.index] is not plant_to_remove:
            log.log(f"ERROR: Attempted to remove a plant with an invalid index or mismatched object. Index: {plant_to_remove.index}")
            try:
                self.plants.remove(plant_to_remove)
            except ValueError:
                pass
            return

        idx_to_remove = plant_to_remove.index
        last_idx = self.count - 1

        if idx_to_remove == last_idx:
            log.log(f"DEBUG: Removing last plant at index {idx_to_remove}. No swap needed.")
        else:
            last_plant = self.plants[last_idx]

            # --- The SWAP (Now automated and secure) ---
            # 1. Loop through all managed arrays and copy the last element's data
            #    into the slot of the element being removed.
            for key, arr in self.arrays.items():
                arr[idx_to_remove] = arr[last_idx]

            # 2. Move the 'last_plant' object to the now-vacant slot in the Python list.
            self.plants[idx_to_remove] = last_plant

            # 3. CRITICAL: Update the index of the plant that we just moved.
            last_plant.index = idx_to_remove
            
            log.log(f"DEBUG: Removing plant at index {idx_to_remove}. Swapped with last plant from index {last_idx}. Moved plant ID: {last_plant.id}")

        # --- The POP ---
        self.plants.pop()
        self.count -= 1

    def __iter__(self):
        """Allows the manager to be iterated over like a list (e.g., 'for plant in manager')."""
        return iter(self.plants)

    def __len__(self):
        """Allows the len() function to be called on the manager."""
        return self.count