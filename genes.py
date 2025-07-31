#genes.py

import constants as C

class PlantGenes:
    """A data container for all the genetic traits of a plant species."""
    def __init__(self):
        self.optimal_temperature = C.PLANT_OPTIMAL_TEMPERATURE
        self.temperature_tolerance = C.PLANT_TEMPERATURE_TOLERANCE
        self.optimal_humidity = C.PLANT_OPTIMAL_HUMIDITY
        self.humidity_tolerance = C.PLANT_HUMIDITY_TOLERANCE
        self.soil_efficiency = C.PLANT_SOIL_EFFICIENCY
        self.core_radius_factor = C.PLANT_CORE_RADIUS_FACTOR