/**
 * Tests for EventEmitter.
 */
import { EventEmitter, EventType } from '@/core/event-emitter';
import type { Event } from '@/core/event-emitter';

describe('EventEmitter', () => {
  let emitter: EventEmitter;

  beforeEach(() => {
    emitter = new EventEmitter();
  });

  it('should register and fire handlers', () => {
    const events: Event[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (e) => events.push(e));
    emitter.emit(EventType.REQUEST_SUCCESS, { msg: 'hello' });
    expect(events.length).toBe(1);
    expect(events[0].data.msg).toBe('hello');
  });

  it('should support multiple handlers on same event', () => {
    const events1: Event[] = [];
    const events2: Event[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (e) => events1.push(e));
    emitter.on(EventType.REQUEST_SUCCESS, (e) => events2.push(e));
    emitter.emit(EventType.REQUEST_SUCCESS, { msg: 'hello' });
    expect(events1.length).toBe(1);
    expect(events2.length).toBe(1);
  });

  it('should not fire handlers for different event types', () => {
    const eventsA: Event[] = [];
    const eventsB: Event[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (e) => eventsA.push(e));
    emitter.on(EventType.REQUEST_FAILURE, (e) => eventsB.push(e));
    emitter.emit(EventType.REQUEST_SUCCESS, { val: 'only-a' });
    expect(eventsA.length).toBe(1);
    expect(eventsB.length).toBe(0);
  });

  it('should unregister a handler with off()', () => {
    const events: Event[] = [];
    const handler = (e: Event) => events.push(e);
    emitter.on(EventType.REQUEST_SUCCESS, handler);
    emitter.off(EventType.REQUEST_SUCCESS, handler);
    emitter.emit(EventType.REQUEST_SUCCESS, { msg: 'hello' });
    expect(events.length).toBe(0);
  });

  it('should not throw when emitting with no listeners', () => {
    expect(() => emitter.emit(EventType.REQUEST_SUCCESS, { msg: 'hello' })).not.toThrow();
  });

  it('should clear all handlers', () => {
    const events: Event[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (e) => events.push(e));
    emitter.on(EventType.REQUEST_FAILURE, (e) => events.push(e));
    emitter.clear();
    emitter.emit(EventType.REQUEST_SUCCESS, { msg: 'hello' });
    emitter.emit(EventType.REQUEST_FAILURE, { msg: 'world' });
    expect(events.length).toBe(0);
  });

  it('should handle multiple emissions', () => {
    const events: Event[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (e) => events.push(e));
    emitter.emit(EventType.REQUEST_SUCCESS, { n: 1 });
    emitter.emit(EventType.REQUEST_SUCCESS, { n: 2 });
    emitter.emit(EventType.REQUEST_SUCCESS, { n: 3 });
    expect(events.length).toBe(3);
  });

  it('should support wildcard (null) listeners', () => {
    const events: Event[] = [];
    emitter.on(null, (e) => events.push(e));
    emitter.emit(EventType.REQUEST_SUCCESS, { n: 1 });
    emitter.emit(EventType.MODEL_ROTATED, { n: 2 });
    expect(events.length).toBe(2);
  });

  it('should include timestamp in emitted events', () => {
    const events: Event[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (e) => events.push(e));
    emitter.emit(EventType.REQUEST_SUCCESS, {});
    expect(events[0].timestamp).toBeGreaterThan(0);
  });

  it('should include event type in emitted events', () => {
    const events: Event[] = [];
    emitter.on(EventType.MODEL_ROTATED, (e) => events.push(e));
    emitter.emit(EventType.MODEL_ROTATED, { model: 'gpt-4o' });
    expect(events[0].type).toBe(EventType.MODEL_ROTATED);
  });
});
