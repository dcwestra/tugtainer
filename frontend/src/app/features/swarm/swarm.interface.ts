import { IHostInfo } from '../hosts/hosts.interface';

export interface ISwarmCluster {
  cluster_id: string;
  cluster_name: string;
  hosts: IHostInfo[];
  available_updates_count: number;
}

export interface ISwarmService {
  name: string;
  service_id: string;
  image: string | null;
  replicas: number | null;
  running_replicas: number | null;
  mode: string;
  update_status: string | null;
  // DB-tracked fields
  id: number | null;
  check_enabled: boolean | null;
  update_enabled: boolean | null;
  update_available: boolean | null;
  checked_at: string | null;
  updated_at: string | null;
}

export interface ISwarmServicePatch {
  check_enabled?: boolean;
  update_enabled?: boolean;
}
