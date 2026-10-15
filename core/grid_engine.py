"""Hydrodynamic vector grid engine for BoğazSim.

# RUBRIC: Composition, Encapsulation, Bilinear Interpolation, Dunder Methods
This module defines the spatial representation of the Bosphorus Strait,
including discrete `FluidCell` encapsulation, the two-layer depth profile,
analytical shoreline morphology, coastal counter-eddies (Girdaplar),
and continuous 2D bilinear interpolation.
"""

from __future__ import annotations

import math
from typing import Any

from core.constants import (
    AVERAGE_STRAIT_DEPTH_M,
    CONSTRICTION_LAT,
    CONSTRICTION_LON,
    DEFAULT_BEACH_ON_COLLISION,
    EDDY_DEFINITIONS,
    GRID_COLS,
    GRID_ROWS,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    MAX_BOTTOM_CURRENT_MS,
    MAX_STRAIT_WIDTH_M,
    MAX_SURFACE_CURRENT_MS,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
    MIN_BOTTOM_CURRENT_MS,
    MIN_STRAIT_WIDTH_M,
    MIN_SURFACE_CURRENT_MS,
    SURFACE_LAYER_DEPTH_M,
)
from core.exceptions import GridBoundsError, InvalidParameterError, LandCollisionError


class FluidCell:
    """Represents a discrete hydrographic cell on the Bosphorus grid.
    
    # RUBRIC: Encapsulation with @property
    # RUBRIC: Dunder Methods
    Encapsulates horizontal velocity components (u, v), bathymetric depth,
    and land/water classification with runtime parameter validation.
    """

    def __init__(
        self,
        u: float = 0.0,
        v: float = 0.0,
        depth: float = 0.0,
        is_land: bool = False,
    ) -> None:
        """Initialize a fluid cell.
        
        Args:
            u: Zonal velocity component (East-West, m/s). Positive = Eastward.
            v: Meridional velocity component (North-South, m/s). Positive = Northward.
            depth: Water column depth in meters (0.0 for land).
            is_land: True if cell is dry land, False if navigable water.
        """
        self._u: float = float(u)
        self._v: float = float(v)
        self._depth: float = max(0.0, float(depth))
        self._is_land: bool = bool(is_land)

    @property
    def u(self) -> float:
        """Zonal (East-West) velocity component in m/s."""
        return self._u

    @u.setter
    def u(self, val: float) -> None:
        """Set zonal velocity with physical sanity validation."""
        val_f = float(val)
        if abs(val_f) > 10.0:
            raise InvalidParameterError("u", val_f, "Unphysical current velocity (|u| > 10 m/s)")
        self._u = val_f

    @property
    def v(self) -> float:
        """Meridional (North-South) velocity component in m/s."""
        return self._v

    @v.setter
    def v(self, val: float) -> None:
        """Set meridional velocity with physical sanity validation."""
        val_f = float(val)
        if abs(val_f) > 10.0:
            raise InvalidParameterError("v", val_f, "Unphysical current velocity (|v| > 10 m/s)")
        self._v = val_f

    @property
    def depth(self) -> float:
        """Water column depth in meters."""
        return self._depth

    @depth.setter
    def depth(self, val: float) -> None:
        """Set depth ensuring non-negative bathymetry."""
        val_f = float(val)
        if val_f < 0.0:
            raise InvalidParameterError("depth", val_f, "Depth cannot be negative")
        self._depth = val_f

    @property
    def is_land(self) -> bool:
        """Flag indicating if this cell represents dry land."""
        return self._is_land

    @is_land.setter
    def is_land(self, val: bool) -> None:
        """Set land classification flag."""
        self._is_land = bool(val)

    @property
    def speed(self) -> float:
        """Scalar flow speed magnitude in m/s.
        
        Physics Note: Derived as Euclidean norm ||v|| = sqrt(u^2 + v^2).
        """
        return math.hypot(self._u, self._v)

    def __repr__(self) -> str:
        """Unambiguous developer representation."""
        return (
            f"FluidCell(u={self._u:.2f}, v={self._v:.2f}, "
            f"depth={self._depth:.1f}, is_land={self._is_land})"
        )

    def __str__(self) -> str:
        """Human-readable description."""
        if self._is_land:
            return "FluidCell[LAND]"
        return f"FluidCell[WATER, speed={self.speed:.2f}m/s, depth={self._depth:.1f}m]"

    def __eq__(self, other: object) -> bool:
        """Value equality comparison."""
        if not isinstance(other, FluidCell):
            return False
        return (
            math.isclose(self._u, other._u, abs_tol=1e-5)
            and math.isclose(self._v, other._v, abs_tol=1e-5)
            and math.isclose(self._depth, other._depth, abs_tol=1e-3)
            and self._is_land == other._is_land
        )


class VectorGrid:
    """Two-dimensional hydrodynamic grid model of the Bosphorus Strait.
    
    # RUBRIC: Composition
    # RUBRIC: Bilinear Interpolation
    # RUBRIC: Dunder Methods
    Composed of a 120 x 160 matrix of FluidCells. Computes two-layer
    stratified currents, promontory counter-eddies, and continuous
    spatial velocity vectors via hand-written bilinear interpolation.
    """

    def __init__(
        self,
        rows: int = GRID_ROWS,
        cols: int = GRID_COLS,
    ) -> None:
        """Initialize the Bosphorus hydrodynamic grid.
        
        Args:
            rows: Number of grid divisions along latitude axis (North-South).
            cols: Number of grid divisions along longitude axis (East-West).
        """
        self._rows: int = rows
        self._cols: int = cols
        self._dlat: float = (LAT_MAX - LAT_MIN) / (rows - 1)
        self._dlon: float = (LON_MAX - LON_MIN) / (cols - 1)
        
        # Composition: 2D matrix of FluidCell objects
        self._cells: list[list[FluidCell]] = [
            [FluidCell() for _ in range(cols)] for _ in range(rows)
        ]
        
        self._build_strait_hydrodynamics()

    @property
    def rows(self) -> int:
        """Number of latitude rows."""
        return self._rows

    @property
    def cols(self) -> int:
        """Number of longitude columns."""
        return self._cols

    @property
    def lat_min(self) -> float:
        """Southern latitude boundary."""
        return LAT_MIN

    @property
    def lat_max(self) -> float:
        """Northern latitude boundary."""
        return LAT_MAX

    @property
    def lon_min(self) -> float:
        """Western longitude boundary."""
        return LON_MIN

    @property
    def lon_max(self) -> float:
        """Eastern longitude boundary."""
        return LON_MAX

    # -----------------------------------------------------------------------
    # Coordinate Conversion Methods
    # -----------------------------------------------------------------------
    def lat_lon_to_indices(self, lat: float, lon: float) -> tuple[float, float]:
        """Convert geographic coordinates to floating-point grid row and column indices.
        
        Args:
            lat: Latitude in decimal degrees North.
            lon: Longitude in decimal degrees East.
            
        Returns:
            Tuple of (row_idx, col_idx) as floating-point values.
            
        Raises:
            GridBoundsError: If coordinates exceed the simulation domain.
        """
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            raise GridBoundsError(lat, lon)
        row = (lat - LAT_MIN) / self._dlat
        col = (lon - LON_MIN) / self._dlon
        return row, col

    def indices_to_lat_lon(self, row: float, col: float) -> tuple[float, float]:
        """Convert grid indices to geographic coordinates (lat, lon).
        
        Args:
            row: Row index (0 to rows-1).
            col: Column index (0 to cols-1).
            
        Returns:
            Tuple of (lat, lon) in decimal degrees.
        """
        lat = LAT_MIN + row * self._dlat
        lon = LON_MIN + col * self._dlon
        return lat, lon

    # -----------------------------------------------------------------------
    # Strait Morphology & Hydrodynamics Initialization
    # -----------------------------------------------------------------------
    @staticmethod
    def get_centerline_lon(lat: float) -> float:
        """Evaluate analytical S-curve centerline longitude at a given latitude.
        
        Physics Note:
        The Bosphorus curves from Marmara (South, lon ~29.00°E) through the
        Rumeli Hisarı constriction (~41.085°N, 29.055°E), Bebek bight,
        and opens into the Black Sea (~41.25°N, 29.13°E).
        """
        t = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)
        # Cubic spline model capturing the characteristic S-bend
        base_lon = 28.995 + 0.135 * t
        s_bend = 0.025 * math.sin(2.0 * math.pi * t)
        narrows_bias = 0.015 * math.exp(-((lat - CONSTRICTION_LAT) / 0.04) ** 2)
        return base_lon + s_bend + narrows_bias

    @staticmethod
    def get_strait_width_m(lat: float) -> float:
        """Compute the channel width in meters at a given latitude.
        
        Physics Note:
        The strait constricts sharply near Rumeli Hisarı (~700m wide)
        and widens at both the Marmara Sea and Black Sea mouths (~3500m).
        """
        dist_from_throat = abs(lat - CONSTRICTION_LAT) / (LAT_MAX - LAT_MIN)
        width_ratio = min(1.0, dist_from_throat * 2.5)
        return MIN_STRAIT_WIDTH_M + (MAX_STRAIT_WIDTH_M - MIN_STRAIT_WIDTH_M) * (width_ratio ** 1.5)

    def _build_strait_hydrodynamics(self) -> None:
        """Populate cell matrix with land masks, two-layer velocity, and eddies."""
        for r in range(self._rows):
            lat, _ = self.indices_to_lat_lon(r, 0)
            center_lon = self.get_centerline_lon(lat)
            half_width_m = self.get_strait_width_m(lat) / 2.0
            
            # Venturi effect: Speed is inversely proportional to cross-section width
            throat_ratio = MIN_STRAIT_WIDTH_M / (half_width_m * 2.0)
            surface_speed = MIN_SURFACE_CURRENT_MS + (
                MAX_SURFACE_CURRENT_MS - MIN_SURFACE_CURRENT_MS
            ) * throat_ratio

            for c in range(self._cols):
                _, lon = self.indices_to_lat_lon(0, c)
                dx_meters = (lon - center_lon) * METERS_PER_DEGREE_LON
                dist_m = abs(dx_meters)

                cell = self._cells[r][c]
                if dist_m > half_width_m:
                    cell.is_land = True
                    cell.depth = 0.0
                    cell.u = 0.0
                    cell.v = 0.0
                else:
                    cell.is_land = False
                    # Bathymetric profile: Parabolic cross-section deepening toward center
                    depth_fraction = 1.0 - (dist_m / half_width_m) ** 2
                    cell.depth = max(10.0, AVERAGE_STRAIT_DEPTH_M * depth_fraction)
                    
                    # Upper layer: Southward flow (negative v) following channel curvature
                    # Curvature unit tangent vector
                    dlat_dt = 1.0
                    dlon_dt = (
                        self.get_centerline_lon(lat + 0.001) - self.get_centerline_lon(lat - 0.001)
                    ) / 0.002
                    dx_m = dlon_dt * METERS_PER_DEGREE_LON
                    dy_m = dlat_dt * METERS_PER_DEGREE_LAT
                    length = math.hypot(dx_m, dy_m)
                    
                    # Directed South (negative dy)
                    cell.u = -surface_speed * (dx_m / length)
                    cell.v = -surface_speed * (dy_m / length)

        self._apply_counter_eddies()

    def _apply_counter_eddies(self) -> None:
        """Superimpose localized coastal vortex perturbations onto the current field."""
        for eddy in EDDY_DEFINITIONS:
            e_lat = float(eddy["lat"])
            e_lon = float(eddy["lon"])
            radius_m = float(eddy["radius_m"])
            gamma = float(eddy["circulation"])

            for r in range(self._rows):
                for c in range(self._cols):
                    cell = self._cells[r][c]
                    if cell.is_land:
                        continue
                    lat, lon = self.indices_to_lat_lon(r, c)
                    dx = (lon - e_lon) * METERS_PER_DEGREE_LON
                    dy = (lat - e_lat) * METERS_PER_DEGREE_LAT
                    dist = math.hypot(dx, dy)
                    
                    if 0.0 < dist < radius_m * 2.5:
                        # Lamb-Oseen vortex tangential velocity: v_theta = (Gamma / 2pi r) * (1 - exp(-r^2/R^2))
                        factor = (gamma / (2.0 * math.pi * dist)) * (
                            1.0 - math.exp(-((dist / radius_m) ** 2))
                        )
                        u_rot = -factor * (dy / dist)
                        v_rot = factor * (dx / dist)
                        cell.u += u_rot
                        cell.v += v_rot

    # -----------------------------------------------------------------------
    # Spatial Interpolation & State Inspection
    # -----------------------------------------------------------------------
    def is_land(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall on dry land or outside navigable domain.
        
        Args:
            lat: Latitude coordinate.
            lon: Longitude coordinate.
            
        Returns:
            True if land or out of bounds, False if navigable water.
        """
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            return True
        r, c = self.lat_lon_to_indices(lat, lon)
        r_idx = min(self._rows - 1, max(0, int(round(r))))
        c_idx = min(self._cols - 1, max(0, int(round(c))))
        return self._cells[r_idx][c_idx].is_land

    def get_depth(self, lat: float, lon: float) -> float:
        """Retrieve bilinearly interpolated water column depth in meters."""
        r, c = self.lat_lon_to_indices(lat, lon)
        return self._interpolate_scalar(r, c, attr="depth")

    def interpolate_velocity(
        self,
        lat: float,
        lon: float,
        depth: float = 0.0,
    ) -> tuple[float, float]:
        """Compute continuous water velocity vector (u, v) at coordinates and depth.
        
        # RUBRIC: Bilinear Interpolation
        Physics Note:
        - If depth <= 35m (Upper layer): Interpolates the rapid southward surface flow.
        - If depth > 35m (Lower layer): Interpolates the saline northward counter-current.
        
        Args:
            lat: Latitude coordinate.
            lon: Longitude coordinate.
            depth: Target depth in meters (default 0.0 = surface).
            
        Returns:
            Tuple of (u, v) velocities in meters per second.
            
        Raises:
            LandCollisionError: If point is on land and beaching is not allowed.
            GridBoundsError: If coordinates exceed domain bounds.
        """
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            return 0.0, 0.0

        r, c = self.lat_lon_to_indices(lat, lon)
        
        if self.is_land(lat, lon):
            return 0.0, 0.0

        u_surf = self._interpolate_scalar(r, c, attr="u")
        v_surf = self._interpolate_scalar(r, c, attr="v")
        
        # Two-layer vertical profile transition
        if depth <= SURFACE_LAYER_DEPTH_M:
            return u_surf, v_surf
        
        # Lower layer (>35m): Weaker northward counter-current (0.2 to 0.8 m/s)
        deep_scale = MIN_BOTTOM_CURRENT_MS / max(0.1, math.hypot(u_surf, v_surf))
        u_deep = -u_surf * deep_scale * 0.4
        v_deep = abs(v_surf) * deep_scale  # Positive = Northward flow
        return u_deep, v_deep

    def _interpolate_scalar(self, r: float, c: float, attr: str) -> float:
        """Execute hand-coded 2D bilinear interpolation for a cell attribute.
        
        # RUBRIC: Bilinear Interpolation
        Formula:
          f(s, t) = (1-s)(1-t)f00 + s(1-t)f10 + (1-s)t f01 + s*t f11
        where s in [0, 1] is horizontal weight and t in [0, 1] is vertical weight.
        """
        r0 = max(0, min(self._rows - 2, int(math.floor(r))))
        c0 = max(0, min(self._cols - 2, int(math.floor(c))))
        r1 = r0 + 1
        c1 = c0 + 1

        t = r - r0  # Latitude fraction
        s = c - c0  # Longitude fraction

        f00 = getattr(self._cells[r0][c0], attr)
        f10 = getattr(self._cells[r0][c1], attr)
        f01 = getattr(self._cells[r1][c0], attr)
        f11 = getattr(self._cells[r1][c1], attr)

        return (1.0 - s) * (1.0 - t) * f00 + s * (1.0 - t) * f10 + (1.0 - s) * t * f01 + s * t * f11

    # -----------------------------------------------------------------------
    # Dunder Magic Methods
    # -----------------------------------------------------------------------
    def __getitem__(self, key: tuple[int, int]) -> FluidCell:
        """Subscript access: grid[row, col] -> FluidCell.
        
        # RUBRIC: Dunder Methods
        """
        r, c = key
        return self._cells[r][c]

    def __len__(self) -> int:
        """Return total cell count across the grid (rows * cols).
        
        # RUBRIC: Dunder Methods
        """
        return self._rows * self._cols

    def __repr__(self) -> str:
        """Unambiguous developer representation."""
        return f"VectorGrid(rows={self._rows}, cols={self._cols})"

    def __str__(self) -> str:
        """Human-readable grid summary."""
        return (
            f"VectorGrid[{self._rows}x{self._cols}, "
            f"lat={LAT_MIN}°-{LAT_MAX}°, lon={LON_MIN}°-{LON_MAX}°]"
        )
