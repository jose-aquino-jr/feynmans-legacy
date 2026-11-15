import { Routes } from '@angular/router';
import { Mapa } from './pages/mapa/mapa';
import { Home } from './pages/home/home';

export const routes: Routes = [
  { path: 'mapa', component: Mapa },
  { path: 'mapa', redirectTo: '' },

  { path: 'home', component: Home },
  { path: 'home', redirectTo: 'home' },
];