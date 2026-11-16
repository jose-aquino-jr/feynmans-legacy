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

  readonly steps = [
    {
      index: '01',
      title: 'Gather the evidence',
      description:
        'Bring together open information about geology, climate, terrain, and soils. Source and geographic coverage matter as much as the measured value.',
    },
    {
      index: '02',
      title: 'Make data comparable',
      description:
        'Prepare measurements with different units and spatial scales so each criterion can be read consistently, while keeping gaps and limitations visible.',
    },
    {
      index: '03',
      title: 'Compare candidate regions',
      description:
        'Evaluate terrestrial locations against selected conditions on the Moon or Mars, then inspect the strongest analogues on the interactive map.',
    },
  ];

  readonly criteria = [
    { name: 'Geology', description: 'Rock types and geological context' },
    { name: 'Temperature', description: 'Local thermal conditions' },
    { name: 'Aridity', description: 'Dryness and water availability' },
    { name: 'Relief', description: 'Surface shape and elevation change' },
    { name: 'Altitude', description: 'Elevation above sea level' },
    { name: 'Soil', description: 'Surface material and soil properties' },
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
