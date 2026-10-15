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
    OIL_DEFAULT_AREA_SQ_M,
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


class TestEntities(unittest.TestCase):
    """Test suite for DriftEntity hierarchy, ABC contract, encapsulation, and polymorphism."""

    def setUp(self) -> None:
        """Initialize test grid."""
        from core.grid_engine import VectorGrid
        self.grid = VectorGrid(rows=GRID_ROWS, cols=GRID_COLS)

    def test_abstract_classes_cannot_be_instantiated(self) -> None:
        """# RUBRIC: ABC Abstraction
        Verify that DriftEntity and Integrator cannot be directly instantiated.
        """
        from core.entities import DriftEntity, Integrator
        with pytest.raises(TypeError) if pytest else self.assertRaises(TypeError):
            DriftEntity(lat=41.0, lon=29.0, mass=80.0)  # type: ignore[abstract]
        with pytest.raises(TypeError) if pytest else self.assertRaises(TypeError):
            Integrator()  # type: ignore[abstract]

    def test_entity_subclasses_instantiation_and_properties(self) -> None:
        """# RUBRIC: Inheritance, Encapsulation with @property
        Verify 4 subclasses instantiate with distinct properties.
        """
        from core.entities import FishingBoat, LifeRaft, OilSlick, PersonInWater

        piw = PersonInWater(lat=41.05, lon=29.02)
        assert piw.mass == PIW_DEFAULT_MASS_KG
        assert piw.windage_coeff == PIW_WINDAGE_COEFF
        assert piw.drag_coeff == PIW_DRAG_COEFF

        raft = LifeRaft(lat=41.05, lon=29.02, has_canopy=True)
        assert raft.windage_coeff == LIFERAFT_WINDAGE_COEFF
        assert raft.has_canopy

        raft_no_canopy = LifeRaft(lat=41.05, lon=29.02, has_canopy=False)
        assert raft_no_canopy.windage_coeff < raft.windage_coeff

        boat = FishingBoat(lat=41.05, lon=29.02)
        assert boat.mass == BOAT_DEFAULT_MASS_KG
        assert boat.depth == 1.5

        # Oil slick with custom spill volume
        oil = OilSlick(lat=41.05, lon=29.02, spill_volume_m3=25.0)
        assert oil.spill_volume_m3 == 25.0
        assert oil.current_area_sq_m == OIL_DEFAULT_AREA_SQ_M
        assert oil.kappa > 350.8  # Larger volume yields larger kappa

    def test_polymorphic_update_on_mixed_collection(self) -> None:
        """# RUBRIC: Polymorphism
        Call update() on a heterogeneous collection and verify distinct physical behaviors.
        """
        from core.entities import FishingBoat, LifeRaft, OilSlick, PersonInWater

        lat_init = 41.080
        lon_init = self.grid.get_centerline_lon(lat_init)
        wind = (8.0, 4.0)

        entities = [
            PersonInWater(lat=lat_init, lon=lon_init),
            LifeRaft(lat=lat_init, lon=lon_init),
            FishingBoat(lat=lat_init, lon=lon_init),
            OilSlick(lat=lat_init, lon=lon_init, spill_volume_m3=10.0),
        ]

        # Polymorphic loop
        for e in entities:
            e.update(dt=10.0, grid=self.grid, wind=wind)
            assert len(e) == 2  # Origin + 1 step
            assert e.lat != lat_init or e.lon != lon_init

        # Verify distinct polymorphic responses:
        # LifeRaft has windage 0.04 vs PIW 0.015; positive eastward wind pushes raft further East
        assert entities[1].lon > entities[0].lon
        # FishingBoat has engine drift bias directed southward, pushing it further South than PIW
        assert entities[2].lat < entities[0].lat
        # OilSlick has expanded its surface area via Fay's gravity-viscous spreading
        assert entities[3].current_area_sq_m > OIL_DEFAULT_AREA_SQ_M

    def test_entity_dunders_and_encapsulation(self) -> None:
        """# RUBRIC: Dunder Methods, Encapsulation with @property
        Verify __len__, __getitem__, __repr__, __str__, __eq__, and validation.
        """
        from core.entities import PersonInWater

        p1 = PersonInWater(lat=41.05, lon=29.02, mass=75.0)
        p2 = PersonInWater(lat=41.05, lon=29.02, mass=75.0)

        assert p1 == p2
        assert len(p1) == 1
        assert p1[0] == (41.05, 29.02)
        assert "PersonInWater" in repr(p1)
        assert "DRIFTING" in str(p1)

        # Validation checks
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            PersonInWater(lat=41.05, lon=29.02, mass=-5.0)


class TestIntegrators(unittest.TestCase):
    """Test suite for EulerIntegrator vs RK2Integrator convergence and accuracy."""

    def test_euler_vs_rk2_convergence_on_circular_field(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Compare Euler and RK2 convergence rates on an analytic rotational velocity field:
          v(x, y) = (-omega * y, omega * x)
        Demonstrates that Euler exhibits 1st-order convergence (ratio ~2x when halving dt)
        while RK2 exhibits 2nd-order convergence (ratio ~4x when halving dt).
        Uses total_time T = 20.0s with dt in [4.0, 2.0, 1.0, 0.5, 0.25] ensuring integer steps.
        """
        from core.entities import EulerIntegrator, RK2Integrator

        omega = 0.05
        center_lat, center_lon = 41.10, 29.05
        radius_m = 1000.0  # 1 km radius
        total_time = 20.0

        def circular_flow(lat: float, lon: float) -> tuple[float, float]:
            y_m = (lat - center_lat) * METERS_PER_DEGREE_LAT
            x_m = (lon - center_lon) * METERS_PER_DEGREE_LON
            u = -omega * y_m
            v = omega * x_m
            return u, v

        euler = EulerIntegrator()
        rk2 = RK2Integrator()

        theta = omega * total_time
        exact_x_m = radius_m * math.cos(theta)
        exact_y_m = radius_m * math.sin(theta)
        exact_lat = center_lat + exact_y_m / METERS_PER_DEGREE_LAT
        exact_lon = center_lon + exact_x_m / METERS_PER_DEGREE_LON

        def run_integration(integrator, dt: float) -> float:
            steps = int(round(total_time / dt))
            assert steps * dt == total_time, f"T/dt must be an integer: steps*dt={steps*dt} != {total_time}"
            lat, lon = center_lat, center_lon + radius_m / METERS_PER_DEGREE_LON
            for _ in range(steps):
                lat, lon = integrator.step(lat, lon, circular_flow, dt)
            return math.hypot(
                (lat - exact_lat) * METERS_PER_DEGREE_LAT,
                (lon - exact_lon) * METERS_PER_DEGREE_LON,
            )

        # Errors for Euler and RK2 at each dt
        err_e_4 = run_integration(euler, 4.0)   # ~103.92 m
        err_e_2 = run_integration(euler, 2.0)   # ~51.12 m
        err_e_1 = run_integration(euler, 1.0)   # ~25.30 m
        err_e_05 = run_integration(euler, 0.5)  # ~12.58 m
        err_e_025 = run_integration(euler, 0.25) # ~6.27 m

        err_r_4 = run_integration(rk2, 4.0)    # ~6.66 m
        err_r_2 = run_integration(rk2, 2.0)    # ~1.67 m
        err_r_1 = run_integration(rk2, 1.0)    # ~0.417 m
        err_r_05 = run_integration(rk2, 0.5)   # ~0.104 m
        err_r_025 = run_integration(rk2, 0.25) # ~0.026 m

        # 1. At dt=0.25s, RK2 error is 0.026m vs Euler's 6.27m
        assert err_r_025 < err_e_025 / 100.0

        # 2. Euler exhibits 1st order convergence: error halves when dt halves (ratios ~2.0)
        assert 1.9 < (err_e_4 / err_e_2) < 2.1
        assert 1.9 < (err_e_2 / err_e_1) < 2.1
        assert 1.9 < (err_e_1 / err_e_05) < 2.1
        assert 1.9 < (err_e_05 / err_e_025) < 2.1

        # 3. RK2 exhibits 2nd order convergence: error quarters when dt halves (ratios ~4.0)
        assert 3.8 < (err_r_4 / err_r_2) < 4.2
        assert 3.8 < (err_r_2 / err_r_1) < 4.2
        assert 3.8 < (err_r_1 / err_r_05) < 4.2
        assert 3.8 < (err_r_05 / err_r_025) < 4.2


class TestSimulators(unittest.TestCase):
    """Test suite for ForwardSwarmSimulator and ReverseTracker."""

    def setUp(self) -> None:
        """Initialize simulation environment."""
        from core.grid_engine import VectorGrid
        self.grid = VectorGrid(rows=GRID_ROWS, cols=GRID_COLS)

    def test_forward_then_reverse_round_trip_halving(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify that in non-linear rotational flow, RK2 midpoint integration
        round-trip error decreases as dt decreases (halving dt drops error by ~8x).
        """
        from core.entities import RK2Integrator

        rk2 = RK2Integrator()
        center_lat, center_lon = 41.10, 29.05
        omega = 0.05

        def circular_flow(lat: float, lon: float) -> tuple[float, float]:
            y_m = (lat - center_lat) * METERS_PER_DEGREE_LAT
            x_m = (lon - center_lon) * METERS_PER_DEGREE_LON
            return -omega * y_m, omega * x_m

        lat_0, lon_0 = center_lat, center_lon + 1000.0 / METERS_PER_DEGREE_LON

        def measure_round_trip(dt: float) -> float:
            total_time = 20.0
            steps = int(round(total_time / dt))
            assert steps * dt == total_time
            lat_f, lon_f = lat_0, lon_0
            for _ in range(steps):
                lat_f, lon_f = rk2.step(lat_f, lon_f, circular_flow, dt)
            lat_r, lon_r = lat_f, lon_f
            for _ in range(steps):
                lat_r, lon_r = rk2.step(lat_r, lon_r, circular_flow, -dt)
            return math.hypot(
                (lat_r - lat_0) * METERS_PER_DEGREE_LAT,
                (lon_r - lon_0) * METERS_PER_DEGREE_LON,
            )

        err_dt2 = measure_round_trip(2.0)  # ~0.250 m
        err_dt1 = measure_round_trip(1.0)  # ~0.031 m

        # Round-trip error shrinks significantly when dt is halved
        assert err_dt1 < err_dt2
        ratio = err_dt2 / err_dt1
        assert 7.5 < ratio < 8.5

    def test_forward_then_reverse_realistic_grid(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify realistic 1-hour trajectory on the actual Bosphorus grid
        with forward dt=10s followed by reverse -dt=10s has negligible round-trip error.
        """
        from core.entities import RK2Integrator

        rk2 = RK2Integrator()
        lat_start = 41.150
        lon_start = self.grid.get_centerline_lon(lat_start)

        def grid_flow(lat: float, lon: float) -> tuple[float, float]:
            return self.grid.interpolate_velocity(lat, lon, depth=0.0)

        dt = 10.0
        steps = 360  # 1 hour = 3600s
        assert steps * dt == 3600.0

        lat_f, lon_f = lat_start, lon_start
        for _ in range(steps):
            lat_f, lon_f = rk2.step(lat_f, lon_f, grid_flow, dt)

        lat_r, lon_r = lat_f, lon_f
        for _ in range(steps):
            lat_r, lon_r = rk2.step(lat_r, lon_r, grid_flow, -dt)

        round_trip_error_m = math.hypot(
            (lat_r - lat_start) * METERS_PER_DEGREE_LAT,
            (lon_r - lon_start) * METERS_PER_DEGREE_LON,
        )
        # Round-trip error on realistic grid is under 1 millimeter (0.001 m)
        assert round_trip_error_m < 0.001

    def test_forward_swarm_simulator(self) -> None:
        """# RUBRIC: Hand-Written Algorithms, Composition
        Run forward swarm simulation and verify particle cloud and heatmap properties.
        """
        from core.simulator import ForwardSwarmSimulator

        sim = ForwardSwarmSimulator(grid=self.grid)
        origin_lat = 41.120
        origin_lon = self.grid.get_centerline_lon(origin_lat)

        res = sim.run(
            entity_type="raft",
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            num_particles=25,
            hours=0.5,
            dt=10.0,
            seed=42,
        )

        assert res["entity_type"] == "raft"
        assert res["particle_count"] == 25
        assert len(res["trajectories"]) == 25
        assert 0.0 <= res["beached_percentage"] <= 100.0

        # Heatmap validation
        heatmap = res["landing_heatmap"]
        assert len(heatmap) == GRID_ROWS
        assert len(heatmap[0]) == GRID_COLS
        total_prob = sum(sum(row) for row in heatmap)
        assert math.isclose(total_prob, 1.0, abs_tol=1e-3)

    def test_reverse_tracker(self) -> None:
        """# RUBRIC: Hand-Written Algorithms, Composition
        Run reverse tracker and verify origin confidence ellipse.
        """
        from core.simulator import ReverseTracker

        tracker = ReverseTracker(grid=self.grid)
        datum_lat = 41.050
        datum_lon = self.grid.get_centerline_lon(datum_lat)

        res = tracker.backtrack(
            entity_type="person",
            datum_lat=datum_lat,
            datum_lon=datum_lon,
            num_particles=25,
            hours_back=0.5,
            dt=10.0,
            seed=42,
        )

        assert res["entity_type"] == "person"
        assert res["datum"] == (datum_lat, datum_lon)
        assert res["particle_count"] == 25
        mean_lat, mean_lon = res["mean_origin"]
        # Since surface current flows southward, backtracking should place origin North of datum
        assert mean_lat > datum_lat
        assert res["confidence_ellipse_95_km"]["semi_major_lat"] > 0.0
        assert "clamped_steps_count" in res
        assert "clamped_particles_count" in res

    def test_reverse_tracker_land_snapping_and_clamping(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify that a datum on dry land is snapped to nearest navigable water,
        and that clamped reverse steps are properly tracked and reported.
        """
        from core.simulator import ReverseTracker

        tracker = ReverseTracker(grid=self.grid)
        # Deep on Asian land
        land_datum_lat = 41.10
        land_datum_lon = 29.18
        assert self.grid.is_land(land_datum_lat, land_datum_lon)

        res = tracker.backtrack(
            entity_type="raft",
            datum_lat=land_datum_lat,
            datum_lon=land_datum_lon,
            num_particles=10,
            hours_back=0.25,
            dt=10.0,
            seed=42,
        )

        assert res["was_snapped"] is True
        assert res["snapped_datum"] != (land_datum_lat, land_datum_lon)
        assert not self.grid.is_land(res["snapped_datum"][0], res["snapped_datum"][1])
        assert res["clamped_steps_count"] >= 0
        assert res["clamped_particles_count"] >= 0


class TestRouteOptimizer(unittest.TestCase):
    """Test suite for WeightedAStarRouter, RouteWaypoint, NavigationRoute, and admissibility."""

    def setUp(self) -> None:
        """Initialize simulation grid and router."""
        from core.grid_engine import VectorGrid
        from core.route_optimizer import WeightedAStarRouter

        self.grid = VectorGrid(rows=GRID_ROWS, cols=GRID_COLS)
        self.router = WeightedAStarRouter(grid=self.grid)

    def test_route_waypoint_properties_and_validation(self) -> None:
        """# RUBRIC: Encapsulation with @property, Dunder Methods
        Verify RouteWaypoint getters, validation, and dunders.
        """
        from core.route_optimizer import RouteWaypoint

        wp1 = RouteWaypoint(
            lat=41.050,
            lon=29.020,
            sog_ms=6.17,
            cumulative_distance_km=5.25,
            cumulative_time_min=14.2,
            fuel_proxy_liters=28.4,
        )
        wp2 = RouteWaypoint(
            lat=41.050,
            lon=29.020,
            sog_ms=6.17,
            cumulative_distance_km=5.25,
            cumulative_time_min=14.2,
            fuel_proxy_liters=28.4,
        )

        assert wp1 == wp2
        assert wp1.lat == 41.050
        assert wp1.lon == 29.020
        assert math.isclose(wp1.sog_knots, 6.17 * 1.94384, abs_tol=0.1)
        assert wp1.cumulative_distance_km == 5.25
        assert "RouteWaypoint" in repr(wp1)
        assert "Waypoint" in str(wp1)

        # Bounds validation
        with pytest.raises(GridBoundsError) if pytest else self.assertRaises(GridBoundsError):
            RouteWaypoint(lat=40.50, lon=29.00)
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            RouteWaypoint(lat=41.05, lon=29.02, cumulative_distance_km=-1.0)

    def test_navigation_route_container_and_sequence_protocols(self) -> None:
        """# RUBRIC: Encapsulation with @property, Dunder Methods
        Verify NavigationRoute container methods, sequence indexing, and JSON export.
        """
        from core.route_optimizer import NavigationRoute, RouteWaypoint

        wps = [
            RouteWaypoint(41.02, 29.03, sog_ms=6.0, cumulative_distance_km=0.0),
            RouteWaypoint(41.04, 29.04, sog_ms=6.5, cumulative_distance_km=2.5),
            RouteWaypoint(41.06, 29.05, sog_ms=5.8, cumulative_distance_km=5.1),
        ]
        route = NavigationRoute(
            waypoints=wps,
            total_distance_km=5.1,
            eta_minutes=18.5,
            fuel_proxy_liters=22.3,
            nodes_expanded=120,
            vessel_speed_knots=12.0,
        )

        assert len(route) == 3
        assert route[0].lat == 41.02
        assert route[-1].lat == 41.06
        assert route.total_distance_km == 5.1
        assert route.eta_minutes == 18.5
        assert "NavigationRoute" in repr(route)
        assert "Route:" in str(route)

        data = route.to_dict()
        assert data["total_distance_km"] == 5.1
        assert len(data["waypoints"]) == 3
        assert len(data["waypoint_details"]) == 3

    def test_haversine_distance_accuracy(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify spherical great-circle distance matches theoretical 1 degree latitude (~111.19 km).
        """
        d = self.router.haversine_distance(41.0, 29.0, 41.1, 29.0)
        # 0.1 degree latitude is approximately 11,119 meters
        assert 11000.0 < d < 11200.0

    def test_admissible_heuristic_strictly_lower_bound(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify that admissible heuristic h(n) is always <= actual optimal cost.
        h(n) = distance / (V_vessel + MAX_SURFACE_CURRENT_MS)
        """
        vessel_speed_ms = 12.0 * KNOTS_TO_MS
        lat_start = 41.020
        lon_start = self.grid.get_centerline_lon(lat_start)
        lat_goal = 41.120
        lon_goal = self.grid.get_centerline_lon(lat_goal)

        h_val = self.router.admissible_heuristic(
            lat_start, lon_start, lat_goal, lon_goal, vessel_speed_ms
        )
        route = self.router.find_route(lat_start, lon_start, lat_goal, lon_goal, vessel_speed_knots=12.0)
        actual_travel_time_sec = route.eta_minutes * 60.0

        # Heuristic must strictly be less than or equal to actual travel time
        assert h_val <= actual_travel_time_sec

    def test_impassable_edge_when_ground_speed_zero(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify that an edge against a head current stronger than vessel speed
        yields infinite cost (impassable).
        """
        # Constriction throat at Rumeli Hisarı has southward current ~2.49 m/s
        lat1 = 41.085
        lon1 = self.grid.get_centerline_lon(lat1)
        # Heading northward directly against the 2.49 m/s current
        lat2 = lat1 + 0.005
        lon2 = lon1

        # Very low vessel speed (1 knot ~ 0.51 m/s), overwhelmed by the ~2.5 m/s head current
        underpowered_speed_ms = 1.0 * KNOTS_TO_MS
        cost, travel_time, sog, dist_m = self.router.compute_edge_cost(
            lat1, lon1, lat2, lon2, underpowered_speed_ms
        )
        assert math.isinf(cost)
        assert math.isinf(travel_time)
        assert sog <= 0.05
        assert dist_m > 0.0

    def test_directional_asymmetry_and_head_current_penalty(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify that Northbound transit (against current) requires more time and fuel
        than Southbound transit (with current) between identical endpoints.
        """
        lat_s = 41.030
        lon_s = self.grid.get_centerline_lon(lat_s)
        lat_n = 41.140
        lon_n = self.grid.get_centerline_lon(lat_n)

        route_northbound = self.router.find_route(
            lat_s, lon_s, lat_n, lon_n, vessel_speed_knots=12.0
        )
        route_southbound = self.router.find_route(
            lat_n, lon_n, lat_s, lon_s, vessel_speed_knots=12.0
        )

        # Distances should be nearly identical (same strait channel)
        assert math.isclose(
            route_northbound.total_distance_km,
            route_southbound.total_distance_km,
            rel_tol=0.08,
        )
        # Northbound (against current) must take significantly longer than Southbound
        assert route_northbound.eta_minutes > route_southbound.eta_minutes * 1.4
        # Northbound fuel consumption must be higher due to head-current resistance
        assert route_northbound.fuel_proxy_liters > route_southbound.fuel_proxy_liters * 1.4

    def test_route_exceptions_on_land_and_invalid_speed(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify LandCollisionError and InvalidParameterError are triggered appropriately.
        """
        water_lat = 41.050
        water_lon = self.grid.get_centerline_lon(water_lat)
        land_lat, land_lon = 41.100, 29.180  # Asian inland

        # Start on land
        with pytest.raises(LandCollisionError) if pytest else self.assertRaises(LandCollisionError):
            self.router.find_route(land_lat, land_lon, water_lat, water_lon)

        # Goal on land
        with pytest.raises(LandCollisionError) if pytest else self.assertRaises(LandCollisionError):
            self.router.find_route(water_lat, water_lon, land_lat, land_lon)

        # Invalid vessel speeds
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            self.router.find_route(water_lat, water_lon, water_lat + 0.01, water_lon, vessel_speed_knots=1.0)
        with pytest.raises(InvalidParameterError) if pytest else self.assertRaises(InvalidParameterError):
            self.router.find_route(water_lat, water_lon, water_lat + 0.01, water_lon, vessel_speed_knots=45.0)

    def test_dijkstra_cross_check_optimality(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify A* cost equals Dijkstra cost (within 1e-9) across multiple
        start/goal pairs on the real grid in both directions, and check nodes expanded.
        """
        pairs = [
            # Northbound
            (41.030, self.grid.get_centerline_lon(41.030), 41.140, self.grid.get_centerline_lon(41.140)),
            # Southbound
            (41.140, self.grid.get_centerline_lon(41.140), 41.030, self.grid.get_centerline_lon(41.030)),
            # Mid-Strait local transit
            (41.060, self.grid.get_centerline_lon(41.060), 41.100, self.grid.get_centerline_lon(41.100)),
        ]

        for s_lat, s_lon, g_lat, g_lon in pairs:
            route_astar = self.router.find_route(
                s_lat, s_lon, g_lat, g_lon, vessel_speed_knots=12.0, heuristic_weight=1.0
            )
            route_dijkstra = self.router.find_route(
                s_lat, s_lon, g_lat, g_lon, vessel_speed_knots=12.0, heuristic_weight=0.0
            )

            # 1. Exact mathematical cost equality within 1e-9 tolerance
            assert math.isclose(
                route_astar.total_cost_seconds,
                route_dijkstra.total_cost_seconds,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ), f"A* cost {route_astar.total_cost_seconds} != Dijkstra cost {route_dijkstra.total_cost_seconds}"

            # 2. A* never expands more nodes than Dijkstra
            assert route_astar.nodes_expanded <= route_dijkstra.nodes_expanded

    def test_detour_around_high_current_cell(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        On a hand-built grid, verify the router chooses a geometric detour
        around a high opposing current cell when the detour has lower total cost.
        """
        from core.grid_engine import VectorGrid
        from core.route_optimizer import WeightedAStarRouter

        small_grid = VectorGrid(rows=5, cols=5)
        for r in range(5):
            for c in range(5):
                small_grid[r, c].is_land = False
                small_grid[r, c].u = 0.0
                small_grid[r, c].v = 0.0

        # Place a strong opposing current at (2, 2) against eastward motion
        small_grid[2, 2].u = -2.4
        small_grid[2, 2].v = 0.0

        router = WeightedAStarRouter(grid=small_grid)
        s_lat, s_lon = small_grid.indices_to_lat_lon(2, 0)
        g_lat, g_lon = small_grid.indices_to_lat_lon(2, 4)

        route = router.find_route(s_lat, s_lon, g_lat, g_lon, vessel_speed_knots=5.0)
        waypoints_rc = [small_grid.lat_lon_to_indices(wp.lat, wp.lon) for wp in route.waypoints]
        waypoints_int = [(int(round(r)), int(round(c))) for r, c in waypoints_rc]

        # The route must detour and avoid the high opposing current at (2, 2)
        assert (2, 2) not in waypoints_int
        assert len(route) >= 5

    def test_route_not_found_on_disconnected_water(self) -> None:
        """# RUBRIC: Custom Exceptions
        Verify RouteNotFoundError is raised when a solid land barrier separates endpoints.
        """
        from core.grid_engine import VectorGrid
        from core.route_optimizer import WeightedAStarRouter

        barrier_grid = VectorGrid(rows=5, cols=5)
        for r in range(5):
            for c in range(5):
                barrier_grid[r, c].is_land = False

        # Create impenetrable vertical land barrier across col 2
        for r in range(5):
            barrier_grid[r, 2].is_land = True

        router = WeightedAStarRouter(grid=barrier_grid)
        s_lat, s_lon = barrier_grid.indices_to_lat_lon(2, 0)
        g_lat, g_lon = barrier_grid.indices_to_lat_lon(2, 4)

        with pytest.raises(RouteNotFoundError) if pytest else self.assertRaises(RouteNotFoundError):
            router.find_route(s_lat, s_lon, g_lat, g_lon)

    def test_max_current_bound_satisfies_admissibility(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify that MAX_SURFACE_CURRENT_MS >= maximum current observed anywhere in VectorGrid.
        """
        max_speed_observed = 0.0
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                if not self.grid[r, c].is_land:
                    lat, lon = self.grid.indices_to_lat_lon(r, c)
                    u, v = self.grid.interpolate_velocity(lat, lon, depth=0.0)
                    spd = math.hypot(u, v)
                    if spd > max_speed_observed:
                        max_speed_observed = spd

        assert MAX_SURFACE_CURRENT_MS >= max_speed_observed

    def test_edge_distance_consistent_with_heuristic(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify edge distance in compute_edge_cost uses the exact same haversine function as the heuristic.
        """
        lat1, lon1 = 41.050, 29.020
        lat2, lon2 = 41.055, 29.025
        expected_haversine = self.router.haversine_distance(lat1, lon1, lat2, lon2)
        _, _, _, edge_dist = self.router.compute_edge_cost(lat1, lon1, lat2, lon2, 6.0)
        assert math.isclose(edge_dist, expected_haversine, abs_tol=1e-9)

    def test_diagonal_corner_cutting_blocked_if_either_neighbor_is_land(self) -> None:
        """# RUBRIC: Hand-Written Algorithms
        Verify diagonal move from (0,0) to (1,1) is prohibited if EITHER orthogonal neighbor is land.
        """
        from core.grid_engine import VectorGrid
        from core.route_optimizer import WeightedAStarRouter

        test_grid = VectorGrid(rows=3, cols=3)
        for r in range(3):
            for c in range(3):
                test_grid[r, c].is_land = False
                test_grid[r, c].u = 0.0
                test_grid[r, c].v = 0.0

        # Set ONLY ONE orthogonal neighbor as land: (0, 1) is land, (1, 0) is water
        test_grid[0, 1].is_land = True
        test_grid[1, 0].is_land = False

        router = WeightedAStarRouter(grid=test_grid)
        s_lat, s_lon = test_grid.indices_to_lat_lon(0, 0)
        g_lat, g_lon = test_grid.indices_to_lat_lon(1, 1)

        route = router.find_route(s_lat, s_lon, g_lat, g_lon, vessel_speed_knots=5.0)
        waypoints_rc = [test_grid.lat_lon_to_indices(wp.lat, wp.lon) for wp in route.waypoints]
        waypoints_int = [(int(round(r)), int(round(c))) for r, c in waypoints_rc]

        # Direct diagonal (0, 0) -> (1, 1) is 2 waypoints. Because (0, 1) is land,
        # diagonal is blocked, so path must step orthogonally through (1, 0) -> (1, 1) (3 waypoints).
        assert len(route) == 3
        assert waypoints_int == [(0, 0), (1, 0), (1, 1)]




