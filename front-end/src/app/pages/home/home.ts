import { Component, AfterViewInit, ElementRef, ViewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.css',
  host: {
    class: 'relative block h-screen overflow-hidden bg-ink font-sans text-cream max-md:min-h-[560px]',
  },
})
export class Home implements AfterViewInit {
  @ViewChild('bg') bgEl!: ElementRef<HTMLVideoElement>;

  readonly navItems = [
    { label: 'MAP', link: '/mapa' },
    { label: 'METHODS', link: null },
    { label: 'DATA', link: null },
    { label: 'TEAM', link: null },
  ];

  ngAfterViewInit() {
    const video = this.bgEl.nativeElement;

    video.muted = true;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      video.pause();
      return;
    }
    video.play().catch(() => {
    });
  }
}