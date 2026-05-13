import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { repeat, takeWhile } from 'rxjs/operators';
import { BaseApiService } from '@shared/types/base-api.service';
import { ISwarmCluster, ISwarmService, ISwarmServicePatch } from './swarm.interface';
import { IHostInfo } from '../hosts/hosts.interface';
import { EActionStatus, IActionProgress } from '@shared/interfaces/progress.interface';

@Injectable({ providedIn: 'root' })
export class SwarmApiService extends BaseApiService<'/swarm'> {
  protected override readonly prefix = '/swarm';

  listClusters(): Observable<ISwarmCluster[]> {
    return this.httpClient.get<ISwarmCluster[]>(`${this.basePath}/clusters`);
  }

  listServices(clusterId: string): Observable<ISwarmService[]> {
    return this.httpClient.get<ISwarmService[]>(`${this.basePath}/${clusterId}/services`);
  }

  patchService(
    clusterId: string,
    serviceName: string,
    body: ISwarmServicePatch,
  ): Observable<ISwarmService> {
    return this.httpClient.patch<ISwarmService>(
      `${this.basePath}/${clusterId}/services/${serviceName}`,
      body,
    );
  }

  setClusterName(clusterId: string, name: string): Observable<IHostInfo[]> {
    return this.httpClient.put<IHostInfo[]>(
      `${this.basePath}/${clusterId}/name`,
      null,
      { params: { name } },
    );
  }

  clusterStatus(clusterId: string): Observable<{ id: number; name: string; ok: boolean; err?: string }[]> {
    return this.httpClient.get<{ id: number; name: string; ok: boolean; err?: string }[]>(
      `${this.basePath}/${clusterId}/status`,
    );
  }

  serviceLogs(clusterId: string, serviceName: string, tail = 100, timestamps = false): Observable<string> {
    return this.httpClient.get(`${this.basePath}/${clusterId}/services/${serviceName}/logs`, {
      params: { tail, timestamps },
      responseType: 'text',
    });
  }

  checkService(clusterId: string, serviceName: string): Observable<string> {
    return this.httpClient.post(
      `${this.basePath}/${clusterId}/services/${serviceName}/check`,
      null,
      { responseType: 'text' },
    );
  }

  updateService(clusterId: string, serviceName: string): Observable<string> {
    return this.httpClient.post(
      `${this.basePath}/${clusterId}/services/${serviceName}/update`,
      null,
      { responseType: 'text' },
    );
  }

  checkCluster(clusterId: string): Observable<string> {
    return this.httpClient.post(
      `${this.basePath}/${clusterId}/services/check`,
      null,
      { responseType: 'text' },
    );
  }

  updateCluster(clusterId: string): Observable<string> {
    return this.httpClient.post(
      `${this.basePath}/${clusterId}/services/update`,
      null,
      { responseType: 'text' },
    );
  }

  progress<T extends IActionProgress>(cacheId: string): Observable<T> {
    return this.httpClient.get<T>('/api/containers/progress', { params: { cache_id: cacheId } });
  }

  watchProgress<T extends IActionProgress>(cacheId: string): Observable<T> {
    return this.progress<T>(cacheId).pipe(
      repeat({ delay: 500 }),
      takeWhile(
        (res) => ![EActionStatus.DONE, EActionStatus.ERROR].includes(res?.status),
        true,
      ),
    );
  }
}
