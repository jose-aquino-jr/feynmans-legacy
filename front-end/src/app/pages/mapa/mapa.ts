import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, NgZone, ChangeDetectorRef, HostListener } from '@angular/core';
import { RouterLink } from '@angular/router';
import * as THREE from 'three';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';

type View = 'both' | 'earth' | 'other';
type Body = 'mars' | 'moon';
type Criterion =
  | 'thermal'
  | 'lightingRadiation'
  | 'waterIce'
  | 'waterAridity'
  | 'terrain'
  | 'geology'
  | 'surfaceDust'
  | 'windDustProcesses'
  | 'biologyHabitability'
  | 'subsurface'
  | 'atmosphere'
  | 'operations';

const MIN_YEAR = 2026;
const MAX_YEAR = 2100;
const CRITERIA: { key: Criterion; label: string }[] = [
  { key: 'thermal', label: 'Thermal' },
  { key: 'lightingRadiation', label: 'Lighting and radiation' },
  { key: 'waterIce', label: 'Water and ice' },
  { key: 'waterAridity', label: 'Water and aridity' },
  { key: 'terrain', label: 'Terrain' },
  { key: 'geology', label: 'Geology' },
  { key: 'surfaceDust', label: 'Surface and dust' },
  { key: 'windDustProcesses', label: 'Wind and dust processes' },
  { key: 'biologyHabitability', label: 'Biology and habitability' },
  { key: 'subsurface', label: 'Subsurface' },
  { key: 'atmosphere', label: 'Atmosphere' },
  { key: 'operations', label: 'Operations' },
];

const RADAR_LABELS: Record<Criterion, string> = {
  thermal: 'Thermal',
  lightingRadiation: 'Light/rad.',
  waterIce: 'Water/ice',
  waterAridity: 'Water/arid.',
  terrain: 'Terrain',
  geology: 'Geology',
  surfaceDust: 'Surface/dust',
  windDustProcesses: 'Wind/dust',
  biologyHabitability: 'Biology',
  subsurface: 'Subsurface',
  atmosphere: 'Atmosphere',
  operations: 'Operations',
};

function criterionScore(scores: number[], criterion: Criterion) {
  const [geology, temperature, aridity, relief, altitude, soil] = scores;
  const mean = (...values: number[]) => values.reduce((total, value) => total + value, 0) / values.length;
  const scoreMap: Record<Criterion, number> = {
    thermal: temperature,
    lightingRadiation: mean(altitude, aridity),
    waterIce: mean(aridity, soil),
    waterAridity: aridity,
    terrain: relief,
    geology,
    surfaceDust: mean(aridity, soil),
    windDustProcesses: mean(aridity, relief),
    biologyHabitability: mean(temperature, soil),
    subsurface: mean(geology, soil),
    atmosphere: mean(temperature, altitude),
    operations: mean(relief, altitude),
  };
  return scoreMap[criterion] ?? 0;
}

function criterionScores(scores: number[]) {
  return CRITERIA.map(({ key }) => criterionScore(scores, key));
}

const R_EARTH = 6371;
const R_MARS = 3396.19;
const R_MOON = 1737.4;
const MARS_SCALE = R_MARS / R_EARTH;
const MOON_SCALE = R_MOON / R_EARTH;

const BODIES: Body[] = ['mars', 'moon'];


const EARTH_MARKER_FILL = { color: 0xde7d28, opacity: 0.71 };
const OTHER_MARKER_FILL = { color: 0x0f0903, opacity: 0.41 };

const CONFIG = {
  mars: {
    label: 'Marte',
    scale: MARS_SCALE,
    target: { name: 'Jezero', lat: 18.4, lon: 77.6, radiusKm: 400 },
    analog: { name: 'Puna de Atacama', lat: -25, lon: -67, radiusKm: 600 },
  },
  moon: {
    label: 'Lua',
    scale: MOON_SCALE,
    target: { name: 'Mare Tranquillitatis', lat: 0.67, lon: 23.47, radiusKm: 150 },
    analog: { name: 'Mauna Kea', lat: 19.82, lon: -155.47, radiusKm: 300 },
  },
};

interface Psychodata {
  stress: number;
  sleep: number;
  workload: number;
  cohesion: number;
  isolation: number;
}

interface AnalogPlace {
  id: string;
  name: string;
  region: string;
  lat: number;
  lon: number;
  targets: Record<Body, { lat: number; lon: number }>;
  scores: Record<Body, number[]>;
  summary: string;
  fit: string;
  psychodata: Psychodata;
}

interface AnalogResult extends AnalogPlace {
  similarity: number;
  matchedCriteria: Criterion[];
}

const ANALOG_PLACES: AnalogPlace[] = [
  {
    id: 'atacama',
    name: 'Puna de Atacama',
    region: 'Chile and Argentina',
    lat: -25,
    lon: -67,
    targets: { mars: { lat: 18.4, lon: 77.6 }, moon: { lat: 0.67, lon: 23.47 } },
    scores: { mars: [0.85, 0.55, 0.7, 0.8, 0.5, 0.65], moon: [0.8, 0.6, 0.7, 0.8, 0.5, 0.64] },
    summary: 'High-altitude salt flats and volcanic terrain with exceptionally dry conditions.',
    fit: 'Aridity, exposed rock, and sparse vegetation support instrument trials and surface exploration rehearsals.',
    psychodata: { stress: 58, sleep: 64, workload: 72, cohesion: 80, isolation: 66 },
  },
  {
    id: 'dry-valleys',
    name: 'McMurdo Dry Valleys',
    region: 'Antarctica',
    lat: -77.5,
    lon: 162,
    targets: { mars: { lat: -14.6, lon: 175.5 }, moon: { lat: -43.3, lon: -11.2 } },
    scores: { mars: [0.78, 0.35, 0.92, 0.72, 0.4, 0.76], moon: [0.85, 0.42, 0.88, 0.83, 0.45, 0.72] },
    summary: 'Cold, dry polar valleys with bare rock, glaciers, and limited surface water.',
    fit: 'Cold desert conditions and remote field operations are useful for testing sampling workflows and equipment reliability.',
    psychodata: { stress: 71, sleep: 48, workload: 78, cohesion: 84, isolation: 88 },
  },
  {
    id: 'devon-island',
    name: 'Haughton Crater',
    region: 'Devon Island, Canada',
    lat: 75.4,
    lon: -89.7,
    targets: { mars: { lat: -4.5, lon: 137.4 }, moon: { lat: -22, lon: 5.2 } },
    scores: { mars: [0.75, 0.38, 0.86, 0.82, 0.32, 0.68], moon: [0.71, 0.47, 0.9, 0.82, 0.38, 0.74] },
    summary: 'A remote Arctic impact structure with rocky terrain and permafrost.',
    fit: 'Impact geology, isolation, and demanding field access support rover, habitat, and crew-operation trials.',
    psychodata: { stress: 66, sleep: 56, workload: 74, cohesion: 82, isolation: 91 },
  },
  {
    id: 'mdrs',
    name: 'Mars Desert Research Station',
    region: 'Utah, United States',
    lat: 38.4,
    lon: -110.8,
    targets: { mars: { lat: 18.2, lon: 77.5 }, moon: { lat: 18, lon: -57 } },
    scores: { mars: [0.7, 0.48, 0.75, 0.68, 0.72, 0.63], moon: [0.68, 0.52, 0.78, 0.71, 0.7, 0.67] },
    summary: 'A desert field site organized around simulated crew missions and habitat operations.',
    fit: 'Mission infrastructure makes it useful for rehearsing EVA routines, habitat procedures, and team coordination.',
    psychodata: { stress: 62, sleep: 68, workload: 70, cohesion: 86, isolation: 73 },
  },
  {
    id: 'pisgah',
    name: 'Pisgah Crater',
    region: 'Mojave Desert, United States',
    lat: 34.75,
    lon: -116.5,
    targets: { mars: { lat: -1.9, lon: 354.5 }, moon: { lat: 23.7, lon: -47.4 } },
    scores: { mars: [0.73, 0.62, 0.81, 0.77, 0.56, 0.66], moon: [0.72, 0.64, 0.82, 0.77, 0.58, 0.72] },
    summary: 'A volcanic cinder cone and lava field in a dry desert environment.',
    fit: 'Rugged volcanic surfaces support geological sampling, route planning, and mobility-equipment exercises.',
    psychodata: { stress: 51, sleep: 76, workload: 64, cohesion: 78, isolation: 58 },
  },
  {
    id: 'lanzarote',
    name: 'Lanzarote Lava Fields',
    region: 'Canary Islands, Spain',
    lat: 29,
    lon: -13.6,
    targets: { mars: { lat: -5.4, lon: 135.9 }, moon: { lat: 9.7, lon: 20 } },
    scores: { mars: [0.82, 0.67, 0.78, 0.71, 0.38, 0.62], moon: [0.88, 0.72, 0.72, 0.75, 0.42, 0.71] },
    summary: 'Basaltic lava fields and volcanic landscapes with accessible field routes.',
    fit: 'Lava textures and volcanic landforms are useful for testing geological classification and surface navigation.',
    psychodata: { stress: 47, sleep: 81, workload: 58, cohesion: 79, isolation: 44 },
  },
  {
    id: 'askja',
    name: 'Askja Caldera',
    region: 'Iceland',
    lat: 65,
    lon: -16.75,
    targets: { mars: { lat: -8.3, lon: 15 }, moon: { lat: -25.5, lon: 3.6 } },
    scores: { mars: [0.77, 0.44, 0.7, 0.75, 0.51, 0.7], moon: [0.82, 0.49, 0.67, 0.8, 0.56, 0.73] },
    summary: 'A remote volcanic caldera with ash, lava, and highland terrain.',
    fit: 'Volcanic geology and remote access provide a setting for field science and equipment deployment practice.',
    psychodata: { stress: 63, sleep: 62, workload: 68, cohesion: 80, isolation: 67 },
  },
  {
    id: 'kilauea',
    name: 'Kīlauea Lava Fields',
    region: 'Hawaiʻi, United States',
    lat: 19.42,
    lon: -155.29,
    targets: { mars: { lat: 6.5, lon: 76.9 }, moon: { lat: 21.3, lon: -17.5 } },
    scores: { mars: [0.84, 0.72, 0.55, 0.76, 0.62, 0.78], moon: [0.91, 0.72, 0.52, 0.81, 0.59, 0.82] },
    summary: 'Active volcanic terrain with basaltic lava, vents, and varied surface textures.',
    fit: 'Basalt analogues are useful for comparing volcanic materials and practicing instrument deployment.',
    psychodata: { stress: 54, sleep: 77, workload: 65, cohesion: 83, isolation: 49 },
  },
  {
    id: 'mauna-kea',
    name: 'Mauna Kea',
    region: 'Hawaiʻi, United States',
    lat: 19.82,
    lon: -155.47,
    targets: { mars: { lat: 24.7, lon: 326.7 }, moon: { lat: 37.4, lon: -9.9 } },
    scores: { mars: [0.79, 0.45, 0.6, 0.73, 0.88, 0.64], moon: [0.84, 0.5, 0.68, 0.78, 0.92, 0.7] },
    summary: 'A high-altitude volcanic landscape with exposed rock and sparse vegetation.',
    fit: 'Elevation, volcanic geology, and exposed terrain support geology training and field-procedure rehearsals.',
    psychodata: { stress: 68, sleep: 58, workload: 76, cohesion: 82, isolation: 64 },
  },
  {
    id: 'craters-moon',
    name: 'Craters of the Moon',
    region: 'Idaho, United States',
    lat: 43.4,
    lon: -113.5,
    targets: { mars: { lat: -27.5, lon: 12.6 }, moon: { lat: 43.3, lon: -11.2 } },
    scores: { mars: [0.83, 0.68, 0.79, 0.8, 0.55, 0.74], moon: [0.86, 0.69, 0.84, 0.82, 0.58, 0.8] },
    summary: 'A basaltic lava field with volcanic cones, caves, and rough surfaces.',
    fit: 'Basaltic terrain and surface roughness support instrument, mobility, and geological sampling exercises.',
    psychodata: { stress: 50, sleep: 75, workload: 61, cohesion: 78, isolation: 52 },
  },
];

const BODY_DETAILS: Record<Body, { label: string; limitation: string; missionUse: string }> = {
  mars: {
    label: 'MARS',
    limitation: 'Earth still has stronger gravity, a dense atmosphere, and a protective magnetic field. This site cannot reproduce Martian pressure, radiation, or dust behavior.',
    missionUse: 'Rehearse traverse planning, sample collection, instrument deployment, and crew procedures before a Mars mission.',
  },
  moon: {
    label: 'MOON',
    limitation: 'This site cannot reproduce the lunar vacuum, one-sixth gravity, radiation, electrostatic dust, or extreme thermal cycle.',
    missionUse: 'Rehearse geological sampling, equipment deployment, navigation, and crew procedures for lunar surface operations.',
  },
};

const MONTHS = [
  { value: 'jan', label: 'January' },
  { value: 'feb', label: 'February' },
  { value: 'mar', label: 'March' },
  { value: 'apr', label: 'April' },
  { value: 'may', label: 'May' },
  { value: 'jun', label: 'June' },
  { value: 'jul', label: 'July' },
  { value: 'aug', label: 'August' },
  { value: 'sep', label: 'September' },
  { value: 'oct', label: 'October' },
  { value: 'nov', label: 'November' },
  { value: 'dec', label: 'December' },
];

const BASE_OPTIONS: Record<Body, { value: string; label: string; lat: number; lon: number }[]> = {
  mars: [
    { value: 'gale', label: 'Gale Crater - Mount Sharp', lat: -5.4, lon: 137.8 },
    { value: 'jezero', label: 'Jezero Crater', lat: 18.4, lon: 77.6 },
    { value: 'elysium', label: 'Elysium Planitia', lat: 4.5, lon: 135.9 },
  ],
  moon: [
    { value: 'mare-tranquillitatis', label: 'Mare Tranquillitatis', lat: 8.5, lon: 30.9 },
    { value: 'south-pole', label: 'Lunar South Pole', lat: -89.5, lon: 0 },
    { value: 'oceanus-procellarum', label: 'Oceanus Procellarum', lat: 18.4, lon: -57.4 },
  ],
};

const PROJECTION_MODELS = [
  { value: 'lightgbm-recursive', label: 'Recursive LightGBM projection (default)' },
  { value: 'seasonal-climatology', label: 'Seasonal climatology' },
  { value: 'linear-trend', label: 'Linear trend' },
];

const TIMELINE = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => ({ year: MIN_YEAR + i }));

function buildRadar(values: number[], selected: Criterion[] = CRITERIA.map((criterion) => criterion.key)) {
  const cx = 120, cy = 100, R = 55, L = 82;
  const angle = (i: number) => ((i * (360 / CRITERIA.length) - 90) * Math.PI) / 180;
  const pt = (i: number, r: number) => ({ x: cx + r * Math.cos(angle(i)), y: cy + r * Math.sin(angle(i)) });
  const fmt = (p: { x: number; y: number }) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  return {
    rings: [1, 0.66, 0.33].map((k) => CRITERIA.map((_, i) => fmt(pt(i, R * k))).join(' ')),
    axes: CRITERIA.map((_, i) => pt(i, R)),
    data: values.map((v, i) => fmt(pt(i, R * (selected.includes(CRITERIA[i].key) ? v : 0)))).join(' '),
    labels: CRITERIA.map(({ key }, i) => {
      const p = pt(i, L);
      const c = Math.cos(angle(i));
      const s = Math.sin(angle(i));
      return { text: RADAR_LABELS[key], x: p.x, y: p.y, anchor: c > 0.1 ? 'start' : c < -0.1 ? 'end' : 'middle', dy: s < -0.5 ? -1 : s > 0.5 ? 9 : 3, selected: selected.includes(key) };
    }),
  };
}

const SEGMENTS = 48;
const ARC_HEIGHT = 0.6;
const DASH_SPEED = 0.25;
const CAMERA_SMOOTHING = 4;
const IDLE_ROTATION_SPEED = 0.08;
const MIN_DISTANCE_FACTOR = 2.5;
const FRAME_INTERVAL = 1000 / 30;
const SCENE_VERTICAL_OFFSET = 0;

const FOV = 18;

const DIST_K = Math.tan((22.5 * Math.PI) / 180) / Math.tan((FOV * Math.PI) / 360);
const EARTH_X = 1.7;
const OTHER_X = -2.1;

const VIEW_HALF = Math.tan((22.5 * Math.PI) / 180);

const FIT_MARGIN = 1.12 * 1.06;


function panelPath(w: number, h: number, bump: boolean): string {
  const r = 20;
  const x0 = bump ? 16 : 0;
  const o = x0 - 16;
  const t = h / 2 - 60;
  const left = bump
    ? `V${t + 120} C${x0} ${t + 98} ${o} ${t + 106} ${o} ${t + 84} V${t + 36} C${o} ${t + 14} ${x0} ${t + 22} ${x0} ${t} `
    : '';
  return (
    `M${x0 + r} 0 H${w - r} A${r} ${r} 0 0 1 ${w} ${r} V${h - r} A${r} ${r} 0 0 1 ${w - r} ${h} ` +
    `H${x0 + r} A${r} ${r} 0 0 1 ${x0} ${h - r} ${left}V${r} A${r} ${r} 0 0 1 ${x0 + r} 0 Z`
  );
}

const DRAW_DURATION = 2.4;
const DRAW_DELAY = 0.6;

const easeInOutCubic = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

function latLon(lat: number, lon: number, r = 1): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
}

@Component({
  selector: 'app-map-page',
  imports: [RouterLink],
  templateUrl: './mapa.html',
  host: {
    class:
      'relative block h-screen overflow-hidden bg-ink font-sans text-cream ' +
      'max-md:h-auto max-md:min-h-screen max-md:overflow-y-auto max-md:overflow-x-hidden ' +
      '[--panel-w:clamp(290px,24vw,361px)] [--panel-top:clamp(148px,16vh,176px)] [--nav-right-offset:calc(var(--panel-w)*0.45)]',
  },
})
export class MapPage implements AfterViewInit, OnDestroy {
  
  @ViewChild('scene', { static: true }) set sceneRef(ref: ElementRef<HTMLCanvasElement> | undefined) {
    if (ref) {
      if (this.sceneCanvas === ref.nativeElement && this.renderer) return;
      this.zone.runOutsideAngular(() => this.init(ref.nativeElement));
    } else if (this.renderer) {
      this.sceneCanvas = null;
      this.teardown();
    }
  }
  @ViewChild('panel') panelEl!: ElementRef<HTMLElement>;
  @ViewChild('glassBody') glassBodyEl!: ElementRef<HTMLElement>;

  readonly cfg = CONFIG;
  readonly timeline = TIMELINE;
  readonly criteria = CRITERIA;
  readonly bodyDetails = BODY_DETAILS;
  readonly months = MONTHS;
  readonly baseOptions = BASE_OPTIONS;
  readonly projectionModels = PROJECTION_MODELS;
  readonly coverageOptions = [50, 60, 70, 80, 90, 100];
  readonly analogCount = ANALOG_PLACES.length;
  readonly psychodataMetrics = [
    { key: 'stress', label: 'Perceived stress' },
    { key: 'sleep', label: 'Sleep quality' },
    { key: 'workload', label: 'Task workload' },
    { key: 'cohesion', label: 'Team cohesion' },
    { key: 'isolation', label: 'Perceived isolation' },
  ] as const;
  readonly navItems = [
    { label: 'HOME', link: '/' },
    { label: 'MAP', link: '/mapa' },
    { label: 'METHODOLOGY', link: '/metodologia' },
    { label: 'DATA', link: '/', fragment: 'data' },
    { label: 'TEAM', link: '/', fragment: 'team' },
  ];
  readonly minYear = MIN_YEAR;
  readonly maxYear = MAX_YEAR;
  panelOpen = false;
  filtersModalOpen = false;
  hasSearched = false;
  selectedCriteria: Criterion[] = [];
  searchYearValue = String(MIN_YEAR);
  searchMonth = 'aug';
  baseValue = 'gale';
  neighborsPerBase = 10;
  minimumCoverage = 70;
  futureEarthState = 'lightgbm-recursive';
  activeYear = 0;
  results: AnalogResult[] = [];
  selectedAnalog: AnalogResult | null = null;
  radar = buildRadar(criterionScores(ANALOG_PLACES[0].scores.mars));
  view: View = 'both';
  body: Body = 'mars';

  private renderer: THREE.WebGLRenderer | null = null;
  private scene = new THREE.Scene();

  private textureCache = new Map<string, THREE.Texture>();
  private maxAnisotropy = 1;
  private moonMaterial!: THREE.MeshStandardMaterial;
  private moonTextureRequested = false;
  private camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 300);
  private earth!: THREE.Mesh;
  private mars!: THREE.Mesh;
  private moon!: THREE.Mesh;
  private earthMarkers = {} as Record<Body, THREE.Group>;
  private otherMarkers = {} as Record<Body, THREE.Group>;
  private earthFocus = {} as Record<Body, THREE.Quaternion>;
  private otherFocus = {} as Record<Body, THREE.Quaternion>;
  private line!: Line2;
  private head!: THREE.Mesh;
  private drawElapsed = -DRAW_DELAY;
  private drawProgress = 0;
  private aligning = true;
  private zoom = 1;
  private cameraX = 0;
  private cameraDistance = 6;
  private fitAspect: number | null = null;
  private visibleSceneWidth = 0;
  private sceneCanvas: HTMLCanvasElement | null = null;
  private viewportWidth = 0;
  private viewportHeight = 0;
  private dragging: THREE.Object3D | null = null;
  private lastPointer = { x: 0, y: 0 };
  private raycaster = new THREE.Raycaster();
  private resizeObserver?: ResizeObserver;
  private panelObserver?: ResizeObserver;
  private cleanups: Array<() => void> = [];
  private frameId: number | null = null;
  private forceNextFrame = false;
  private lineDirty = true;
  private lastSpread: number | null = null;
  private lastRenderTime = 0;
  private previousTime = performance.now();

  constructor(private zone: NgZone, private cdr: ChangeDetectorRef) { }

  get canSearch() {
    return this.selectedCriteria.length > 0 && this.validSearchYear !== null;
  }

  get allCriteriaSelected() {
    return this.selectedCriteria.length === this.criteria.length;
  }

  private get validSearchYear() {
    const year = Number(this.searchYearValue);
    return this.searchYearValue.trim() !== '' && Number.isInteger(year) && year >= this.minYear && year <= this.maxYear
      ? year
      : null;
  }

  ngAfterViewInit() {
    this.zone.runOutsideAngular(() => {
      this.observePanel();
      this.updateSceneLayout();
    });
  }

  togglePanel() {
    this.panelOpen = !this.panelOpen;
    this.zone.runOutsideAngular(() => this.updateSceneLayout());
  }

  openFilters() {
    this.filtersModalOpen = true;
  }

  closeFilters() {
    this.filtersModalOpen = false;
  }

  @HostListener('document:keydown.escape')
  onEscape() {
    if (this.filtersModalOpen) this.closeFilters();
  }

  toggleCriterion(criterion: Criterion, event: Event) {
    const checked = (event.target as HTMLInputElement).checked;
    this.selectedCriteria = checked
      ? [...this.selectedCriteria, criterion]
      : this.selectedCriteria.filter((selected) => selected !== criterion);
  }

  toggleAllCriteria(event: Event) {
    this.selectedCriteria = (event.target as HTMLInputElement).checked
      ? this.criteria.map(({ key }) => key)
      : [];
  }

  setSearchYear(raw: string) {
    this.searchYearValue = raw;
  }

  setNeighborsPerBase(raw: string) {
    const value = Number(raw);
    if (Number.isInteger(value) && value >= 1 && value <= ANALOG_PLACES.length) {
      this.neighborsPerBase = value;
    }
  }

  setMinimumCoverage(raw: string) {
    const value = Number(raw);
    if (this.coverageOptions.includes(value)) this.minimumCoverage = value;
  }

  searchAnalogs() {
    if (!this.canSearch) return;

    this.closeFilters();
    this.hasSearched = true;
    this.panelOpen = true;
    this.activeYear = this.validSearchYear! - this.minYear;
    this.results = this.rankAnalogs(this.body).slice(0, this.neighborsPerBase);
    this.selectedAnalog = null;
    this.applyBody();
    this.zoom = 1;
    this.aligning = false;
    this.drawProgress = 0;
    this.drawElapsed = -DRAW_DELAY;
    this.line.visible = false;
    this.head.visible = false;
    this.lineDirty = true;
    this.zone.runOutsideAngular(() => this.updateSceneLayout());
  }

  private rankAnalogs(body: Body): AnalogResult[] {
    const matchedCriteria = this.selectedCriteria.length > 0
      ? [...this.selectedCriteria]
      : CRITERIA.map((criterion) => criterion.key);

    return ANALOG_PLACES.map((place) => {
      const scores = place.scores[body];
      const similarity = Math.round(
        (matchedCriteria.reduce((total, criterion) => total + criterionScore(scores, criterion), 0) / matchedCriteria.length) * 100
      );
      return { ...place, similarity, matchedCriteria };
    }).sort((first, second) => second.similarity - first.similarity);
  }

  selectAnalog(result: AnalogResult) {
    this.selectedAnalog = result;
    this.radar = buildRadar(criterionScores(result.scores[this.body]), result.matchedCriteria);

    const target = this.baseOptions[this.body].find((base) => base.value === this.baseValue) ?? result.targets[this.body];
    const scale = CONFIG[this.body].scale;
    this.setMarkerPosition(this.earthMarkers[this.body], result.lat, result.lon, 1);
    this.setMarkerPosition(this.otherMarkers[this.body], target.lat, target.lon, scale);

    const front = new THREE.Vector3(0, 0, 1);
    this.earthFocus[this.body] = new THREE.Quaternion().setFromUnitVectors(latLon(result.lat, result.lon).normalize(), front);
    this.otherFocus[this.body] = new THREE.Quaternion().setFromUnitVectors(latLon(target.lat, target.lon).normalize(), front);

    this.applyBody();
    this.zoom = 1;
    this.aligning = true;
    this.restartDraw();
    this.requestFrame();
  }

  backToResults() {
    this.selectedAnalog = null;
    this.aligning = false;
    this.drawProgress = 0;
    this.drawElapsed = -DRAW_DELAY;
    this.line.visible = false;
    this.head.visible = false;
    this.applyBody();
    this.requestFrame();
  }

  private updateSceneLayout() {
    const canvas = this.sceneCanvas;
    if (!canvas) return;

    const canvasWidth = canvas.clientWidth;
    if (canvasWidth <= 0) return;
    const canvasHeight = canvas.clientHeight || 1;
    let visibleWidth = canvasWidth;

    if (this.panelOpen && window.innerWidth >= 768 && this.panelEl?.nativeElement) {
      const panel = this.panelEl.nativeElement;
      const panelRight = Number.parseFloat(getComputedStyle(panel).right) || 0;
      const panelLeft = window.innerWidth - panelRight - panel.offsetWidth;
      const canvasLeft = canvas.getBoundingClientRect().left;
      visibleWidth = THREE.MathUtils.clamp(panelLeft - canvasLeft, 1, canvasWidth);
    }

    this.visibleSceneWidth = visibleWidth;
    this.fitAspect = visibleWidth / canvasHeight;
    this.lineDirty = true;

    if (this.lastRenderTime === 0) {
      const initial = this.desiredCamera();
      this.cameraX = initial.x;
      this.cameraDistance = initial.distance;
      this.camera.position.set(this.cameraX, SCENE_VERTICAL_OFFSET, this.cameraDistance);
    }

    this.requestFrame();
  }

  
  private observePanel() {
    const el = this.panelEl.nativeElement;
    const update = () => {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      if (!w || !h) return;
      const d = panelPath(w, h, window.innerWidth >= 768);
      const svg = el.querySelector('svg');
      svg?.setAttribute('viewBox', `0 0 ${w} ${h}`);
      el.querySelectorAll('path[data-shape]').forEach((p) => p.setAttribute('d', d));
      this.glassBodyEl.nativeElement.style.clipPath = `path('${d}')`;
      this.updateSceneLayout();
    };
    this.panelObserver = new ResizeObserver(update);
    this.panelObserver.observe(el);
    update();
  }

  
  private get other(): THREE.Mesh {
    return this.body === 'mars' ? this.mars : this.moon;
  }

  
  setView(view: View) {
    this.view = view;
    this.zoom = 1;
    this.aligning = this.selectedAnalog !== null;

    this.cdr.markForCheck();
    this.requestFrame();
  }

  setBody(body: Body) {
    if (this.body === body) return;
    this.body = body;
    this.selectedAnalog = null;
    this.results = this.hasSearched ? this.rankAnalogs(body).slice(0, this.neighborsPerBase) : [];
    this.baseValue = body === 'mars' ? 'gale' : 'mare-tranquillitatis';
    if (!this.renderer) return;
    this.applyBody();
    this.zoom = 1;
    this.aligning = false;
    this.drawProgress = 0;
    this.drawElapsed = -DRAW_DELAY;
    this.line.visible = false;
    this.head.visible = false;
    this.lineDirty = true;
    if (body === 'moon') this.loadMoonTexture();
    this.requestFrame();
  }

  align() {
    this.aligning = this.selectedAnalog !== null;
    this.requestFrame();
  }

  private restartDraw() {
    this.drawElapsed = -DRAW_DELAY;
    this.drawProgress = 0;
    this.lineDirty = true;
  }

  private applyBody() {
    this.mars.visible = this.body === 'mars';
    this.moon.visible = this.body === 'moon';
    for (const b of BODIES) {
      const visible = this.selectedAnalog !== null && b === this.body;
      this.earthMarkers[b].visible = visible;
      this.otherMarkers[b].visible = visible;
    }
    this.lineDirty = true;
  }

  
  private spread() {
    const aspect = this.fitAspect ?? this.camera.aspect;
    return THREE.MathUtils.clamp(aspect / 2.1, 1, 2);
  }

  
  private fitSphere(r: number) {
    const aspect = this.fitAspect ?? this.camera.aspect;
    return (r * FIT_MARGIN) / (VIEW_HALF * Math.min(1, aspect));
  }

  private cameraLimits() {
    const aspect = this.fitAspect ?? this.camera.aspect;
    if (this.view === 'earth') {
      return {
        x: this.earth.position.x,
        base: Math.max(3.4, 3.2 / aspect),
        min: Math.max(1 * MIN_DISTANCE_FACTOR, this.fitSphere(1)),
      };
    }
    if (this.view === 'other') {
      const scale = CONFIG[this.body].scale;
      const f = scale / MARS_SCALE;
      return {
        x: this.other.position.x,
        base: Math.max(1.8 * f, (1.7 * f) / aspect),
        min: Math.max(scale * MIN_DISTANCE_FACTOR, this.fitSphere(scale)),
      };
    }

    const spread = this.spread();
    const right = EARTH_X * spread + 1.12;
    const left = -OTHER_X * spread + CONFIG[this.body].scale * 1.08;
    const fitWidth = (Math.max(right, left) * 1.04) / (VIEW_HALF * aspect);
    return { x: 0, base: Math.max(4.4, 8 / aspect), min: Math.max(3, fitWidth) };
  }

  private minZoom() {
    const { base, min } = this.cameraLimits();
    return min / base;
  }

  private desiredCamera() {
    const { x, base, min } = this.cameraLimits();
    const distance = Math.max(base * this.zoom, min) * DIST_K;
    const canvas = this.sceneCanvas;
    const height = canvas?.clientHeight || 1;
    const coveredWidth = Math.max(0, (canvas?.clientWidth || 0) - this.visibleSceneWidth);
    const focalPixels = height / (2 * Math.tan((FOV * Math.PI) / 360));
    const centerOffset = (coveredWidth * distance) / (2 * focalPixels);
    return { x: x + centerOffset, distance };
  }

  private loadTexture(url: string, srgb: boolean, onLoad: (texture: THREE.Texture) => void) {
    const cached = this.textureCache.get(url);
    if (cached) {
      cached.anisotropy = this.maxAnisotropy;
      onLoad(cached);
      return;
    }
    const rendererAtRequest = this.renderer;
    new THREE.TextureLoader().load(
      url,
      (texture) => {
        if (!rendererAtRequest || this.renderer !== rendererAtRequest) {
          texture.dispose();
          return;
        }
        if (srgb) texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = this.maxAnisotropy;
        this.textureCache.set(url, texture);
        onLoad(texture);
        this.requestFrame();
      },
      undefined,
      () => console.warn('Texture not found:', url)
    );
  }

  private createEarth(): THREE.Mesh {
    const material = new THREE.MeshPhongMaterial({
      color: '#2a5d8f',
      specular: new THREE.Color(0x222222),
      shininess: 12,
      emissive: new THREE.Color(0x0b1620),
      emissiveIntensity: 1,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 64, 48), material);

    this.loadTexture('/textures/earth.jpg', true, (texture) => {
      material.map = texture;
      material.color.set(0xffffff);
      material.needsUpdate = true;
    });

    this.createAtmosphere(mesh, 1.12, 0x4da6ff, 2.2, 0.6);
    return mesh;
  }

  private createMars(): THREE.Mesh {
    const material = new THREE.MeshStandardMaterial({
      color: '#9c4a2a',
      roughness: 1,
      metalness: 0,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(MARS_SCALE, 64, 48), material);

    this.loadTexture('/textures/mars.jpg', true, (texture) => {
      material.map = texture;
      material.color.set(0xffffff);
      material.needsUpdate = true;
    });

    this.createAtmosphere(mesh, MARS_SCALE * 1.08, 0xd98a5f, 2.5, 0.6);
    return mesh;
  }

  private createMoon(): THREE.Mesh {
    const material = new THREE.MeshStandardMaterial({
      color: '#8a8a8a',
      roughness: 0.95,
      metalness: 0,
      emissive: new THREE.Color(0x0e1014),
      emissiveIntensity: 1,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(MOON_SCALE, 64, 48), material);
    this.moonMaterial = material;
    this.moonTextureRequested = false;


    this.createAtmosphere(mesh, MOON_SCALE * 1.07, 0xbfd0e8, 3, 0.55);
    return mesh;
  }

  private loadMoonTexture() {
    if (this.moonTextureRequested) return;
    this.moonTextureRequested = true;
    this.loadTexture('/textures/moon.jpg', true, (texture) => {
      this.moonMaterial.map = texture;
      this.moonMaterial.bumpMap = texture;
      this.moonMaterial.bumpScale = 0.5;
      this.moonMaterial.color.set(0xffffff);
      this.moonMaterial.needsUpdate = true;
    });
  }

  private createAtmosphere(planet: THREE.Mesh, radius: number, color: number, power: number, gain: number) {
    const material = new THREE.ShaderMaterial({
      uniforms: {
        glowColor: { value: new THREE.Color(color) },
        power: { value: power },
        gain: { value: gain },
      },
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vView;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vNormal = normalize(normalMatrix * normal);
          vView = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        uniform vec3 glowColor;
        uniform float power;
        uniform float gain;
        varying vec3 vNormal;
        varying vec3 vView;
        void main() {
          float intensity = pow(max(-dot(vNormal, vView), 0.0), power) * gain;
          gl_FragColor = vec4(glowColor, clamp(intensity, 0.0, 1.0));
        }
      `,
      side: THREE.BackSide,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    planet.add(new THREE.Mesh(new THREE.SphereGeometry(radius, 32, 24), material));
  }

  private createMarker(
    planet: THREE.Mesh,
    lat: number,
    lon: number,
    planetRadius: number,
    radiusKm: number,
    fill: { color: number; opacity: number }
  ): THREE.Group {
    const radius = Math.max(radiusKm / R_EARTH, 0.04);
    const group = new THREE.Group();
    group.add(
      new THREE.Mesh(
        new THREE.CircleGeometry(radius, 40),
        new THREE.MeshBasicMaterial({
          color: fill.color,
          transparent: true,
          opacity: fill.opacity,
          depthWrite: false,
          side: THREE.DoubleSide,
          toneMapped: false,
        })
      )
    );


    const ring = new THREE.Mesh(
      new THREE.RingGeometry(radius * 0.93, radius, 40),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, side: THREE.DoubleSide, toneMapped: false })
    );
    ring.renderOrder = 1;
    group.add(ring);
    this.setMarkerPosition(group, lat, lon, planetRadius);
    planet.add(group);
    return group;
  }

  private setMarkerPosition(group: THREE.Group, lat: number, lon: number, planetRadius: number) {
    const position = latLon(lat, lon, planetRadius * 1.004);
    group.position.copy(position);
    group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), position.clone().normalize());
  }

  private createLine() {
    const base: number[] = [];
    for (let i = 0; i <= SEGMENTS; i++) base.push(i / SEGMENTS, 0, 0);
    const geometry = new LineGeometry();
    geometry.setPositions(base);
    const material = new LineMaterial({ color: 0xffffff, linewidth: 2.5, toneMapped: false });
    material.dashed = true;
    material.dashSize = 0.06;
    material.gapSize = 0.04;
    this.line = new Line2(geometry, material);
    this.line.computeLineDistances();
    this.line.frustumCulled = false;
    this.line.visible = false;
    this.scene.add(this.line);

    this.head = new THREE.Mesh(
      new THREE.SphereGeometry(0.03, 24, 16),
      new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false })
    );
    this.head.visible = false;
    this.scene.add(this.head);
  }

  private updateLine() {
    if (!this.selectedAnalog) {
      this.line.visible = false;
      this.head.visible = false;
      return;
    }

    const other = this.other;
    const otherScale = CONFIG[this.body].scale;

    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    this.otherMarkers[this.body].getWorldPosition(a);
    this.earthMarkers[this.body].getWorldPosition(b);

    const normalA = a.clone().sub(other.position).normalize();
    const normalB = b.clone().sub(this.earth.position).normalize();
    const height = ARC_HEIGHT * 1.5;
    const c1 = a.clone().addScaledVector(normalA, height);
    const c2 = b.clone().addScaledVector(normalB, height);

    const bodies = [
      { center: other.position, radius: otherScale * 1.02 },
      { center: this.earth.position, radius: 1 * 1.02 },
    ];
    const tmp = new THREE.Vector3();

    const geometry: any = this.line.geometry;
    const positions = geometry.attributes.instanceStart.data;
    const distances = geometry.attributes.instanceDistanceStart.data;
    const P = positions.array as Float32Array;
    const D = distances.array as Float32Array;

    const point = (t: number, out: THREE.Vector3) => {
      const u = 1 - t;
      const k0 = u * u * u;
      const k1 = 3 * u * u * t;
      const k2 = 3 * u * t * t;
      const k3 = t * t * t;
      out.set(
        k0 * a.x + k1 * c1.x + k2 * c2.x + k3 * b.x,
        k0 * a.y + k1 * c1.y + k2 * c2.y + k3 * b.y,
        k0 * a.z + k1 * c1.z + k2 * c2.z + k3 * b.z
      );
      if (t > 0 && t < 1) {
        for (const { center, radius } of bodies) {
          tmp.copy(out).sub(center);
          const length = tmp.length();
          if (length < radius) out.copy(center).addScaledVector(tmp, radius / length);
        }
      }
      return out;
    };

    const p0 = new THREE.Vector3();
    const p1 = new THREE.Vector3();
    let accumulated = 0;
    const progress = this.drawProgress;
    this.line.visible = progress > 0;
    point(0, p0);
    for (let i = 0; i < SEGMENTS; i++) {
      point((progress * (i + 1)) / SEGMENTS, p1);
      P.set([p0.x, p0.y, p0.z, p1.x, p1.y, p1.z], i * 6);
      D[i * 2] = accumulated;
      accumulated += p0.distanceTo(p1);
      D[i * 2 + 1] = accumulated;
      p0.copy(p1);
    }
    positions.needsUpdate = true;
    distances.needsUpdate = true;

    this.head.visible = progress > 0 && progress < 1;
    this.head.position.copy(p0);
  }

  private requestFrame() {
    if (!this.renderer || this.frameId !== null) return;
    this.frameId = requestAnimationFrame(this.renderFrame);
  }

  private renderFrame = (now: number) => {
    this.frameId = null;
    const renderer = this.renderer;
    if (!renderer) return;

    const forceRender = this.forceNextFrame;
    this.forceNextFrame = false;
    if (!forceRender && now - this.lastRenderTime < FRAME_INTERVAL) {
      this.requestFrame();
      return;
    }

    const dt = Math.min((now - this.previousTime) / 1000, 0.1);
    this.previousTime = now;
    this.lastRenderTime = now;
    (this.line.material as LineMaterial).dashOffset -= DASH_SPEED * dt;

    if (!this.selectedAnalog) {
      const rotation = IDLE_ROTATION_SPEED * dt;
      this.earth.rotation.y += rotation;
      this.mars.rotation.y += rotation;
      this.moon.rotation.y += rotation;
    }

    if (this.selectedAnalog && this.drawProgress < 1) {
      this.drawElapsed += dt;
      const p = Math.min(Math.max(this.drawElapsed / DRAW_DURATION, 0), 1);
      this.drawProgress = easeInOutCubic(p);
      this.lineDirty = true;
    }

    const spread = this.spread();
    if (this.lastSpread === null || Math.abs(spread - this.lastSpread) > 0.0001) {
      this.lastSpread = spread;
      this.lineDirty = true;
    }
    this.earth.position.x = EARTH_X * spread;
    this.mars.position.x = OTHER_X * spread;
    this.moon.position.x = OTHER_X * spread;

    const desired = this.desiredCamera();
    const cameraMoving =
      Math.abs(desired.x - this.cameraX) > 0.001 || Math.abs(desired.distance - this.cameraDistance) > 0.001;
    const k = 1 - Math.exp(-dt * CAMERA_SMOOTHING);
    this.cameraX += (desired.x - this.cameraX) * k;
    this.cameraDistance += (desired.distance - this.cameraDistance) * k;
    this.camera.position.set(this.cameraX, SCENE_VERTICAL_OFFSET, this.cameraDistance);
    this.camera.updateMatrixWorld();

    if (this.aligning && this.selectedAnalog) {
      const earthTarget = this.earthFocus[this.body];
      const otherTarget = this.otherFocus[this.body];
      const alignmentStep = 1 - Math.pow(1 - 0.06, dt * 60);
      this.earth.quaternion.slerp(earthTarget, alignmentStep);
      this.other.quaternion.slerp(otherTarget, alignmentStep);
      if (this.earth.quaternion.angleTo(earthTarget) < 0.001 && this.other.quaternion.angleTo(otherTarget) < 0.001) {
        this.earth.quaternion.copy(earthTarget);
        this.other.quaternion.copy(otherTarget);
        this.aligning = false;
      } else {
        this.lineDirty = true;
      }
    }

    if (this.lineDirty) {
      this.updateLine();
      this.lineDirty = false;
    }
    renderer.render(this.scene, this.camera);

    if (!this.selectedAnalog || this.drawProgress < 1 || this.aligning || cameraMoving || this.line.visible) this.requestFrame();
  };

  private init(canvas: HTMLCanvasElement) {
    this.teardown();
    this.sceneCanvas = canvas;


    this.scene = new THREE.Scene();
    this.view = 'both';
    this.zoom = 1;
    this.aligning = this.selectedAnalog !== null;
    this.dragging = null;
    this.restartDraw();
    this.previousTime = performance.now();
    this.lastRenderTime = 0;
    this.lastSpread = null;
    this.fitAspect = null;
    this.viewportWidth = window.innerWidth;
    this.viewportHeight = window.innerHeight;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer = renderer;
    this.maxAnisotropy = renderer.capabilities.getMaxAnisotropy();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    renderer.setClearColor(0x000000, 0);

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.22));
    const sun = new THREE.DirectionalLight(0xffffff, 3);
    sun.position.set(4, 3, 6);
    this.scene.add(sun);

    this.earth = this.createEarth();
    this.earth.position.set(EARTH_X, 0, 0);
    this.mars = this.createMars();
    this.mars.position.set(OTHER_X, 0, 0);
    this.moon = this.createMoon();
    this.moon.position.set(OTHER_X, 0, 0);
    this.scene.add(this.earth, this.mars, this.moon);

    const front = new THREE.Vector3(0, 0, 1);
    const planets: Record<Body, THREE.Mesh> = { mars: this.mars, moon: this.moon };
    for (const b of BODIES) {
      const { analog, target, scale } = CONFIG[b];
      this.earthMarkers[b] = this.createMarker(this.earth, analog.lat, analog.lon, 1, analog.radiusKm, EARTH_MARKER_FILL);
      this.otherMarkers[b] = this.createMarker(planets[b], target.lat, target.lon, scale, target.radiusKm, OTHER_MARKER_FILL);
      this.earthFocus[b] = new THREE.Quaternion().setFromUnitVectors(latLon(analog.lat, analog.lon).normalize(), front);
      this.otherFocus[b] = new THREE.Quaternion().setFromUnitVectors(latLon(target.lat, target.lon).normalize(), front);
    }
    this.applyBody();

    this.createLine();

    let lastW = 0;
    let lastH = 0;
    const resize = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight || 1;
      if (w === lastW && h === lastH) return;

      const viewportChanged = this.viewportWidth !== window.innerWidth || this.viewportHeight !== window.innerHeight;
      if (this.fitAspect === null || viewportChanged) {
        this.viewportWidth = window.innerWidth;
        this.viewportHeight = window.innerHeight;
        this.fitAspect = w / h;
      }

      lastW = w;
      lastH = h;
      renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      (this.line.material as LineMaterial).resolution.set(w, h);
      this.updateSceneLayout();
      this.lineDirty = true;
      this.forceNextFrame = true;
      if (this.lastRenderTime > 0) {
        if (this.frameId !== null) {
          cancelAnimationFrame(this.frameId);
          this.frameId = null;
        }
        this.renderFrame(performance.now());
      } else {
        this.requestFrame();
      }
    };
    this.resizeObserver = new ResizeObserver(resize);
    this.resizeObserver.observe(canvas);
    resize();

    const initial = this.desiredCamera();
    this.cameraX = initial.x;
    this.cameraDistance = initial.distance;
    this.camera.position.set(this.cameraX, SCENE_VERTICAL_OFFSET, this.cameraDistance);

    const toNdc = (e: PointerEvent | MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      return new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );
    };
    const pick = (e: PointerEvent | MouseEvent) => {
      this.raycaster.setFromCamera(toNdc(e), this.camera);
      return this.raycaster.intersectObjects([this.earth, this.other], false)[0];
    };
    const onDown = (e: PointerEvent) => {
      const hit = pick(e);
      if (!hit) return;
      this.dragging = hit.object;
      this.aligning = false;
      this.lastPointer = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture(e.pointerId);
    };
    const onMove = (e: PointerEvent) => {
      if (!this.dragging) return;
      const dx = e.clientX - this.lastPointer.x;
      const dy = e.clientY - this.lastPointer.y;
      this.lastPointer = { x: e.clientX, y: e.clientY };
      this.dragging.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), dx * 0.006);
      this.dragging.rotateOnWorldAxis(new THREE.Vector3(1, 0, 0), dy * 0.006);
      this.lineDirty = true;
      this.requestFrame();
    };
    const onUp = () => {
      this.dragging = null;
    };
    const onDoubleClick = (e: MouseEvent) => {
      const hit = pick(e);
      if (!hit) {
        this.zone.run(() => this.setView('both'));
        return;
      }
      const next: View = hit.object === this.earth ? 'earth' : 'other';
      this.zone.run(() => this.setView(next));
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const next = this.zoom * (e.deltaY > 0 ? 1.08 : 0.92);
      this.zoom = Math.min(1.8, Math.max(this.minZoom(), next));
      this.requestFrame();
    };
    canvas.addEventListener('pointerdown', onDown);
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerup', onUp);
    canvas.addEventListener('dblclick', onDoubleClick);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    this.cleanups.push(
      () => canvas.removeEventListener('pointerdown', onDown),
      () => canvas.removeEventListener('pointermove', onMove),
      () => canvas.removeEventListener('pointerup', onUp),
      () => canvas.removeEventListener('dblclick', onDoubleClick),
      () => canvas.removeEventListener('wheel', onWheel)
    );

    if (this.body === 'moon') this.loadMoonTexture();
    this.requestFrame();
  }

  
  private teardown() {
    if (this.frameId !== null) {
      cancelAnimationFrame(this.frameId);
      this.frameId = null;
    }
    const renderer = this.renderer;
    if (!renderer) return;
    this.renderer = null;
    this.resizeObserver?.disconnect();
    this.resizeObserver = undefined;
    this.cleanups.forEach((fn) => fn());
    this.cleanups = [];
    this.scene.traverse((o: any) => {
      o.geometry?.dispose?.();
      const materials = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      materials.forEach((m: THREE.Material) => m.dispose());
    });
    this.scene.clear();
    renderer.dispose();
    renderer.forceContextLoss();
  }

  ngOnDestroy() {
    this.panelObserver?.disconnect();
    this.teardown();
    this.textureCache.forEach((t) => t.dispose());
    this.textureCache.clear();
  }
}
