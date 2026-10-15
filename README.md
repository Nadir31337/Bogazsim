# BoğazSim — Istanbul Bosphorus SAR Swarm & Vessel Routing Simulator

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-104%20Passing%20(3.25s)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-Academic%20Capstone-lightgrey.svg)]()

> **SEN4015 Advanced Programming with Python — Capstone Project**  
> A high-performance, physics-based simulation suite and mission-control digital twin modeling Bosphorus Strait hydrodynamics, Monte Carlo search-and-rescue (SAR) swarm dispersion, backward-in-time datum backtracking, and weighted A* optimal vessel passage planning.

---

## 1. Executive Summary

The Istanbul Strait (Bosphorus) is one of the world's most hazardous and strategically vital maritime chokepoints. Spanning $30\text{ km}$ between the Black Sea and the Sea of Marmara, it features strong surface currents reaching $2.5\text{ m/s}$ ($4.86\text{ knots}$) through the narrow $700\text{m}$ Rumeli Hisarı constriction, localized coastal counter-eddies (*Girdaplar*), and dense commercial maritime traffic regulated by the International Maritime Organization (IMO) Traffic Separation Scheme (TSS).

**BoğazSim** delivers a complete, end-to-end computational maritime simulator integrating:
1. **Computational Fluid Dynamics (CFD) Spatial Grid**: A $120 \times 160$ discrete cell model capturing two-layer stratified currents, Venturi throat acceleration, and Rankine-Lamb coastal vortices with continuous 2D bilinear interpolation.
2. **Lagrangian Stochastic Swarm Simulation**: Runge-Kutta 2nd Order (RK2 Midpoint) and Explicit Euler numerical integration modeling person-in-water, life raft leeway deflection, residual rudder drag, and Fay gravity-viscous oil slick spreading with Brownian turbulent diffusion.
3. **Reverse Datum Backtracking ($- \Delta t$)**: Time-inverted numerical integration from last-known sightings, calculating $95\%$ bivariate confidence dispersion ellipses for maritime search-and-rescue (SAR) operations.
4. **Weighted A* Vessel Routing**: Graph search optimizing vessel Ground Speed (SOG) while penalizing opposing head-current drag ($\lambda_{\text{head}}$), smoothed via line-of-sight raycasting.
5. **Data Analysis Pipelines**: Pandas and NumPy data processing calculating spherical Haversine geodesic distances, rolling hydrodynamic statistics, and 300-DPI publication figures.
6. **FastAPI REST Application**: Production asynchronous REST service with 10 endpoints, Pydantic v2 schemas, custom exception mapping, AnyIO worker thread pools, and thread-safe simulation state locking.
7. **Mission-Control HTML5 Digital Twin**: High-resolution ($1400 \times 950$) interactive maritime dashboard featuring continuous analytical S-curve shorelines, 3 suspension bridges, 22 named geographic landmarks, and real-time Open-Meteo meteorological API integration with animated wind rose vector tracking.

---

## 2. Quickstart & Installation

### Prerequisites
- Python 3.11+ (Tested on Python 3.13.0, macOS arm64 / Linux x86_64)
- Modern web browser (Chrome, Safari, Edge, Firefox)

### Setup Instructions
```bash
# 1. Clone repository and navigate to workspace
git clone https://github.com/mohamednadirsaidi/Bogazsim.git
cd Bogazsim

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install pinned dependencies
pip install -r requirements.txt

# 4. Run full test suite (104 tests offline in ~3.25s)
./.venv/bin/python -m pytest -x -q

# 5. Launch FastAPI Mission-Control Server
./.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000`** in your browser to access the interactive mission-control dashboard.

### Generate 300-DPI Report Assets
```bash
# Generates all 6 dark-themed publication charts into report_assets/
./.venv/bin/python generate_report_assets.py
```

---

## 3. Grading Rubric Verification Matrix

| # | SEN4015 Rubric Domain | Implementation File & Code Symbols | Technical Description & Academic Significance |
|:---:|:---|:---|:---|
| 1 | **Object-Oriented Design & Encapsulation** | [`core/grid_engine.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/grid_engine.py#L40-L115)<br>[`core/weather_client.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/weather_client.py#L31-L87) | `FluidCell` encapsulates horizontal velocity $(u, v)$, water depth, and land masks using `@property` and setter validation preventing unphysical speeds ($> 10\text{ m/s}$). `WindClassifier` encapsulates Beaufort scale and sector categorization. |
| 2 | **Dunder Methods & Pythonic Protocols** | [`core/grid_engine.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/grid_engine.py#L115-L150)<br>[`core/entities.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/entities.py#L100-L135) | `FluidCell` and `VectorGrid` implement `__repr__`, `__getitem__`, `__len__`, and `__iter__` for clean matrix slicing and debugging string representations. |
| 3 | **Inheritance & Polymorphism** | [`core/integrators.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/integrators.py#L25-L110)<br>[`core/entities.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/entities.py#L35-L250) | Abstract base class `Integrator` with polymorphic `EulerIntegrator` and `RK2Integrator`. Abstract base `DriftEntity` subclassed by `PersonInWater`, `LifeRaft`, `FishingBoat`, and `OilSlick`. |
| 4 | **Custom Exception Hierarchy** | [`core/exceptions.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/exceptions.py#L1-L115) | Domain exception tree rooted at `BogazSimError`: `LandCollisionError`, `GridBoundsError`, `RouteNotFoundError`, `WeatherAPIError`, and `InvalidParameterError`. |
| 5 | **Zero Magic Numbers Principle** | [`core/constants.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/constants.py#L1-L261) | All physical parameters, geographic bounds, time intervals, eddy vorticities, and visual colors defined as typed `Final` constants. Zero raw literals outside constants. |
| 6 | **Bilinear Interpolation** | [`core/grid_engine.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/grid_engine.py#L350-L420) | Hand-crafted 2D bilinear interpolation sampling continuous coordinates $(x, y)$ within four enclosing grid cell nodes, guaranteeing $C^0$ velocity continuity. |
| 7 | **Numerical Integrators & CFL Compliance** | [`core/integrators.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/integrators.py#L65-L105) | Explicit Euler ($\mathcal{O}(\Delta t)$ global error) and RK2 Midpoint Scheme ($\mathcal{O}(\Delta t^2)$ error). Courant number $\mathcal{C} \approx 0.19$ keeps particles from skipping cells and ensures stability. |
| 8 | **Monte Carlo Stochastic Swarms** | [`core/simulator.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/simulator.py#L40-L210) | Simulates $N = 100\text{ to }500$ particles subject to current velocity, aerodynamic leeway deflection with Coriolis rotation ($+15^\circ$), and Brownian motion turbulent diffusion. |
| 9 | **Fay Oil Spill Spreading Model** | [`core/entities.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/entities.py#L205-L250) | Models gravity-viscous oil slick boundary growth $r(t) \propto V_0^{1/3} t^{1/4}$ with Gaussian radial dispersion over time. |
| 10 | **Reverse Datum Backtracking** | [`core/simulator.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/simulator.py#L215-L360) | Inverts time integration ($- \Delta t$) from last-known sightings, generating an upstream origin cloud with an analytical $95\%$ bivariate confidence dispersion ellipse. |
| 11 | **Weighted A* Vessel Navigation** | [`core/route_optimizer.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/core/route_optimizer.py#L1-L320) | Graph search on Moore 8-neighborhood optimizing Ground Speed ($V_{\text{ground}} = V_s + \mathbf{V}_c \cdot \hat{\mathbf{u}}$) and quadratic head-current fuel penalties ($\lambda_{\text{head}}$), smoothed via raycasting. |
| 12 | **Data Analysis & Rolling Statistics** | [`analytics/data_processor.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/analytics/data_processor.py#L1-L396) | Pandas and NumPy pipelines computing spherical Haversine geodesic distances, rolling velocity means/variances ($w = 5$), landing histograms, and particle summary metrics. |
| 13 | **Dark-Themed Publication Visualizer** | [`analytics/visualizer.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/analytics/visualizer.py#L1-L420) | Thread-safe object-oriented Matplotlib/Seaborn engine with `threading.Lock` generating Base64 web URIs and 300-DPI publication PNGs (quiver, wind rose, heatmap, KDEs, route). |
| 14 | **Web REST API Domain** | [`main.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/main.py#L1-L660) | 10 FastAPI endpoints, Pydantic v2 schemas, AnyIO worker thread pools for CPU-bound routes, thread-safe `SimulationStateManager`, and custom exception handlers. |
| 15 | **Offline Testing & Zero-Dependency ASGI** | [`tests/test_bogazsim.py`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/tests/test_bogazsim.py#L1-L760) | 104 unit tests executing 100% offline via mock weather injection and in-memory ASGI client fallback (`_ASGITestClient`) in 3.25 seconds. |
| 16 | **Mission-Control Digital Twin** | [`templates/index.html`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/templates/index.html)<br>[`static/js/dashboard.js`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/static/js/dashboard.js) | 1400x950 HTML5 Canvas rendering continuous S-curve shorelines, 3 suspension bridges, 22 landmarks, live Open-Meteo REST API poller, and interactive wind compass rose. |

---

## 4. System Architecture

```mermaid
graph TD
    Client["Mission-Control Browser Client (HTML5 Canvas / Tailwind)"]
    
    subgraph FastAPI["FastAPI Application (ASGI Server)"]
        API["REST Router (10 Endpoints)"]
        Lock["SimulationStateManager (threading.Lock)"]
        Singletons["Lazy Singletons (VectorGrid, Visualizer, Processor)"]
    end

    subgraph Physics["Computational Hydrodynamics Engine"]
        VG["VectorGrid (120x160 Cells, Bilinear Interpolation)"]
        Fwd["ForwardSwarmSimulator (RK2 / Euler Monte Carlo)"]
        Rev["ReverseTracker (Time-Inverted Datum Search)"]
        AStar["RouteOptimizer (Weighted A* Navigation)"]
        WX["WeatherAPIClient (Open-Meteo & Synthetic Fallback)"]
    end

    subgraph DataEngine["Analytics & Visualization"]
        DP["SimulationDataProcessor (Pandas / Haversine / Rolling)"]
        Vis["MaritimeVisualizer (Matplotlib Agg / Seaborn Dark)"]
    end

    Client -->|GET /api/grid, /api/weather| API
    Client -->|POST /api/simulate/forward| API
    Client -->|POST /api/simulate/reverse| API
    Client -->|POST /api/route| API
    Client -->|GET /api/analytics/chart/{name}| API
    Client -->|GET /api/export/csv| API

    API --> Lock
    API --> Singletons
    Singletons --> VG
    Singletons --> Fwd
    Singletons --> Rev
    Singletons --> AStar
    Singletons --> WX
    Singletons --> DP
    Singletons --> Vis
```

---

## 5. Physical & Mathematical Formulations

### 1. Venturi Throat Acceleration
Across a channel of variable width $W(y)$, mass conservation under shallow-water assumptions dictates:
$$V_{\text{surface}}(y) = V_{\min} + (V_{\max} - V_{\min}) \cdot \left(\frac{W_{\min}}{W(y)}\right)$$
In the Rumeli Hisarı constriction ($W_{\min} = 700\text{m}$ at $41.085^\circ\text{N}$), surface speed reaches $2.5\text{ m/s}$ ($4.86\text{ kts}$), while widening to $3500\text{m}$ at both entrances drops velocity to $1.0\text{ m/s}$.

### 2. Runge-Kutta 2nd Order (Midpoint) Numerical Integration
For particle position $\mathbf{x}(t)$ advecting with local velocity $\mathbf{V}(\mathbf{x}, t)$:
$$\mathbf{k}_1 = \mathbf{V}(\mathbf{x}_n)$$
$$\mathbf{k}_2 = \mathbf{V}\left(\mathbf{x}_n + \frac{\Delta t}{2}\mathbf{k}_1\right)$$
$$\mathbf{x}_{n+1} = \mathbf{x}_n + \Delta t \, \mathbf{k}_2$$
RK2 eliminates first-order Taylor truncation error, yielding $\mathcal{O}(\Delta t^2)$ global convergence.

### 3. Courant-Friedrichs-Lewy (CFL) Condition
$$\mathcal{C} = \frac{V_{\max} \Delta t}{\Delta x_{\min}} = \frac{2.5\text{ m/s} \times 10.0\text{ s}}{131.0\text{ m}} \approx 0.19$$
A Courant number of about 0.19 keeps particles from skipping grid cells and helps accuracy; it is not a strict stability guarantee for particle tracking.

### 4. 95% Bivariate Confidence Datum Ellipse
For $N$ backtracked terminal particle positions with spatial sample covariance $\boldsymbol{\Sigma}$:
$$\boldsymbol{\Sigma} = \frac{1}{N-1}\sum_{i=1}^N (\mathbf{p}_i - \bar{\mathbf{p}})(\mathbf{p}_i - \bar{\mathbf{p}})^T, \quad \boldsymbol{\Sigma}\mathbf{v}_i = \lambda_i \mathbf{v}_i$$
Using the $95\%$ bivariate chi-squared critical value $\chi^2_{2, 0.95} = -2\ln(0.05) \approx 5.991$:
$$a = \sqrt{5.991 \cdot \lambda_1}, \quad b = \sqrt{5.991 \cdot \lambda_2}$$

### 5. Weighted A* Head-Current Cost Function
With vessel speed through water $V_s$ and edge direction $\hat{\mathbf{u}}$:
$$V_{\text{ground}} = V_s + \mathbf{V}_{\text{current}} \cdot \hat{\mathbf{u}}$$
$$\text{Cost} = \Delta t \cdot \left(1.0 + \lambda_{\text{head}} \cdot \max\left(0, -\frac{\mathbf{V}_{\text{current}} \cdot \hat{\mathbf{u}}}{V_s}\right)^2\right), \quad \Delta t = \frac{\|\mathbf{d}\|}{V_{\text{ground}}}$$
The heuristic $h(n) = \frac{\text{Distance}_{\text{Euclidean}}(n, g)}{V_s + V_{\max}^{\text{current}}}$ is strictly admissible and consistent.

---

## 6. REST API Reference

The FastAPI application provides 10 endpoints serving JSON data, rendered HTML, Base64 charts, and dynamic CSV downloads:

| HTTP Method | Endpoint Path | Summary | Key Parameters | Success Response |
|:---:|:---|:---|:---|:---|
| `GET` | `/` | Web Dashboard | None | `200 OK` (HTML5 single-page mission control) |
| `GET` | `/api/health` | Node Health | None | `200 OK` (`status`, `uptime_seconds`, `grid_rows`, `memory_rss_mb`) |
| `GET` | `/api/weather` | Live Meteorology | `force_refresh` (bool) | `200 OK` (`speed_ms`, `direction_deg`, `sector_name`, `source`) |
| `GET` | `/api/grid` | Vector Grid Data | None | `200 OK` (`bounds`, `constriction`, `downsampled_vectors`) |
| `POST` | `/api/simulate/forward` | Forward Swarm | `ForwardSimulationRequest` | `200 OK` (`trajectories`, `beached_count`, `landing_heatmap`) |
| `POST` | `/api/simulate/reverse` | Reverse Backtrack | `ReverseSimulationRequest` | `200 OK` (`estimated_origins`, `confidence_ellipse_95_km`) |
| `POST` | `/api/route` | A* Route Planner | `RouteRequest` | `200 OK` (`waypoints`, `total_distance_km`, `eta_minutes`, `fuel_proxy`) |
| `GET` | `/api/analytics/summary` | Simulation Summary | None | `200 OK` (Aggregated statistics for most recent simulation) |
| `GET` | `/api/analytics/chart/{name}` | Base64 Chart | `name` in `[quiver, windrose, heatmap, kde, distance_kde, route]` | `200 OK` (`image_base64`, `chart_name`, `mime_type`) |
| `GET` | `/api/export/csv` | CSV Telemetry Export | None | `200 OK` (`text/csv` attachment of simulation time-series) |

---

## 7. Test Suite Execution

All 104 tests across all 12 test classes pass in **3.25 seconds** with zero external network access:

```bash
./.venv/bin/python -m pytest -x -q
```

```
TestPhase1ScaffoldAndExceptions: 8 tests -> OK in 0.00s
TestConstantsIntegrity: 8 tests          -> OK in 0.00s
TestFluidCell: 3 tests                   -> OK in 0.00s
TestVectorGrid: 7 tests                  -> OK in 0.25s
TestWeatherClient: 5 tests               -> OK in 0.25s
TestEntities: 4 tests                    -> OK in 0.13s
TestIntegrators: 1 tests                 -> OK in 0.00s
TestSimulators: 5 tests                  -> OK in 0.31s
TestRouteOptimizer: 13 tests             -> OK in 0.65s
TestSimulationDataProcessor: 10 tests    -> OK in 0.04s
TestMaritimeVisualizer: 9 tests          -> OK in 0.79s
TestFastAPIEndpoints: 31 tests           -> OK in 0.84s
=========================================================
Total time: 3.25s (104 tests passed, 0 failures, 0 errors)
```

---

## 8. Academic Defense Reference

For preparation before the professor oral examination, see the comprehensive academic defense guide:
👉 **[`ARCHITECTURE_AND_QA_GUIDE.md`](file:///Users/mohamednadirsaidi/Desktop/Bogazsim/ARCHITECTURE_AND_QA_GUIDE.md)**  
Contains **27 in-depth professor defense questions and detailed answers** spanning fluid dynamics, numerical analysis, inverse Bayesian estimation, graph optimization, and software architecture.
