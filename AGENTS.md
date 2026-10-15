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
