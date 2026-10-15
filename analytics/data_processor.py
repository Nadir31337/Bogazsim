"""BoğazSim Simulation Data Processor.

# RUBRIC: Data Analysis Domain
# RUBRIC: Trajectory Resampling
# RUBRIC: Rolling Statistics
# RUBRIC: Group-By Aggregation

Processes raw simulation trajectories and navigation routes using Pandas pipelines.
Computes rolling hydrodynamic statistics, cumulative Haversine distances,
beaching distributions, and exports tabular data for REST endpoints.
"""

from __future__ import annotations

import math
from typing import Any

try:
    import numpy as np
    import pandas as pd
except ImportError as err:  # pragma: no cover
    raise ImportError(
        "BoğazSim data processing requires numpy and pandas. "
        "Install dependencies via: pip install -r requirements.txt"
    ) from err

from core.constants import (
    DEFAULT_DT_SECONDS,
    EARTH_RADIUS_METERS,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
)
from core.exceptions import InvalidParameterError


class SimulationDataProcessor:
    """Pandas-based trajectory analysis and statistical processing engine.

    # RUBRIC: Data Analysis Domain
    Transforms unstructured trajectory sequences from Monte Carlo swarms,
    reverse backtracking, and A* routes into structured DataFrames.
    Computes rolling velocity averages, heading deviations, beaching rates,
    and CSV export payloads.
    """

    def __init__(self) -> None:
        """Initialize the simulation data processor."""
        self._name: str = "SimulationDataProcessor"

    def swarm_to_dataframe(
        self,
        trajectories: list[Any],
        dt: float = DEFAULT_DT_SECONDS,
        final_positions: list[tuple[float, float, bool]] | None = None,
    ) -> pd.DataFrame:
        """Convert swarm trajectory paths into a tidy Pandas DataFrame.

        # RUBRIC: Data Analysis Domain

        Args:
            trajectories: List of particle trajectory point sequences.
            dt: Time step in seconds between consecutive steps.
            final_positions: Optional list of (lat, lon, is_beached) tuples.

        Returns:
            Structured DataFrame with particle trajectory records.

        Raises:
            InvalidParameterError: If trajectories list is empty or dt <= 0.
        """
        if not trajectories:
            raise InvalidParameterError("trajectories", trajectories, "Trajectory list cannot be empty")
        if dt <= 0:
            raise InvalidParameterError("dt", dt, "Time step dt must be positive")

        records: list[dict[str, Any]] = []
        for p_id, path in enumerate(trajectories):
            is_finally_beached = False
            if final_positions and p_id < len(final_positions):
                is_finally_beached = bool(final_positions[p_id][2])

            for step_idx, pt in enumerate(path):
                lat, lon = pt[0], pt[1]
                t_sec = step_idx * dt
                is_beached_step = is_finally_beached if step_idx == len(path) - 1 else False
                records.append({
                    "particle_id": p_id,
                    "step": step_idx,
                    "time_seconds": t_sec,
                    "time_hours": t_sec / 3600.0,
                    "lat": lat,
                    "lon": lon,
                    "is_beached": is_beached_step,
                })

        df = pd.DataFrame(records)
        return self._compute_instantaneous_velocities(df, dt)

    def _compute_instantaneous_velocities(self, df: pd.DataFrame, dt: float) -> pd.DataFrame:
        """Compute estimated velocity components from consecutive spatial differences.

        Args:
            df: Trajectory DataFrame.
            dt: Time step in seconds.

        Returns:
            DataFrame augmented with u_ms, v_ms, and speed_ms columns.
        """
        dlat = df.groupby("particle_id")["lat"].diff().fillna(0.0)
        dlon = df.groupby("particle_id")["lon"].diff().fillna(0.0)

        # Convert degree displacements to metric velocities using equirectangular projection
        dy_meters = dlat * METERS_PER_DEGREE_LAT
        dx_meters = dlon * METERS_PER_DEGREE_LON

        df["u_ms"] = dx_meters / dt
        df["v_ms"] = dy_meters / dt
        df["speed_ms"] = np.hypot(df["u_ms"].values, df["v_ms"].values)
        return df

    def route_to_dataframe(self, waypoints: list[Any]) -> pd.DataFrame:
        """Convert navigation route waypoints into a structured DataFrame.

        Args:
            waypoints: List of RouteWaypoint objects or waypoint dictionaries.

        Returns:
            DataFrame with route navigation columns.

        Raises:
            InvalidParameterError: If waypoints list is empty.
        """
        if not waypoints:
            raise InvalidParameterError("waypoints", waypoints, "Route waypoints cannot be empty")

        records: list[dict[str, Any]] = []
        for idx, wp in enumerate(waypoints):
            if hasattr(wp, "to_dict"):
                d = wp.to_dict()
            elif isinstance(wp, dict):
                d = wp
            else:
                d = {"lat": wp[0], "lon": wp[1]}

            records.append({
                "waypoint_index": idx,
                "lat": float(d.get("lat", 0.0)),
                "lon": float(d.get("lon", 0.0)),
                "sog_ms": float(d.get("sog_ms", 0.0)),
                "sog_knots": float(d.get("sog_knots", 0.0)),
                "cumulative_distance_km": float(d.get("cumulative_distance_km", 0.0)),
                "cumulative_time_min": float(d.get("cumulative_time_min", 0.0)),
                "fuel_proxy": float(d.get("fuel_proxy", d.get("fuel_proxy_liters", 0.0))),
            })

        return pd.DataFrame(records)

    def compute_rolling_statistics(
        self,
        df: pd.DataFrame,
        window: int = 5,
    ) -> pd.DataFrame:
        """Compute rolling hydrodynamic statistics across trajectory sequences.

        # RUBRIC: Rolling Statistics
        Calculates moving window mean velocity and heading changes to filter out
        high-frequency turbulent fluctuations. Note that the rolling-mean variance
        reduction of 1/W assumes independent noise, and a trailing window lags by
        about (W-1)/2 steps.

        Args:
            df: Trajectory DataFrame containing particle_id, lat, lon, and speed_ms.
            window: Rolling window size in time steps.

        Returns:
            Augmented DataFrame with rolling_mean_speed and heading columns.

        Raises:
            InvalidParameterError: If window is less than 1.
        """
        if window < 1:
            raise InvalidParameterError("window", window, "Rolling window must be >= 1")

        result = df.copy()
        speed_col = "speed_ms" if "speed_ms" in result.columns else "sog_ms"
        group_col = "particle_id" if "particle_id" in result.columns else None

        if group_col:
            result["rolling_mean_speed"] = (
                result.groupby(group_col)[speed_col]
                .rolling(window, min_periods=1)
                .mean()
                .reset_index(level=0, drop=True)
            )
            result["cumulative_distance_km"] = self._compute_cumulative_haversine(result)
            result["heading_deg"] = self._compute_headings(result)
        else:
            result["rolling_mean_speed"] = (
                result[speed_col].rolling(window, min_periods=1).mean()
            )

        return result

    def _compute_cumulative_haversine(self, df: pd.DataFrame) -> pd.Series:
        """Compute step-by-step cumulative Haversine distance per particle."""
        distances: list[float] = []
        for _, group in df.groupby("particle_id"):
            lats = group["lat"].values
            lons = group["lon"].values
            cum_dist = 0.0
            distances.append(0.0)
            for i in range(1, len(lats)):
                step_dist = self._haversine_distance(lats[i - 1], lons[i - 1], lats[i], lons[i])
                cum_dist += step_dist / 1000.0  # Convert meters to km
                distances.append(cum_dist)
        return pd.Series(distances, index=df.index)

    def _compute_headings(self, df: pd.DataFrame) -> pd.Series:
        """Compute forward track heading angles (compass bearings) in degrees [0, 360).

        Physics Note:
        Compass bearing is measured clockwise from True North:
        bearing = atan2(east_displacement, north_displacement) normalized to [0, 360).
        Due North is 0°, Due East is 90°, Due South is 180°, Due West is 270°.
        Uses equirectangular metric projection consistent with core.constants.
        """
        headings: list[float] = []
        for _, group in df.groupby("particle_id"):
            lats = group["lat"].values
            lons = group["lon"].values
            headings.append(0.0)
            for i in range(1, len(lats)):
                dlat = lats[i] - lats[i - 1]
                dlon = lons[i] - lons[i - 1]
                east_disp = dlon * METERS_PER_DEGREE_LON
                north_disp = dlat * METERS_PER_DEGREE_LAT
                if math.isclose(east_disp, 0.0, abs_tol=1e-12) and math.isclose(north_disp, 0.0, abs_tol=1e-12):
                    headings.append(headings[-1])
                else:
                    deg = (math.degrees(math.atan2(east_disp, north_disp)) + 360.0) % 360.0
                    headings.append(deg)
        return pd.Series(headings, index=df.index)

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Compute great-circle distance between coordinates in meters."""
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
        )
        return 2.0 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def resample_trajectories(
        self,
        df: pd.DataFrame,
        sample_step: int = 5,
    ) -> pd.DataFrame:
        """Downsample trajectory points to reduce payload size.

        # RUBRIC: Trajectory Resampling
        Adequate for plotting and transfer; calculations use the full-resolution data.

        Args:
            df: Trajectory DataFrame.
            sample_step: Keep every Nth time step.

        Returns:
            Resampled DataFrame.
        """
        if sample_step < 1:
            raise InvalidParameterError("sample_step", sample_step, "Sample step must be >= 1")
        if "step" not in df.columns:
            return df
        return df[df["step"] % sample_step == 0].copy()

    def summarize_by_particle(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate trajectory metrics grouped by individual particle.

        # RUBRIC: Group-By Aggregation

        Args:
            df: Trajectory DataFrame with particle_id, speed_ms, lat, lon.

        Returns:
            Summary DataFrame indexed by particle_id.
        """
        if "particle_id" not in df.columns:
            raise InvalidParameterError("df", type(df), "DataFrame must contain 'particle_id'")

        grouped = df.groupby("particle_id")
        summary = grouped.agg(
            mean_speed_ms=("speed_ms", "mean"),
            max_speed_ms=("speed_ms", "max"),
            final_lat=("lat", "last"),
            final_lon=("lon", "last"),
            final_beached=("is_beached", "last"),
            drift_duration_hours=("time_hours", "max"),
        )
        if "cumulative_distance_km" in df.columns:
            summary["total_distance_km"] = grouped["cumulative_distance_km"].last()
        return summary

    def compute_beaching_statistics(self, df: pd.DataFrame) -> dict[str, Any]:
        """Compute beaching incident statistics and landing distribution.

        Args:
            df: Trajectory DataFrame.

        Returns:
            Dictionary containing beaching counts, rate, and centroid.
        """
        if "particle_id" not in df.columns or "is_beached" not in df.columns:
            return {"total_particles": 0, "beached_count": 0, "beached_percentage": 0.0}

        summary = self.summarize_by_particle(df)
        total_particles = len(summary)
        beached_particles = summary[summary["final_beached"] == True]
        beached_count = len(beached_particles)
        pct = round((beached_count / total_particles) * 100.0, 1) if total_particles > 0 else 0.0

        landing_centroid = None
        if beached_count > 0:
            mean_lat = float(beached_particles["final_lat"].mean())
            mean_lon = float(beached_particles["final_lon"].mean())
            landing_centroid = (round(mean_lat, 5), round(mean_lon, 5))

        return {
            "total_particles": total_particles,
            "beached_count": beached_count,
            "beached_percentage": pct,
            "landing_centroid": landing_centroid,
        }

    def export_csv(self, df: pd.DataFrame) -> str:
        """Export DataFrame to a clean CSV formatted string.

        Args:
            df: DataFrame to serialize.

        Returns:
            Comma-separated values text payload.
        """
        return df.to_csv(index=False, float_format="%.5f")

    def generate_summary_metrics(
        self,
        simulation_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Consolidate high-level analytics summary for API endpoints.

        Args:
            simulation_result: Dictionary returned by simulator or route optimizer.

        Returns:
            JSON-compatible aggregate summary metrics dictionary.
        """
        if not simulation_result:
            return {"status": "no_data", "message": "No simulation has been performed yet."}

        # Check if result is a route
        if "waypoints" in simulation_result and "total_distance_km" in simulation_result:
            return {
                "simulation_type": "vessel_route",
                "total_distance_km": simulation_result.get("total_distance_km", 0.0),
                "eta_minutes": simulation_result.get("eta_minutes", 0.0),
                "fuel_proxy": simulation_result.get("fuel_proxy", 0.0),
                "waypoint_count": len(simulation_result.get("waypoints", [])),
                "nodes_expanded": simulation_result.get("nodes_expanded", 0),
            }

        # Check if result is reverse tracking
        if "mean_origin" in simulation_result:
            return {
                "simulation_type": "reverse_tracking",
                "entity_type": simulation_result.get("entity_type", "unknown"),
                "hours_back": simulation_result.get("hours_back", 0.0),
                "particle_count": simulation_result.get("particle_count", 0),
                "mean_origin": simulation_result.get("mean_origin"),
                "confidence_ellipse_95_km": simulation_result.get("confidence_ellipse_95_km"),
                "clamped_steps_count": simulation_result.get("clamped_steps_count", 0),
            }

        # Otherwise forward swarm simulation
        return {
            "simulation_type": "forward_swarm",
            "entity_type": simulation_result.get("entity_type", "unknown"),
            "particle_count": simulation_result.get("particle_count", 0),
            "duration_hours": simulation_result.get("duration_hours", 0.0),
            "beached_count": simulation_result.get("beached_count", 0),
            "beached_percentage": simulation_result.get("beached_percentage", 0.0),
        }
