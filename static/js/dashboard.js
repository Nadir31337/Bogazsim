/**
 * BoğazSim — Zoom Earth Style Maritime GIS Dashboard Client
 *
 * Combines Leaflet GIS with CartoDB Dark Matter basemap, 60 FPS wind streamline
 * particle animation, Zoom Earth style district wind badges, 3 suspension bridges,
 * live Open-Meteo meteorological API integration, Monte Carlo SAR swarms,
 * reverse datum backtracking, and weighted A* passage navigation.
 */

// Geographic domain constants
const LAT_MIN = 40.98;
const LAT_MAX = 41.25;
const LON_MIN = 28.95;
const LON_MAX = 29.20;
const CONSTRICTION_LAT = 41.085;
const CONSTRICTION_LON = 29.0786;

// Application State
const state = {
  map: null,
  canvas: null,
  ctx: null,
  grid: null,
  weather: {
    speed_ms: 8.1,
    speed_kmh: 29.0,
    speed_knots: 15.7,
    direction_deg: 354.0,
    u_wind: 0.85,
    v_wind: -8.05,
    sector_name: 'Yıldız',
    sector_description: 'North (N) — Cold Black Sea flow',
    speed_category: 'Fresh Breeze',
    surface_pressure_hpa: 1019.6,
    temperature_c: 14.4,
    source: 'live',
  },
  layers: {
    windFlow: true,
    districts: true,
    bridges: true,
    tss: true,
  },
  mapMarkers: [],
  bridgeLayers: [],
  tssLayers: [],
  targetMarker: null,
  currentSim: null,
  currentRoute: null,
  activeTab: 'forward',
  animating: false,
  animationStep: 0,
  maxSteps: 0,
  windStreamlines: [],
};

/**
 * Clean Coastal Bosphorus Maritime Stations matching Zoom Earth layout.
 * Accurately spans the Bosphorus Strait from Black Sea entrance to Marmara Sea.
 */
const BOSPHORUS_STATIONS = [
  // --- North Entrance / Black Sea ---
  { name: 'Rumelifeneri', lat: 41.240, lon: 29.098, baseSpeedKmh: 24 },
  { name: 'Poyrazköy', lat: 41.210, lon: 29.135, baseSpeedKmh: 23 },
  { name: 'Kilyos', lat: 41.248, lon: 29.030, baseSpeedKmh: 25 },
  { name: 'Riva', lat: 41.225, lon: 29.225, baseSpeedKmh: 24 },

  // --- Upper Bosphorus (North of FSM Bridge) ---
  { name: 'Sarıyer', lat: 41.170, lon: 29.048, baseSpeedKmh: 20 },
  { name: 'Beykoz', lat: 41.135, lon: 29.110, baseSpeedKmh: 18 },
  { name: 'Tarabya', lat: 41.140, lon: 29.045, baseSpeedKmh: 19 },
  { name: 'Paşabahçe', lat: 41.115, lon: 29.102, baseSpeedKmh: 18 },

  // --- The Narrows (700m Constriction - Highest Maritime Hazard) ---
  { name: 'Rumeli Hisarı', lat: 41.085, lon: 29.048, baseSpeedKmh: 18, isNarrows: true },
  { name: 'Kandilli', lat: 41.076, lon: 29.070, baseSpeedKmh: 17, isNarrows: true },

  // --- Lower Bosphorus (Between Bridges & Historic Peninsula) ---
  { name: 'Ortaköy', lat: 41.050, lon: 29.020, baseSpeedKmh: 16 },
  { name: 'Beşiktaş', lat: 41.042, lon: 28.995, baseSpeedKmh: 15 },
  { name: 'Üsküdar', lat: 41.026, lon: 29.022, baseSpeedKmh: 15 },
  { name: 'Kız Kulesi', lat: 41.021, lon: 29.004, baseSpeedKmh: 16, isWater: true },

  // --- South Entrance / Marmara Sea ---
  { name: 'Karaköy', lat: 41.022, lon: 28.974, baseSpeedKmh: 16 },
  { name: 'Kadıköy', lat: 40.990, lon: 29.030, baseSpeedKmh: 17 },
  { name: 'Bakırköy', lat: 40.975, lon: 28.875, baseSpeedKmh: 18 },
  { name: 'Bostancı', lat: 40.955, lon: 29.100, baseSpeedKmh: 17 },
];

/**
 * 3 Iconic Suspension Bridges
 */
const BOSPHORUS_BRIDGES = [
  {
    name: 'Yavuz Sultan Selim Köprüsü (3. Köprü)',
    coords: [[41.2025, 29.1020], [41.2035, 29.1320]],
    color: '#f59e0b',
  },
  {
    name: 'Fatih Sultan Mehmet Köprüsü (FSM / 2. Köprü)',
    coords: [[41.0910, 29.0555], [41.0915, 29.0725]],
    color: '#38bdf8',
  },
  {
    name: '15 Temmuz Şehitler Köprüsü (1. Köprü)',
    coords: [[41.0450, 29.0255], [41.0455, 29.0445]],
    color: '#34d399',
  },
];

/**
 * International TSS Fairways
 */
const TSS_NORTHBOUND = [
  [40.990, 29.025], [41.025, 29.020], [41.045, 29.038],
  [41.075, 29.062], [41.090, 29.068], [41.135, 29.085],
  [41.170, 29.070], [41.205, 29.120], [41.235, 29.135],
];

const TSS_SOUTHBOUND = [
  [41.235, 29.105], [41.205, 29.105], [41.170, 29.055],
  [41.135, 29.065], [41.090, 29.058], [41.075, 29.048],
  [41.045, 29.028], [41.025, 29.008], [40.990, 29.005],
];

/**
 * Initialize Leaflet Map with High-Performance, Watermark-Free GIS Basemaps
 */
function initMap() {
  const mapEl = document.getElementById('bosphorus-map');
  if (!mapEl) return;

  // Center on Istanbul Bosphorus with optimal framing
  state.map = L.map('bosphorus-map', {
    center: [41.115, 29.065],
    zoom: 11.4,
    minZoom: 10,
    maxZoom: 17,
    zoomControl: true,
    attributionControl: true,
  });

  // Basemap Tile Layers (Zero Watermark, 100% Free & Fast CDN)
  state.baseLayers = {
    dark: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ | BoğazSim',
      maxZoom: 16,
    }),
    sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics | BoğazSim',
      maxZoom: 18,
    }),
    osm: L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors | BoğazSim',
      maxZoom: 19,
    }),
  };

  // Add default Dark Canvas basemap
  state.activeBaseLayer = 'dark';
  state.baseLayers.dark.addTo(state.map);

  // Setup Animation Canvas Overlay
  initAnimationCanvas();

  // Populate Clean Coastal District Badges
  renderDistrictBadges();

  // Render Bridges and TSS Lanes
  renderBridges();
  renderTSSLanes();
}

/**
 * Switch Active Basemap Layer (Dark / Satellite / Street)
 */
function setBasemap(name) {
  if (!state.baseLayers || !state.baseLayers[name] || state.activeBaseLayer === name) return;
  state.map.removeLayer(state.baseLayers[state.activeBaseLayer]);
  state.baseLayers[name].addTo(state.map);

  // Keep particle canvas overlay on top of basemap
  if (state.canvas && state.canvas.parentNode) {
    state.canvas.parentNode.appendChild(state.canvas);
  }
  state.activeBaseLayer = name;

  // Update UI pill buttons
  ['dark', 'sat', 'osm'].forEach((b) => {
    const el = document.getElementById(`btn-bm-${b}`);
    if (el) {
      if (b === name) el.classList.add('active');
      else el.classList.remove('active');
    }
  });
}

  // Map Click Listener to Set Form Coordinates
  state.map.on('click', (e) => {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    // Place Target Pin
    if (state.targetMarker) state.map.removeLayer(state.targetMarker);
    state.targetMarker = L.circleMarker([lat, lon], {
      radius: 7,
      color: '#38bdf8',
      fillColor: '#0284c7',
      fillOpacity: 0.9,
      weight: 2,
    }).addTo(state.map);

    // Auto-fill active tab inputs
    if (state.activeTab === 'forward') {
      const latInp = document.getElementById('fwd-lat');
      const lonInp = document.getElementById('fwd-lon');
      if (latInp) latInp.value = lat.toFixed(4);
      if (lonInp) lonInp.value = lon.toFixed(4);
    } else if (state.activeTab === 'reverse') {
      const latInp = document.getElementById('rev-lat');
      const lonInp = document.getElementById('rev-lon');
      if (latInp) latInp.value = lat.toFixed(4);
      if (lonInp) lonInp.value = lon.toFixed(4);
    } else if (state.activeTab === 'route') {
      const sLat = document.getElementById('route-start-lat');
      const sLon = document.getElementById('route-start-lon');
      const eLat = document.getElementById('route-end-lat');
      const eLon = document.getElementById('route-end-lon');
      if (sLat && (!sLat.value || eLat.value)) {
        sLat.value = lat.toFixed(4);
        if (sLon) sLon.value = lon.toFixed(4);
      } else if (eLat) {
        eLat.value = lat.toFixed(4);
        if (eLon) eLon.value = lon.toFixed(4);
      }
    }
  });

  // Map Mousemove Telemetry
  state.map.on('mousemove', (e) => {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;
    const coordsEl = document.getElementById('cursor-coords');
    if (coordsEl) {
      coordsEl.textContent = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E | GIS VIEWPORT`;
    }
  });

  // Re-seed wind particles on zoom or pan
  state.map.on('moveend', () => {
    initWindStreamlines();
  });
}

/**
 * Setup High-Performance Transparent Canvas Overlay
 */
function initAnimationCanvas() {
  state.canvas = document.getElementById('anim-canvas');
  if (!state.canvas) return;
  state.ctx = state.canvas.getContext('2d');

  function resizeCanvas() {
    const container = document.getElementById('map-container');
    if (container && state.canvas) {
      state.canvas.width = container.clientWidth;
      state.canvas.height = container.clientHeight;
      initWindStreamlines();
    }
  }

  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
}

/**
 * Minimalist Zoom Earth Station Badges (DivIcon)
 */
function renderDistrictBadges() {
  // Clear old markers
  state.mapMarkers.forEach((m) => state.map.removeLayer(m));
  state.mapMarkers = [];

  if (!state.layers.districts) return;

  const windDir = state.weather.direction_deg || 0;

  BOSPHORUS_STATIONS.forEach((d) => {
    let speedVal = Math.round(d.baseSpeedKmh * ((state.weather.speed_kmh || 29.0) / 29.0));
    if (isNaN(speedVal) || speedVal <= 0) speedVal = d.baseSpeedKmh;

    const isNarrows = !!d.isNarrows;

    const iconHtml = `
      <div class="ze-station ${isNarrows ? 'ze-narrows' : ''}">
        <div class="ze-name">${isNarrows ? '⚠️ ' : ''}${d.name}</div>
        <div class="ze-pill">
          <span class="ze-val">${speedVal}</span>
          <span class="ze-arr" style="transform: rotate(${windDir}deg);">↓</span>
        </div>
      </div>
    `;

    const icon = L.divIcon({
      html: iconHtml,
      className: 'ze-div-icon',
      iconSize: [80, 36],
      iconAnchor: [40, 18],
    });

    const marker = L.marker([d.lat, d.lon], { icon }).addTo(state.map);
    marker.on('click', () => {
      if (state.activeTab === 'forward') {
        const latEl = document.getElementById('fwd-lat');
        const lonEl = document.getElementById('fwd-lon');
        if (latEl) latEl.value = d.lat.toFixed(4);
        if (lonEl) lonEl.value = d.lon.toFixed(4);
      } else if (state.activeTab === 'reverse') {
        const latEl = document.getElementById('rev-lat');
        const lonEl = document.getElementById('rev-lon');
        if (latEl) latEl.value = d.lat.toFixed(4);
        if (lonEl) lonEl.value = d.lon.toFixed(4);
      }
    });

    state.mapMarkers.push(marker);
  });
}

/**
 * Render Suspension Bridges
 */
function renderBridges() {
  state.bridgeLayers.forEach((b) => state.map.removeLayer(b));
  state.bridgeLayers = [];

  if (!state.layers.bridges) return;

  BOSPHORUS_BRIDGES.forEach((bridge) => {
    const line = L.polyline(bridge.coords, {
      color: bridge.color,
      weight: 3.5,
      opacity: 0.85,
      dashArray: '4, 2',
    }).addTo(state.map);

    line.bindTooltip(bridge.name, {
      permanent: false,
      direction: 'top',
      className: 'bg-slate-900 border border-slate-700 text-slate-100 font-mono text-xs px-2 py-1',
    });

    state.bridgeLayers.push(line);
  });
}

/**
 * Render International TSS Fairways
 */
function renderTSSLanes() {
  state.tssLayers.forEach((t) => state.map.removeLayer(t));
  state.tssLayers = [];

  if (!state.layers.tss) return;

  const north = L.polyline(TSS_NORTHBOUND, {
    color: '#34d399',
    weight: 2,
    opacity: 0.55,
    dashArray: '8, 8',
  }).addTo(state.map);
  north.bindTooltip('TSS Northbound Fairway (Asian Sector)', { className: 'bg-slate-900 text-emerald-400 font-mono text-xs' });

  const south = L.polyline(TSS_SOUTHBOUND, {
    color: '#f43f5e',
    weight: 2,
    opacity: 0.55,
    dashArray: '8, 8',
  }).addTo(state.map);
  south.bindTooltip('TSS Southbound Fairway (European Sector)', { className: 'bg-slate-900 text-rose-400 font-mono text-xs' });

  state.tssLayers.push(north, south);
}

/**
 * Zoom Earth Style Animated Wind Streamlines Engine
 */
function initWindStreamlines() {
  state.windStreamlines = [];
  if (!state.canvas) return;

  const count = 300;
  const W = state.canvas.width;
  const H = state.canvas.height;

  for (let i = 0; i < count; i++) {
    state.windStreamlines.push({
      x: Math.random() * W,
      y: Math.random() * H,
      len: 14 + Math.random() * 24,
      speed: 1.6 + Math.random() * 2.2,
      width: 1.2 + Math.random() * 0.8,
      life: Math.random() * 100,
      maxLife: 60 + Math.random() * 80,
      alpha: 0.35 + Math.random() * 0.55,
    });
  }
}

function renderWindStreamlines() {
  if (!state.layers.windFlow || !state.ctx || !state.canvas) return;

  const ctx = state.ctx;
  const W = state.canvas.width;
  const H = state.canvas.height;

  // Clear canvas overlay for next frame
  ctx.clearRect(0, 0, W, H);

  // Meteorological wind direction:
  // θ = direction from which wind blows (0° = North, 90° = East, etc.)
  // Motion vector on screen (x = East, y = South):
  // dx = -sin(θ), dy = +cos(θ)
  const rad = ((state.weather.direction_deg || 0) * Math.PI) / 180.0;
  const dx = -Math.sin(rad);
  const dy = Math.cos(rad);

  const speedMult = Math.max(0.6, (state.weather.speed_kmh || 20.0) / 18.0);

  ctx.lineCap = 'round';

  for (const p of state.windStreamlines) {
    const headX = p.x + dx * p.len;
    const headY = p.y + dy * p.len;

    const grad = ctx.createLinearGradient(p.x, p.y, headX, headY);
    grad.addColorStop(0, `rgba(186, 230, 253, 0)`);
    grad.addColorStop(0.65, `rgba(224, 242, 254, ${p.alpha * 0.5})`);
    grad.addColorStop(1, `rgba(255, 255, 255, ${p.alpha * 0.95})`);

    ctx.strokeStyle = grad;
    ctx.lineWidth = p.width;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(headX, headY);
    ctx.stroke();

    p.x += dx * p.speed * speedMult;
    p.y += dy * p.speed * speedMult;
    p.life++;

    // Re-spawn with edge offset
    if (p.life > p.maxLife || p.x < -80 || p.x > W + 80 || p.y < -80 || p.y > H + 80) {
      p.x = Math.random() * W - dx * (Math.random() * 120);
      p.y = Math.random() * H - dy * (Math.random() * 120);
      p.life = 0;
      p.maxLife = 60 + Math.random() * 90;
    }
  }
}

/**
 * Render Forward Swarm & Reverse Backtrack Overlays on Canvas
 */
function renderSimulationOverlays() {
  if (!state.map || !state.ctx) return;
  const ctx = state.ctx;

  // 1. Forward Monte Carlo Swarm
  if (state.currentSim && state.currentSim.trajectories && state.activeTab === 'forward') {
    const trajs = state.currentSim.trajectories;
    const curStep = Math.min(state.animationStep, state.maxSteps);

    let color = '#38bdf8';
    if (state.currentSim.entity_type === 'raft') color = '#34d399';
    else if (state.currentSim.entity_type === 'boat') color = '#fbbf24';
    else if (state.currentSim.entity_type === 'oil') color = '#a78bfa';

    ctx.lineWidth = 1.8;
    for (const path of trajs) {
      if (!path || path.length === 0) continue;
      const visLen = Math.min(curStep, path.length);

      ctx.strokeStyle = color + '60';
      ctx.beginPath();
      for (let s = 0; s < visLen; s++) {
        const pt = state.map.latLngToContainerPoint([path[s][0], path[s][1]]);
        if (s === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.stroke();

      if (visLen > 0) {
        const head = state.map.latLngToContainerPoint([path[visLen - 1][0], path[visLen - 1][1]]);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(head.x, head.y, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Beaching Collisions
    if (state.currentSim.final_positions && curStep >= state.maxSteps) {
      for (const p of state.currentSim.final_positions) {
        if (p[2]) {
          const pt = state.map.latLngToContainerPoint([p[0], p[1]]);
          ctx.fillStyle = '#f43f5e';
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 5.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }
    }
  }

  // 2. Reverse Backtracking Cloud & Ellipse
  if (state.currentSim && state.currentSim.estimated_origins && state.activeTab === 'reverse') {
    const curStep = Math.min(state.animationStep, state.maxSteps);
    const trajs = state.currentSim.trajectories || [];

    ctx.lineWidth = 1.2;
    ctx.strokeStyle = 'rgba(251, 191, 36, 0.45)';
    for (const path of trajs) {
      const visLen = Math.min(curStep, path.length);
      ctx.beginPath();
      for (let s = 0; s < visLen; s++) {
        const pt = state.map.latLngToContainerPoint([path[s][0], path[s][1]]);
        if (s === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.stroke();
    }

    if (curStep >= state.maxSteps) {
      ctx.fillStyle = '#fbbf24';
      for (const orig of state.currentSim.estimated_origins) {
        const pt = state.map.latLngToContainerPoint([orig[0], orig[1]]);
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      // 95% Confidence Ellipse
      if (state.currentSim.mean_origin && state.currentSim.confidence_ellipse_95_km) {
        const meanPt = state.map.latLngToContainerPoint([state.currentSim.mean_origin[0], state.currentSim.mean_origin[1]]);
        const ellipse = state.currentSim.confidence_ellipse_95_km;

        // Convert km to map pixels at current zoom
        const ptLat = state.map.latLngToContainerPoint([state.currentSim.mean_origin[0] + (ellipse.semi_major_lat / 111.0), state.currentSim.mean_origin[1]]);
        const ptLon = state.map.latLngToContainerPoint([state.currentSim.mean_origin[0], state.currentSim.mean_origin[1] + (ellipse.semi_minor_lon / 84.0)]);
        const rx = Math.abs(ptLon.x - meanPt.x);
        const ry = Math.abs(ptLat.y - meanPt.y);

        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.2;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.ellipse(meanPt.x, meanPt.y, Math.max(16, rx), Math.max(16, ry), 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 11px monospace';
        ctx.fillText('95% SAR DATUM ELLIPSE', meanPt.x + 20, meanPt.y - 10);
      }
    }
  }

  // 3. Optimal A* Passage Polyline
  if (state.currentRoute && state.currentRoute.waypoints) {
    const wps = state.currentRoute.waypoints;
    if (wps.length >= 2) {
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 4;
      ctx.shadowColor = '#34d399';
      ctx.shadowBlur = 12;

      ctx.beginPath();
      for (let i = 0; i < wps.length; i++) {
        const pt = state.map.latLngToContainerPoint([wps[i][0], wps[i][1]]);
        if (i === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      for (let i = 0; i < wps.length; i++) {
        const pt = state.map.latLngToContainerPoint([wps[i][0], wps[i][1]]);
        ctx.fillStyle = i === 0 ? '#38bdf8' : i === wps.length - 1 ? '#f43f5e' : '#34d399';
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, i === 0 || i === wps.length - 1 ? 6 : 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }
  }
}

/**
 * 60 FPS Master Animation Loop
 */
function animate() {
  renderWindStreamlines();
  renderSimulationOverlays();

  if (state.animating && state.animationStep < state.maxSteps) {
    state.animationStep += 2;
  }

  requestAnimationFrame(animate);
}

/**
 * Live Open-Meteo Weather Synchronization
 */
async function fetchWeatherData(force = false) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const openMeteoUrl = 'https://api.open-meteo.com/v1/forecast?latitude=41.0422&longitude=29.0083&current=wind_speed_10m,wind_direction_10m,surface_pressure,temperature_2m,relative_humidity_2m&wind_speed_unit=ms';
    const res = await fetch(openMeteoUrl, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      const cur = data.current;
      const speed = parseFloat(cur.wind_speed_10m);
      const dir = parseFloat(cur.wind_direction_10m);
      const press = parseFloat(cur.surface_pressure || 1014.0);
      const temp = parseFloat(cur.temperature_2m || 15.0);

      const rad = (dir * Math.PI) / 180.0;
      const u = -speed * Math.sin(rad);
      const v = -speed * Math.cos(rad);
      const sector = classifyWindSector(dir);
      const category = classifyBeaufort(speed);
      const kmh = Math.round(speed * 3.6);
      const kts = (speed * 1.94384).toFixed(1);

      state.weather = {
        speed_ms: Math.round(speed * 10) / 10,
        speed_kmh: kmh,
        speed_knots: parseFloat(kts),
        direction_deg: Math.round(dir * 10) / 10,
        u_wind: Math.round(u * 100) / 100,
        v_wind: Math.round(v * 100) / 100,
        sector_name: sector.name,
        sector_description: sector.desc,
        speed_category: category,
        surface_pressure_hpa: Math.round(press * 10) / 10,
        temperature_c: Math.round(temp * 10) / 10,
        source: 'live',
      };
      updateWeatherUI();
      renderDistrictBadges();
      return;
    }
  } catch (err) {
    console.warn('Direct Open-Meteo fetch failed, using fallback:', err);
  }

  // Fallback to /api/weather
  try {
    const res = await fetch('/api/weather');
    if (res.ok) {
      const data = await res.json();
      const kmh = Math.round(data.speed_ms * 3.6);
      state.weather = {
        speed_ms: data.speed_ms,
        speed_kmh: kmh,
        speed_knots: parseFloat((data.speed_ms * 1.94384).toFixed(1)),
        direction_deg: data.direction_deg,
        u_wind: data.u_wind,
        v_wind: data.v_wind,
        sector_name: data.sector_name,
        sector_description: data.sector_description || '',
        speed_category: data.speed_category || classifyBeaufort(data.speed_ms),
        surface_pressure_hpa: data.surface_pressure_hpa || 1014.0,
        temperature_c: 15.0,
        source: data.source || 'cached',
      };
      updateWeatherUI();
      renderDistrictBadges();
    }
  } catch (err) {
    console.error('All weather sources failed:', err);
  }
}

function classifyWindSector(deg) {
  const d = (deg % 360 + 360) % 360;
  if (d >= 337.5 || d < 22.5) return { name: 'Yıldız', desc: 'North (N) — Cold Black Sea air' };
  if (d >= 22.5 && d < 67.5) return { name: 'Poyraz', desc: 'North-East (NE) — Dominant high-speed prevailing wind' };
  if (d >= 67.5 && d < 112.5) return { name: 'Gündoğusu', desc: 'East (E) — Continental mild breeze' };
  if (d >= 112.5 && d < 157.5) return { name: 'Keşişleme', desc: 'South-East (SE) — Dry warm breeze' };
  if (d >= 157.5 && d < 202.5) return { name: 'Kıble', desc: 'South (S) — Warm southerly Mediterranean flow' };
  if (d >= 202.5 && d < 247.5) return { name: 'Lodos', desc: 'South-West (SW) — Storm squalls, heavy chop and swells' };
  if (d >= 247.5 && d < 292.5) return { name: 'Günbatısı', desc: 'West (W) — Maritime westerly front' };
  return { name: 'Karayel', desc: 'North-West (NW) — Cold, gusty storm winds' };
}

function classifyBeaufort(speed_ms) {
  if (speed_ms < 0.5) return 'Calm';
  if (speed_ms < 1.5) return 'Light Air';
  if (speed_ms < 3.3) return 'Light Breeze';
  if (speed_ms < 5.4) return 'Gentle Breeze';
  if (speed_ms < 7.9) return 'Moderate Breeze';
  if (speed_ms < 10.7) return 'Fresh Breeze';
  if (speed_ms < 13.8) return 'Strong Breeze';
  if (speed_ms < 17.1) return 'Near Gale';
  if (speed_ms < 20.7) return 'Gale';
  if (speed_ms < 24.4) return 'Strong Gale';
  return 'Storm Force';
}

function updateWeatherUI() {
  const w = state.weather;

  // Header Pill
  const statusEl = document.getElementById('weather-status');
  if (statusEl) {
    statusEl.textContent = `${w.sector_name.toUpperCase()} (${w.direction_deg}° ${w.speed_ms} m/s | ${w.speed_kmh} km/h)`;
  }
  const badgeEl = document.getElementById('weather-source-badge');
  if (badgeEl) {
    badgeEl.textContent = w.source === 'live' ? 'LIVE API' : 'SYNTHETIC';
    badgeEl.className = w.source === 'live'
      ? 'text-[10px] uppercase px-1.5 py-0.2 rounded bg-emerald-950 border border-emerald-700 text-emerald-300'
      : 'text-[10px] uppercase px-1.5 py-0.2 rounded bg-amber-950 border border-amber-700 text-amber-300';
  }

  // Sidebar Card
  const sSec = document.getElementById('wx-sector');
  if (sSec) sSec.textContent = `${w.sector_name.toUpperCase()}`;
  const sDeg = document.getElementById('wx-deg');
  if (sDeg) sDeg.textContent = `${w.direction_deg}° • ${w.speed_category}`;
  const sSpd = document.getElementById('wx-speed');
  if (sSpd) sSpd.textContent = `${w.speed_ms} m/s`;
  const sKts = document.getElementById('wx-knots');
  if (sKts) sKts.textContent = `(${w.speed_knots} kts | ${w.speed_kmh} km/h)`;
  const sTmp = document.getElementById('wx-temp');
  if (sTmp) sTmp.textContent = `${w.temperature_c}°C`;
  const sPrs = document.getElementById('wx-press');
  if (sPrs) sPrs.textContent = `${w.surface_pressure_hpa} hPa`;

  // Zoom Earth Top Right Status Badge
  const zwSpeed = document.getElementById('zoom-wind-speed-val');
  if (zwSpeed) zwSpeed.textContent = `${w.speed_kmh} km/h`;
  const zwArrow = document.getElementById('zoom-wind-arrow');
  if (zwArrow) zwArrow.style.transform = `rotate(${w.direction_deg}deg)`;
  const zwDir = document.getElementById('zoom-wind-dir-name');
  if (zwDir) zwDir.textContent = `${w.direction_deg}° (${w.sector_name.toUpperCase()})`;
}

/**
 * API Submissions
 */
async function handleForwardSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-forward');
  if (btn) btn.disabled = true;

  const payload = {
    entity_type: document.getElementById('fwd-entity').value,
    lat: parseFloat(document.getElementById('fwd-lat').value),
    lon: parseFloat(document.getElementById('fwd-lon').value),
    particles: parseInt(document.getElementById('fwd-particles').value, 10),
    hours: parseFloat(document.getElementById('fwd-hours').value),
    dt: parseFloat(document.getElementById('fwd-dt').value),
    integrator: document.getElementById('fwd-integrator').value,
    beach_on_collision: document.getElementById('fwd-beach').checked,
    spill_volume_m3: parseFloat(document.getElementById('fwd-spill').value || 10.0),
  };

  if (document.getElementById('fwd-use-live-wind')?.checked && state.weather) {
    payload.wind_speed = state.weather.speed_ms;
    payload.wind_direction = state.weather.direction_deg;
  }

  try {
    const res = await fetch('/api/simulate/forward', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Simulation Error (${res.status}): ${err.detail || err.error}`);
      return;
    }
    state.currentSim = await res.json();
    state.maxSteps = state.currentSim.trajectories && state.currentSim.trajectories[0] ? state.currentSim.trajectories[0].length : 100;
    state.animationStep = 0;
    state.animating = true;
    updateTelemetryCard(state.currentSim, 'forward');
  } catch (err) {
    alert(`Request failed: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleReverseSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-reverse');
  if (btn) btn.disabled = true;

  const payload = {
    entity_type: document.getElementById('rev-entity').value,
    last_lat: parseFloat(document.getElementById('rev-lat').value),
    last_lon: parseFloat(document.getElementById('rev-lon').value),
    particles: parseInt(document.getElementById('rev-particles').value, 10),
    hours_back: parseFloat(document.getElementById('rev-hours').value),
    dt: parseFloat(document.getElementById('rev-dt').value),
    integrator: document.getElementById('rev-integrator').value,
  };

  if (document.getElementById('rev-use-live-wind')?.checked && state.weather) {
    payload.wind_speed = state.weather.speed_ms;
    payload.wind_direction = state.weather.direction_deg;
  }

  try {
    const res = await fetch('/api/simulate/reverse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Reverse Tracking Error (${res.status}): ${err.detail || err.error}`);
      return;
    }
    state.currentSim = await res.json();
    state.maxSteps = state.currentSim.trajectories && state.currentSim.trajectories[0] ? state.currentSim.trajectories[0].length : 100;
    state.animationStep = 0;
    state.animating = true;
    updateTelemetryCard(state.currentSim, 'reverse');
  } catch (err) {
    alert(`Request failed: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleRouteSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-route');
  if (btn) btn.disabled = true;

  const payload = {
    start_lat: parseFloat(document.getElementById('route-start-lat').value),
    start_lon: parseFloat(document.getElementById('route-start-lon').value),
    end_lat: parseFloat(document.getElementById('route-end-lat').value),
    end_lon: parseFloat(document.getElementById('route-end-lon').value),
    vessel_speed_knots: parseFloat(document.getElementById('route-speed').value),
    head_current_penalty: parseFloat(document.getElementById('route-penalty').value),
  };

  try {
    const res = await fetch('/api/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Routing Error (${res.status}): ${err.detail || err.error}`);
      return;
    }
    state.currentRoute = await res.json();
    updateTelemetryCard(state.currentRoute, 'route');
  } catch (err) {
    alert(`Routing request failed: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function updateTelemetryCard(data, type) {
  const card = document.getElementById('telemetry-card');
  if (!card) return;

  if (type === 'forward') {
    card.innerHTML = `
      <div class="text-xs font-semibold uppercase text-cyan-400 mb-1">Forward Swarm Telemetry</div>
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div><span class="text-slate-400">Particles:</span> <span class="font-mono text-slate-100">${data.particle_count}</span></div>
        <div><span class="text-slate-400">Duration:</span> <span class="font-mono text-slate-100">${data.duration_hours}h</span></div>
        <div><span class="text-slate-400">Beached:</span> <span class="font-mono text-rose-400">${data.beached_count} (${data.beached_percentage.toFixed(1)}%)</span></div>
        <div><span class="text-slate-400">Timestep:</span> <span class="font-mono text-slate-100">${data.time_step_seconds}s</span></div>
      </div>
    `;
  } else if (type === 'reverse') {
    card.innerHTML = `
      <div class="text-xs font-semibold uppercase text-amber-400 mb-1">Reverse Backtracking Telemetry</div>
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div><span class="text-slate-400">Particles:</span> <span class="font-mono text-slate-100">${data.particle_count}</span></div>
        <div><span class="text-slate-400">Backtrack:</span> <span class="font-mono text-slate-100">${data.hours_back}h</span></div>
        <div class="col-span-2"><span class="text-slate-400">Mean Origin:</span> <span class="font-mono text-cyan-400">${data.mean_origin[0].toFixed(4)}°N, ${data.mean_origin[1].toFixed(4)}°E</span></div>
      </div>
    `;
  } else if (type === 'route') {
    card.innerHTML = `
      <div class="text-xs font-semibold uppercase text-emerald-400 mb-1">A* Passage Plan Telemetry</div>
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div><span class="text-slate-400">Distance:</span> <span class="font-mono text-slate-100">${data.total_distance_km.toFixed(2)} km</span></div>
        <div><span class="text-slate-400">ETA:</span> <span class="font-mono text-slate-100">${data.eta_minutes.toFixed(1)} min</span></div>
        <div><span class="text-slate-400">Fuel Proxy:</span> <span class="font-mono text-slate-100">${data.fuel_proxy.toFixed(1)} rel units</span></div>
        <div><span class="text-slate-400">Nodes Expanded:</span> <span class="font-mono text-slate-100">${data.nodes_expanded}</span></div>
      </div>
    `;
  }
}

async function openChartModal(chartName) {
  const modal = document.getElementById('chart-modal');
  const img = document.getElementById('modal-chart-img');
  const title = document.getElementById('modal-chart-title');
  if (!modal || !img || !title) return;

  title.textContent = `LOADING OCEANOGRAPHIC CHART: ${chartName.toUpperCase()}...`;
  img.src = '';
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/analytics/chart/${chartName}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    title.textContent = `DARK MARITIME CHART: ${chartName.toUpperCase()}`;
    img.src = data.image_base64;
  } catch (err) {
    alert(`Could not generate chart '${chartName}': ${err.message}`);
    modal.classList.add('hidden');
  }
}

function closeChartModal() {
  const modal = document.getElementById('chart-modal');
  if (modal) modal.classList.add('hidden');
}

function switchTab(tabId) {
  state.activeTab = tabId;
  const tabs = ['forward', 'reverse', 'route', 'analytics'];
  tabs.forEach((t) => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const panel = document.getElementById(`panel-${t}`);
    if (btn) {
      if (t === tabId) btn.classList.add('active');
      else btn.classList.remove('active');
    }
    if (panel) {
      if (t === tabId) panel.classList.remove('hidden');
      else panel.classList.add('hidden');
    }
  });
}

function setupLayerToggles() {
  const toggles = [
    { id: 'toggle-layer-wind-flow', key: 'windFlow' },
    { id: 'toggle-layer-districts', key: 'districts', onChange: renderDistrictBadges },
    { id: 'toggle-layer-bridges', key: 'bridges', onChange: renderBridges },
    { id: 'toggle-layer-tss', key: 'tss', onChange: renderTSSLanes },
  ];

  toggles.forEach(({ id, key, onChange }) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener('click', () => {
      state.layers[key] = !state.layers[key];
      if (state.layers[key]) btn.classList.add('active');
      else btn.classList.remove('active');
      if (onChange) onChange();
    });
  });

  // Basemap Switcher Listeners
  ['dark', 'sat', 'osm'].forEach((bm) => {
    const btn = document.getElementById(`btn-bm-${bm}`);
    if (btn) {
      btn.addEventListener('click', () => setBasemap(bm));
    }
  });
}

/**
 * DOM Ready Entrypoint
 */
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  fetchWeatherData();
  setupLayerToggles();

  // Tab listeners
  document.getElementById('tab-btn-forward')?.addEventListener('click', () => switchTab('forward'));
  document.getElementById('tab-btn-reverse')?.addEventListener('click', () => switchTab('reverse'));
  document.getElementById('tab-btn-route')?.addEventListener('click', () => switchTab('route'));
  document.getElementById('tab-btn-analytics')?.addEventListener('click', () => switchTab('analytics'));

  // Form listeners
  document.getElementById('form-forward')?.addEventListener('submit', handleForwardSubmit);
  document.getElementById('form-reverse')?.addEventListener('submit', handleReverseSubmit);
  document.getElementById('form-route')?.addEventListener('submit', handleRouteSubmit);

  // Preset buttons
  document.getElementById('btn-preset-northbound')?.addEventListener('click', () => {
    document.getElementById('route-start-lat').value = '41.0100';
    document.getElementById('route-start-lon').value = '29.0265';
    document.getElementById('route-end-lat').value = '41.2000';
    document.getElementById('route-end-lon').value = '29.0820';
  });

  document.getElementById('btn-preset-southbound')?.addEventListener('click', () => {
    document.getElementById('route-start-lat').value = '41.2000';
    document.getElementById('route-start-lon').value = '29.0820';
    document.getElementById('route-end-lat').value = '41.0100';
    document.getElementById('route-end-lon').value = '29.0265';
  });

  // Export CSV
  document.getElementById('btn-export-csv')?.addEventListener('click', () => {
    window.location.href = '/api/export/csv';
  });

  // Live Weather Sync Button
  document.getElementById('btn-sync-weather')?.addEventListener('click', () => {
    fetchWeatherData(true);
  });

  // Periodic Weather Refresh (Every 60s)
  setInterval(() => {
    fetchWeatherData(false);
  }, 60000);

  // Start 60 FPS Rendering Loop
  requestAnimationFrame(animate);
});
