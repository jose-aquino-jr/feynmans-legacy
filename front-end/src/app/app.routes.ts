import { Routes } from '@angular/router';
import { Home } from './pages/home/home';

export const routes: Routes = [
  { path: '', component: Home, pathMatch: 'full' },
  { path: 'mapa', loadComponent: () => import('./pages/mapa/mapa').then((m) => m.MapPage) },
  { path: 'metodologia', loadComponent: () => import('./pages/metodologia/metodologia').then((m) => m.MethodologyPage) },

  { path: 'home', redirectTo: '', pathMatch: 'full' },
  { path: '**', redirectTo: '' },
];
