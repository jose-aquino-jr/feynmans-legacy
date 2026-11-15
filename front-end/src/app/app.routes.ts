import { Routes } from '@angular/router';
import { Home } from './pages/home/home';
import { Mapa } from './pages/mapa/mapa';

export const routes: Routes = [
  { path: '', component: Home, pathMatch: 'full' },
  { path: 'mapa', component: Mapa },

  { path: 'home', redirectTo: '', pathMatch: 'full' },
  { path: '**', redirectTo: '' },
];