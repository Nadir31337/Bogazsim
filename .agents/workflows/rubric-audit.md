---
description: Perform comprehensive audit mapping every rubric requirement to code locations, fix gaps, and verify tests
---

# /rubric-audit Workflow

Execute this workflow whenever the user runs `/rubric-audit` or when preparing the final grading submission.

## Step 1: Scan and Trace Rubric Items
Scan the entire repository for the following core grading criteria:

### Category 1: OOP Principles
1. **Abstract Base Classes**:
   - `DriftEntity` (`abc.ABC`, `@abstractmethod` update, windage, drag)
   - `Integrator` (`abc.ABC`, `@abstractmethod` step)
2. **Inheritance & Subclasses**:
   - `PersonInWater(DriftEntity)`
   - `LifeRaft(DriftEntity)`
   - `FishingBoat(DriftEntity)`
   - `OilSlick(DriftEntity)`
3. **Polymorphism**:
   - Mixed collection updating: `for e in entities: e.update(...)`
4. **Encapsulation with `@property`**:
   - Validated getters and setters on entity and grid properties
5. **Composition**:
   - `VectorGrid` containing matrix of `FluidCell` instances
   - Simulators composed of `VectorGrid` and `Integrator`
6. **Dunder Methods**:
   - `__repr__`, `__str__`, `__len__`, `__getitem__`, `__eq__` across core classes
7. **Custom Exception Hierarchy**:
   - Base: `SimulationError`
   - Children: `LandCollisionError`, `GridBoundsError`, `WeatherAPIError`, `RouteNotFoundError`, `InvalidParameterError`

### Category 2: Hand-Written Algorithms
1. **Numerical Integrators**:
   - Hand-coded `EulerIntegrator` (1st order)
   - Hand-coded `RK2Integrator` / Midpoint (2nd order)
2. **Bilinear Spatial Interpolation**:
   - Hand-coded 2D continuous velocity interpolation on grid
3. **Monte Carlo Swarm Dynamics**:
   - Hand-coded stochastic forward simulation with Gaussian perturbations
4. **Reverse Time-Stepping (-dt)**:
   - Hand-coded backward backtrack integration
5. **Weighted A\* Search**:
   - Hand-coded priority queue A* with current penalty and admissible heuristic

### Category 3: Three Technical Domains
1. **Web Domain**:
   - FastAPI application with Pydantic v2 schemas and Jinja2 templates
   - Interactive HTML5 Canvas UI with dark maritime mission-control styling
2. **Data Analysis Domain**:
   - NumPy vector calculations and masking
   - Pandas processing pipelines (resampling, rolling averages, drift stats, CSV export)
   - Matplotlib & Seaborn dark-mode visualizations (heatmap, quiver, wind rose, KDE, route)
3. **Automation Domain**:
   - Resilient Weather API client with TTL caching and synthetic fallback
   - Automated offline pytest suite
   - Automated report asset generation script (`generate_report_assets.py`)

### Category 4: Presentation & Academic Readiness
1. **Docstring Clarity**:
   - Plain-English mathematical and physical explanations in docstrings
2. **Architecture and QA Guide**:
   - `ARCHITECTURE_AND_QA_GUIDE.md` with class explanations, demo walkthrough, and $\ge 25$ professor Q&As.

## Step 2: Compile the Audit Table
Generate or update the Rubric Compliance Table with exact references:
| Rubric Item | File Path | Class / Function | Line Range | Test Case | Status |
|---|---|---|---|---|---|

## Step 3: Identify & Remediate Gaps
If any rubric criterion is missing, incomplete, or lacks explicit test coverage:
1. Locate the file or test suite needing enhancement.
2. Implement the missing behavior or test assertion.
3. Add appropriate `# RUBRIC: <Item>` tag.

## Step 4: Run Offline Verification
Execute the test suite to guarantee zero regressions:
```bash
pytest -q
```
Verify that all tests pass without errors or warnings.
