import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  resource,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { ButtonModule } from 'primeng/button';
import { ButtonGroupModule } from 'primeng/buttongroup';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { catchError, firstValueFrom, of } from 'rxjs';
import { ToastService } from 'src/app/core/services/toast.service';
import { HostsApiService } from 'src/app/features/hosts/hosts-api.service';
import { IHostInfo } from 'src/app/features/hosts/hosts.interface';
import { SwarmApiService } from 'src/app/features/swarm/swarm-api.service';
import { ISwarmCluster } from 'src/app/features/swarm/swarm.interface';
import { HostStatusComponent } from '@shared/components/host-status/host-status.component';

@Component({
  selector: 'app-hosts-table',
  imports: [
    TableModule,
    ButtonModule,
    TranslatePipe,
    RouterLink,
    IconFieldModule,
    InputIconModule,
    ButtonGroupModule,
    InputTextModule,
    TagModule,
    HostStatusComponent,
    ToolbarModule,
  ],
  templateUrl: './hosts-table.component.html',
  styleUrl: './hosts-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostsTableComponent {
  private readonly hostsApiService = inject(HostsApiService);
  private readonly swarmApiService = inject(SwarmApiService);
  private readonly toastService = inject(ToastService);

  public readonly list = resource<IHostInfo[], unknown>({
    loader: () =>
      firstValueFrom(
        this.hostsApiService.list().pipe(
          catchError((error) => {
            this.toastService.error(error);
            return of([]);
          }),
        ),
      ),
    defaultValue: [],
  });

  public readonly clusters = resource<ISwarmCluster[], unknown>({
    loader: () =>
      firstValueFrom(
        this.swarmApiService.listClusters().pipe(
          catchError(() => of([])),
        ),
      ),
    defaultValue: [],
  });

  protected readonly clusterUpdates = computed(() => {
    const map = new Map<string, number>();
    for (const c of this.clusters.value()) {
      map.set(c.cluster_id, c.available_updates_count);
    }
    return map;
  });

  protected isSwarmHost(host: IHostInfo): boolean {
    return !!host.swarm_cluster_id;
  }

  protected clusterUpdateCount(host: IHostInfo): number {
    return host.swarm_cluster_id
      ? (this.clusterUpdates().get(host.swarm_cluster_id) ?? 0)
      : 0;
  }

  protected rowLink(host: IHostInfo): string {
    return host.host_type === 'swarm_agent'
      ? `/swarm/${host.swarm_cluster_id}/services`
      : `/hosts/${host.id}`;
  }

  public reloadAll(): void {
    this.list.reload();
    this.clusters.reload();
  }
}
