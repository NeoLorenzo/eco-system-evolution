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
        # --- Still using a list for the main objects during refactoring ---
        self.plants = []

        # --- NEW: NumPy arrays for vectorized calculations ---
        # We start with a pre-allocated capacity to avoid resizing arrays every time.
        initial_capacity = 1000
        self.capacity = initial_capacity
        self.count = 0 # The actual number of living plants.

        # --- Attributes stored in NumPy arrays ---
        self.ages = np.zeros(initial_capacity, dtype=np.float64)
        self.heights = np.zeros(initial_capacity, dtype=np.float32)
        self.radii = np.zeros(initial_capacity, dtype=np.float32)
        self.root_radii = np.zeros(initial_capacity, dtype=np.float32)
        self.core_radii = np.zeros(initial_capacity, dtype=np.float32)
        self.energies = np.zeros(initial_capacity, dtype=np.float64)
        self.reproductive_energies_stored = np.zeros(initial_capacity, dtype=np.float64)
        self.positions = np.zeros((initial_capacity, 2), dtype=np.float32) # x, y

        self.aging_efficiencies = np.ones(initial_capacity, dtype=np.float32)
        self.hydraulic_efficiencies = np.ones(initial_capacity, dtype=np.float32)

    def add_plant(self, plant):
        """Adds a new plant, linking it to the NumPy arrays via its index."""
        # If we're out of space, we need to grow our arrays.
        if self.count == self.capacity:
            self._grow_capacity()

        # The plant's index is its position in the NumPy arrays.
        plant.index = self.count

        # Add the object to the list (for now)
        self.plants.append(plant)

        # Add the plant's attributes to the NumPy arrays at its new index.
        self.ages[self.count] = plant.age
        self.heights[self.count] = plant.height
        self.radii[self.count] = plant.radius
        self.root_radii[self.count] = plant.root_radius
        self.core_radii[self.count] = plant.core_radius
        self.energies[self.count] = plant.energy
        self.reproductive_energies_stored[self.count] = plant.reproductive_energy_stored
        self.positions[self.count] = (plant.x, plant.y)

        # Increment the count of living plants.
        self.count += 1

    def _grow_capacity(self):
        """Doubles the capacity of all NumPy arrays."""
        new_capacity = self.capacity * 2
        
        # A log message is useful for knowing when this happens.
        print(f"DEBUG: PlantManager growing from {self.capacity} to {new_capacity}")

        # Create new, larger arrays and copy the old data over.
        self.ages = np.resize(self.ages, new_capacity)
        self.heights = np.resize(self.heights, new_capacity)
        self.radii = np.resize(self.radii, new_capacity)
        self.root_radii = np.resize(self.root_radii, new_capacity)
        self.core_radii = np.resize(self.core_radii, new_capacity)
        self.energies = np.resize(self.energies, new_capacity)
        self.reproductive_energies_stored = np.resize(self.reproductive_energies_stored, new_capacity)
        self.positions = np.resize(self.positions, (new_capacity, 2))
        self.aging_efficiencies = np.resize(self.aging_efficiencies, new_capacity)
        self.hydraulic_efficiencies = np.resize(self.hydraulic_efficiencies, new_capacity)
        
        self.capacity = new_capacity

    def update_aging_efficiencies(self):
        """
        Calculates aging efficiency for ALL plants in a single vectorized operation.
        """
        # We only need to compute for the plants that are actually alive.
        live_ages = self.ages[:self.count]
        
        # This one line replaces millions of individual math.exp calls.
        self.aging_efficiencies[:self.count] = np.exp(-(live_ages / C.PLANT_SENESCENCE_TIMESCALE_SECONDS))

    def update_hydraulic_efficiencies(self):
        """
        Calculates hydraulic efficiency for ALL plants in a single vectorized operation.
        This is based on the plant's height.
        """
        # We only need to compute for the plants that are actually alive.
        live_heights = self.heights[:self.count]

        # This replaces a loop of individual math.exp calls with one NumPy operation.
        self.hydraulic_efficiencies[:self.count] = np.exp(-(live_heights / C.PLANT_MAX_HYDRAULIC_HEIGHT_CM))

    def remove_plant(self, plant_to_remove):
        """
        Removes a plant efficiently using the 'swap and pop' method.
        This ensures data integrity between the object list and NumPy arrays.
        """
        # Ensure the plant is actually in our list and its index is valid. This is a safeguard.
        if plant_to_remove.index >= self.count or self.plants[plant_to_remove.index] is not plant_to_remove:
            log.log(f"ERROR: Attempted to remove a plant with an invalid index or that doesn't match the object list. Index: {plant_to_remove.index}")
            # As a fallback, try a slow search and remove if found. This prevents a crash but indicates a problem.
            try:
                self.plants.remove(plant_to_remove)
            except ValueError:
                pass # It wasn't in the list anyway.
            return

        idx_to_remove = plant_to_remove.index
        last_idx = self.count - 1

        # If the plant to remove is the last one, we don't need to swap.
        if idx_to_remove == last_idx:
            log.log(f"DEBUG: Removing last plant at index {idx_to_remove}. No swap needed.")
        else:
            # Get the plant object that is currently at the end of the list.
            last_plant = self.plants[last_idx]

            # --- The SWAP ---
            # 1. Copy the data from the last element into the slot of the element being removed.
            self.ages[idx_to_remove] = self.ages[last_idx]
            self.heights[idx_to_remove] = self.heights[last_idx]
            self.radii[idx_to_remove] = self.radii[last_idx]
            self.root_radii[idx_to_remove] = self.root_radii[last_idx]
            self.core_radii[idx_to_remove] = self.core_radii[last_idx]
            self.energies[idx_to_remove] = self.energies[last_idx]
            self.reproductive_energies_stored[idx_to_remove] = self.reproductive_energies_stored[last_idx]
            self.positions[idx_to_remove] = self.positions[last_idx] # <-- THIS LINE WAS MISSING
            self.aging_efficiencies[idx_to_remove] = self.aging_efficiencies[last_idx]
            self.hydraulic_efficiencies[idx_to_remove] = self.hydraulic_efficiencies[last_idx]

            # 2. Move the 'last_plant' object to the now-vacant slot in the Python list.
            self.plants[idx_to_remove] = last_plant

            # 3. CRITICAL: Update the index of the plant that we just moved.
            last_plant.index = idx_to_remove
            
            log.log(f"DEBUG: Removing plant at index {idx_to_remove}. Swapped with last plant from index {last_idx}. Moved plant ID: {last_plant.id}")

        # --- The POP ---
        # The last element in the list is now a duplicate, so we remove it.
        self.plants.pop()
        
        # Decrement the total count of plants. The data at 'last_idx' in the NumPy arrays
        # is now considered garbage and will be overwritten by the next new plant.
        self.count -= 1

    def __iter__(self):
        """Allows the manager to be iterated over like a list (e.g., 'for plant in manager')."""
        return iter(self.plants)

    def __len__(self):
        """Allows the len() function to be called on the manager."""
        return self.count