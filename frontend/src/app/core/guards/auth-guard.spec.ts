import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
} from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { authGuard } from './auth-guard';
import { AuthApiService } from 'src/app/features/auth/auth-api.service';
import { provideZonelessChangeDetection } from '@angular/core';

describe('authGuard', () => {
  let authApiServiceMock: jest.Mocked<AuthApiService>;
  let routerMock: jest.Mocked<Router>;

  beforeEach(() => {
    authApiServiceMock = { isAuthorized: jest.fn() } as unknown as jest.Mocked<AuthApiService>;
    routerMock = { navigate: jest.fn() } as unknown as jest.Mocked<Router>;

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: AuthApiService, useValue: authApiServiceMock },
        { provide: Router, useValue: routerMock },
      ],
    });
  });

  function runGuard() {
    return TestBed.runInInjectionContext(
      () =>
        authGuard(
          {} as ActivatedRouteSnapshot,
          {} as RouterStateSnapshot,
        ) as Observable<boolean>,
    );
  }

  it('should return true when user is authorized', (done) => {
    authApiServiceMock.isAuthorized.mockReturnValue(of(null));

    runGuard().subscribe((result) => {
      expect(result).toBe(true);
      expect(routerMock.navigate).not.toHaveBeenCalled();
      done();
    });
  });

  it('should return false and redirect when unauthorized (error)', (done) => {
    authApiServiceMock.isAuthorized.mockReturnValue(
      throwError(() => new Error('Unauthorized')),
    );

    runGuard().subscribe((result) => {
      expect(result).toBe(false);
      expect(routerMock.navigate).toHaveBeenCalledWith(['/auth']);
      done();
    });
  });
});
