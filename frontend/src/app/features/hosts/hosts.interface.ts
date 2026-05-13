export type EHostType = 'standalone' | 'swarm_agent';

export interface ICreateHost {
  name: string;
  enabled: boolean;
  prune: boolean;
  prune_all: boolean;
  url: string;
  secret: string;
  ssl: boolean;
  timeout: number;
  container_hc_timeout: number;
  host_type: EHostType;
  swarm_cluster_name: string | null;
}
export interface IHostInfo extends ICreateHost {
  id: number;
  available_updates_count: number;
  swarm_cluster_id: string | null;
}
export interface IHostStatus {
  id: number;
  ok: boolean;
  err: string;
}
