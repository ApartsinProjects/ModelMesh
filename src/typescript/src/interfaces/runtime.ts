/**
 * Runtime environment compatibility for connector classes.
 *
 * Every connector declares which runtime environments it supports
 * via a static RUNTIME property. This enables automated filtering
 * in browser.ts, clear error messages, and registry queries.
 */

export enum RuntimeEnvironment {
  /** Works only in Node.js (uses fs, http, child_process, etc.) */
  NODE_ONLY = 'node',
  /** Works only in browsers (uses window, localStorage, IndexedDB, etc.) */
  BROWSER_ONLY = 'browser',
  /** Works in both Node.js and browser environments. */
  UNIVERSAL = 'universal',
}
