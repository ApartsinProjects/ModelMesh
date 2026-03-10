/**
 * Core system components.
 *
 * This package contains the central orchestration objects: the ModelMesh
 * facade, the request Router, CapabilityPools, the CapabilityTree, the
 * StateManager, and the EventEmitter.
 */

export { CapabilityNode, CapabilityTree } from "./capability-tree";
export {
  EventEmitter,
  EventType,
  type Event,
  type EventHandler,
} from "./event-emitter";
export { ModelMesh } from "./mesh";
export {
  CapabilityPool,
  createPoolModel,
  poolModelToModelState,
  type PoolModel,
} from "./pool";
export { NoActiveModelError, Router } from "./router";
export { StateManager } from "./state-manager";
