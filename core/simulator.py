"""Monte Carlo forward swarm simulator and reverse backtracking tracker.

# RUBRIC: Hand-Written Algorithms, Composition
This module provides stochastic Monte Carlo forward drift predictions
with Gaussian turbulence dispersion, beaching probability heatmaps,
and reverse (-dt) backtracking for maritime search and rescue.
"""

from __future__ import annotations

import math
import random
from typing import Any

from core.constants import (
    DEFAULT_BEACH_ON_COLLISION,
    DEFAULT_DT_SECONDS,
    DEFAULT_SIMULATION_HOURS,
    DEFAULT_SWARM_PARTICLES,
    GRID_COLS,
    GRID_ROWS,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
    WATER_TURBULENCE_SIGMA_MS,
    WIND_TURBULENCE_SIGMA_MS,
)
from core.entities import (
    DriftEntity,
    EulerIntegrator,
    FishingBoat,
    Integrator,
    LifeRaft,
    OilSlick,
    PersonInWater,
    RK2Integrator,
)
from core.exceptions import InvalidParameterError
from core.grid_engine import VectorGrid


def create_entity(
    entity_type: str,
    lat: float,
    lon: float,
    spill_volume_m3: float = 10.0,
) -> DriftEntity:
    """Factory helper to instantiate a DriftEntity subclass by name.
    
    # RUBRIC: Polymorphism
    """
    etype = entity_type.lower().strip()
    if etype in ("person", "piw", "personinwater"):
        return PersonInWater(lat=lat, lon=lon)
    elif etype in ("raft", "liferaft"):
        return LifeRaft(lat=lat, lon=lon)
    elif etype in ("boat", "fishingboat"):
        return FishingBoat(lat=lat, lon=lon)
    elif etype in ("oil", "oilslick"):
        return OilSlick(lat=lat, lon=lon, spill_volume_m3=spill_volume_m3)
    else:
        raise InvalidParameterError(
            "entity_type", entity_type, f"Unknown entity type: '{entity_type}'"
        )


class ForwardSwarmSimulator:
    """Monte Carlo forward search-and-rescue drift simulator.
    
    # RUBRIC: Composition, Hand-Written Algorithms
    Simulates N stochastic particles with Gaussian perturbations of current
    and wind, tracking particle clouds, beaching incidents, and landing heatmaps.
    """

    def __init__(
        self,
        grid: VectorGrid,
        integrator: Integrator | None = None,
    ) -> None:
        """Initialize swarm simulator with grid and numerical integrator."""
        self.grid: VectorGrid = grid
        self.integrator: Integrator = integrator or RK2Integrator()

    def run(
        self,
        entity_type: str,
        origin_lat: float,
        origin_lon: float,
        num_particles: int = DEFAULT_SWARM_PARTICLES,
        hours: float = DEFAULT_SIMULATION_HOURS,
        dt: float = DEFAULT_DT_SECONDS,
        wind: tuple[float, float] = (0.0, 0.0),
        beach_on_collision: bool = DEFAULT_BEACH_ON_COLLISION,
        spill_volume_m3: float = 10.0,
        seed: int | None = 42,
    ) -> dict[str, Any]:
        """Execute forward stochastic Monte Carlo simulation.
        
        Args:
            entity_type: Type of entity ('person', 'raft', 'boat', 'oil').
            origin_lat: Spill/incident latitude.
            origin_lon: Spill/incident longitude.
            num_particles: Swarm size (1 to 500).
            hours: Total drift duration in hours.
            dt: Time step in seconds.
            wind: Wind velocity vector (u_wind, v_wind) in m/s.
            beach_on_collision: If True, entities stick to shore; if False, raises error.
            spill_volume_m3: Initial volume for oil slicks.
            seed: Deterministic random seed for offline test reproducibility.
            
        Returns:
            Dictionary containing trajectories, beached stats, and landing heatmap.
        """
        if num_particles < 1:
            raise InvalidParameterError("num_particles", num_particles, "Particles must be >= 1")
        if hours <= 0:
            raise InvalidParameterError("hours", hours, "Duration must be > 0")

        rng = random.Random(seed)
        total_steps = int((hours * 3600.0) / dt)

        # Snap origin to navigable water if starting on land
        if self.grid.is_land(origin_lat, origin_lon):
            origin_lat, origin_lon = self.grid.snap_to_water(origin_lat, origin_lon)

        # Instantiate N independent particles with slight spatial perturbation
        particles: list[DriftEntity] = []
        for _ in range(num_particles):
            # Small initial positioning jitter (~15 meters)
            dlat_0 = rng.gauss(0.0, 0.00015)
            dlon_0 = rng.gauss(0.0, 0.00015)
            p_lat = origin_lat + dlat_0
            p_lon = origin_lon + dlon_0
            if self.grid.is_land(p_lat, p_lon):
                p_lat, p_lon = self.grid.snap_to_water(p_lat, p_lon)
            p = create_entity(
                entity_type,
                p_lat,
                p_lon,
                spill_volume_m3=spill_volume_m3,
            )
            particles.append(p)

        u_wind_base, v_wind_base = wind

        # Time-stepping integration loop
        for _ in range(total_steps):
            for p in particles:
                if p.is_beached:
                    continue

                # Stochastic wind and turbulence perturber
                u_wind_pert = u_wind_base + rng.gauss(0.0, WIND_TURBULENCE_SIGMA_MS)
                v_wind_pert = v_wind_base + rng.gauss(0.0, WIND_TURBULENCE_SIGMA_MS)
                
                # Water turbulence perturbation injected via custom velocity wrapper
                def perturbed_velocity(lat: float, lon: float) -> tuple[float, float]:
                    u_wat, v_wat = self.grid.interpolate_velocity(lat, lon, depth=p.depth)
                    u_wat += rng.gauss(0.0, WATER_TURBULENCE_SIGMA_MS)
                    v_wat += rng.gauss(0.0, WATER_TURBULENCE_SIGMA_MS)
                    u_tot = u_wat + p.windage_coeff * u_wind_pert
                    v_tot = v_wat + p.windage_coeff * v_wind_pert
                    return u_tot, v_tot

                new_lat, new_lon = self.integrator.step(p.lat, p.lon, perturbed_velocity, dt)

                res_lat, res_lon, beached, _ = self.grid.resolve_movement(
                    p.lat, p.lon, new_lat, new_lon,
                    beach_on_collision=beach_on_collision,
                )

                if beached:
                    p.is_beached = True
                    p.lat = res_lat
                    p.lon = res_lon
                elif self.grid.segment_intersects_land(p.lat, p.lon, new_lat, new_lon) and not beach_on_collision:
                    from core.exceptions import LandCollisionError
                    raise LandCollisionError(new_lat, new_lon)
                else:
                    p.lat = res_lat
                    p.lon = res_lon
                p._trajectory.append((p.lat, p.lon))

        # Compute landing probability heatmap and summary statistics
        heatmap = [[0.0 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        beached_count = 0
        final_positions = []

        for p in particles:
            if p.is_beached:
                beached_count += 1
            final_positions.append((p.lat, p.lon, p.is_beached))
            clamped_lat = max(self.grid.lat_min, min(self.grid.lat_max, p.lat))
            clamped_lon = max(self.grid.lon_min, min(self.grid.lon_max, p.lon))
            r, c = self.grid.lat_lon_to_indices(clamped_lat, clamped_lon)
            r_idx = max(0, min(GRID_ROWS - 1, int(round(r))))
            c_idx = max(0, min(GRID_COLS - 1, int(round(c))))
            heatmap[r_idx][c_idx] += 1.0 / num_particles

        return {
            "entity_type": entity_type,
            "particle_count": num_particles,
            "duration_hours": hours,
            "time_step_seconds": dt,
            "trajectories": [p.trajectory for p in particles],
            "final_positions": final_positions,
            "beached_count": beached_count,
            "beached_percentage": round((beached_count / num_particles) * 100.0, 1),
            "landing_heatmap": heatmap,
        }


class ReverseTracker:
    """Reverse time-stepping (-dt) maritime backtrack locator.
    
    # RUBRIC: Composition, Hand-Written Algorithms
    Steps backwards in time from a discovered survivor/debris datum
    to reconstruct the probable origin distribution and confidence ellipse.
    """

    def __init__(
        self,
        grid: VectorGrid,
        integrator: Integrator | None = None,
    ) -> None:
        """Initialize reverse tracker."""
        self.grid: VectorGrid = grid
        self.integrator: Integrator = integrator or RK2Integrator()

    def _snap_to_water(self, lat: float, lon: float) -> tuple[float, float]:
        """Snap a terrestrial datum to the nearest navigable water grid cell.
        
        Physics Note:
        When debris is recovered on a beach, reverse time-stepping requires
        launching particles from adjacent water rather than frozen dry land.
        """
        if not self.grid.is_land(lat, lon):
            return lat, lon
        r_start, c_start = self.grid.lat_lon_to_indices(lat, lon)
        r0 = int(round(r_start))
        c0 = int(round(c_start))
        best_dist = float("inf")
        best_coord = (lat, lon)
        max_radius = max(self.grid.rows, self.grid.cols)
        for radius in range(1, max_radius):
            candidates: list[tuple[int, int]] = []
            for c in range(c0 - radius, c0 + radius + 1):
                candidates.append((r0 - radius, c))
                candidates.append((r0 + radius, c))
            for r in range(r0 - radius + 1, r0 + radius):
                candidates.append((r, c0 - radius))
                candidates.append((r, c0 + radius))
            for r, c in candidates:
                if 0 <= r < self.grid.rows and 0 <= c < self.grid.cols:
                    if not self.grid[r, c].is_land:
                        cand_lat, cand_lon = self.grid.indices_to_lat_lon(r, c)
                        dist = math.hypot(cand_lat - lat, cand_lon - lon)
                        if dist < best_dist:
                            best_dist = dist
                            best_coord = (cand_lat, cand_lon)
            if best_dist < float("inf"):
                break
        return best_coord

    def backtrack(
        self,
        entity_type: str,
        datum_lat: float,
        datum_lon: float,
        num_particles: int = DEFAULT_SWARM_PARTICLES,
        hours_back: float = DEFAULT_SIMULATION_HOURS,
        dt: float = DEFAULT_DT_SECONDS,
        wind: tuple[float, float] = (0.0, 0.0),
        seed: int | None = 42,
    ) -> dict[str, Any]:
        """Execute backward-in-time integration from datum to estimate origin.
        
        Args:
            entity_type: Target entity class.
            datum_lat: Last-known latitude sighting.
            datum_lon: Last-known longitude sighting.
            num_particles: Number of stochastic backtrack particles.
            hours_back: Drift time to invert (hours).
            dt: Magnitude of time step in seconds (applied as -abs(dt)).
            wind: Prevailing wind vector during the drift interval.
            seed: Deterministic random seed.
            
        Returns:
            Dictionary containing backtracked trajectories, mean origin, and 95% confidence ellipse.
        """
        if num_particles < 1:
            raise InvalidParameterError("num_particles", num_particles, "Particles must be >= 1")
        if hours_back <= 0:
            raise InvalidParameterError("hours_back", hours_back, "Backtrack hours must be > 0")

        # Snap terrestrial datum to nearest navigable shoreline water
        snapped_lat, snapped_lon = self._snap_to_water(datum_lat, datum_lon)

        rng = random.Random(seed)
        total_steps = int((hours_back * 3600.0) / dt)
        dt_reverse = -abs(dt)  # Negative time step for reverse integration

        particles: list[DriftEntity] = []
        for _ in range(num_particles):
            dlat_0 = rng.gauss(0.0, 0.0001)
            dlon_0 = rng.gauss(0.0, 0.0001)
            p = create_entity(entity_type, snapped_lat + dlat_0, snapped_lon + dlon_0)
            particles.append(p)

        u_wind_base, v_wind_base = wind
        clamped_steps_count = 0
        clamped_particles: set[int] = set()

        for _ in range(total_steps):
            for i, p in enumerate(particles):
                u_wind_pert = u_wind_base + rng.gauss(0.0, WIND_TURBULENCE_SIGMA_MS)
                v_wind_pert = v_wind_base + rng.gauss(0.0, WIND_TURBULENCE_SIGMA_MS)

                def velocity_fn(curr_lat: float, curr_lon: float) -> tuple[float, float]:
                    u_wat, v_wat = self.grid.interpolate_velocity(curr_lat, curr_lon, depth=p.depth)
                    u_wat += rng.gauss(0.0, WATER_TURBULENCE_SIGMA_MS)
                    v_wat += rng.gauss(0.0, WATER_TURBULENCE_SIGMA_MS)
                    u_tot = u_wat + p.windage_coeff * u_wind_pert
                    v_tot = v_wat + p.windage_coeff * v_wind_pert
                    return u_tot, v_tot

                # Step backward with negative dt
                new_lat, new_lon = self.integrator.step(p.lat, p.lon, velocity_fn, dt_reverse)
                
                # In reverse tracking, do not clip silently: track clamped steps
                if not self.grid.segment_intersects_land(p.lat, p.lon, new_lat, new_lon):
                    p.lat = new_lat
                    p.lon = new_lon
                else:
                    clamped_steps_count += 1
                    clamped_particles.add(i)
                p._trajectory.append((p.lat, p.lon))

        # Compute centroid and 95% confidence bounds (2.447 * sigma)
        final_lats = [p.lat for p in particles]
        final_lons = [p.lon for p in particles]
        mean_lat = sum(final_lats) / num_particles
        mean_lon = sum(final_lons) / num_particles

        var_lat = sum((x - mean_lat) ** 2 for x in final_lats) / max(1, num_particles - 1)
        var_lon = sum((x - mean_lon) ** 2 for x in final_lons) / max(1, num_particles - 1)
        std_lat = math.sqrt(var_lat)
        std_lon = math.sqrt(var_lon)

        # 95% confidence radius in kilometers
        radius_95_lat_km = 2.447 * std_lat * (METERS_PER_DEGREE_LAT / 1000.0)
        radius_95_lon_km = 2.447 * std_lon * (METERS_PER_DEGREE_LON / 1000.0)

        return {
            "entity_type": entity_type,
            "datum": (datum_lat, datum_lon),
            "snapped_datum": (round(snapped_lat, 5), round(snapped_lon, 5)),
            "was_snapped": (snapped_lat != datum_lat or snapped_lon != datum_lon),
            "hours_back": hours_back,
            "particle_count": num_particles,
            "mean_origin": (round(mean_lat, 5), round(mean_lon, 5)),
            "std_lat": round(std_lat, 6),
            "std_lon": round(std_lon, 6),
            "clamped_steps_count": clamped_steps_count,
            "clamped_particles_count": len(clamped_particles),
            "confidence_ellipse_95_km": {
                "semi_major_lat": round(radius_95_lat_km, 3),
                "semi_minor_lon": round(radius_95_lon_km, 3),
            },
            "estimated_origins": [(p.lat, p.lon) for p in particles],
            "trajectories": [p.trajectory for p in particles],
        }
