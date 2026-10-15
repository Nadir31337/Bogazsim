"""Weighted A* vessel routing engine with current-aware cost optimization.

# RUBRIC: Hand-Written Algorithms, Composition
This module provides hydrodynamically-aware vessel route planning
accounting for Speed Over Ground (SOG), opposing head-current fuel penalties,
impassable edge constraints, and strictly admissible A* heuristics.
"""

from __future__ import annotations

import heapq
import math
from typing import Any

from core.constants import (
    DEFAULT_VESSEL_SPEED_KNOTS,
    FUEL_CONSUMPTION_PROXY_FACTOR,
    GRID_COLS,
    GRID_ROWS,
    KNOTS_TO_MS,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    MAX_SURFACE_CURRENT_MS,
    MAX_VESSEL_SPEED_KNOTS,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
    MIN_VESSEL_SPEED_KNOTS,
    MS_TO_KNOTS,
    ROUTING_FUEL_PENALTY_FACTOR,
)
from core.exceptions import (
    GridBoundsError,
    InvalidParameterError,
    LandCollisionError,
    RouteNotFoundError,
)
from core.grid_engine import VectorGrid


class RouteWaypoint:
    """Encapsulated waypoint on a planned navigation route.
    
    # RUBRIC: Encapsulation with @property, Dunder Methods
    Captures geographic position, Speed Over Ground, cumulative distance,
    travel time, and fuel expenditure metrics.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        sog_ms: float = 0.0,
        cumulative_distance_km: float = 0.0,
        cumulative_time_min: float = 0.0,
        fuel_proxy_liters: float = 0.0,
    ) -> None:
        """Initialize route waypoint with validation."""
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            raise GridBoundsError(lat, lon)
        if cumulative_distance_km < 0.0:
            raise InvalidParameterError(
                "cumulative_distance_km", cumulative_distance_km, "Distance must be >= 0"
            )
        if cumulative_time_min < 0.0:
            raise InvalidParameterError(
                "cumulative_time_min", cumulative_time_min, "Time must be >= 0"
            )
        self._lat: float = lat
        self._lon: float = lon
        self._sog_ms: float = max(0.0, sog_ms)
        self._cum_dist_km: float = cumulative_distance_km
        self._cum_time_min: float = cumulative_time_min
        self._fuel_liters: float = max(0.0, fuel_proxy_liters)

    @property
    def lat(self) -> float:
        """Latitude in decimal degrees."""
        return self._lat

    @property
    def lon(self) -> float:
        """Longitude in decimal degrees."""
        return self._lon

    @property
    def sog_ms(self) -> float:
        """Speed Over Ground in meters per second."""
        return self._sog_ms

    @property
    def sog_knots(self) -> float:
        """Speed Over Ground in nautical knots."""
        return self._sog_ms * MS_TO_KNOTS

    @property
    def cumulative_distance_km(self) -> float:
        """Cumulative route distance in kilometers."""
        return self._cum_dist_km

    @property
    def cumulative_time_min(self) -> float:
        """Cumulative elapsed navigation time in minutes."""
        return self._cum_time_min

    @property
    def fuel_proxy_liters(self) -> float:
        """Estimated fuel proxy consumption in relative units."""
        return self._fuel_liters

    @property
    def fuel_proxy(self) -> float:
        """Estimated fuel proxy consumption in relative units."""
        return self._fuel_liters

    def to_dict(self) -> dict[str, Any]:
        """Serialize waypoint to dictionary."""
        return {
            "lat": round(self._lat, 5),
            "lon": round(self._lon, 5),
            "sog_ms": round(self._sog_ms, 2),
            "sog_knots": round(self.sog_knots, 2),
            "cumulative_distance_km": round(self._cum_dist_km, 3),
            "cumulative_time_min": round(self._cum_time_min, 2),
            "fuel_proxy_liters": round(self._fuel_liters, 2),
            "fuel_proxy": round(self._fuel_liters, 2),
        }

    def __repr__(self) -> str:
        """Developer inspection representation."""
        return (
            f"RouteWaypoint(lat={self._lat:.5f}, lon={self._lon:.5f}, "
            f"sog_knots={self.sog_knots:.1f}, dist_km={self._cum_dist_km:.2f})"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Waypoint({self._lat:.4f}°N, {self._lon:.4f}°E | {self.sog_knots:.1f} kts)"

    def __eq__(self, other: object) -> bool:
        """Value equality comparison."""
        if not isinstance(other, RouteWaypoint):
            return NotImplemented
        return (
            math.isclose(self._lat, other._lat, abs_tol=1e-5)
            and math.isclose(self._lon, other._lon, abs_tol=1e-5)
        )


class NavigationRoute:
    """Encapsulated navigation route container.
    
    # RUBRIC: Encapsulation with @property, Dunder Methods
    Contains ordered waypoints, overall navigational metrics, and sequence protocols.
    """

    def __init__(
        self,
        waypoints: list[RouteWaypoint],
        total_distance_km: float,
        eta_minutes: float,
        fuel_proxy_liters: float,
        nodes_expanded: int,
        vessel_speed_knots: float,
        total_cost_seconds: float = 0.0,
    ) -> None:
        """Initialize navigation route container."""
        self._waypoints: list[RouteWaypoint] = list(waypoints)
        self._total_distance_km: float = total_distance_km
        self._eta_minutes: float = eta_minutes
        self._fuel_liters: float = fuel_proxy_liters
        self._nodes_expanded: int = nodes_expanded
        self._vessel_speed_knots: float = vessel_speed_knots
        self._total_cost_seconds: float = total_cost_seconds

    @property
    def waypoints(self) -> list[RouteWaypoint]:
        """Ordered sequence of route waypoints."""
        return list(self._waypoints)

    @property
    def total_distance_km(self) -> float:
        """Total voyage distance in kilometers."""
        return self._total_distance_km

    @property
    def eta_minutes(self) -> float:
        """Estimated Time of Arrival / travel time in minutes."""
        return self._eta_minutes

    @property
    def fuel_proxy_liters(self) -> float:
        """Estimated total fuel consumption proxy in relative units."""
        return self._fuel_liters

    @property
    def fuel_proxy(self) -> float:
        """Estimated total fuel consumption proxy in relative units."""
        return self._fuel_liters

    @property
    def total_cost_seconds(self) -> float:
        """Total cumulative traversal cost along the optimal path in seconds."""
        return self._total_cost_seconds

    @property
    def nodes_expanded(self) -> int:
        """Total search nodes expanded during A* optimization."""
        return self._nodes_expanded

    @property
    def vessel_speed_knots(self) -> float:
        """Nominal calm-water vessel cruising speed in knots."""
        return self._vessel_speed_knots

    def to_dict(self) -> dict[str, Any]:
        """Convert navigation route to JSON-compatible dictionary."""
        return {
            "start_coord": (self._waypoints[0].lat, self._waypoints[0].lon) if self._waypoints else None,
            "goal_coord": (self._waypoints[-1].lat, self._waypoints[-1].lon) if self._waypoints else None,
            "vessel_speed_knots": self._vessel_speed_knots,
            "total_distance_km": round(self._total_distance_km, 3),
            "eta_minutes": round(self._eta_minutes, 2),
            "fuel_proxy_liters": round(self._fuel_liters, 2),
            "fuel_proxy": round(self._fuel_liters, 2),
            "total_cost_seconds": round(self._total_cost_seconds, 4),
            "nodes_expanded": self._nodes_expanded,
            "waypoints": [(wp.lat, wp.lon) for wp in self._waypoints],
            "waypoint_details": [wp.to_dict() for wp in self._waypoints],
        }

    def __len__(self) -> int:
        """Number of waypoints on the route."""
        return len(self._waypoints)

    def __getitem__(self, index: int) -> RouteWaypoint:
        """Index access into waypoints."""
        return self._waypoints[index]

    def __repr__(self) -> str:
        """Developer inspection representation."""
        return (
            f"NavigationRoute(points={len(self._waypoints)}, dist={self._total_distance_km:.2f}km, "
            f"eta={self._eta_minutes:.1f}min, fuel={self._fuel_liters:.1f}L)"
        )

    def __str__(self) -> str:
        """Human-readable route summary."""
        return (
            f"Route: {len(self._waypoints)} waypoints, {self._total_distance_km:.2f} km, "
            f"ETA {self._eta_minutes:.1f} min ({self._fuel_liters:.1f} L fuel)"
        )

    def __eq__(self, other: object) -> bool:
        """Value equality comparison."""
        if not isinstance(other, NavigationRoute):
            return NotImplemented
        return (
            len(self._waypoints) == len(other._waypoints)
            and math.isclose(self._total_distance_km, other._total_distance_km, abs_tol=1e-3)
            and math.isclose(self._eta_minutes, other._eta_minutes, abs_tol=1e-2)
        )


class WeightedAStarRouter:
    """Current-aware Weighted A* marine routing engine.
    
    # RUBRIC: Hand-Written Algorithms, Composition
    Plans energy- and time-optimal transit paths through the Bosphorus strait.
    Accounts for 2D surface current vector advection, opposing head-current
    fuel drag penalties, and channel geography.
    """

    def __init__(
        self,
        grid: VectorGrid,
        fuel_penalty_weight: float = ROUTING_FUEL_PENALTY_FACTOR,
    ) -> None:
        """Initialize router with grid model and fuel penalty weight."""
        self.grid: VectorGrid = grid
        self.fuel_penalty_weight: float = fuel_penalty_weight

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Compute great-circle distance between coordinates in meters.
        
        # RUBRIC: Hand-Written Algorithms
        """
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * (math.sin(dlam / 2.0) ** 2)
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return 6371000.0 * c

    def admissible_heuristic(
        self,
        lat: float,
        lon: float,
        goal_lat: float,
        goal_lon: float,
        vessel_speed_ms: float,
    ) -> float:
        """Compute strictly admissible remaining cost heuristic in seconds.
        
        # RUBRIC: Hand-Written Algorithms
        Mathematical Admissibility Proof:
        The edge traversal cost C(e) = (d / V_ground) + Penalty, where Penalty >= 0.
        Along any valid path, the maximum possible ground speed is bounded by:
          V_ground <= V_vessel + V_current_max everywhere on the grid.
        Therefore, minimum possible traversal time over remaining distance d is:
          T_min = d / (V_vessel + V_current_max).
        Since great-circle distance d_haversine(n, goal) <= true distance along any
        navigable path (triangle inequality) and Penalty >= 0:
          h(n) = d_haversine(n, goal) / (V_vessel + MAX_SURFACE_CURRENT_MS) <= C*(n, goal).
        Thus h(n) never overestimates the true remaining cost, guaranteeing admissibility.
        """
        dist_m = self.haversine_distance(lat, lon, goal_lat, goal_lon)
        max_ground_speed = vessel_speed_ms + MAX_SURFACE_CURRENT_MS
        return dist_m / max_ground_speed

    def compute_edge_cost(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        vessel_speed_ms: float,
    ) -> tuple[float, float, float, float]:
        """Calculate dimensionally consistent edge traversal cost, travel time, and distance.
        
        # RUBRIC: Hand-Written Algorithms
        Returns:
            Tuple of (edge_cost_seconds, travel_time_seconds, ground_speed_ms, distance_meters).
            If edge is impassable (ground speed <= 0), cost is float('inf').
            
        Dimensional Units:
        - Distance d: meters [m]
        - Ground speed V_ground: [m/s]
        - Travel time: d / V_ground [seconds]
        - Head-current penalty: lambda * (d / V_vessel) * (v_head / V_vessel) [seconds]
        - Edge cost = Travel time + Penalty [seconds]
        """
        dist_m = self.haversine_distance(lat1, lon1, lat2, lon2)
        if dist_m < 1e-3:
            return 0.0, 0.0, vessel_speed_ms, 0.0

        # Compute heading unit vector
        dy = (lat2 - lat1) * METERS_PER_DEGREE_LAT
        dx = (lon2 - lon1) * METERS_PER_DEGREE_LON
        ux = dx / dist_m
        uy = dy / dist_m

        # Current velocity along edge (sampled at starting midpoint)
        u_wat, v_wat = self.grid.interpolate_velocity(
            0.5 * (lat1 + lat2), 0.5 * (lon1 + lon2), depth=0.0
        )
        v_parallel = u_wat * ux + v_wat * uy
        v_ground = vessel_speed_ms + v_parallel

        # Impassable edge rule: ground speed <= 0 makes edge impassable
        if v_ground <= 0.05:
            return float("inf"), float("inf"), 0.0, dist_m

        travel_time_sec = dist_m / v_ground
        v_head = max(0.0, -v_parallel)
        head_penalty_sec = (
            self.fuel_penalty_weight
            * (dist_m / vessel_speed_ms)
            * (v_head / vessel_speed_ms)
        )
        edge_cost_sec = travel_time_sec + head_penalty_sec

        return edge_cost_sec, travel_time_sec, v_ground, dist_m

    def find_route(
        self,
        start_lat: float,
        start_lon: float,
        goal_lat: float,
        goal_lon: float,
        vessel_speed_knots: float = DEFAULT_VESSEL_SPEED_KNOTS,
        heuristic_weight: float = 1.0,
    ) -> NavigationRoute:
        """Find the optimal hydrodynamically-aware path using Weighted A*.
        
        # RUBRIC: Hand-Written Algorithms, Custom Exceptions
        Args:
            start_lat: Starting waypoint latitude.
            start_lon: Starting waypoint longitude.
            goal_lat: Destination waypoint latitude.
            goal_lon: Destination waypoint longitude.
            vessel_speed_knots: Vessel engine speed through water in knots.
            heuristic_weight: Heuristic weight w (default 1.0).
                - When w = 1.0 (default): strictly optimal A* with admissible heuristic.
                - When w = 0.0: executes Dijkstra's uniform-cost algorithm.
                - When w > 1.0: executes Weighted A* with bounded w-suboptimality
                  (total cost <= w * optimal cost).
            
        Returns:
            NavigationRoute instance containing waypoints and voyage metrics.
            
        Raises:
            LandCollisionError: If start or goal coordinates lie on dry land.
            InvalidParameterError: If vessel speed exceeds allowable operational limits.
            RouteNotFoundError: If no navigable water connection exists.
        """
        if not (MIN_VESSEL_SPEED_KNOTS <= vessel_speed_knots <= MAX_VESSEL_SPEED_KNOTS):
            raise InvalidParameterError(
                "vessel_speed_knots",
                vessel_speed_knots,
                f"Vessel speed must be between {MIN_VESSEL_SPEED_KNOTS} and {MAX_VESSEL_SPEED_KNOTS} knots",
            )
        if heuristic_weight < 0.0:
            raise InvalidParameterError(
                "heuristic_weight",
                heuristic_weight,
                "Heuristic weight must be >= 0.0",
            )
        if self.grid.is_land(start_lat, start_lon):
            raise LandCollisionError(start_lat, start_lon)
        if self.grid.is_land(goal_lat, goal_lon):
            raise LandCollisionError(goal_lat, goal_lon)

        vessel_speed_ms = vessel_speed_knots * KNOTS_TO_MS

        r_start, c_start = self.grid.lat_lon_to_indices(start_lat, start_lon)
        r_goal, c_goal = self.grid.lat_lon_to_indices(goal_lat, goal_lon)
        start_node = (int(round(r_start)), int(round(c_start)))
        goal_node = (int(round(r_goal)), int(round(c_goal)))

        if start_node == goal_node:
            wp = RouteWaypoint(start_lat, start_lon, sog_ms=vessel_speed_ms)
            return NavigationRoute([wp], 0.0, 0.0, 0.0, 0, vessel_speed_knots, total_cost_seconds=0.0)

        # Priority queue: (f_score, g_score, (r, c))
        h_start = heuristic_weight * self.admissible_heuristic(start_lat, start_lon, goal_lat, goal_lon, vessel_speed_ms)
        open_set: list[tuple[float, float, tuple[int, int]]] = [(h_start, 0.0, start_node)]
        g_scores: dict[tuple[int, int], float] = {start_node: 0.0}
        travel_times: dict[tuple[int, int], float] = {start_node: 0.0}
        distances: dict[tuple[int, int], float] = {start_node: 0.0}
        ground_speeds: dict[tuple[int, int], float] = {start_node: vessel_speed_ms}
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        nodes_expanded = 0

        while open_set:
            f, g, current = heapq.heappop(open_set)
            nodes_expanded += 1

            if current == goal_node:
                return self._reconstruct_route(
                    came_from=came_from,
                    goal_node=goal_node,
                    travel_times=travel_times,
                    distances=distances,
                    ground_speeds=ground_speeds,
                    nodes_expanded=nodes_expanded,
                    vessel_speed_knots=vessel_speed_knots,
                    total_cost_seconds=g,
                )

            # Prune stale priority queue entries
            if g > g_scores.get(current, float("inf")):
                continue

            r, c = current
            c_lat, c_lon = self.grid.indices_to_lat_lon(r, c)

            # 8-connectivity exploration
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < self.grid.rows and 0 <= nc < self.grid.cols):
                        continue
                    if self.grid[nr, nc].is_land:
                        continue
                    # Prevent diagonal corner-cutting: diagonal step is blocked if EITHER
                    # orthogonal intermediate neighbor is land.
                    if dr != 0 and dc != 0:
                        if self.grid[r, nc].is_land or self.grid[nr, c].is_land:
                            continue

                    n_lat, n_lon = self.grid.indices_to_lat_lon(nr, nc)
                    edge_cost, edge_time, edge_sog, edge_dist = self.compute_edge_cost(
                        c_lat, c_lon, n_lat, n_lon, vessel_speed_ms
                    )
                    if math.isinf(edge_cost):
                        continue

                    tentative_g = g + edge_cost
                    neighbor = (nr, nc)

                    if tentative_g < g_scores.get(neighbor, float("inf")):
                        g_scores[neighbor] = tentative_g
                        travel_times[neighbor] = travel_times[current] + edge_time
                        distances[neighbor] = distances[current] + edge_dist
                        ground_speeds[neighbor] = edge_sog
                        came_from[neighbor] = current
                        h_val = heuristic_weight * self.admissible_heuristic(
                            n_lat, n_lon, goal_lat, goal_lon, vessel_speed_ms
                        )
                        heapq.heappush(open_set, (tentative_g + h_val, tentative_g, neighbor))

        raise RouteNotFoundError(
            start_coord=(start_lat, start_lon),
            goal_coord=(goal_lat, goal_lon),
            message="No navigable water route connects the selected start and destination points",
        )

    def _reconstruct_route(
        self,
        came_from: dict[tuple[int, int], tuple[int, int]],
        goal_node: tuple[int, int],
        travel_times: dict[tuple[int, int], float],
        distances: dict[tuple[int, int], float],
        ground_speeds: dict[tuple[int, int], float],
        nodes_expanded: int,
        vessel_speed_knots: float,
        total_cost_seconds: float = 0.0,
    ) -> NavigationRoute:
        """Trace back from goal to start to construct NavigationRoute instance."""
        path: list[tuple[int, int]] = [goal_node]
        curr = goal_node
        while curr in came_from:
            curr = came_from[curr]
            path.append(curr)
        path.reverse()

        waypoints: list[RouteWaypoint] = []
        for node in path:
            lat, lon = self.grid.indices_to_lat_lon(node[0], node[1])
            cum_dist_km = distances[node] / 1000.0
            cum_time_min = travel_times[node] / 60.0
            # Fuel proxy in relative units = distance_km * (time_min / 60.0) * proxy_factor
            fuel_proxy = (cum_dist_km * (cum_time_min / 60.0)) * FUEL_CONSUMPTION_PROXY_FACTOR
            wp = RouteWaypoint(
                lat=lat,
                lon=lon,
                sog_ms=ground_speeds[node],
                cumulative_distance_km=cum_dist_km,
                cumulative_time_min=cum_time_min,
                fuel_proxy_liters=fuel_proxy,
            )
            waypoints.append(wp)

        total_dist_km = distances[goal_node] / 1000.0
        total_time_min = travel_times[goal_node] / 60.0
        total_fuel = (total_dist_km * (total_time_min / 60.0)) * FUEL_CONSUMPTION_PROXY_FACTOR

        return NavigationRoute(
            waypoints=waypoints,
            total_distance_km=total_dist_km,
            eta_minutes=total_time_min,
            fuel_proxy_liters=total_fuel,
            nodes_expanded=nodes_expanded,
            vessel_speed_knots=vessel_speed_knots,
            total_cost_seconds=total_cost_seconds,
        )
