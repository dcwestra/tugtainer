import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  input,
  resource,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { TranslatePipe } from '@ngx-translate/core';
import { ButtonModule } from 'primeng/button';
import { ButtonGroupModule } from 'primeng/buttongroup';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToggleButtonModule } from 'primeng/togglebutton';
import { Tooltip } from 'primeng/tooltip';
import { ToolbarModule } from 'primeng/toolbar';
import { catchError, firstValueFrom, of } from 'rxjs';
import { ToastService } from 'src/app/core/services/toast.service';
import { SwarmApiService } from './swarm-api.service';
import { SwarmServiceLogsComponent } from './swarm-service-logs.component';
import { ISwarmService, ISwarmServicePatch } from './swarm.interface';

@Component({
  selector: 'app-swarm-services-inline',
  imports: [
    TableModule,
    ButtonModule,
    ButtonGroupModule,
    TagModule,
    TranslatePipe,
    ToggleButtonModule,
    Tooltip,
    FormsModule,
    ToolbarModule,
    IconFieldModule,
    InputTextModule,
    InputIconModule,
    SwarmServiceLogsComponent,
  ],
  templateUrl: './swarm-services-inline.component.html',
  styleUrl: './swarm-services-inline.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SwarmServicesInlineComponent {
  private readonly swarmApiService = inject(SwarmApiService);
  private readonly toastService = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);

  public readonly clusterId = input.required<string>();

  protected readonly logsDialog = viewChild.required(SwarmServiceLogsComponent);

  protected readonly services = resource<ISwarmService[], { clusterId: string }>({
    params: () => ({ clusterId: this.clusterId() }),
    loader: ({ params }) =>
      firstValueFrom(
        this.swarmApiService.listServices(params.clusterId).pipe(
          catchError((error) => {
            this.toastService.error(error);
            return of([]);
          }),
        ),
      ),
    defaultValue: [],
  });

  protected readonly availableCount = computed(
    () => this.services.value().filter((s) => s.update_available).length,
  );

  protected readonly patchingServices = signal<Set<string>>(new Set());
  protected readonly checkingServices = signal<Set<string>>(new Set());
  protected readonly updatingServices = signal<Set<string>>(new Set());

  protected readonly isCheckingAll = signal(false);
  protected readonly isUpdatingAll = signal(false);

  protected toggleCheck(service: ISwarmService): void {
    this._patch(service, { check_enabled: !service.check_enabled });
  }

  protected toggleUpdate(service: ISwarmService): void {
    this._patch(service, { update_enabled: !service.update_enabled });
  }

  protected checkService(service: ISwarmService): void {
    const key = service.name;
    this.checkingServices.update(s => new Set([...s, key]));
    this.swarmApiService
      .checkService(this.clusterId(), service.name)
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe((cacheId) => {
        if (!cacheId) {
          this.checkingServices.update(s => { const n = new Set(s); n.delete(key); return n; });
          return;
        }
        this.swarmApiService.watchProgress(cacheId)
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            complete: () => {
              this.checkingServices.update(s => { const n = new Set(s); n.delete(key); return n; });
              this.services.reload();
            },
          });
      });
  }

  protected updateService(service: ISwarmService): void {
    const key = service.name;
    this.updatingServices.update(s => new Set([...s, key]));
    this.swarmApiService
      .updateService(this.clusterId(), service.name)
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe((cacheId) => {
        if (!cacheId) {
          this.updatingServices.update(s => { const n = new Set(s); n.delete(key); return n; });
          return;
        }
        this.swarmApiService.watchProgress(cacheId)
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            complete: () => {
              this.updatingServices.update(s => { const n = new Set(s); n.delete(key); return n; });
              this.services.reload();
            },
          });
      });
  }

  protected checkAll(): void {
    this.isCheckingAll.set(true);
    this.swarmApiService
      .checkCluster(this.clusterId())
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe((cacheId) => {
        if (!cacheId) { this.isCheckingAll.set(false); return; }
        this.swarmApiService.watchProgress(cacheId)
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            complete: () => {
              this.isCheckingAll.set(false);
              this.services.reload();
            },
          });
      });
  }

  protected updateAll(): void {
    this.isUpdatingAll.set(true);
    this.swarmApiService
      .updateCluster(this.clusterId())
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe((cacheId) => {
        if (!cacheId) { this.isUpdatingAll.set(false); return; }
        this.swarmApiService.watchProgress(cacheId)
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            complete: () => {
              this.isUpdatingAll.set(false);
              this.services.reload();
            },
          });
      });
  }

  private _patch(service: ISwarmService, body: ISwarmServicePatch): void {
    const key = service.name;
    this.patchingServices.update((s) => new Set([...s, key]));
    this.swarmApiService
      .patchService(this.clusterId(), service.name, body)
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe((updated) => {
        this.patchingServices.update((s) => { const n = new Set(s); n.delete(key); return n; });
        if (updated) this.services.reload();
      });
  }

  protected openLogs(service: ISwarmService): void {
    this.logsDialog().open(service);
  }

  protected replicasLabel(service: ISwarmService): string {
    const running = service.running_replicas != null ? service.running_replicas : '?';
    const desired = service.replicas != null ? service.replicas : '?';
    return `${running}/${desired}`;
  }
}
