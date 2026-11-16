// Contrato de GET /api/v1/analogos/recomendacoes (espelha app/schemas/recommendations.py).

export type Corpo = 'lua' | 'marte';
export type Estrategia = 'recursiva' | 'auto' | 'sazonal';
export type Origem = 'observada' | 'prevista' | 'extrapolada' | 'cenario_sazonal';
export type StatusGrupo = 'ok' | 'parcial' | 'sem_dados' | 'sem_candidatos' | 'nicho_incompativel';

export interface BaseOpcao {
  base_id: string;
  corpo: Corpo;
  nome: string;
  latitude: number | null;
  longitude: number | null;
  raio_km: number | null;
  nichos: string[];
}

export interface Publicacao {
  corte: number;
  horizontes_diretos: Record<string, number[]>;
  estrategias: Estrategia[];
  estrategia_padrao_futuro: Estrategia;
  algoritmo: string;
  modelo_sha256: string;
  historico_sha256: string;
  trajetoria: string;
}

export interface OpcoesResponse {
  bases: BaseOpcao[];
  meses_observados: number[];
  anomes_max: number;
  k_max: number;
  cobertura_minima_padrao: number;
  publicacao: Publicacao;
}

export interface Criterio {
  variavel: string;
  nome: string;
  unidade: string;
  alvo: number;
  tolerancia: number;
  peso: number;
  tipo_alvo: string | null;
  fonte: string | null;
}

export interface Candidato {
  posicao: number;
  location_id: string;
  latitude: number;
  longitude: number;
  nota: number;
  cobertura: number;
  cluster: number | null;
  valores: Record<string, number | null>;
  notas_criterios: Record<string, number | null>;
  criterios_sem_dado: string[];
}

export interface GrupoBase {
  base_id: string;
  corpo: Corpo;
  nome: string;
  latitude: number | null;
  longitude: number | null;
  status: StatusGrupo;
  criterios: Criterio[];
  criterios_ausentes: string[];
  total_elegiveis: number;
  candidatos: Candidato[];
}

export interface RecomendacoesResponse {
  anomes: number;
  nicho: string;
  origem: Origem;
  estrategia: Estrategia;
  horizonte_meses: number;
  mes_base_cenario: number | null;
  anomes_cluster: number | null;
  rotulo: string | null;
  metodos: Record<string, string>;
  cobertura_minima: number;
  k: number;
  offset: number;
  publicacao: Publicacao;
  resultados: GrupoBase[];
}

export interface Calculando {
  status: 'calculando';
  anomes: number;
  estrategia: Estrategia;
  repetir_em_segundos: number;
  tarefa_id: string;
  meses_calculados: number;
  meses_necessarios: number;
  na_fila: boolean;
}

export interface ConsultaRecomendacoes {
  anomes: number;
  nicho: string;
  corpo: Corpo;
  base_id: string | null;
  k: number;
  cobertura_minima: number;
  estrategia: Estrategia;
}

/** Estado da busca exibido no painel; `consulta` identifica a que filtros ele pertence. */
export type EstadoBusca =
  | { tipo: 'ocioso' }
  | { tipo: 'carregando'; consulta: ConsultaRecomendacoes }
  | { tipo: 'calculando'; consulta: ConsultaRecomendacoes; progresso: Calculando }
  | { tipo: 'sucesso'; consulta: ConsultaRecomendacoes; resposta: RecomendacoesResponse }
  | { tipo: 'falha'; consulta: ConsultaRecomendacoes; codigo: string; mensagem: string };
