import { HttpClient, HttpErrorResponse, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, defer, of, shareReplay, switchMap, timer } from 'rxjs';

import {
  Calculando,
  ConsultaRecomendacoes,
  EstadoBusca,
  OpcoesResponse,
  RecomendacoesResponse,
} from './recomendacoes.models';

export const API_BASE = '/api/v1';

/** AAAAMM do primeiro mês depois do corte observado. */
export function proximoMes(anomes: number): number {
  const ano = Math.floor(anomes / 100);
  const mes = anomes % 100;
  return mes === 12 ? (ano + 1) * 100 + 1 : anomes + 1;
}

export function mesesEntre(de: number, ate: number): number {
  return (Math.floor(ate / 100) - Math.floor(de / 100)) * 12 + ((ate % 100) - (de % 100));
}

@Injectable({ providedIn: 'root' })
export class RecomendacoesService {
  private readonly http = inject(HttpClient);
  private opcoes$?: Observable<OpcoesResponse>;

  opcoes(): Observable<OpcoesResponse> {
    this.opcoes$ ??= this.http
      .get<OpcoesResponse>(`${API_BASE}/analogos/recomendacoes/opcoes`)
      .pipe(shareReplay(1));
    return this.opcoes$;
  }

  /**
   * Faz a consulta e repete enquanto a API responder 202, respeitando Retry-After.
   * Cada emissão carrega a `consulta` de origem; quem usa com `switchMap` descarta
   * automaticamente o polling de filtros antigos.
   */
  buscar(consulta: ConsultaRecomendacoes): Observable<EstadoBusca> {
    const params = paramsDe(consulta);
    const tentativa = (): Observable<EstadoBusca> =>
      this.http
        .get<RecomendacoesResponse | Calculando>(`${API_BASE}/analogos/recomendacoes`, {
          params,
          observe: 'response',
        })
        .pipe(
          switchMap((resposta: HttpResponse<RecomendacoesResponse | Calculando>) => {
            if (resposta.status === 202) {
              const progresso = resposta.body as Calculando;
              const segundos = Number(resposta.headers.get('Retry-After')) || progresso.repetir_em_segundos || 5;
              const estado: EstadoBusca = { tipo: 'calculando', consulta, progresso };
              return timer(segundos * 1000).pipe(
                switchMap(() => tentativa()),
                (fluxo) => concatInicio(estado, fluxo),
              );
            }
            return of<EstadoBusca>({ tipo: 'sucesso', consulta, resposta: resposta.body as RecomendacoesResponse });
          }),
          catchError((erro: HttpErrorResponse) => of<EstadoBusca>(falha(consulta, erro))),
        );
    return concatInicio<EstadoBusca>({ tipo: 'carregando', consulta }, defer(tentativa));
  }
}

function paramsDe(consulta: ConsultaRecomendacoes): HttpParams {
  let params = new HttpParams()
    .set('anomes', consulta.anomes)
    .set('nicho', consulta.nicho)
    .set('k', consulta.k)
    .set('cobertura_minima', consulta.cobertura_minima)
    .set('estrategia', consulta.estrategia);
  params = consulta.base_id ? params.set('base_id', consulta.base_id) : params.set('corpo', consulta.corpo);
  return params;
}

function falha(consulta: ConsultaRecomendacoes, erro: HttpErrorResponse): EstadoBusca {
  const detalhe = erro.error?.detail;
  return {
    tipo: 'falha',
    consulta,
    codigo: detalhe?.code ?? `http_${erro.status}`,
    mensagem: detalhe?.message ?? (erro.status === 0 ? 'API indisponível.' : 'Falha na consulta.'),
  };
}

function concatInicio<T>(primeiro: T, resto: Observable<T>): Observable<T> {
  return new Observable<T>((assinante) => {
    assinante.next(primeiro);
    return resto.subscribe(assinante);
  });
}

export function mesmaConsulta(a: ConsultaRecomendacoes, b: ConsultaRecomendacoes): boolean {
  return (Object.keys(a) as (keyof ConsultaRecomendacoes)[]).every((chave) => a[chave] === b[chave]);
}

export const ROTULO_ORIGEM: Record<string, string> = {
  observada: 'Observado',
  prevista: 'Previsto (LightGBM direto)',
  extrapolada: 'Projeção exploratória (recursiva)',
  cenario_sazonal: 'Cenário sazonal',
};

export const descreverMetodo = (metodo: string): string =>
  metodo.startsWith('lightgbm_h')
    ? `LightGBM H${metodo.slice(10)}`
    : metodo.startsWith('persistencia_h')
      ? `persistência H${metodo.slice(14)}`
      : metodo === 'sazonal_t-12'
        ? 'mesmo mês do ano anterior'
        : metodo.startsWith('observado_')
          ? `observado em ${metodo.slice(10)}`
          : metodo;


