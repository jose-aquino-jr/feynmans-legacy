import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Subject, switchMap } from 'rxjs';
import { vi } from 'vitest';

import { ConsultaRecomendacoes, EstadoBusca } from './recomendacoes.models';
import { RecomendacoesService, mesesEntre, proximoMes } from './recomendacoes.service';

const consulta = (anomes: number): ConsultaRecomendacoes => ({
  anomes, nicho: 'Todos', corpo: 'marte', base_id: 'MARTE_JEZERO', k: 10, cobertura_minima: 0.7,
  estrategia: 'recursiva',
});

const calculando = { status: 'calculando', anomes: 204007, estrategia: 'recursiva', repetir_em_segundos: 3,
  tarefa_id: 'abc', meses_calculados: 10, meses_necessarios: 167, na_fila: false };

describe('RecomendacoesService', () => {
  let servico: RecomendacoesService;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    servico = TestBed.inject(RecomendacoesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('envia estrategia=recursiva explicitamente e repete após Retry-After', () => {
    const estados: EstadoBusca[] = [];
    servico.buscar(consulta(204007)).subscribe((e) => estados.push(e));
    const primeira = http.expectOne((r) => r.url.endsWith('/analogos/recomendacoes'));
    expect(primeira.request.params.get('estrategia')).toBe('recursiva');
    expect(primeira.request.params.get('base_id')).toBe('MARTE_JEZERO');
    expect(primeira.request.params.get('corpo')).toBeNull();
    primeira.flush(calculando, { status: 202, statusText: 'Accepted', headers: { 'Retry-After': '3' } });
    expect(estados.map((e) => e.tipo)).toEqual(['carregando', 'calculando']);
    vi.advanceTimersByTime(2999);
    http.expectNone((r) => r.url.endsWith('/analogos/recomendacoes'));
    vi.advanceTimersByTime(1);
    http.expectOne((r) => r.url.endsWith('/analogos/recomendacoes')).flush({ anomes: 204007, origem: 'extrapolada', resultados: [] });
    expect(estados.at(-1)?.tipo).toBe('sucesso');
  });

  it('cancela o polling antigo quando os filtros mudam', () => {
    const consultas = new Subject<ConsultaRecomendacoes>();
    const estados: EstadoBusca[] = [];
    consultas.pipe(switchMap((c) => servico.buscar(c))).subscribe((e) => estados.push(e));
    consultas.next(consulta(204001));
    const janeiro = http.expectOne((r) => r.params.get('anomes') === '204001');
    janeiro.flush(calculando, { status: 202, statusText: 'Accepted', headers: { 'Retry-After': '3' } });
    consultas.next(consulta(204007));
    http.expectOne((r) => r.params.get('anomes') === '204007').flush({ anomes: 204007, origem: 'extrapolada', resultados: [] });
    vi.advanceTimersByTime(10_000);
    http.expectNone((r) => r.params.get('anomes') === '204001');
    const final = estados.at(-1)!;
    expect(final.tipo).toBe('sucesso');
    expect(final.tipo !== 'ocioso' && final.consulta.anomes).toBe(204007);
  });

  it('transforma erro da API em estado de falha', () => {
    const estados: EstadoBusca[] = [];
    servico.buscar(consulta(202613)).subscribe((e) => estados.push(e));
    http.expectOne(() => true).flush(
      { detail: { code: 'anomes_invalido', message: 'Mês inválido.', context: {} } },
      { status: 400, statusText: 'Bad Request' },
    );
    expect(estados.at(-1)).toMatchObject({ tipo: 'falha', codigo: 'anomes_invalido', mensagem: 'Mês inválido.' });
  });

  it('conta meses entre AAAAMM', () => {
    expect(mesesEntre(202608, 204007)).toBe(167);
    expect(proximoMes(202612)).toBe(202701);
  });
});
