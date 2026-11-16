import {
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  Output,
  SimpleChanges,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

import {
  Candidato,
  ConsultaRecomendacoes,
  Corpo,
  Criterio,
  Estrategia,
  EstadoBusca,
  GrupoBase,
  OpcoesResponse,
  RecomendacoesResponse,
} from '../../core/recomendacoes.models';
import {
  ROTULO_ORIGEM,
  RecomendacoesService,
  descreverMetodo,
  mesmaConsulta,
} from '../../core/recomendacoes.service';

export interface SelecaoCandidato {
  grupo: GrupoBase;
  candidato: Candidato;
  resposta: RecomendacoesResponse;
}

const NOMES_NICHO: Record<string, string> = {
  Todos: 'Todos os critérios',
  termico: 'Térmico',
  iluminacao_radiacao: 'Iluminação e radiação',
  agua_gelo: 'Água e gelo',
  agua_aridez: 'Água e aridez',
  terreno: 'Terreno',
  geologia: 'Geologia',
  superficie_poeira: 'Superfície e poeira',
  processos: 'Processos de vento e poeira',
  biologia_habitabilidade: 'Biologia e habitabilidade',
  subsuperficie: 'Subsuperfície',
  atmosfera: 'Atmosfera',
  operacoes: 'Operações',
};

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const COBERTURAS = [0.5, 0.6, 0.7, 0.8, 0.9, 1];

@Component({
  selector: 'app-painel-recomendacoes',
  templateUrl: './painel-recomendacoes.html',
})
export class PainelRecomendacoes implements OnInit, OnChanges {
  /** Corpo exibido no globo ('lua' | 'marte'). */
  @Input({ required: true }) corpo: Corpo = 'marte';
  /** Ano escolhido na linha do tempo do mapa. */
  @Input() ano: number | null = null;
  @Output() resultados = new EventEmitter<RecomendacoesResponse | null>();
  @Output() selecionar = new EventEmitter<SelecaoCandidato>();
  @Output() corpoChange = new EventEmitter<Corpo>();

  private readonly servico = inject(RecomendacoesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly consultas = new Subject<ConsultaRecomendacoes>();

  readonly meses = MESES;
  readonly coberturas = COBERTURAS;
  readonly opcoes = signal<OpcoesResponse | null>(null);
  readonly erroOpcoes = signal<string | null>(null);
  readonly estado = signal<EstadoBusca>({ tipo: 'ocioso' });
  readonly filtros = signal<ConsultaRecomendacoes>({
    anomes: 0,
    nicho: 'Todos',
    corpo: 'marte',
    base_id: null,
    k: 10,
    cobertura_minima: 0.7,
    estrategia: 'recursiva',
  });
  readonly selecionado = signal<{ base: string; id: string } | null>(null);
  readonly avisoNicho = signal<string | null>(null);

  readonly ano_ = computed(() => Math.floor(this.filtros().anomes / 100));
  readonly mes_ = computed(() => this.filtros().anomes % 100);
  readonly anoMin = computed(() =>
    Math.floor((this.opcoes()?.meses_observados[0] ?? 190001) / 100),
  );
  readonly anoMax = computed(() => Math.floor((this.opcoes()?.anomes_max ?? 210012) / 100));
  readonly corte = computed(() => this.opcoes()?.publicacao.corte ?? null);
  readonly estrategias = computed(() => {
    const publicadas = this.opcoes()?.publicacao.estrategias;
    return publicadas?.length ? publicadas : (['recursiva', 'auto', 'sazonal'] as Estrategia[]);
  });
  readonly futuro = computed(() => {
    const corte = this.corte();
    return corte !== null && this.filtros().anomes > corte;
  });
  readonly basesDoCorpo = computed(() =>
    (this.opcoes()?.bases ?? []).filter((b) => b.corpo === this.filtros().corpo),
  );
  readonly nichos = computed(() => {
    const base = this.basesDoCorpo().find((b) => b.base_id === this.filtros().base_id);
    const lista = base ? base.nichos : [...new Set(this.basesDoCorpo().flatMap((b) => b.nichos))];
    return lista.length ? lista : ['Todos'];
  });
  /** Só mostra resultados que pertencem aos filtros atuais. */
  readonly atual = computed<EstadoBusca>(() => {
    const estado = this.estado();
    if (estado.tipo === 'ocioso' || mesmaConsulta(estado.consulta, this.filtros())) return estado;
    return { tipo: 'carregando', consulta: this.filtros() };
  });
  readonly resposta = computed(() => {
    const estado = this.atual();
    return estado.tipo === 'sucesso' ? estado.resposta : null;
  });
  readonly detalhe = computed(() => {
    const sel = this.selecionado();
    const resposta = this.resposta();
    if (!sel || !resposta) return null;
    const grupo = resposta.resultados.find((g) => g.base_id === sel.base);
    const candidato = grupo?.candidatos.find((c) => c.location_id === sel.id);
    return grupo && candidato ? { grupo, candidato } : null;
  });

  ngOnInit() {
    this.consultas
      .pipe(
        debounceTime(300),
        distinctUntilChanged(mesmaConsulta),
        switchMap((consulta) => this.servico.buscar(consulta)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((estado) => {
        this.estado.set(estado);
        if (estado.tipo === 'sucesso' && mesmaConsulta(estado.consulta, this.filtros())) {
          this.resultados.emit(estado.resposta);
          this.selecionarPrimeiro(estado.resposta);
        }
      });
    this.servico
      .opcoes()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (opcoes) => {
          this.opcoes.set(opcoes);
          const estrategia = opcoes.publicacao.estrategia_padrao_futuro;
          const ultimo = opcoes.meses_observados[opcoes.meses_observados.length - 1];
          const ano = this.ano ?? Math.floor(ultimo / 100);
          this.atualizar({
            corpo: this.corpo,
            estrategia: opcoes.publicacao.estrategias.includes(estrategia)
              ? estrategia
              : 'recursiva',
            anomes: this.limitar(ano * 100 + (ultimo % 100)),
          });
        },
        error: () => this.erroOpcoes.set('Não foi possível carregar as opções da API.'),
      });
  }

  ngOnChanges(mudancas: SimpleChanges) {
    if (!this.opcoes()) return;
    if (mudancas['corpo'] && this.corpo !== this.filtros().corpo) {
      this.atualizar({ corpo: this.corpo, base_id: null });
    }
    if (mudancas['ano'] && this.ano !== null && this.ano !== this.ano_()) {
      this.atualizar({ anomes: this.limitar(this.ano * 100 + this.mes_()) });
    }
  }

  // ------------------------------------------------------------------ filtros
  private limitar(anomes: number): number {
    const opcoes = this.opcoes();
    if (!opcoes) return anomes;
    const primeiro = opcoes.meses_observados[0];
    return Math.min(opcoes.anomes_max, Math.max(primeiro, anomes));
  }

  private atualizar(parcial: Partial<ConsultaRecomendacoes>) {
    const proximo = { ...this.filtros(), ...parcial };
    if (!this.nichosPara(proximo).includes(proximo.nicho)) {
      this.avisoNicho.set(
        `O nicho “${NOMES_NICHO[proximo.nicho] ?? proximo.nicho}” não existe para esta seleção; voltei para Todos.`,
      );
      proximo.nicho = 'Todos';
    } else if (parcial.nicho !== undefined || parcial.base_id !== undefined) {
      this.avisoNicho.set(null);
    }
    this.filtros.set(proximo);
    this.selecionado.set(null);
    this.resultados.emit(null);
    this.consultas.next(proximo);
  }

  private nichosPara(consulta: ConsultaRecomendacoes): string[] {
    const bases = (this.opcoes()?.bases ?? []).filter((b) => b.corpo === consulta.corpo);
    const base = bases.find((b) => b.base_id === consulta.base_id);
    return base ? base.nichos : [...new Set(bases.flatMap((b) => b.nichos))];
  }

  mudarAno(valor: string) {
    const ano = Math.round(Number(valor));
    if (Number.isFinite(ano) && ano > 1000)
      this.atualizar({ anomes: this.limitar(ano * 100 + this.mes_()) });
  }
  mudarMes(valor: string) {
    const mes = Number(valor);
    if (Number.isInteger(mes) && mes >= 1 && mes <= 12) {
      this.atualizar({ anomes: this.limitar(this.ano_() * 100 + mes) });
    }
  }
  mudarCorpo(corpo: Corpo) {
    if (corpo === this.filtros().corpo) return;
    this.corpoChange.emit(corpo);
    this.atualizar({ corpo, base_id: null });
  }
  mudarBase(valor: string) {
    this.atualizar({ base_id: valor || null });
  }
  mudarNicho(valor: string) {
    this.atualizar({ nicho: valor });
  }
  mudarK(valor: string) {
    const k = Math.round(Number(valor));
    if (Number.isFinite(k)) this.atualizar({ k: Math.min(50, Math.max(1, k)) });
  }
  mudarCobertura(valor: string) {
    const cobertura = Number(valor);
    if (this.coberturas.includes(cobertura)) this.atualizar({ cobertura_minima: cobertura });
  }
  mudarEstrategia(valor: string) {
    if (this.estrategias().includes(valor as Estrategia))
      this.atualizar({ estrategia: valor as Estrategia });
  }
  tentarDeNovo() {
    const consulta = { ...this.filtros() };
    this.estado.set({ tipo: 'carregando', consulta });
    this.servico
      .buscar(consulta)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((estado) => {
        if (estado.tipo !== 'ocioso' && mesmaConsulta(estado.consulta, this.filtros()))
          this.estado.set(estado);
        if (estado.tipo === 'sucesso') this.resultados.emit(estado.resposta);
      });
  }

  // --------------------------------------------------------------- seleção
  private selecionarPrimeiro(resposta: RecomendacoesResponse) {
    const grupo = resposta.resultados.find((g) => g.candidatos.length);
    if (grupo) this.escolher(grupo, grupo.candidatos[0], resposta);
  }

  escolher(grupo: GrupoBase, candidato: Candidato, resposta = this.resposta()) {
    if (!resposta) return;
    this.selecionado.set({ base: grupo.base_id, id: candidato.location_id });
    this.selecionar.emit({ grupo, candidato, resposta });
  }

  ativo(grupo: GrupoBase, candidato: Candidato): boolean {
    const sel = this.selecionado();
    return sel?.base === grupo.base_id && sel.id === candidato.location_id;
  }

  // ---------------------------------------------------------------- textos
  nomeNicho(nicho: string): string {
    return NOMES_NICHO[nicho] ?? nicho;
  }
  rotuloOrigem(origem: string): string {
    return ROTULO_ORIGEM[origem] ?? origem;
  }
  metodo(metodo: string): string {
    return descreverMetodo(metodo);
  }
  metodosLista(resposta: RecomendacoesResponse): { variavel: string; metodo: string }[] {
    return Object.entries(resposta.metodos).map(([variavel, metodo]) => ({
      variavel,
      metodo: descreverMetodo(metodo),
    }));
  }
  fallbacks(resposta: RecomendacoesResponse): string[] {
    return Object.entries(resposta.metodos)
      .filter(([, metodo]) => metodo === 'sazonal_t-12' || metodo.startsWith('persistencia'))
      .map(([variavel]) => variavel);
  }
  mesTexto(anomes: number | null): string {
    if (!anomes) return '—';
    return `${MESES[(anomes % 100) - 1]}/${Math.floor(anomes / 100)}`;
  }
  statusTexto(status: string): string {
    return (
      {
        ok: '',
        parcial: 'Algum critério não tem dado em nenhum local neste mês; a nota usa os demais.',
        sem_dados: 'Faltam dados terrestres de critérios desta base neste mês.',
        sem_candidatos: 'Nenhum local atinge a cobertura mínima.',
        nicho_incompativel: 'Esta base não tem esse nicho.',
      }[status] ?? status
    );
  }
  numero(valor: number | null | undefined, casas = 1): string {
    if (valor === null || valor === undefined || !Number.isFinite(valor)) return '—';
    return valor.toLocaleString('pt-BR', {
      maximumFractionDigits: casas,
      minimumFractionDigits: 0,
    });
  }
  diferenca(criterio: Criterio, candidato: Candidato): number | null {
    const valor = candidato.valores[criterio.variavel];
    return valor === null || valor === undefined ? null : valor - criterio.alvo;
  }
  coordenadas(c: Candidato): string {
    const lat = `${Math.abs(c.latitude).toFixed(2)}°${c.latitude >= 0 ? 'N' : 'S'}`;
    const lon = `${Math.abs(c.longitude).toFixed(2)}°${c.longitude >= 0 ? 'L' : 'O'}`;
    return `${lat}, ${lon}`;
  }
}
