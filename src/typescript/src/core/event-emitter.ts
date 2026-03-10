/**
 * Event emitter for publishing routing events to observability connectors.
 *
 * Provides a simple publish/subscribe mechanism for internal events such as
 * routing decisions, model rotations, and provider health changes. Multiple
 * observability connectors can subscribe simultaneously.
 */

/** Types of events emitted by the system. */
export enum EventType {
  REQUEST_ROUTED = "request.routed",
  REQUEST_SUCCESS = "request.success",
  REQUEST_FAILURE = "request.failure",
  MODEL_DEACTIVATED = "model.deactivated",
  MODEL_REACTIVATED = "model.reactivated",
  MODEL_ROTATED = "model.rotated",
  PROVIDER_ERROR = "provider.error",
  POOL_EXHAUSTED = "pool.exhausted",
  RETRY_ATTEMPTED = "retry.attempted",
}

/**
 * An event emitted by the system.
 *
 * @property type - The event type.
 * @property timestamp - Unix timestamp when the event occurred.
 * @property data - Arbitrary event payload (varies by event type).
 */
export interface Event {
  type: EventType;
  timestamp: number;
  data: Record<string, unknown>;
}

/** Type alias for event handler callbacks. */
export type EventHandler = (event: Event) => void;

/**
 * Publish/subscribe event bus for system observability.
 *
 * Handlers subscribe to specific event types and receive events as they
 * are emitted. A wildcard subscription (null event type) receives
 * all events.
 *
 * Example:
 *
 *   const emitter = new EventEmitter();
 *
 *   function onRotation(event: Event) {
 *     console.log("Model rotated:", event.data);
 *   }
 *
 *   emitter.on(EventType.MODEL_ROTATED, onRotation);
 *   emitter.emit(EventType.MODEL_ROTATED, { modelId: "openai.gpt-4o" });
 */
export class EventEmitter {
  private _handlers: Map<EventType | null, EventHandler[]> = new Map();

  /**
   * Subscribe a handler to an event type.
   *
   * @param eventType - The event type to listen for, or null to receive all events.
   * @param handler - Callable that accepts an Event.
   */
  on(eventType: EventType | null, handler: EventHandler): void {
    if (!this._handlers.has(eventType)) {
      this._handlers.set(eventType, []);
    }
    this._handlers.get(eventType)!.push(handler);
  }

  /**
   * Unsubscribe a handler from an event type.
   *
   * @param eventType - The event type to unsubscribe from.
   * @param handler - The handler to remove.
   */
  off(eventType: EventType | null, handler: EventHandler): void {
    const handlers = this._handlers.get(eventType);
    if (handlers) {
      const idx = handlers.indexOf(handler);
      if (idx !== -1) {
        handlers.splice(idx, 1);
      }
    }
  }

  /**
   * Emit an event to all subscribed handlers.
   *
   * Constructs an Event with the given type and data, then
   * dispatches to type-specific handlers and wildcard handlers.
   *
   * @param eventType - The type of event to emit.
   * @param data - Key-value pairs forming the event payload.
   */
  emit(eventType: EventType, data: Record<string, unknown> = {}): void {
    const event: Event = {
      type: eventType,
      timestamp: Date.now() / 1000,
      data,
    };

    // Dispatch to type-specific handlers
    const typeHandlers = this._handlers.get(eventType);
    if (typeHandlers) {
      for (const handler of typeHandlers) {
        handler(event);
      }
    }

    // Dispatch to wildcard handlers
    const wildcardHandlers = this._handlers.get(null);
    if (wildcardHandlers) {
      for (const handler of wildcardHandlers) {
        handler(event);
      }
    }
  }

  /** Remove all registered handlers. */
  clear(): void {
    this._handlers.clear();
  }
}
