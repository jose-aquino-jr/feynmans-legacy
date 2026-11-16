import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  NgZone,
  OnDestroy,
  OnInit,
  Output,
  ViewChild,
  inject,
} from '@angular/core';
import * as THREE from 'three';

import {
  Mundo,
  ParametrosTerreno,
  Relevo,
  TAMANHO,
  Variaveis,
  aleatorio,
  parametrosDe,
} from './terreno';

/** Uma ponta da linha do mapa: o alvo (Lua/Marte) ou o análogo (Terra). */
export interface Cenario {
  mundo: Mundo;
  titulo: string;
  papel: 'alvo' | 'análogo';
  lat: number;
  lon: number;
  fonte: string;
  variaveis: Variaveis;
  nomes: Record<string, { nome: string; unidade: string }>;
}

interface Linha {
  nome: string;
  valor: string;
  efeito: string;
}

const NOME_MUNDO: Record<Mundo, string> = { terra: 'Earth', lua: 'Moon', marte: 'Mars' };
const ALTURA_OLHOS = 1.7;
const VEL_PULO = 3.2; // m/s: ~0,5 m na Terra, ~3,2 m na Lua
const fmt = (x: number, d = 1) => x.toLocaleString('en-US', { maximumFractionDigits: d });

/** Variáveis da API que moldam a cena e o que cada uma faz. */
const EFEITOS: Array<[string, (p: ParametrosTerreno, v: number) => string]> = [
  ['relevo__amplitude_relevo_m', (p) => `hills up to ~${fmt(p.relevo, 0)} m`],
  ['relevo__declividade_media_graus', (p) => `${fmt(p.rugosidade)} m roughness`],
  ['operacoes__fracao_terreno_plano_lt5graus', (p) => `${fmt(p.plano * 100, 0)}% flattened`],
  [
    'relevo__indice_posicao_topografica_m',
    (p) =>
      p.posicao < 0
        ? 'you stand in a basin'
        : p.posicao > 0
          ? 'you stand on a rise'
          : 'neutral ground',
  ],
  ['geologia_superficie__litologia_impacto', (p) => `${p.crateras} craters`],
  [
    'subsuperficie__potencial_tubos_lava',
    (p) => (p.tuboLava ? 'lava-tube pit to the east' : 'no lava tubes'),
  ],
  [
    'geologia_superficie__litologia_anortosito',
    (_p, v) => (v > 0.5 ? 'bright ground (anorthosite)' : 'no anorthosite'),
  ],
  [
    'geologia_superficie__litologia_basalto',
    (_p, v) => (v > 0.5 ? 'dark ground (basalt)' : 'no basalt'),
  ],
  ['geologia_superficie__albedo', (p) => `ground brightness ${fmt(p.brilho * 100, 0)}%`],
  [
    'biologia__ndvi',
    (p) => (p.vegetacao > 0 ? `vegetation ${fmt(p.vegetacao * 100, 0)}%` : 'no vegetation'),
  ],
  [
    'agua_gelo__indice_permafrost',
    (p) => (p.gelo > 0.05 ? `ice ${fmt(p.gelo * 100, 0)}%` : 'no ice'),
  ],
  ['temperatura__ar_2m_c', (p) => (p.gelo > 0.05 ? 'cold: frost and snow' : 'no frost')],
  [
    'poeira_vento_processos__pressao_estimada_altitude_kpa',
    (p) =>
      p.atmosfera < 0.03 ? 'vacuum: black sky' : `sky and haze (${fmt(p.atmosfera * 100, 0)}%)`,
  ],
  [
    'poeira_vento_processos__poeira_superficie_ugm3',
    (p) => `airborne dust ${fmt(p.poeira * 100, 0)}%`,
  ],
  ['poeira_vento_processos__vento_superficie_ms', (p) => `particles at ${fmt(p.vento)} m/s`],
  [
    'iluminacao_radiacao__elevacao_solar_max_graus',
    (p) => `sun ${fmt(p.elevacaoSol)}° above the horizon`,
  ],
];

@Component({
  selector: 'app-primeira-pessoa',
  host: { class: 'fixed inset-0 z-50 block bg-black font-sans text-cream' },
  template: `
    <canvas
      #tela
      class="absolute inset-0 block h-full w-full touch-none"
      [class.cursor-crosshair]="!travado"
    ></canvas>

    <div
      class="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-start justify-between gap-3 p-4"
    >
      <div class="glass pointer-events-auto max-w-[min(440px,100%)] rounded-2xl px-4 py-3">
        <p class="text-[10px] tracking-[.18em] opacity-70">
          FIRST PERSON · {{ cenario.papel === 'alvo' ? 'TARGET' : 'ANALOG' }}
        </p>
        <h2 class="mt-0.5 text-[15px] font-medium leading-snug">{{ cenario.titulo }}</h2>
        <p class="mt-1 text-[10px] opacity-70">
          {{ cenario.fonte }} · {{ cenario.lat.toFixed(2) }}°, {{ cenario.lon.toFixed(2) }}°
        </p>
        <div class="mt-2 flex flex-wrap gap-1.5">
          @for (c of cenarios; track c.mundo + c.titulo; let i = $index) {
            <button
              type="button"
              (click)="trocar(i)"
              class="cursor-pointer rounded-lg border border-white/15 px-3 py-1 text-[11px] tracking-[.12em]"
              [class]="i === atual ? 'glass-active' : 'opacity-75 hover:opacity-100'"
            >
              {{ nomeMundo[c.mundo].toUpperCase() }}
            </button>
          }
        </div>
      </div>
      <button
        type="button"
        (click)="sair()"
        class="glass pointer-events-auto cursor-pointer rounded-xl px-4 py-2 text-[11px] tracking-[.15em]"
      >
        EXIT ✕
      </button>
    </div>

    @if (mostrarVariaveis) {
      <aside
        class="glass panel-scroll absolute bottom-4 right-4 max-h-[52vh] w-[min(340px,calc(100vw-32px))] overflow-y-auto rounded-2xl px-4 py-3 max-md:bottom-24"
      >
        <div class="flex items-center justify-between">
          <p class="text-[10px] tracking-[.18em] opacity-70">API VARIABLES → TERRAIN</p>
          <button
            type="button"
            class="cursor-pointer px-1 text-[13px] opacity-70 hover:opacity-100"
            (click)="mostrarVariaveis = false"
            aria-label="Collapse"
          >
            −
          </button>
        </div>
        <p class="mt-1 text-[10px] opacity-70">
          Gravity {{ gravidade }} m/s² · jump of ~{{ alturaPulo }} m
        </p>
        <dl class="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1.5 text-[11px]">
          @for (l of linhas; track l.nome) {
            <dt class="leading-tight">
              {{ l.nome }}<br /><span class="text-[10px] text-ember">{{ l.efeito }}</span>
            </dt>
            <dd class="text-right tabular-nums opacity-85">{{ l.valor }}</dd>
          }
        </dl>
        <p class="mt-3 text-[9px] leading-snug opacity-55">
          Procedural terrain built from the statistics above; it is not the site's real elevation
          model.
        </p>
      </aside>
    } @else {
      <button
        type="button"
        (click)="mostrarVariaveis = true"
        class="glass absolute bottom-4 right-4 cursor-pointer rounded-xl px-3 py-2 text-[10px] tracking-[.15em] max-md:bottom-24"
      >
        VARIABLES
      </button>
    }

    @if (!travado) {
      <p
        class="pointer-events-none absolute bottom-4 left-4 max-w-[60vw] text-[10px] leading-relaxed opacity-75 max-md:hidden"
      >
        Click the scene to look around · WASD/arrows to walk · Shift to run · Space to jump · Esc
        releases the mouse
      </p>
    } @else {
      <div
        class="pointer-events-none absolute left-1/2 top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cream/80"
      ></div>
    }

    <div class="absolute bottom-4 left-4 flex gap-2 md:hidden">
      <button
        type="button"
        class="glass size-14 rounded-2xl text-lg"
        aria-label="Walk forward"
        (pointerdown)="toque.frente = true"
        (pointerup)="toque.frente = false"
        (pointerleave)="toque.frente = false"
      >
        ▲
      </button>
      <button
        type="button"
        class="glass size-14 rounded-2xl text-[10px] tracking-[.1em]"
        (click)="pular()"
      >
        JUMP
      </button>
    </div>
  `,
})
export class PrimeiraPessoa implements OnInit, AfterViewInit, OnDestroy {
  @Input({ required: true }) cenarios: Cenario[] = [];
  @Input() inicial = 0;
  @Output() fechar = new EventEmitter<void>();
  @ViewChild('tela') telaRef!: ElementRef<HTMLCanvasElement>;

  readonly nomeMundo = NOME_MUNDO;
  atual = 0;
  travado = false;
  mostrarVariaveis = typeof window === 'undefined' || window.innerWidth >= 768;
  linhas: Linha[] = [];
  gravidade = '';
  alturaPulo = '';
  toque = { frente: false };

  private readonly zone = inject(NgZone);
  private readonly cdr = inject(ChangeDetectorRef);
  private renderer: THREE.WebGLRenderer | null = null;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(70, 1, 0.1, 9000);
  private sol = new THREE.DirectionalLight(0xffffff, 3);
  private relevo!: Relevo;
  private poeira: { pontos: THREE.Points; vel: THREE.Vector3 } | null = null;
  private yaw = 0;
  private pitch = 0;
  private vy = 0;
  private noChao = true;
  private teclas = new Set<string>();
  private ultimo = performance.now();
  private limpeza: Array<() => void> = [];

  get cenario(): Cenario {
    return this.cenarios[this.atual];
  }

  ngOnInit() {
    this.atual = Math.max(0, Math.min(this.inicial, this.cenarios.length - 1));
  }

  ngAfterViewInit() {
    this.zone.runOutsideAngular(() => this.iniciar());
  }

  trocar(i: number) {
    if (i < 0 || i >= this.cenarios.length || i === this.atual) return;
    this.atual = i;
    this.teclas.clear();
    this.toque.frente = false;
    this.zone.runOutsideAngular(() => this.montar());
  }

  sair() {
    document.exitPointerLock?.();
    this.fechar.emit();
  }

  pular() {
    if (!this.noChao) return;
    this.vy = VEL_PULO;
    this.noChao = false;
  }

  // ------------------------------------------------------------------ cena
  private iniciar() {
    const tela = this.telaRef.nativeElement;
    const renderer = new THREE.WebGLRenderer({ canvas: tela, antialias: true });
    this.renderer = renderer;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.camera.rotation.order = 'YXZ';

    const redimensionar = () => {
      const w = tela.clientWidth,
        h = tela.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    };
    const obs = new ResizeObserver(redimensionar);
    obs.observe(tela);
    redimensionar();
    this.limpeza.push(() => obs.disconnect());

    this.controles(tela);
    this.montar();
    renderer.setAnimationLoop((agora) => this.quadro(agora));
  }

  private montar() {
    this.descartarCena();
    const c = this.cenario;
    const p = parametrosDe(c.mundo, c.variaveis, c.lat, c.lon);
    this.relevo = new Relevo(p);
    this.atualizarHud(c, p);

    const cena = new THREE.Scene();
    this.scene = cena;
    const paleta = paletaDe(p);
    cena.background = paleta.horizonte.clone();
    if (p.mundo !== 'lua')
      cena.fog = new THREE.FogExp2(
        paleta.horizonte,
        0.00018 + p.poeira * 0.0007 + p.atmosfera * 0.00012,
      );

    // Sol na altura máxima informada pela API
    const elev = THREE.MathUtils.degToRad(p.elevacaoSol);
    const az = THREE.MathUtils.degToRad(140);
    const dirSol = new THREE.Vector3(
      Math.cos(elev) * Math.cos(az),
      Math.sin(elev),
      Math.cos(elev) * Math.sin(az),
    );
    this.sol = new THREE.DirectionalLight(
      0xffffff,
      p.mundo === 'lua' ? 3.4 : p.mundo === 'marte' ? 2.2 : 2.8,
    );
    this.sol.color.set(p.mundo === 'marte' ? 0xffe2c4 : 0xfff6e8);
    this.sol.userData['dir'] = dirSol;
    this.sol.castShadow = true;
    this.sol.shadow.mapSize.set(2048, 2048);
    Object.assign(this.sol.shadow.camera, {
      left: -220,
      right: 220,
      top: 220,
      bottom: -220,
      near: 1,
      far: 2000,
    });
    this.sol.shadow.bias = -0.0004;
    cena.add(this.sol, this.sol.target);
    // Sem ar a sombra lunar seria preta; um preenchimento fraco (luz refletida) mantém o relevo legível
    const ceuLuz = p.mundo === 'lua' ? new THREE.Color(0x9aa6b8) : paleta.ceu;
    cena.add(
      new THREE.HemisphereLight(
        ceuLuz,
        paleta.chao,
        p.mundo === 'lua' ? 0.55 : 0.35 + p.atmosfera * 0.35,
      ),
    );

    cena.add(ceu(paleta, dirSol, p));
    if (p.atmosfera < 0.05) cena.add(estrelas(p.semente));
    cena.add(this.terreno(p));
    cena.add(this.rochas(p));
    if (p.vegetacao > 0.02) cena.add(this.plantas(p));
    this.poeira = p.atmosfera > 0.02 && (p.vento > 0.5 || p.poeira > 0.05) ? particulas(p) : null;
    if (this.poeira) cena.add(this.poeira.pontos);

    // Começa no centro, olhando para o sol (sombras longas para trás)
    this.camera.position.set(0, this.relevo.altura(0, 0) + ALTURA_OLHOS, 0);
    this.yaw = Math.atan2(-dirSol.x, -dirSol.z) + Math.PI;
    this.pitch = -0.05;
    this.vy = 0;
    this.noChao = true;
  }

  private atualizarHud(c: Cenario, p: ParametrosTerreno) {
    this.zone.run(() => {
      this.gravidade = fmt(p.gravidade, 2);
      this.alturaPulo = fmt((VEL_PULO * VEL_PULO) / (2 * p.gravidade), 1);
      this.linhas = EFEITOS.filter(([chave]) => typeof c.variaveis[chave] === 'number').map(
        ([chave, efeito]) => {
          const meta = c.nomes[chave];
          const v = c.variaveis[chave] as number;
          return {
            nome: meta?.nome ?? chave.split('__').pop()!.replaceAll('_', ' '),
            valor: `${fmt(v, Math.abs(v) < 10 ? 2 : 0)}${meta?.unidade && meta.unidade !== '0/1' ? ' ' + meta.unidade : ''}`,
            efeito: efeito(p, v),
          };
        },
      );
      this.cdr.markForCheck();
    });
  }

  private terreno(p: ParametrosTerreno): THREE.Mesh {
    const seg = 300;
    const geo = new THREE.PlaneGeometry(TAMANHO, TAMANHO, seg, seg);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes['position'] as THREE.BufferAttribute;
    const cores = new Float32Array(pos.count * 3);
    const base = new THREE.Color(...p.solo).multiplyScalar(0.55 + p.brilho * 0.9);
    const neve = new THREE.Color(0.93, 0.95, 0.98);
    const verde = new THREE.Color(0.22, 0.36, 0.14);
    const cor = new THREE.Color();
    const rnd = aleatorio(p.semente + 3);
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i),
        z = pos.getZ(i);
      const h = this.relevo.altura(x, z);
      pos.setY(i, h);
      cor.copy(base).multiplyScalar(0.9 + rnd() * 0.16);
      cor.lerp(verde, this.relevo.verde(x, z) * 0.85);
      cor.lerp(neve, this.relevo.gelo(x, z, h));
      cores.set([cor.r, cor.g, cor.b], i * 3);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(cores, 3));
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 1,
      metalness: 0,
      map: grao(),
    });
    const malha = new THREE.Mesh(geo, mat);
    malha.receiveShadow = true;
    malha.castShadow = true;
    return malha;
  }

  private rochas(p: ParametrosTerreno): THREE.InstancedMesh {
    const n = Math.min(1600, Math.round(300 + p.rugosidade * 25 + p.crateras * 18));
    const malha = new THREE.InstancedMesh(
      new THREE.DodecahedronGeometry(1, 0),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(...p.solo).multiplyScalar(0.45 + p.brilho * 0.6),
        roughness: 1,
        flatShading: true,
      }),
      n,
    );
    const rnd = aleatorio(p.semente + 11);
    const m = new THREE.Matrix4(),
      q = new THREE.Quaternion(),
      e = new THREE.Euler(),
      s = new THREE.Vector3(),
      v = new THREE.Vector3();
    for (let i = 0; i < n; i++) {
      const ang = rnd() * Math.PI * 2,
        dist = 3 + Math.pow(rnd(), 0.7) * 650;
      const x = Math.cos(ang) * dist,
        z = Math.sin(ang) * dist;
      const k = 0.15 + Math.pow(rnd(), 4) * 2.2;
      s.set(k * (0.8 + rnd() * 0.6), k * (0.4 + rnd() * 0.5), k * (0.8 + rnd() * 0.6));
      v.set(x, this.relevo.altura(x, z) + s.y * 0.35, z);
      q.setFromEuler(e.set(rnd() * 3, rnd() * 3, rnd() * 3));
      malha.setMatrixAt(i, m.compose(v, q, s));
    }
    malha.castShadow = true;
    malha.receiveShadow = true;
    return malha;
  }

  private plantas(p: ParametrosTerreno): THREE.InstancedMesh {
    const max = Math.round(p.vegetacao * 2600);
    const malha = new THREE.InstancedMesh(
      new THREE.ConeGeometry(0.7, 1.8, 6).translate(0, 0.9, 0),
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, flatShading: true }),
      max,
    );
    const rnd = aleatorio(p.semente + 29);
    const m = new THREE.Matrix4(),
      q = new THREE.Quaternion(),
      s = new THREE.Vector3(),
      v = new THREE.Vector3();
    const cor = new THREE.Color();
    let n = 0;
    for (let tent = 0; tent < max * 4 && n < max; tent++) {
      const ang = rnd() * Math.PI * 2,
        dist = 4 + Math.pow(rnd(), 0.6) * 700;
      const x = Math.cos(ang) * dist,
        z = Math.sin(ang) * dist;
      if (this.relevo.verde(x, z) < 0.35) continue;
      const k = 0.4 + rnd() * 1.6;
      s.set(k, k * (0.6 + rnd() * 1.4), k);
      v.set(x, this.relevo.altura(x, z) - 0.1, z);
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * 6.28);
      malha.setMatrixAt(n, m.compose(v, q, s));
      malha.setColorAt(n, cor.setHSL(0.24 + rnd() * 0.08, 0.45, 0.16 + rnd() * 0.12));
      n++;
    }
    malha.count = n;
    malha.castShadow = true;
    return malha;
  }

  // ------------------------------------------------------------------ controles
  private controles(tela: HTMLCanvasElement) {
    const ouvir = <K extends keyof DocumentEventMap>(
      alvo: Document | HTMLElement,
      tipo: K,
      fn: (e: DocumentEventMap[K]) => void,
    ) => {
      alvo.addEventListener(tipo, fn as EventListener);
      this.limpeza.push(() => alvo.removeEventListener(tipo, fn as EventListener));
    };
    ouvir(tela, 'click', () => {
      if (matchMedia('(pointer: fine)').matches) tela.requestPointerLock?.();
    });
    ouvir(document, 'pointerlockchange', () => {
      const travado = document.pointerLockElement === tela;
      if (travado !== this.travado)
        this.zone.run(() => {
          this.travado = travado;
          this.cdr.markForCheck();
        });
    });
    ouvir(document, 'mousemove', (e) => {
      if (this.travado) this.olhar(e.movementX, e.movementY);
    });
    let toqueAnterior: { x: number; y: number } | null = null;
    ouvir(tela, 'pointerdown', (e) => {
      if (e.pointerType !== 'mouse') toqueAnterior = { x: e.clientX, y: e.clientY };
    });
    ouvir(tela, 'pointermove', (e) => {
      if (!toqueAnterior) return;
      this.olhar((e.clientX - toqueAnterior.x) * 1.6, (e.clientY - toqueAnterior.y) * 1.6);
      toqueAnterior = { x: e.clientX, y: e.clientY };
    });
    ouvir(tela, 'pointerup', () => (toqueAnterior = null));
    ouvir(tela, 'pointercancel', () => (toqueAnterior = null));
    ouvir(document, 'keydown', (e) => {
      if (e.code === 'Escape' && !this.travado) {
        this.zone.run(() => this.sair());
        return;
      }
      if (
        [
          'KeyW',
          'KeyA',
          'KeyS',
          'KeyD',
          'ArrowUp',
          'ArrowDown',
          'ArrowLeft',
          'ArrowRight',
          'Space',
          'ShiftLeft',
          'ShiftRight',
        ].includes(e.code)
      ) {
        e.preventDefault();
        this.teclas.add(e.code);
        if (e.code === 'Space') this.pular();
      }
    });
    ouvir(document, 'keyup', (e) => this.teclas.delete(e.code));
    const onBlur = () => {
      this.teclas.clear();
      this.toque.frente = false;
    };
    window.addEventListener('blur', onBlur);
    this.limpeza.push(() => window.removeEventListener('blur', onBlur));
  }

  private olhar(dx: number, dy: number) {
    this.yaw -= dx * 0.0022;
    this.pitch = THREE.MathUtils.clamp(this.pitch - dy * 0.0022, -1.45, 1.45);
  }

  private quadro(agora: number) {
    const renderer = this.renderer;
    if (!renderer) return;
    const dt = Math.min((agora - this.ultimo) / 1000, 0.1);
    this.ultimo = agora;
    const t = this.teclas;
    const frente =
      (t.has('KeyW') || t.has('ArrowUp') || this.toque.frente ? 1 : 0) -
      (t.has('KeyS') || t.has('ArrowDown') ? 1 : 0);
    const lado =
      (t.has('KeyD') || t.has('ArrowRight') ? 1 : 0) -
      (t.has('KeyA') || t.has('ArrowLeft') ? 1 : 0);
    const vel = t.has('ShiftLeft') || t.has('ShiftRight') ? 11 : 4.5;

    const cam = this.camera;
    cam.rotation.set(this.pitch, this.yaw, 0);
    if (frente || lado) {
      const sin = Math.sin(this.yaw),
        cos = Math.cos(this.yaw);
      const norma = Math.hypot(frente, lado);
      cam.position.x += ((-sin * frente + cos * lado) / norma) * vel * dt;
      cam.position.z += ((-cos * frente - sin * lado) / norma) * vel * dt;
    }
    const lim = TAMANHO * 0.36;
    cam.position.x = THREE.MathUtils.clamp(cam.position.x, -lim, lim);
    cam.position.z = THREE.MathUtils.clamp(cam.position.z, -lim, lim);

    // Gravidade do mundo
    const chao = this.relevo.altura(cam.position.x, cam.position.z) + ALTURA_OLHOS;
    this.vy -= this.relevo.p.gravidade * dt;
    cam.position.y += this.vy * dt;
    if (cam.position.y <= chao) {
      cam.position.y = chao;
      this.vy = 0;
      this.noChao = true;
    }

    // Sombra acompanha o jogador
    const dir = this.sol.userData['dir'] as THREE.Vector3;
    this.sol.target.position.copy(cam.position);
    this.sol.position.copy(cam.position).addScaledVector(dir, 800);

    if (this.poeira) {
      const attr = this.poeira.pontos.geometry.attributes['position'] as THREE.BufferAttribute;
      const a = attr.array as Float32Array;
      const v = this.poeira.vel;
      for (let i = 0; i < a.length; i += 3) {
        a[i] += v.x * dt;
        a[i + 1] += v.y * dt * Math.sin(i + agora / 900);
        a[i + 2] += v.z * dt;
        if (a[i] > 60) a[i] -= 120;
        else if (a[i] < -60) a[i] += 120;
        if (a[i + 2] > 60) a[i + 2] -= 120;
        else if (a[i + 2] < -60) a[i + 2] += 120;
      }
      attr.needsUpdate = true;
      this.poeira.pontos.position.set(cam.position.x, cam.position.y - 1, cam.position.z);
    }
    renderer.render(this.scene, cam);
  }

  private descartarCena() {
    this.scene.traverse((o: any) => {
      o.geometry?.dispose?.();
      const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      mats.forEach((m: any) => {
        m.map?.dispose?.();
        m.dispose();
      });
    });
    this.scene.clear();
  }

  ngOnDestroy() {
    this.renderer?.setAnimationLoop(null);
    this.teclas.clear();
    this.toque.frente = false;
    this.limpeza.forEach((fn) => fn());
    if (document.pointerLockElement) document.exitPointerLock();
    this.descartarCena();
    this.renderer?.dispose();
    this.renderer?.forceContextLoss();
    this.renderer = null;
  }
}

// ------------------------------------------------------------------ ambiente
interface Paleta {
  ceu: THREE.Color;
  horizonte: THREE.Color;
  chao: THREE.Color;
}

function paletaDe(p: ParametrosTerreno): Paleta {
  const solo = new THREE.Color(...p.solo);
  if (p.mundo === 'lua')
    return { ceu: new THREE.Color(0x000000), horizonte: new THREE.Color(0x010102), chao: solo };
  if (p.mundo === 'marte') {
    const horizonte = new THREE.Color(0xd8a878).lerp(new THREE.Color(0xc58a5c), p.poeira);
    return {
      ceu: new THREE.Color(0x9b7458).lerp(new THREE.Color(0xc9a07a), p.poeira),
      horizonte,
      chao: solo,
    };
  }
  // Terra: menos ar (altitude) escurece o azul; poeira deixa o horizonte bege
  const ceu = new THREE.Color(0x1d3f7a).lerp(new THREE.Color(0x3f7fcf), p.atmosfera);
  const horizonte = new THREE.Color(0xa9c8ea).lerp(new THREE.Color(0xd9c6a2), p.poeira);
  return { ceu, horizonte, chao: solo };
}

function ceu(paleta: Paleta, dirSol: THREE.Vector3, p: ParametrosTerreno): THREE.Mesh {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      topo: { value: paleta.ceu },
      horizonte: { value: paleta.horizonte },
      sol: { value: dirSol },
      brilho: { value: p.mundo === 'lua' ? 0.0 : 0.6 },
      disco: {
        value:
          p.mundo === 'marte' ? new THREE.Color(0.85, 0.9, 1.0) : new THREE.Color(1, 0.97, 0.9),
      },
    },
    vertexShader: `varying vec3 vDir; void main() { vDir = normalize(position);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform vec3 topo; uniform vec3 horizonte; uniform vec3 sol; uniform float brilho; uniform vec3 disco;
      varying vec3 vDir;
      void main() {
        float h = max(vDir.y, 0.0);
        vec3 c = mix(horizonte, topo, pow(h, 0.45));
        float s = max(dot(normalize(vDir), normalize(sol)), 0.0);
        c += disco * (pow(s, 900.0) * 3.0 + pow(s, 12.0) * brilho * 0.35);
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  const malha = new THREE.Mesh(new THREE.SphereGeometry(8000, 32, 16), mat);
  malha.renderOrder = -1;
  malha.onBeforeRender = (_r, _s, camera) => malha.position.copy(camera.position);
  return malha;
}

function estrelas(semente: number): THREE.Points {
  const rnd = aleatorio(semente + 7);
  const pos: number[] = [];
  for (let i = 0; i < 2500; i++) {
    const v = new THREE.Vector3(rnd() * 2 - 1, rnd() * 1.1 - 0.1, rnd() * 2 - 1)
      .normalize()
      .multiplyScalar(7000);
    pos.push(v.x, v.y, v.z);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  const pontos = new THREE.Points(
    geo,
    new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, fog: false }),
  );
  pontos.onBeforeRender = (_r, _s, camera) => pontos.position.copy(camera.position);
  return pontos;
}

function particulas(p: ParametrosTerreno): { pontos: THREE.Points; vel: THREE.Vector3 } {
  const rnd = aleatorio(p.semente + 5);
  const n = Math.round(400 + p.poeira * 2500);
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) pos.set([rnd() * 120 - 60, rnd() * 14 - 2, rnd() * 120 - 60], i * 3);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const cor = p.mundo === 'marte' ? 0xd9a275 : 0xe8dcc4;
  const pontos = new THREE.Points(
    geo,
    new THREE.PointsMaterial({
      color: cor,
      size: 0.06,
      transparent: true,
      opacity: 0.25 + p.poeira * 0.5,
      depthWrite: false,
    }),
  );
  pontos.frustumCulled = false;
  return { pontos, vel: new THREE.Vector3(p.vento * 0.8, 0.3, p.vento * 0.35) };
}

/** Textura de grão fino para o chão não parecer liso de perto. */
function grao(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const ctx = c.getContext('2d')!;
  const img = ctx.createImageData(128, 128);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 205 + Math.random() * 50;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(TAMANHO / 3, TAMANHO / 3);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
