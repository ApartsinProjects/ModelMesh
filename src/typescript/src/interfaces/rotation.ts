/**
 * Rotation policy interfaces and associated data types.
 *
 * Defines the three independently replaceable rotation policy components:
 * deactivation, recovery, and selection.
 */

import { CompletionRequest } from './provider';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export enum ModelStatus {
  ACTIVE = 'active',
  STANDBY = 'standby',
}

export enum DeactivationReason {
  ERROR_THRESHOLD = 'error_threshold',
  QUOTA_EXHAUSTED = 'quota_exhausted',
  BUDGET_EXCEEDED = 'budget_exceeded',
  TOKEN_LIMIT = 'token_limit',
  REQUEST_LIMIT = 'request_limit',
  MAINTENANCE_WINDOW = 'maintenance_window',
  MANUAL = 'manual',
}

export enum RecoveryTrigger {
  COOLDOWN_EXPIRED = 'cooldown_expired',
  QUOTA_RESET = 'quota_reset',
  PROBE_SUCCESS = 'probe_success',
  MANUAL = 'manual',
  STARTUP_PROBE = 'startup_probe',
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

export interface ModelState {
  modelId: string;
  status: ModelStatus;
  failureCount: number;
  errorRate: number;
  totalRequests: number;
  totalTokens: number;
  totalCost: number;
  cooldownUntil?: number;
  deactivationReason?: DeactivationReason;
  lastFailureAt?: number;
  lastSuccessAt?: number;
  providerId?: string;
}

export function createDefaultModelState(
  overrides: Partial<ModelState> & { modelId: string }
): ModelState {
  return {
    status: ModelStatus.ACTIVE,
    failureCount: 0,
    errorRate: 0.0,
    totalRequests: 0,
    totalTokens: 0,
    totalCost: 0.0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface DeactivationPolicy {
  shouldDeactivate(state: ModelState): boolean;
  getReason(state: ModelState): DeactivationReason | null;
}

export interface RecoveryPolicy {
  shouldRecover(state: ModelState): boolean;
  getRecoverySchedule(state: ModelState): number | null;
}

export interface SelectionStrategy {
  select(candidates: ModelState[], request: CompletionRequest): ModelState | null;
  score(state: ModelState, request: CompletionRequest): number;
}
