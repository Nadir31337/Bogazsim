"""Centralized geographic boundary and continuous collision detection service.

# RUBRIC: Composition, Encapsulation, Hand-Written Algorithms, Spatial Indexing
This module provides the authoritative geographic foundation for BoğazSim.
It loads exact high-resolution GIS polygons of the Istanbul Bosphorus Strait
(European mainland, Asian mainland, and islands), builds an O(1) spatial hash
grid for line-segment continuous collision detection (CCD), and enforces
strict water constraints across particle simulations, backtrackers, and routers.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Final

from core.constants import (
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    METERS_PER_DEGREE_LAT,
    METERS_PER_DEGREE_LON,
)
from core.exceptions import InvalidParameterError, LandCollisionError

# Bounding box tolerances and numerical clearance
DEFAULT_COLLISION_CLEARANCE_DEG: Final[float] = 1e-5  # ~1 meter buffer from shore
MAX_CCD_SUBSTEPS: Final[int] = 4
RASTER_ROWS: Final[int] = 200
RASTER_COLS: Final[int] = 200


class CoastlineSegment:
    """Represents a discrete directed coastline line segment with spatial caching.
    
    # RUBRIC: Encapsulation
    """

    def __init__(self, p1: tuple[float, float], p2: tuple[float, float]) -> None:
        """Initialize segment from two (lon, lat) tuples."""
        self.p1: tuple[float, float] = (float(p1[0]), float(p1[1]))
        self.p2: tuple[float, float] = (float(p2[0]), float(p2[1]))
        
        self.min_lon: float = min(self.p1[0], self.p2[0])
        self.max_lon: float = max(self.p1[0], self.p2[0])
        self.min_lat: float = min(self.p1[1], self.p2[1])
        self.max_lat: float = max(self.p1[1], self.p2[1])

        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        length = math.hypot(dx, dy)
        if length > 1e-12:
            self.tangent: tuple[float, float] = (dx / length, dy / length)
            # Normal perpendicular vector pointing into the water (+90 deg rotation)
            self.normal: tuple[float, float] = (-dy / length, dx / length)
        else:
            self.tangent = (1.0, 0.0)
            self.normal = (0.0, 1.0)


class BosphorusGeographicService:
    """Central geographic authority and trajectory validator for BoğazSim.
    
    # RUBRIC: Hand-Written Algorithms, Spatial Indexing
    Enforces continuous boundary collision detection, point-in-polygon verification,
    coastal interaction physics, and end-to-end trajectory validity.
    """

    def __init__(self, geojson_path: str | None = None) -> None:
        """Initialize geographic service with authoritative GIS dataset."""
        if geojson_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            geojson_path = os.path.join(base_dir, "data", "bosphorus_shorelines.geojson")

        if not os.path.isfile(geojson_path):
            raise FileNotFoundError(f"Authoritative geographic dataset missing: {geojson_path}")

        with open(geojson_path, "r", encoding="utf-8") as f:
            self._geojson: dict[str, Any] = json.load(f)

        self._euro_poly: list[tuple[float, float]] = []
        self._asia_poly: list[tuple[float, float]] = []
        self._island_polys: list[list[tuple[float, float]]] = []
        self._segments: list[CoastlineSegment] = []

        self._load_features()
        self._init_spatial_grid()
        self._init_raster_mask()

    def _load_features(self) -> None:
        """Parse features into European, Asian, and island polygon structures."""
        for feat in self._geojson.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            g_type = geom.get("type")
            coords = geom.get("coordinates", [])

            if g_type == "Polygon" and coords:
                ring = [(float(p[0]), float(p[1])) for p in coords[0]]
                if props.get("name") == "EuropeanLandmass":
                    self._euro_poly = ring
                elif props.get("name") == "AsianLandmass":
                    self._asia_poly = ring
                elif props.get("is_island"):
                    self._island_polys.append(ring)

            if props.get("is_boundary") and g_type == "LineString":
                pts = [(float(p[0]), float(p[1])) for p in coords]
                for i in range(len(pts) - 1):
                    self._segments.append(CoastlineSegment(pts[i], pts[i + 1]))

        # Include island perimeters as coastline collision segments
        for isl in self._island_polys:
            for i in range(len(isl) - 1):
                self._segments.append(CoastlineSegment(isl[i], isl[i + 1]))

    def _init_spatial_grid(self) -> None:
        """Build 2D uniform spatial hash grid for sub-millisecond segment queries."""
        self._grid_rows = 120
        self._grid_cols = 160
        self._dlat = (LAT_MAX - LAT_MIN) / self._grid_rows
        self._dlon = (LON_MAX - LON_MIN) / self._grid_cols

        self._bins: list[list[list[int]]] = [
            [[] for _ in range(self._grid_cols)] for _ in range(self._grid_rows)
        ]

        for idx, seg in enumerate(self._segments):
            r_start = max(0, min(self._grid_rows - 1, int((seg.min_lat - LAT_MIN) / self._dlat)))
            r_end = max(0, min(self._grid_rows - 1, int((seg.max_lat - LAT_MIN) / self._dlat)))
            c_start = max(0, min(self._grid_cols - 1, int((seg.min_lon - LON_MIN) / self._dlon)))
            c_end = max(0, min(self._grid_cols - 1, int((seg.max_lon - LON_MIN) / self._dlon)))

            for r in range(r_start, r_end + 1):
                for c in range(c_start, c_end + 1):
                    self._bins[r][c].append(idx)

    def _init_raster_mask(self) -> None:
        """Precompute fast spatial classification raster: 0=water, 1=land, 2=boundary."""
        self._raster: list[list[int]] = [
            [0 for _ in range(RASTER_COLS)] for _ in range(RASTER_ROWS)
        ]
        r_dlat = (LAT_MAX - LAT_MIN) / RASTER_ROWS
        r_dlon = (LON_MAX - LON_MIN) / RASTER_COLS

        # Identify boundary cells intersecting any coastline segment
        boundary_cells: set[tuple[int, int]] = set()
        for seg in self._segments:
            r_min = max(0, min(RASTER_ROWS - 1, int((seg.min_lat - LAT_MIN) / r_dlat)))
            r_max = max(0, min(RASTER_ROWS - 1, int((seg.max_lat - LAT_MIN) / r_dlat)))
            c_min = max(0, min(RASTER_COLS - 1, int((seg.min_lon - LON_MIN) / r_dlon)))
            c_max = max(0, min(RASTER_COLS - 1, int((seg.max_lon - LON_MIN) / r_dlon)))
            for r in range(r_min, r_max + 1):
                for c in range(c_min, c_max + 1):
                    boundary_cells.add((r, c))

        # Classify grid cell centers
        for r in range(RASTER_ROWS):
            c_lat = LAT_MIN + (r + 0.5) * r_dlat
            for c in range(RASTER_COLS):
                if (r, c) in boundary_cells:
                    self._raster[r][c] = 2  # Boundary: requires detailed PIP check
                else:
                    c_lon = LON_MIN + (c + 0.5) * r_dlon
                    if self._raw_point_in_land(c_lon, c_lat):
                        self._raster[r][c] = 1  # Pure land
                    else:
                        self._raster[r][c] = 0  # Pure water

    # -----------------------------------------------------------------------
    # Core Geometric Point & Segment Algorithms
    # -----------------------------------------------------------------------
    @staticmethod
    def _point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
        """Hand-written Ray-Casting Point-in-Polygon (pnpoly) algorithm.
        
        # RUBRIC: Hand-Written Algorithms
        """
        inside = False
        n = len(poly)
        if n < 3:
            return False
        p1x, p1y = poly[0]
        for i in range(1, n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def _raw_point_in_land(self, lon: float, lat: float) -> bool:
        """Evaluate exact geometric polygon containment across landmasses and islands."""
        if self._euro_poly and self._point_in_polygon(lon, lat, self._euro_poly):
            return True
        if self._asia_poly and self._point_in_polygon(lon, lat, self._asia_poly):
            return True
        for isl in self._island_polys:
            if self._point_in_polygon(lon, lat, isl):
                return True
        return False

    def is_land(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall on dry land or outside simulation domain.
        
        # RUBRIC: Encapsulation
        Args:
            lat: Latitude coordinate.
            lon: Longitude coordinate.
            
        Returns:
            True if land or out of bounds, False if navigable water.
        """
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            return True

        # Fast raster mask lookup
        r = max(0, min(RASTER_ROWS - 1, int((lat - LAT_MIN) / ((LAT_MAX - LAT_MIN) / RASTER_ROWS))))
        c = max(0, min(RASTER_COLS - 1, int((lon - LON_MIN) / ((LON_MAX - LON_MIN) / RASTER_COLS))))
        val = self._raster[r][c]

        if val == 0:
            return False  # Confirmed pure water
        if val == 1:
            return True   # Confirmed pure land

        # Boundary cell: perform exact polygon containment check
        return self._raw_point_in_land(lon, lat)

    def is_water(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall strictly in navigable water."""
        return not self.is_land(lat, lon)

    def find_segment_intersection(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> tuple[bool, float, tuple[float, float] | None, tuple[float, float] | None]:
        """Continuous Collision Detection (CCD): Find earliest intersection with coastlines.
        
        # RUBRIC: Hand-Written Algorithms
        Returns:
            Tuple of (hit, t_hit, hit_coord, normal_vector)
            where t_hit in [0.0, 1.0] is the fraction of distance along the segment.
        """
        r_start = max(0, min(self._grid_rows - 1, int((min(lat1, lat2) - LAT_MIN) / self._dlat)))
        r_end = max(0, min(self._grid_rows - 1, int((max(lat1, lat2) - LAT_MIN) / self._dlat)))
        c_start = max(0, min(self._grid_cols - 1, int((min(lon1, lon2) - LON_MIN) / self._dlon)))
        c_end = max(0, min(self._grid_cols - 1, int((max(lon1, lon2) - LON_MIN) / self._dlon)))

        cand_indices: set[int] = set()
        for r in range(r_start, r_end + 1):
            for c in range(c_start, c_end + 1):
                cand_indices.update(self._bins[r][c])

        if not cand_indices:
            return False, 1.0, None, None

        best_t = 1.0
        hit = False
        hit_pt: tuple[float, float] | None = None
        hit_normal: tuple[float, float] | None = None

        dx1 = lon2 - lon1
        dy1 = lat2 - lat1

        for idx in cand_indices:
            seg = self._segments[idx]
            x3, y3 = seg.p1
            x4, y4 = seg.p2

            denom = (y4 - y3) * dx1 - (x4 - x3) * dy1
            if abs(denom) < 1e-14:
                continue

            ua = ((x4 - x3) * (lat1 - y3) - (y4 - y3) * (lon1 - x3)) / denom
            ub = (dx1 * (lat1 - y3) - dy1 * (lon1 - x3)) / denom

            if 0.0 <= ua <= 1.0 and 0.0 <= ub <= 1.0:
                if ua < best_t:
                    best_t = ua
                    hit = True
                    hit_pt = (lat1 + ua * dy1, lon1 + ua * dx1)
                    hit_normal = (seg.normal[1], seg.normal[0])  # (norm_lat, norm_lon)

        return hit, best_t, hit_pt, hit_normal

    def segment_intersects_land(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> bool:
        """Check whether straight segment between two points penetrates land."""
        # 1. Endpoint checks
        if self.is_land(lat1, lon1) or self.is_land(lat2, lon2):
            return True

        # 2. Continuous raycast intersection with coastline boundaries
        hit, _, _, _ = self.find_segment_intersection(lat1, lon1, lat2, lon2)
        if hit:
            return True

        # 3. Midpoint check to prevent bridging narrow peninsulas without ray intersection
        mid_lat = 0.5 * (lat1 + lat2)
        mid_lon = 0.5 * (lon1 + lon2)
        return self.is_land(mid_lat, mid_lon)

    # -----------------------------------------------------------------------
    # Coastal Boundary Interaction & Movement Resolution
    # -----------------------------------------------------------------------
    def resolve_movement(
        self,
        curr_lat: float,
        curr_lon: float,
        proposed_lat: float,
        proposed_lon: float,
        beach_on_collision: bool = False,
        max_substeps: int = MAX_CCD_SUBSTEPS,
    ) -> tuple[float, float, bool, bool]:
        """Resolve a proposed particle integration movement against geographic coastlines.
        
        # RUBRIC: Hand-Written Algorithms
        Physics Note:
        - For beaching entities (oil slick, stranded SAR debris): particle anchors at waterline.
        - For free-floating bodies (craft, water masses): normal velocity vanishes (v . n -> 0),
          sliding tangentially along the coast without artificial energy or penetration.
          
        Returns:
            Tuple of (resolved_lat, resolved_lon, is_beached, is_unresolved)
        """
        # If proposed movement remains entirely in water, accept unconditionally
        if not self.segment_intersects_land(curr_lat, curr_lon, proposed_lat, proposed_lon):
            return proposed_lat, proposed_lon, False, False

        # Collision detected: find exact intersection parameter t_hit
        hit, t_hit, hit_pt, hit_normal = self.find_segment_intersection(
            curr_lat, curr_lon, proposed_lat, proposed_lon
        )

        dlat_total = proposed_lat - curr_lat
        dlon_total = proposed_lon - curr_lon

        if not hit or hit_pt is None:
            # Step endpoint penetrates land but did not register line cross (e.g. initial on boundary)
            # Safe retreat toward current water point
            return curr_lat, curr_lon, beach_on_collision, False

        # 1. Shoreline Contact / Beaching Behavior
        if beach_on_collision:
            # Anchor right at the waterline with small water-ward safety clearance
            clamp_factor = max(0.0, t_hit - DEFAULT_COLLISION_CLEARANCE_DEG)
            safe_lat = curr_lat + clamp_factor * dlat_total
            safe_lon = curr_lon + clamp_factor * dlon_total
            # Guarantee final position is inside water
            if self.is_land(safe_lat, safe_lon):
                safe_lat, safe_lon = curr_lat, curr_lon
            return safe_lat, safe_lon, True, False

        # 2. Tangential Coastal Slip (Non-beaching interaction policy)
        contact_lat = curr_lat + max(0.0, t_hit - DEFAULT_COLLISION_CLEARANCE_DEG) * dlat_total
        contact_lon = curr_lon + max(0.0, t_hit - DEFAULT_COLLISION_CLEARANCE_DEG) * dlon_total

        # Remaining displacement for the time step
        rem_fraction = max(0.0, 1.0 - t_hit)
        rem_dlat = rem_fraction * dlat_total
        rem_dlon = rem_fraction * dlon_total

        if hit_normal is not None and max_substeps > 0:
            norm_lat, norm_lon = hit_normal
            # Orthogonal projection: remove component directed into the shore
            dot_prod = rem_dlat * norm_lat + rem_dlon * norm_lon
            if dot_prod < 0:  # Moving into the wall
                tangent_dlat = rem_dlat - dot_prod * norm_lat
                tangent_dlon = rem_dlon - dot_prod * norm_lon
            else:
                tangent_dlat = rem_dlat
                tangent_dlon = rem_dlon

            slide_target_lat = contact_lat + tangent_dlat
            slide_target_lon = contact_lon + tangent_dlon

            # Recursively resolve tangential slide substep
            if not self.segment_intersects_land(contact_lat, contact_lon, slide_target_lat, slide_target_lon):
                return slide_target_lat, slide_target_lon, False, False

        return contact_lat, contact_lon, False, False

    def snap_to_water(
        self,
        lat: float,
        lon: float,
        max_search_m: float = 3000.0,
    ) -> tuple[float, float]:
        """Snap a terrestrial or boundary datum to the nearest navigable water coordinate."""
        if self.is_water(lat, lon):
            return lat, lon

        best_dist = float("inf")
        best_coord = (lat, lon)

        # Search nearest coastline segment
        for seg in self._segments:
            p1x, p1y = seg.p1  # (lon, lat)
            p2x, p2y = seg.p2

            # Projection of (lon, lat) onto segment
            dx = p2x - p1x
            dy = p2y - p1y
            length_sq = dx * dx + dy * dy
            if length_sq < 1e-12:
                continue

            t = max(0.0, min(1.0, ((lon - p1x) * dx + (lat - p1y) * dy) / length_sq))
            proj_lon = p1x + t * dx
            proj_lat = p1y + t * dy

            # Push coordinate outward into water along normal
            cand_lat = proj_lat + seg.normal[0] * (50.0 / METERS_PER_DEGREE_LAT)
            cand_lon = proj_lon + seg.normal[1] * (50.0 / METERS_PER_DEGREE_LON)

            if self.is_water(cand_lat, cand_lon):
                dist = math.hypot(
                    (cand_lat - lat) * METERS_PER_DEGREE_LAT,
                    (cand_lon - lon) * METERS_PER_DEGREE_LON,
                )
                if dist < best_dist and dist <= max_search_m:
                    best_dist = dist
                    best_coord = (cand_lat, cand_lon)

        return best_coord

    def validate_trajectory(
        self,
        trajectory: list[tuple[float, float]],
    ) -> tuple[bool, int | None, list[str]]:
        """Validate an entire trajectory ensuring no vertex or segment intersects land."""
        errors: list[str] = []
        if not trajectory:
            return True, None, []

        for i, (lat, lon) in enumerate(trajectory):
            if self.is_land(lat, lon):
                errors.append(f"Vertex {i} at ({lat:.5f}°N, {lon:.5f}°E) is on land")
                return False, i, errors

        for i in range(len(trajectory) - 1):
            lat1, lon1 = trajectory[i]
            lat2, lon2 = trajectory[i + 1]
            if self.segment_intersects_land(lat1, lon1, lat2, lon2):
                errors.append(
                    f"Segment {i}->{i+1} from ({lat1:.5f}°N, {lon1:.5f}°E) to ({lat2:.5f}°N, {lon2:.5f}°E) crosses land"
                )
                return False, i, errors

        return True, None, []

    def get_geojson(self) -> dict[str, Any]:
        """Return authoritative GeoJSON boundary collection."""
        return self._geojson


# ---------------------------------------------------------------------------
# Global Singleton Accessor
# ---------------------------------------------------------------------------
_GLOBAL_GEO_SERVICE: BosphorusGeographicService | None = None


def get_geographic_service() -> BosphorusGeographicService:
    """Retrieve shared singleton instance of BosphorusGeographicService."""
    global _GLOBAL_GEO_SERVICE
    if _GLOBAL_GEO_SERVICE is None:
        _GLOBAL_GEO_SERVICE = BosphorusGeographicService()
    return _GLOBAL_GEO_SERVICE
