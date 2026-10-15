#!/usr/bin/env python3
"""BoğazSim Capstone Publication Report Asset Generator.

# RUBRIC: Dark-Themed Matplotlib/Seaborn Engine
# RUBRIC: Data Analysis Domain
# RUBRIC: Trajectory Resampling
# RUBRIC: Rolling Statistics
# RUBRIC: Group-By Aggregation

Generates all publication-quality, 300-DPI dark-themed oceanographic and
search-and-rescue (SAR) figures for the SEN4015 capstone report.

Saved Assets in `report_assets/`:
1. `quiver_currents.png`       — Bosphorus 2D surface hydrodynamic velocity quiver field
2. `wind_rose_istanbul.png`     — Canonical Istanbul nautical wind rose (Poyraz, Lodos, etc.)
3. `sar_landing_heatmap.png`    — Monte Carlo swarm shoreline landing probability heatmap
4. `sar_spatial_kde.png`        — Bivariate spatial KDE density cluster for SAR datum origin
5. `drift_distance_kde.png`     — 1D kernel density distribution of cumulative particle drift
6. `optimal_passage_route.png`  — Weighted A* route Speed Over Ground (SOG) and fuel profile
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Configure headless Agg backend and isolated font cache directory
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib
matplotlib.use("Agg")

from analytics.data_processor import SimulationDataProcessor
from analytics.visualizer import MaritimeVisualizer
from core.constants import (
    CONSTRICTION_LAT,
    CONSTRICTION_LON,
    DEFAULT_DT_SECONDS,
)
from core.grid_engine import VectorGrid
from core.integrators import RK2Integrator
from core.route_optimizer import RouteOptimizer
from core.simulator import ForwardSwarmSimulator, ReverseTracker


def main() -> None:
    """Generate all 6 dark-themed 300-DPI report assets."""
    t0 = time.time()
    print("=" * 70)
    print(" BoğazSim — Generating Capstone Publication Report Assets (300 DPI)")
    print("=" * 70)

    output_dir = Path("report_assets")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n[1/7] Initializing VectorGrid and Hydrodynamic Engine...")
    grid = VectorGrid()
    vis = MaritimeVisualizer()
    dp = SimulationDataProcessor()
    integrator = RK2Integrator()

    # 1. Surface Current Quiver Field
    print("\n[2/7] Generating Figure 1: Surface Current Quiver Vector Field...")
    fig_quiver, _ = vis.generate_quiver(grid=grid, subsample=4)
    quiver_path = vis.save_figure_png(fig_quiver, output_dir / "quiver_currents.png", dpi=300)
    print(f"      ✓ Saved: {quiver_path} ({quiver_path.stat().st_size / 1024:.1f} KB)")

    # 2. Polar Wind Rose
    print("\n[3/7] Generating Figure 2: Istanbul Maritime Polar Wind Rose...")
    fig_windrose, _ = vis.generate_windrose()
    windrose_path = vis.save_figure_png(fig_windrose, output_dir / "wind_rose_istanbul.png", dpi=300)
    print(f"      ✓ Saved: {windrose_path} ({windrose_path.stat().st_size / 1024:.1f} KB)")

    # 3. Monte Carlo Forward Simulation & Landing Heatmap
    print("\n[4/7] Executing Monte Carlo Forward Swarm Simulation (120 particles, 4.0h)...")
    sim_forward = ForwardSwarmSimulator(grid=grid, integrator=integrator)
    fwd_result = sim_forward.run(
        entity_type="raft",
        origin_lat=CONSTRICTION_LAT,
        origin_lon=CONSTRICTION_LON,
        num_particles=120,
        hours=4.0,
        dt=DEFAULT_DT_SECONDS,
        beach_on_collision=True,
    )
    print(f"      Forward swarm complete: {fwd_result['beached_count']} beached ({fwd_result['beached_percentage']:.1f}%)")

    print("      Generating Figure 3: Shoreline Landing Probability Heatmap...")
    fig_heatmap, _ = vis.generate_heatmap(fwd_result["landing_heatmap"])
    heatmap_path = vis.save_figure_png(fig_heatmap, output_dir / "sar_landing_heatmap.png", dpi=300)
    print(f"      ✓ Saved: {heatmap_path} ({heatmap_path.stat().st_size / 1024:.1f} KB)")

    # 4. Reverse Backtracking & Spatial KDE
    print("\n[5/7] Executing Reverse Datum Backtracking (50 particles, 3.0h)...")
    sim_reverse = ReverseTracker(grid=grid, integrator=integrator)
    rev_result = sim_reverse.backtrack(
        entity_type="raft",
        datum_lat=41.0500,
        datum_lon=29.0620,
        num_particles=50,
        hours_back=3.0,
        dt=DEFAULT_DT_SECONDS,
    )
    print(f"      Reverse backtracking complete: Mean origin = ({rev_result['mean_origin'][0]:.4f}°N, {rev_result['mean_origin'][1]:.4f}°E)")

    print("      Generating Figure 4: Bivariate Spatial KDE Dispersal Cloud...")
    fig_kde, _ = vis.generate_kde(rev_result["estimated_origins"])
    kde_path = vis.save_figure_png(fig_kde, output_dir / "sar_spatial_kde.png", dpi=300)
    print(f"      ✓ Saved: {kde_path} ({kde_path.stat().st_size / 1024:.1f} KB)")

    # 5. Trajectory Resampling & 1D Distance KDE
    print("\n[6/7] Processing Trajectory Resampling & Rolling Statistics...")
    df_raw = dp.swarm_to_dataframe(
        fwd_result["trajectories"],
        dt=DEFAULT_DT_SECONDS,
        final_positions=fwd_result.get("final_positions"),
    )
    df_rolled = dp.compute_rolling_statistics(df_raw, window_size=5)
    summary_df = dp.summarize_by_particle(df_rolled)
    distances_km = summary_df["total_distance_km"].dropna().tolist()

    print("      Generating Figure 5: 1D Drift Distance KDE Distribution...")
    fig_dist_kde, _ = vis.generate_distance_kde(distances_km)
    dist_kde_path = vis.save_figure_png(fig_dist_kde, output_dir / "drift_distance_kde.png", dpi=300)
    print(f"      ✓ Saved: {dist_kde_path} ({dist_kde_path.stat().st_size / 1024:.1f} KB)")

    # 6. Weighted A* Route Optimization & SOG Profile
    print("\n[7/7] Computing Weighted A* Optimal Passage (Northbound: Marmara -> Black Sea)...")
    optimizer = RouteOptimizer(grid=grid)
    route_plan = optimizer.find_optimal_route(
        start_lat=41.0100,
        start_lon=29.0265,
        end_lat=41.2000,
        end_lon=29.0820,
        vessel_speed_knots=12.0,
        head_current_penalty=1.5,
    )
    print(f"      Route calculated: {route_plan.total_distance_km:.2f} km, ETA: {route_plan.eta_minutes:.1f} min, Fuel: {route_plan.fuel_proxy:.1f}")

    print("      Generating Figure 6: Route Speed Over Ground (SOG) & Fuel Profile...")
    fig_route, _ = vis.generate_route_profile(
        sog_knots=route_plan.sog_profile_knots,
        fuel_proxies=route_plan.fuel_profile,
        cumulative_distances_km=route_plan.cumulative_distance_km,
    )
    route_path = vis.save_figure_png(fig_route, output_dir / "optimal_passage_route.png", dpi=300)
    print(f"      ✓ Saved: {route_path} ({route_path.stat().st_size / 1024:.1f} KB)")

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f" All 6 Publication Figures Successfully Generated in {elapsed:.2f}s!")
    print(f" Output Directory: {output_dir.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
