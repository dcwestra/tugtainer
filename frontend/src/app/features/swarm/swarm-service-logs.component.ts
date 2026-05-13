import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslatePipe } from '@ngx-translate/core';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { IftaLabelModule } from 'primeng/iftalabel';
import { InputNumberModule } from 'primeng/inputnumber';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { catchError, firstValueFrom, of } from 'rxjs';
import { ToastService } from 'src/app/core/services/toast.service';
import { BooleanFieldComponent } from '@shared/components/boolean-field/boolean-field.component';
import { SwarmApiService } from './swarm-api.service';
import { ISwarmService } from './swarm.interface';

@Component({
  selector: 'app-swarm-service-logs',
  imports: [
    DialogModule,
    ButtonModule,
    InputNumberModule,
    IftaLabelModule,
    TranslatePipe,
    FormsModule,
    ToggleSwitchModule,
    BooleanFieldComponent,
  ],
  templateUrl: './swarm-service-logs.component.html',
  styleUrl: './swarm-service-logs.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SwarmServiceLogsComponent {
  private readonly swarmApiService = inject(SwarmApiService);
  private readonly toastService = inject(ToastService);

  public readonly clusterId = input.required<string>();

  protected readonly visible = signal(false);
  protected readonly service = signal<ISwarmService | null>(null);
  protected tail = signal(100);
  protected timestamps = signal(false);

  protected readonly logs = resource<string | null, { clusterId: string; serviceName: string | undefined; tail: number; timestamps: boolean }>({
    params: () => ({
      clusterId: this.clusterId(),
      serviceName: this.service()?.name,
      tail: this.tail(),
      timestamps: this.timestamps(),
    }),
    loader: ({ params }) => {
      if (!params.serviceName) return Promise.resolve(null);
      return firstValueFrom(
        this.swarmApiService.serviceLogs(params.clusterId, params.serviceName, params.tail, params.timestamps).pipe(
          catchError((error) => {
            this.toastService.error(error);
            return of(null);
          }),
        ),
      );
    },
    defaultValue: null,
  });

  open(svc: ISwarmService): void {
    this.service.set(svc);
    this.visible.set(true);
  }

  protected close(): void {
    this.visible.set(false);
    this.service.set(null);
  }
}
