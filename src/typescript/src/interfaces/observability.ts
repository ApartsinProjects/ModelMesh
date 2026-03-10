/**
 * Observability connector interface and associated data types.
 *
 * Defines the ObservabilityConnector interface for exporting routing
 * activity to external outputs. Multiple connectors can be active
 * simultaneously. The library pushes data at three levels: events for
 * state changes, logs for request/response data, and statistics for
 * aggregate metrics.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export enum EventType {
  MODEL_ACTIVATED = 'model_activated',
  MODEL_DEACTIVATED = 'model_deactivated',
  MODEL_ROTATED = 'model_rotated',
  PROVIDER_HEALTH_CHANGED = 'provider_health_changed',
  PROVIDER_DEACTIVATED = 'provider_deactivated',
  PROVIDER_RECOVERED = 'provider_recovered',
  POOL_MEMBERSHIP_CHANGED = 'pool_membership_changed',
  DISCOVERY_MODELS_UPDATED = 'discovery_models_updated',
}

export enum LogLevel {
  METADATA = 'metadata',
  SUMMARY = 'summary',
  FULL = 'full',
}

export enum Severity {
  DEBUG = 'debug',
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical',
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

export interface RoutingEvent {
  eventType: EventType;
  timestamp: Date;
  modelId?: string;
  providerId?: string;
  poolId?: string;
  metadata: Record<string, unknown>;
}

export interface RequestLogEntry {
  timestamp: Date;
  modelId: string;
  providerId: string;
  capability: string;
  deliveryMode: string;
  latencyMs: number;
  statusCode: number;
  tokensIn: number;
  tokensOut: number;
  cost?: number;
  error?: string;
}

export interface AggregateStats {
  requestsTotal: number;
  requestsSuccess: number;
  requestsFailed: number;
  tokensIn: number;
  tokensOut: number;
  costTotal: number;
  latencyAvg: number;
  latencyP95: number;
  downtimeTotal: number;
  rotationEvents: number;
}

export interface TraceEntry {
  severity: Severity;
  timestamp: Date;
  component: string;
  message: string;
  metadata: Record<string, unknown>;
  error?: string;
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface Events {
  emit(event: RoutingEvent): void;
}

export interface Logging {
  log(entry: RequestLogEntry): void;
}

export interface Statistics {
  flush(stats: Record<string, AggregateStats>): void;
}

export interface Tracing {
  trace(entry: TraceEntry): void;
}

export interface ObservabilityConnector extends Events, Logging, Statistics, Tracing {}
