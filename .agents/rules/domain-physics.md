# Domain Physics, Data Models, Endpoints, and UI Rules

This rule document specifies the physical equations, mathematical foundations, domain entities, REST endpoints, and UI behavior for the BoğazSim maritime simulation platform.

---

## 1. Domain Physics & Mathematical Specifications

### 1.1 Geographic & Grid Domain
- **Latitude Span**: $40.98^\circ\text{N}$ (Marmara Sea entrance) to $41.25^\circ\text{N}$ (Black Sea mouth).
- **Longitude Span**: $28.95^\circ\text{E}$ (European coast) to $29.20^\circ\text{E}$ (Asian coast).
- **Spatial Resolution**: Uniform grid of $120 \text{ rows} \times 160 \text{ columns}$.
  - Grid cell size: $\Delta y \approx 250\text{ m}$, $\Delta x \approx 130\text{ m}$.
  - Coordinate transformations: Convert between `(lat, lon)` and `(row, col)` floating indices using linear mapping:
    $$\text{row} = \frac{\text{lat} - \text{lat}_{\min}}{\text{lat}_{\max} - \text{lat}_{\min}} \times (N_{\text{rows}} - 1)$$
    $$\text{col} = \frac{\text{lon} - \text{lon}_{\min}}{\text{lon}_{\max} - \text{lon}_{\min}} \times (N_{\text{cols}} - 1)$$

### 1.2 Bosphorus Strait Morphology & Land Mask
- **Analytical Centerline**: Defined as a continuous function $\text{lon}_c(\text{lat})$ capturing the S-curved geomorphology:
  - Southern reach (Seraglio Point / Sarayburnu to Üsküdar)
  - Middle narrows (Arnavutköy, Bebek, Kandilli, Rumeli Hisarı)
  - Northern reach (Beykoz, Tarabya, Sarıyer to Poyrazköy / Rumeli Feneri)
- **Width Function $W(\text{lat})$**:
  - Minimum width: $\approx 700\text{ m}$ at the Rumeli Hisarı – Anadolu Hisarı constriction ($\approx 41.085^\circ\text{N}$).
  - Maximum width: $\approx 3500\text{ m}$ at the northern and southern entrances.
- **Land Mask Formulation**:
  - Distance from cell center $(\text{lat}, \text{lon})$ to centerline $\text{lon}_c(\text{lat})$ converted to meters $d_{\perp}$.
  - Water if $d_{\perp} \le W(\text{lat}) / 2$, Land otherwise.

### 1.3 Two-Layer Stratified Hydrodynamics
1. **Upper Layer (0 to ~35m depth)**:
   - Driven by water density gradient and hydrostatic sea-level elevation difference between Black Sea (+30 cm) and Marmara Sea.
   - Low-salinity brackish water ($\approx 17-18 \text{ PSU}$) discharging southwards toward Marmara.
   - Surface speed $V_{\text{surf}} \in [1.0, 2.5]\text{ m/s}$, accelerating to peak velocity at the narrows (venturi effect: $V \propto 1/W$).
2. **Lower Layer (>35m depth)**:
   - Dense Mediterranean/Marmara saline water ($\approx 38 \text{ PSU}$) flowing northwards into the Black Sea.
   - Speed $V_{\text{bottom}} \in [0.2, 0.8]\text{ m/s}$ directed north-northeast.
3. **Coastal Counter-Eddies (Girdaplar)**:
   - Strong flow separation behind promontories produces localized recirculating vortices in bays:
     - Bebek Bay (cyclonic eddy)
     - Arnavutköy (Akıntıburnu shear zone)
     - Kandilli & Kanlıca bights
   - Mathematical model: Superimposed Gaussian vortex perturber:
     $$\mathbf{v}_{\text{eddy}}(\mathbf{r}) = \Gamma \frac{1 - e^{-\|\mathbf{r}-\mathbf{r}_0\|^2 / R_0^2}}{\|\mathbf{r}-\mathbf{r}_0\|^2} \hat{\mathbf{k}} \times (\mathbf{r} - \mathbf{r}_0)$$

### 1.4 Surface Drift & Leeway Mechanics
Floating objects move due to water currents plus direct atmospheric wind forcing:
$$\mathbf{v}_{\text{total}} = \mathbf{v}_{\text{water}} + C_{\text{windage}} \mathbf{v}_{\text{wind}} + \boldsymbol{\epsilon}$$
- $\mathbf{v}_{\text{water}}$: Bilinearly interpolated surface current at entity location.
- $\mathbf{v}_{\text{wind}}$: 10m wind velocity vector (Poyraz NE, Lodos SW, etc.).
- $C_{\text{windage}}$: Empirical leeway coefficient depending on entity freeboard and profile.
- $\boldsymbol{\epsilon} \sim \mathcal{N}(0, \sigma^2)$: Stochastic Gaussian turbulence component for Monte Carlo swarms.

### 1.5 Land Collision Handling
- If updated position $(y, x)$ falls within a land cell:
  - If `beach_on_collision=True`: Entity velocity is clamped to 0, status marked `is_beached=True`, and entity remains fixed on the shore.
  - If `beach_on_collision=False`: Raise `LandCollisionError` with detailed geographic coordinates.

---

## 2. Core Entities & Algorithms

### 2.1 DriftEntity Hierarchy (`core/entities.py`)
- `DriftEntity(ABC)`:
  - Attributes: `lat`, `lon`, `depth`, `mass`, `is_beached`, `trajectory`.
  - Properties: `windage_coeff`, `drag_coeff`.
  - Methods: `update(dt: float, grid: VectorGrid, wind: tuple[float, float]) -> None`.
- Subclasses:
  1. `PersonInWater`: $C_{\text{windage}} \approx 0.015$, high hydrodynamic drag ($C_d \approx 1.0$), low mass ($80\text{ kg}$).
  2. `LifeRaft`: $C_{\text{windage}} \approx 0.040$, moderate drag ($C_d \approx 0.5$), higher leeway deflection.
  3. `FishingBoat`: $C_{\text{windage}} \approx 0.030$, partial residual propulsion / rudder drag drift bias.
  4. `OilSlick`: $C_{\text{windage}} \approx 0.033$, models spreading area $A(t) = A_0 + \alpha t^{3/4}$ and mass loss via volatile evaporation.

### 2.2 Numerical Integration (`core/entities.py` / `core/simulator.py`)
- `EulerIntegrator`:
  $$\mathbf{x}_{t+\Delta t} = \mathbf{x}_t + \mathbf{v}(\mathbf{x}_t) \Delta t$$
- `RK2Integrator` (Midpoint Runge-Kutta):
  $$\mathbf{k}_1 = \mathbf{v}(\mathbf{x}_t)$$
  $$\mathbf{k}_2 = \mathbf{v}(\mathbf{x}_t + \frac{1}{2} \Delta t \mathbf{k}_1)$$
  $$\mathbf{x}_{t+\Delta t} = \mathbf{x}_t + \mathbf{k}_2 \Delta t$$

### 2.3 Simulators (`core/simulator.py`)
- `ForwardSwarmSimulator`:
  - Instantiates $N$ stochastic particles with randomized initial perturbations.
  - Simulates forward in time ($t = 0 \to T$).
  - Outputs time series of particle positions, beached counts, and 2D landing probability matrix.
- `ReverseTracker`:
  - Given last-known datum $(\text{lat}_0, \text{lon}_0)$ and drift elapsed time $T$, steps backward with $\Delta t < 0$.
  - Inverts current and wind forces to generate an estimated origin probability cloud.

### 2.4 Route Optimizer (`core/route_optimizer.py`)
- Weighted A* search over the water graph.
- Cost function between adjacent nodes $n_1 \to n_2$:
  $$\text{cost} = \frac{d(n_1, n_2)}{V_{\text{vessel\_ground}}} + \lambda_{\text{head}} \max(0, -\mathbf{v}_{\text{water}} \cdot \hat{\mathbf{u}})$$
  where $\hat{\mathbf{u}}$ is unit travel vector, $V_{\text{vessel\_ground}} = V_{\text{engine}} + \mathbf{v}_{\text{water}} \cdot \hat{\mathbf{u}}$.
- Admissible Heuristic:
  $$h(n) = \frac{\text{haversine\_distance}(n, \text{goal})}{V_{\text{vessel\_max}} + V_{\text{current\_max}}}$$
  Guaranteeing $h(n) \le c^*(n, \text{goal})$ for optimality.

### 2.5 Weather Client (`core/weather_client.py`)
- `WeatherAPIClient`:
  - Fetches Open-Meteo current and hourly wind components.
  - Implements in-memory TTL caching (default 600s).
  - Robust exception fallback on `requests.exceptions.RequestException`, timeouts, and non-200 responses to `SyntheticWeatherGenerator`.
  - Classifies winds using `WindClassifier`: Poyraz (NE, 45°), Lodos (SW, 225°), Karayel (NW, 315°), Yıldız (N, 0°), etc.

---

## 3. REST API Specifications (`main.py`)

All endpoints use Pydantic v2 schemas:

1. `GET /`: Serve single-page dashboard rendered via Jinja2 templates.
2. `GET /api/health`: Health status, uptime, active grid dimensions, memory footprint.
3. `GET /api/weather`: Current wind vector, speed, direction, classification (e.g. Poyraz), source (`live` | `cache` | `synthetic`), timestamp.
4. `GET /api/grid`: Metadata, geographic bounding box, downsampled surface current vector field for Canvas rendering.
5. `POST /api/simulate/forward`:
   - Input: `entity_type`, `lat`, `lon`, `particles` ($1-500$), `hours` ($0.5-24$), `integrator` (`euler` | `rk2`), optional `wind_override`.
   - Output: particle trajectories, bounding boxes, beached summary, landing probability matrix.
6. `POST /api/simulate/reverse`:
   - Input: `entity_type`, `last_lat`, `last_lon`, `particles`, `hours_back`, `integrator`.
   - Output: origin distribution cloud, mean origin coordinate, 95% confidence ellipse.
7. `POST /api/route`:
   - Input: `start_lat`, `start_lon`, `end_lat`, `end_lon`, `vessel_speed_knots`.
   - Output: waypoint coordinates, total distance (km), ETA (minutes), fuel cost proxy, nodes expanded.
8. `GET /api/analytics/summary`: Aggregate metrics across recent simulations.
9. `GET /api/analytics/chart/{name}`: Base64-encoded dark-mode chart (`heatmap`, `quiver`, `windrose`, `kde`, `route`).
10. `GET /api/export/csv`: Export simulation trajectories as downloadable CSV.

---

## 4. UI Dashboard Specifications

- **Styling**: Dark maritime mission-control theme (slate-900 background, cyan/emerald vector overlays, amber warnings, projector-friendly high-contrast 1280x720 layout).
- **Interactive Canvas**:
  - Deep blue water channel, dark charcoal land mass.
  - Animated flow streamlines or particle quivers showing Bosphorus current.
  - Render Monte Carlo particle swarms with semi-transparent glowing points.
  - Interactive map click handlers: Click to set start, end, or incident location.
- **Controls & Status**:
  - Mode selector tabs: Forward Swarm, Reverse Tracking, A* Vessel Routing.
  - Entity picker (Person, Life Raft, Fishing Boat, Oil Slick).
  - Weather status pill: Glowing green `LIVE`, yellow `CACHE`, or orange `SYNTHETIC`.
  - Analytics drawer: Slide-out panel rendering server-generated Matplotlib/Seaborn figures.
