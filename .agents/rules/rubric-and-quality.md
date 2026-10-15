# Grading Rubric and Code Quality Rules

This rule document defines the evaluation criteria, architectural standards, and coding conventions for BoğazSim (SEN4015). Every module and function must adhere strictly to these principles.

---

## 1. Grading Rubric Breakdown

Code comments must tag evidence of rubric fulfillment using the exact pattern: `# RUBRIC: <Criterion>`.

### Criterion 1: Object-Oriented Programming (OOP)
- **Abstract Base Classes (ABC)**:
  - `DriftEntity` in `core/entities.py` inheriting from `abc.ABC` with abstract methods: `@abstractmethod def update(...)`, `@property @abstractmethod def windage_coeff(...)`, `@property @abstractmethod def drag_coeff(...)`.
  - `Integrator` in `core/entities.py` or `core/simulator.py` with `@abstractmethod def step(...)`.
- **Inheritance & Polymorphism**:
  - Four distinct subclasses of `DriftEntity`:
    1. `PersonInWater`: High drag coefficient, low windage, vulnerable state.
    2. `LifeRaft`: Moderate drag, higher windage leeway drift ($0.035 - 0.045$).
    3. `FishingBoat`: Mixed leeway drift, residual propulsion/rudder bias option.
    4. `OilSlick`: Time-dependent hydrodynamic spreading (Fay's gravity-viscous regime) and mass evaporation rate.
  - Mixed-list polymorphism: iterating a collection `list[DriftEntity]` invoking `entity.update(...)` with heterogeneous dynamic responses.
- **Encapsulation with `@property`**:
  - Getters and setters with boundary/sanity validation on coordinates, physical properties (e.g., mass $> 0$, windage $\in [0, 1]$, latitude/longitude bounds).
- **Composition**:
  - `VectorGrid` composed of a 2D matrix of `FluidCell` objects alongside NumPy spatial arrays.
  - `ForwardSwarmSimulator` and `ReverseTracker` composed with an `Integrator` and `VectorGrid`.
- **Dunder Magic Methods**:
  - Comprehensive implementation of:
    - `__repr__`: Unambiguous developer representation for debugging.
    - `__str__`: Human-readable summary for logging.
    - `__len__`: Element count (e.g., grid cell count or swarm entity count).
    - `__getitem__`: Coordinate or index subscripting (e.g., `grid[row, col]` or `grid[lat, lon]`).
    - `__eq__`: Value equality comparison based on internal state.
- **Custom Exception Hierarchy**:
  - Base class: `SimulationError(Exception)`
  - Subclasses:
    - `LandCollisionError(SimulationError)`: Raised on illegal impassable shoreline intersection.
    - `GridBoundsError(SimulationError)`: Raised when coordinates fall outside grid domain.
    - `WeatherAPIError(SimulationError)`: Raised when weather service fails unrecoverably.
    - `RouteNotFoundError(SimulationError)`: Raised when A* cannot find a navigable water path.
    - `InvalidParameterError(SimulationError)`: Raised on bad user input or unphysical parameter.

---

### Criterion 2: Hand-Written Algorithms (No Black-Box Wrappers)
- **Numerical Integrators**:
  - Shared `Integrator` ABC.
  - `EulerIntegrator`: First-order explicit Euler ($x_{t+\Delta t} = x_t + v(x_t) \Delta t$).
  - `RK2Integrator`: Second-order Runge-Kutta / Midpoint scheme ($k_1 = v(x_t)$, $k_2 = v(x_t + \frac{1}{2}\Delta t k_1)$, $x_{t+\Delta t} = x_t + \Delta t k_2$).
- **Bilinear Spatial Interpolation**:
  - Smooth 2D spatial sampling between grid nodes for velocity components $u(y, x)$ and $v(y, x)$ without SciPy wrappers:
    $$f(x, y) \approx (1-s)(1-t)f_{00} + s(1-t)f_{10} + (1-s)t f_{01} + s t f_{11}$$
- **Monte Carlo Swarm Dynamics**:
  - Stochastically perturbed velocity fields combining water current and windage with Gaussian dispersion ($\sigma_w, \sigma_c$) to compute probability clouds.
- **Reverse Time-Stepping (-dt)**:
  - Exact time-reversed integration ($dt < 0$) with negative current and wind drift to backtrack maritime incident origins from last-known sightings.
- **Custom Weighted A\* Search**:
  - Custom priority-queue based pathfinder (`heapq` primitive allowed for min-heap priority queue, but search loop, neighbor expansion, heuristic, and edge weights are fully hand-written).
  - Cost function: Edge length divided by ground speed accounting for cross/head currents plus steering penalty.
  - Heuristic: Admissible Euclidean distance divided by maximum vessel forward speed ($h(n) \le c^*(n, \text{goal})$).

---

### Criterion 3: Three Technical Domains
1. **Web Domain**:
   - `FastAPI` application with strict `Pydantic` v2 request/response schemas.
   - `Jinja2` templating serving single-page application.
   - Interactive HTML5 Canvas dashboard with dark maritime mission-control styling.
2. **Data Analysis Domain**:
   - `NumPy` array operations for vector fields and masks.
   - `Pandas` pipelines: trajectory aggregation, resampling, rolling statistics, group-by drift summary.
   - `Matplotlib` and `Seaborn`: Dark-themed visualization charts (heatmaps, quivers, KDE, wind rose) generated as Base64 strings for UI and saved as 300-DPI PNGs for reports.
3. **Automation Domain**:
   - TTL-cached HTTP client for keyless Open-Meteo forecasts with automatic fallback to synthetic Poyraz/Lodos generator.
   - Comprehensive offline `pytest` test suite with automated assertions.
   - Automated report asset generator script (`generate_report_assets.py`).

---

### Criterion 4: Presentation & Academic Readiness
- **Plain-English Explanations**: All docstrings must explain the underlying physical principles, hydrodynamics, and mathematical formulation so an undergraduate student can explain them in an oral defense.
- **Comprehensive QA Guide**: `ARCHITECTURE_AND_QA_GUIDE.md` detailing every class, a 2-minute demo walkthrough, and $\ge 25$ potential professor questions with rigorous answers.

---

## 2. Code Quality & Formatting Rules

1. **Strict Type Annotations**:
   - Every function and method must declare complete parameter types and return type annotations.
   - Use modern standard typing (`list[T]`, `dict[K, V]`, `tuple[A, ...]`, `T | None`).
2. **Docstring Quality**:
   - Every module, class, and public method must include Google/Sphinx style docstrings.
   - Docstrings must state: Purpose, Parameters, Returns, Raises, and "Physics Note" explaining the formula.
3. **Function Length**:
   - Maximum ~40 lines per function. Decompose complex logic into clean, reusable private helpers (`_helper_name`).
4. **No Magic Numbers**:
   - Zero hardcoded numeric constants in business logic.
   - All spatial bounds, physical constants, default speeds, time steps, and colors must reside in `core/constants.py`.
5. **No Placeholders**:
   - Never commit `pass`, `...`, or `# TODO`. Every function must have working logic.
6. **Exception Handling**:
   - Never use bare `except:`. Always catch explicit exceptions.
   - Map domain exceptions to appropriate FastAPI HTTP status codes (e.g., `LandCollisionError` $\rightarrow$ 422, `RouteNotFoundError` $\rightarrow$ 404, `GridBoundsError` $\rightarrow$ 400).
7. **Clean Imports**:
   - Group imports: standard library, third-party libraries, local application modules. Sort alphabetically within groups.
