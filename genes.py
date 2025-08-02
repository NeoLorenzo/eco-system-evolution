#genes.py

import constants as C

class PlantGenes:
    """A data container for all the genetic traits of a plant species."""
    def __init__(self):
        self.optimal_temperature = C.PLANT_OPTIMAL_TEMPERATURE  # Ideal temperature, unitless [0, 1]
        self.temperature_tolerance = C.PLANT_TEMPERATURE_TOLERANCE  # Range of tolerable temperatures, unitless
        self.optimal_humidity = C.PLANT_OPTIMAL_HUMIDITY  # Ideal humidity, unitless [0, 1]
        self.humidity_tolerance = C.PLANT_HUMIDITY_TOLERANCE  # Range of tolerable humidity, unitless
        self.soil_efficiency = C.PLANT_SOIL_EFFICIENCY  # Nutrient uptake multiplier by soil type, unitless
        self.core_radius_factor = C.PLANT_CORE_RADIUS_FACTOR  # Ratio of core radius to canopy radius, unitless