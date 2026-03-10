/**
 * Discovery connector interface and associated data types.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export enum SyncAction {
  REGISTER = 'register',
  NOTIFY = 'notify',
  IGNORE = 'ignore',
}

export enum DeprecationAction {
  DEACTIVATE = 'deactivate',
  NOTIFY = 'notify',
  IGNORE = 'ignore',
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

export interface SyncResult {
  newModels: string[];
  deprecatedModels: string[];
  updatedModels: string[];
  errors: string[];
}

export interface SyncStatus {
  lastSync?: Date;
  nextSync?: Date;
  modelsSynced: number;
  status: string;
}

export interface HealthReport {
  providerId: string;
  available: boolean;
  latencyMs?: number;
  statusCode?: number;
  error?: string;
  availabilityScore: number;
  timestamp: Date;
}

export interface ProbeResult {
  providerId: string;
  success: boolean;
  latencyMs?: number;
  statusCode?: number;
  error?: string;
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface RegistrySync {
  sync(providers?: string[]): Promise<SyncResult>;
  getSyncStatus(): Promise<SyncStatus>;
}

export interface HealthMonitoring {
  probe(providerId: string): Promise<ProbeResult>;
  getHealthReport(providerId?: string): Promise<HealthReport[]>;
}

export interface DiscoveryConnector extends RegistrySync, HealthMonitoring {}
