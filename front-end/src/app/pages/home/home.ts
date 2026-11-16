import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.css',
  host: {
    class: 'relative block overflow-x-hidden bg-ink font-sans text-cream',
  },
})
export class Home implements AfterViewInit, OnDestroy {
  @ViewChild('bg') bgEl!: ElementRef<HTMLVideoElement>;

  readonly scrolled = signal(false);
  private readonly onScroll = () => this.scrolled.set(window.scrollY > 40);

  readonly navItems: Array<{ label: string; link: string | null; anchor?: string }> = [
    { label: 'MAP', link: '/mapa' },
    { label: 'METHODOLOGY', link: '/metodologia' },
    { label: 'DATA', link: null, anchor: 'data' },
    { label: 'TEAM', link: null, anchor: 'team' },
  ];

  readonly dataCards = [
    {
      index: '01',
      title: 'Earth observation grid',
      stat: '85,726 locations · 7.9M rows',
      desc: 'A global 0.5° grid covers 92 months from January 2019 through August 2026, with 16 dynamic variables and 67 static attributes.',
      sources: '12 MERRA-2 and 4 MODIS Terra products, plus SEDAC, EONET, Macrostrat, SoilGrids, and terrain data. Four derived variables add solar geometry, pressure, thermal amplitude, and permafrost; eight classical Earth analogs form a separate reference set.',
    },
    {
      index: '02',
      title: 'Lunar scientific base',
      stat: '60 regions · 404 variables',
      desc: 'An equal-area Moon atlas combines 36 datasets into 22,406 observation records and passed quality control with zero errors.',
      sources: 'LRO LOLA, Diviner, LROC and Mini-RF; Lunar Prospector; GRAIL; SELENE; crater inventories; and the USGS geologic map.',
    },
    {
      index: '03',
      title: 'Martian scientific base',
      stat: '6 Martian bases · 61 target values',
      desc: 'Each reference profile uses published measurements and mapped surface properties from six proposed Martian base regions.',
      sources: 'MOLA topography, TES thermal inertia, Odyssey GRS, CRISM mineralogy, USGS geologic maps, and Mars 2020 CTX imagery, elevation, and slope.',
    },
  ];

  readonly dataHighlights = [
    { value: '8', label: 'reference bases: 2 lunar and 6 Martian' },
    { value: '77', label: 'target values with source, unit, and confidence' },
    { value: '358', label: 'ranked pairs across 187 sites and 35 countries' },
    { value: '182 + 561', label: 'support installations and route records' },
    { value: '5,280', label: 'monthly rows: Sep 2025–Nov 2026; 4,224 observed and 1,056 forecast' },
  ];

  onNav(anchor: string | undefined, event: Event) {
    event.preventDefault();
    if (!anchor) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.getElementById(anchor)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }

  ngAfterViewInit() {
    window.addEventListener('scroll', this.onScroll, { passive: true });
    this.onScroll();

    const video = this.bgEl.nativeElement;
    video.muted = true;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      video.pause();
      return;
    }
    video.play().catch(() => {});
  }

  ngOnDestroy() {
    window.removeEventListener('scroll', this.onScroll);
  }
}
