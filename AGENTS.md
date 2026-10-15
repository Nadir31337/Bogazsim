# AGENTS.md — BoğazSim

## 1. Project Identity
- **Name**: BoğazSim (Istanbul Bosphorus Maritime Hydrodynamics, SAR Swarm & Vessel Routing Simulator)
- **Course**: SEN4015 Advanced Programming with Python (University Senior Project)
- **Target Audience**: Course grading professor and student presenter for a 10-minute live demonstration.
- **Language & Runtime**: Python 3.11+, FastAPI, HTML5 Canvas, Tailwind CSS.

## 2. Standard Run and Test Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run local development server**: `uvicorn main:app --reload`
- **Run test suite**: `pytest -q`
- **Generate report assets**: `python generate_report_assets.py`

## 3. Allowed Libraries (Pinned in requirements.txt)
- `fastapi`
- `uvicorn`
- `pydantic`
- `jinja2`
- `numpy`
- `pandas`
- `matplotlib`
- `seaborn`
- `requests`
- `pytest`

## 4. Hard Constraints
1. **Zero Cost & Zero API Keys**: No paid services, no Google Maps/Mapbox/OpenWeatherMap tokens.
2. **Weather API**: Keyless Open-Meteo endpoint (`https://api.open-meteo.com/v1/forecast?latitude=41.0422&longitude=29.0083&current=wind_speed_10m,wind_direction_10m,surface_pressure&hourly=wind_speed_10m,wind_direction_10m&past_days=1&wind_speed_unit=ms`).
3. **Resilient Weather Client**: Catch all network failures (timeout, DNS, HTTP error, malformed JSON). Fall back to synthetic Poyraz (NE) and Lodos (SW) generator. Cache with configurable TTL (default 10 minutes). Source indicator: `live` | `cache` | `synthetic`.
4. **Offline Testing**: All pytest suites must run 100% offline using mocked network fixtures and deterministic random seeds.
5. **No Placeholders**: Zero `pass`, zero `TODO`, no stub implementations.
6. **Code Quality**: Strict type hints, informative plain-English docstrings explaining physics and mathematical formulas, functions under ~40 lines, no magic numbers outside `core/constants.py`, PEP 8.
7. **Rubric Tagging**: Explicit `# RUBRIC: <Feature>` annotations in code.

## 5. Assumptions
*Decisions and architectural choices made during setup and implementation:*
- **Grid Coordinates**: 120 rows (latitudes 40.98°N to 41.25°N) by 160 columns (longitudes 28.95°E to 29.20°E). Row 0 maps to 40.98°N (South/Marmara) and Row 119 maps to 41.25°N (North/Black Sea) with uniform spacing $\Delta \text{lat} \approx 0.00227^{\circ}$, $\Delta \text{lon} \approx 0.00156^{\circ}$.
- **Centerline Representation**: Analytical polynomial / piecewise spline of the Bosphorus strait with a narrowing constriction factor minimum at Rumeli Hisarı (~41.085°N).
- **Two-Layer Depth Threshold**: Transition interface fixed at 35 m depth between upper layer (salinity ~18 PSU, southward 1.0–2.5 m/s) and bottom layer (salinity ~38 PSU, northward 0.2–0.8 m/s counter-current).
- **Time Stepping**: Default $\Delta t = 10.0$ seconds for numerical stability in Euler and RK2 integration without exceeding CFL stability criteria ($C = u \Delta t / \Delta x < 1$).
- **Land Handling**: Entities colliding with land trigger either a beached state (velocity clamped to 0, `is_beached=True`) or raise `LandCollisionError` based on simulation parameter `beach_on_collision` (default `True` for swarms, configurable `False` for strict trajectory validation).
- **Python Environment & Wheels**: System environment is Python 3.13.0 on macOS arm64 (`/usr/local/bin/python3`). `requirements.txt` is pinned to modern packages (`numpy==2.1.3`, `pandas==2.2.3`, `matplotlib==3.9.2`, `fastapi==0.115.5`, etc.) with official arm64 wheels.
- **Oil Slick Fay Law**: Spreading area modeled in Fay's gravity-viscous regime as $A(t) = A_0 + \kappa \sqrt{t}$, where $\kappa = \pi k_2^2 \left(\frac{\Delta g V^2}{\sqrt{\nu_w}}\right)^{1/3} \approx 350.8 \text{ m}^2/\text{s}^{1/2}$ derived dynamically in code from spill volume $V = 10 \text{ m}^3$, brackish water density $\rho_w = 1015 \text{ kg/m}^3$, oil density $\rho_o = 860 \text{ kg/m}^3$, kinematic viscosity $\nu_w = 1.0 \times 10^{-6} \text{ m}^2/\text{s}$, and Fay's constant $k_2 = 1.45$.
- **A* Dimensionally Consistent Cost & Admissible Heuristic**: Edge traversal cost is defined in consistent units of seconds as $C = \frac{d}{V_{\text{ground}}} + \lambda_{\text{head}} \frac{d}{V_{\text{vessel}}} \frac{\max(0, -v_{\parallel})}{V_{\text{vessel}}}$. Impassable edges ($V_{\text{ground}} \le 0$) have infinite cost. The heuristic $h(n) = \frac{d_{\text{haversine}}(n, \text{goal})}{V_{\text{vessel\_max}} + V_{\text{current\_max}}}$ in seconds is strictly admissible ($h(n) \le c^*(n, \text{goal})$) because travel time alone along any optimal edge $\ge \frac{d}{V_{\text{max\_ground}}}$ and the fuel penalty is non-negative.
- **In-Memory Simulation State**: The FastAPI server maintains the latest forward, reverse, and routing results in memory, returning HTTP 404 with an informative message if `/api/analytics/summary` or `/api/export/csv` are requested before any simulation has been performed.
- **Lamb-Oseen Eddy Cutoff**: Coastal counter-eddies use Lamb-Oseen vortex formulation with tangential velocity $v_{\theta} = \frac{\Gamma}{2\pi r}(1 - e^{-r^2/R^2})$ truncated at $r = 2.5 R$ to ensure localized wake vortices without artificial far-field distortions.
- **Bilinear Clamping**: Spatial interpolation clamps index baselines to $[0, \text{rows}-2]$ and $[0, \text{cols}-2]$ to prevent out-of-bounds indexing at boundary margins.
- **Meteorological Wind Convention**: Wind directions indicate the compass direction from which wind arrives, mapping to drift forcing components as $u = -s \sin(\theta)$ and $v = -s \cos(\theta)$.
- **Reverse Tracker Datum Snapping & Land Handling**: A datum sighting located on land (e.g. debris washed ashore) is snapped to the nearest navigable water cell via `_snap_to_water` before launching reverse particles. Because beaching is an irreversible physical process that loses trajectory information, backtracking models the assumption that the object drifted to the shore from adjacent waters rather than calculating an exact physical reversal. During reverse time-stepping, collisions with land are not clipped silently; clamped step and particle counts are recorded and reported in the tracker result.
- **95% Confidence Ellipse Assumption**: The bivariate 95% confidence ellipse ($2.447 \sigma$) assumes an approximately Gaussian particle cloud, which serves as an operational estimate that is only approximate near irregular shorelines, constriction bottlenecks, and non-linear eddies.
- **Interactive Swarm Sizing & Benchmark**: Default swarm configuration is set to $N=100$ particles and horizon $4.0\text{ hours}$ ($\Delta t = 10\text{ s}$, 1440 steps), executing in $\approx 1.69\text{ seconds}$ for responsive interactive web performance. A stress test of $N=500$ particles for $24.0\text{ hours}$ (8640 steps, 4.32 million particle updates) executes in $\approx 15.08\text{ seconds}$ in pure Python.
- **A* Diagonal Corner-Cutting Prevention**: In 8-connectivity grid navigation, diagonal transitions from $(r_1, c_1)$ to $(r_2, c_2)$ are blocked if either orthogonal intermediate neighbor $(r_1, c_2)$ or $(r_2, c_1)$ is land, strictly preventing routes from cutting diagonally across touching shoreline corners.
- **Crabbing & Cross-Current Limitation**: Speed Over Ground along route edges projects the local current vector directly onto the vessel's heading direction, ignoring the leeway/drift angle and lateral propulsion ("crabbing") required to maintain course over ground in strong cross-currents.
- **Fuel Consumption Proxy**: Fuel expenditure is computed using an assumed nominal burn rate proportional to voyage transit time and distance in relative fuel proxy units (not calibrated to specific marine diesel engine models or AIS telemetry); fuel asymmetry therefore follows directly from transit time asymmetry rather than representing independent physical data.
- **Analytics Data Pipelines**: `SimulationDataProcessor` consumes trajectory lists from forward swarms, reverse trackers, or route waypoint lists and formats them into tidy DataFrames with metric instantaneous velocities ($u_{\text{ms}}, v_{\text{ms}}$, $\text{speed}_{\text{ms}}$) derived from an equirectangular metric projection using single-source constants `METERS_PER_DEGREE_LAT` and `METERS_PER_DEGREE_LON` from `core.constants` ($\Delta y = \Delta \text{lat} \cdot \text{METERS\_PER\_DEGREE\_LAT}$, $\Delta x = \Delta \text{lon} \cdot \text{METERS\_PER\_DEGREE\_LON}$), valid as a flat-earth approximation over the localized Bosphorus domain (~30 km extent). Forward heading is computed as a compass bearing: $\theta = \text{atan2}(\text{east\_displacement}, \text{north\_displacement})$ normalized to $[0, 360)^{\circ}$ (Due North $0^{\circ}$, East $90^{\circ}$, South $180^{\circ}$, West $270^{\circ}$). Rolling-mean variance reduction of $1/W$ assumes independent noise, and a trailing window lags by about $(W-1)/2$ steps. Trajectory resampling is adequate for plotting and transfer; calculations use the full-resolution data.
- **Headless Maritime Visualizer & Thread Safety**: `MaritimeVisualizer` utilizes thread-safe object-oriented `Figure` instances and an explicit `threading.Lock()` to prevent figure crosstalk during concurrent API requests. It avoids `pyplot` global state and contains zero hard-coded `MPLCONFIGDIR` in project code. Outputs Base64-encoded PNG strings (`data:image/png;base64,...`) for web delivery and 300-DPI PNGs for document asset generation. Features 6 charts: landing heatmap, current quiver, wind rose, bivariate spatial KDE, 1D drift-distance KDE, and route profile.
- **Istanbul Wind Rose Sectors**: Polar wind rose projection maps Istanbul's 8 traditional meteorological wind sectors (Yıldız $0^{\circ}$, Poyraz $45^{\circ}$, Gündoğusu $90^{\circ}$, Keşişleme $135^{\circ}$, Kıble $180^{\circ}$, Lodos $225^{\circ}$, Günbatısı $270^{\circ}$, Karayel $315^{\circ}$) with standard binning centered on sector azimuths.
- **Pytest Warnings Filtered**: `pytest.ini` filters `PyparsingDeprecationWarning` (triggered by Python 3.13 / pyparsing 3.2+ camelCase deprecations within matplotlib 3.9's mathtext parser) and `UserWarning` (emitted by matplotlib/seaborn layout routines on headless Agg backends). These are third-party library deprecations outside project code.
- **A* Head-Current Penalty Sensitivity**: Evaluated across $\lambda_{\text{head}} \in \{0, 0.5, 1.5, 3.0\}$:
  - *Southbound (with current)*: Distance $13.24\text{ km}$, ETA $27.05\text{ min}$ invariant across all $\lambda_{\text{head}}$ (current is favorable).
  - *Northbound (against current)*: $\lambda=0.0 \to 13.43\text{ km}, 49.21\text{ min}$; $\lambda=0.5 \to 13.47\text{ km}, 49.23\text{ min}$; $\lambda=1.5 \to 13.50\text{ km}, 49.26\text{ min}$; $\lambda=3.0 \to 13.63\text{ km}, 49.42\text{ min}$ (path hugs coastal margins to avoid high-current mid-channel throat).



