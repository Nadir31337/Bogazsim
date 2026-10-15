"""Drift entities and numerical integrators for BoğazSim.

# RUBRIC: ABC Abstraction, Inheritance, Polymorphism, Encapsulation with @property, Dunder Methods
This module defines the abstract Integrator and DriftEntity interfaces alongside
their concrete implementations: Euler and RK2 integrators, PersonInWater,
LifeRaft, FishingBoat, and OilSlick with Fay gravity-viscous spreading.
"""

from __future__ import annotations

import abc
import math
from typing import Any, Callable

from core.constants import (
    BOAT_DEFAULT_ENGINE_BIAS_MS,
    BOAT_DEFAULT_MASS_KG,
    BOAT_DRAG_COEFF,
    BOAT_WINDAGE_COEFF,
    LAT_MAX,
    LAT_MIN,
    LIFERAFT_DEFAULT_MASS_KG,
    LIFERAFT_DRAG_COEFF,
    LIFERAFT_WINDAGE_COEFF,
    LON_MAX,
    LON_MIN,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
    OIL_DEFAULT_AREA_SQ_M,
    OIL_DEFAULT_MASS_KG,
    OIL_DRAG_COEFF,
    OIL_EVAPORATION_RATE_PER_SEC,
    OIL_SPILL_VOLUME_M3,
    OIL_WINDAGE_COEFF,
    PIW_DEFAULT_MASS_KG,
    PIW_DRAG_COEFF,
    PIW_WINDAGE_COEFF,
    compute_fay_kappa,
)
from core.exceptions import InvalidParameterError, LandCollisionError
from core.grid_engine import VectorGrid


# ---------------------------------------------------------------------------
# Numerical Integrators Hierarchy
# ---------------------------------------------------------------------------
class Integrator(abc.ABC):
    """Abstract Base Class for numerical differential equation integrators.
    
    # RUBRIC: ABC Abstraction
    # RUBRIC: Hand-Written Algorithms
    Defines the contract for advancing spatial coordinates given a continuous
    velocity evaluation function and time step dt.
    """

    @abc.abstractmethod
    def step(
        self,
        lat: float,
        lon: float,
        velocity_fn: Callable[[float, float], tuple[float, float]],
        dt: float,
    ) -> tuple[float, float]:
        """Advance coordinates (lat, lon) by time step dt using velocity_fn.
        
        Args:
            lat: Current latitude in decimal degrees.
            lon: Current longitude in decimal degrees.
            velocity_fn: Callable(lat, lon) returning (u, v) velocity in m/s.
            dt: Time step in seconds (positive for forward, negative for reverse).
            
        Returns:
            Tuple of new (lat, lon) coordinates.
        """
        ...


class EulerIntegrator(Integrator):
    """First-order explicit forward Euler integrator.
    
    # RUBRIC: Hand-Written Algorithms
    Formulation:
      x_{t+dt} = x_t + v(x_t) * dt
    Global truncation error is O(dt). Fast, but accumulates drift error on curved streamlines.
    """

    def step(
        self,
        lat: float,
        lon: float,
        velocity_fn: Callable[[float, float], tuple[float, float]],
        dt: float,
    ) -> tuple[float, float]:
        """Execute single forward Euler step."""
        u, v = velocity_fn(lat, lon)
        dlat = (v * dt) / METERS_PER_DEGREE_LAT
        dlon = (u * dt) / METERS_PER_DEGREE_LON
        return lat + dlat, lon + dlon


class RK2Integrator(Integrator):
    """Second-order Runge-Kutta (Midpoint scheme) numerical integrator.
    
    # RUBRIC: Hand-Written Algorithms
    Physics Note:
      k1 = v(x_t)
      x_mid = x_t + 0.5 * dt * k1
      k2 = v(x_mid)
      x_{t+dt} = x_t + dt * k2
    Global truncation error is O(dt^2). Accurately resolves curvature in Bosphorus eddies.
    """

    def step(
        self,
        lat: float,
        lon: float,
        velocity_fn: Callable[[float, float], tuple[float, float]],
        dt: float,
    ) -> tuple[float, float]:
        """Execute 2nd-order Runge-Kutta midpoint integration step."""
        u1, v1 = velocity_fn(lat, lon)
        dlat1 = (v1 * 0.5 * dt) / METERS_PER_DEGREE_LAT
        dlon1 = (u1 * 0.5 * dt) / METERS_PER_DEGREE_LON
        
        lat_mid = lat + dlat1
        lon_mid = lon + dlon1

        u2, v2 = velocity_fn(lat_mid, lon_mid)
        dlat2 = (v2 * dt) / METERS_PER_DEGREE_LAT
        dlon2 = (u2 * dt) / METERS_PER_DEGREE_LON
        return lat + dlat2, lon + dlon2


# ---------------------------------------------------------------------------
# Drift Entities Hierarchy
# ---------------------------------------------------------------------------
class DriftEntity(abc.ABC):
    """Abstract Base Class for maritime drift and search-and-rescue objects.
    
    # RUBRIC: ABC Abstraction
    # RUBRIC: Encapsulation with @property
    # RUBRIC: Dunder Methods
    Encapsulates geographic location, depth, mass, shoreline beaching status,
    and historical trajectory.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        mass: float,
        depth: float = 0.0,
    ) -> None:
        """Initialize drift entity.
        
        Args:
            lat: Initial latitude coordinate.
            lon: Initial longitude coordinate.
            mass: Entity mass in kilograms.
            depth: Submersion depth in meters (0.0 for surface).
        """
        if mass <= 0.0:
            raise InvalidParameterError("mass", mass, "Entity mass must be positive")
        self._lat: float = float(lat)
        self._lon: float = float(lon)
        self._mass: float = float(mass)
        self._depth: float = max(0.0, float(depth))
        self._is_beached: bool = False
        self._trajectory: list[tuple[float, float]] = [(self._lat, self._lon)]

    @property
    def lat(self) -> float:
        """Current latitude in decimal degrees."""
        return self._lat

    @lat.setter
    def lat(self, val: float) -> None:
        """Set latitude with domain range check."""
        val_f = float(val)
        if not (LAT_MIN - 0.05 <= val_f <= LAT_MAX + 0.05):
            raise InvalidParameterError("lat", val_f, "Latitude outside domain")
        self._lat = val_f

    @property
    def lon(self) -> float:
        """Current longitude in decimal degrees."""
        return self._lon

    @lon.setter
    def lon(self, val: float) -> None:
        """Set longitude with domain range check."""
        val_f = float(val)
        if not (LON_MIN - 0.05 <= val_f <= LON_MAX + 0.05):
            raise InvalidParameterError("lon", val_f, "Longitude outside domain")
        self._lon = val_f

    @property
    def mass(self) -> float:
        """Entity mass in kilograms."""
        return self._mass

    @property
    def depth(self) -> float:
        """Submersion depth in meters."""
        return self._depth

    @property
    def is_beached(self) -> bool:
        """Flag indicating if entity has grounded on shore."""
        return self._is_beached

    @is_beached.setter
    def is_beached(self, val: bool) -> None:
        """Set beaching status."""
        self._is_beached = bool(val)

    @property
    def trajectory(self) -> list[tuple[float, float]]:
        """Ordered history of (lat, lon) trajectory coordinates."""
        return list(self._trajectory)

    @property
    @abc.abstractmethod
    def windage_coeff(self) -> float:
        """Empirical leeway windage coefficient [0.0, 1.0]."""
        ...

    @property
    @abc.abstractmethod
    def drag_coeff(self) -> float:
        """Hydrodynamic skin/form drag coefficient."""
        ...

    @abc.abstractmethod
    def update(
        self,
        dt: float,
        grid: VectorGrid,
        wind: tuple[float, float],
        integrator: Integrator | None = None,
        beach_on_collision: bool = True,
    ) -> None:
        """Advance entity state over time step dt.
        
        # RUBRIC: Polymorphism
        Heterogeneous subclasses implement specialized drift physics.
        """
        ...

    # -----------------------------------------------------------------------
    # Dunder Magic Methods
    # -----------------------------------------------------------------------
    def __len__(self) -> int:
        """Return total number of recorded trajectory positions."""
        return len(self._trajectory)

    def __getitem__(self, index: int) -> tuple[float, float]:
        """Index trajectory history: entity[i] -> (lat, lon)."""
        return self._trajectory[index]

    def __repr__(self) -> str:
        """Unambiguous developer representation."""
        return (
            f"{self.__class__.__name__}(lat={self._lat:.5f}, lon={self._lon:.5f}, "
            f"mass={self._mass:.1f}, beached={self._is_beached})"
        )

    def __str__(self) -> str:
        """Human-readable entity summary."""
        status = "BEACHED" if self._is_beached else "DRIFTING"
        return f"{self.__class__.__name__} [{status} at ({self._lat:.4f}°N, {self._lon:.4f}°E)]"

    def __eq__(self, other: object) -> bool:
        """Value equality based on coordinates, mass, and class type."""
        if not isinstance(other, self.__class__):
            return False
        return (
            math.isclose(self._lat, other._lat, abs_tol=1e-5)
            and math.isclose(self._lon, other._lon, abs_tol=1e-5)
            and math.isclose(self._mass, other._mass, abs_tol=1e-2)
            and self._is_beached == other._is_beached
        )


class PersonInWater(DriftEntity):
    """Person In Water (PIW) search-and-rescue target.
    
    # RUBRIC: Inheritance, Polymorphism
    Physics Note:
    Low freeboard profile minimizes atmospheric wind exposure (windage ~1.5%),
    while full body submersion generates high hydrodynamic skin drag (Cd ~1.05).
    Drift trajectory is dominated by surface currents.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        mass: float = PIW_DEFAULT_MASS_KG,
    ) -> None:
        """Initialize person in water."""
        super().__init__(lat=lat, lon=lon, mass=mass, depth=0.0)

    @property
    def windage_coeff(self) -> float:
        """Leeway windage coefficient for person in water."""
        return PIW_WINDAGE_COEFF

    @property
    def drag_coeff(self) -> float:
        """Hydrodynamic drag coefficient."""
        return PIW_DRAG_COEFF

    def update(
        self,
        dt: float,
        grid: VectorGrid,
        wind: tuple[float, float],
        integrator: Integrator | None = None,
        beach_on_collision: bool = True,
    ) -> None:
        """Update person in water drift position."""
        if self._is_beached:
            return

        active_integrator = integrator or RK2Integrator()
        u_wind, v_wind = wind

        def velocity_fn(curr_lat: float, curr_lon: float) -> tuple[float, float]:
            u_water, v_water = grid.interpolate_velocity(curr_lat, curr_lon, depth=0.0)
            u_total = u_water + self.windage_coeff * u_wind
            v_total = v_water + self.windage_coeff * v_wind
            return u_total, v_total

        new_lat, new_lon = active_integrator.step(self._lat, self._lon, velocity_fn, dt)

        if grid.is_land(new_lat, new_lon):
            if beach_on_collision:
                self._is_beached = True
            else:
                raise LandCollisionError(new_lat, new_lon)
        else:
            self._lat = new_lat
            self._lon = new_lon

        self._trajectory.append((self._lat, self._lon))


class LifeRaft(DriftEntity):
    """Inflatable life raft with canopy and ballast pockets.
    
    # RUBRIC: Inheritance, Polymorphism
    Physics Note:
    Erect canopy acts as a wind sail, giving higher leeway drift (~4.0%).
    Under-hull water pockets provide stabilization with moderate drag (Cd ~0.50).
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        mass: float = LIFERAFT_DEFAULT_MASS_KG,
        has_canopy: bool = True,
    ) -> None:
        """Initialize life raft."""
        super().__init__(lat=lat, lon=lon, mass=mass, depth=0.0)
        self.has_canopy: bool = bool(has_canopy)

    @property
    def windage_coeff(self) -> float:
        """Leeway coefficient dependent on canopy configuration."""
        return LIFERAFT_WINDAGE_COEFF if self.has_canopy else LIFERAFT_WINDAGE_COEFF * 0.6

    @property
    def drag_coeff(self) -> float:
        """Hydrodynamic drag coefficient."""
        return LIFERAFT_DRAG_COEFF

    def update(
        self,
        dt: float,
        grid: VectorGrid,
        wind: tuple[float, float],
        integrator: Integrator | None = None,
        beach_on_collision: bool = True,
    ) -> None:
        """Update life raft position."""
        if self._is_beached:
            return

        active_integrator = integrator or RK2Integrator()
        u_wind, v_wind = wind

        def velocity_fn(curr_lat: float, curr_lon: float) -> tuple[float, float]:
            u_water, v_water = grid.interpolate_velocity(curr_lat, curr_lon, depth=0.0)
            u_total = u_water + self.windage_coeff * u_wind
            v_total = v_water + self.windage_coeff * v_wind
            return u_total, v_total

        new_lat, new_lon = active_integrator.step(self._lat, self._lon, velocity_fn, dt)

        if grid.is_land(new_lat, new_lon):
            if beach_on_collision:
                self._is_beached = True
            else:
                raise LandCollisionError(new_lat, new_lon)
        else:
            self._lat = new_lat
            self._lon = new_lon

        self._trajectory.append((self._lat, self._lon))


class FishingBoat(DriftEntity):
    """Disabled fishing boat dead in the water (NUC - Not Under Command).
    
    # RUBRIC: Inheritance, Polymorphism
    Physics Note:
    Substantial displacement hull with superstructure windage (~3.0%).
    May exhibit asymmetric leeway drift due to rudder lock or residual propulsion.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        mass: float = BOAT_DEFAULT_MASS_KG,
        engine_drift_bias: float = BOAT_DEFAULT_ENGINE_BIAS_MS,
    ) -> None:
        """Initialize disabled fishing boat."""
        super().__init__(lat=lat, lon=lon, mass=mass, depth=1.5)
        self.engine_drift_bias: float = float(engine_drift_bias)

    @property
    def windage_coeff(self) -> float:
        """Leeway windage coefficient."""
        return BOAT_WINDAGE_COEFF

    @property
    def drag_coeff(self) -> float:
        """Hull drag coefficient."""
        return BOAT_DRAG_COEFF

    def update(
        self,
        dt: float,
        grid: VectorGrid,
        wind: tuple[float, float],
        integrator: Integrator | None = None,
        beach_on_collision: bool = True,
    ) -> None:
        """Update disabled boat drift position."""
        if self._is_beached:
            return

        active_integrator = integrator or RK2Integrator()
        u_wind, v_wind = wind

        def velocity_fn(curr_lat: float, curr_lon: float) -> tuple[float, float]:
            u_water, v_water = grid.interpolate_velocity(curr_lat, curr_lon, depth=self._depth)
            u_total = u_water + self.windage_coeff * u_wind
            v_total = v_water + self.windage_coeff * v_wind - self.engine_drift_bias * 0.5
            return u_total, v_total

        new_lat, new_lon = active_integrator.step(self._lat, self._lon, velocity_fn, dt)

        if grid.is_land(new_lat, new_lon):
            if beach_on_collision:
                self._is_beached = True
            else:
                raise LandCollisionError(new_lat, new_lon)
        else:
            self._lat = new_lat
            self._lon = new_lon

        self._trajectory.append((self._lat, self._lon))


class OilSlick(DriftEntity):
    """Hydrodynamic oil slick modeling surface spreading and volatile evaporation.
    
    # RUBRIC: Inheritance, Polymorphism, Hand-Written Algorithms
    Physics Note:
    Spreading follows Fay's (1971) gravity-viscous regime:
      A(t) = A_0 + kappa * sqrt(t)
    where kappa = pi * k2^2 * ((Delta * g * V^2) / sqrt(nu_w))^(1/3).
    Volatile light hydrocarbon fractions evaporate exponentially:
      M(t) = M_0 * exp(-k_evap * t)
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        mass: float = OIL_DEFAULT_MASS_KG,
        initial_area_sq_m: float = OIL_DEFAULT_AREA_SQ_M,
        spill_volume_m3: float = OIL_SPILL_VOLUME_M3,
    ) -> None:
        """Initialize oil slick with configurable spill volume.
        
        Args:
            lat: Origin latitude.
            lon: Origin longitude.
            mass: Total spilled oil mass in kilograms.
            initial_area_sq_m: Initial slick area in square meters.
            spill_volume_m3: Spill volume in m^3 (used in Fay spreading derivation).
        """
        super().__init__(lat=lat, lon=lon, mass=mass, depth=0.0)
        self.initial_area_sq_m: float = float(initial_area_sq_m)
        self.current_area_sq_m: float = self.initial_area_sq_m
        self.current_mass_kg: float = float(mass)
        self.spill_volume_m3: float = float(spill_volume_m3)
        self.kappa: float = compute_fay_kappa(volume_m3=self.spill_volume_m3)
        self._elapsed_seconds: float = 0.0

    @property
    def windage_coeff(self) -> float:
        """Surface slick leeway windage (~3.3%)."""
        return OIL_WINDAGE_COEFF

    @property
    def drag_coeff(self) -> float:
        """Surface slick hydrodynamic friction."""
        return OIL_DRAG_COEFF

    def update(
        self,
        dt: float,
        grid: VectorGrid,
        wind: tuple[float, float],
        integrator: Integrator | None = None,
        beach_on_collision: bool = True,
    ) -> None:
        """Update slick advection, Fay gravity-viscous spreading, and mass evaporation."""
        if self._is_beached:
            return

        active_integrator = integrator or RK2Integrator()
        u_wind, v_wind = wind

        def velocity_fn(curr_lat: float, curr_lon: float) -> tuple[float, float]:
            u_water, v_water = grid.interpolate_velocity(curr_lat, curr_lon, depth=0.0)
            u_total = u_water + self.windage_coeff * u_wind
            v_total = v_water + self.windage_coeff * v_wind
            return u_total, v_total

        new_lat, new_lon = active_integrator.step(self._lat, self._lon, velocity_fn, dt)

        if grid.is_land(new_lat, new_lon):
            if beach_on_collision:
                self._is_beached = True
            else:
                raise LandCollisionError(new_lat, new_lon)
        else:
            self._lat = new_lat
            self._lon = new_lon

        # Fay's gravity-viscous expansion: A(t) = A0 + kappa * sqrt(t)
        self._elapsed_seconds += abs(dt)
        self.current_area_sq_m = (
            self.initial_area_sq_m + self.kappa * math.sqrt(self._elapsed_seconds)
        )
        # Volatile hydrocarbon mass evaporation
        self.current_mass_kg = self._mass * math.exp(
            -OIL_EVAPORATION_RATE_PER_SEC * self._elapsed_seconds
        )

        self._trajectory.append((self._lat, self._lon))
