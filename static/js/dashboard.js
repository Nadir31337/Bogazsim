/**
 * BoğazSim — Maritime Mission-Control Dashboard Client (Enhanced Digital Twin)
 *
 * Handles continuous analytical S-curve rendering of the Bosphorus Strait,
 * suspension bridges, geographic landmark namings from Karadeniz to Marmara,
 * live Open-Meteo meteorological API integration with interactive wind compass,
 * hydrodynamic flow advection, Monte Carlo SAR swarms, reverse datum backtracking,
 * and weighted A* passage navigation.
 */

// Geographic domain constants matching core.constants
const LAT_MIN = 40.98;
const LAT_MAX = 41.25;
const LON_MIN = 28.95;
const LON_MAX = 29.20;
const CONSTRICTION_LAT = 41.085;
const CONSTRICTION_LON = 29.0786;
const METERS_PER_DEG_LON = 83865.0;

// Application State
const state = {
  grid: null,
  weather: {
    speed_ms: 8.5,
    direction_deg: 45.0,
    u_wind: -6.01,
    v_wind: -6.01,
    sector_name: 'Poyraz',
    sector_description: 'North-East (NE) — Dominant high-speed prevailing wind',
    speed_category: 'Fresh Breeze',
    surface_pressure_hpa: 1014.0,
    temperature_c: 16.2,
    source: 'loading',
  },
  layers: {
    landmarks: true,
    flow: true,
    tss: true,
    vectors: false,
    wind: true,
  },
  currentSim: null,
  currentRoute: null,
  activeTab: 'forward',
  animating: false,
  animationStep: 0,
  maxSteps: 0,
  streamParticles: [],
  windParticles: [],
  mousePos: { lat: 0, lon: 0, isWater: false, speed: 0.0, depth: 0.0 },
};

// Canvas & Context References
let canvas, ctx;

/**
 * Coordinate Transformations
 * Converts geographic WGS84 (lat, lon) to Canvas (x, y) pixels
 */
function latLonToCanvas(lat, lon) {
  const normX = (lon - LON_MIN) / (LON_MAX - LON_MIN);
  const normY = 1.0 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN);
  return {
    x: normX * canvas.width,
    y: normY * canvas.height,
  };
}

function canvasToLatLon(x, y) {
  const normX = x / canvas.width;
  const normY = y / canvas.height;
  const lon = LON_MIN + normX * (LON_MAX - LON_MIN);
  const lat = LAT_MIN + (1.0 - normY) * (LAT_MAX - LAT_MIN);
  return { lat, lon };
}

/**
 * Analytical S-Curve Geometry Functions matching core.grid_engine
 */
function getCenterlineLon(lat) {
  const t = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN);
  const base_lon = 28.995 + 0.135 * t;
  const s_bend = 0.025 * Math.sin(2.0 * Math.PI * t);
  const narrows_bias = 0.015 * Math.exp(-Math.pow((lat - CONSTRICTION_LAT) / 0.04, 2));
  return base_lon + s_bend + narrows_bias;
}

function getStraitHalfWidthDeg(lat) {
  const dist_from_throat = Math.abs(lat - CONSTRICTION_LAT) / (LAT_MAX - LAT_MIN);
  const width_ratio = Math.min(1.0, dist_from_throat * 2.5);
  const width_m = 700.0 + (3500.0 - 700.0) * Math.pow(width_ratio, 1.5);
  return (width_m / 2.0) / METERS_PER_DEG_LON;
}

function isCoordInWater(lat, lon) {
  if (lat < LAT_MIN || lat > LAT_MAX || lon < LON_MIN || lon > LON_MAX) return false;
  const cLon = getCenterlineLon(lat);
  const halfW = getStraitHalfWidthDeg(lat);
  const dLon = Math.abs(lon - cLon);
  return dLon <= halfW;
}

function getWaterSpeedAndDepth(lat, lon) {
  if (!isCoordInWater(lat, lon)) return { isWater: false, speed: 0.0, depth: 0.0 };
  const cLon = getCenterlineLon(lat);
  const halfW = getStraitHalfWidthDeg(lat);
  const dLon = Math.abs(lon - cLon);
  const frac = Math.max(0.0, 1.0 - Math.pow(dLon / halfW, 2));
  const depth = Math.max(10.0, 65.0 * frac);

  const throatRatio = 350.0 / (halfW * METERS_PER_DEG_LON);
  const speed = 1.0 + (2.5 - 1.0) * Math.min(1.0, throatRatio);
  return { isWater: true, speed, depth };
}

/**
 * Bosphorus Landmark Catalog from Karadeniz to Marmara
 */
const BOSPHORUS_LANDMARKS = [
  // Northern Entrance (Black Sea)
  { name: 'KARADENİZ (BLACK SEA)', lat: 41.246, lon: 29.115, type: 'sea', align: 'center' },
  { name: 'Rumeli Feneri', lat: 41.235, lon: 29.096, type: 'lighthouse', align: 'left' },
  { name: 'Anadolu Feneri', lat: 41.218, lon: 29.152, type: 'lighthouse', align: 'right' },
  { name: 'Garipçe', lat: 41.205, lon: 29.102, type: 'village', align: 'left' },
  { name: 'Poyrazköy', lat: 41.205, lon: 29.132, type: 'village', align: 'right' },

  // Upper Bosphorus Reach
  { name: 'Büyükdere & Sarıyer', lat: 41.165, lon: 29.052, type: 'town', align: 'left' },
  { name: 'Beykoz', lat: 41.135, lon: 29.102, type: 'town', align: 'right' },
  { name: 'Tarabya', lat: 41.137, lon: 29.058, type: 'town', align: 'left' },
  { name: 'Yeniköy', lat: 41.120, lon: 29.070, type: 'town', align: 'left' },
  { name: 'Paşabahçe & Çubuklu', lat: 41.114, lon: 29.090, type: 'town', align: 'right' },
  { name: 'Kanlıca', lat: 41.100, lon: 29.066, type: 'town', align: 'right' },

  // Narrows / The Throat (Rumeli - Anadolu Hisarı)
  { name: 'Rumeli Hisarı', lat: 41.085, lon: 29.054, type: 'fortress', align: 'left' },
  { name: 'Anadolu Hisarı', lat: 41.083, lon: 29.068, type: 'fortress', align: 'right' },

  // Middle Bosphorus & Eddy Zones
  { name: 'Bebek Koyu', lat: 41.077, lon: 29.040, type: 'eddy', align: 'left' },
  { name: 'Kandilli Burnu', lat: 41.075, lon: 29.062, type: 'cape', align: 'right' },
  { name: 'Akıntıburnu (Şeytan Akıntısı ~5 kts)', lat: 41.068, lon: 29.041, type: 'current', align: 'left' },

  // Lower Bosphorus & Historic Core
  { name: 'Ortaköy', lat: 41.048, lon: 29.025, type: 'town', align: 'left' },
  { name: 'Beylerbeyi', lat: 41.042, lon: 29.046, type: 'town', align: 'right' },
  { name: 'Beşiktaş / Dolmabahçe', lat: 41.038, lon: 28.998, type: 'town', align: 'left' },
  { name: 'Üsküdar', lat: 41.025, lon: 29.014, type: 'town', align: 'right' },
  { name: 'Kız Kulesi (Maiden\'s Tower)', lat: 41.0211, lon: 29.0041, type: 'tower', align: 'center' },
  { name: 'Haliç (Golden Horn)', lat: 41.022, lon: 28.975, type: 'inlet', align: 'left' },
  { name: 'Sarayburnu (Topkapı)', lat: 41.017, lon: 28.983, type: 'cape', align: 'left' },
  { name: 'Haydarpaşa & Kadıköy', lat: 40.995, lon: 29.022, type: 'port', align: 'right' },

  // Southern Mouth (Marmara Sea)
  { name: 'MARMARA DENİZİ (SEA OF MARMARA)', lat: 40.982, lon: 29.030, type: 'sea', align: 'center' },
];

/**
 * 3 Iconic Suspension Bridges
 */
const BOSPHORUS_BRIDGES = [
  {
    name: 'Yavuz Sultan Selim Köprüsü (3. Köprü)',
    lat: 41.203,
    westLon: 29.102,
    eastLon: 29.132,
    pylonColor: '#f59e0b',
  },
  {
    name: 'Fatih Sultan Mehmet Köprüsü (FSM / 2. Köprü)',
    lat: 41.091,
    westLon: 29.056,
    eastLon: 29.072,
    pylonColor: '#38bdf8',
  },
  {
    name: '15 Temmuz Şehitler Köprüsü (1. Köprü)',
    lat: 41.045,
    westLon: 29.026,
    eastLon: 29.044,
    pylonColor: '#34d399',
  },
];

/**
 * Canonical Istanbul Nautical Wind Sectors
 */
const WIND_SECTORS = {
  Yıldız: { min: 337.5, max: 22.5, desc: 'North (N) — Cold Black Sea flow' },
  Poyraz: { min: 22.5, max: 67.5, desc: 'North-East (NE) — Dominant prevailing maritime wind' },
  Gündoğusu: { min: 67.5, max: 112.5, desc: 'East (E) — Mild continental breeze' },
  Keşişleme: { min: 112.5, max: 157.5, desc: 'South-East (SE) — Warm dry breeze' },
  Kıble: { min: 157.5, max: 202.5, desc: 'South (S) — Warm southerly Mediterranean front' },
  Lodos: { min: 202.5, max: 247.5, desc: 'South-West (SW) — Storm squalls, heavy chop and swells' },
  Günbatısı: { min: 247.5, max: 292.5, desc: 'West (W) — Maritime westerly front' },
  Karayel: { min: 292.5, max: 337.5, desc: 'North-West (NW) — Cold, gusty storm winds' },
};

function classifyWindSector(degrees) {
  const deg = (degrees % 360 + 360) % 360;
  for (const [name, sec] of Object.entries(WIND_SECTORS)) {
    if (sec.min > sec.max) {
      if (deg >= sec.min || deg < sec.max) return { name, desc: sec.desc };
    } else {
      if (deg >= sec.min && deg < sec.max) return { name, desc: sec.desc };
    }
  }
  return { name: 'Poyraz', desc: WIND_SECTORS.Poyraz.desc };
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
  return 'Storm / Hurricane Force';
}

/**
 * Live Open-Meteo Weather Fetcher with Local Fallback
 */
async function fetchWeatherData(force = false) {
  const statusEl = document.getElementById('weather-status');
  const sourceEl = document.getElementById('weather-source-badge');
  const sidebarSourceEl = document.getElementById('sidebar-weather-source');

  // Try direct Open-Meteo API query from the browser first (100% live and accurate)
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
      const press = parseFloat(cur.surface_pressure || 1013.25);
      const temp = parseFloat(cur.temperature_2m || 16.0);

      const rad = (dir * Math.PI) / 180.0;
      const u = -speed * Math.sin(rad);
      const v = -speed * Math.cos(rad);
      const sector = classifyWindSector(dir);
      const category = classifyBeaufort(speed);

      state.weather = {
        speed_ms: Math.round(speed * 10) / 10,
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
      updateWeatherHUD();
      initWindParticles();
      return;
    }
  } catch (err) {
    console.warn('Browser direct Open-Meteo fetch timed out, falling back to backend:', err);
  }

  // Fallback to local backend API /api/weather
  try {
    const res = await fetch('/api/weather');
    if (res.ok) {
      const data = await res.json();
      state.weather = {
        speed_ms: data.speed_ms,
        direction_deg: data.direction_deg,
        u_wind: data.u_wind,
        v_wind: data.v_wind,
        sector_name: data.sector_name,
        sector_description: data.sector_description || '',
        speed_category: data.speed_category || classifyBeaufort(data.speed_ms),
        surface_pressure_hpa: data.surface_pressure_hpa || 1013.25,
        temperature_c: 16.2,
        source: data.source || 'cached',
      };
      updateWeatherHUD();
      initWindParticles();
    }
  } catch (err) {
    console.error('All weather sources failed:', err);
  }
}

function updateWeatherHUD() {
  const w = state.weather;
  const kts = (w.speed_ms * 1.94384).toFixed(1);

  // Header Pill
  const statusEl = document.getElementById('weather-status');
  if (statusEl) {
    statusEl.textContent = `${w.sector_name.toUpperCase()} (${w.direction_deg}° ${w.speed_ms} m/s | ${kts} kts)`;
  }
  const badgeEl = document.getElementById('weather-source-badge');
  if (badgeEl) {
    badgeEl.textContent = w.source === 'live' ? 'LIVE API' : 'SYNTHETIC';
    badgeEl.className = w.source === 'live'
      ? 'text-[10px] uppercase px-1.5 py-0.2 rounded bg-emerald-950 border border-emerald-700 text-emerald-300'
      : 'text-[10px] uppercase px-1.5 py-0.2 rounded bg-amber-950 border border-amber-700 text-amber-300';
  }

  // Sidebar Meteorology Card
  const sSector = document.getElementById('wx-sector');
  if (sSector) sSector.textContent = `${w.sector_name.toUpperCase()}`;
  const sDeg = document.getElementById('wx-deg');
  if (sDeg) sDeg.textContent = `Bearing: ${w.direction_deg}° (${w.speed_category})`;
  const sSpeed = document.getElementById('wx-speed');
  if (sSpeed) sSpeed.textContent = `${w.speed_ms} m/s`;
  const sKnots = document.getElementById('wx-knots');
  if (sKnots) sKnots.textContent = `(${kts} kts)`;
  const sTemp = document.getElementById('wx-temp');
  if (sTemp) sTemp.textContent = `${w.temperature_c}°C`;
  const sPress = document.getElementById('wx-press');
  if (sPress) sPress.textContent = `${w.surface_pressure_hpa} hPa`;
  const sSource = document.getElementById('sidebar-weather-source');
  if (sSource) sSource.textContent = w.source === 'live' ? 'OPEN-METEO LIVE' : 'SYNTHETIC BACKUP';
}

/**
 * Initialize Continuous Streamline Particles & Wind Ambient Streaks
 */
function initStreamParticles() {
  state.streamParticles = [];
  const count = 180;
  for (let i = 0; i < count; i++) {
    const lat = LAT_MIN + Math.random() * (LAT_MAX - LAT_MIN);
    const cLon = getCenterlineLon(lat);
    const halfW = getStraitHalfWidthDeg(lat);
    const lon = cLon + (Math.random() - 0.5) * halfW * 1.6;

    state.streamParticles.push({
      lat,
      lon,
      life: Math.random() * 120,
      maxLife: 100 + Math.random() * 100,
    });
  }
}

function initWindParticles() {
  state.windParticles = [];
  const count = 60;
  for (let i = 0; i < count; i++) {
    state.windParticles.push({
      x: Math.random() * (canvas ? canvas.width : 1400),
      y: Math.random() * (canvas ? canvas.height : 950),
      len: 15 + Math.random() * 25,
      speed: 1.5 + Math.random() * 2.0,
      alpha: 0.15 + Math.random() * 0.25,
    });
  }
}

/**
 * Fetch Grid Metadata & Surface Current Vectors
 */
async function fetchGridData() {
  try {
    const res = await fetch('/api/grid');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.grid = await res.json();
  } catch (err) {
    console.error('Failed to load grid data:', err);
  }
}

/**
 * Initialize Canvas & Viewport Sizing
 */
function initCanvas() {
  canvas = document.getElementById('bosphorus-canvas');
  if (!canvas) return;
  ctx = canvas.getContext('2d');

  initStreamParticles();
  initWindParticles();

  // Mouse Move Listener for Coordinate Telemetry HUD
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const canvasX = (e.clientX - rect.left) * scaleX;
    const canvasY = (e.clientY - rect.top) * scaleY;
    const { lat, lon } = canvasToLatLon(canvasX, canvasY);

    const { isWater, speed, depth } = getWaterSpeedAndDepth(lat, lon);
    state.mousePos = { lat, lon, isWater, speed, depth };

    const coordsDisplay = document.getElementById('cursor-coords');
    if (coordsDisplay) {
      if (isWater) {
        coordsDisplay.textContent = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E | WATER (${speed.toFixed(1)} m/s, ${depth.toFixed(0)}m depth)`;
      } else {
        coordsDisplay.textContent = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E | LAND TERRAIN`;
      }
    }
  });

  // Canvas Click Listener for Coordinate Auto-Fill
  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const canvasX = (e.clientX - rect.left) * scaleX;
    const canvasY = (e.clientY - rect.top) * scaleY;
    const { lat, lon } = canvasToLatLon(canvasX, canvasY);

    if (state.activeTab === 'forward') {
      const latInput = document.getElementById('fwd-lat');
      const lonInput = document.getElementById('fwd-lon');
      if (latInput) latInput.value = lat.toFixed(4);
      if (lonInput) lonInput.value = lon.toFixed(4);
    } else if (state.activeTab === 'reverse') {
      const latInput = document.getElementById('rev-lat');
      const lonInput = document.getElementById('rev-lon');
      if (latInput) latInput.value = lat.toFixed(4);
      if (lonInput) lonInput.value = lon.toFixed(4);
    } else if (state.activeTab === 'route') {
      const startLat = document.getElementById('route-start-lat');
      const startLon = document.getElementById('route-start-lon');
      const endLat = document.getElementById('route-end-lat');
      const endLon = document.getElementById('route-end-lon');
      if (startLat && (!startLat.value || endLat.value)) {
        startLat.value = lat.toFixed(4);
        if (startLon) startLon.value = lon.toFixed(4);
      } else if (endLat) {
        endLat.value = lat.toFixed(4);
        if (endLon) endLon.value = lon.toFixed(4);
      }
    }
  });
}

/**
 * Renders the High-Definition Realistic Bosphorus Digital Twin
 */
function renderBaseMap() {
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;

  // 1. Deep Topographic Landmass Background
  ctx.fillStyle = '#0a1122';
  ctx.fillRect(0, 0, W, H);

  // Subtle Elevation Contour Shading for Hills of Istanbul
  ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
  ctx.lineWidth = 1;
  for (let r = 120; r < W; r += 220) {
    ctx.beginPath();
    ctx.arc(r, H * 0.4, 180, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(r + 80, H * 0.75, 240, 0, Math.PI * 2);
    ctx.stroke();
  }

  // 2. Continental Watermark Typography
  ctx.fillStyle = 'rgba(148, 163, 184, 0.12)';
  ctx.font = 'bold 26px sans-serif';
  ctx.letterSpacing = '6px';
  ctx.fillText('AVRUPA YAKASI (EUROPE)', W * 0.08, H * 0.45);
  ctx.fillText('ANADOLU YAKASI (ASIA)', W * 0.68, H * 0.45);

  // 3. Construct Continuous Analytical Shoreline Curves (European and Asian Banks)
  const steps = 300;
  const dLat = (LAT_MAX - LAT_MIN) / steps;
  const westPoints = [];
  const eastPoints = [];

  for (let i = 0; i <= steps; i++) {
    const lat = LAT_MAX - i * dLat;
    const cLon = getCenterlineLon(lat);
    let halfW = getStraitHalfWidthDeg(lat);

    // Natural Coastal Micro-Variations
    let westOffset = 0;
    let eastOffset = 0;

    // Golden Horn Inlet (Haliç) around 41.020°N
    if (lat > 41.015 && lat < 41.035) {
      const hFrac = Math.sin(((lat - 41.015) / 0.02) * Math.PI);
      westOffset -= 0.012 * hFrac;
    }
    // Bebek Bay Indentation around 41.077°N
    if (lat > 41.072 && lat < 41.082) {
      const bFrac = Math.sin(((lat - 41.072) / 0.01) * Math.PI);
      westOffset -= 0.004 * bFrac;
    }
    // Tarabya Bay around 41.137°N
    if (lat > 41.132 && lat < 41.142) {
      const tFrac = Math.sin(((lat - 41.132) / 0.01) * Math.PI);
      westOffset -= 0.0035 * tFrac;
    }
    // Kandilli Promontory around 41.075°N (sharp Asian point)
    if (lat > 41.070 && lat < 41.080) {
      const kFrac = Math.sin(((lat - 41.070) / 0.01) * Math.PI);
      eastOffset -= 0.003 * kFrac;
    }
    // Beykoz Cove around 41.135°N
    if (lat > 41.130 && lat < 41.140) {
      const bkFrac = Math.sin(((lat - 41.130) / 0.01) * Math.PI);
      eastOffset += 0.004 * bkFrac;
    }

    const wPt = latLonToCanvas(lat, cLon - halfW + westOffset);
    const ePt = latLonToCanvas(lat, cLon + halfW + eastOffset);
    westPoints.push(wPt);
    eastPoints.push(ePt);
  }

  // 4. Fill Rich Hydrodynamic Ocean Water Polygon
  ctx.beginPath();
  // Move down European Shore
  ctx.moveTo(westPoints[0].x, westPoints[0].y);
  for (let i = 1; i < westPoints.length; i++) {
    ctx.lineTo(westPoints[i].x, westPoints[i].y);
  }
  // Cross southern mouth (Marmara)
  ctx.lineTo(eastPoints[eastPoints.length - 1].x, eastPoints[eastPoints.length - 1].y);
  // Move up Asian Shore
  for (let i = eastPoints.length - 2; i >= 0; i--) {
    ctx.lineTo(eastPoints[i].x, eastPoints[i].y);
  }
  ctx.closePath();

  // Multi-Stop Depth & Velocity Ocean Gradient
  const waterGrad = ctx.createLinearGradient(0, 0, 0, H);
  waterGrad.addColorStop(0.0, '#0c2a4a'); // Deep Black Sea
  waterGrad.addColorStop(0.25, '#0e3860'); // Beykoz reach
  waterGrad.addColorStop(0.48, '#0891b2'); // Rumeli Hisarı High-Speed Constriction
  waterGrad.addColorStop(0.55, '#0284c7'); // Bebek-Kandilli
  waterGrad.addColorStop(0.75, '#0e3860'); // Beşiktaş-Üsküdar
  waterGrad.addColorStop(1.0, '#0c2a4a'); // Marmara Entrance
  ctx.fillStyle = waterGrad;
  ctx.fill();

  // 5. Glowing Shoreline Contours
  // Outer Surf Glow
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.22)';
  ctx.lineWidth = 5;
  ctx.stroke();

  // Inner Crisp Coastline Edge
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.75)';
  ctx.lineWidth = 1.8;
  ctx.stroke();

  // 6. International Maritime TSS Fairway Lanes (Traffic Separation Scheme)
  if (state.layers.tss) {
    ctx.lineWidth = 1.2;
    ctx.setLineDash([6, 6]);

    // Southbound Commercial Lane (Red/Rose track on European side)
    ctx.strokeStyle = 'rgba(244, 63, 94, 0.45)';
    ctx.beginPath();
    for (let i = 0; i <= steps; i += 4) {
      const lat = LAT_MAX - i * dLat;
      const cLon = getCenterlineLon(lat);
      const halfW = getStraitHalfWidthDeg(lat);
      const pt = latLonToCanvas(lat, cLon - halfW * 0.42);
      if (i === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    }
    ctx.stroke();

    // Northbound Commercial Lane (Emerald track on Asian side)
    ctx.strokeStyle = 'rgba(52, 211, 153, 0.45)';
    ctx.beginPath();
    for (let i = 0; i <= steps; i += 4) {
      const lat = LAT_MAX - i * dLat;
      const cLon = getCenterlineLon(lat);
      const halfW = getStraitHalfWidthDeg(lat);
      const pt = latLonToCanvas(lat, cLon + halfW * 0.42);
      if (i === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    }
    ctx.stroke();

    // Neutral Separation Centerline
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.3)';
    ctx.beginPath();
    for (let i = 0; i <= steps; i += 6) {
      const lat = LAT_MAX - i * dLat;
      const cLon = getCenterlineLon(lat);
      const pt = latLonToCanvas(lat, cLon);
      if (i === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // 7. Hydrodynamic Current Vector Quivers
  if (state.layers.vectors && state.grid && state.grid.downsampled_vectors) {
    ctx.lineWidth = 1.2;
    for (const vec of state.grid.downsampled_vectors) {
      if (!vec.is_land && vec.speed > 0.3) {
        const { x, y } = latLonToCanvas(vec.lat, vec.lon);
        const arrowLen = Math.min(22, vec.speed * 9);
        const angle = Math.atan2(-vec.v, vec.u);

        ctx.strokeStyle = vec.speed > 2.0 ? 'rgba(251, 191, 36, 0.5)' : 'rgba(56, 189, 248, 0.35)';
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + Math.cos(angle) * arrowLen, y + Math.sin(angle) * arrowLen);
        ctx.stroke();
      }
    }
  }

  // 8. Continuous Flowing Hydrodynamic Streamline Particles
  if (state.layers.flow && state.streamParticles.length > 0) {
    for (const p of state.streamParticles) {
      const { x, y } = latLonToCanvas(p.lat, p.lon);
      const { speed } = getWaterSpeedAndDepth(p.lat, p.lon);

      ctx.fillStyle = speed > 2.0 ? 'rgba(251, 191, 36, 0.7)' : 'rgba(52, 211, 153, 0.55)';
      ctx.beginPath();
      ctx.arc(x, y, 1.6, 0, 2 * Math.PI);
      ctx.fill();

      // Advect southward along the S-channel with local speed
      const dtLat = 0.00035 * (speed || 1.2);
      p.lat -= dtLat;

      // Keep inside water channel
      const cLon = getCenterlineLon(p.lat);
      p.lon += (cLon - p.lon) * 0.04;
      p.life++;

      // Re-seed at Black Sea entrance (north) when expired or reaching Marmara
      if (p.life > p.maxLife || p.lat < LAT_MIN + 0.005) {
        p.lat = LAT_MAX - Math.random() * 0.02;
        const startCLon = getCenterlineLon(p.lat);
        const startHalfW = getStraitHalfWidthDeg(p.lat);
        p.lon = startCLon + (Math.random() - 0.5) * startHalfW * 1.5;
        p.life = 0;
      }
    }
  }

  // 9. All 3 Iconic Suspension Bridges
  if (state.layers.landmarks) {
    for (const bridge of BOSPHORUS_BRIDGES) {
      const wPt = latLonToCanvas(bridge.lat, bridge.westLon);
      const ePt = latLonToCanvas(bridge.lat, bridge.eastLon);

      // Bridge Pylons
      ctx.fillStyle = bridge.pylonColor;
      ctx.fillRect(wPt.x - 3, wPt.y - 7, 6, 14);
      ctx.fillRect(ePt.x - 3, ePt.y - 7, 6, 14);

      // Suspension Deck Line
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(wPt.x, wPt.y);
      ctx.lineTo(ePt.x, ePt.y);
      ctx.stroke();

      // Catenary Cables
      ctx.strokeStyle = bridge.pylonColor;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(wPt.x, wPt.y - 7);
      ctx.quadraticCurveTo((wPt.x + ePt.x) / 2, wPt.y + 4, ePt.x, ePt.y - 7);
      ctx.stroke();
      ctx.setLineDash([]);

      // Bridge Name Label
      ctx.fillStyle = bridge.pylonColor;
      ctx.font = 'bold 11px monospace';
      ctx.fillText(bridge.name.toUpperCase(), (wPt.x + ePt.x) / 2 - 120, wPt.y - 10);
    }

    // 10. The 700m Constriction Caliper (Rumeli Hisarı Throat)
    const constrW = latLonToCanvas(CONSTRICTION_LAT, 29.054);
    const constrE = latLonToCanvas(CONSTRICTION_LAT, 29.068);
    ctx.strokeStyle = 'rgba(244, 63, 94, 0.7)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(constrW.x, constrW.y);
    ctx.lineTo(constrE.x, constrE.y);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#f43f5e';
    ctx.font = 'bold 11px monospace';
    ctx.fillText('EN DAR BOĞAZ BOĞAZI — 700m THROAT', (constrW.x + constrE.x) / 2 - 110, constrW.y + 14);

    // 11. Geographic Landmark Pins & Namings from Start to Finish
    for (const lm of BOSPHORUS_LANDMARKS) {
      const pt = latLonToCanvas(lm.lat, lm.lon);

      if (lm.type === 'sea') {
        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`⚓ ${lm.name} ⚓`, pt.x, pt.y);
        ctx.textAlign = 'left';
        continue;
      }

      // Pin Color by Type
      let pinColor = '#38bdf8';
      let icon = '•';
      if (lm.type === 'lighthouse') { pinColor = '#fbbf24'; icon = '⛯'; }
      else if (lm.type === 'fortress') { pinColor = '#f43f5e'; icon = '♜'; }
      else if (lm.type === 'tower') { pinColor = '#fbbf24'; icon = '★'; }
      else if (lm.type === 'eddy') { pinColor = '#a78bfa'; icon = '🌀'; }
      else if (lm.type === 'current') { pinColor = '#fb923c'; icon = '⚡'; }

      // Draw Marker Pin
      ctx.fillStyle = pinColor;
      ctx.font = 'bold 12px sans-serif';
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, lm.type === 'tower' ? 5 : 3.5, 0, Math.PI * 2);
      ctx.fill();

      // Label
      ctx.font = '11px sans-serif';
      if (lm.type === 'tower' || lm.type === 'fortress' || lm.type === 'current') {
        ctx.font = 'bold 11px sans-serif';
      }

      if (lm.align === 'right') {
        ctx.fillText(`${lm.name}`, pt.x + 8, pt.y + 4);
      } else if (lm.align === 'center') {
        ctx.textAlign = 'center';
        ctx.fillText(`${lm.name}`, pt.x, pt.y - 8);
        ctx.textAlign = 'left';
      } else {
        ctx.textAlign = 'right';
        ctx.fillText(`${lm.name}`, pt.x - 8, pt.y + 4);
        ctx.textAlign = 'left';
      }
    }
  }

  // 12. Ambient Live Wind Streaks
  if (state.layers.wind && state.windParticles && state.windParticles.length > 0) {
    const rad = ((state.weather.direction_deg + 180) * Math.PI) / 180.0;
    const dx = Math.sin(rad);
    const dy = -Math.cos(rad);

    ctx.lineWidth = 1.2;
    for (const wp of state.windParticles) {
      ctx.strokeStyle = `rgba(56, 189, 248, ${wp.alpha * 0.7})`;
      ctx.beginPath();
      ctx.moveTo(wp.x, wp.y);
      ctx.lineTo(wp.x + dx * wp.len, wp.y + dy * wp.len);
      ctx.stroke();

      wp.x += dx * wp.speed * (state.weather.speed_ms / 5.0);
      wp.y += dy * wp.speed * (state.weather.speed_ms / 5.0);

      // Wrap around bounds
      if (wp.x < 0) wp.x = W;
      if (wp.x > W) wp.x = 0;
      if (wp.y < 0) wp.y = H;
      if (wp.y > H) wp.y = 0;
    }
  }

  // 13. Nautical Compass Rose & Live Wind Vector Overlay
  if (state.layers.wind) {
    renderNauticalCompass(W - 85, 95);
  }

  // 14. Nautical Scale Bar (5 km / 2.7 NM)
  renderScaleBar(30, H - 30);
}

/**
 * Render Nautical Compass Rose with Live Wind Vector
 */
function renderNauticalCompass(cx, cy) {
  const radius = 48;

  // Background Dial Plate
  ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.5)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Cardinal Ticks
  ctx.fillStyle = '#94a3b8';
  ctx.font = 'bold 10px monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('N', cx, cy - radius + 11);
  ctx.fillText('S', cx, cy + radius - 11);
  ctx.fillText('E', cx + radius - 11, cy);
  ctx.fillText('W', cx - radius + 11, cy);

  // Compass North Pointer Needle
  ctx.fillStyle = '#38bdf8';
  ctx.beginPath();
  ctx.moveTo(cx, cy - radius + 18);
  ctx.lineTo(cx - 5, cy);
  ctx.lineTo(cx + 5, cy);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#64748b';
  ctx.beginPath();
  ctx.moveTo(cx, cy + radius - 18);
  ctx.lineTo(cx - 4, cy);
  ctx.lineTo(cx + 4, cy);
  ctx.closePath();
  ctx.fill();

  // Rotating Live Wind Vector Arrow (Pointing in direction wind is blowing towards)
  const wDeg = state.weather.direction_deg;
  const windToAngle = ((wDeg + 180 - 90) * Math.PI) / 180.0; // In radians for canvas
  const arrowLen = radius - 8;
  const ax = cx + Math.cos(windToAngle) * arrowLen;
  const ay = cy + Math.sin(windToAngle) * arrowLen;

  ctx.strokeStyle = '#fbbf24';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(ax, ay);
  ctx.stroke();

  // Arrow Head
  ctx.fillStyle = '#fbbf24';
  ctx.beginPath();
  ctx.arc(ax, ay, 4, 0, Math.PI * 2);
  ctx.fill();

  // Center Pivot
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fill();

  // Digital Compass Readout Badge
  ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
  ctx.strokeStyle = 'rgba(251, 191, 36, 0.6)';
  ctx.lineWidth = 1;
  ctx.fillRect(cx - 70, cy + radius + 8, 140, 24);
  ctx.strokeRect(cx - 70, cy + radius + 8, 140, 24);

  ctx.fillStyle = '#fbbf24';
  ctx.font = 'bold 10px monospace';
  ctx.fillText(`WIND: ${wDeg}° ${state.weather.sector_name}`, cx, cy + radius + 20);

  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
}

/**
 * Render Nautical Scale Bar (5 km / 2.7 NM)
 */
function renderScaleBar(x, y) {
  // 5 km in canvas pixels: (5000 / 111139) / (LAT_MAX - LAT_MIN) * canvas.height
  const px5km = ((5000.0 / 111139.0) / (LAT_MAX - LAT_MIN)) * canvas.height;

  ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
  ctx.lineWidth = 1;
  ctx.fillRect(x - 6, y - 22, px5km + 12, 30);
  ctx.strokeRect(x - 6, y - 22, px5km + 12, 30);

  // Black & White Nautical Bar Segments
  const halfPx = px5km / 2.0;
  ctx.fillStyle = '#38bdf8';
  ctx.fillRect(x, y - 8, halfPx, 6);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(x + halfPx, y - 8, halfPx, 6);
  ctx.strokeRect(x, y - 8, px5km, 6);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px monospace';
  ctx.fillText('0', x - 2, y - 12);
  ctx.fillText('2.5', x + halfPx - 8, y - 12);
  ctx.fillText('5 km (2.7 NM)', x + px5km - 30, y - 12);
}

/**
 * Render Swarm Particles & Beaching Incidents
 */
function renderSwarmSimulation() {
  if (!state.currentSim || !state.currentSim.trajectories) return;

  const trajs = state.currentSim.trajectories;
  const currentStep = Math.min(state.animationStep, state.maxSteps);

  let entityColor = '#38bdf8';
  if (state.currentSim.entity_type === 'raft') entityColor = '#34d399';
  else if (state.currentSim.entity_type === 'boat') entityColor = '#fbbf24';
  else if (state.currentSim.entity_type === 'oil') entityColor = '#a78bfa';

  for (let i = 0; i < trajs.length; i++) {
    const path = trajs[i];
    if (!path || path.length === 0) continue;

    const visibleLen = Math.min(currentStep, path.length);

    // Trail
    ctx.strokeStyle = entityColor + '50';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let s = 0; s < visibleLen; s++) {
      const pt = latLonToCanvas(path[s][0], path[s][1]);
      if (s === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    }
    ctx.stroke();

    // Head Particle
    if (visibleLen > 0) {
      const headPt = latLonToCanvas(path[visibleLen - 1][0], path[visibleLen - 1][1]);
      ctx.fillStyle = entityColor;
      ctx.beginPath();
      ctx.arc(headPt.x, headPt.y, 3, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  // Draw Beached Particles
  if (state.currentSim.final_positions && currentStep >= state.maxSteps) {
    for (const p of state.currentSim.final_positions) {
      if (p[2]) {
        const pt = latLonToCanvas(p[0], p[1]);
        ctx.fillStyle = '#f43f5e';
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 5, 0, 2 * Math.PI);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }
  }

  // Draw Incident Origin Sighting Marker
  if (trajs.length > 0 && trajs[0].length > 0) {
    const origin = latLonToCanvas(trajs[0][0][0], trajs[0][0][1]);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(origin.x, origin.y, 8, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.fillStyle = '#f59e0b';
    ctx.font = 'bold 11px monospace';
    ctx.fillText('ORIGIN DATUM', origin.x + 12, origin.y + 4);
  }
}

/**
 * Render Reverse Backtracking Origin Ellipse
 */
function renderReverseSimulation() {
  if (!state.currentSim || !state.currentSim.estimated_origins) return;

  const currentStep = Math.min(state.animationStep, state.maxSteps);
  const trajs = state.currentSim.trajectories || [];

  // Trajectory trails
  ctx.strokeStyle = 'rgba(251, 191, 36, 0.4)';
  ctx.lineWidth = 1.2;
  for (const path of trajs) {
    const visibleLen = Math.min(currentStep, path.length);
    ctx.beginPath();
    for (let s = 0; s < visibleLen; s++) {
      const pt = latLonToCanvas(path[s][0], path[s][1]);
      if (s === 0) ctx.moveTo(pt.x, pt.y);
      else ctx.lineTo(pt.x, pt.y);
    }
    ctx.stroke();
  }

  // Estimated origin particle cloud
  if (currentStep >= state.maxSteps) {
    ctx.fillStyle = '#fbbf24';
    for (const orig of state.currentSim.estimated_origins) {
      const pt = latLonToCanvas(orig[0], orig[1]);
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 2.5, 0, 2 * Math.PI);
      ctx.fill();
    }

    // 95% Confidence Ellipse
    if (state.currentSim.mean_origin && state.currentSim.confidence_ellipse_95_km) {
      const meanPt = latLonToCanvas(state.currentSim.mean_origin[0], state.currentSim.mean_origin[1]);
      const ellipse = state.currentSim.confidence_ellipse_95_km;

      const rLat = (ellipse.semi_major_lat / 111.0) * (canvas.height / (LAT_MAX - LAT_MIN));
      const rLon = (ellipse.semi_minor_lon / 84.0) * (canvas.width / (LON_MAX - LON_MIN));

      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.ellipse(meanPt.x, meanPt.y, Math.max(15, rLon), Math.max(15, rLat), 0, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 11px monospace';
      ctx.fillText('95% SAR DATUM ELLIPSE', meanPt.x + 20, meanPt.y - 10);
    }
  }
}

/**
 * Render A* Optimal Navigation Route
 */
function renderOptimalRoute() {
  if (!state.currentRoute || !state.currentRoute.waypoints) return;

  const wps = state.currentRoute.waypoints;
  if (wps.length < 2) return;

  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = 3.5;
  ctx.shadowColor = '#34d399';
  ctx.shadowBlur = 12;

  ctx.beginPath();
  for (let i = 0; i < wps.length; i++) {
    const pt = latLonToCanvas(wps[i][0], wps[i][1]);
    if (i === 0) ctx.moveTo(pt.x, pt.y);
    else ctx.lineTo(pt.x, pt.y);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;

  for (let i = 0; i < wps.length; i++) {
    const pt = latLonToCanvas(wps[i][0], wps[i][1]);
    ctx.fillStyle = i === 0 ? '#38bdf8' : i === wps.length - 1 ? '#f43f5e' : '#34d399';
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, i === 0 || i === wps.length - 1 ? 6 : 3, 0, 2 * Math.PI);
    ctx.fill();
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  const startPt = latLonToCanvas(wps[0][0], wps[0][1]);
  const endPt = latLonToCanvas(wps[wps.length - 1][0], wps[wps.length - 1][1]);
  ctx.fillStyle = '#38bdf8';
  ctx.font = 'bold 11px monospace';
  ctx.fillText('DEPARTURE', startPt.x + 10, startPt.y - 6);

  ctx.fillStyle = '#f43f5e';
  ctx.fillText('DESTINATION', endPt.x + 10, endPt.y - 6);
}

/**
 * Main 60 FPS Animation Loop
 */
function animate() {
  renderBaseMap();

  if (state.activeTab === 'forward') {
    renderSwarmSimulation();
  } else if (state.activeTab === 'reverse') {
    renderReverseSimulation();
  }

  renderOptimalRoute();

  if (state.animating && state.animationStep < state.maxSteps) {
    state.animationStep += 2;
  }

  requestAnimationFrame(animate);
}

/**
 * API Submissions with Accurate Live Meteorology
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

  // Embed Live Weather data from Open-Meteo API
  const useLive = document.getElementById('fwd-use-live-wind')?.checked;
  if (useLive && state.weather) {
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

  const useLive = document.getElementById('rev-use-live-wind')?.checked;
  if (useLive && state.weather) {
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

/**
 * Telemetry Card HUD Update
 */
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

/**
 * Chart Modal Viewer
 */
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

/**
 * Tab Switching Functionality
 */
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

/**
 * Layer Visibility Toggle Handlers
 */
function setupLayerToggles() {
  const layerDefs = [
    { id: 'toggle-layer-landmarks', key: 'landmarks' },
    { id: 'toggle-layer-flow', key: 'flow' },
    { id: 'toggle-layer-tss', key: 'tss' },
    { id: 'toggle-layer-vectors', key: 'vectors' },
    { id: 'toggle-layer-wind', key: 'wind' },
  ];

  layerDefs.forEach(({ id, key }) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener('click', () => {
      state.layers[key] = !state.layers[key];
      if (state.layers[key]) btn.classList.add('active');
      else btn.classList.remove('active');
    });
  });
}

/**
 * DOM Ready Initialization
 */
document.addEventListener('DOMContentLoaded', () => {
  initCanvas();
  fetchGridData();
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

  // Start 60 FPS Rendering Animation Loop
  requestAnimationFrame(animate);
});
