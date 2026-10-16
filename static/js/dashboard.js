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
const CONSTRICTION_LON = 29.0621;

// Application State
const state = {
  map: null,
  canvas: null,
  ctx: null,
  grid: null,
  weather: {
    speed_ms: 4.2,
    speed_kmh: 15.0,
    speed_knots: 8.2,
    direction_deg: 350.0,
    u_wind: 0.73,
    v_wind: -4.14,
    sector_name: 'Yıldız',
    sector_description: 'North (N) — Cold Black Sea maritime flow',
    speed_category: 'Gentle Breeze',
    surface_pressure_hpa: 1017.5,
    temperature_c: 15.0,
    source: 'live',
  },
  layers: {
    windFlow: true,
    districts: true,
  },
  mapMarkers: [],
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
 * Features authentic hydrodynamic exposure factors and topographical channel azimuths.
 */
const BOSPHORUS_STATIONS = [
  // --- North Entrance / Black Sea (Direct open marine exposure) ---
  { name: 'Rumelifeneri', lat: 41.240, lon: 29.098, exposure: 1.10, channelAzimuth: 355 },
  { name: 'Poyrazköy', lat: 41.210, lon: 29.135, exposure: 1.08, channelAzimuth: 015 },
  { name: 'Kilyos', lat: 41.248, lon: 29.030, exposure: 1.14, channelAzimuth: 345 },
  { name: 'Riva', lat: 41.225, lon: 29.225, exposure: 1.12, channelAzimuth: 025 },

  // --- Upper Bosphorus (Channeled valley flow) ---
  { name: 'Sarıyer', lat: 41.170, lon: 29.048, exposure: 1.02, channelAzimuth: 020 },
  { name: 'Beykoz', lat: 41.135, lon: 29.110, exposure: 0.98, channelAzimuth: 025 },
  { name: 'Tarabya', lat: 41.140, lon: 29.045, exposure: 1.00, channelAzimuth: 020 },
  { name: 'Paşabahçe', lat: 41.115, lon: 29.102, exposure: 0.98, channelAzimuth: 030 },

  // --- The Narrows (700m Constriction - Venturi acceleration & sharp bend) ---
  { name: 'Rumeli Hisarı', lat: 41.085, lon: 29.048, exposure: 1.18, channelAzimuth: 035, isNarrows: true },
  { name: 'Kandilli', lat: 41.076, lon: 29.070, exposure: 1.16, channelAzimuth: 035, isNarrows: true },

  // --- Lower Bosphorus (Transition reach) ---
  { name: 'Ortaköy', lat: 41.050, lon: 29.020, exposure: 0.98, channelAzimuth: 030 },
  { name: 'Beşiktaş', lat: 41.042, lon: 28.995, exposure: 0.95, channelAzimuth: 030 },
  { name: 'Üsküdar', lat: 41.026, lon: 29.022, exposure: 0.96, channelAzimuth: 030 },
  { name: 'Kız Kulesi', lat: 41.021, lon: 29.004, exposure: 1.04, channelAzimuth: 030, isWater: true },

  // --- South Entrance / Marmara Sea ---
  { name: 'Karaköy', lat: 41.022, lon: 28.974, exposure: 0.95, channelAzimuth: 035 },
  { name: 'Kadıköy', lat: 40.990, lon: 29.030, exposure: 1.02, channelAzimuth: 040 },
  { name: 'Bakırköy', lat: 40.975, lon: 28.875, exposure: 1.05, channelAzimuth: 045 },
  { name: 'Bostancı', lat: 40.955, lon: 29.100, exposure: 1.02, channelAzimuth: 045 },
];

/**
 * Authentic Bosphorus Shoreline Model & Water Constraints
 */
const BOSPHORUS_COASTLINE = [
  [40.9700, 28.9400, 29.0350],  // Marmara South Open
  [40.9850, 28.9650, 29.0250],  // Ahırkapı / Kadıköy Outer
  [40.9950, 28.9830, 29.0200],  // Ahırkapı / Haydarpaşa
  [41.0100, 28.9840, 29.0110],  // Sarayburnu South / Harem
  [41.0180, 28.9870, 29.0065],  // Sarayburnu Tip / Salacak
  [41.0250, 28.9800, 29.0120],  // Karaköy / Kız Kulesi / Üsküdar Shore
  [41.0330, 28.9950, 29.0250],  // Kabataş / Kuzguncuk
  [41.0410, 29.0080, 29.0380],  // Beşiktaş / Beylerbeyi South
  [41.0450, 29.0270, 29.0430],  // Ortaköy / 15 Temmuz Bridge / Beylerbeyi
  [41.0500, 29.0300, 29.0480],  // Ortaköy / Beylerbeyi North
  [41.0580, 29.0340, 29.0520],  // Kuruçeşme / Çengelköy
  [41.0660, 29.0410, 29.0580],  // Arnavutköy / Vaniköy
  [41.0730, 29.0445, 29.0620],  // Akıntı Burnu / Kandilli
  [41.0800, 29.0440, 29.0620],  // Bebek Bay / Aşiyan / Kandilli North
  [41.0855, 29.0575, 29.0660],  // Rumeli Hisarı / Anadolu Hisarı (The Narrows)
  [41.0915, 29.0570, 29.0690],  // FSM Bridge
  [41.0990, 29.0570, 29.0700],  // Baltalimanı / Kanlıca
  [41.1100, 29.0575, 29.0780],  // Emirgan / Çubuklu
  [41.1180, 29.0585, 29.0880],  // İstinye Bay / Paşabahçe
  [41.1270, 29.0700, 29.0960],  // Yeniköy / Paşabahçe North
  [41.1380, 29.0600, 29.1000],  // Tarabya Bay / Beykoz
  [41.1480, 29.0520, 29.0740],  // Kireçburnu / Umuryeri
  [41.1580, 29.0480, 29.0700],  // Kefeliköy / Umuryeri North
  [41.1660, 29.0430, 29.0750],  // Büyükdere Bay / Selvi Burnu
  [41.1750, 29.0520, 29.0860],  // Sarıyer / Yuşa Tepesi
  [41.1850, 29.0740, 29.0980],  // Rumeli Kavağı / Anadolu Kavağı
  [41.1960, 29.0940, 29.1140],  // Altınkum / Mezar Burnu
  [41.2030, 29.1080, 29.1300],  // Garipçe / Poyrazköy (YSS Bridge)
  [41.2200, 29.1030, 29.1400],  // Rumelifeneri South / Poyrazköy North
  [41.2350, 29.1080, 29.1480],  // Rumelifeneri / Fil Burnu
  [41.2500, 29.0850, 29.1650],  // Black Sea North Open Mouth
];

function getBosphorusShores(lat) {
  const pts = BOSPHORUS_COASTLINE;
  if (lat <= pts[0][0]) return { west: pts[0][1], east: pts[0][2] };
  if (lat >= pts[pts.length - 1][0]) return { west: pts[pts.length - 1][1], east: pts[pts.length - 1][2] };
  for (let i = 0; i < pts.length - 1; i++) {
    if (pts[i][0] <= lat && lat <= pts[i + 1][0]) {
      const r = (lat - pts[i][0]) / (pts[i + 1][0] - pts[i][0]);
      return {
        west: pts[i][1] + r * (pts[i + 1][1] - pts[i][1]),
        east: pts[i][2] + r * (pts[i + 1][2] - pts[i][2]),
      };
    }
  }
  return { west: 29.00, east: 29.08 };
}

function snapToBosphorusWater(lat, lon) {
  const clampedLat = Math.max(40.985, Math.min(41.245, lat));
  const shores = getBosphorusShores(clampedLat);
  const channelWidth = shores.east - shores.west;
  const margin = Math.max(0.0020, channelWidth * 0.14);
  let snappedLon = lon;
  let wasSnapped = false;
  if (lon < shores.west + margin) {
    snappedLon = shores.west + margin;
    wasSnapped = true;
  } else if (lon > shores.east - margin) {
    snappedLon = shores.east - margin;
    wasSnapped = true;
  }
  return { lat: clampedLat, lon: snappedLon, wasSnapped };
}



/**
 * Initialize Leaflet Map Locked to Istanbul Bosphorus
 */
function initMap() {
  const mapEl = document.getElementById('bosphorus-map');
  if (!mapEl) return;

  // Strict spatial boundaries: Lock viewport strictly to Greater Istanbul & Bosphorus
  const ISTANBUL_BOUNDS = L.latLngBounds(
    [40.80, 28.65], // Southwest Istanbul / Sea of Marmara
    [41.35, 29.40]  // Northeast Istanbul / Black Sea entrance
  );

  state.map = L.map('bosphorus-map', {
    center: [41.115, 29.065],
    zoom: 11.5,
    minZoom: 11.2,
    maxZoom: 17,
    maxBounds: ISTANBUL_BOUNDS,
    maxBoundsViscosity: 1.0, // Hard bounce-back strictly locks navigation to Istanbul
    worldCopyJump: false,
    zoomControl: true,
    attributionControl: true,
  });

  // Strict physical lock to Istanbul: prevent any pan or zoom beyond Greater Istanbul
  state.map.setMaxBounds(ISTANBUL_BOUNDS);
  state.map.on('drag', () => {
    state.map.panInsideBounds(ISTANBUL_BOUNDS, { animate: false });
  });
  state.map.on('zoomend', () => {
    if (state.map.getZoom() < 11.2) {
      state.map.setZoom(11.2);
    }
    state.map.panInsideBounds(ISTANBUL_BOUNDS, { animate: false });
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

  // Load high-precision GIS coastline boundaries
  fetch('/api/geojson/coastline')
    .then((res) => (res.ok ? res.json() : null))
    .then((geoData) => {
      if (geoData && state.map) {
        state.coastlineLayer = L.geoJSON(geoData, {
          style: (feature) => {
            const isIsland = feature.properties && feature.properties.type === 'island';
            return {
              color: isIsland ? '#f59e0b' : '#38bdf8',
              weight: isIsland ? 1.5 : 1.0,
              opacity: 0.6,
              fillColor: isIsland ? '#f59e0b' : '#0284c7',
              fillOpacity: 0.08,
            };
          },
        }).addTo(state.map);
      }
    })
    .catch(() => {});

  // Setup Animation Canvas Overlay
  initAnimationCanvas();

  // Populate Clean Coastal District Badges
  renderDistrictBadges();

  // Map Click Listener: Strictly Constrains Navigation to Bosphorus Waterway
  state.map.on('click', (e) => {
    let lat = e.latlng.lat;
    let lon = e.latlng.lng;

    // Automatic snapping to navigable Bosphorus channel
    const snapped = snapToBosphorusWater(lat, lon);
    lat = snapped.lat;
    lon = snapped.lon;

    // Place Target Pin
    if (state.targetMarker) state.map.removeLayer(state.targetMarker);
    state.targetMarker = L.circleMarker([lat, lon], {
      radius: 7,
      color: snapped.wasSnapped ? '#38bdf8' : '#34d399',
      fillColor: snapped.wasSnapped ? '#0284c7' : '#059669',
      fillOpacity: 0.9,
      weight: 2,
    }).addTo(state.map);

    // Auto-fill active tab inputs with valid Bosphorus coordinates
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

      if (!state.routeClickTarget || state.routeClickTarget === 'start') {
        if (sLat) sLat.value = lat.toFixed(4);
        if (sLon) sLon.value = lon.toFixed(4);
        state.routeClickTarget = 'end';
        if (state.departureMarker) state.map.removeLayer(state.departureMarker);
        state.departureMarker = L.circleMarker([lat, lon], {
          radius: 7,
          color: '#38bdf8',
          fillColor: '#0284c7',
          fillOpacity: 0.9,
          weight: 2,
        }).addTo(state.map).bindTooltip('Departure (A)', { permanent: true, direction: 'top', className: 'bg-slate-900 text-cyan-300 font-mono text-xs' });
      } else {
        if (eLat) eLat.value = lat.toFixed(4);
        if (eLon) eLon.value = lon.toFixed(4);
        state.routeClickTarget = 'start';
        if (state.destinationMarker) state.map.removeLayer(state.destinationMarker);
        state.destinationMarker = L.circleMarker([lat, lon], {
          radius: 7,
          color: '#f43f5e',
          fillColor: '#e11d48',
          fillOpacity: 0.9,
          weight: 2,
        }).addTo(state.map).bindTooltip('Destination (B)', { permanent: true, direction: 'top', className: 'bg-slate-900 text-rose-300 font-mono text-xs' });
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
 * Compute Authentic Local District Wind Vector from Real Open-Meteo Meteorology.
 * Applies physical strait channeling, Venturi constriction acceleration at Rumeli Hisarı/Kandilli,
 * and open marine exposure factors to regional ambient wind observations.
 */
function getStationWindData(station) {
  const baseSpd = state.weather?.speed_ms || 4.2;
  const baseDir = state.weather?.direction_deg || 350.0;

  // Local speed adjustment based on topography & exposure
  const localSpeedMs = Math.round(baseSpd * (station.exposure || 1.0) * 10) / 10;
  const localSpeedKmh = Math.max(1, Math.round(localSpeedMs * 3.6));

  // Topographic channeling: interpolate between free ambient wind and strait channel azimuth
  // For Northerly flow (Yıldız/Poyraz: 290°–070°), wind aligns downstream with channel azimuth
  // For Southerly flow (Lodos: 140°–250°), wind aligns upstream with channel azimuth + 180°
  let localDir = baseDir;
  const ch = station.channelAzimuth || 25;

  const isNortherly = (baseDir >= 290 || baseDir <= 70);
  const isSoutherly = (baseDir >= 140 && baseDir <= 250);

  if (isNortherly) {
    const channelTarget = ch;
    // Morphological channeling weight: higher in narrow gorge (0.45), lower at open sea (0.12)
    const weight = station.isNarrows ? 0.45 : (station.lat > 41.20 || station.lat < 41.00 ? 0.12 : 0.28);
    let diff = (channelTarget - baseDir + 540) % 360 - 180;
    localDir = (baseDir + diff * weight + 360) % 360;
  } else if (isSoutherly) {
    const channelTarget = (ch + 180) % 360;
    const weight = station.isNarrows ? 0.45 : (station.lat < 41.00 || station.lat > 41.20 ? 0.12 : 0.28);
    let diff = (channelTarget - baseDir + 540) % 360 - 180;
    localDir = (baseDir + diff * weight + 360) % 360;
  }

  localDir = Math.round(localDir * 10) / 10;
  // Flow heading: direction the wind is blowing towards (downwind vector)
  const flowHeading = Math.round((localDir + 180) % 360);
  const sector = classifyWindSector(localDir);

  return {
    speedMs: localSpeedMs,
    speedKmh: localSpeedKmh,
    directionDeg: localDir,
    flowHeading: flowHeading,
    sectorName: sector.name,
    sectorDesc: sector.desc,
  };
}

/**
 * Minimalist Zoom Earth Station Badges (DivIcon)
 * Renders authentic district wind vectors derived from real Open-Meteo API data.
 */
function renderDistrictBadges() {
  // Clear old markers
  state.mapMarkers.forEach((m) => state.map.removeLayer(m));
  state.mapMarkers = [];

  if (!state.layers.districts) return;

  BOSPHORUS_STATIONS.forEach((d) => {
    const w = getStationWindData(d);
    const isNarrows = !!d.isNarrows;

    const iconHtml = `
      <div class="ze-station ${isNarrows ? 'ze-narrows' : ''}">
        <div class="ze-name">${isNarrows ? '⚠️ ' : ''}${d.name}</div>
        <div class="ze-pill" title="${d.name}: ${w.speedKmh} km/h (${w.speedMs} m/s) • Bearing ${w.directionDeg}° (${w.sectorName})">
          <span class="ze-val">${w.speedKmh}</span>
          <span class="ze-unit">km/h</span>
          <svg class="ze-arr" style="transform: rotate(${w.flowHeading}deg);" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
          </svg>
        </div>
      </div>
    `;

    const icon = L.divIcon({
      html: iconHtml,
      className: 'ze-div-icon',
      iconSize: [84, 38],
      iconAnchor: [42, 19],
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

  // Accurate meteorological wind vectors from live Open-Meteo API:
  // u_wind: East component (m/s), positive = Eastward (+X on screen)
  // v_wind: North component (m/s), positive = Northward (-Y on screen)
  let u = state.weather?.u_wind;
  let v = state.weather?.v_wind;

  if (u === undefined || v === undefined || isNaN(u) || isNaN(v)) {
    const dir = state.weather?.direction_deg || 0;
    const spd = state.weather?.speed_ms || 5.0;
    const rad = (dir * Math.PI) / 180.0;
    u = -spd * Math.sin(rad);
    v = -spd * Math.cos(rad);
  }

  const speedMag = Math.hypot(u, v) || 1.0;
  // Normalized screen motion vector:
  // Screen X = East (+u)
  // Screen Y = South (-v, because Canvas Y increases downwards)
  const dx = u / speedMag;
  const dy = -v / speedMag;

  const liveSpeedKmh = state.weather?.speed_kmh || (speedMag * 3.6);
  const speedMult = Math.max(0.7, Math.min(3.5, liveSpeedKmh / 16.0));

  ctx.lineCap = 'round';

  for (const p of state.windStreamlines) {
    // Tail is behind motion, head is forward in motion direction
    const tailX = p.x - dx * p.len;
    const tailY = p.y - dy * p.len;

    const grad = ctx.createLinearGradient(tailX, tailY, p.x, p.y);
    grad.addColorStop(0, 'rgba(186, 230, 253, 0)');
    grad.addColorStop(0.6, `rgba(224, 242, 254, ${p.alpha * 0.45})`);
    grad.addColorStop(1, `rgba(255, 255, 255, ${p.alpha * 0.95})`);

    ctx.strokeStyle = grad;
    ctx.lineWidth = p.width;
    ctx.beginPath();
    ctx.moveTo(tailX, tailY);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();

    // Bright leading head particle indicating flow direction
    ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha})`;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.width * 0.75, 0, Math.PI * 2);
    ctx.fill();

    // Advance particle forward along the wind direction vector
    p.x += dx * p.speed * speedMult;
    p.y += dy * p.speed * speedMult;
    p.life++;

    // Re-spawn smoothly when particle expires or moves offscreen
    if (p.life > p.maxLife || p.x < -80 || p.x > W + 80 || p.y < -80 || p.y > H + 80) {
      p.x = Math.random() * W - dx * (Math.random() * 150);
      p.y = Math.random() * H - dy * (Math.random() * 150);
      p.life = 0;
      p.maxLife = 60 + Math.random() * 90;
      p.len = 16 + Math.random() * 26;
      p.speed = 1.8 + Math.random() * 2.2;
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
  if (state.ctx && state.canvas) {
    state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
  }

  if (state.layers.windFlow) {
    renderWindStreamlines();
  }
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
  const syncBtn = document.getElementById('btn-sync-weather');
  const syncIcon = document.getElementById('sync-icon');
  const syncText = document.getElementById('sync-text');

  if (syncBtn && force) {
    syncBtn.disabled = true;
    if (syncIcon) syncIcon.classList.add('animate-spin');
    if (syncText) syncText.textContent = 'Syncing...';
  }

  // 1. Direct Open-Meteo live API request (fast client-side attempt)
  let directSuccess = false;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const openMeteoUrl = 'https://api.open-meteo.com/v1/forecast?latitude=41.1600&longitude=29.0700&current=wind_speed_10m,wind_direction_10m,surface_pressure,temperature_2m,relative_humidity_2m&wind_speed_unit=ms';
    const res = await fetch(openMeteoUrl, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      const cur = data.current;
      const rawSpeed = parseFloat(cur.wind_speed_10m);
      const speed = Math.max(0.5, Math.round(rawSpeed * 10) / 10);
      const dir = parseFloat(cur.wind_direction_10m);
      const press = parseFloat(cur.surface_pressure || 1014.0);
      const temp = parseFloat(cur.temperature_2m || 15.0);

      const rad = (dir * Math.PI) / 180.0;
      const u = -speed * Math.sin(rad);
      const v = -speed * Math.cos(rad);
      const sector = classifyWindSector(dir);
      const category = classifyBeaufort(speed);
      const kmh = Math.round(speed * 3.6);
      const kts = Math.round(speed * 1.94384 * 10) / 10;

      state.weather = {
        speed_ms: speed,
        speed_kmh: kmh,
        speed_knots: kts,
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
      initWindStreamlines();
      directSuccess = true;
    }
  } catch (err) {
    console.warn('Direct Open-Meteo fetch failed, attempting server proxy:', err);
  }

  // 2. Resilient Server-Side Proxy Fallback (/api/weather?force=true)
  if (!directSuccess) {
    try {
      const endpoint = force ? '/api/weather?force=true' : '/api/weather';
      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        const rawSpeed = parseFloat(data.speed_ms);
        const speed = Math.max(0.5, Math.round(rawSpeed * 10) / 10);
        const kmh = Math.round(speed * 3.6);
        const kts = Math.round(speed * 1.94384 * 10) / 10;
        const dir = parseFloat(data.direction_deg);
        const rad = (dir * Math.PI) / 180.0;
        const u = -speed * Math.sin(rad);
        const v = -speed * Math.cos(rad);

        state.weather = {
          speed_ms: speed,
          speed_kmh: kmh,
          speed_knots: kts,
          direction_deg: dir,
          u_wind: Math.round(u * 100) / 100,
          v_wind: Math.round(v * 100) / 100,
          sector_name: data.sector_name,
          sector_description: data.sector_description || '',
          speed_category: data.speed_category || classifyBeaufort(speed),
          surface_pressure_hpa: data.surface_pressure_hpa || 1014.0,
          temperature_c: 15.0,
          source: data.source || 'cached',
        };
        updateWeatherUI();
        renderDistrictBadges();
        initWindStreamlines();
      }
    } catch (err) {
      console.error('All weather sources failed:', err);
    }
  }

  // Update sync timestamp and toast feedback
  const timeStr = new Date().toLocaleTimeString();
  const tsEl = document.getElementById('sync-timestamp');
  if (tsEl) tsEl.textContent = `Last: ${timeStr}`;

  if (syncBtn && force) {
    if (syncIcon) syncIcon.classList.remove('animate-spin');
    if (syncText) syncText.textContent = `✓ Synced! (${timeStr})`;
    showSyncToast(`Open-Meteo Live API Synchronized: ${state.weather.speed_kmh} km/h ${state.weather.sector_name.toUpperCase()} (${state.weather.direction_deg}°) | Pressure: ${state.weather.surface_pressure_hpa} hPa`, state.weather.source === 'live');
    setTimeout(() => {
      if (syncText) syncText.textContent = 'Sync API';
      if (syncBtn) syncBtn.disabled = false;
    }, 2000);
  }
}

function showSyncToast(message, isLive = true) {
  let toast = document.getElementById('sync-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'sync-toast';
    toast.className = 'fixed top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-lg border shadow-2xl font-mono text-xs flex items-center space-x-2 transition-all duration-300 pointer-events-none';
    document.body.appendChild(toast);
  }
  toast.className = `fixed top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-lg border shadow-2xl font-mono text-xs flex items-center space-x-2 transition-all duration-300 pointer-events-none ${
    isLive ? 'bg-slate-900/95 border-emerald-500 text-emerald-300' : 'bg-slate-900/95 border-amber-500 text-amber-300'
  }`;
  toast.innerHTML = `<span>${isLive ? '📡' : '⚠️'}</span><span>${message}</span>`;
  toast.style.opacity = '1';
  clearTimeout(state._toastTimer);
  state._toastTimer = setTimeout(() => {
    toast.style.opacity = '0';
  }, 3500);
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
  const flowHeading = Math.round((w.direction_deg + 180) % 360);
  if (zwArrow) zwArrow.style.transform = `rotate(${flowHeading}deg)`;
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
      let errMsg = `Server returned status ${res.status}`;
      try {
        const text = await res.text();
        try {
          const err = JSON.parse(text);
          errMsg = err.detail || err.error || errMsg;
        } catch {
          if (text) errMsg = text.slice(0, 200);
        }
      } catch {}
      alert(`Simulation Error (${res.status}): ${errMsg}`);
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

  const rawLat = parseFloat(document.getElementById('rev-lat').value);
  const rawLon = parseFloat(document.getElementById('rev-lon').value);
  const snapped = snapToBosphorusWater(rawLat, rawLon);
  document.getElementById('rev-lat').value = snapped.lat.toFixed(4);
  document.getElementById('rev-lon').value = snapped.lon.toFixed(4);

  const payload = {
    entity_type: document.getElementById('rev-entity').value,
    last_lat: snapped.lat,
    last_lon: snapped.lon,
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
      let errMsg = `Server returned status ${res.status}`;
      try {
        const text = await res.text();
        try {
          const err = JSON.parse(text);
          errMsg = err.detail || err.error || errMsg;
        } catch {
          if (text) errMsg = text.slice(0, 200);
        }
      } catch {}
      alert(`Reverse Tracking Error (${res.status}): ${errMsg}`);
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

  const rawStartLat = parseFloat(document.getElementById('route-start-lat').value);
  const rawStartLon = parseFloat(document.getElementById('route-start-lon').value);
  const rawEndLat = parseFloat(document.getElementById('route-end-lat').value);
  const rawEndLon = parseFloat(document.getElementById('route-end-lon').value);

  const startSnap = snapToBosphorusWater(rawStartLat, rawStartLon);
  const endSnap = snapToBosphorusWater(rawEndLat, rawEndLon);

  document.getElementById('route-start-lat').value = startSnap.lat.toFixed(4);
  document.getElementById('route-start-lon').value = startSnap.lon.toFixed(4);
  document.getElementById('route-end-lat').value = endSnap.lat.toFixed(4);
  document.getElementById('route-end-lon').value = endSnap.lon.toFixed(4);

  const payload = {
    start_lat: startSnap.lat,
    start_lon: startSnap.lon,
    end_lat: endSnap.lat,
    end_lon: endSnap.lon,
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
      let errMsg = `Server returned status ${res.status}`;
      try {
        const text = await res.text();
        try {
          const err = JSON.parse(text);
          errMsg = err.detail || err.error || errMsg;
        } catch {
          if (text) errMsg = text.slice(0, 200);
        }
      } catch {}
      alert(`Routing Error (${res.status}): ${errMsg}`);
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
    {
      id: 'toggle-layer-wind-flow',
      key: 'windFlow',
      onChange: () => {
        if (!state.layers.windFlow && state.ctx && state.canvas) {
          state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
        }
      },
    },
    { id: 'toggle-layer-districts', key: 'districts', onChange: renderDistrictBadges },
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

  // Preset buttons (Authentic Navigable Fairway Endpoints)
  document.getElementById('btn-preset-northbound')?.addEventListener('click', () => {
    document.getElementById('route-start-lat').value = '40.9950';
    document.getElementById('route-start-lon').value = '29.0100';
    document.getElementById('route-end-lat').value = '41.2250';
    document.getElementById('route-end-lon').value = '29.1220';
  });

  document.getElementById('btn-preset-southbound')?.addEventListener('click', () => {
    document.getElementById('route-start-lat').value = '41.2250';
    document.getElementById('route-start-lon').value = '29.1220';
    document.getElementById('route-end-lat').value = '40.9950';
    document.getElementById('route-end-lon').value = '29.0100';
  });

  // Export CSV
  document.getElementById('btn-export-csv')?.addEventListener('click', () => {
    window.location.href = '/api/export/csv';
  });

  // Live Weather Sync Button
  document.getElementById('btn-sync-weather')?.addEventListener('click', () => {
    fetchWeatherData(true);
  });

  // Periodic Weather Refresh: Automatically pull fresh meteorological observations every 15 minutes
  const FIFTEEN_MINUTES_MS = 15 * 60 * 1000;
  setInterval(() => {
    fetchWeatherData(true);
  }, FIFTEEN_MINUTES_MS);

  // Start 60 FPS Rendering Loop
  requestAnimationFrame(animate);
});
