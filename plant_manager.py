# plant_manager.py
import numpy as np
import constants as C

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
        # We are starting by only vectorizing 'age' and its resulting efficiency.
        self.ages = np.zeros(initial_capacity, dtype=np.float64)
        self.heights = np.zeros(initial_capacity, dtype=np.float32)
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

    def remove_plant(self, plant):
        """Removes a plant object from the list."""
        # This part of the refactor is complex and will be handled in a later step.
        # For now, we just remove from the list to prevent crashes.
        if plant in self.plants:
            self.plants.remove(plant)
            # Note: This creates a mismatch between the list and the NumPy arrays.
            # This is acceptable for now, as we are focused on the update performance.

    def __iter__(self):
        """Allows the manager to be iterated over like a list (e.g., 'for plant in manager')."""
        return iter(self.plants)

    def __len__(self):
        """Allows the len() function to be called on the manager."""
        return len(self.plants)