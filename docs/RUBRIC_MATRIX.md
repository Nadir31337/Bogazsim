# SEN4015 Grading Rubric Verification Matrix

This matrix maps every academic and technical requirement of the SEN4015 Advanced Programming with Python grading rubric to its concrete implementation in the BoğazSim codebase.

| # | SEN4015 Rubric Domain | Implementation File & Code Symbols | Technical Description & Academic Significance |
|:---:|:---|:---|:---|
| 1 | **Object-Oriented Design & Encapsulation** | [`core/grid_engine.py`](../core/grid_engine.py)<br>[`core/weather_client.py`](../core/weather_client.py) | `FluidCell` encapsulates horizontal velocity $(u, v)$, water depth, and land masks using `@property` and setter validation preventing unphysical speeds ($> 10\text{ m/s}$). `WindClassifier` encapsulates Beaufort scale and sector categorization. |
| 2 | **Dunder Methods & Pythonic Protocols** | [`core/grid_engine.py`](../core/grid_engine.py)<br>[`core/entities.py`](../core/entities.py) | `FluidCell` and `VectorGrid` implement `__repr__`, `__getitem__`, `__len__`, and `__iter__` for clean matrix slicing and debugging string representations. |
| 3 | **Inheritance & Polymorphism** | [`core/integrators.py`](../core/integrators.py)<br>[`core/entities.py`](../core/entities.py) | Abstract base class `Integrator` with polymorphic `EulerIntegrator` and `RK2Integrator`. Abstract base `DriftEntity` subclassed by `PersonInWater`, `LifeRaft`, `FishingBoat`, and `OilSlick`. |
| 4 | **Custom Exception Hierarchy** | [`core/exceptions.py`](../core/exceptions.py) | Domain exception tree rooted at `BogazSimError`: `LandCollisionError`, `GridBoundsError`, `RouteNotFoundError`, `WeatherAPIError`, and `InvalidParameterError`. |
| 5 | **Centralized Constants Principle** | [`core/constants.py`](../core/constants.py) | All physical parameters, geographic bounds, time intervals, eddy vorticities, and visual colors defined as typed `Final` constants. |
| 6 | **Bilinear Interpolation** | [`core/grid_engine.py`](../core/grid_engine.py) | Hand-crafted 2D bilinear interpolation sampling continuous coordinates $(x, y)$ within four enclosing grid cell nodes, guaranteeing $C^0$ velocity continuity. |
| 7 | **Numerical Integrators & CFL Compliance** | [`core/integrators.py`](../core/integrators.py) | Explicit Euler ($\mathcal{O}(\Delta t)$ global error) and RK2 Midpoint Scheme ($\mathcal{O}(\Delta t^2)$ error). Courant number $\mathcal{C} \approx 0.19$ keeps particles from skipping cells and ensures numerical stability. |
| 8 | **Monte Carlo Stochastic Swarms** | [`core/simulator.py`](../core/simulator.py) | Simulates $N = 100\text{ to }500$ particles subject to current velocity, aerodynamic leeway deflection with Coriolis rotation ($+15^\circ$), and Brownian motion turbulent diffusion. |
| 9 | **Fay Oil Spill Spreading Model** | [`core/entities.py`](../core/entities.py) | Models gravity-viscous oil slick boundary growth $r(t) \propto V_0^{1/3} t^{1/4}$ with Gaussian radial dispersion over time. |
| 10 | **Reverse Datum Backtracking** | [`core/simulator.py`](../core/simulator.py) | Inverts time integration ($-\Delta t$) from last-known sightings, generating an upstream origin cloud with an analytical $95\%$ bivariate confidence dispersion ellipse. |
| 11 | **Weighted A\* Vessel Navigation** | [`core/route_optimizer.py`](../core/route_optimizer.py) | Graph search on Moore 8-neighborhood optimizing Ground Speed ($V_{\text{ground}} = V_s + \mathbf{V}_c \cdot \hat{\mathbf{u}}$) and quadratic head-current fuel penalties ($\lambda_{\text{head}}$), smoothed via raycasting. |
| 12 | **Data Analysis & Rolling Statistics** | [`analytics/data_processor.py`](../analytics/data_processor.py) | Pandas and NumPy pipelines computing spherical Haversine geodesic distances, rolling velocity means/variances ($w = 5$), landing histograms, and particle summary metrics. |
| 13 | **Dark-Themed Publication Visualizer** | [`analytics/visualizer.py`](../analytics/visualizer.py) | Thread-safe object-oriented Matplotlib/Seaborn engine with `threading.Lock` generating Base64 web URIs and 300-DPI publication PNGs (quiver, wind rose, heatmap, KDEs, route). |
| 14 | **Web REST API Domain** | [`main.py`](../main.py) | 10 FastAPI endpoints, Pydantic v2 schemas, AnyIO worker thread pools for CPU-bound routes, thread-safe `SimulationStateManager`, and custom exception handlers. |
| 15 | **Offline Testing & Zero-Dependency ASGI** | [`tests/test_bogazsim.py`](../tests/test_bogazsim.py) | 104 unit tests executing 100% offline via mock weather injection and in-memory ASGI client fallback (`_ASGITestClient`). |
| 16 | **Mission-Control Digital Twin** | [`templates/index.html`](../templates/index.html)<br>[`static/js/dashboard.js`](../static/js/dashboard.js) | Interactive HTML5 Canvas map rendering continuous shorelines, 3 suspension bridges, 22 landmarks, live Open-Meteo REST API poller, and interactive wind compass rose. |

---

### Related Documentation
- [Architecture & Academic Defense Guide](ARCHITECTURE_AND_QA_GUIDE.md)
- [Project Readme](../README.md)
