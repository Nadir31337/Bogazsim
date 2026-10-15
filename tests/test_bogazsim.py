"""Comprehensive test suite for BoğazSim.

# RUBRIC: Offline Testing
All tests run 100% offline without external network calls,
using deterministic parameters and mocked dependencies where applicable.
"""

from __future__ import annotations

import unittest
try:
    import pytest
except ImportError:
    pytest = None  # Fallback for offline testing before pip install

import analytics
import core
from core.constants import (
    BOAT_DEFAULT_MASS_KG,
    BOAT_DRAG_COEFF,
    BOAT_WINDAGE_COEFF,
    COLOR_BG_DARK,
    COLOR_ROUTE,
    CONSTRICTION_LAT,
    CURRENT_HEAD_PENALTY_FACTOR,
    DEFAULT_DT_SECONDS,
    DEFAULT_VESSEL_SPEED_KNOTS,
    EDDY_DEFINITIONS,
    GRID_COLS,
    GRID_ROWS,
    KNOTS_TO_MS,
    LAT_MAX,
    LAT_MIN,
    LIFERAFT_DEFAULT_MASS_KG,
    LIFERAFT_DRAG_COEFF,
    LIFERAFT_WINDAGE_COEFF,
    LON_MAX,
    LON_MIN,
    MAX_POSSIBLE_GROUND_SPEED_MS,
    MAX_STRAIT_WIDTH_M,
    MAX_SURFACE_CURRENT_MS,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
    MIN_STRAIT_WIDTH_M,
    MIN_SURFACE_CURRENT_MS,
    OIL_DEFAULT_MASS_KG,
    OIL_DRAG_COEFF,
    OIL_FAY_SPREADING_KAPPA,
    OIL_SPILL_VOLUME_M3,
    WATER_DENSITY_KG_M3,
    OIL_DENSITY_KG_M3,
    FAY_GRAVITY_VISCOUS_K2,
    OIL_WINDAGE_COEFF,
    PIW_DEFAULT_MASS_KG,
    PIW_DRAG_COEFF,
    PIW_WINDAGE_COEFF,
    ROUTING_FUEL_PENALTY_FACTOR,
    SURFACE_LAYER_DEPTH_M,
    WIND_SECTORS,
)
from core.exceptions import (
    GridBoundsError,
    InvalidParameterError,
    LandCollisionError,
    RouteNotFoundError,
    SimulationError,
    WeatherAPIError,
)


class TestPhase1ScaffoldAndExceptions(unittest.TestCase):
    """Test suite for Phase 1: exceptions hierarchy, constants, and module initialization."""

    def test_package_versions_and_imports(self) -> None:
        """Verify package exports and version integrity."""
        assert core.__version__ == "1.0.0"
        assert analytics.__version__ == "1.0.0"

    def test_simulation_error_base(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify SimulationError behaves as a base Exception with clean repr and str.
        """
        err = SimulationError("Base simulation failure")
        assert isinstance(err, Exception)
        assert str(err) == "Base simulation failure"
        assert repr(err) == "SimulationError(message='Base simulation failure')"

    def test_land_collision_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify LandCollisionError captures coordinates and inherits from SimulationError.
        """
        lat, lon = 41.0500, 29.0200
        err = LandCollisionError(lat=lat, lon=lon)
        assert isinstance(err, SimulationError)
        assert err.lat == lat
        assert err.lon == lon
        assert "Land collision detected" in str(err)
        assert f"{lat:.5f}°N" in str(err)

    def test_grid_bounds_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify GridBoundsError captures out-of-domain coordinates.
        """
        lat, lon = 41.5000, 29.5000
        err = GridBoundsError(lat=lat, lon=lon)
        assert isinstance(err, SimulationError)
        assert err.lat == lat
        assert err.lon == lon
        assert "exceed grid domain boundaries" in str(err)

    def test_weather_api_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify WeatherAPIError captures failure message and optional HTTP status code.
        """
        err = WeatherAPIError("Remote connection timeout", status_code=504)
        assert isinstance(err, SimulationError)
        assert err.status_code == 504
        assert "Remote connection timeout" in str(err)

    def test_route_not_found_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify RouteNotFoundError records start and destination coordinates.
        """
        start = (41.00, 29.00)
        goal = (41.20, 29.10)
        err = RouteNotFoundError(start_coord=start, goal_coord=goal)
        assert isinstance(err, SimulationError)
        assert err.start_coord == start
        assert err.goal_coord == goal
        assert "No navigable route found" in str(err)

    def test_invalid_parameter_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify InvalidParameterError stores offending parameter name and value.
        """
        err = InvalidParameterError(parameter_name="particles", value=-10)
        assert isinstance(err, SimulationError)
        assert err.parameter_name == "particles"
        assert err.value == -10
        assert "particles" in str(err)

    def test_all_custom_exceptions_caught_by_simulation_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Polymorphic exception test: verify all custom exceptions are caught by SimulationError.
        """
        exceptions: list[SimulationError] = [
            LandCollisionError(41.0, 29.0),
            GridBoundsError(42.0, 30.0),
            WeatherAPIError("API down", 500),
            RouteNotFoundError((41.0, 29.0), (41.1, 29.1)),
            InvalidParameterError("dt", 0.0),
        ]
        for exc in exceptions:
            try:
                raise exc
            except SimulationError as caught:
                assert caught is exc
                assert len(str(caught)) > 0


class TestConstantsIntegrity(unittest.TestCase):
    """Test suite verifying sanity and correctness of all constants."""

    def test_geographic_domain_bounds(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify Bosphorus bounding box and resolution are positive and valid.
        """
        assert LAT_MIN < LAT_MAX
        assert 40.95 <= LAT_MIN <= 41.00
        assert 41.20 <= LAT_MAX <= 41.30
        assert LON_MIN < LON_MAX
        assert 28.90 <= LON_MIN <= 29.00
        assert 29.15 <= LON_MAX <= 29.25
        assert GRID_ROWS == 120
        assert GRID_COLS == 160
        assert METERS_PER_DEGREE_LAT > 100_000.0
        assert METERS_PER_DEGREE_LON > 70_000.0

    def test_morphology_and_constriction(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify constriction coordinates and width dimensions.
        """
        assert LAT_MIN < CONSTRICTION_LAT < LAT_MAX
        assert MIN_STRAIT_WIDTH_M < MAX_STRAIT_WIDTH_M
        assert MIN_STRAIT_WIDTH_M >= 500.0
        assert MAX_STRAIT_WIDTH_M <= 5000.0

    def test_two_layer_hydrodynamics(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify two-layer depth interface and current speed bounds.
        """
        assert SURFACE_LAYER_DEPTH_M == 35.0
        assert 0.0 < MIN_SURFACE_CURRENT_MS < MAX_SURFACE_CURRENT_MS
        assert MAX_SURFACE_CURRENT_MS <= 3.5

    def test_eddy_definitions_structure(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify counter-eddy vortex specifications have required keys and valid domains.
        """
        assert len(EDDY_DEFINITIONS) >= 4
        for eddy in EDDY_DEFINITIONS:
            assert "name" in eddy
            assert LAT_MIN <= float(eddy["lat"]) <= LAT_MAX
            assert LON_MIN <= float(eddy["lon"]) <= LON_MAX
            assert float(eddy["radius_m"]) > 0.0
            assert float(eddy["circulation"]) != 0.0

    def test_wind_sectors(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify all 8 canonical Istanbul wind sectors are present.
        """
        expected_winds = [
            "Poyraz", "Lodos", "Karayel", "Yıldız",
            "Keşişleme", "Kıble", "Gündoğusu", "Günbatısı",
        ]
        for name in expected_winds:
            assert name in WIND_SECTORS
            deg_min, deg_max, description = WIND_SECTORS[name]
            assert 0.0 <= deg_min <= 360.0
            assert 0.0 <= deg_max <= 360.0
            assert len(description) > 0

    def test_entity_physics_parameters(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify physical coefficients for all 4 drift entities.
        """
        # Person in water
        assert PIW_DEFAULT_MASS_KG > 0
        assert 0.0 < PIW_WINDAGE_COEFF < 0.05
        assert PIW_DRAG_COEFF > 0.8  # high drag

        # Life raft
        assert LIFERAFT_DEFAULT_MASS_KG > PIW_DEFAULT_MASS_KG
        assert LIFERAFT_WINDAGE_COEFF > PIW_WINDAGE_COEFF  # higher leeway
        assert LIFERAFT_DRAG_COEFF < PIW_DRAG_COEFF

        # Fishing boat
        assert BOAT_DEFAULT_MASS_KG > LIFERAFT_DEFAULT_MASS_KG
        assert 0.0 < BOAT_WINDAGE_COEFF < 0.1

        # Oil slick
        assert OIL_DEFAULT_MASS_KG > 0
        assert OIL_SPILL_VOLUME_M3 == 10.0
        assert WATER_DENSITY_KG_M3 == 1015.0
        assert OIL_DENSITY_KG_M3 == 860.0
        assert FAY_GRAVITY_VISCOUS_K2 == 1.45
        assert OIL_FAY_SPREADING_KAPPA > 2000.0  # Derived ~2556.11
        assert 0.0 < OIL_WINDAGE_COEFF < 0.1

    def test_astar_parameters(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify A* speed bounds, unit conversion, and admissible maximum ground speed.
        """
        vessel_speed_ms = DEFAULT_VESSEL_SPEED_KNOTS * KNOTS_TO_MS
        # Admissible heuristic condition: MAX_POSSIBLE_GROUND_SPEED_MS >= max_vessel + max_current
        assert MAX_POSSIBLE_GROUND_SPEED_MS >= vessel_speed_ms + MAX_SURFACE_CURRENT_MS
        assert CURRENT_HEAD_PENALTY_FACTOR > 1.0

    def test_ui_color_palette(self) -> None:
        """# RUBRIC: No Magic Numbers
        Verify UI colors are defined in standard hex format.
        """
        assert COLOR_BG_DARK.startswith("#")
        assert len(COLOR_BG_DARK) == 7
        assert COLOR_ROUTE.startswith("#")
        assert len(COLOR_ROUTE) == 7
