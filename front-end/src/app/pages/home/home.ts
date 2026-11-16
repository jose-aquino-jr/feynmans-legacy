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
    { index: '01', title: 'Data source one', desc: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed erat felis, euismod et dictum sed.' },
    { index: '02', title: 'Data source two', desc: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed erat felis, euismod et dictum sed.' },
    { index: '03', title: 'Data source three', desc: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed erat felis, euismod et dictum sed.' },
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
