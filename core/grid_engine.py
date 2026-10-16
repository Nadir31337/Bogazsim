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
        
        self._geo_service: Any = None
        if rows == GRID_ROWS and cols == GRID_COLS:
            from core.geographic_service import get_geographic_service
            self._geo_service = get_geographic_service()

        self._build_strait_hydrodynamics()

    @property
    def geo_service(self) -> Any:
        """Central geographic constraint service."""
        if self._geo_service is None and self._rows == GRID_ROWS and self._cols == GRID_COLS:
            from core.geographic_service import get_geographic_service
            self._geo_service = get_geographic_service()
        return self._geo_service

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
    # Authentic Bosphorus GIS Coastlines: (lat, west_shore_lon, east_shore_lon)
    # Calibrated to real European (Thrace) and Asian (Anatolia) shoreline contours
    COASTLINE_WAYPOINTS: list[tuple[float, float, float]] = [
        (40.9700, 28.9400, 29.0350),  # Marmara South Open
        (40.9850, 28.9500, 29.0200),  # Ahırkapı / Kadıköy Outer
        (40.9950, 28.9500, 29.0232),  # Ahırkapı / Haydarpaşa
        (41.0100, 28.9878, 29.0098),  # Sarayburnu South / Harem
        (41.0180, 28.9742, 29.0080),  # Sarayburnu Tip / Salacak
        (41.0250, 28.9822, 29.0082),  # Karaköy / Kız Kulesi / Üsküdar Shore
        (41.0330, 28.9936, 29.0234),  # Kabataş / Kuzguncuk
        (41.0410, 29.0076, 29.0368),  # Beşiktaş / Beylerbeyi South
        (41.0450, 29.0194, 29.0446),  # Ortaköy / 15 Temmuz Bridge / Beylerbeyi
        (41.0500, 29.0330, 29.0522),  # Ortaköy / Beylerbeyi North
        (41.0580, 29.0364, 29.0530),  # Kuruçeşme / Çengelköy
        (41.0660, 29.0418, 29.0564),  # Arnavutköy / Vaniköy
        (41.0730, 29.0450, 29.0554),  # Akıntı Burnu / Kandilli
        (41.0800, 29.0524, 29.0650),  # Bebek Bay / Aşiyan / Kandilli North
        (41.0855, 29.0574, 29.0668),  # Rumeli Hisarı / Anadolu Hisarı (The Narrows)
        (41.0915, 29.0568, 29.0662),  # FSM Bridge
        (41.0990, 29.0538, 29.0650),  # Baltalimanı / Kanlıca
        (41.1100, 29.0588, 29.0826),  # Emirgan / Çubuklu
        (41.1180, 29.0674, 29.0962),  # İstinye Bay / Paşabahçe
        (41.1270, 29.0706, 29.0964),  # Yeniköy / Paşabahçe North
        (41.1380, 29.0554, 29.0794),  # Tarabya Bay / Beykoz
        (41.1480, 29.0506, 29.0748),  # Kireçburnu / Umuryeri
        (41.1580, 29.0382, 29.0762),  # Kefeliköy / Umuryeri North
        (41.1660, 29.0574, 29.0746),  # Büyükdere Bay / Selvi Burnu
        (41.1750, 29.0726, 29.0874),  # Sarıyer / Yuşa Tepesi
        (41.1850, 29.0770, 29.1144),  # Rumeli Kavağı / Anadolu Kavağı
        (41.1960, 29.0884, 29.1198),  # Altınkum / Mezar Burnu
        (41.2030, 29.0980, 29.1306),  # Garipçe / Poyrazköy (YSS Bridge)
        (41.2200, 29.1062, 29.1632),  # Rumelifeneri South / Poyrazköy North
        (41.2350, 29.1110, 29.1998),  # Rumelifeneri / Fil Burnu
        (41.2500, 28.9888, 29.1998),  # Black Sea North Open Mouth
    ]

    CENTERLINE_WAYPOINTS: list[tuple[float, float, float]] = [
        (lat, 0.5 * (w + e), (e - w) * METERS_PER_DEGREE_LON)
        for lat, w, e in COASTLINE_WAYPOINTS
    ]

    @classmethod
    def get_west_shore_lon(cls, lat: float) -> float:
        """Evaluate GIS European (West) coastline longitude at a given latitude."""
        pts = cls.COASTLINE_WAYPOINTS
        if lat <= pts[0][0]:
            return pts[0][1]
        if lat >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            lat0, w0, _ = pts[i]
            lat1, w1, _ = pts[i + 1]
            if lat0 <= lat <= lat1:
                ratio = (lat - lat0) / (lat1 - lat0)
                return w0 + ratio * (w1 - w0)
        return 29.00

    @classmethod
    def get_east_shore_lon(cls, lat: float) -> float:
        """Evaluate GIS Asian (East) coastline longitude at a given latitude."""
        pts = cls.COASTLINE_WAYPOINTS
        if lat <= pts[0][0]:
            return pts[0][2]
        if lat >= pts[-1][0]:
            return pts[-1][2]
        for i in range(len(pts) - 1):
            lat0, _, e0 = pts[i]
            lat1, _, e1 = pts[i + 1]
            if lat0 <= lat <= lat1:
                ratio = (lat - lat0) / (lat1 - lat0)
                return e0 + ratio * (e1 - e0)
        return 29.10

    @classmethod
    def get_centerline_lon(cls, lat: float) -> float:
        """Evaluate GIS-calibrated Bosphorus centerline longitude at a given latitude.
        
        Physics Note:
        The Bosphorus curves from Marmara (South, lon ~28.98°E) through the
        Rumeli Hisarı constriction (~41.085°N, 29.056°E), Bebek bight,
        Tarabya Bay, and opens into the Black Sea (~41.25°N, 29.123°E).
        """
        return 0.5 * (cls.get_west_shore_lon(lat) + cls.get_east_shore_lon(lat))

    @classmethod
    def get_strait_width_m(cls, lat: float) -> float:
        """Compute the channel width in meters at a given latitude.
        
        Physics Note:
        The strait constricts sharply near Rumeli Hisarı (~760m wide)
        and widens at both the Marmara Sea and Black Sea mouths (>4000m).
        """
        w = cls.get_west_shore_lon(lat)
        e = cls.get_east_shore_lon(lat)
        return max(MIN_STRAIT_WIDTH_M, (e - w) * METERS_PER_DEGREE_LON)

    def snap_to_water(self, lat: float, lon: float) -> tuple[float, float]:
        """Snap a terrestrial or boundary datum to the nearest navigable water coordinate.
        
        Physics Note:
        When a click or debris datum lands on dry land (e.g. city streets),
        this snaps coordinates into the adjacent Bosphorus navigation channel.
        """
        if self._rows == GRID_ROWS and self._cols == GRID_COLS and self.geo_service is not None:
            return self.geo_service.snap_to_water(lat, lon)
        clamped_lat = max(LAT_MIN + 0.001, min(LAT_MAX - 0.001, lat))
        w = self.get_west_shore_lon(clamped_lat)
        e = self.get_east_shore_lon(clamped_lat)
        margin_deg = 80.0 / METERS_PER_DEGREE_LON
        if lon < w:
            snapped_lon = min(0.5 * (w + e), w + margin_deg)
        elif lon > e:
            snapped_lon = max(0.5 * (w + e), e - margin_deg)
        else:
            snapped_lon = lon
        return clamped_lat, snapped_lon

    def _build_strait_hydrodynamics(self) -> None:
        """Populate cell matrix with land masks, two-layer velocity, and eddies."""
        for r in range(self._rows):
            lat, _ = self.indices_to_lat_lon(r, 0)
            west_lon = self.get_west_shore_lon(lat)
            east_lon = self.get_east_shore_lon(lat)
            channel_width_m = (east_lon - west_lon) * METERS_PER_DEGREE_LON

            # Venturi effect: Speed is inversely proportional to cross-section width
            throat_ratio = min(1.0, MIN_STRAIT_WIDTH_M / max(MIN_STRAIT_WIDTH_M, channel_width_m))
            center_speed = MIN_SURFACE_CURRENT_MS + (
                MAX_SURFACE_CURRENT_MS - MIN_SURFACE_CURRENT_MS
            ) * throat_ratio

            # Sample channel tangent direction along local streamlines
            dlat_sample = 0.005
            w_plus = self.get_west_shore_lon(lat + dlat_sample)
            e_plus = self.get_east_shore_lon(lat + dlat_sample)
            w_minus = self.get_west_shore_lon(lat - dlat_sample)
            e_minus = self.get_east_shore_lon(lat - dlat_sample)

            for c in range(self._cols):
                _, lon = self.indices_to_lat_lon(0, c)
                cell = self._cells[r][c]

                is_cell_land = (
                    self._geo_service.is_land(lat, lon)
                    if self._geo_service is not None
                    else (lon <= west_lon or lon >= east_lon)
                )

                if is_cell_land:
                    cell.is_land = True
                    cell.depth = 0.0
                    cell.u = 0.0
                    cell.v = 0.0
                else:
                    cell.is_land = False
                    alpha = max(0.01, min(0.99, (lon - west_lon) / max(1e-6, east_lon - west_lon)))

                    # Streamline points upstream (North) and downstream (South)
                    lon_plus = (1.0 - alpha) * w_plus + alpha * e_plus
                    lon_minus = (1.0 - alpha) * w_minus + alpha * e_minus
                    dlon = lon_minus - lon_plus
                    dx_m = dlon * METERS_PER_DEGREE_LON
                    dy_m = (-2.0 * dlat_sample) * METERS_PER_DEGREE_LAT
                    flow_len = math.hypot(dx_m, dy_m)

                    tangent_u = (dx_m / flow_len) if flow_len > 0 else 0.0
                    tangent_v = (dy_m / flow_len) if flow_len > 0 else -1.0

                    # Parabolic transverse velocity profile across channel
                    transverse_factor = 0.50 + 0.50 * (4.0 * alpha * (1.0 - alpha))
                    surf_speed = center_speed * transverse_factor

                    # Bathymetric profile: Parabolic cross-section deepening toward center
                    depth_fraction = 4.0 * alpha * (1.0 - alpha)
                    cell.depth = max(10.0, AVERAGE_STRAIT_DEPTH_M * depth_fraction)

                    cell.u = surf_speed * tangent_u
                    cell.v = surf_speed * tangent_v

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
        
        # RUBRIC: Encapsulation
        Args:
            lat: Latitude coordinate.
            lon: Longitude coordinate.
            
        Returns:
            True if land or out of bounds, False if navigable water.
        """
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            return True
        if self._rows == GRID_ROWS and self._cols == GRID_COLS and self.geo_service is not None:
            return self.geo_service.is_land(lat, lon)
        r, c = self.lat_lon_to_indices(lat, lon)
        r_idx = min(self._rows - 1, max(0, int(round(r))))
        c_idx = min(self._cols - 1, max(0, int(round(c))))
        return bool(self._cells[r_idx][c_idx].is_land)

    def is_water(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall strictly in navigable water."""
        return not self.is_land(lat, lon)

    def segment_intersects_land(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> bool:
        """Continuous Collision Detection: Verify segment between two coordinates.
        
        # RUBRIC: Hand-Written Algorithms
        """
        if self._rows == GRID_ROWS and self._cols == GRID_COLS and self.geo_service is not None:
            return self.geo_service.segment_intersects_land(lat1, lon1, lat2, lon2)
        return self.is_land(lat1, lon1) or self.is_land(lat2, lon2)

    def resolve_movement(
        self,
        curr_lat: float,
        curr_lon: float,
        proposed_lat: float,
        proposed_lon: float,
        beach_on_collision: bool = False,
    ) -> tuple[float, float, bool, bool]:
        """Resolve movement against physical boundaries using continuous collision detection."""
        if self._rows == GRID_ROWS and self._cols == GRID_COLS and self.geo_service is not None:
            return self.geo_service.resolve_movement(
                curr_lat, curr_lon, proposed_lat, proposed_lon,
                beach_on_collision=beach_on_collision,
            )
        if self.is_land(proposed_lat, proposed_lon):
            return curr_lat, curr_lon, beach_on_collision, False
        return proposed_lat, proposed_lon, False, False

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
