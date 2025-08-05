# plant_manager.py
import numpy as np
import constants as C
import logger as log

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
            'aging_efficiencies': np.ones(initial_capacity, dtype=np.float32),
            'hydraulic_efficiencies': np.ones(initial_capacity, dtype=np.float32),
            'metabolism_costs_per_second': np.zeros(initial_capacity, dtype=np.float32),
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
        - hydraulic_efficiencies, metabolism_costs_per_second
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