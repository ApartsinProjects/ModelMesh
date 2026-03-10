/**
 * Tests for ProxyServer and related interfaces.
 */
import type { ServerStatus } from '@/proxy/server';

// ---------------------------------------------------------------------------
// ServerStatus interface -- snake_case field names for REST API
// ---------------------------------------------------------------------------

describe('ServerStatus interface', () => {
  it('should use snake_case field names for REST API compatibility', () => {
    // Construct a ServerStatus object to verify the interface shape
    // uses snake_case as required for the REST API.
    const status: ServerStatus = {
      running: true,
      host: '0.0.0.0',
      port: 8080,
      uptime_seconds: 123.45,
      active_connections: 3,
      total_requests: 42,
    };

    // Verify all snake_case fields exist and have correct values
    expect(status.uptime_seconds).toBe(123.45);
    expect(status.active_connections).toBe(3);
    expect(status.total_requests).toBe(42);
    expect(status.running).toBe(true);
    expect(status.host).toBe('0.0.0.0');
    expect(status.port).toBe(8080);

    // Verify the object shape has exactly the expected keys
    const keys = Object.keys(status).sort();
    expect(keys).toEqual([
      'active_connections',
      'host',
      'port',
      'running',
      'total_requests',
      'uptime_seconds',
    ]);
  });
});
