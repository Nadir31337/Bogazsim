"""Domain-specific custom exceptions for BoğazSim.

# RUBRIC: Custom Exceptions
This module defines a structured exception hierarchy rooted at `SimulationError`.
These exceptions capture domain violations such as illegal shoreline collisions,
out-of-bounds geographic queries, external weather provider failures, impossible
vessel routes, and invalid simulation configuration parameters.
"""

from __future__ import annotations


class SimulationError(Exception):
    """Base exception for all simulation and domain runtime errors in BoğazSim.
    
    All specialized exceptions in the simulator inherit from this class,
    allowing caller modules to catch any domain exception with a single except clause.
    """

    def __init__(self, message: str) -> None:
        """Initialize base simulation error.
        
        Args:
            message: Plain-English explanation of the error condition.
        """
        super().__init__(message)
        self.message: str = message

    def __repr__(self) -> str:
        """Return unambiguous string representation."""
        return f"{self.__class__.__name__}(message={self.message!r})"

    def __str__(self) -> str:
        """Return user-facing error message."""
        return self.message


class LandCollisionError(SimulationError):
    """Raised when an entity's trajectory intersects an impassable shoreline.
    
    # RUBRIC: Custom Exceptions
    In strict collision mode, maritime vessels and drift objects cannot pass
    through dry land. When an update step lands on a non-navigable grid cell,
    this error is raised to halt integration and signal the incident location.
    """

    def __init__(self, lat: float, lon: float, message: str | None = None) -> None:
        """Initialize land collision error.
        
        Args:
            lat: Latitude coordinate where shoreline collision occurred.
            lon: Longitude coordinate where shoreline collision occurred.
            message: Optional custom message describing the collision context.
        """
        self.lat: float = float(lat)
        self.lon: float = float(lon)
        msg = message or f"Land collision detected at coordinates ({self.lat:.5f}°N, {self.lon:.5f}°E)"
        super().__init__(msg)


class GridBoundsError(SimulationError):
    """Raised when requested geographic coordinates fall outside the simulation domain.
    
    # RUBRIC: Custom Exceptions
    The Bosphorus hydrodynamic grid spans strictly between lat 40.98°N–41.25°N
    and lon 28.95°E–29.20°E. Any query outside this bounded rectangular domain
    cannot be bilinearly interpolated and triggers this exception.
    """

    def __init__(self, lat: float, lon: float, message: str | None = None) -> None:
        """Initialize grid bounds error.
        
        Args:
            lat: Latitude coordinate that violated domain boundaries.
            lon: Longitude coordinate that violated domain boundaries.
            message: Optional custom message describing the boundary violation.
        """
        self.lat: float = float(lat)
        self.lon: float = float(lon)
        msg = message or f"Coordinates ({self.lat:.5f}°N, {self.lon:.5f}°E) exceed grid domain boundaries"
        super().__init__(msg)


class WeatherAPIError(SimulationError):
    """Raised when the weather service encounters an unrecoverable failure.
    
    # RUBRIC: Custom Exceptions
    Used when external API requests fail and synthetic fallback generation
    cannot be completed, or when invalid meteorological payloads are received.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize weather API error.
        
        Args:
            message: Plain-English explanation of the weather retrieval failure.
            status_code: Optional HTTP status code returned by remote endpoint.
        """
        self.status_code: int | None = status_code
        super().__init__(message)


class RouteNotFoundError(SimulationError):
    """Raised when weighted A* pathfinding fails to discover a navigable water path.
    
    # RUBRIC: Custom Exceptions
    Occurs when the start or goal point is surrounded by impassable land,
    when opposing currents overpower the maximum vessel speed across all corridors,
    or when disconnected water basins are requested.
    """

    def __init__(
        self,
        start_coord: tuple[float, float],
        goal_coord: tuple[float, float],
        message: str | None = None,
    ) -> None:
        """Initialize route not found error.
        
        Args:
            start_coord: (lat, lon) origin coordinate.
            goal_coord: (lat, lon) target destination coordinate.
            message: Optional explanation of the routing failure.
        """
        self.start_coord: tuple[float, float] = start_coord
        self.goal_coord: tuple[float, float] = goal_coord
        msg = message or f"No navigable route found from {start_coord} to {goal_coord}"
        super().__init__(msg)


class InvalidParameterError(SimulationError):
    """Raised when an unphysical or out-of-range simulation parameter is provided.
    
    # RUBRIC: Custom Exceptions
    Enforces domain invariants such as positive particle counts, time horizons > 0,
    windage coefficients between 0.0 and 1.0, and positive vessel speeds.
    """

    def __init__(self, parameter_name: str, value: object, message: str | None = None) -> None:
        """Initialize invalid parameter error.
        
        Args:
            parameter_name: Name of the invalid configuration parameter.
            value: The invalid value that was rejected.
            message: Optional custom rejection message.
        """
        self.parameter_name: str = parameter_name
        self.value: object = value
        msg = message or f"Invalid value {value!r} for parameter '{parameter_name}'"
        super().__init__(msg)
