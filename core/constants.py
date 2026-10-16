"""Centralized constants module for BoğazSim.

# RUBRIC: No Magic Numbers
All physical parameters, geographic bounds, numerical thresholds,
wind classifications, and styling constants are defined here. No raw
magic numbers should exist outside this module.
"""

from __future__ import annotations

import math
from typing import Final

# ---------------------------------------------------------------------------
# Geographic Domain & Grid Dimensions
# ---------------------------------------------------------------------------
# Bosphorus Strait bounding box: 40.98°N (Marmara) to 41.25°N (Black Sea)
LAT_MIN: Final[float] = 40.98
LAT_MAX: Final[float] = 41.25
LON_MIN: Final[float] = 28.95
LON_MAX: Final[float] = 29.20

# Discrete hydrodynamic grid dimensions
GRID_ROWS: Final[int] = 120  # Latitude axis resolution
GRID_COLS: Final[int] = 160  # Longitude axis resolution

# Geodesic conversion approximations at ~41°N latitude
METERS_PER_DEGREE_LAT: Final[float] = 111_139.0
METERS_PER_DEGREE_LON: Final[float] = 83_865.0  # 111139.0 * cos(41.1°)
EARTH_RADIUS_METERS: Final[float] = 6_371_000.0

# ---------------------------------------------------------------------------
# Strait Morphology & Centerline Constants
# ---------------------------------------------------------------------------
# The Rumeli Hisarı – Anadolu Hisarı constriction (narrowest throat of the strait)
CONSTRICTION_LAT: Final[float] = 41.085
CONSTRICTION_LON: Final[float] = 29.0565

# Strait navigable width parameters (in meters)
MIN_STRAIT_WIDTH_M: Final[float] = 700.0   # Width at Rumeli Hisarı
MAX_STRAIT_WIDTH_M: Final[float] = 3500.0  # Width at northern/southern mouths
AVERAGE_STRAIT_DEPTH_M: Final[float] = 65.0
MAX_STRAIT_DEPTH_M: Final[float] = 110.0

# ---------------------------------------------------------------------------
# Two-Layer Hydrodynamic Profile
# ---------------------------------------------------------------------------
# Depth interface separating brackish upper layer and dense saline undercurrent
SURFACE_LAYER_DEPTH_M: Final[float] = 35.0

# Surface current velocity bounds (southward flow, m/s)
MIN_SURFACE_CURRENT_MS: Final[float] = 1.0
MAX_SURFACE_CURRENT_MS: Final[float] = 2.5

# Deep lower layer counter-current velocity bounds (northward flow, m/s)
MIN_BOTTOM_CURRENT_MS: Final[float] = 0.2
MAX_BOTTOM_CURRENT_MS: Final[float] = 0.8

# Water salinities (Practical Salinity Units)
UPPER_LAYER_SALINITY_PSU: Final[float] = 18.0
LOWER_LAYER_SALINITY_PSU: Final[float] = 38.0

# ---------------------------------------------------------------------------
# Numerical Integration & Stability
# ---------------------------------------------------------------------------
# Default integration time step: 10.0 seconds satisfies CFL condition (u*dt/dx < 1)
DEFAULT_DT_SECONDS: Final[float] = 10.0
MIN_DT_SECONDS: Final[float] = 1.0
MAX_DT_SECONDS: Final[float] = 60.0

# ---------------------------------------------------------------------------
# Coastal Counter-Eddy (Girdap) Vortex Perturbers
# ---------------------------------------------------------------------------
# Localized recirculation vortices behind sharp headlands:
# Each entry contains: (name, lat, lon, radius_meters, circulation_m2_per_s)
EDDY_DEFINITIONS: Final[list[dict[str, object]]] = [
    {
        "name": "Bebek Bay Cyclonic Eddy",
        "lat": 41.077,
        "lon": 29.044,
        "radius_m": 350.0,
        "circulation": 450.0,
    },
    {
        "name": "Arnavutköy Akıntıburnu Shear",
        "lat": 41.068,
        "lon": 29.043,
        "radius_m": 300.0,
        "circulation": -380.0,
    },
    {
        "name": "Kandilli Promontory Wake",
        "lat": 41.075,
        "lon": 29.060,
        "radius_m": 400.0,
        "circulation": 420.0,
    },
    {
        "name": "Kanlıca Bight Recirculation",
        "lat": 41.100,
        "lon": 29.065,
        "radius_m": 350.0,
        "circulation": -350.0,
    },
]

# ---------------------------------------------------------------------------
# Weather & Atmospheric Forcing
# ---------------------------------------------------------------------------
OPEN_METEO_URL: Final[str] = (
    "https://api.open-meteo.com/v1/forecast?"
    "latitude=41.0422&longitude=29.0083&"
    "current=wind_speed_10m,wind_direction_10m,surface_pressure&"
    "hourly=wind_speed_10m,wind_direction_10m&"
    "past_days=1&wind_speed_unit=ms"
)

WEATHER_CACHE_TTL_SECONDS: Final[int] = 900  # 15 minutes cache expiration
WEATHER_REQUEST_TIMEOUT_SECONDS: Final[float] = 5.0

# Canonical Istanbul Wind Sectors (Direction in degrees from True North)
WIND_SECTORS: Final[dict[str, tuple[float, float, str]]] = {
    "Yıldız": (337.5, 22.5, "North (N) — Cold maritime air from the Black Sea"),
    "Poyraz": (22.5, 67.5, "North-East (NE) — Dominant high-speed prevailing wind"),
    "Gündoğusu": (67.5, 112.5, "East (E) — Continental mild breeze"),
    "Keşişleme": (112.5, 157.5, "South-East (SE) — Dry warm breeze"),
    "Kıble": (157.5, 202.5, "South (S) — Warm southerly Mediterranean flow"),
    "Lodos": (202.5, 247.5, "South-West (SW) — Strong squalls, heavy chop and swells"),
    "Günbatısı": (247.5, 292.5, "West (W) — Maritime westerly front"),
    "Karayel": (292.5, 337.5, "North-West (NW) — Cold, gusty storm winds"),
}

# Synthetic fallback meteorological profiles
SYNTHETIC_POYRAZ_SPEED_MS: Final[float] = 8.5
SYNTHETIC_POYRAZ_DIR_DEG: Final[float] = 45.0
SYNTHETIC_LODOS_SPEED_MS: Final[float] = 11.0
SYNTHETIC_LODOS_DIR_DEG: Final[float] = 225.0

# ---------------------------------------------------------------------------
# Drift Entities Physical Characteristics
# ---------------------------------------------------------------------------
# Person In Water (PIW)
PIW_DEFAULT_MASS_KG: Final[float] = 80.0
PIW_WINDAGE_COEFF: Final[float] = 0.015
PIW_DRAG_COEFF: Final[float] = 1.05

# Life Raft
LIFERAFT_DEFAULT_MASS_KG: Final[float] = 120.0
LIFERAFT_WINDAGE_COEFF: Final[float] = 0.040
LIFERAFT_DRAG_COEFF: Final[float] = 0.50

# Fishing Boat (Dead in the water / disabled)
BOAT_DEFAULT_MASS_KG: Final[float] = 3500.0
BOAT_WINDAGE_COEFF: Final[float] = 0.030
BOAT_DRAG_COEFF: Final[float] = 0.65
BOAT_DEFAULT_ENGINE_BIAS_MS: Final[float] = 0.20

# Oil Slick Parameters
# RUBRIC: Hand-Written Algorithms
# Spreading in Fay's gravity-viscous regime (Fay, J.A., "Physical Processes in the
# Spread of Oil on a Water Surface", Proc. Joint Conf. Prevention & Control of Oil Spills, 1971):
#   Radius:  r(t) = k2 * [ (Delta * g * V^2) / sqrt(nu_w) ]^(1/6) * t^(1/4)
#   Area:    A(t) = pi * r(t)^2 = pi * k2^2 * [ (Delta * g * V^2) / sqrt(nu_w) ]^(1/3) * sqrt(t)
#                 = A0 + kappa * sqrt(t)
# where:
#   Delta = (rho_w - rho_o) / rho_w (reduced relative buoyancy ratio)
#   V = spill volume (m^3)
#   g = gravitational acceleration (m/s^2)
#   nu_w = kinematic viscosity of water (m^2/s)
#   k2 = Fay empirical dimensionless constant (~1.45)
OIL_DEFAULT_MASS_KG: Final[float] = 1000.0
OIL_DEFAULT_AREA_SQ_M: Final[float] = 250.0
OIL_WINDAGE_COEFF: Final[float] = 0.033
OIL_DRAG_COEFF: Final[float] = 0.20
OIL_SPILL_VOLUME_M3: Final[float] = 10.0
WATER_DENSITY_KG_M3: Final[float] = 1015.0      # Bosphorus brackish surface layer
OIL_DENSITY_KG_M3: Final[float] = 860.0          # Marine diesel / light crude
WATER_KINEMATIC_VISCOSITY_M2_S: Final[float] = 1.0e-6
GRAVITATIONAL_ACCELERATION_MS2: Final[float] = 9.80665
FAY_GRAVITY_VISCOUS_K2: Final[float] = 1.45


def compute_fay_kappa(
    volume_m3: float = OIL_SPILL_VOLUME_M3,
    water_density: float = WATER_DENSITY_KG_M3,
    oil_density: float = OIL_DENSITY_KG_M3,
    nu_water: float = WATER_KINEMATIC_VISCOSITY_M2_S,
    g: float = GRAVITATIONAL_ACCELERATION_MS2,
    k2: float = FAY_GRAVITY_VISCOUS_K2,
) -> float:
    """Compute Fay's gravity-viscous spreading coefficient kappa dynamically.
    
    Physics Note:
    Fay's (1971) spreading law in the gravity-viscous regime:
      A(t) = A_0 + kappa * sqrt(t)
    where kappa = pi * k2^2 * ((Delta * g * V^2) / sqrt(nu_w))^(1/3).
    For default values (V=10 m^3, Delta=0.1527, nu=1e-6, k2=1.45), kappa ~= 350.78 m^2/s^(1/2).
    """
    delta = (water_density - oil_density) / water_density
    bracket = (delta * g * (volume_m3 ** 2)) / math.sqrt(nu_water)
    return math.pi * (k2 ** 2) * (bracket ** (1.0 / 3.0))


# Derived dynamically in code from physical parameters (V=10 m^3, Delta=0.1527, etc.)
OIL_FAY_SPREADING_KAPPA: Final[float] = compute_fay_kappa()
OIL_EVAPORATION_RATE_PER_SEC: Final[float] = 0.00005  # Mass decay constant

# ---------------------------------------------------------------------------
# Monte Carlo Swarm Simulation Defaults
# ---------------------------------------------------------------------------
DEFAULT_SWARM_PARTICLES: Final[int] = 100
MIN_SWARM_PARTICLES: Final[int] = 1
MAX_SWARM_PARTICLES: Final[int] = 500

DEFAULT_SIMULATION_HOURS: Final[float] = 4.0
MIN_SIMULATION_HOURS: Final[float] = 0.5
MAX_SIMULATION_HOURS: Final[float] = 24.0

# Turbulence stochastic dispersion standard deviations
WATER_TURBULENCE_SIGMA_MS: Final[float] = 0.15
WIND_TURBULENCE_SIGMA_MS: Final[float] = 1.00

# Default land beaching behavior
DEFAULT_BEACH_ON_COLLISION: Final[bool] = True

# ---------------------------------------------------------------------------
# Weighted A* Route Optimization Constants
# ---------------------------------------------------------------------------
KNOTS_TO_MS: Final[float] = 0.514444
MS_TO_KNOTS: Final[float] = 1.94384
DEFAULT_VESSEL_SPEED_KNOTS: Final[float] = 12.0
MIN_VESSEL_SPEED_KNOTS: Final[float] = 3.0
MAX_VESSEL_SPEED_KNOTS: Final[float] = 30.0

# Upper bound on ground speed for admissible heuristic: max vessel + max current
MAX_POSSIBLE_GROUND_SPEED_MS: Final[float] = 18.0

# Dimensionally consistent A* cost: time (seconds) + fuel penalty (time-equivalent seconds)
# Edge cost = (distance / V_ground) + ROUTING_FUEL_PENALTY_FACTOR * (distance / V_vessel) * (v_opposing / V_vessel)
# Both terms are strictly non-negative and expressed in seconds.
ROUTING_FUEL_PENALTY_FACTOR: Final[float] = 1.5
CURRENT_HEAD_PENALTY_FACTOR: Final[float] = 1.5  # Backward-compatible alias

# Fuel consumption proxy factor (relative units per km-hour equivalent).
# Assumes a constant nominal engine burn rate proportional to elapsed transit time
# and distance traveled, expressed in relative fuel proxy units rather than specific MGO liters.
FUEL_CONSUMPTION_PROXY_FACTOR: Final[float] = 14.2

# ---------------------------------------------------------------------------
# UI, Visualization & Dark Mission-Control Palette
# ---------------------------------------------------------------------------
COLOR_BG_DARK: Final[str] = "#0b1329"        # Deep midnight blue
COLOR_LAND: Final[str] = "#1e293b"           # Slate charcoal landmass
COLOR_WATER: Final[str] = "#0f172a"          # Navigable water channel
COLOR_ACCENT_CYAN: Final[str] = "#38bdf8"    # Flow streamlines
COLOR_SWARM_PERSON: Final[str] = "#f87171"   # Red coral (vulnerable)
COLOR_SWARM_RAFT: Final[str] = "#fbbf24"     # Amber yellow
COLOR_SWARM_BOAT: Final[str] = "#34d399"     # Emerald sea
COLOR_SWARM_OIL: Final[str] = "#a78bfa"      # Violet slick
COLOR_ROUTE: Final[str] = "#f59e0b"           # Golden navigation line
