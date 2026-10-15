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
