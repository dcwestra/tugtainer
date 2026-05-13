import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  resource,
  signal,
  viewChild,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { ButtonModule } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { TooltipModule } from 'primeng/tooltip';
import { catchError, firstValueFrom, of } from 'rxjs';
import { ToastService } from 'src/app/core/services/toast.service';
import { SwarmApiService } from './swarm-api.service';
import { SwarmServiceLogsComponent } from './swarm-service-logs.component';
import { ISwarmService } from './swarm.interface';
import { FormsModule } from '@angular/forms';
import { DayjsPipe } from '@shared/pipes/dayjs.pipe';

@Component({
  selector: 'app-swarm-services',
  imports: [
    TableModule,
    ButtonModule,
    TagModule,
    TranslatePipe,
    ToolbarModule,
    ToggleSwitchModule,
    TooltipModule,
    RouterLink,
    FormsModule,
    DayjsPipe,
    SwarmServiceLogsComponent,
  ],
  templateUrl: './swarm-services.component.html',
  styleUrl: './swarm-services.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SwarmServicesComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly swarmApiService = inject(SwarmApiService);
  private readonly toastService = inject(ToastService);

  protected readonly logsDialog = viewChild.required(SwarmServiceLogsComponent);

  protected readonly clusterId = this.route.snapshot.paramMap.get('clusterId') ?? '';

  protected readonly services = resource<ISwarmService[], unknown>({
    loader: () =>
      firstValueFrom(
        this.swarmApiService.listServices(this.clusterId).pipe(
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
  protected readonly isChecking = signal(false);
  protected readonly isUpdating = signal(false);

  protected toggleCheck(service: ISwarmService): void {
    this._patch(service, { check_enabled: !service.check_enabled });
  }

  protected toggleUpdate(service: ISwarmService): void {
    this._patch(service, { update_enabled: !service.update_enabled });
  }

  protected checkAll(): void {
    this.isChecking.set(true);
    this.swarmApiService
      .checkCluster(this.clusterId)
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe(() => {
        this.isChecking.set(false);
        this.services.reload();
      });
  }

  protected updateAll(): void {
    this.isUpdating.set(true);
    this.swarmApiService
      .updateCluster(this.clusterId)
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe(() => {
        this.isUpdating.set(false);
        this.services.reload();
      });
  }

  private _patch(service: ISwarmService, body: Partial<ISwarmService>): void {
    const key = service.name;
    this.patchingServices.update((s) => new Set([...s, key]));
    this.swarmApiService
      .patchService(this.clusterId, service.name, body)
      .pipe(catchError((error) => { this.toastService.error(error); return of(null); }))
      .subscribe((updated) => {
        this.patchingServices.update((s) => { const n = new Set(s); n.delete(key); return n; });
        if (updated) {
          this.services.reload();
        }
      });
  }

  protected openLogs(service: ISwarmService): void {
    this.logsDialog().open(service);
  }

  protected replicasLabel(service: ISwarmService): string {
    if (service.mode === 'global') return 'global';
    return service.replicas != null ? String(service.replicas) : '—';
  }
}
