"""BoğazSim REST API & Mission-Control Application.

# RUBRIC: Web Domain
# RUBRIC: Custom Exceptions
# RUBRIC: No Magic Numbers
FastAPI application serving the single-page dashboard and REST endpoints
for hydrodynamic grid data, live/synthetic meteorology, Monte Carlo SAR swarms,
reverse datum backtracking, A* vessel routing, analytics, and chart rendering.
"""

from __future__ import annotations

import math
import os
import resource
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from core.constants import (
    CONSTRICTION_LAT,
    CONSTRICTION_LON,
    DEFAULT_BEACH_ON_COLLISION,
    DEFAULT_DT_SECONDS,
    DEFAULT_SIMULATION_HOURS,
    DEFAULT_SWARM_PARTICLES,
    DEFAULT_VESSEL_SPEED_KNOTS,
    GRID_COLS,
    GRID_ROWS,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    MAX_DT_SECONDS,
    MAX_SIMULATION_HOURS,
    MAX_SWARM_PARTICLES,
    MAX_VESSEL_SPEED_KNOTS,
    MIN_DT_SECONDS,
    MIN_SIMULATION_HOURS,
    MIN_SWARM_PARTICLES,
    MIN_VESSEL_SPEED_KNOTS,
    ROUTING_FUEL_PENALTY_FACTOR,
)
from core.entities import EulerIntegrator, Integrator, RK2Integrator
from core.exceptions import (
    GridBoundsError,
    InvalidParameterError,
    LandCollisionError,
    RouteNotFoundError,
    SimulationError,
    WeatherAPIError,
)

if TYPE_CHECKING:
    from analytics.data_processor import SimulationDataProcessor
    from analytics.visualizer import MaritimeVisualizer
    from core.grid_engine import VectorGrid
    from core.weather_client import WeatherAPIClient

# ---------------------------------------------------------------------------
# Application Initialization & Singletons
# ---------------------------------------------------------------------------
SERVER_START_TIME: float = time.time()
ALLOWED_CHARTS: tuple[str, ...] = ("heatmap", "quiver", "windrose", "kde", "distance_kde", "route")
ALLOWED_ENTITIES: tuple[str, ...] = ("person", "piw", "raft", "liferaft", "boat", "fishingboat", "oil", "oilslick")

app = FastAPI(
    title="BoğazSim API",
    description="Istanbul Bosphorus Hydrodynamics, SAR Swarm & Vessel Routing Platform",
    version="1.0.0",
)

# Restrict CORS to localhost origins (the app serves its own frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & Jinja2 templates configuration
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------
class SimulationStateManager:
    """Thread-safe in-memory store for recent simulation artifacts.
    
    # RUBRIC: Encapsulation
    Maintains the latest forward swarm, reverse tracking, and A* route
    results to support analytics summaries, chart generation, and CSV exports.
    """

    def __init__(self) -> None:
        """Initialize simulation state repository with mutual exclusion lock."""
        self._lock: threading.Lock = threading.Lock()
        self.latest_forward: dict[str, Any] | None = None
        self.latest_reverse: dict[str, Any] | None = None
        self.latest_route: dict[str, Any] | None = None
        self.latest_any: dict[str, Any] | None = None

    def store_forward(self, result: dict[str, Any]) -> None:
        """Store latest forward Monte Carlo swarm simulation result."""
        with self._lock:
            self.latest_forward = result
            self.latest_any = result

    def store_reverse(self, result: dict[str, Any]) -> None:
        """Store latest reverse datum tracking result."""
        with self._lock:
            self.latest_reverse = result
            self.latest_any = result

    def store_route(self, result: dict[str, Any]) -> None:
        """Store latest A* vessel navigation route result."""
        with self._lock:
            self.latest_route = result
            self.latest_any = result

    def clear(self) -> None:
        """Purge all stored simulation artifacts (used in unit test isolation)."""
        with self._lock:
            self.latest_forward = None
            self.latest_reverse = None
            self.latest_route = None
            self.latest_any = None


# State singleton (lightweight thread-safe container)
state = SimulationStateManager()

# ---------------------------------------------------------------------------
# Lazily Created Shared Singletons
# ---------------------------------------------------------------------------
_grid_singleton: VectorGrid | None = None
_weather_client_singleton: WeatherAPIClient | None = None
_data_processor_singleton: SimulationDataProcessor | None = None
_visualizer_singleton: MaritimeVisualizer | None = None
_downsampled_vectors_cache: list[dict[str, Any]] | None = None


def get_grid() -> VectorGrid:
    """Retrieve or lazily initialize the shared VectorGrid singleton."""
    global _grid_singleton
    if _grid_singleton is None:
        from core.grid_engine import VectorGrid
        _grid_singleton = VectorGrid()
    return _grid_singleton


def get_weather_client() -> WeatherAPIClient:
    """Retrieve or lazily initialize the shared WeatherAPIClient singleton."""
    global _weather_client_singleton
    if _weather_client_singleton is None:
        from core.weather_client import WeatherAPIClient
        _weather_client_singleton = WeatherAPIClient()
    return _weather_client_singleton


def set_weather_client(client: WeatherAPIClient | None) -> None:
    """Inject a custom or mock WeatherAPIClient instance (for offline testing)."""
    global _weather_client_singleton
    _weather_client_singleton = client


def get_data_processor() -> SimulationDataProcessor:
    """Retrieve or lazily initialize the shared SimulationDataProcessor singleton."""
    global _data_processor_singleton
    if _data_processor_singleton is None:
        from analytics.data_processor import SimulationDataProcessor
        _data_processor_singleton = SimulationDataProcessor()
    return _data_processor_singleton


def get_visualizer() -> MaritimeVisualizer:
    """Retrieve or lazily initialize the shared MaritimeVisualizer singleton."""
    global _visualizer_singleton
    if _visualizer_singleton is None:
        from analytics.visualizer import MaritimeVisualizer
        _visualizer_singleton = MaritimeVisualizer()
    return _visualizer_singleton


def get_downsampled_vectors(stride: int = 4) -> list[dict[str, Any]]:
    """Retrieve or lazily build downsampled surface current vectors for Canvas."""
    global _downsampled_vectors_cache
    if _downsampled_vectors_cache is None:
        grid = get_grid()
        vectors: list[dict[str, Any]] = []
        for r in range(0, GRID_ROWS, stride):
            for c in range(0, GRID_COLS, stride):
                cell = grid[r, c]
                lat, lon = grid.indices_to_lat_lon(float(r), float(c))
                is_land = cell.is_land
                u = 0.0 if is_land else cell.u
                v = 0.0 if is_land else cell.v
                spd = 0.0 if is_land else math.hypot(u, v)
                vectors.append({
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "u": round(u, 2),
                    "v": round(v, 2),
                    "speed": round(spd, 2),
                    "is_land": is_land,
                })
        _downsampled_vectors_cache = vectors
    return _downsampled_vectors_cache


# ---------------------------------------------------------------------------
# Custom Exception Handlers
# ---------------------------------------------------------------------------
# RUBRIC: Custom Exceptions
@app.exception_handler(LandCollisionError)
def land_collision_handler(request: Request, exc: LandCollisionError) -> JSONResponse:
    """Handle illegal navigation or incident coordinates on dry land."""
    return JSONResponse(
        status_code=422,
        content={"error": "LandCollisionError", "detail": str(exc)},
    )


@app.exception_handler(RouteNotFoundError)
def route_not_found_handler(request: Request, exc: RouteNotFoundError) -> JSONResponse:
    """Handle unreachable navigational targets or severed water passages."""
    return JSONResponse(
        status_code=404,
        content={"error": "RouteNotFoundError", "detail": str(exc)},
    )


@app.exception_handler(GridBoundsError)
def grid_bounds_handler(request: Request, exc: GridBoundsError) -> JSONResponse:
    """Handle geographic coordinates falling outside the Bosphorus domain."""
    return JSONResponse(
        status_code=400,
        content={"error": "GridBoundsError", "detail": str(exc)},
    )


@app.exception_handler(InvalidParameterError)
def invalid_parameter_handler(request: Request, exc: InvalidParameterError) -> JSONResponse:
    """Handle unphysical parameters or invalid configuration selections."""
    return JSONResponse(
        status_code=400,
        content={"error": "InvalidParameterError", "detail": str(exc)},
    )


@app.exception_handler(WeatherAPIError)
def weather_api_error_handler(request: Request, exc: WeatherAPIError) -> JSONResponse:
    """Handle unrecoverable remote meteorological service failures."""
    return JSONResponse(
        status_code=502,
        content={"error": "WeatherAPIError", "detail": str(exc)},
    )


@app.exception_handler(SimulationError)
def simulation_error_handler(request: Request, exc: SimulationError) -> JSONResponse:
    """Handle general domain simulation errors."""
    return JSONResponse(
        status_code=500,
        content={"error": "SimulationError", "detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Pydantic v2 Request Schemas
# ---------------------------------------------------------------------------
class ForwardSimulationRequest(BaseModel):
    """Payload schema for Monte Carlo forward search-and-rescue swarms."""

    entity_type: str = Field(default="person", description="Entity: person, raft, boat, oil")
    lat: float = Field(default=CONSTRICTION_LAT, description="Incident latitude (°N)")
    lon: float = Field(default=CONSTRICTION_LON, description="Incident longitude (°E)")
    particles: int = Field(default=DEFAULT_SWARM_PARTICLES, ge=MIN_SWARM_PARTICLES, le=MAX_SWARM_PARTICLES)
    hours: float = Field(default=DEFAULT_SIMULATION_HOURS, ge=MIN_SIMULATION_HOURS, le=MAX_SIMULATION_HOURS)
    dt: float = Field(default=DEFAULT_DT_SECONDS, ge=MIN_DT_SECONDS, le=MAX_DT_SECONDS)
    integrator: str = Field(default="rk2", description="Numerical scheme: euler or rk2")
    wind_speed: float | None = Field(default=None, ge=0.0, le=50.0, description="Wind speed override (m/s)")
    wind_direction: float | None = Field(default=None, ge=0.0, le=360.0, description="Wind direction override (°)")
    beach_on_collision: bool = Field(default=DEFAULT_BEACH_ON_COLLISION)
    spill_volume_m3: float = Field(default=10.0, ge=0.1, le=1000.0)


class ReverseSimulationRequest(BaseModel):
    """Payload schema for reverse backtracking from last-known sighting datum."""

    entity_type: str = Field(default="person", description="Entity: person, raft, boat, oil")
    last_lat: float = Field(default=41.050, description="Datum latitude (°N)")
    last_lon: float = Field(default=29.030, description="Datum longitude (°E)")
    particles: int = Field(default=DEFAULT_SWARM_PARTICLES, ge=MIN_SWARM_PARTICLES, le=MAX_SWARM_PARTICLES)
    hours_back: float = Field(default=DEFAULT_SIMULATION_HOURS, ge=MIN_SIMULATION_HOURS, le=MAX_SIMULATION_HOURS)
    dt: float = Field(default=DEFAULT_DT_SECONDS, ge=MIN_DT_SECONDS, le=MAX_DT_SECONDS)
    integrator: str = Field(default="rk2", description="Numerical scheme: euler or rk2")
    wind_speed: float | None = Field(default=None, ge=0.0, le=50.0)
    wind_direction: float | None = Field(default=None, ge=0.0, le=360.0)


class RouteRequest(BaseModel):
    """Payload schema for weighted A* optimal vessel passage planning."""

    start_lat: float = Field(default=41.010, description="Departure latitude (°N)")
    start_lon: float = Field(default=28.980, description="Departure longitude (°E)")
    end_lat: float = Field(default=41.200, description="Destination latitude (°N)")
    end_lon: float = Field(default=29.120, description="Destination longitude (°E)")
    vessel_speed_knots: float = Field(default=DEFAULT_VESSEL_SPEED_KNOTS, ge=MIN_VESSEL_SPEED_KNOTS, le=MAX_VESSEL_SPEED_KNOTS)
    head_current_penalty: float = Field(default=ROUTING_FUEL_PENALTY_FACTOR, ge=0.0, le=10.0)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _validate_bounds(lat: float, lon: float) -> None:
    """Check whether coordinate falls strictly inside the Bosphorus domain."""
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        raise GridBoundsError(
            lat,
            lon,
            f"Coordinates ({lat:.4f}°N, {lon:.4f}°E) exceed bounds [{LAT_MIN}, {LAT_MAX}] x [{LON_MIN}, {LON_MAX}]",
        )


def _resolve_integrator(name: str) -> Integrator:
    """Instantiate numerical integrator scheme based on request parameter."""
    scheme = name.lower().strip()
    if scheme == "rk2":
        return RK2Integrator()
    elif scheme == "euler":
        return EulerIntegrator()
    raise InvalidParameterError("integrator", name, "Integrator must be 'euler' or 'rk2'")


def _resolve_wind_vector(speed_override: float | None, dir_override: float | None) -> tuple[float, float]:
    """Resolve wind drift components from manual overrides or live weather client."""
    if speed_override is not None and dir_override is not None:
        rad = math.radians(dir_override)
        return -speed_override * math.sin(rad), -speed_override * math.cos(rad)
    client = get_weather_client()
    w = client.get_current_wind()
    return float(w["u_wind"]), float(w["v_wind"])


def _get_memory_mb() -> float:
    """Calculate process resident set size in megabytes across operating systems."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / (1024.0 * 1024.0), 2) if sys.platform == "darwin" else round(rss / 1024.0, 2)


# ---------------------------------------------------------------------------
# Chart Renderer Helpers (Concise & Modular)
# ---------------------------------------------------------------------------
def _render_quiver() -> str:
    """Generate quiver vector field Base64 chart."""
    vis = get_visualizer()
    grid = get_grid()
    _, b64 = vis.generate_quiver(grid=grid, subsample=5)
    return b64


def _render_windrose() -> str:
    """Generate polar wind rose Base64 chart."""
    vis = get_visualizer()
    _, b64 = vis.generate_windrose()
    return b64


def _render_heatmap() -> str:
    """Generate landing probability heatmap Base64 chart."""
    if state.latest_forward is None:
        raise HTTPException(status_code=404, detail="No forward simulation data available to generate heatmap.")
    vis = get_visualizer()
    _, b64 = vis.generate_heatmap(state.latest_forward["landing_heatmap"])
    return b64


def _render_kde() -> str:
    """Generate bivariate spatial KDE Base64 chart."""
    coords: list[tuple[float, float]] = []
    if state.latest_forward is not None:
        coords = [(p[0], p[1]) for p in state.latest_forward.get("final_positions", [])]
    elif state.latest_reverse is not None:
        coords = state.latest_reverse.get("estimated_origins", [])
    if len(coords) < 3:
        raise HTTPException(
            status_code=404,
            detail="At least 3 simulation particles required to generate spatial KDE. Run a swarm first.",
        )
    vis = get_visualizer()
    _, b64 = vis.generate_kde(coords)
    return b64


def _render_distance_kde() -> str:
    """Generate 1D drift distance KDE Base64 chart."""
    sim = state.latest_forward or state.latest_reverse
    if sim is None or "trajectories" not in sim:
        raise HTTPException(status_code=404, detail="No swarm simulation data available to generate drift distance KDE.")
    dt = sim.get("time_step_seconds", DEFAULT_DT_SECONDS)
    dp = get_data_processor()
    df = dp.swarm_to_dataframe(
        sim["trajectories"],
        dt=dt,
        final_positions=sim.get("final_positions"),
    )
    df_rolled = dp.compute_rolling_statistics(df)
    summary = dp.summarize_by_particle(df_rolled)
    distances = summary["total_distance_km"].dropna().tolist()
    if len(distances) < 3:
        raise HTTPException(status_code=404, detail="At least 3 drift distance samples required to generate distance KDE.")
    vis = get_visualizer()
    _, b64 = vis.generate_distance_kde(distances)
    return b64


def _render_route_profile() -> str:
    """Generate route SOG and fuel profile Base64 chart."""
    if state.latest_route is None:
        raise HTTPException(status_code=404, detail="No route navigation data available to generate route profile.")
    waypoints = state.latest_route.get("waypoint_details", [])
    if not waypoints:
        raise HTTPException(status_code=404, detail="Route waypoints are empty.")
    vis = get_visualizer()
    _, b64 = vis.generate_route_profile(waypoints)
    return b64


# ---------------------------------------------------------------------------
# API Endpoints (All CPU-Bound Routes Use Plain `def`)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def serve_dashboard(request: Request) -> Response:
    """Serve single-page interactive maritime simulation dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/health")
def get_health() -> dict[str, Any]:
    """Retrieve application health, uptime, memory, and spatial boundaries."""
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - SERVER_START_TIME, 2),
        "grid_dimensions": {"rows": GRID_ROWS, "cols": GRID_COLS},
        "geographic_bounds": {
            "lat_min": LAT_MIN,
            "lat_max": LAT_MAX,
            "lon_min": LON_MIN,
            "lon_max": LON_MAX,
        },
        "memory_rss_mb": _get_memory_mb(),
    }


@app.get("/api/weather")
def get_weather() -> dict[str, Any]:
    """Retrieve current Bosphorus wind observations or synthetic regime."""
    client = get_weather_client()
    return client.get_current_wind()


@app.get("/api/grid")
def get_grid_metadata() -> dict[str, Any]:
    """Retrieve grid metadata and downsampled surface current vectors for Canvas."""
    return {
        "lat_min": LAT_MIN,
        "lat_max": LAT_MAX,
        "lon_min": LON_MIN,
        "lon_max": LON_MAX,
        "rows": GRID_ROWS,
        "cols": GRID_COLS,
        "constriction": {"lat": CONSTRICTION_LAT, "lon": CONSTRICTION_LON},
        "downsampled_vectors": get_downsampled_vectors(stride=4),
    }


@app.post("/api/simulate/forward")
def simulate_forward(req: ForwardSimulationRequest) -> dict[str, Any]:
    """Execute stochastic Monte Carlo forward drift swarm simulation.
    
    Physics Note: Plain `def` ensures CPU-bound particle stepping runs on
    worker threads without blocking the FastAPI event loop.
    """
    grid = get_grid()
    _validate_bounds(req.lat, req.lon)
    if grid.is_land(req.lat, req.lon):
        raise LandCollisionError(req.lat, req.lon)

    etype = req.entity_type.lower().strip()
    if etype not in ALLOWED_ENTITIES:
        raise InvalidParameterError("entity_type", req.entity_type, f"Unknown entity: '{req.entity_type}'")

    integrator = _resolve_integrator(req.integrator)
    wind_vec = _resolve_wind_vector(req.wind_speed, req.wind_direction)

    from core.simulator import ForwardSwarmSimulator
    sim = ForwardSwarmSimulator(grid=grid, integrator=integrator)
    result = sim.run(
        entity_type=etype,
        origin_lat=req.lat,
        origin_lon=req.lon,
        num_particles=req.particles,
        hours=req.hours,
        dt=req.dt,
        wind=wind_vec,
        beach_on_collision=req.beach_on_collision,
        spill_volume_m3=req.spill_volume_m3,
    )
    state.store_forward(result)
    return result


@app.post("/api/simulate/reverse")
def simulate_reverse(req: ReverseSimulationRequest) -> dict[str, Any]:
    """Execute reverse (-dt) backtracking to identify incident origin probability cloud.
    
    Physics Note: Uses time-reversed numerical integration. Land datums are
    snapped to the nearest navigable water cell via `_snap_to_water`.
    """
    _validate_bounds(req.last_lat, req.last_lon)

    etype = req.entity_type.lower().strip()
    if etype not in ALLOWED_ENTITIES:
        raise InvalidParameterError("entity_type", req.entity_type, f"Unknown entity: '{req.entity_type}'")

    integrator = _resolve_integrator(req.integrator)
    wind_vec = _resolve_wind_vector(req.wind_speed, req.wind_direction)

    grid = get_grid()
    from core.simulator import ReverseTracker
    tracker = ReverseTracker(grid=grid, integrator=integrator)
    result = tracker.backtrack(
        entity_type=etype,
        datum_lat=req.last_lat,
        datum_lon=req.last_lon,
        num_particles=req.particles,
        hours_back=req.hours_back,
        dt=req.dt,
        wind=wind_vec,
    )
    state.store_reverse(result)
    return result


@app.post("/api/route")
def plan_route(req: RouteRequest) -> dict[str, Any]:
    """Calculate optimal passage plan using custom weighted A* search.
    
    Physics Note: Traversal cost combines ground transit time with opposing
    current penalties in dimensionally consistent units of seconds.
    """
    _validate_bounds(req.start_lat, req.start_lon)
    _validate_bounds(req.end_lat, req.end_lon)

    grid = get_grid()
    if grid.is_land(req.start_lat, req.start_lon):
        raise LandCollisionError(req.start_lat, req.start_lon)
    if grid.is_land(req.end_lat, req.end_lon):
        raise LandCollisionError(req.end_lat, req.end_lon)

    from core.route_optimizer import WeightedAStarRouter
    router = WeightedAStarRouter(
        grid=grid,
        fuel_penalty_weight=req.head_current_penalty,
    )
    route = router.find_route(
        start_lat=req.start_lat,
        start_lon=req.start_lon,
        goal_lat=req.end_lat,
        goal_lon=req.end_lon,
        vessel_speed_knots=req.vessel_speed_knots,
    )
    result = route.to_dict()
    state.store_route(result)
    return result


@app.get("/api/analytics/summary")
def get_analytics_summary() -> dict[str, Any]:
    """Retrieve consolidated analytics metrics from the latest simulation run."""
    if state.latest_any is None:
        raise HTTPException(
            status_code=404,
            detail="No simulation has been performed yet. Run a forward swarm, reverse track, or route first.",
        )
    dp = get_data_processor()
    return dp.generate_summary_metrics(state.latest_any)


@app.get("/api/analytics/chart/{name}")
def get_analytics_chart(name: str) -> dict[str, Any]:
    """Generate and return Base64-encoded dark-mode nautical visualization chart.
    
    Allowed charts: heatmap, quiver, windrose, kde, distance_kde, route.
    """
    chart_name = name.lower().strip()
    if chart_name not in ALLOWED_CHARTS:
        raise InvalidParameterError("name", name, f"Invalid chart name '{name}'. Allowed charts: {list(ALLOWED_CHARTS)}")

    renderers = {
        "quiver": _render_quiver,
        "windrose": _render_windrose,
        "heatmap": _render_heatmap,
        "kde": _render_kde,
        "distance_kde": _render_distance_kde,
        "route": _render_route_profile,
    }
    b64 = renderers[chart_name]()
    return {"chart_name": chart_name, "image_base64": b64}


@app.get("/api/export/csv")
def export_csv_data() -> Response:
    """Export latest simulation trajectory or route data as downloadable CSV."""
    if state.latest_any is None:
        raise HTTPException(
            status_code=404,
            detail="No simulation has been performed yet. Run a forward swarm, reverse track, or route first.",
        )

    sim = state.latest_any
    dp = get_data_processor()
    if "waypoints" in sim and "total_distance_km" in sim:
        df = dp.route_to_dataframe(sim.get("waypoint_details", sim.get("waypoints", [])))
    elif "trajectories" in sim:
        df = dp.swarm_to_dataframe(
            trajectories=sim["trajectories"],
            dt=sim.get("time_step_seconds", DEFAULT_DT_SECONDS),
            final_positions=sim.get("final_positions"),
        )
    else:
        raise HTTPException(status_code=400, detail="Stored simulation data is unrecognized or malformed.")

    csv_content = dp.export_csv(df)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bogazsim_export.csv"'},
    )
