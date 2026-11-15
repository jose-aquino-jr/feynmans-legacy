import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MapPage } from './mapa';

describe('MapPage', () => {
  let component: MapPage;
  let fixture: ComponentFixture<MapPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MapPage],
    }).compileComponents();

    fixture = TestBed.createComponent(MapPage);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
