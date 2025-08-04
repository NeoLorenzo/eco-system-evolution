# plant_manager.py

class PlantManager:
    """
    A dedicated class to manage all plant-related data and operations.
    Initially, it will just hold a list of plant objects, but it will
    be refactored to use NumPy arrays for performance.
    """
    def __init__(self):
        # For now, we still use a simple list. This is the part we will change later.
        self.plants = []

    def add_plant(self, plant):
        """Adds a new plant object to the list."""
        self.plants.append(plant)

    def remove_plant(self, plant):
        """Removes a plant object from the list."""
        if plant in self.plants:
            self.plants.remove(plant)

    def __iter__(self):
        """Allows the manager to be iterated over like a list (e.g., 'for plant in manager')."""
        return iter(self.plants)

    def __len__(self):
        """Allows the len() function to be called on the manager."""
        return len(self.plants)