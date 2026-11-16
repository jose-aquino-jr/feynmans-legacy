import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { MapPage } from './mapa';

// jsdom has no ResizeObserver.
(globalThis as any).ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('MapPage', () => {
  let component: MapPage;
  let fixture: ComponentFixture<MapPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MapPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    })
      // jsdom has no WebGL: keep the panel wiring, drop the Three.js canvas.
      .overrideComponent(MapPage, {
        set: {
          imports: [],
          template: '<aside #panel><div #glassBody></div></aside>',
        },
      })
      .compileComponents();

    fixture = TestBed.createComponent(MapPage);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
    expect(component.body).toBe('mars');
  });

  it('keeps the panel host available for layout observation', () => {
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('aside')).not.toBeNull();
  });
});
