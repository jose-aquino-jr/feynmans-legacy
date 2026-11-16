import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  NgZone,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subject, switchMap } from 'rxjs';
import * as THREE from 'three';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';

import { NICHO_DA_VARIAVEL, NOMES_LOCAIS } from '../../core/nichos';
import {
  Candidato,
  ConsultaRecomendacoes,
  Corpo,
  Estrategia,
  EstadoBusca,
  GrupoBase,
  OpcoesResponse,
  RecomendacoesResponse,
} from '../../core/recomendacoes.models';
import { RecomendacoesService } from '../../core/recomendacoes.service';
import { Cenario, PrimeiraPessoa } from './primeira-pessoa';
import { aleatorio } from './terreno';

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
type SearchStatus = 'idle' | 'loading' | 'calculating' | 'error' | 'done';

const MIN_YEAR = 2026;
const MAX_YEAR = 2100;
/** Cada critério do design é um nicho da API (`nicho` em /analogos/recomendacoes). */
const CRITERIA: { key: Criterion; label: string; niche: string }[] = [
  { key: 'thermal', label: 'Thermal', niche: 'termico' },
  { key: 'lightingRadiation', label: 'Lighting and radiation', niche: 'iluminacao_radiacao' },
  { key: 'waterIce', label: 'Water and ice', niche: 'agua_gelo' },
  { key: 'waterAridity', label: 'Water and aridity', niche: 'agua_aridez' },
  { key: 'terrain', label: 'Terrain', niche: 'terreno' },
  { key: 'geology', label: 'Geology', niche: 'geologia' },
  { key: 'surfaceDust', label: 'Surface and dust', niche: 'superficie_poeira' },
  { key: 'windDustProcesses', label: 'Wind and dust processes', niche: 'processos' },
  {
    key: 'biologyHabitability',
    label: 'Biology and habitability',
    niche: 'biologia_habitabilidade',
  },
  { key: 'subsurface', label: 'Subsurface', niche: 'subsuperficie' },
  { key: 'atmosphere', label: 'Atmosphere', niche: 'atmosfera' },
  { key: 'operations', label: 'Operations', niche: 'operacoes' },
];
const CRITERION_OF_NICHE = Object.fromEntries(CRITERIA.map((c) => [c.niche, c.key])) as Record<
  string,
  Criterion
>;

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

const CORPO: Record<Body, Corpo> = { mars: 'marte', moon: 'lua' };

const R_EARTH = 6371;
const R_MARS = 3396.19;
const R_MOON = 1737.4;
const MARS_SCALE = R_MARS / R_EARTH;
const MOON_SCALE = R_MOON / R_EARTH;

const BODIES: Body[] = ['mars', 'moon'];

const EARTH_MARKER_FILL = { color: 0xde7d28, opacity: 0.71 };
const OTHER_MARKER_FILL: Record<Body, { color: number; opacity: number }> = {
  mars: { color: 0xffb36b, opacity: 0.78 },
  moon: { color: 0xf6e8c9, opacity: 0.78 },
};

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

/** Um candidato da API pronto para a lista, o radar e o globo. */
interface AnalogResult {
  id: string;
  name: string;
  region: string;
  lat: number;
  lon: number;
  similarity: number;
  coverage: number;
  nicheScores: Partial<Record<Criterion, number>>;
  matchedCriteria: Criterion[];
  summary: string;
  fit: string;
  shortfall: string;
  psychodata: Psychodata;
  candidato: Candidato;
  grupo: GrupoBase;
  resposta: RecomendacoesResponse;
}

interface BaseOption {
  value: string;
  label: string;
  lat: number;
  lon: number;
  niches: string[];
}

const BODY_DETAILS: Record<Body, { label: string; limitation: string; missionUse: string }> = {
  mars: {
    label: 'MARS',
    limitation:
      'Earth still has stronger gravity, a dense atmosphere, and a protective magnetic field. This site cannot reproduce Martian pressure, radiation, or dust behavior.',
    missionUse:
      'Rehearse traverse planning, sample collection, instrument deployment, and crew procedures before a Mars mission.',
  },
  moon: {
    label: 'MOON',
    limitation:
      'This site cannot reproduce the lunar vacuum, one-sixth gravity, radiation, electrostatic dust, or extreme thermal cycle.',
    missionUse:
      'Rehearse geological sampling, equipment deployment, navigation, and crew procedures for lunar surface operations.',
  },
};

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
].map((label, i) => ({ value: String(i + 1), label }));

const STRATEGY_LABELS: Record<Estrategia, string> = {
  recursiva: 'Recursive LightGBM projection (default)',
  auto: 'Direct LightGBM when available, recursive after',
  sazonal: 'Seasonal scenario (same month, last observed year)',
};

const ORIGIN_LABELS: Record<string, string> = {
  observada: 'Observed',
  prevista: 'Forecast (direct LightGBM)',
  extrapolada: 'Exploratory projection (recursive)',
  cenario_sazonal: 'Seasonal scenario',
};

const GROUP_STATUS: Record<string, string> = {
  sem_dados: 'The API has no Earth data for this month.',
  sem_candidatos: 'No Earth location reaches the minimum coverage. Try a lower coverage.',
  nicho_incompativel: 'The selected variables do not apply to this base.',
};

const buildTimeline = (min: number, max: number) =>
  Array.from({ length: max - min + 1 }, (_, i) => ({ year: min + i }));

function buildRadar(
  values: number[],
  selected: Criterion[] = CRITERIA.map((criterion) => criterion.key),
) {
  const cx = 120,
    cy = 100,
    R = 55,
    L = 82;
  const angle = (i: number) => ((i * (360 / CRITERIA.length) - 90) * Math.PI) / 180;
  const pt = (i: number, r: number) => ({
    x: cx + r * Math.cos(angle(i)),
    y: cy + r * Math.sin(angle(i)),
  });
  const fmt = (p: { x: number; y: number }) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  return {
    rings: [1, 0.66, 0.33].map((k) => CRITERIA.map((_, i) => fmt(pt(i, R * k))).join(' ')),
    axes: CRITERIA.map((_, i) => pt(i, R)),
    data: values
      .map((v, i) => fmt(pt(i, R * (selected.includes(CRITERIA[i].key) ? v : 0))))
      .join(' '),
    labels: CRITERIA.map(({ key }, i) => {
      const p = pt(i, L);
      const c = Math.cos(angle(i));
      const s = Math.sin(angle(i));
      return {
        text: RADAR_LABELS[key],
        x: p.x,
        y: p.y,
        anchor: c > 0.1 ? 'start' : c < -0.1 ? 'end' : 'middle',
        dy: s < -0.5 ? -1 : s > 0.5 ? 9 : 3,
        selected: selected.includes(key),
      };
    }),
  };
}

const mean = (values: number[]) =>
  values.reduce((total, value) => total + value, 0) / values.length;
const coord = (lat: number, lon: number) =>
  `${Math.abs(lat).toFixed(2)}°${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(2)}°${lon < 0 ? 'W' : 'E'}`;

/** Média das notas das variáveis de cada nicho (0–100); nichos sem dado ficam de fora. */
function nicheScores(candidato: Candidato, corpo: Corpo): Partial<Record<Criterion, number>> {
  const groups: Partial<Record<Criterion, number[]>> = {};
  for (const [variable, score] of Object.entries(candidato.notas_criterios)) {
    const criterion = CRITERION_OF_NICHE[NICHO_DA_VARIAVEL[corpo][variable]];
    if (criterion && score !== null) (groups[criterion] ??= []).push(score);
  }
  return Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, mean(v!)])) as Partial<
    Record<Criterion, number>
  >;
}

/** Indicadores ilustrativos e estáveis por local (o painel avisa que são simulados). */
function simulatedPsychodata(id: string): Psychodata {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const next = () => 40 + ((h = (h * 1103515245 + 12345) >>> 0) % 51);
  return { stress: next(), sleep: next(), workload: next(), cohesion: next(), isolation: next() };
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
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta),
  );
}

/** Distância máxima (px) de um clique até a linha para abrir a primeira pessoa. */
const LINE_HIT_PX = 14;

@Component({
  selector: 'app-map-page',
  imports: [RouterLink, PrimeiraPessoa],
  templateUrl: './mapa.html',
  host: {
    class:
      'relative block h-screen overflow-hidden bg-ink font-sans text-cream ' +
      'max-md:h-auto max-md:min-h-screen max-md:overflow-y-auto max-md:overflow-x-hidden ' +
      '[--panel-w:clamp(290px,24vw,361px)] [--panel-top:clamp(148px,16vh,176px)] [--nav-right-offset:calc(var(--panel-w)*0.45)]',
  },
})
export class MapPage implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('scene', { static: true }) set sceneRef(
    ref: ElementRef<HTMLCanvasElement> | undefined,
  ) {
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
  readonly bodyDetails = BODY_DETAILS;
  readonly months = MONTHS;
  readonly coverageOptions = [50, 60, 70, 80, 90, 100];
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
  /** Preenchidos por GET /analogos/recomendacoes/opcoes. */
  minYear = MIN_YEAR;
  maxYear = MAX_YEAR;
  timeline = buildTimeline(MIN_YEAR, MAX_YEAR);
  baseOptions: Record<Body, BaseOption[]> = { mars: [], moon: [] };
  optionsLoading = true;
  projectionModels = (Object.keys(STRATEGY_LABELS) as Estrategia[]).map((value) => ({
    value,
    label: STRATEGY_LABELS[value],
  }));
  analogCount = 100;
  optionsError: string | null = null;

  panelOpen = false;
  filtersModalOpen = false;
  hasSearched = false;
  selectedCriteria: Criterion[] = [];
  searchYearValue = String(MIN_YEAR);
  searchMonth = '8';
  baseValue = '';
  neighborsPerBase = 10;
  minimumCoverage = 70;
  futureEarthState: Estrategia = 'recursiva';
  activeYear = 0;
  results: AnalogResult[] = [];
  selectedAnalog: AnalogResult | null = null;
  radar = buildRadar(
    CRITERIA.map(() => 0),
    [],
  );
  view: View = 'both';
  body: Body = 'mars';

  /** Estado da consulta à API mostrado no painel. */
  searchStatus: SearchStatus = 'idle';
  searchMessage = '';
  searchContext = '';

  /** Cena em primeira pessoa aberta a partir da linha (null = globo). */
  primeiraPessoa: { cenarios: Cenario[]; inicial: number } | null = null;
  /** Menu que aparece ao clicar na linha, em px relativos ao canvas. */
  menuLinha: { x: number; y: number } | null = null;
  /** Pontos do arco em coordenadas de mundo (de Lua/Marte até a Terra). */
  private arcPoints: THREE.Vector3[] = [];

  private readonly api = inject(RecomendacoesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searches = new Subject<ConsultaRecomendacoes>();
  private searchCriteria: Criterion[] = [];
  private searchSubset = false;

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

  constructor(
    private zone: NgZone,
    private cdr: ChangeDetectorRef,
  ) {}

  /** Critérios que a base escolhida aceita (a Lua não tem aridez, processos nem biologia). */
  get criteria() {
    const base = this.allBases.find((b) => b.value === this.baseValue);
    return base ? CRITERIA.filter((c) => base.niches.includes(c.niche)) : CRITERIA;
  }

  get allBases(): BaseOption[] {
    return [...this.baseOptions.mars, ...this.baseOptions.moon];
  }

  get canSearch() {
    return (
      this.selectedCriteria.length > 0 && this.validSearchYear !== null && this.baseValue !== ''
    );
  }

  get allCriteriaSelected() {
    return this.selectedCriteria.length === this.criteria.length;
  }

  private get validSearchYear() {
    const year = Number(this.searchYearValue);
    return this.searchYearValue.trim() !== '' &&
      Number.isInteger(year) &&
      year >= this.minYear &&
      year <= this.maxYear
      ? year
      : null;
  }

  ngOnInit() {
    this.loadOptions();
    this.searches
      .pipe(
        switchMap((query) => this.api.buscar(query)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((state) => this.onSearchState(state));
  }

  /** Carrega as bases e os limites diretamente do endpoint público de opções da API. */
  loadOptions() {
    this.optionsLoading = true;
    this.optionsError = null;
    this.api
      .opcoes()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (options) => this.applyOptions(options),
        error: (error: unknown) => {
          const status = (error as { status?: number })?.status;
          this.optionsLoading = false;
          this.optionsError = status
            ? `The recommendations API returned HTTP ${status}. Check that the API is running and its /opcoes endpoint is available.`
            : 'Could not reach the recommendations API. Check the API server and the /api proxy.';
          this.cdr.markForCheck();
        },
      });
  }

  private applyOptions(options: OpcoesResponse) {
    const bases: Record<Body, BaseOption[]> = { mars: [], moon: [] };
    for (const base of options.bases) {
      bases[base.corpo === 'lua' ? 'moon' : 'mars'].push({
        value: base.base_id,
        label: base.nome,
        // A ausência de coordenadas não deve esconder uma base devolvida pela API.
        lat: base.latitude ?? CONFIG[base.corpo === 'lua' ? 'moon' : 'mars'].target.lat,
        lon: base.longitude ?? CONFIG[base.corpo === 'lua' ? 'moon' : 'mars'].target.lon,
        niches: base.nichos,
      });
    }
    this.baseOptions = bases;
    if (!bases[this.body].some((base) => base.value === this.baseValue)) {
      this.baseValue = bases[this.body][0]?.value ?? '';
    }
    this.minYear = Math.floor(options.meses_observados[0] / 100);
    this.maxYear = Math.floor(options.anomes_max / 100);
    this.timeline = buildTimeline(this.minYear, this.maxYear);
    const year = Math.min(this.maxYear, Math.max(this.minYear, new Date().getFullYear()));
    this.searchYearValue = String(year);
    this.activeYear = year - this.minYear;
    this.analogCount = options.k_max;
    this.minimumCoverage = Math.round(options.cobertura_minima_padrao * 100);
    this.projectionModels = options.publicacao.estrategias.map((value) => ({
      value,
      label: STRATEGY_LABELS[value] ?? value,
    }));
    this.futureEarthState = options.publicacao.estrategia_padrao_futuro;
    this.optionsLoading = false;
    this.optionsError = options.bases.length
      ? null
      : 'The recommendations API responded successfully but returned no bases.';
    this.cdr.markForCheck();
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
    else if (this.menuLinha) this.menuLinha = null;
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
    if (Number.isInteger(value) && value >= 1 && value <= this.analogCount) {
      this.neighborsPerBase = value;
    }
  }

  setMinimumCoverage(raw: string) {
    const value = Number(raw);
    if (this.coverageOptions.includes(value)) this.minimumCoverage = value;
  }

  setStrategy(raw: string) {
    if (raw in STRATEGY_LABELS) this.futureEarthState = raw as Estrategia;
  }

  /** A base define o corpo: escolher uma base da Lua troca o globo para a Lua. */
  setBase(value: string) {
    this.baseValue = value;
    const body: Body = this.baseOptions.moon.some((b) => b.value === value) ? 'moon' : 'mars';
    if (body !== this.body) this.setBody(body, false);
    const allowed = new Set(this.criteria.map((c) => c.key));
    this.selectedCriteria = this.selectedCriteria.filter((c) => allowed.has(c));
  }

  searchAnalogs() {
    if (!this.canSearch) return;

    this.closeFilters();
    this.hasSearched = true;
    this.panelOpen = true;
    this.activeYear = this.validSearchYear! - this.minYear;
    this.runSearch();
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

  /** Clique na linha do tempo: refaz a busca no mesmo mês daquele ano. */
  selectYear(index: number) {
    this.activeYear = index;
    this.searchYearValue = String(this.minYear + index);
    if (this.hasSearched && this.canSearch) this.searchAnalogs();
  }

  /**
   * Um nicho vai direto para a API; todos viram `Todos`. Vários (não todos) também
   * consultam `Todos`, com mais candidatos, e reordenam pela média dos nichos escolhidos.
   */
  private runSearch() {
    const year = this.validSearchYear!;
    const criteria = this.selectedCriteria.filter((c) =>
      this.criteria.some((allowed) => allowed.key === c),
    );
    const all = criteria.length === this.criteria.length;
    const subset = !all && criteria.length > 1;
    const single =
      !all && criteria.length === 1 ? CRITERIA.find((c) => c.key === criteria[0])!.niche : null;
    this.searchCriteria = criteria;
    this.searchSubset = subset;
    this.results = [];
    this.searches.next({
      anomes: year * 100 + Number(this.searchMonth),
      nicho: single ?? 'Todos',
      corpo: CORPO[this.body],
      base_id: this.baseValue,
      k: subset
        ? Math.min(this.analogCount, Math.max(this.neighborsPerBase * 5, 50))
        : this.neighborsPerBase,
      cobertura_minima: this.minimumCoverage / 100,
      estrategia: this.futureEarthState,
    });
  }

  private onSearchState(state: EstadoBusca) {
    switch (state.tipo) {
      case 'carregando':
        this.searchStatus = 'loading';
        this.searchMessage = 'Querying the analog API…';
        break;
      case 'calculando': {
        const p = state.progresso;
        this.searchStatus = 'calculating';
        this.searchMessage = `Projecting Earth to this month… ${p.meses_calculados}/${p.meses_necessarios} months${p.na_fila ? ' (queued)' : ''}`;
        break;
      }
      case 'falha':
        this.searchStatus = 'error';
        this.searchMessage = `${state.mensagem} (${state.codigo})`;
        break;
      case 'sucesso':
        this.showResults(state.resposta, state.consulta);
        break;
    }
    this.cdr.markForCheck();
  }

  private showResults(response: RecomendacoesResponse, query: ConsultaRecomendacoes) {
    const group =
      response.resultados.find((g) => g.base_id === query.base_id) ?? response.resultados[0];
    const month = MONTHS[(response.anomes % 100) - 1]?.label ?? '';
    this.searchContext = `${ORIGIN_LABELS[response.origem] ?? response.origem} · ${month} ${Math.floor(response.anomes / 100)}`;
    this.searchStatus = 'done';
    if (!group || group.candidatos.length === 0) {
      this.results = [];
      this.searchMessage =
        (group && GROUP_STATUS[group.status]) || 'No analog locations for these settings.';
      return;
    }
    let results = group.candidatos.map((c) => this.toResult(c, group, response));
    if (this.searchSubset) {
      results = results.sort((a, b) => b.similarity - a.similarity).slice(0, this.neighborsPerBase);
    }
    this.results = results;
    this.searchMessage = '';
  }

  private toResult(c: Candidato, group: GrupoBase, response: RecomendacoesResponse): AnalogResult {
    const scores = nicheScores(c, group.corpo);
    const matched = this.searchCriteria;
    const matchedScores = matched.map((k) => scores[k]).filter((v): v is number => v !== undefined);
    const similarity = Math.round(
      this.searchSubset && matchedScores.length ? mean(matchedScores) : c.nota,
    );
    const label = (k: Criterion) => CRITERIA.find((x) => x.key === k)!.label;
    const scored = matched
      .filter((k) => scores[k] !== undefined)
      .sort((a, b) => scores[b]! - scores[a]!);
    const strong = scored.filter((k) => scores[k]! >= 75);
    const weak = scored.filter((k) => scores[k]! < 50);
    const missing = matched.filter((k) => scores[k] === undefined);
    const named = NOMES_LOCAIS[`${c.latitude},${c.longitude}`];
    const body: Body = group.corpo === 'lua' ? 'moon' : 'mars';

    return {
      id: c.location_id,
      name: named?.regiao ?? `Site ${c.location_id}`,
      region: [named?.pais, coord(c.latitude, c.longitude)].filter(Boolean).join(' · '),
      lat: c.latitude,
      lon: c.longitude,
      similarity,
      coverage: Math.round(c.cobertura * 100),
      nicheScores: scores,
      matchedCriteria: matched,
      summary:
        `Earth grid cell ${c.location_id}, #${c.posicao} of ${group.total_elegiveis} eligible sites for ${group.nome}` +
        `${this.searchSubset ? ' in the all-criteria ranking' : ''}. ` +
        `${Math.round(c.cobertura * 100)}% of the criteria weight has data (${(ORIGIN_LABELS[response.origem] ?? response.origem).toLowerCase()} values).`,
      fit: strong.length
        ? `Strongest niches: ${strong.map((k) => `${label(k)} (${Math.round(scores[k]!)})`).join(', ')}.`
        : scored.length
          ? `No selected niche reaches 75; the closest is ${label(scored[0])} (${Math.round(scores[scored[0]]!)}).`
          : 'No selected niche has data at this site.',
      shortfall: [
        weak.length
          ? `Weak niches: ${weak.map((k) => `${label(k)} (${Math.round(scores[k]!)})`).join(', ')}.`
          : '',
        missing.length ? `No data for ${missing.map(label).join(', ')}.` : '',
        BODY_DETAILS[body].limitation,
      ]
        .filter(Boolean)
        .join(' '),
      psychodata: simulatedPsychodata(c.location_id),
      candidato: c,
      grupo: group,
      resposta: response,
    };
  }

  selectAnalog(result: AnalogResult) {
    this.selectedAnalog = result;
    this.radar = buildRadar(
      CRITERIA.map(({ key }) => (result.nicheScores[key] ?? 0) / 100),
      result.matchedCriteria,
    );

    const base = this.allBases.find((b) => b.value === result.grupo.base_id);
    const target = {
      lat: result.grupo.latitude ?? base?.lat ?? CONFIG[this.body].target.lat,
      lon: result.grupo.longitude ?? base?.lon ?? CONFIG[this.body].target.lon,
    };
    const scale = CONFIG[this.body].scale;
    this.setMarkerPosition(this.earthMarkers[this.body], result.lat, result.lon, 1);
    this.setMarkerPosition(this.otherMarkers[this.body], target.lat, target.lon, scale);

    const front = new THREE.Vector3(0, 0, 1);
    this.earthFocus[this.body] = new THREE.Quaternion().setFromUnitVectors(
      latLon(result.lat, result.lon).normalize(),
      front,
    );
    this.otherFocus[this.body] = new THREE.Quaternion().setFromUnitVectors(
      latLon(target.lat, target.lon).normalize(),
      front,
    );

    this.applyBody();
    this.zoom = 1;
    this.aligning = true;
    this.restartDraw();
    this.requestFrame();
  }

  backToResults() {
    this.selectedAnalog = null;
    this.menuLinha = null;
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

  setBody(body: Body, search = true) {
    if (this.body === body) return;
    this.body = body;
    this.selectedAnalog = null;
    this.menuLinha = null;
    this.results = [];
    if (!this.baseOptions[body].some((b) => b.value === this.baseValue)) {
      this.baseValue = this.baseOptions[body][0]?.value ?? '';
    }
    const allowed = new Set(this.criteria.map((c) => c.key));
    this.selectedCriteria = this.selectedCriteria.filter((c) => allowed.has(c));
    if (search && this.hasSearched) {
      if (this.canSearch) this.runSearch();
      else {
        this.searchStatus = 'error';
        this.searchMessage =
          'None of the selected variables applies to this body. Open Analysis settings to choose others.';
      }
    }
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
      () => console.warn('Texture not found:', url),
    );
  }

  private createStarfield(): THREE.Points {
    const random = aleatorio(42);
    const positions = new Float32Array(900 * 3);
    for (let i = 0; i < 900; i++) {
      const direction = new THREE.Vector3(
        random() * 2 - 1,
        random() * 2 - 1,
        random() * 2 - 1,
      ).normalize();
      const distance = 14 + random() * 14;
      positions.set(
        [direction.x * distance, direction.y * distance, direction.z * distance],
        i * 3,
      );
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return new THREE.Points(
      geometry,
      new THREE.PointsMaterial({
        color: 0xfff1d6,
        size: 0.035,
        sizeAttenuation: true,
        transparent: true,
        opacity: 0.75,
      }),
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
      material.bumpMap = texture;
      material.bumpScale = 0.08;
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

  private createAtmosphere(
    planet: THREE.Mesh,
    radius: number,
    color: number,
    power: number,
    gain: number,
  ) {
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
    fill: { color: number; opacity: number },
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
        }),
      ),
    );

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(radius * 0.93, radius, 40),
      new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        side: THREE.DoubleSide,
        toneMapped: false,
      }),
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
      new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }),
    );
    this.head.visible = false;
    this.scene.add(this.head);
  }

  private updateLine() {
    if (!this.selectedAnalog) {
      this.line.visible = false;
      this.head.visible = false;
      this.arcPoints = [];
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
        k0 * a.z + k1 * c1.z + k2 * c2.z + k3 * b.z,
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
    this.arcPoints = [p0.clone()];
    for (let i = 0; i < SEGMENTS; i++) {
      point((progress * (i + 1)) / SEGMENTS, p1);
      this.arcPoints.push(p1.clone());
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
    // Com a primeira pessoa aberta, o globo fica parado (retoma ao fechar).
    if (!renderer || this.primeiraPessoa) return;

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
      Math.abs(desired.x - this.cameraX) > 0.001 ||
      Math.abs(desired.distance - this.cameraDistance) > 0.001;
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
      if (
        this.earth.quaternion.angleTo(earthTarget) < 0.001 &&
        this.other.quaternion.angleTo(otherTarget) < 0.001
      ) {
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

    if (
      !this.selectedAnalog ||
      this.drawProgress < 1 ||
      this.aligning ||
      cameraMoving ||
      this.line.visible
    )
      this.requestFrame();
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
    this.scene.add(this.createStarfield());
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
      this.earthMarkers[b] = this.createMarker(
        this.earth,
        analog.lat,
        analog.lon,
        1,
        analog.radiusKm,
        EARTH_MARKER_FILL,
      );
      this.otherMarkers[b] = this.createMarker(
        planets[b],
        target.lat,
        target.lon,
        scale,
        target.radiusKm,
        OTHER_MARKER_FILL[b],
      );
      this.earthFocus[b] = new THREE.Quaternion().setFromUnitVectors(
        latLon(analog.lat, analog.lon).normalize(),
        front,
      );
      this.otherFocus[b] = new THREE.Quaternion().setFromUnitVectors(
        latLon(target.lat, target.lon).normalize(),
        front,
      );
    }
    this.applyBody();

    this.createLine();

    let lastW = 0;
    let lastH = 0;
    const resize = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight || 1;
      if (w === lastW && h === lastH) return;

      const viewportChanged =
        this.viewportWidth !== window.innerWidth || this.viewportHeight !== window.innerHeight;
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
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
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
    // Clique na linha (sem arrastar) abre o menu da primeira pessoa
    let downAt = { x: 0, y: 0 };
    const onLineDown = (e: PointerEvent) => (downAt = { x: e.clientX, y: e.clientY });
    const onLineHover = (e: PointerEvent) => {
      if (!this.dragging) canvas.style.cursor = this.nearLine(e) !== null ? 'pointer' : '';
    };
    const onClick = (e: MouseEvent) => {
      if (Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5) return;
      const hit = this.nearLine(e);
      if (!hit && !this.menuLinha) return;
      this.zone.run(() => {
        this.menuLinha = hit;
        this.cdr.markForCheck();
      });
    };
    canvas.addEventListener('pointerdown', onDown);
    canvas.addEventListener('pointerdown', onLineDown);
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointermove', onLineHover);
    canvas.addEventListener('pointerup', onUp);
    canvas.addEventListener('click', onClick);
    canvas.addEventListener('dblclick', onDoubleClick);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    this.cleanups.push(
      () => canvas.removeEventListener('pointerdown', onDown),
      () => canvas.removeEventListener('pointerdown', onLineDown),
      () => canvas.removeEventListener('pointermove', onMove),
      () => canvas.removeEventListener('pointermove', onLineHover),
      () => canvas.removeEventListener('pointerup', onUp),
      () => canvas.removeEventListener('click', onClick),
      () => canvas.removeEventListener('dblclick', onDoubleClick),
      () => canvas.removeEventListener('wheel', onWheel),
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

  /** Posição do clique (px no canvas) se estiver sobre a linha desenhada; senão null. */
  private nearLine(e: MouseEvent): { x: number; y: number } | null {
    const canvas = this.sceneCanvas;
    if (!canvas || !this.line?.visible || this.arcPoints.length < 2) return null;
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const v = new THREE.Vector3();
    const toScreen = (p: THREE.Vector3) => {
      v.copy(p).project(this.camera);
      return { x: ((v.x + 1) / 2) * rect.width, y: ((1 - v.y) / 2) * rect.height };
    };
    let a = toScreen(this.arcPoints[0]);
    for (let i = 1; i < this.arcPoints.length; i++) {
      const b = toScreen(this.arcPoints[i]);
      const dx = b.x - a.x,
        dy = b.y - a.y;
      const t = THREE.MathUtils.clamp(
        ((px - a.x) * dx + (py - a.y) * dy) / (dx * dx + dy * dy || 1),
        0,
        1,
      );
      if (Math.hypot(a.x + t * dx - px, a.y + t * dy - py) <= LINE_HIT_PX) return { x: px, y: py };
      a = b;
    }
    return null;
  }

  /** Abre a primeira pessoa numa ponta da linha, com as variáveis do análogo selecionado na API. */
  entrarPrimeiraPessoa(lado: 'corpo' | 'terra') {
    const analog = this.selectedAnalog;
    if (!analog) return;
    const { grupo, candidato, resposta } = analog;
    const nomes = Object.fromEntries(
      grupo.criterios.map((c) => [c.variavel, { nome: c.nome, unidade: c.unidade }]),
    );
    const month = MONTHS[(resposta.anomes % 100) - 1]?.label ?? '';
    const cenarios: Cenario[] = [
      {
        mundo: grupo.corpo,
        papel: 'alvo',
        titulo: `${grupo.corpo === 'lua' ? 'Moon' : 'Mars'} · ${grupo.nome}`,
        lat: grupo.latitude ?? CONFIG[this.body].target.lat,
        lon: grupo.longitude ?? CONFIG[this.body].target.lon,
        fonte: 'Target values of the base (API)',
        nomes,
        variaveis: Object.fromEntries(grupo.criterios.map((c) => [c.variavel, c.alvo])),
      },
      {
        mundo: 'terra',
        papel: 'análogo',
        titulo: `Earth · ${analog.name} (${analog.similarity}%)`,
        lat: candidato.latitude,
        lon: candidato.longitude,
        nomes,
        variaveis: candidato.valores,
        fonte: `${ORIGIN_LABELS[resposta.origem] ?? resposta.origem} · ${month} ${Math.floor(resposta.anomes / 100)} (API)`,
      },
    ];
    this.menuLinha = null;
    this.primeiraPessoa = { cenarios, inicial: lado === 'corpo' ? 0 : 1 };
  }

  fecharPrimeiraPessoa() {
    this.primeiraPessoa = null;
    this.forceNextFrame = true;
    this.requestFrame();
  }

  ngOnDestroy() {
    this.panelObserver?.disconnect();
    this.teardown();
    this.textureCache.forEach((t) => t.dispose());
    this.textureCache.clear();
  }
}
