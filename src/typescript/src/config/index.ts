/**
 * Configuration module barrel export.
 */

export { MeshConfig } from './mesh-config';
export {
  detectProviders,
  PROVIDER_REGISTRY,
} from './auto-detect';
export type {
  ProviderRegistryEntry,
  DetectedProvider,
} from './auto-detect';
