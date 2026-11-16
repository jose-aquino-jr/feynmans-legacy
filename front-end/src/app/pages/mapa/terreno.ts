// Converte as variáveis da API (valores observados do local na Terra ou valores-alvo
// da base na Lua/Marte) nos parâmetros de um terreno procedural em primeira pessoa.
// Não é um DEM real: é uma paisagem plausível com as mesmas estatísticas do relevo.

import { ImprovedNoise } from 'three/examples/jsm/math/ImprovedNoise.js';

export type Mundo = 'terra' | 'lua' | 'marte';

export type Variaveis = Record<string, number | null | undefined>;

export interface ParametrosTerreno {
  mundo: Mundo;
  gravidade: number;
  /** Variação de altura do relevo na cena (m). */
  relevo: number;
  /** Rugosidade de pequena escala (m). */
  rugosidade: number;
  /** 0–1: quanto do terreno é plano. */
  plano: number;
  /** Bacia (<0) ou elevação (>0) em relação ao entorno (m). */
  posicao: number;
  crateras: number;
  tuboLava: boolean;
  /** 0–1: cobertura de gelo/neve. */
  gelo: number;
  /** 0–1: vegetação. */
  vegetacao: number;
  /** Cor base do solo (RGB 0–1). */
  solo: [number, number, number];
  /** 0–1: brilho do solo (albedo). */
  brilho: number;
  /** 0–1: densidade da atmosfera (pressão). */
  atmosfera: number;
  /** 0–1: poeira suspensa. */
  poeira: number;
  vento: number;
  elevacaoSol: number;
  temperatura: number | null;
  semente: number;
}

export const GRAVIDADE: Record<Mundo, number> = { terra: 9.81, lua: 1.62, marte: 3.71 };
const PRESSAO_PADRAO: Record<Mundo, number> = { terra: 101.3, lua: 0, marte: 0.6 };
export const TAMANHO = 2400; // lado do terreno (m)

const num = (v: Variaveis, chave: string): number | null => {
  const x = v[chave];
  return typeof x === 'number' && Number.isFinite(x) ? x : null;
};
const clamp = (x: number, a: number, b: number) => Math.min(b, Math.max(a, x));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Lê as variáveis (com padrões por mundo quando faltam) e devolve os parâmetros da cena. */
export function parametrosDe(mundo: Mundo, v: Variaveis, lat: number, lon: number): ParametrosTerreno {
  const amplitude = num(v, 'relevo__amplitude_relevo_m') ?? (mundo === 'terra' ? 300 : 600);
  const declividade = num(v, 'relevo__declividade_media_graus') ?? 3;
  const plano = num(v, 'operacoes__fracao_terreno_plano_lt5graus') ?? 0.5;
  const tpi = num(v, 'relevo__indice_posicao_topografica_m') ?? 0;
  const impacto = num(v, 'geologia_superficie__litologia_impacto') ?? (mundo === 'lua' ? 1 : 0);
  const anortosito = num(v, 'geologia_superficie__litologia_anortosito') ?? 0;
  const basalto = num(v, 'geologia_superficie__litologia_basalto') ?? 0;
  const albedo = num(v, 'geologia_superficie__albedo');
  const ndvi = num(v, 'biologia__ndvi') ?? 0;
  const solo_exposto = num(v, 'biologia__cobertura_solo_exposto_arido_fracao');
  const permafrost = Math.max(num(v, 'agua_gelo__indice_permafrost') ?? 0, num(v, 'subsuperficie__solo_congelado_indice') ?? 0);
  const temperatura = num(v, 'temperatura__ar_2m_c');
  const pressao = num(v, 'poeira_vento_processos__pressao_estimada_altitude_kpa') ?? PRESSAO_PADRAO[mundo];
  const poeira = num(v, 'poeira_vento_processos__poeira_superficie_ugm3') ?? 0;
  const vento = num(v, 'poeira_vento_processos__vento_superficie_ms') ?? (mundo === 'lua' ? 0 : 3);
  const sol = num(v, 'iluminacao_radiacao__elevacao_solar_max_graus') ?? 45;
  const tubos = num(v, 'subsuperficie__potencial_tubos_lava') ?? 0;

  // Cor do solo pela litologia e pelo mundo
  let solo: [number, number, number] =
    mundo === 'marte' ? [0.62, 0.33, 0.19] : mundo === 'lua' ? [0.55, 0.55, 0.54] : [0.66, 0.56, 0.42];
  if (anortosito > 0.5) solo = mix(solo, [0.78, 0.78, 0.76], 0.6);
  if (basalto > 0.5) solo = mix(solo, mundo === 'marte' ? [0.36, 0.22, 0.16] : [0.3, 0.29, 0.28], 0.55);
  const frio = temperatura === null ? 0 : clamp((-temperatura - 2) / 25, 0, 1);

  return {
    mundo,
    gravidade: GRAVIDADE[mundo],
    // A amplitude vem de uma região de vários km; a cena mostra ~2,4 km
    relevo: clamp(amplitude, 10, 3000) * 0.14,
    rugosidade: clamp(declividade, 0, 30) * 0.9,
    plano: clamp(plano, 0, 1),
    posicao: clamp(tpi, -600, 600) * 0.35,
    crateras: Math.round(impacto * (mundo === 'terra' ? 6 : 34) + (mundo === 'terra' ? 0 : 6)),
    tuboLava: tubos >= 0.5,
    // Na Terra o frio do ar vira neve; na Lua/Marte só o gelo indicado pela API aparece
    gelo: mundo === 'terra' ? clamp(permafrost * 0.6 + frio * 0.5, 0, 1) : permafrost * (mundo === 'lua' ? 0.2 : 0.6),
    vegetacao: mundo === 'terra' ? clamp((ndvi - 0.08) / 0.6, 0, 1) * (1 - (solo_exposto ?? 0) * 0.5) : 0,
    solo,
    brilho: albedo === null ? 0.5 : clamp(0.2 + albedo * 2.2, 0.15, 1),
    atmosfera: clamp(Math.log10(1 + pressao) / Math.log10(102), 0, 1),
    poeira: clamp(poeira / 150, 0, 1),
    vento: clamp(vento, 0, 25),
    elevacaoSol: clamp(sol, 1.5, 88),
    temperatura,
    semente: Math.abs(Math.sin(lat * 12.9898 + lon * 78.233) * 43758.5453) % 1000,
  };
}

function mix(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

interface Cratera { x: number; z: number; r: number; prof: number }

/** Função de altura determinística (mesma para a malha e para os pés do jogador). */
export class Relevo {
  private readonly ruido = new ImprovedNoise();
  readonly crateras: Cratera[] = [];
  readonly tubo: { x: number; z: number; r: number } | null;

  constructor(readonly p: ParametrosTerreno) {
    const rnd = aleatorio(p.semente);
    for (let i = 0; i < p.crateras; i++) {
      const r = 8 + Math.pow(rnd(), 3) * 180;
      const ang = rnd() * Math.PI * 2;
      const dist = 40 + rnd() * TAMANHO * 0.42;
      this.crateras.push({ x: Math.cos(ang) * dist, z: Math.sin(ang) * dist, r, prof: r * (0.16 + rnd() * 0.08) });
    }
    this.tubo = p.tuboLava ? { x: 140 + rnd() * 80, z: -120 - rnd() * 80, r: 22 } : null;
  }

  private fbm(x: number, z: number, oitavas: number): number {
    let soma = 0, amp = 1, freq = 1, norm = 0;
    const s = this.p.semente;
    for (let i = 0; i < oitavas; i++) {
      soma += amp * this.ruido.noise(x * freq + s, z * freq - s, s * 0.37 + i * 7.1);
      norm += amp; amp *= 0.5; freq *= 2.03;
    }
    return soma / norm;
  }

  altura(x: number, z: number): number {
    const p = this.p;
    // Relevo amplo, achatado pela fração de terreno plano
    let base = this.fbm(x / 700, z / 700, 5) * 2;
    const limiar = p.plano * 0.6;
    base = Math.sign(base) * Math.max(Math.abs(base) - limiar, 0) / (1 - limiar * 0.9);
    let h = base * p.relevo;
    // Rugosidade local (declividade média)
    h += this.fbm(x / 45, z / 45, 3) * p.rugosidade * (1 - p.plano * 0.5);
    // Bacia ou elevação: o entorno sobe (ou desce) em relação ao centro
    const r = Math.hypot(x, z) / (TAMANHO / 2);
    h -= p.posicao * Math.min(r * r, 1);
    // Crateras: cuba com borda elevada
    for (const c of this.crateras) {
      const d = Math.hypot(x - c.x, z - c.z) / c.r;
      if (d < 1) h += -c.prof * (1 - d * d) + c.prof * 0.25 * d ** 6;
      else if (d < 2.2) h += c.prof * 0.25 * Math.exp(-((d - 1) ** 2) * 6);
    }
    // Poço de tubo de lava: claraboia de paredes íngremes
    if (this.tubo) {
      const d = Math.hypot(x - this.tubo.x, z - this.tubo.z) / this.tubo.r;
      if (d < 1.3) h -= 38 * (1 - smooth(0.85, 1.3, d));
    }
    // Queda nas bordas para o fim do terreno virar horizonte
    h -= smooth(0.72, 1, r) * 90;
    return h;
  }

  /** 0–1: neve/gelo em vales e encostas sombreadas. */
  gelo(x: number, z: number, h: number): number {
    if (this.p.gelo <= 0) return 0;
    const n = this.fbm(x / 90, z / 90, 3) * 0.5 + 0.5;
    return smooth(1 - this.p.gelo, 1.15 - this.p.gelo, n + (this.p.relevo ? -h / (this.p.relevo * 6) : 0));
  }

  /** 0–1: manchas de vegetação. */
  verde(x: number, z: number): number {
    if (this.p.vegetacao <= 0) return 0;
    const n = this.fbm(x / 120 + 50, z / 120 - 50, 3) * 0.5 + 0.5;
    return smooth(1 - this.p.vegetacao, 1.2 - this.p.vegetacao, n);
  }
}

export function smooth(a: number, b: number, x: number): number {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
}

export function aleatorio(semente: number): () => number {
  let s = Math.floor(semente * 1000) % 2147483647 || 1;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}
