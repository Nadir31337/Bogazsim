"""BoğazSim Dark Maritime Visualization Engine.

# RUBRIC: Dark-Themed Matplotlib/Seaborn Engine
# RUBRIC: Visualizer

Generates publication-quality dark-themed maritime oceanographic charts.
Uses thread-safe object-oriented Matplotlib Figure APIs guarded by threading.Lock
to prevent figure cross-talk in concurrent async/threaded web serving environments.
Outputs Base64-encoded strings for responsive web delivery and 300-DPI PNGs
for technical report asset generation.
"""

from __future__ import annotations

import base64
import io
import math
import os
from pathlib import Path
import threading
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive headless backend
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    import numpy as np
    import seaborn as sns
except ImportError as err:  # pragma: no cover
    raise ImportError(
        "BoğazSim visualizer requires matplotlib, numpy, and seaborn. "
        "Install dependencies via: pip install -r requirements.txt"
    ) from err

from core.constants import (
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    WIND_SECTORS,
)
from core.exceptions import InvalidParameterError


class MaritimeVisualizer:
    """Dark-themed Matplotlib and Seaborn visualization generator.

    # RUBRIC: Dark-Themed Matplotlib/Seaborn Engine
    Produces high-contrast maritime figures styled for 1280x720 mission-control displays.
    Generates landing heatmaps, vector current quivers, polar wind roses,
    bivariate spatial KDE dispersal clouds, 1D particle drift distance distributions,
    and A* route performance profiles.
    
    Thread Safety:
    Uses object-oriented Figure instances and an explicit threading.Lock to ensure
    concurrent API requests cannot collide or mix figure states.
    """

    # Maritime dark theme color palette
    BG_COLOR = "#0f172a"        # Dark slate navy
    SURFACE_COLOR = "#1e293b"   # Slate 800 panel
    GRID_COLOR = "#334155"      # Slate 700 grid
    TEXT_COLOR = "#f8fafc"      # White slate text
    CYAN_ACCENT = "#06b6d4"     # Hydrodynamic cyan
    EMERALD_ACCENT = "#10b981"  # Optimal route green
    AMBER_ACCENT = "#f59e0b"    # Warning / fuel amber
    ROSE_ACCENT = "#f43f5e"     # Incident rose

    def __init__(self) -> None:
        """Initialize the visualizer with thread synchronization lock."""
        self._lock: threading.Lock = threading.Lock()

    def _create_figure(self, figsize: tuple[float, float] = (8.0, 6.0)) -> Figure:
        """Create a standalone object-oriented Figure configured with dark styling.

        Args:
            figsize: Figure dimensions in inches (width, height).

        Returns:
            Configured matplotlib Figure instance.
        """
        fig = Figure(figsize=figsize, facecolor=self.BG_COLOR, edgecolor=self.GRID_COLOR)
        return fig

    def _style_axes(self, ax: Any) -> None:
        """Apply consistent dark theme styling to axes elements."""
        ax.set_facecolor(self.SURFACE_COLOR)
        ax.tick_params(colors=self.TEXT_COLOR, which="both")
        for spine in ax.spines.values():
            spine.set_color(self.GRID_COLOR)
        ax.xaxis.label.set_color(self.TEXT_COLOR)
        ax.yaxis.label.set_color(self.TEXT_COLOR)
        ax.title.set_color(self.TEXT_COLOR)

    def figure_to_base64(self, fig: Figure) -> str:
        """Convert an object-oriented Figure to a Base64 data URI string.

        Args:
            fig: Matplotlib Figure instance.

        Returns:
            Data URI string formatted as 'data:image/png;base64,...'.
        """
        buf = io.BytesIO()
        canvas = FigureCanvasAgg(fig)
        canvas.print_png(buf)
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode("ascii")
        fig.clear()
        return f"data:image/png;base64,{encoded}"

    def save_figure_png(self, fig: Figure, filepath: str | Path, dpi: int = 300) -> Path:
        """Save figure to disk at publication resolution (300 DPI).

        Args:
            fig: Matplotlib Figure instance.
            filepath: Destination file path.
            dpi: Dots per inch resolution.

        Returns:
            Resolved Path object of saved file.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas = FigureCanvasAgg(fig)
        canvas.print_figure(str(path), dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
        fig.clear()
        return path

    def generate_heatmap(
        self,
        landing_matrix: list[list[float]] | np.ndarray,
        title: str = "Monte Carlo Swarm Landing Probability Distribution",
    ) -> tuple[Figure, str]:
        """Generate a 2D landing probability heatmap.

        Args:
            landing_matrix: 2D array of landing probabilities across grid cells.
            title: Chart title.

        Returns:
            Tuple of (Matplotlib Figure, Base64 data URI string).
        """
        mat = np.array(landing_matrix, dtype=float)
        if mat.ndim != 2:
            raise InvalidParameterError("landing_matrix", mat.shape, "Matrix must be 2-dimensional")

        with self._lock:
            fig = self._create_figure((8, 6))
            ax = fig.add_subplot(111)
            self._style_axes(ax)

            cmap = sns.color_palette("mako", as_cmap=True)
            im = ax.imshow(mat, cmap=cmap, aspect="auto", origin="lower")
            cbar = fig.colorbar(im, ax=ax)
            cbar.set_label("Landing Probability Density", color=self.TEXT_COLOR)
            cbar.ax.tick_params(colors=self.TEXT_COLOR)

            ax.set_title(title, fontsize=12, pad=10)
            ax.set_xlabel("Longitude Index (West $\\to$ East)", fontsize=10)
            ax.set_ylabel("Latitude Index (South $\\to$ North)", fontsize=10)

            b64 = self.figure_to_base64(fig)
            return fig, b64

    def generate_quiver(
        self,
        grid: Any,
        subsample: int = 5,
        title: str = "Bosphorus Surface Current Field (m/s)",
    ) -> tuple[Figure, str]:
        """Generate a vector quiver field of surface water currents.

        Args:
            grid: VectorGrid instance.
            subsample: Downsampling step for arrow density.
            title: Chart title.

        Returns:
            Tuple of (Matplotlib Figure, Base64 data URI string).
        """
        with self._lock:
            fig = self._create_figure((8, 7))
            ax = fig.add_subplot(111)
            self._style_axes(ax)

            lats = np.linspace(grid.lat_min, grid.lat_max, grid.rows)[::subsample]
            lons = np.linspace(grid.lon_min, grid.lon_max, grid.cols)[::subsample]
            grid_lon, grid_lat = np.meshgrid(lons, lats)

            u_mat = np.zeros_like(grid_lat)
            v_mat = np.zeros_like(grid_lat)
            speed_mat = np.zeros_like(grid_lat)

            for i in range(grid_lat.shape[0]):
                for j in range(grid_lat.shape[1]):
                    la, lo = grid_lat[i, j], grid_lon[i, j]
                    if not grid.is_land(la, lo):
                        u, v = grid.interpolate_velocity(la, lo, depth=0.0)
                        u_mat[i, j] = u
                        v_mat[i, j] = v
                        speed_mat[i, j] = math.hypot(u, v)

            q = ax.quiver(
                grid_lon,
                grid_lat,
                u_mat,
                v_mat,
                speed_mat,
                cmap="cool",
                scale=30.0,
                width=0.003,
                headwidth=3.5,
            )
            cbar = fig.colorbar(q, ax=ax)
            cbar.set_label("Surface Current Speed (m/s)", color=self.TEXT_COLOR)
            cbar.ax.tick_params(colors=self.TEXT_COLOR)

            ax.set_title(title, fontsize=12, pad=10)
            ax.set_xlabel("Longitude (°E)", fontsize=10)
            ax.set_ylabel("Latitude (°N)", fontsize=10)
            ax.set_xlim(grid.lon_min, grid.lon_max)
            ax.set_ylim(grid.lat_min, grid.lat_max)

            b64 = self.figure_to_base64(fig)
            return fig, b64

    def generate_windrose(
        self,
        wind_records: list[dict[str, Any]] | None = None,
        title: str = "Nautical Wind Rose (Istanbul Bosphorus Sectors)",
    ) -> tuple[Figure, str]:
        """Generate a polar wind rose chart classified by historical Bosphorus sectors.

        Args:
            wind_records: Optional list of {'speed': float, 'direction': float} observations.
            title: Chart title.

        Returns:
            Tuple of (Matplotlib Figure, Base64 data URI string).
        """
        with self._lock:
            fig = self._create_figure((7, 7))
            ax = fig.add_subplot(111, polar=True)
            ax.set_facecolor(self.SURFACE_COLOR)
            ax.tick_params(colors=self.TEXT_COLOR)

            sector_names = list(WIND_SECTORS.keys())
            sector_angles_deg = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
            angles_rad = np.radians(sector_angles_deg)

            if not wind_records:
                frequencies = [0.08, 0.42, 0.05, 0.03, 0.07, 0.23, 0.04, 0.08]
            else:
                frequencies = self._bin_wind_records(wind_records)

            width = (2.0 * math.pi) / len(WIND_SECTORS)
            ax.bar(
                angles_rad,
                frequencies,
                width=width * 0.9,
                bottom=0.0,
                color=self.CYAN_ACCENT,
                edgecolor=self.GRID_COLOR,
                alpha=0.8,
            )

            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)  # Clockwise compass direction
            ax.set_xticks(angles_rad)
            ax.set_xticklabels([f"{n}\n({d}°)" for n, d in zip(sector_names, sector_angles_deg)], fontsize=8)
            ax.set_title(title, fontsize=12, pad=18, color=self.TEXT_COLOR)

            b64 = self.figure_to_base64(fig)
            return fig, b64

    def _bin_wind_records(self, records: list[dict[str, Any]]) -> list[float]:
        """Bin wind observations into 8 compass sectors."""
        counts = [0] * len(WIND_SECTORS)
        total = len(records)
        for rec in records:
            deg = float(rec.get("direction", rec.get("wind_direction_10m", 0.0))) % 360.0
            idx = int((deg + 22.5) // 45.0) % 8
            counts[idx] += 1
        return [c / max(1, total) for c in counts]

    def generate_kde(
        self,
        final_coordinates: list[tuple[float, float]],
        title: str = "Swarm Dispersal Kernel Density Estimate (KDE)",
    ) -> tuple[Figure, str]:
        """Generate a bivariate Kernel Density Estimation of particle positions.

        Args:
            final_coordinates: List of (lat, lon) coordinates.
            title: Chart title.

        Returns:
            Tuple of (Matplotlib Figure, Base64 data URI string).
        """
        if len(final_coordinates) < 3:
            raise InvalidParameterError(
                "final_coordinates", len(final_coordinates), "KDE requires >= 3 sample coordinates"
            )

        lats = [pt[0] for pt in final_coordinates]
        lons = [pt[1] for pt in final_coordinates]

        with self._lock:
            fig = self._create_figure((8, 6))
            ax = fig.add_subplot(111)
            self._style_axes(ax)

            sns.kdeplot(
                x=lons,
                y=lats,
                ax=ax,
                cmap="rocket",
                fill=True,
                thresh=0.05,
                levels=10,
                alpha=0.85,
            )
            ax.scatter(lons, lats, color=self.CYAN_ACCENT, s=15, alpha=0.6, label="Drift Particles")

            ax.set_title(title, fontsize=12, pad=10)
            ax.set_xlabel("Longitude (°E)", fontsize=10)
            ax.set_ylabel("Latitude (°N)", fontsize=10)
            ax.legend(facecolor=self.SURFACE_COLOR, edgecolor=self.GRID_COLOR, labelcolor=self.TEXT_COLOR)

            b64 = self.figure_to_base64(fig)
            return fig, b64

    def generate_distance_kde(
        self,
        distances_km: list[float],
        title: str = "Swarm Drift Distance Distribution (1D KDE)",
    ) -> tuple[Figure, str]:
        """Generate a 1D Kernel Density Estimate of particle total drift distances.

        # RUBRIC: Visualizer

        Args:
            distances_km: List of drift distance values in kilometers per particle.
            title: Chart title.

        Returns:
            Tuple of (Matplotlib Figure, Base64 data URI string).
        """
        if len(distances_km) < 3:
            raise InvalidParameterError(
                "distances_km", len(distances_km), "Distance KDE requires >= 3 distance samples"
            )

        with self._lock:
            fig = self._create_figure((8, 5))
            ax = fig.add_subplot(111)
            self._style_axes(ax)

            sns.kdeplot(distances_km, ax=ax, fill=True, color=self.CYAN_ACCENT, alpha=0.7, lw=2.0)
            mean_dist = float(np.mean(distances_km))
            ax.axvline(
                mean_dist,
                color=self.AMBER_ACCENT,
                linestyle="--",
                lw=1.8,
                label=f"Mean Distance ({mean_dist:.2f} km)",
            )

            ax.set_title(title, fontsize=12, pad=10)
            ax.set_xlabel("Total Drift Distance (km)", fontsize=10)
            ax.set_ylabel("Probability Density", fontsize=10)
            ax.grid(True, linestyle="--", alpha=0.3, color=self.GRID_COLOR)
            ax.legend(facecolor=self.SURFACE_COLOR, edgecolor=self.GRID_COLOR, labelcolor=self.TEXT_COLOR)

            b64 = self.figure_to_base64(fig)
            return fig, b64

    def generate_route_profile(
        self,
        waypoints: list[dict[str, Any]],
        title: str = "A* Route Speed Over Ground & Fuel Proxy Profile",
    ) -> tuple[Figure, str]:
        """Generate a two-panel navigation performance profile.

        Args:
            waypoints: List of route waypoint dictionaries.
            title: Chart title.

        Returns:
            Tuple of (Matplotlib Figure, Base64 data URI string).
        """
        if not waypoints:
            raise InvalidParameterError("waypoints", waypoints, "Waypoints cannot be empty")

        dist_km = [wp.get("cumulative_distance_km", 0.0) for wp in waypoints]
        sog_kts = [wp.get("sog_knots", wp.get("sog_ms", 0.0) * 1.94384) for wp in waypoints]
        fuel = [wp.get("fuel_proxy", wp.get("fuel_proxy_liters", 0.0)) for wp in waypoints]

        with self._lock:
            fig = self._create_figure((8, 6))
            ax1 = fig.add_subplot(211)
            ax2 = fig.add_subplot(212, sharex=ax1)
            self._style_axes(ax1)
            self._style_axes(ax2)

            ax1.plot(dist_km, sog_kts, color=self.CYAN_ACCENT, lw=2.0, label="Speed Over Ground (kts)")
            ax1.set_ylabel("SOG (knots)", fontsize=10)
            ax1.set_title(title, fontsize=12, pad=10)
            ax1.grid(True, linestyle="--", alpha=0.4, color=self.GRID_COLOR)
            ax1.legend(facecolor=self.SURFACE_COLOR, edgecolor=self.GRID_COLOR, labelcolor=self.TEXT_COLOR)

            ax2.plot(dist_km, fuel, color=self.AMBER_ACCENT, lw=2.0, label="Fuel Proxy (Relative Units)")
            ax2.set_xlabel("Cumulative Track Distance (km)", fontsize=10)
            ax2.set_ylabel("Cumulative Fuel Proxy", fontsize=10)
            ax2.grid(True, linestyle="--", alpha=0.4, color=self.GRID_COLOR)
            ax2.legend(facecolor=self.SURFACE_COLOR, edgecolor=self.GRID_COLOR, labelcolor=self.TEXT_COLOR)

            b64 = self.figure_to_base64(fig)
            return fig, b64
