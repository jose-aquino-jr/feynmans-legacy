import { AfterViewInit, Component, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-methodology-page',
  imports: [RouterLink],
  templateUrl: './metodologia.html',
  styleUrl: './metodologia.css',
  host: {
    class: 'relative block min-h-screen overflow-x-hidden bg-ink font-sans text-cream',
  },
})
export class MethodologyPage implements AfterViewInit, OnDestroy {
  readonly scrolled = signal(false);
  readonly navItems = [
    { label: 'HOME', link: '/' },
    { label: 'MAP', link: '/mapa' },
    { label: 'METHODOLOGY', link: '/metodologia' },
    { label: 'DATA', link: '/', fragment: 'data' },
    { label: 'TEAM', link: '/', fragment: 'team' },
  ];

  readonly keyNumbers = [
    { value: '21', label: 'niches · 9 Moon / 12 Mars' },
    { value: '51', label: 'comparison criteria' },
    { value: '34', label: 'terrestrial variables' },
    { value: '8', label: 'reference bases · 2 Moon / 6 Mars' },
  ];

  readonly steps = [
    {
      index: '01',
      title: 'Build a shared taxonomy',
      description:
        'Organize the comparison into 21 niches: nine lunar and twelve Martian. They contain 51 criteria expressed through 34 terrestrial variables, which can serve more than one niche.',
    },
    {
      index: '02',
      title: 'Set measured targets',
      description:
        'Compare eight reference bases using 77 target values drawn from mission measurements. Each value records its source, unit, quantity, confidence, and whether it is measured, classified, or a terrestrial equivalent.',
    },
    {
      index: '03',
      title: 'Score each criterion',
      description:
        'Use tolerance = max distance from the target to Earth P1 or P99. Score = max(0, 100 − 100 × |Earth − target| / tolerance), so the closest terrestrial match scores highest.',
    },
    {
      index: '04',
      title: 'Account for data coverage',
      description:
        'Combine criteria with a weighted mean and renormalize weights over available data. A candidate needs at least 70% overall coverage and 50% coverage within each niche.',
    },
    {
      index: '05',
      title: 'Keep recommendations diverse',
      description:
        'Cluster candidate environments across 22 variables and enforce 500 km separation. Exclude water-covered cells and the classical analog sites from automatic discovery.',
    },
    {
      index: '06',
      title: 'Add logistics and forecasts',
      description:
        'Logistics weights accessibility, support, and routes at 0.40, 0.35, and 0.25; cost-benefit is the square root of similarity × logistics. LightGBM forecasts three months and reduced mean test error by 41% across 25 series.',
    },
  ];

  readonly criteria = [
    { name: 'Thermal', description: 'Air and surface temperatures, thermal inertia, and day–night range.' },
    { name: 'Lighting and radiation', description: 'Solar geometry, illumination, radiation, and shadow conditions.' },
    { name: 'Water and ice', description: 'Water availability, ice, precipitation, and permafrost indicators.' },
    { name: 'Water and aridity', description: 'Dryness, soil moisture, evaporation, and atmospheric water.' },
    { name: 'Terrain', description: 'Elevation, slope, roughness, and local relief.' },
    { name: 'Geology', description: 'Rock types, mineralogy, elemental composition, and geologic context.' },
    { name: 'Surface and dust', description: 'Soil properties, albedo, dust concentration, and deposition.' },
    { name: 'Wind and dust processes', description: 'Wind speed, aeolian activity, and dust transport conditions.' },
    { name: 'Biology and habitability', description: 'Environmental conditions relevant to habitability and biological constraints.' },
    { name: 'Subsurface', description: 'Subsurface structure, caves, pits, and resources inferred from available datasets.' },
    { name: 'Atmosphere', description: 'Pressure, atmospheric composition proxies, and weather conditions.' },
    { name: 'Operations', description: 'Surface conditions that affect field work, equipment, and crew procedures.' },
  ];

  private readonly onScroll = () => this.scrolled.set(window.scrollY > 40);

  ngAfterViewInit() {
    window.addEventListener('scroll', this.onScroll, { passive: true });
    this.onScroll();
  }

  ngOnDestroy() {
    window.removeEventListener('scroll', this.onScroll);
  }
}
