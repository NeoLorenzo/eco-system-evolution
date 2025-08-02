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
PROFILER_PRINT_LINE_COUNT = 30
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
    0: 1.0, 1: 60.0, 2: 3600.0, 3: 86400.0, 4: 31536000.0
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
TERRAIN_WATER_LEVEL = 0.41
TERRAIN_SAND_LEVEL = 0.42
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
UI_LOG_INTERVAL_SECONDS = 518400.0
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
# Calculation: Photosynthesis Rate * Respiration Fraction
# Units: (J/s/cm^2 * %) = J/s/cm^2
PLANT_METABOLISM_PER_AREA = PLANT_PHOTOSYNTHESIS_PER_AREA * PLANT_RESPIRATION_FRAC_OF_GPP

# --- Biomass Cost (Growth Cost) ---
# Calculation: Energy Density of Biomass * Mass per Area of Growth
# Units: (J/kg) * (kg/m^2) / (cm^2/m^2) = J/cm^2
PLANT_BIOMASS_ENERGY_COST = (BIOMASS_ENERGY_DENSITY_J_PER_KG * LEAF_MASS_PER_AREA_KG_PER_M2) / CM2_PER_M2

# =============================================================================
# --- CREATURES (GENERAL) ---
# =============================================================================
# NOTE: All energy values are now in Joules (J) and are scaled realistically.

# --- Initial State & Placement ---
# A starting buffer to survive the initial phase where the canopy is small.
# This value needs to be large enough to cover metabolic costs while the plant grows.
CREATURE_INITIAL_ENERGY = 5000.0
INITIAL_PLANT_POSITION = (50000, 50000)
INITIAL_ANIMAL_POSITION = (51000, 51000)

# --- Reproduction ---
# These values must be achievable after a period of net energy gain.
CREATURE_REPRODUCTION_ENERGY_THRESHOLD = 6000.0 # Joules
CREATURE_REPRODUCTION_ENERGY_COST = 3000.0      # Joules

CREATURE_ID_MIN = 1000
CREATURE_ID_MAX = 9999

# =============================================================================
# --- PLANTS ---
# =============================================================================
# The mandatory waiting period (in seconds) after reproduction before trying again.
PLANT_REPRODUCTION_COOLDOWN_SECONDS = 2592000.0 # (30 days)

# The interval (in sim seconds) for a plant to re-calculate its competition.
PLANT_COMPETITION_UPDATE_INTERVAL_SECONDS = 1.0

# The interval (in sim seconds) at which a plant runs its main logic loop.
# This is the fixed, discrete time-step for all biological calculations.
PLANT_LOGIC_UPDATE_INTERVAL_SECONDS = 3600.0 # (1 Hour)

# --- Initial Properties & Size ---
PLANT_INITIAL_RADIUS_CM = 20
PLANT_CORE_RADIUS_FACTOR = 0.25

# --- Reproduction & Spacing ---
PLANT_MAX_NEIGHBORS = 5
PLANT_CROWDED_RADIUS_CM = 30
PLANT_SEED_SPREAD_RADIUS_CM = 250
PLANT_REPRODUCTION_ATTEMPTS = 5
PLANT_COMPETITION_RADIUS_CM = 100

# --- Root System ---
PLANT_INITIAL_ROOT_RADIUS_CM = 10.0
PLANT_CORE_PERSONAL_SPACE_FACTOR = 1.5
PLANT_ROOT_EFFICIENCY_FACTOR = 2.0

# --- Genetic Traits & Environmental Interaction ---
PLANT_OPTIMAL_TEMPERATURE = 0.65
PLANT_TEMPERATURE_TOLERANCE = 0.2
PLANT_OPTIMAL_HUMIDITY = 0.6
PLANT_HUMIDITY_TOLERANCE = 0.3
PLANT_SOIL_EFFICIENCY = {"sand": 0.4, "grass": 1.0, "dirt": 0.7}

# time for senescence. It defines the age at which a plant's metabolic
# efficiency drops to ~37% (1/e) of its peak. It's a measure of how
# quickly the plant ages, not a hard limit on how long it can live.
PLANT_SENESCENCE_TIMESCALE_SECONDS = 315360000.0 # (Represents a characteristic time of 10 years)

PLANT_COMPETITION_MASS_FACTOR = 0.001

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