import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NewPasswordFormComponent } from './new-password-form.component';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideTranslateService } from '@ngx-translate/core';
import { By } from '@angular/platform-browser';

describe('NewPasswordFormComponent', () => {
  let component: NewPasswordFormComponent;
  let fixture: ComponentFixture<NewPasswordFormComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewPasswordFormComponent],
      providers: [provideTranslateService(), provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(NewPasswordFormComponent);
    component = fixture.componentInstance;

    fixture.detectChanges();
  });

  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  function setValidPasswords() {
    component['form'].setValue({
      password: '123QWErty!',
      confirm_password: '123QWErty!',
    });
  }

  function setInvalidPasswords() {
    component['form'].setValue({
      password: '123qwe!',
      confirm_password: 'rty123',
    });
  }

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should have invalid form initially', () => {
    expect(component['form'].invalid).toBe(true);
  });

  it('should validate matching passwords', () => {
    setValidPasswords();
    expect(component['form'].valid).toBe(true);
    expect(component['form'].errors).toBeNull();
  });

  it('should invalidate when passwords do not match', () => {
    setInvalidPasswords();
    expect(component['form'].invalid).toBe(true);
    expect(component['form'].errors).toEqual({
      passwordMatchValidator: true,
    });
  });

  it('should set confirmPasswordError signal correctly', () => {
    setInvalidPasswords();
    fixture.detectChanges();

    expect(component['confirmPasswordError']()).toBe(true);

    setValidPasswords();
    fixture.detectChanges();

    expect(component['confirmPasswordError']()).toBe(false);
  });

  it('should not emit when form is invalid', () => {
    jest.spyOn(component.OnSubmit, 'emit');

    component['onSubmit']();

    expect(component.OnSubmit.emit).not.toHaveBeenCalled();
  });

  it('should emit form value when valid', () => {
    jest.spyOn(component.OnSubmit, 'emit');

    setValidPasswords();
    component['form'].markAsDirty();

    component['onSubmit']();

    expect(component.OnSubmit.emit).toHaveBeenCalledWith({
      password: '123QWErty!',
      confirm_password: '123QWErty!',
    });
  });

  it('should mark form as pristine after submit', () => {
    setValidPasswords();
    component['form'].markAsDirty();

    component['onSubmit']();

    expect(component['form'].pristine).toBe(true);
  });

  it('should disable submit button when form is not dirty', () => {
    const button = fixture.debugElement.query(By.css('p-button'));

    expect(button.componentInstance.disabled).toBe(true);
  });

  it('should enable submit button when form is dirty', () => {
    component['form'].markAsDirty();
    fixture.detectChanges();

    const button = fixture.debugElement.query(By.css('p-button'));

    expect(button.componentInstance.disabled).toBe(false);
  });
});
