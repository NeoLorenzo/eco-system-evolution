# constants.py

# =============================================================================
# --- SIMULATION & PERFORMANCE SETTINGS ---
# =============================================================================
CLOCK_TICK_RATE = 60
SIMULATION_TICK_RATE = 60.0 # The fixed number of logic updates per second
SIMULATION_TICK_INTERVAL_SECONDS = 1.0 / SIMULATION_TICK_RATE
SPATIAL_UPDATE_INTERVAL_SECONDS = 1.0 # Rebuild the quadtree once per second
QUADTREE_CAPACITY = 4
MILLISECONDS_PER_SECOND = 1000.0
PROFILER_PRINT_LINE_COUNT = 20
UI_LOADING_BAR_UPDATE_INTERVAL = 10
SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60

# =============================================================================
# --- WORLD & ENVIRONMENT ---
# =============================================================================
WORLD_WIDTH_CM = 100000
WORLD_HEIGHT_CM = 100000
TIME_MULTIPLIERS = {
    0: 1.0, # 1 sec/sec
    1: 60.0, # 1 min/sec
    2: 3600.0, # 1 hour/sec
    3: 86400.0, # 1 day/sec
    4: 604800.0, # 1 week/sec
    5: 2592000.0 # 1 month (30 days)/sec
}
CHUNK_SIZE_CM = 4000
CHUNK_RESOLUTION = 100
NOISE_SCALE = 20000.0
NOISE_OCTAVES = 4
NOISE_PERSISTENCE = 0.5
NOISE_LACUNARITY = 2.0
TERRAIN_AMPLITUDE = 1.5
TEMP_NOISE_SEED = 12345
TERRAIN_NOISE_SEED = 24322
HUMIDITY_NOISE_SEED = 98765
TERRAIN_WATER_LEVEL = 0.31
TERRAIN_SAND_LEVEL = 0.32
TERRAIN_GRASS_LEVEL = 0.57
TERRAIN_DIRT_LEVEL = 0.59
ENVIRONMENT_VIEW_MODE_COUNT = 3

CHUNK_RENDER_OVERLAP_PIXELS = 2

WORLD_BORDER_WIDTH_PIXELS = 1

# =============================================================================
# --- UI, CAMERA & COLORS ---
# =============================================================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
CAMERA_PANSPEED_PIXELS = 15
CAMERA_ZOOM_SPEED = 0.1
CAMERA_MAX_ZOOM = 1.0
CAMERA_MIN_ZOOM = 0.008
UI_LOG_INTERVAL_SECONDS = 2592000.0
COLOR_WHITE = (255, 255, 255); COLOR_GREEN = (0, 255, 0); COLOR_BLUE = (0, 0, 255)
COLOR_BLACK = (0, 0, 0); COLOR_VOID = (10, 0, 20)
COLOR_LOADING_BAR_BG = (50, 50, 50); COLOR_LOADING_BAR_FG = (100, 200, 100)
COLOR_COLDEST = (0, 0, 100); COLOR_COLD = (0, 0, 255); COLOR_TEMPERATE = (255, 255, 0)
COLOR_HOT = (255, 0, 0); COLOR_HOTTEST = (150, 0, 0)
COLOR_DEEP_WATER = (0, 0, 50); COLOR_SHALLOW_WATER = (26, 102, 255)
COLOR_SAND = (240, 230, 140); COLOR_GRASS = (34, 139, 34); COLOR_DIRT = (139, 69, 19)
COLOR_MOUNTAIN = (112, 128, 144)
COLOR_DRY = (210, 180, 140); COLOR_WET = (70, 130, 180)
COLOR_PLANT_CANOPY_HEALTHY = (74, 255, 0, 120)
COLOR_PLANT_CANOPY_SICKLY = (189, 183, 107, 120)
COLOR_PLANT_CORE = (101, 67, 33)
COLOR_PLANT_FLOWER = (255, 105, 180, 200) # Bright Pink
COLOR_PLANT_FRUIT = (220, 20, 60, 255) # Crimson Red
COLOR_PLANT_SEED = (85, 55, 25) # Dark Brown

TEMP_COLOR_THRESHOLD_COLD = 0.25
TEMP_COLOR_THRESHOLD_TEMPERATE = 0.5
TEMP_COLOR_THRESHOLD_HOT = 0.75

UI_FONT_SIZE = 36
UI_TIME_DISPLAY_POS_X = 10
UI_TIME_DISPLAY_POS_Y = 10
UI_LOADING_TEXT_OFFSET_Y = 50
UI_LOADING_BAR_WIDTH = 400
UI_LOADING_BAR_HEIGHT = 30

# =============================================================================
# --- PHYSICS & BIOLOGY CONSTANTS (REAL-WORLD VALUES) ---
# =============================================================================
# This section defines foundational, real-world physical and biological values.
# The simulation's energy constants are derived from these. All energy is in Joules (J).

# --- Solar Energy ---
# Solar irradiance on a clear day at sea level is ~1000 Watts/m^2.
# A Watt is a Joule per second (J/s).
SOLAR_IRRADIANCE_W_PER_M2 = 1000.0

# --- Plant Biology ---
# The efficiency of converting solar energy into chemical energy (biomass).
# Typically 3-6% of total solar radiation for a healthy plant. We use a conservative 3%.
PHOTOSYNTHETIC_EFFICIENCY = 0.03

# The percentage of gross energy production (GPP) that a plant uses for its own
# metabolic maintenance (respiration). This is typically 45-55%.
PLANT_RESPIRATION_FRAC_OF_GPP = 0.50

# The energy density of dry plant biomass (wood, leaves).
# A widely accepted average is ~18 Megajoules/kg or 18,000,000 J/kg.
BIOMASS_ENERGY_DENSITY_J_PER_KG = 18000000.0

# Leaf Mass per Area (LMA): The dry mass of leaf tissue per unit of surface area.
# This bridges the gap between growth (area) and biomass cost (mass).
# A common value for temperate woody plants is ~100 g/m^2, or 0.1 kg/m^2.
LEAF_MASS_PER_AREA_KG_PER_M2 = 0.1

# --- Unit Conversions ---
CM2_PER_M2 = 10000.0 # Conversion factor from square meters to square centimeters.
KG_PER_G = 0.001 # Conversion factor from grams to kilograms.

# =============================================================================
# --- DERIVED ENERGY CONSTANTS (USED BY THE SIMULATION) ---
# =============================================================================
# These values are calculated from the real-world constants above.
# Do not change these directly; instead, tweak the values in the section above.

# --- Photosynthesis Rate (Energy Gain) ---
# Calculation: (Solar Irradiance * Efficiency) / Area Conversion
# Units: (J/s/m^2 * %) / (cm^2/m^2) = J/s/cm^2
PLANT_PHOTOSYNTHESIS_PER_AREA = (SOLAR_IRRADIANCE_W_PER_M2 * PHOTOSYNTHETIC_EFFICIENCY) / CM2_PER_M2

# --- Metabolism Rate (Maintenance Cost) ---
# DEPRECATED: This is no longer used as metabolism is now decoupled from photosynthesis.
# PLANT_METABOLISM_PER_AREA = PLANT_PHOTOSYNTHESIS_PER_AREA * PLANT_RESPIRATION_FRAC_OF_GPP

# The base rate of energy consumption for maintenance respiration at the reference temperature.
# This is based on the total 2D area of the plant's canopy and roots.
# Units: J/s/cm^2 (Joules per second per square centimeter of total biomass area)
PLANT_BASE_MAINTENANCE_RESPIRATION_PER_AREA = 0.00075

# The Q10 temperature coefficient for respiration. A value of 2.0 means the rate
# doubles for every 10°C increase in temperature.
# Unit: Unitless
PLANT_Q10_FACTOR = 2.0

# The reference temperature at which the base respiration rate is measured.
# This is on the simulation's normalized scale. 0.5 represents a temperate midpoint.
# Unit: Unitless [0, 1]
PLANT_RESPIRATION_REFERENCE_TEMP = 0.5

# The interval on our normalized temperature scale that corresponds to a 10°C change.
# If our full temp range (0.0 to 1.0) represents a 50°C span, then 10°C is 0.2.
# Unit: Unitless [0, 1]
PLANT_Q10_INTERVAL_DIVISOR = 0.2

# --- Biomass Cost (Growth Cost) ---
# Calculation: Energy Density of Biomass * Mass per Area of Growth
# This now represents the cost to grow a 2D area of "cheap" tissue like roots and leaves.
# Units: (J/kg) * (kg/m^2) / (cm^2/m^2) = J/cm^2
PLANT_BIOMASS_ENERGY_COST = (BIOMASS_ENERGY_DENSITY_J_PER_KG * LEAF_MASS_PER_AREA_KG_PER_M2) / CM2_PER_M2

# A multiplier to define how much more expensive structural core tissue is compared to standard biomass.
# Unit: Unitless
PLANT_CORE_COST_MULTIPLIER = 8.0

# The energy cost to create 1 cm^2 of dense, structural core tissue, derived from the base cost.
# Unit: J/cm^2
PLANT_CORE_BIOMASS_ENERGY_COST = PLANT_BIOMASS_ENERGY_COST * PLANT_CORE_COST_MULTIPLIER

# =============================================================================
# --- CREATURES (GENERAL) ---
# =============================================================================
# NOTE: All energy values are now in Joules (J) and are scaled realistically.

# --- Initial State & Placement ---
# A starting buffer to survive the initial phase where the canopy is small.
# This represents the energy stored in the seed (endosperm) and must be
# large enough to cover the metabolic deficit of a seedling for several days.
CREATURE_INITIAL_ENERGY = 48000.0
INITIAL_PLANT_POSITION = (50000, 50000)
INITIAL_ANIMAL_POSITION = (51000, 51000)

# --- Reproduction ---
# DEPRECATED for Plants, still used by Animals. Plants now use a more complex system.
CREATURE_REPRODUCTION_ENERGY_COST = CREATURE_INITIAL_ENERGY # Joules

CREATURE_ID_MIN = 1000
CREATURE_ID_MAX = 9999

# =============================================================================
# --- PLANTS ---
# =============================================================================
# --- NEW: Life Cycle & Germination ---
# The passive energy drain on a dormant seed per hour.
# Unit: Joules per Hour (J/h)
PLANT_DORMANCY_METABOLISM_J_PER_HOUR = 10.0

# The one-time energy cost for a seed to sprout into a seedling.
# Unit: Joules (J)
PLANT_SPROUTING_ENERGY_COST = 2000.0

# The minimum normalized humidity [0,1] required for a seed to germinate.
# Unit: Unitless [0, 1]
GERMINATION_HUMIDITY_THRESHOLD = 0.5

# The minimum normalized temperature [0,1] required for a seed to germinate.
# Unit: Unitless [0, 1]
GERMINATION_MIN_TEMP = 0.4

# The maximum normalized temperature [0,1] required for a seed to germinate.
# Unit: Unitless [0, 1]
GERMINATION_MAX_TEMP = 0.85


# --- Reproduction & Maturity ---
# The rate at which a mature plant will attempt to store energy for reproduction,
# drawing from its main reserves if necessary.
# Unit: Joules per Hour (J/h)
PLANT_REPRODUCTIVE_INVESTMENT_J_PER_HOUR = 250.0

# The amount of stored reproductive energy required before a plant is mature enough to fruit.
# Unit: Joules (J)
PLANT_REPRODUCTION_MINIMUM_STORED_ENERGY = 20000.0

# The energy cost to create and sustain a single flower. This replaces the old fruit structural cost.
# Unit: Joules (J)
PLANT_FLOWER_ENERGY_COST = 7500.0

# The lifespan of a flower before it matures into a fruit.
# Unit: Seconds (s)
PLANT_FLOWER_LIFESPAN_SECONDS = 604800.0 # (7 Days)

# The lifespan of a fruit before it drops from the parent plant.
# Unit: Seconds (s)
PLANT_FRUIT_LIFESPAN_SECONDS = 604800.0 # (7 Days)

# The maximum density of flowers on a canopy, to prevent visual clutter and unrealistic production.
# Unit: Flowers per square centimeter (flowers/cm^2)
PLANT_MAX_FLOWERS_PER_CANOPY_AREA = 0.0001

# The energy packed into the seed itself, which becomes the newborn's starting energy.
# Unit: Joules (J)
PLANT_SEED_PROVISIONING_ENERGY = 15000.0

# The energy a plant will spend per hour on growth if it's in the "seedling" phase
# (i.e., running a deficit but has large energy reserves).
PLANT_GROWTH_INVESTMENT_J_PER_HOUR = 900.0

# The energy threshold below which a plant will stop investing in growth to conserve energy.
# It will not spend its last reserves on growing.
PLANT_GROWTH_INVESTMENT_ENERGY_RESERVE = 10000.0

# The interval (in sim seconds) for a plant to re-calculate its competition.
# This is a heavy calculation, so it should not be run frequently. Once a day is a reasonable starting point.
PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS = 86400.0 # (1 Day)

# The radius used in quadtree queries to find potential competitors for light and nutrients.
# This needs to be large enough to find plants with large canopies whose centers are far away.
# Unit: Centimeters (cm)
PLANT_COMPETITION_SEARCH_RADIUS_CM = 5000.0

# The interval (in sim seconds) at which a plant runs its main logic loop.
# This is the fixed, discrete time-step for all biological calculations.
PLANT_LOGIC_UPDATE_INTERVAL_SECONDS = 3600.0 # (1 Hour)

# The efficiency of the self-pruning process. 1.0 means the plant sheds
# exactly enough biomass to cover its energy deficit for that tick.
# Unit: Unitless
PLANT_PRUNING_EFFICIENCY = 1.0

# --- Initial Properties & Size ---
# The initial radius of a seedling's canopy and roots right after sprouting.
# Unit: Centimeters (cm)
PLANT_SPROUT_RADIUS_CM = 1.0

# --- NEW: Growth Allocation ---
# The ideal ratio of core cross-sectional area to canopy area that the plant
# tries to maintain for structural stability. This is a behavioral target, not a fixed rule.
# Unit: Unitless ratio (area/area)
PLANT_IDEAL_CORE_TO_CANOPY_AREA_RATIO = 0.1

# The initial radius of a seedling's structural core right after sprouting.
# Unit: Centimeters (cm)
PLANT_SPROUT_CORE_RADIUS_CM = 0.2

# This now represents the BASE or "genetically ideal" shape of the plant in open sunlight.
# A low value means a wide, sprawling plant (like an oak).
# Unit: Unitless ratio
PLANT_RADIUS_TO_HEIGHT_FACTOR = 2.0

# The target shape a plant will strive for when completely shaded.
# A high value means a tall, skinny plant (like a pine in a dense forest).
# Unit: Unitless ratio
PLANT_MAX_SHADE_RADIUS_TO_HEIGHT_FACTOR = 2.5

# The rate at which a plant adjusts its morphology in response to changing light conditions.
# A higher value means it adapts its shape faster.
# Unit: Unitless
PLANT_MORPHOLOGY_ADAPTATION_RATE = 0.01

# The characteristic height at which hydraulic stress begins to significantly
# limit photosynthetic efficiency. At this height, efficiency drops to ~37% (1/e).
# Unit: Centimeters (cm)
PLANT_MAX_HYDRAULIC_HEIGHT_CM = 1000.0 # Represents a very tall tree (50 meters)

# --- Reproduction & Spacing ---
PLANT_MAX_NEIGHBORS = 5
PLANT_CROWDED_RADIUS_CM = 30
# DEPRECATED: PLANT_SEED_SPREAD_RADIUS_CM = 250
# DEPRECATED: PLANT_REPRODUCTION_ATTEMPTS = 5

# A base distance that a fruit will always roll, even on flat ground.
# Unit: Centimeters (cm)
PLANT_SEED_ROLL_BASE_DISTANCE_CM = 20.0

# A multiplier that determines how much farther a fruit rolls based on the steepness of the terrain.
# A higher value means slope has a greater effect on dispersal distance.
# Unit: Unitless
PLANT_SEED_ROLL_DISTANCE_FACTOR = 5000.0

# --- Root System ---
PLANT_INITIAL_ROOT_RADIUS_CM = 10.0
PLANT_CORE_PERSONAL_SPACE_FACTOR = 1.5
PLANT_ROOT_EFFICIENCY_FACTOR = 2.0

# The radius a plant must reach to no longer be vulnerable to being crushed by a neighbor's core.
# Unit: Centimeters (cm)
PLANT_CRUSH_RESISTANCE_RADIUS_CM = 25.0

# --- Genetic Traits & Environmental Interaction ---
PLANT_OPTIMAL_TEMPERATURE = 0.65
PLANT_TEMPERATURE_TOLERANCE = 0.2
PLANT_OPTIMAL_HUMIDITY = 0.6
PLANT_HUMIDITY_TOLERANCE = 0.3
PLANT_SOIL_EFFICIENCY = {"sand": 0.4, "grass": 1.0, "dirt": 0.7}

# time for senescence. It defines the age at which a plant's metabolic
# efficiency drops to ~37% (1/e) of its peak. It's a measure of how
# quickly the plant ages, not a hard limit on how long it can live.
PLANT_SENESCENCE_TIMESCALE_SECONDS = 252288000.0 # (Represents a characteristic time of 10 years)

PLANT_COMPETITION_MASS_FACTOR = 0.001

# A safe, large radius used for broad-phase checks to ensure we don't miss
# interactions with very large plants whose centers are far away.
# Unit: Centimeters (cm)
PLANT_MAX_INTERACTION_RADIUS_CM = 500000.0

# =============================================================================
# --- ANIMALS ---
# =============================================================================
# The internal processing interval for animal logic.
ANIMAL_UPDATE_TICK_SECONDS = 60.0 # Process animal logic in 1-minute increments
ANIMAL_INITIAL_WIDTH_CM = 30
ANIMAL_INITIAL_HEIGHT_CM = 30
ANIMAL_SIGHT_RADIUS_CM = 200
ANIMAL_SPEED_CM_PER_SEC = 0.0 #TEMPORARY UNTIL ANIMALS GET IMPLIMENTED PROPERLY
# Energy from eating a plant should be substantial, reflecting the stored biomass.
# A plant of radius 30cm has an area of ~2827 cm^2.
# Net energy stored = (Photosynthesis - Metabolism) * Area.
# A rough estimate gives this a high but plausible value.
ANIMAL_ENERGY_PER_PLANT = 7500.0

ANIMAL_METABOLISM_PER_SECOND = 1.0