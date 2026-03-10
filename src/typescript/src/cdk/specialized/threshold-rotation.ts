/**
 * Threshold-based rotation policy.
 *
 * Pre-configured rotation policy that deactivates models after a
 * failure count threshold, recovers after a cooldown period, and
 * selects by lowest error rate. This is an alias for BaseRotationPolicy
 * with a specialized config interface for clarity.
 *
 * Matches Python's ThresholdRotationPolicy from
 * modelmesh.cdk.specialized.threshold_rotation.
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import {
  BaseRotationPolicy,
  BaseRotationConfig,
} from '../base-rotation';

/**
 * Configuration for ThresholdRotationPolicy.
 *
 * Uses the same fields as BaseRotationConfig but provides a
 * named config type for documentation and discovery purposes.
 */
export interface ThresholdRotationConfig extends BaseRotationConfig {
  /**
   * Number of consecutive failures before deactivation.
   * @default 3
   */
  failureCountThreshold?: number;
}

/**
 * Threshold-based rotation policy.
 *
 * Deactivates models after exceeding a failure count or error rate
 * threshold, recovers after a cooldown period, and selects the model
 * with the lowest error rate.
 *
 * @example
 * const policy = new ThresholdRotationPolicy({
 *   failureCountThreshold: 5,
 *   cooldownSeconds: 120,
 * });
 *
 * const state = mockModelSnapshot({ failureCount: 6 });
 * console.log(policy.shouldDeactivate(state)); // true
 */
export class ThresholdRotationPolicy extends BaseRotationPolicy {
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  constructor(config?: ThresholdRotationConfig) {
    // Map failureCountThreshold to failureThreshold for base class
    const resolvedConfig: BaseRotationConfig = {
      ...config,
    };
    if (config?.failureCountThreshold !== undefined) {
      resolvedConfig.failureThreshold = config.failureCountThreshold;
    }
    super(resolvedConfig);
  }
}
