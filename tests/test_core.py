"""Tests for core components: CapabilityTree, EventEmitter, Pool, StateManager."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.core.capability_tree import CapabilityTree
from modelmesh.core.event_emitter import EventEmitter, EventType, Event
from modelmesh.core.pool import CapabilityPool, PoolModel
from modelmesh.core.state_manager import StateManager
from modelmesh.interfaces.rotation import ModelState, ModelStatus
from modelmesh.interfaces.provider import CompletionRequest


class TestCapabilityTree(unittest.TestCase):
    """Test the CapabilityTree class."""

    def setUp(self):
        self.tree = CapabilityTree()

    def test_register_and_resolve(self):
        self.tree.register("generation.text-generation.chat-completion")
        result = self.tree.resolve("generation.text-generation.chat-completion")
        self.assertEqual(result, ["generation.text-generation.chat-completion"])

    def test_resolve_parent_returns_leaves(self):
        self.tree.register("generation.text-generation.chat-completion")
        self.tree.register("generation.text-generation.code-generation")
        result = self.tree.resolve("generation.text-generation")
        self.assertIn("generation.text-generation.chat-completion", result)
        self.assertIn("generation.text-generation.code-generation", result)
        self.assertEqual(len(result), 2)

    def test_resolve_root_returns_all_leaves(self):
        self.tree.register("generation.text-generation.chat-completion")
        self.tree.register("generation.image.text-to-image")
        result = self.tree.resolve("generation")
        self.assertIn("generation.text-generation.chat-completion", result)
        self.assertIn("generation.image.text-to-image", result)

    def test_contains(self):
        self.tree.register("generation.text-generation.chat-completion")
        self.assertTrue(self.tree.contains("generation"))
        self.assertTrue(self.tree.contains("generation.text-generation"))
        self.assertTrue(
            self.tree.contains("generation.text-generation.chat-completion")
        )
        self.assertFalse(self.tree.contains("unknown"))

    def test_all_paths(self):
        self.tree.register("generation.text-generation.chat-completion")
        paths = self.tree.all_paths()
        self.assertIn("generation", paths)
        self.assertIn("generation.text-generation", paths)
        self.assertIn("generation.text-generation.chat-completion", paths)

    def test_all_leaves(self):
        self.tree.register("generation.text-generation.chat-completion")
        self.tree.register("generation.image.text-to-image")
        leaves = self.tree.all_leaves()
        self.assertEqual(len(leaves), 2)
        self.assertIn("generation.text-generation.chat-completion", leaves)
        self.assertIn("generation.image.text-to-image", leaves)

    def test_resolve_unknown(self):
        result = self.tree.resolve("nonexistent.capability")
        self.assertEqual(result, [])

    def test_register_empty_raises(self):
        with self.assertRaises(ValueError):
            self.tree.register("")

    def test_register_idempotent(self):
        self.tree.register("generation.text-generation.chat-completion")
        self.tree.register("generation.text-generation.chat-completion")
        result = self.tree.resolve("generation.text-generation.chat-completion")
        self.assertEqual(len(result), 1)


class TestEventEmitter(unittest.TestCase):
    """Test the EventEmitter class."""

    def setUp(self):
        self.emitter = EventEmitter()

    def test_emit_and_receive(self):
        received = []
        self.emitter.on(EventType.REQUEST_SUCCESS, lambda e: received.append(e))
        self.emitter.emit(EventType.REQUEST_SUCCESS, model_id="test")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, EventType.REQUEST_SUCCESS)
        self.assertEqual(received[0].data["model_id"], "test")

    def test_multiple_handlers(self):
        count = {"a": 0, "b": 0}
        self.emitter.on(EventType.MODEL_ROTATED, lambda e: count.__setitem__("a", count["a"] + 1))
        self.emitter.on(EventType.MODEL_ROTATED, lambda e: count.__setitem__("b", count["b"] + 1))
        self.emitter.emit(EventType.MODEL_ROTATED)
        self.assertEqual(count["a"], 1)
        self.assertEqual(count["b"], 1)

    def test_wildcard_handler(self):
        received = []
        self.emitter.on(None, lambda e: received.append(e))
        self.emitter.emit(EventType.REQUEST_SUCCESS)
        self.emitter.emit(EventType.REQUEST_FAILURE)
        self.assertEqual(len(received), 2)

    def test_off_removes_handler(self):
        received = []
        handler = lambda e: received.append(e)
        self.emitter.on(EventType.MODEL_ROTATED, handler)
        self.emitter.emit(EventType.MODEL_ROTATED)
        self.assertEqual(len(received), 1)

        self.emitter.off(EventType.MODEL_ROTATED, handler)
        self.emitter.emit(EventType.MODEL_ROTATED)
        self.assertEqual(len(received), 1)  # Should not have increased

    def test_clear(self):
        received = []
        self.emitter.on(EventType.REQUEST_SUCCESS, lambda e: received.append(e))
        self.emitter.clear()
        self.emitter.emit(EventType.REQUEST_SUCCESS)
        self.assertEqual(len(received), 0)

    def test_event_timestamp(self):
        received = []
        self.emitter.on(EventType.REQUEST_SUCCESS, lambda e: received.append(e))
        self.emitter.emit(EventType.REQUEST_SUCCESS)
        self.assertIsInstance(received[0].timestamp, float)
        self.assertGreater(received[0].timestamp, 0)

    def test_no_handler_does_not_error(self):
        # Emitting with no handlers should not raise
        self.emitter.emit(EventType.POOL_EXHAUSTED, pool_id="test")


class TestPoolModel(unittest.TestCase):
    """Test the PoolModel dataclass."""

    def test_to_model_state(self):
        model = PoolModel(
            model_id="openai.gpt-4o",
            real_model_id="gpt-4o",
            provider_id="openai.llm.v1",
            failure_count=2,
            total_requests=10,
        )
        state = model.to_model_state()
        self.assertIsInstance(state, ModelState)
        self.assertEqual(state.model_id, "openai.gpt-4o")
        self.assertEqual(state.failure_count, 2)
        self.assertEqual(state.total_requests, 10)
        self.assertEqual(state.status, ModelStatus.ACTIVE)

    def test_defaults(self):
        model = PoolModel(
            model_id="test.model",
            real_model_id="model",
            provider_id="test.v1",
        )
        self.assertEqual(model.status, ModelStatus.ACTIVE)
        self.assertEqual(model.failure_count, 0)
        self.assertEqual(model.total_requests, 0)
        self.assertEqual(model.total_tokens, 0)
        self.assertIsNone(model.last_failure_at)
        self.assertIsNone(model.last_success_at)


class TestCapabilityPool(unittest.TestCase):
    """Test the CapabilityPool class."""

    def setUp(self):
        self.pool = CapabilityPool(
            "chat-completion",
            {"capability": "generation.text-generation.chat-completion"},
        )
        self.model_a = PoolModel(
            model_id="openai.gpt-4o",
            real_model_id="gpt-4o",
            provider_id="openai.llm.v1",
        )
        self.model_b = PoolModel(
            model_id="anthropic.claude-sonnet",
            real_model_id="claude-sonnet",
            provider_id="anthropic.claude.v1",
        )

    def test_add_model(self):
        self.pool.add_model(self.model_a)
        self.assertEqual(len(self.pool.models), 1)
        self.assertEqual(self.pool.models[0].model_id, "openai.gpt-4o")

    def test_add_duplicate_raises(self):
        self.pool.add_model(self.model_a)
        with self.assertRaises(ValueError):
            self.pool.add_model(self.model_a)

    def test_remove_model(self):
        self.pool.add_model(self.model_a)
        self.pool.remove_model("openai.gpt-4o")
        self.assertEqual(len(self.pool.models), 0)

    def test_remove_missing_raises(self):
        with self.assertRaises(KeyError):
            self.pool.remove_model("nonexistent")

    def test_select_returns_active(self):
        self.pool.add_model(self.model_a)
        self.pool.add_model(self.model_b)
        request = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        selected = self.pool.select(request)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.status, ModelStatus.ACTIVE)

    def test_select_returns_none_when_all_standby(self):
        self.pool.add_model(self.model_a)
        self.model_a.status = ModelStatus.STANDBY
        request = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        selected = self.pool.select(request)
        self.assertIsNone(selected)

    def test_record_success_resets_failures(self):
        self.pool.add_model(self.model_a)
        self.model_a.failure_count = 2
        self.pool.record_success("openai.gpt-4o")
        self.assertEqual(self.model_a.failure_count, 0)
        self.assertEqual(self.model_a.total_requests, 1)
        self.assertIsNotNone(self.model_a.last_success_at)

    def test_record_failure_increments(self):
        self.pool.add_model(self.model_a)
        self.pool.record_failure("openai.gpt-4o", RuntimeError("test"))
        self.assertEqual(self.model_a.failure_count, 1)
        self.assertEqual(self.model_a.total_requests, 1)
        self.assertIsNotNone(self.model_a.last_failure_at)

    def test_deactivation_on_threshold(self):
        pool = CapabilityPool(
            "test",
            {"capability": "test", "failure_threshold": 2},
        )
        model = PoolModel(
            model_id="test.model",
            real_model_id="model",
            provider_id="test.v1",
        )
        pool.add_model(model)
        pool.record_failure("test.model", RuntimeError("err"))
        self.assertEqual(model.status, ModelStatus.ACTIVE)
        pool.record_failure("test.model", RuntimeError("err"))
        self.assertEqual(model.status, ModelStatus.STANDBY)

    def test_rotate(self):
        self.pool.add_model(self.model_a)
        self.pool.add_model(self.model_b)
        result = self.pool.rotate()
        self.assertIsNotNone(result)
        self.assertEqual(self.model_a.status, ModelStatus.STANDBY)
        self.assertEqual(result.model_id, "anthropic.claude-sonnet")

    def test_rotate_single_model(self):
        self.pool.add_model(self.model_a)
        result = self.pool.rotate()
        self.assertIsNone(result)
        self.assertEqual(self.model_a.status, ModelStatus.STANDBY)

    def test_reactivate(self):
        self.pool.add_model(self.model_a)
        self.model_a.status = ModelStatus.STANDBY
        self.model_a.failure_count = 5
        self.pool.reactivate("openai.gpt-4o")
        self.assertEqual(self.model_a.status, ModelStatus.ACTIVE)
        self.assertEqual(self.model_a.failure_count, 0)

    def test_reactivate_missing_raises(self):
        with self.assertRaises(KeyError):
            self.pool.reactivate("nonexistent")

    def test_status(self):
        self.pool.add_model(self.model_a)
        self.pool.add_model(self.model_b)
        self.model_b.status = ModelStatus.STANDBY
        status = self.pool.status()
        self.assertEqual(status["active"], 1)
        self.assertEqual(status["standby"], 1)
        self.assertEqual(status["total"], 2)
        self.assertEqual(status["current_model"], "openai.gpt-4o")

    def test_pool_id(self):
        self.assertEqual(self.pool.pool_id, "chat-completion")

    def test_active_models_property(self):
        self.pool.add_model(self.model_a)
        self.pool.add_model(self.model_b)
        self.model_b.status = ModelStatus.STANDBY
        active = self.pool.active_models
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].model_id, "openai.gpt-4o")

    def test_standby_models_property(self):
        self.pool.add_model(self.model_a)
        self.pool.add_model(self.model_b)
        self.model_b.status = ModelStatus.STANDBY
        standby = self.pool.standby_models
        self.assertEqual(len(standby), 1)
        self.assertEqual(standby[0].model_id, "anthropic.claude-sonnet")

    # -- WITH OBSERVABILITY --

    def test_failure_emits_warning_trace(self):
        """Verify that recording a failure emits a WARNING trace via observability."""
        from modelmesh.cdk.specialized.file_observability import (
            FileObservability,
            FileObservabilityConfig,
        )

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(file_path=tmp, min_severity="debug")
            )
            pool = CapabilityPool(
                "test-pool",
                {"capability": "test", "failure_threshold": 5},
                observability=obs,
            )
            model = PoolModel(
                model_id="test.model",
                real_model_id="model",
                provider_id="test.v1",
            )
            pool.add_model(model)
            pool.record_failure("test.model", RuntimeError("test error"))
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Find the warning trace for the failure
            warning_lines = [
                l
                for l in lines
                if '"severity": "warning"' in l and "Failure recorded" in l
            ]
            self.assertGreater(len(warning_lines), 0, "Expected a WARNING trace for failure")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_deactivation_emits_error_trace(self):
        """Verify that deactivation emits an ERROR trace via observability."""
        from modelmesh.cdk.specialized.file_observability import (
            FileObservability,
            FileObservabilityConfig,
        )

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(file_path=tmp, min_severity="debug")
            )
            pool = CapabilityPool(
                "test-pool",
                {"capability": "test", "failure_threshold": 2},
                observability=obs,
            )
            model = PoolModel(
                model_id="test.model",
                real_model_id="model",
                provider_id="test.v1",
            )
            pool.add_model(model)
            pool.record_failure("test.model", RuntimeError("err1"))
            pool.record_failure("test.model", RuntimeError("err2"))
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            error_lines = [
                l
                for l in lines
                if '"severity": "error"' in l and "deactivated" in l
            ]
            self.assertGreater(
                len(error_lines), 0, "Expected an ERROR trace for deactivation"
            )
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class TestStateManager(unittest.TestCase):
    """Test the StateManager class."""

    def setUp(self):
        self.sm = StateManager()

    def test_get_or_create(self):
        state = self.sm.get_or_create("openai.gpt-4o")
        self.assertIsInstance(state, ModelState)
        self.assertEqual(state.model_id, "openai.gpt-4o")
        self.assertEqual(state.status, ModelStatus.ACTIVE)

    def test_get_or_create_returns_same_instance(self):
        s1 = self.sm.get_or_create("model-a")
        s2 = self.sm.get_or_create("model-a")
        self.assertIs(s1, s2)

    def test_get_nonexistent(self):
        result = self.sm.get("nonexistent")
        self.assertIsNone(result)

    def test_record_success(self):
        self.sm.record_success("model-a", tokens=100)
        state = self.sm.get("model-a")
        self.assertIsNotNone(state)
        self.assertEqual(state.failure_count, 0)
        self.assertEqual(state.total_requests, 1)
        self.assertEqual(state.total_tokens, 100)
        self.assertIsNotNone(state.last_success_at)

    def test_record_failure(self):
        self.sm.record_failure("model-a")
        state = self.sm.get("model-a")
        self.assertIsNotNone(state)
        self.assertEqual(state.failure_count, 1)
        self.assertEqual(state.total_requests, 1)
        self.assertIsNotNone(state.last_failure_at)

    def test_record_failure_increments_error_rate(self):
        self.sm.record_failure("model-a")
        state = self.sm.get("model-a")
        self.assertEqual(state.error_rate, 1.0)
        self.sm.record_success("model-a")
        # After 1 fail + 1 success: error_rate should be 0.0 because
        # record_success resets failure_count and error_rate
        self.assertEqual(state.error_rate, 0.0)

    def test_activate_deactivate(self):
        self.sm.get_or_create("model-a")
        self.sm.deactivate("model-a")
        state = self.sm.get("model-a")
        self.assertEqual(state.status, ModelStatus.STANDBY)

        self.sm.activate("model-a")
        self.assertEqual(state.status, ModelStatus.ACTIVE)
        self.assertEqual(state.failure_count, 0)

    def test_active_standby_models(self):
        self.sm.get_or_create("model-a")
        self.sm.get_or_create("model-b")
        self.sm.deactivate("model-b")

        active = self.sm.active_models()
        standby = self.sm.standby_models()
        self.assertIn("model-a", active)
        self.assertNotIn("model-b", active)
        self.assertIn("model-b", standby)

    def test_reset(self):
        self.sm.record_failure("model-a")
        self.sm.record_failure("model-a")
        self.sm.reset("model-a")
        state = self.sm.get("model-a")
        self.assertEqual(state.failure_count, 0)
        self.assertEqual(state.total_requests, 0)
        self.assertEqual(state.status, ModelStatus.ACTIVE)

    def test_clear(self):
        self.sm.get_or_create("model-a")
        self.sm.get_or_create("model-b")
        self.sm.clear()
        self.assertEqual(len(self.sm.all_states()), 0)

    def test_is_dirty(self):
        self.assertFalse(self.sm.is_dirty)
        self.sm.record_success("model-a")
        self.assertTrue(self.sm.is_dirty)
        self.sm.mark_clean()
        self.assertFalse(self.sm.is_dirty)


if __name__ == "__main__":
    unittest.main()
