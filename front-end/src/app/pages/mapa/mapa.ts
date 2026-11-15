import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, NgZone, ChangeDetectorRef } from '@angular/core';
import { RouterLink } from '@angular/router';
import * as THREE from 'three';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';

type View = 'both' | 'earth' | 'other';
type Body = 'mars' | 'moon';

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

interface PanelInfo {
  eyebrow: string;
  place: string;
  pct: number;
  desc: string;
  
  values: number[];
}


const PANELS: Record<Body, PanelInfo> = {
  mars: {
    eyebrow: 'MARS ANALOG',
    place: 'ATACAMA',
    pct: 65,
    desc: 'Lava and ash field used in astronaut training. Lava and ash field used in astronaut training.',
    values: [0.85, 0.55, 0.7, 0.8, 0.5, 0.65],
  },
  moon: {
    eyebrow: 'MOON ANALOG',
    place: 'MAUNA KEA',
    pct: 58,
    desc: 'Volcanic terrain used in astronaut training. Volcanic terrain used in astronaut training.',
    values: [0.7, 0.45, 0.8, 0.6, 0.75, 0.55],
  },
};

const RADAR_LABELS = ['Geologia', 'Temperatura', 'Aridez', 'Relevo', 'Altitude', 'Solo'];
const TIMELINE = Array.from({ length: 22 }, (_, i) => ({ year: 2026 + i }));

function buildRadar(values: number[]) {
  const cx = 120, cy = 100, R = 62, L = 80;
  const angle = (i: number) => ((i * 60 - 90) * Math.PI) / 180;
  const pt = (i: number, r: number) => ({ x: cx + r * Math.cos(angle(i)), y: cy + r * Math.sin(angle(i)) });
  const fmt = (p: { x: number; y: number }) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  return {
    rings: [1, 0.66, 0.33].map((k) => RADAR_LABELS.map((_, i) => fmt(pt(i, R * k))).join(' ')),
    axes: RADAR_LABELS.map((_, i) => pt(i, R)),
    data: values.map((v, i) => fmt(pt(i, R * v))).join(' '),
    labels: RADAR_LABELS.map((text, i) => {
      const p = pt(i, L);
      const c = Math.cos(angle(i));
      const s = Math.sin(angle(i));
      return { text, x: p.x, y: p.y, anchor: c > 0.1 ? 'start' : c < -0.1 ? 'end' : 'middle', dy: s < -0.5 ? -1 : s > 0.5 ? 9 : 3 };
    }),
  };
}

const SEGMENTS = 80;
const ARC_HEIGHT = 0.6;
const DASH_SPEED = 0.25;
const CAMERA_SMOOTHING = 4;
const MIN_DISTANCE_FACTOR = 2.5;

const FOV = 18;

const DIST_K = Math.tan((22.5 * Math.PI) / 180) / Math.tan((FOV * Math.PI) / 360);
const EARTH_X = 1.7;
const OTHER_X = -2.1;

const VIEW_HALF = Math.tan((22.5 * Math.PI) / 180);

const FIT_MARGIN = 1.12 * 1.06;


function panelPath(w: number, h: number, bump: boolean): string {
  const r = 20;
  const x0 = bump ? 14 : 0;
  const o = x0 - 13;
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
  selector: 'app-mapa',
  imports: [RouterLink],
  templateUrl: './mapa.html',
  host: {
    class:
      'relative block h-screen overflow-hidden bg-ink font-sans text-cream ' +
      'max-md:h-auto max-md:min-h-screen max-md:overflow-y-auto max-md:overflow-x-hidden ' +
      '[--panel-w:clamp(290px,24vw,361px)] [--panel-top:clamp(76px,12vh,150px)]',
  },
})
export class Mapa implements AfterViewInit, OnDestroy {
  
  @ViewChild('scene') set sceneRef(ref: ElementRef<HTMLCanvasElement> | undefined) {
    if (ref) this.zone.runOutsideAngular(() => this.init(ref.nativeElement));
    else this.teardown();
  }
  @ViewChild('panel') panelEl!: ElementRef<HTMLElement>;
  @ViewChild('glassBody') glassBodyEl!: ElementRef<HTMLElement>;

  readonly cfg = CONFIG;
  readonly timeline = TIMELINE;
  readonly navItems = ['MAP', 'METHODS', 'DATA', 'TEAM'];
  readonly minYear = TIMELINE[0].year;
  readonly maxYear = TIMELINE[TIMELINE.length - 1].year;
  panelOpen = true;
  activeYear = 0;
  info = PANELS.mars;
  radar = buildRadar(PANELS.mars.values);
  view: View = 'both';
  body: Body = 'mars';

  private renderer: THREE.WebGLRenderer | null = null;
  private scene = new THREE.Scene();
  
  private textureCache = new Map<string, THREE.Texture>();
  private maxAnisotropy = 1;
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
  private dragging: THREE.Object3D | null = null;
  private lastPointer = { x: 0, y: 0 };
  private raycaster = new THREE.Raycaster();
  private resizeObserver?: ResizeObserver;
  private panelObserver?: ResizeObserver;
  private cleanups: Array<() => void> = [];
  private previousTime = performance.now();

  constructor(private zone: NgZone, private cdr: ChangeDetectorRef) { }

  ngAfterViewInit() {
    this.zone.runOutsideAngular(() => this.observePanel());
  }

  
  private observePanel() {
    const el = this.panelEl.nativeElement;
    const update = () => {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      if (!w || !h) return;
      const d = panelPath(w, h, window.innerWidth >= 768);
      el.querySelectorAll('path[data-shape]').forEach((p) => p.setAttribute('d', d));
      this.glassBodyEl.nativeElement.style.clipPath = `path('${d}')`;
    };
    this.panelObserver = new ResizeObserver(update);
    this.panelObserver.observe(el);
    update();
  }

  
  private get other(): THREE.Mesh {
    return this.body === 'mars' ? this.mars : this.moon;
  }

  
  stepYear(delta: number) {
    this.activeYear = Math.min(this.timeline.length - 1, Math.max(0, this.activeYear + delta));
  }

  
  setYear(raw: string) {
    const year = Math.round(Number(raw));
    if (!raw || !Number.isFinite(year)) return;
    const clamped = Math.min(this.maxYear, Math.max(this.minYear, year));
    this.activeYear = clamped - this.minYear;
  }

  setView(view: View) {
    this.view = view;
    this.zoom = 1;
    this.aligning = true;

    this.cdr.markForCheck();
  }

  setBody(body: Body) {
    if (this.body === body) return;
    this.body = body;
    this.info = PANELS[body];
    this.radar = buildRadar(this.info.values);
    if (!this.renderer) return;
    this.applyBody();
    this.zoom = 1;
    this.aligning = true;
    this.restartDraw();
  }

  align() {
    this.aligning = true;
  }

  private restartDraw() {
    this.drawElapsed = -DRAW_DELAY;
    this.drawProgress = 0;
  }

  private applyBody() {
    this.mars.visible = this.body === 'mars';
    this.moon.visible = this.body === 'moon';
    for (const b of BODIES) {
      this.earthMarkers[b].visible = b === this.body;
      this.otherMarkers[b].visible = b === this.body;
    }
  }

  
  private spread() {
    return THREE.MathUtils.clamp(this.camera.aspect / 2.1, 1, 2);
  }

  
  private fitSphere(r: number) {
    return (r * FIT_MARGIN) / (VIEW_HALF * Math.min(1, this.camera.aspect));
  }

  private cameraLimits() {
    const aspect = this.camera.aspect;
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
    return { x, distance: Math.max(base * this.zoom, min) * DIST_K };
  }

  private loadTexture(url: string, srgb: boolean, onLoad: (texture: THREE.Texture) => void) {
    const cached = this.textureCache.get(url);
    if (cached) {
      cached.anisotropy = this.maxAnisotropy;
      onLoad(cached);
      return;
    }
    new THREE.TextureLoader().load(
      url,
      (texture) => {
        if (srgb) texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = this.maxAnisotropy;
        this.textureCache.set(url, texture);
        onLoad(texture);
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
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64), material);

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
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(MARS_SCALE, 96, 64), material);

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
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(MOON_SCALE, 96, 64), material);

    this.loadTexture('/textures/moon.jpg', true, (texture) => {
      material.map = texture;
      material.bumpMap = texture;
      material.bumpScale = 0.5;
      material.color.set(0xffffff);
      material.needsUpdate = true;
    });


    this.createAtmosphere(mesh, MOON_SCALE * 1.07, 0xbfd0e8, 3, 0.55);
    return mesh;
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
    planet.add(new THREE.Mesh(new THREE.SphereGeometry(radius, 64, 48), material));
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
        new THREE.CircleGeometry(radius, 64),
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
      new THREE.RingGeometry(radius * 0.93, radius, 64),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, side: THREE.DoubleSide, toneMapped: false })
    );
    ring.renderOrder = 1;
    group.add(ring);
    const position = latLon(lat, lon, planetRadius * 1.004);
    group.position.copy(position);
    group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), position.clone().normalize());
    planet.add(group);
    return group;
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
    this.scene.add(this.line);

    this.head = new THREE.Mesh(
      new THREE.SphereGeometry(0.03, 24, 16),
      new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false })
    );
    this.head.visible = false;
    this.scene.add(this.head);
  }

  private updateLine() {
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

  private init(canvas: HTMLCanvasElement) {
    this.teardown();


    this.scene = new THREE.Scene();
    this.view = 'both';
    this.zoom = 1;
    this.aligning = true;
    this.dragging = null;
    this.restartDraw();
    this.previousTime = performance.now();

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer = renderer;
    this.maxAnisotropy = renderer.capabilities.getMaxAnisotropy();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
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
      lastW = w;
      lastH = h;
      renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      (this.line.material as LineMaterial).resolution.set(w, h);
    };
    this.resizeObserver = new ResizeObserver(resize);
    this.resizeObserver.observe(canvas);
    resize();

    const initial = this.desiredCamera();
    this.cameraX = initial.x;
    this.cameraDistance = initial.distance;
    this.camera.position.set(this.cameraX, 0, this.cameraDistance);

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

    renderer.setAnimationLoop(() => {
      const now = performance.now();
      const dt = Math.min((now - this.previousTime) / 1000, 0.1);
      this.previousTime = now;

      (this.line.material as LineMaterial).dashOffset -= DASH_SPEED * dt;

      if (this.drawProgress < 1) {
        this.drawElapsed += dt;
        const p = Math.min(Math.max(this.drawElapsed / DRAW_DURATION, 0), 1);
        this.drawProgress = easeInOutCubic(p);
      }

      resize();

      const spread = this.spread();
      this.earth.position.x = EARTH_X * spread;
      this.mars.position.x = OTHER_X * spread;
      this.moon.position.x = OTHER_X * spread;

      const desired = this.desiredCamera();
      const k = 1 - Math.exp(-dt * CAMERA_SMOOTHING);
      this.cameraX += (desired.x - this.cameraX) * k;
      this.cameraDistance += (desired.distance - this.cameraDistance) * k;
      this.camera.position.set(this.cameraX, 0, this.cameraDistance);
      this.camera.updateMatrixWorld();

      if (this.aligning) {
        this.earth.quaternion.slerp(this.earthFocus[this.body], 0.06);
        this.other.quaternion.slerp(this.otherFocus[this.body], 0.06);
      }

      this.updateLine();
      renderer.render(this.scene, this.camera);
    });
  }

  
  private teardown() {
    const renderer = this.renderer;
    if (!renderer) return;
    this.renderer = null;
    renderer.setAnimationLoop(null);
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