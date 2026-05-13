import { Component, provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { App } from './app';
import { AuthApiService } from './features/auth/auth-api.service';
import { PublicApiService } from './features/public/public-api.service';
import { provideRouter } from '@angular/router';
import { ToastService } from './core/services/toast.service';
import { provideTranslateService } from '@ngx-translate/core';
import { of } from 'rxjs';
import { IsUpdateAvailableResponseBody } from './features/public/public-interface';
import { MessageService } from 'primeng/api';
import { RouterTestingHarness } from '@angular/router/testing';

@Component({
  selector: 'app-test-comp',
  standalone: true,
  template: '',
})
class TestComponent {}

describe('App', () => {
  let fixture: ComponentFixture<App>;
  let component: App;

  let harness: RouterTestingHarness;
  let authApiServiceMock: jest.Mocked<AuthApiService>;
  let publicApiServiceMock: jest.Mocked<PublicApiService>;
  let toastServiceMock: jest.Mocked<ToastService>;

  beforeEach(async () => {
    authApiServiceMock = {
      initiateLogin: jest.fn(),
      isAuthorized: jest.fn().mockReturnValue(of(null)),
      isDisabled: jest.fn().mockReturnValue(of(false)),
      logout: jest.fn().mockReturnValue(of({})),
    } as unknown as jest.Mocked<AuthApiService>;

    publicApiServiceMock = {
      getVersion: jest.fn().mockReturnValue(of({ image_version: '1.2.3' })),
      isUpdateAvailable: jest.fn().mockReturnValue(
        of({
          is_available: false,
          release_url: null,
        } satisfies IsUpdateAvailableResponseBody),
      ),
    } as unknown as jest.Mocked<PublicApiService>;

    toastServiceMock = {
      success: jest.fn(),
      error: jest.fn(),
    } as unknown as jest.Mocked<ToastService>;

    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideZonelessChangeDetection(),
        provideTranslateService(),
        { provide: AuthApiService, useValue: authApiServiceMock },
        { provide: PublicApiService, useValue: publicApiServiceMock },
        { provide: ToastService, useValue: toastServiceMock },
        provideRouter([
          {
            path: '',
            pathMatch: 'full',
            redirectTo: '/containers',
          },
          {
            path: 'containers',
            component: TestComponent,
          },
          {
            path: 'auth',
            component: TestComponent,
          },
        ]),
        MessageService,
      ],
    }).compileComponents();

    harness = await RouterTestingHarness.create();
    fixture = TestBed.createComponent(App);
    component = fixture.componentInstance;
  });

  it('should create the app', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('should hide toolbar', async () => {
    fixture.detectChanges();
    await harness.navigateByUrl('/auth');
    expect(component['isToolbarVisible']()).toBe(false);
  });

  it('should show toolbar', async () => {
    fixture.detectChanges();
    await harness.navigateByUrl('/containers');
    expect(component['isToolbarVisible']()).toBe(true);
  });

  // TODO add more tests
});
