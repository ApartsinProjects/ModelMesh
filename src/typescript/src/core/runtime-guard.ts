/**
 * Runtime environment detection and compatibility guard.
 *
 * Provides utilities for detecting the current runtime (Node.js vs browser)
 * and for throwing descriptive errors when a connector is used in an
 * incompatible environment.
 */

import { RuntimeEnvironment } from '../interfaces/runtime';

/**
 * Detect the current runtime environment.
 *
 * Uses the presence of `window` and `document` globals to distinguish
 * browser environments from Node.js.
 */
export function detectRuntime(): RuntimeEnvironment {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    return RuntimeEnvironment.BROWSER_ONLY;
  }
  return RuntimeEnvironment.NODE_ONLY;
}

/**
 * Assert that a connector is compatible with the current runtime.
 *
 * Throws a descriptive error if the connector's declared runtime does
 * not match the current environment. Universal connectors are always
 * compatible.
 *
 * @param connectorId - The connector's CONNECTOR_ID for error messages.
 * @param connectorRuntime - The connector's static RUNTIME value.
 * @throws Error if the runtime is incompatible.
 */
export function assertRuntimeCompatible(
  connectorId: string,
  connectorRuntime: RuntimeEnvironment,
): void {
  if (connectorRuntime === RuntimeEnvironment.UNIVERSAL) return;

  const current = detectRuntime();
  if (connectorRuntime === current) return;

  const envLabel =
    current === RuntimeEnvironment.NODE_ONLY ? 'Node.js' : 'browser';
  const reqLabel =
    connectorRuntime === RuntimeEnvironment.NODE_ONLY ? 'Node.js' : 'browser';
  throw new Error(
    `Connector "${connectorId}" requires ${reqLabel} but the current ` +
      `environment is ${envLabel}. Use a ` +
      `${connectorRuntime === RuntimeEnvironment.NODE_ONLY ? 'browser-compatible' : 'Node.js'} alternative.`,
  );
}
