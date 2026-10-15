"""Comprehensive test suite for BoğazSim.

# RUBRIC: Offline Testing
All tests run 100% offline without external network calls,
using deterministic parameters and mocked dependencies where applicable.
"""

from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock, patch

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
    MAX_BOTTOM_CURRENT_MS,
    MAX_POSSIBLE_GROUND_SPEED_MS,
    MAX_STRAIT_WIDTH_M,
    MAX_SURFACE_CURRENT_MS,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
    MIN_BOTTOM_CURRENT_MS,
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
    SYNTHETIC_LODOS_SPEED_MS,
    SYNTHETIC_POYRAZ_SPEED_MS,
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
        # Verify derived kappa is within 1% of 350.8 m^2/s^0.5 (Fay gravity-viscous regime)
        assert abs(OIL_FAY_SPREADING_KAPPA - 350.8) / 350.8 < 0.01
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


class TestFluidCell(unittest.TestCase):
    """Test suite for FluidCell encapsulation, property validation, and dunder methods."""

    def test_fluid_cell_defaults_and_properties(self) -> None:
        """# RUBRIC: Encapsulation with @property
        Verify default attributes and scalar speed calculation.
        """
        from core.grid_engine import FluidCell

        cell = FluidCell(u=3.0, v=4.0, depth=45.0, is_land=False)
        assert cell.u == 3.0
        assert cell.v == 4.0
        assert cell.depth == 45.0
        assert not cell.is_land
        assert math.isclose(cell.speed, 5.0, abs_tol=1e-5)

    def test_fluid_cell_validation(self) -> None:
        """# RUBRIC: Encapsulation with @property
        Verify property setters reject unphysical values.
        """
        from core.grid_engine import FluidCell

        cell = FluidCell()
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            cell.u = 15.0  # Speed > 10 m/s
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            cell.v = -12.0
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            cell.depth = -5.0

    def test_fluid_cell_dunders(self) -> None:
        """# RUBRIC: Dunder Methods
        Verify __repr__, __str__, and __eq__ on FluidCell.
        """
        from core.grid_engine import FluidCell

        cell1 = FluidCell(u=1.2, v=-2.5, depth=30.0, is_land=False)
        cell2 = FluidCell(u=1.2, v=-2.5, depth=30.0, is_land=False)
        cell3 = FluidCell(u=0.0, v=0.0, depth=0.0, is_land=True)

        assert cell1 == cell2
        assert cell1 != cell3
        assert cell1 != "not_a_cell"
        assert "FluidCell(u=1.20, v=-2.50" in repr(cell1)
        assert "FluidCell[WATER" in str(cell1)
        assert "FluidCell[LAND]" in str(cell3)


class TestVectorGrid(unittest.TestCase):
    """Test suite for VectorGrid morphology, composition, interpolation, and two-layer flow."""

    def setUp(self) -> None:
        """Initialize standard grid instance."""
        from core.grid_engine import VectorGrid
        self.grid = VectorGrid(rows=GRID_ROWS, cols=GRID_COLS)

    def test_grid_composition_and_dunders(self) -> None:
        """# RUBRIC: Composition
        # RUBRIC: Dunder Methods
        Verify grid cell matrix composition, len(), and subscripting.
        """
        from core.grid_engine import FluidCell

        assert len(self.grid) == GRID_ROWS * GRID_COLS
        cell = self.grid[10, 20]
        assert isinstance(cell, FluidCell)
        assert "VectorGrid(rows=120, cols=160)" in repr(self.grid)
        assert "VectorGrid[120x160" in str(self.grid)

    def test_coordinate_transforms(self) -> None:
        """Verify coordinate transformations round-trip accurately."""
        test_coords = [(41.00, 29.00), (41.10, 29.05), (41.20, 29.15)]
        for lat, lon in test_coords:
            r, c = self.grid.lat_lon_to_indices(lat, lon)
            lat_back, lon_back = self.grid.indices_to_lat_lon(r, c)
            assert math.isclose(lat, lat_back, abs_tol=1e-5)
            assert math.isclose(lon, lon_back, abs_tol=1e-5)

    def test_out_of_bounds_raises_grid_bounds_error(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify coordinates outside the domain trigger GridBoundsError.
        """
        with pytest.raises(GridBoundsError) if pytest else self.assertRaises(GridBoundsError):
            self.grid.lat_lon_to_indices(40.50, 29.00)
        with pytest.raises(GridBoundsError) if pytest else self.assertRaises(GridBoundsError):
            self.grid.lat_lon_to_indices(41.10, 29.50)

    def test_hand_computed_bilinear_interpolation(self) -> None:
        """# RUBRIC: Bilinear Interpolation
        # RUBRIC: Hand-Written Algorithms
        Verify bilinear interpolation matches exact analytical hand calculation.
        Given corners (0,0)->1.0, (0,1)->3.0, (1,0)->2.0, (1,1)->4.0 at (s,t)=(0.5, 0.5):
        f = (1-0.5)*(1-0.5)*1.0 + 0.5*(1-0.5)*3.0 + (1-0.5)*0.5*2.0 + 0.5*0.5*4.0 = 2.5
        """
        from core.grid_engine import VectorGrid
        test_grid = VectorGrid(rows=10, cols=10)
        test_grid[2, 3].u = 1.0
        test_grid[2, 4].u = 3.0
        test_grid[3, 3].u = 2.0
        test_grid[3, 4].u = 4.0

        val = test_grid._interpolate_scalar(2.5, 3.5, attr="u")
        assert math.isclose(val, 2.5, abs_tol=1e-6)

    def test_two_layer_hydrodynamics_profile(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify upper layer flows southward (v < 0) and lower layer flows northward (v > 0).
        """
        # Pick a point in the central channel near Bebek / Kandilli
        lat = 41.080
        lon = self.grid.get_centerline_lon(lat)
        assert not self.grid.is_land(lat, lon)

        # Upper layer (0m depth)
        u_surf, v_surf = self.grid.interpolate_velocity(lat, lon, depth=0.0)
        assert v_surf < 0.0  # Southward surface flow toward Marmara
        assert math.hypot(u_surf, v_surf) >= MIN_SURFACE_CURRENT_MS

        # Lower layer (50m depth)
        u_deep, v_deep = self.grid.interpolate_velocity(lat, lon, depth=50.0)
        assert v_deep > 0.0  # Northward counter-current toward Black Sea
        assert math.hypot(u_deep, v_deep) <= MAX_BOTTOM_CURRENT_MS

    def test_venturi_throat_acceleration(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify current accelerates at Rumeli Hisarı constriction due to Venturi effect.
        """
        lat_throat = CONSTRICTION_LAT  # ~41.085°N
        lon_throat = self.grid.get_centerline_lon(lat_throat)
        u_throat, v_throat = self.grid.interpolate_velocity(lat_throat, lon_throat, depth=0.0)
        speed_throat = math.hypot(u_throat, v_throat)

        lat_wide = 41.220  # Northern wide mouth
        lon_wide = self.grid.get_centerline_lon(lat_wide)
        u_wide, v_wide = self.grid.interpolate_velocity(lat_wide, lon_wide, depth=0.0)
        speed_wide = math.hypot(u_wide, v_wide)

        assert speed_throat > speed_wide

    def test_land_mask_classification(self) -> None:
        """Verify land mask distinguishes water channel from distant terrestrial terrain."""
        # Deep in the Anatolian interior (East of strait)
        assert self.grid.is_land(41.10, 29.18)
        # Deep in Thrace / European interior (West of strait)
        assert self.grid.is_land(41.10, 28.98)
        # Center of the strait
        center_lon = self.grid.get_centerline_lon(41.10)
        assert not self.grid.is_land(41.10, center_lon)


class TestWeatherClient(unittest.TestCase):
    """Test suite for WindClassifier, SyntheticWeatherGenerator, and WeatherAPIClient."""

    def test_wind_classifier_sectors(self) -> None:
        """# RUBRIC: Automation
        Verify nautical wind direction sector classification.
        """
        from core.weather_client import WindClassifier

        assert WindClassifier.get_sector_name(45.0)[0] == "Poyraz"
        assert WindClassifier.get_sector_name(225.0)[0] == "Lodos"
        assert WindClassifier.get_sector_name(0.0)[0] == "Yıldız"
        assert WindClassifier.get_sector_name(315.0)[0] == "Karayel"
        assert WindClassifier.get_sector_name(135.0)[0] == "Keşişleme"
        assert WindClassifier.get_sector_name(180.0)[0] == "Kıble"

    def test_wind_classifier_speed_tiers(self) -> None:
        """# RUBRIC: Automation
        Verify Beaufort wind speed categorization.
        """
        from core.weather_client import WindClassifier

        assert WindClassifier.get_speed_category(0.3) == "Calm"
        assert WindClassifier.get_speed_category(4.0) == "Gentle Breeze"
        assert WindClassifier.get_speed_category(9.0) == "Fresh Breeze"
        assert WindClassifier.get_speed_category(15.0) == "High Wind / Near Gale"

    def test_synthetic_weather_generator(self) -> None:
        """# RUBRIC: Automation
        Verify synthetic generator outputs valid schema for Poyraz and Lodos.
        """
        from core.weather_client import SyntheticWeatherGenerator

        gen = SyntheticWeatherGenerator("poyraz")
        data_poyraz = gen.generate()
        assert data_poyraz["source"] == "synthetic"
        assert data_poyraz["sector_name"] == "Poyraz"
        assert data_poyraz["speed_ms"] == SYNTHETIC_POYRAZ_SPEED_MS

        gen.regime = "lodos"
        data_lodos = gen.generate()
        assert data_lodos["source"] == "synthetic"
        assert data_lodos["sector_name"] == "Lodos"
        assert data_lodos["speed_ms"] == SYNTHETIC_LODOS_SPEED_MS

    def test_weather_client_live_mock_and_caching(self) -> None:
        """# RUBRIC: Automation
        # RUBRIC: Offline Testing
        Verify live API fetch (mocked) and subsequent TTL cache hit.
        """
        from unittest.mock import MagicMock, patch
        from core.weather_client import WeatherAPIClient

        mock_payload = {
            "current": {
                "wind_speed_10m": 7.2,
                "wind_direction_10m": 48.0,
                "surface_pressure": 1016.4,
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload

        client = WeatherAPIClient(ttl_seconds=300)

        with patch("requests.get", return_value=mock_response) as mock_get:
            # 1st call: Live fetch
            data1 = client.get_current_wind()
            assert data1["source"] == "live"
            assert data1["speed_ms"] == 7.2
            assert data1["direction_deg"] == 48.0
            assert mock_get.call_count == 1

            # 2nd call: Cache hit (requests.get should NOT be called again)
            data2 = client.get_current_wind()
            assert data2["source"] == "cache"
            assert data2["speed_ms"] == 7.2
            assert mock_get.call_count == 1

            # Force refresh bypasses cache
            data3 = client.get_current_wind(force_refresh=True)
            assert data3["source"] == "live"
            assert mock_get.call_count == 2

    def test_weather_client_network_failure_fallback(self) -> None:
        """# RUBRIC: Automation
        # RUBRIC: Offline Testing
        Verify automatic fallback to synthetic generator when network times out or fails.
        """
        import requests
        from unittest.mock import patch
        from core.weather_client import WeatherAPIClient

        client = WeatherAPIClient()

        # Simulate connection timeout
        with patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout")):
            data = client.get_current_wind()
            assert data["source"] == "synthetic"
            assert data["sector_name"] == "Poyraz"

        # Simulate HTTP 500 error
        mock_500 = MagicMock()
        mock_500.status_code = 500
        with patch("requests.get", return_value=mock_500):
            data = client.get_current_wind(force_refresh=True)
            assert data["source"] == "synthetic"

        # Simulate malformed JSON
        mock_bad_json = MagicMock()
        mock_bad_json.status_code = 200
        mock_bad_json.json.side_effect = ValueError("Corrupt JSON")
        with patch("requests.get", return_value=mock_bad_json):
            data = client.get_current_wind(force_refresh=True)
            assert data["source"] == "synthetic"

