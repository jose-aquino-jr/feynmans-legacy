import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, NgZone } from '@angular/core';
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

const SEGMENTS = 80;
const ARC_HEIGHT = 0.6;
const DASH_SPEED = 0.25;
const CAMERA_SMOOTHING = 4;
const MIN_DISTANCE_FACTOR = 2.5;

function latLon(lat: number, lon: number, r = 1): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
}

@Component({
  selector: 'app-mapa',
  imports: [RouterLink],
  templateUrl: './mapa.html',
  styleUrl: './mapa.css',
})
export class Mapa implements AfterViewInit, OnDestroy {
  @ViewChild('scene') sceneEl!: ElementRef<HTMLCanvasElement>;
  @ViewChild('marsLabel') marsLabelEl!: ElementRef<HTMLElement>;
  @ViewChild('earthLabel') earthLabelEl!: ElementRef<HTMLElement>;

  readonly cfg = CONFIG;
  view: View = 'both';
  body: Body = 'mars';

  private renderer!: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
  private earth!: THREE.Mesh;
  private mars!: THREE.Mesh;
  private moon!: THREE.Mesh;
  private earthMarkers = {} as Record<Body, THREE.Group>;
  private otherMarkers = {} as Record<Body, THREE.Group>;
  private earthFocus = {} as Record<Body, THREE.Quaternion>;
  private otherFocus = {} as Record<Body, THREE.Quaternion>;
  private line!: Line2;
  private stars: Array<{ points: THREE.Points; speed: number }> = [];
  private aligning = true;
  private zoom = 1;
  private cameraX = 0;
  private cameraDistance = 6;
  private dragging: THREE.Object3D | null = null;
  private lastPointer = { x: 0, y: 0 };
  private raycaster = new THREE.Raycaster();
  private resizeObserver?: ResizeObserver;
  private cleanups: Array<() => void> = [];
  private previousTime = performance.now();

  constructor(private zone: NgZone) {}

  ngAfterViewInit() {
    this.zone.runOutsideAngular(() => this.init());
  }

  /** Corpo que está sendo comparado com a Terra (Marte ou Lua) */
  private get other(): THREE.Mesh {
    return this.body === 'mars' ? this.mars : this.moon;
  }

  setView(view: View) {
    this.view = view;
    this.zoom = 1;
    this.aligning = true;
  }

  setBody(body: Body) {
    if (this.body === body) return;
    this.body = body;
    this.applyBody();
    this.zoom = 1;
    this.aligning = true;
  }

  align() {
    this.aligning = true;
  }

  private applyBody() {
    this.mars.visible = this.body === 'mars';
    this.moon.visible = this.body === 'moon';
    for (const b of BODIES) {
      this.earthMarkers[b].visible = b === this.body;
      this.otherMarkers[b].visible = b === this.body;
    }
  }

  private cameraLimits() {
    const aspect = this.camera.aspect;
    if (this.view === 'earth') {
      return { x: this.earth.position.x, base: Math.max(3.4, 3.2 / aspect), min: 1 * MIN_DISTANCE_FACTOR };
    }
    if (this.view === 'other') {
      const scale = CONFIG[this.body].scale;
      const f = scale / MARS_SCALE;
      return {
        x: this.other.position.x,
        base: Math.max(1.8 * f, (1.7 * f) / aspect),
        min: scale * MIN_DISTANCE_FACTOR,
      };
    }
    return { x: 0, base: Math.max(5.6, 7 / aspect), min: 3 };
  }

  private minZoom() {
    const { base, min } = this.cameraLimits();
    return min / base;
  }

  private desiredCamera() {
    const { x, base, min } = this.cameraLimits();
    return { x, distance: Math.max(base * this.zoom, min) };
  }

  private loadTexture(url: string, srgb: boolean, onLoad: (texture: THREE.Texture) => void) {
    new THREE.TextureLoader().load(
      url,
      (texture) => {
        if (srgb) texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
        onLoad(texture);
      },
      undefined,
      () => console.warn('Texture not found:', url)
    );
  }

  private createStars(count: number, radius: number, size: number, speed: number) {
    const positions: number[] = [];
    for (let i = 0; i < count; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(radius);
      positions.push(v.x, v.y, v.z);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const points = new THREE.Points(
      geometry,
      new THREE.PointsMaterial({ color: 0xffffff, size, sizeAttenuation: true })
    );
    this.scene.add(points);
    this.stars.push({ points, speed });
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
      roughness: 1,
      metalness: 0,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(MOON_SCALE, 96, 64), material);

    this.loadTexture('/textures/moon.jpg', true, (texture) => {
      material.map = texture;
      material.color.set(0xffffff);
      material.needsUpdate = true;
    });

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

  private createMarker(planet: THREE.Mesh, lat: number, lon: number, planetRadius: number, radiusKm: number): THREE.Group {
    const radius = Math.max(radiusKm / R_EARTH, 0.04);
    const group = new THREE.Group();
    group.add(
      new THREE.Mesh(
        new THREE.CircleGeometry(radius, 64),
        new THREE.MeshBasicMaterial({
          color: 0xff2d2d,
          transparent: true,
          opacity: 0.4,
          depthWrite: false,
          side: THREE.DoubleSide,
          toneMapped: false,
        })
      )
    );
    group.add(
      new THREE.Mesh(
        new THREE.RingGeometry(radius * 0.93, radius, 64),
        new THREE.MeshBasicMaterial({ color: 0xff2d2d, side: THREE.DoubleSide, toneMapped: false })
      )
    );
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
    const material = new LineMaterial({ color: 0xff2d2d, linewidth: 2.5 });
    material.dashed = true;
    material.dashSize = 0.06;
    material.gapSize = 0.04;
    this.line = new Line2(geometry, material);
    this.line.computeLineDistances();
    this.line.frustumCulled = false;
    this.scene.add(this.line);
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
    point(0, p0);
    for (let i = 0; i < SEGMENTS; i++) {
      point((i + 1) / SEGMENTS, p1);
      P.set([p0.x, p0.y, p0.z, p1.x, p1.y, p1.z], i * 6);
      D[i * 2] = accumulated;
      accumulated += p0.distanceTo(p1);
      D[i * 2 + 1] = accumulated;
      p0.copy(p1);
    }
    positions.needsUpdate = true;
    distances.needsUpdate = true;
  }

  private init() {
    const canvas = this.sceneEl.nativeElement;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;
    this.scene.background = new THREE.Color(0x000000);

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.22));
    const sun = new THREE.DirectionalLight(0xffffff, 3);
    sun.position.set(4, 3, 6);
    this.scene.add(sun);

    this.createStars(1200, 60, 0.12, 0.004);
    this.createStars(800, 90, 0.18, 0.009);

    this.earth = this.createEarth();
    this.earth.position.set(1.7, 0, 0);
    this.mars = this.createMars();
    this.mars.position.set(-2.1, 0, 0);
    this.moon = this.createMoon();
    this.moon.position.set(-2.1, 0, 0);
    this.scene.add(this.earth, this.mars, this.moon);

    const front = new THREE.Vector3(0, 0, 1);
    const planets: Record<Body, THREE.Mesh> = { mars: this.mars, moon: this.moon };
    for (const b of BODIES) {
      const { analog, target, scale } = CONFIG[b];
      this.earthMarkers[b] = this.createMarker(this.earth, analog.lat, analog.lon, 1, analog.radiusKm);
      this.otherMarkers[b] = this.createMarker(planets[b], target.lat, target.lon, scale, target.radiusKm);
      this.earthFocus[b] = new THREE.Quaternion().setFromUnitVectors(latLon(analog.lat, analog.lon).normalize(), front);
      this.otherFocus[b] = new THREE.Quaternion().setFromUnitVectors(latLon(target.lat, target.lon).normalize(), front);
    }
    this.applyBody();

    this.createLine();

    const resize = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight || 1;
      this.renderer.setSize(w, h, false);
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
      if (!hit) return;
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

    this.renderer.setAnimationLoop(() => {
      const now = performance.now();
      const dt = Math.min((now - this.previousTime) / 1000, 0.1);
      this.previousTime = now;

      (this.line.material as LineMaterial).dashOffset -= DASH_SPEED * dt;

      for (const { points, speed } of this.stars) {
        points.rotation.y += speed * dt;
        points.rotation.x += speed * 0.4 * dt;
      }

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
      this.positionLabel(this.marsLabelEl.nativeElement, this.other, 'other');
      this.positionLabel(this.earthLabelEl.nativeElement, this.earth, 'earth');
      this.renderer.render(this.scene, this.camera);
    });
  }

  private positionLabel(el: HTMLElement, planet: THREE.Mesh, owner: View) {
    const v = planet.position.clone().project(this.camera);
    const canvas = this.sceneEl.nativeElement;
    el.style.left = ((v.x + 1) / 2) * canvas.clientWidth + 'px';
    el.style.opacity = this.view === 'both' || this.view === owner ? '1' : '0';
  }

  ngOnDestroy() {
    this.renderer?.setAnimationLoop(null);
    this.resizeObserver?.disconnect();
    this.cleanups.forEach((fn) => fn());
    this.scene.traverse((o: any) => {
      o.geometry?.dispose?.();
      if (o.material) {
        o.material.map?.dispose?.();
        o.material.dispose?.();
      }
    });
    this.renderer?.dispose();
  }
}