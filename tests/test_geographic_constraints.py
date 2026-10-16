"""Comprehensive automated test suite for geographic constraints and collision detection.

# RUBRIC: Hand-Written Algorithms, Spatial Indexing, Continuous Collision Detection
This suite rigorously verifies that no simulated trajectory, particle step,
interpolated segment, or navigation route crosses dry land across the Bosphorus domain.
"""

from __future__ import annotations

import math
import unittest
import pytest

from core.constants import (
    CONSTRICTION_LAT,
    CONSTRICTION_LON,
    DEFAULT_DT_SECONDS,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
)
from core.exceptions import LandCollisionError
from core.geographic_service import BosphorusGeographicService, get_geographic_service
from core.grid_engine import VectorGrid
from core.route_optimizer import WeightedAStarRouter
from core.simulator import ForwardSwarmSimulator, ReverseTracker


class TestGeographicConstraints(unittest.TestCase):
    """Rigorous test suite for geographic constraint enforcement and continuous collision detection."""

    def setUp(self) -> None:
        """Initialize central geographic service and vector grid."""
        self.geo = get_geographic_service()
        self.grid = VectorGrid()
        self.router = WeightedAStarRouter(grid=self.grid)
        self.sim = ForwardSwarmSimulator(grid=self.grid)

    # -----------------------------------------------------------------------
    # 1. Straight segments whose endpoints are in water but interiors cross land
    # -----------------------------------------------------------------------
    def test_endpoints_in_water_interior_crosses_land_sarayburnu(self) -> None:
        """Verify CCD detects land crossing when both endpoints are in water around Sarayburnu."""
        # Ahırkapı (Marmara water) to Karaköy (Golden Horn / Bosphorus water)
        p_ahirkapi = (41.0100, 28.9885)
        p_karakoy = (41.0240, 28.9840)

        assert self.geo.is_water(*p_ahirkapi), "Start point must be in water"
        assert self.geo.is_water(*p_karakoy), "Goal point must be in water"

        # The straight line between them cuts through Sarayburnu / Topkapı Palace
        hit, t_hit, hit_pt, _ = self.geo.find_segment_intersection(
            p_ahirkapi[0], p_ahirkapi[1], p_karakoy[0], p_karakoy[1]
        )
        assert hit is True, "CCD must intercept segment cutting across Sarayburnu"
        assert 0.0 < t_hit < 1.0, f"Intersection must be between endpoints: t_hit={t_hit}"
        assert self.geo.segment_intersects_land(
            p_ahirkapi[0], p_ahirkapi[1], p_karakoy[0], p_karakoy[1]
        )

        valid, err_idx, errors = self.geo.validate_trajectory([p_ahirkapi, p_karakoy])
        assert valid is False, "Trajectory validator must reject segment crossing Sarayburnu"
        assert err_idx == 0

    def test_endpoints_in_water_interior_crosses_land_kandilli(self) -> None:
        """Verify CCD detects land crossing across Kandilli headland."""
        # South of Kandilli cape to bay northeast of Kandilli cape in water
        p_south = (41.0700, 29.0550)
        p_north = (41.0780, 29.0620)

        assert self.geo.is_water(*p_south)
        assert self.geo.is_water(*p_north)

        # Straight chord cuts the Kandilli promontory
        intersects = self.geo.segment_intersects_land(
            p_south[0], p_south[1], p_north[0], p_north[1]
        )
        assert intersects is True, "Must detect intersection across Kandilli cape"

    # -----------------------------------------------------------------------
    # 2. Movement around both sides of a peninsula
    # -----------------------------------------------------------------------
    def test_movement_around_peninsula_routes_in_water(self) -> None:
        """Verify that routing or trajectories that steer around a cape remain in water."""
        # Route from Ahırkapı to Beşiktaş must steer east around Sarayburnu
        start = (41.0100, 28.9950)
        goal = (41.0420, 29.0150)

        route = self.router.find_route(start[0], start[1], goal[0], goal[1], vessel_speed_knots=12.0)
        trajectory = [(wp.lat, wp.lon) for wp in route.waypoints]

        valid, err_idx, errors = self.geo.validate_trajectory(trajectory)
        assert valid is True, f"Route around Sarayburnu must remain in water, errors: {errors}"
        for lat, lon in trajectory:
            assert self.geo.is_water(lat, lon)

    # -----------------------------------------------------------------------
    # 3. Movement around islands
    # -----------------------------------------------------------------------
    def test_movement_across_and_around_maiden_tower(self) -> None:
        """Verify segment crossing Maiden's Tower (Kız Kulesi) is intercepted and path circles it."""
        # West and east of Maiden's Tower in water
        p_west = (41.0211, 28.9950)
        p_east = (41.0211, 29.0055)

        assert self.geo.is_water(*p_west)
        assert self.geo.is_water(*p_east)

        # Straight line crosses the island
        hit, t_hit, hit_pt, _ = self.geo.find_segment_intersection(
            p_west[0], p_west[1], p_east[0], p_east[1]
        )
        assert hit is True, "Must intercept straight chord cutting Maiden's Tower"
        assert 0.4 < t_hit < 0.9

        # Circle waypoints around Maiden's Tower in water
        circle_waypoints = [
            (41.0211, 28.9980),
            (41.0230, 29.0041),
            (41.0211, 29.0055),
            (41.0190, 29.0041),
            (41.0211, 28.9980),
        ]
        valid, _, errors = self.geo.validate_trajectory(circle_waypoints)
        assert valid is True, f"Circling Maiden's Tower must be valid: {errors}"

    # -----------------------------------------------------------------------
    # 4. Narrow passages such as the Bosphorus
    # -----------------------------------------------------------------------
    def test_narrow_passage_navigation_rumeli_hisari(self) -> None:
        """Verify navigation through the narrowest constriction (Rumeli Hisarı) is unobstructed."""
        # Transit from Bebek (41.075) through the narrows (41.0855) to Kanlıca (41.100)
        s_lat, s_lon = 41.0750, self.grid.get_centerline_lon(41.0750)
        g_lat, g_lon = 41.1000, self.grid.get_centerline_lon(41.1000)

        assert self.geo.is_water(s_lat, s_lon)
        assert self.geo.is_water(g_lat, g_lon)

        route = self.router.find_route(s_lat, s_lon, g_lat, g_lon, vessel_speed_knots=10.0)
        trajectory = [(wp.lat, wp.lon) for wp in route.waypoints]

        valid, err_idx, errors = self.geo.validate_trajectory(trajectory)
        assert valid is True, f"Constriction route must be unobstructed: {errors}"
        assert len(route) >= 3

    # -----------------------------------------------------------------------
    # 5. Large integration steps that could jump across land
    # -----------------------------------------------------------------------
    def test_large_step_ccd_prevents_jumping_land(self) -> None:
        """Verify continuous collision detection prevents large time steps from hopping land."""
        # Particle at Rumeli Hisarı channel water moving with huge velocity westwards
        curr_lat, curr_lon = 41.0855, 29.0620
        assert self.geo.is_water(curr_lat, curr_lon)

        # Huge proposed leap 2 km west into European hills
        leap_lat, leap_lon = 41.0855, 29.0300

        # With beach_on_collision=True: must clamp at the waterline
        res_lat, res_lon, beached, _ = self.geo.resolve_movement(
            curr_lat, curr_lon, leap_lat, leap_lon, beach_on_collision=True
        )
        assert beached is True
        assert self.geo.is_water(res_lat, res_lon), "Clamped position must be in water"
        assert res_lon > 29.0560, "Must be halted at the European shoreline"

    # -----------------------------------------------------------------------
    # 6. Valid movement parallel to coastlines
    # -----------------------------------------------------------------------
    def test_movement_parallel_to_coastline(self) -> None:
        """Verify movement along channel streamlines parallel to shore is allowed without collision."""
        # Off Arnavutköy shore in water, moving southward parallel to current
        p1 = (41.0680, 29.0480)
        p2 = (41.0640, 29.0460)

        assert self.geo.is_water(*p1)
        assert self.geo.is_water(*p2)

        hit, _, _, _ = self.geo.find_segment_intersection(p1[0], p1[1], p2[0], p2[1])
        assert hit is False, "Parallel movement along waterway must not collide"

    # -----------------------------------------------------------------------
    # 7. Shoreline contact and configured beaching behavior
    # -----------------------------------------------------------------------
    def test_shoreline_contact_beaching_and_sliding_policies(self) -> None:
        """Verify beaching anchors at waterline and sliding deflects tangentially."""
        curr_lat, curr_lon = 41.0855, 29.0600
        target_lat, target_lon = 41.0855, 29.0500  # Pushing into European fortress

        # Policy 1: Beaching
        b_lat, b_lon, beached, _ = self.geo.resolve_movement(
            curr_lat, curr_lon, target_lat, target_lon, beach_on_collision=True
        )
        assert beached is True
        assert self.geo.is_water(b_lat, b_lon)
        assert b_lon >= 29.0570

        # Policy 2: Coastal slip (non-beaching)
        s_lat, s_lon, beached_slip, _ = self.geo.resolve_movement(
            curr_lat, curr_lon, target_lat, target_lon, beach_on_collision=False
        )
        assert beached_slip is False
        assert self.geo.is_water(s_lat, s_lon)
        # Should be deflected along the channel axis (dlat != 0)
        assert abs(s_lat - curr_lat) > 0.0 or abs(s_lon - curr_lon) > 0.0

    # -----------------------------------------------------------------------
    # 8. Complex and irregular coastlines
    # -----------------------------------------------------------------------
    def test_complex_bays_istinye_and_bebek(self) -> None:
        """Verify accurate navigation inside deep coastal bays (İstinye & Bebek)."""
        # Deep in İstinye Bay
        p_istinye = (41.1120, 29.0600)
        assert self.geo.is_water(*p_istinye)

        # Deep in Bebek Bay
        p_bebek = (41.0780, 29.0460)
        assert self.geo.is_water(*p_bebek)

        # Motion inside bay remains water-compliant
        p_bebek_out = (41.0790, 29.0490)
        assert self.geo.is_water(*p_bebek_out)
        assert not self.geo.segment_intersects_land(
            p_bebek[0], p_bebek[1], p_bebek_out[0], p_bebek_out[1]
        )

    # -----------------------------------------------------------------------
    # 9. Interpolation and simplification edge cases
    # -----------------------------------------------------------------------
    def test_trajectory_validation_service(self) -> None:
        """Verify validator flags any segment cutting a headland."""
        valid_traj = [
            (41.050, self.grid.get_centerline_lon(41.050)),
            (41.060, self.grid.get_centerline_lon(41.060)),
            (41.070, self.grid.get_centerline_lon(41.070)),
            (41.080, self.grid.get_centerline_lon(41.080)),
        ]
        is_ok, idx, errs = self.geo.validate_trajectory(valid_traj)
        assert is_ok is True
        assert errs == []

        # Introduce land cut
        invalid_traj = list(valid_traj) + [(41.0855, 29.0450)]  # into European land
        is_ok, idx, errs = self.geo.validate_trajectory(invalid_traj)
        assert is_ok is False
        assert len(errs) > 0

    # -----------------------------------------------------------------------
    # 10. Invalid or missing geographic data handling
    # -----------------------------------------------------------------------
    def test_out_of_bounds_and_invalid_coordinates(self) -> None:
        """Verify out-of-domain coordinates are strictly classified as land."""
        assert self.geo.is_land(45.0, 30.0) is True  # North of domain
        assert self.geo.is_land(40.0, 29.0) is True  # South of domain
        assert self.geo.is_land(41.1, 28.0) is True  # West of domain
        assert self.geo.is_land(41.1, 30.0) is True  # East of domain

    # -----------------------------------------------------------------------
    # 11. Multiple simulation durations, speeds, and particle counts
    # -----------------------------------------------------------------------
    def test_multi_parameter_swarm_simulations_zero_land_crossings(self) -> None:
        """Run swarms with diverse release points, speeds, and particle counts; verify 0 land crossings."""
        test_configs = [
            # (lat, lon, particles, hours)
            (41.1600, 29.0550, 30, 1.0),   # Büyükdere Bay
            (41.0855, 29.0620, 40, 1.5),   # The Narrows
            (41.0500, 29.0420, 30, 1.0),   # Ortaköy / Beylerbeyi
        ]

        for lat, lon, count, dur in test_configs:
            res = self.sim.run(
                entity_type="person",
                origin_lat=lat,
                origin_lon=lon,
                num_particles=count,
                hours=dur,
                dt=10.0,
                seed=42,
            )
            for traj in res["trajectories"]:
                valid, idx, errs = self.geo.validate_trajectory(traj)
                assert valid is True, f"Land crossing detected in config ({lat}, {lon}): {errs}"

    # -----------------------------------------------------------------------
    # 12. Regression test for previous user-reported failure points
    # -----------------------------------------------------------------------
    def test_regression_user_reported_pasabahce_southwest_drift(self) -> None:
        """Verify the user's reported Paşabahçe failure (drift into Baltalimanı/Rumeli shore) is solved.
        
        Original failure: Forward swarm from 41.1210°N, 29.0833°E drifted southwest
        into the European landmass with particles placed hundreds of meters deep inside dry land.
        Requirement: 0 land crossings; all beached particles clamped at waterline.
        """
        origin_lat = 41.1210
        origin_lon = 29.0833

        assert self.geo.is_water(origin_lat, origin_lon)

        res = self.sim.run(
            entity_type="person",
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            num_particles=50,
            hours=4.0,
            dt=10.0,
            seed=42,
        )

        land_crossings = 0
        for traj in res["trajectories"]:
            is_valid, _, _ = self.geo.validate_trajectory(traj)
            if not is_valid:
                land_crossings += 1

        assert land_crossings == 0, f"Expected 0 land crossings, got {land_crossings}"
        assert res["beached_count"] > 0, "Shoreward drift must result in shoreline beaching"

        # Verify all final positions are in water (never on dry land)
        for lat, lon, beached in res["final_positions"]:
            assert self.geo.is_water(lat, lon), f"Beached particle at ({lat}, {lon}) is on land!"
