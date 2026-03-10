"""Tests for interface data types and abstract base classes."""
import sys
import os
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.interfaces.observability import (
    Severity,
    TraceEntry,
    ObservabilityConnector,
    RoutingEvent,
    RequestLogEntry,
    AggregateStats,
    EventType as ObsEventType,
    LogLevel,
)
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    CompletionChoice,
    ChatMessage,
    ModelInfo,
    ModelPricing,
    TokenUsage,
    ErrorClassification,
    QuotaStatus,
    RateLimitStatus,
    ProviderConnector,
    AudioSpeechRequest,
    AudioSpeechResponse,
    AudioTranscriptionRequest,
    AudioTranscriptionResponse,
)
from modelmesh.interfaces.rotation import (
    ModelState,
    ModelStatus,
    DeactivationReason,
    RecoveryTrigger,
    DeactivationPolicy,
    RecoveryPolicy,
    SelectionStrategy,
)


class TestSeverityEnum(unittest.TestCase):
    """Test the Severity enum values and ordering."""

    def test_severity_values(self):
        self.assertEqual(Severity.DEBUG.value, "debug")
        self.assertEqual(Severity.INFO.value, "info")
        self.assertEqual(Severity.WARNING.value, "warning")
        self.assertEqual(Severity.ERROR.value, "error")
        self.assertEqual(Severity.CRITICAL.value, "critical")

    def test_severity_ordering(self):
        from modelmesh.cdk.base_observability import BaseObservability

        order = BaseObservability._SEVERITY_ORDER
        self.assertLess(order[Severity.DEBUG], order[Severity.INFO])
        self.assertLess(order[Severity.INFO], order[Severity.WARNING])
        self.assertLess(order[Severity.WARNING], order[Severity.ERROR])
        self.assertLess(order[Severity.ERROR], order[Severity.CRITICAL])

    def test_severity_from_string(self):
        self.assertEqual(Severity("debug"), Severity.DEBUG)
        self.assertEqual(Severity("info"), Severity.INFO)
        self.assertEqual(Severity("warning"), Severity.WARNING)
        self.assertEqual(Severity("error"), Severity.ERROR)
        self.assertEqual(Severity("critical"), Severity.CRITICAL)

    def test_severity_count(self):
        self.assertEqual(len(Severity), 5)


class TestTraceEntry(unittest.TestCase):
    """Test the TraceEntry dataclass."""

    def test_creation(self):
        now = datetime.now()
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=now,
            component="router",
            message="Test message",
        )
        self.assertEqual(entry.severity, Severity.INFO)
        self.assertEqual(entry.timestamp, now)
        self.assertEqual(entry.component, "router")
        self.assertEqual(entry.message, "Test message")

    def test_defaults(self):
        now = datetime.now()
        entry = TraceEntry(
            severity=Severity.DEBUG,
            timestamp=now,
            component="pool",
            message="debug msg",
        )
        self.assertIsNone(entry.error)
        # metadata should be set to {} by __post_init__
        self.assertEqual(entry.metadata, {})

    def test_metadata_default_dict(self):
        now = datetime.now()
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=now,
            component="test",
            message="msg",
        )
        # __post_init__ converts None -> {}
        self.assertIsInstance(entry.metadata, dict)
        self.assertEqual(entry.metadata, {})

    def test_metadata_explicit(self):
        now = datetime.now()
        meta = {"key": "value"}
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=now,
            component="test",
            message="msg",
            metadata=meta,
        )
        self.assertEqual(entry.metadata, {"key": "value"})

    def test_error_field(self):
        now = datetime.now()
        entry = TraceEntry(
            severity=Severity.ERROR,
            timestamp=now,
            component="router",
            message="failure",
            error="Connection refused",
        )
        self.assertEqual(entry.error, "Connection refused")


class TestCompletionRequest(unittest.TestCase):
    """Test the CompletionRequest dataclass."""

    def test_creation(self):
        req = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
        )
        self.assertEqual(req.model, "test-model")
        self.assertEqual(len(req.messages), 1)

    def test_defaults(self):
        req = CompletionRequest(
            model="test-model",
            messages=[],
        )
        self.assertEqual(req.temperature, 1.0)
        self.assertIsNone(req.max_tokens)
        self.assertFalse(req.stream)
        self.assertIsNone(req.tools)
        self.assertEqual(req.top_p, 1.0)
        self.assertIsNone(req.stop)

    def test_with_all_fields(self):
        req = CompletionRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.5,
            max_tokens=100,
            stream=True,
            tools=[{"type": "function"}],
            top_p=0.9,
            stop=["END"],
        )
        self.assertEqual(req.temperature, 0.5)
        self.assertEqual(req.max_tokens, 100)
        self.assertTrue(req.stream)
        self.assertEqual(len(req.tools), 1)
        self.assertEqual(req.top_p, 0.9)
        self.assertEqual(req.stop, ["END"])


class TestCompletionResponse(unittest.TestCase):
    """Test the CompletionResponse dataclass."""

    def test_creation(self):
        resp = CompletionResponse(
            id="chatcmpl-123",
            model="gpt-4o",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello!"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=10, completion_tokens=5, total_tokens=15
            ),
        )
        self.assertEqual(resp.id, "chatcmpl-123")
        self.assertEqual(resp.model, "gpt-4o")
        self.assertEqual(len(resp.choices), 1)
        self.assertEqual(resp.choices[0].message.content, "Hello!")
        self.assertEqual(resp.usage.total_tokens, 15)

    def test_defaults(self):
        resp = CompletionResponse()
        self.assertEqual(resp.id, "")
        self.assertEqual(resp.model, "")
        self.assertEqual(resp.choices, [])
        self.assertEqual(resp.usage.total_tokens, 0)
        self.assertEqual(resp.created, 0)
        self.assertEqual(resp.object, "chat.completion")


class TestModelInfo(unittest.TestCase):
    """Test the ModelInfo dataclass."""

    def test_creation(self):
        info = ModelInfo(
            id="openai.gpt-4o",
            name="GPT-4o",
            capabilities=["chat", "tools"],
            context_window=128000,
            max_output_tokens=16384,
        )
        self.assertEqual(info.id, "openai.gpt-4o")
        self.assertEqual(info.name, "GPT-4o")
        self.assertEqual(info.capabilities, ["chat", "tools"])
        self.assertEqual(info.context_window, 128000)

    def test_defaults(self):
        info = ModelInfo(id="test", name="Test")
        self.assertEqual(info.capabilities, [])
        self.assertEqual(info.context_window, 0)
        self.assertEqual(info.max_output_tokens, 0)
        self.assertIsNone(info.pricing)
        self.assertEqual(info.features, {})
        self.assertEqual(info.delivery, {"synchronous": True})

    def test_with_pricing(self):
        pricing = ModelPricing(
            input_per_1k_tokens=0.01,
            output_per_1k_tokens=0.03,
        )
        info = ModelInfo(id="test", name="Test", pricing=pricing)
        self.assertIsNotNone(info.pricing)
        self.assertEqual(info.pricing.input_per_1k_tokens, 0.01)


class TestTokenUsage(unittest.TestCase):
    """Test the TokenUsage dataclass."""

    def test_total_tokens(self):
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        self.assertEqual(usage.total_tokens, 150)
        self.assertEqual(usage.prompt_tokens, 100)
        self.assertEqual(usage.completion_tokens, 50)

    def test_defaults(self):
        usage = TokenUsage()
        self.assertEqual(usage.prompt_tokens, 0)
        self.assertEqual(usage.completion_tokens, 0)
        self.assertEqual(usage.total_tokens, 0)


class TestModelState(unittest.TestCase):
    """Test the ModelState dataclass."""

    def test_creation(self):
        state = ModelState(model_id="openai.gpt-4o")
        self.assertEqual(state.model_id, "openai.gpt-4o")

    def test_defaults(self):
        state = ModelState(model_id="test")
        self.assertEqual(state.status, ModelStatus.ACTIVE)
        self.assertEqual(state.failure_count, 0)
        self.assertEqual(state.error_rate, 0.0)
        self.assertEqual(state.total_requests, 0)
        self.assertEqual(state.total_tokens, 0)
        self.assertEqual(state.total_cost, 0.0)
        self.assertIsNone(state.cooldown_until)
        self.assertIsNone(state.deactivation_reason)
        self.assertIsNone(state.last_failure_at)
        self.assertIsNone(state.last_success_at)

    def test_standby_status(self):
        state = ModelState(
            model_id="test", status=ModelStatus.STANDBY
        )
        self.assertEqual(state.status, ModelStatus.STANDBY)


class TestObservabilityConnectorABC(unittest.TestCase):
    """Test that ObservabilityConnector requires all abstract methods."""

    def test_requires_all_methods(self):
        # Attempting to instantiate without implementing all methods
        # should fail
        with self.assertRaises(TypeError):

            class IncompleteConnector(ObservabilityConnector):
                pass

            IncompleteConnector()

    def test_complete_implementation(self):
        class CompleteConnector(ObservabilityConnector):
            def emit(self, event):
                pass

            def log(self, entry):
                pass

            def flush(self, stats):
                pass

            def trace(self, entry):
                pass

        # Should not raise
        connector = CompleteConnector()
        self.assertIsInstance(connector, ObservabilityConnector)


class TestRoutingEvent(unittest.TestCase):
    """Test the RoutingEvent dataclass."""

    def test_creation(self):
        now = datetime.now()
        event = RoutingEvent(
            event_type=ObsEventType.MODEL_ACTIVATED,
            timestamp=now,
            model_id="openai.gpt-4o",
        )
        self.assertEqual(event.event_type, ObsEventType.MODEL_ACTIVATED)
        self.assertEqual(event.model_id, "openai.gpt-4o")

    def test_metadata_default(self):
        now = datetime.now()
        event = RoutingEvent(
            event_type=ObsEventType.MODEL_ROTATED,
            timestamp=now,
        )
        self.assertEqual(event.metadata, {})


class TestErrorClassification(unittest.TestCase):
    """Test the ErrorClassification dataclass."""

    def test_defaults(self):
        ec = ErrorClassification()
        self.assertFalse(ec.retryable)
        self.assertIsNone(ec.error_code)
        self.assertEqual(ec.message, "")
        self.assertEqual(ec.category, "unknown")

    def test_retryable(self):
        ec = ErrorClassification(retryable=True, error_code=429, category="rate_limit")
        self.assertTrue(ec.retryable)
        self.assertEqual(ec.error_code, 429)
        self.assertEqual(ec.category, "rate_limit")


# ---------------------------------------------------------------------------
# Audio types
# ---------------------------------------------------------------------------


class TestAudioSpeechRequest(unittest.TestCase):
    """Test the AudioSpeechRequest dataclass."""

    def test_creation(self):
        req = AudioSpeechRequest(
            model="tts-1",
            input="Hello, world!",
            voice="alloy",
        )
        self.assertEqual(req.model, "tts-1")
        self.assertEqual(req.input, "Hello, world!")
        self.assertEqual(req.voice, "alloy")

    def test_defaults(self):
        req = AudioSpeechRequest(model="tts-1", input="Hello", voice="nova")
        self.assertEqual(req.response_format, "mp3")
        self.assertEqual(req.speed, 1.0)

    def test_custom_format_and_speed(self):
        req = AudioSpeechRequest(
            model="tts-1-hd",
            input="Testing",
            voice="shimmer",
            response_format="wav",
            speed=1.5,
        )
        self.assertEqual(req.response_format, "wav")
        self.assertEqual(req.speed, 1.5)


class TestAudioSpeechResponse(unittest.TestCase):
    """Test the AudioSpeechResponse dataclass."""

    def test_defaults(self):
        resp = AudioSpeechResponse()
        self.assertIsNone(resp.audio_data)
        self.assertEqual(resp.format, "mp3")
        self.assertEqual(resp.size_bytes, 0)
        self.assertIsNone(resp.duration_seconds)
        self.assertEqual(resp.model, "")
        self.assertEqual(resp.input_characters, 0)

    def test_with_data(self):
        resp = AudioSpeechResponse(
            audio_data=b"\x00\x01\x02",
            format="wav",
            size_bytes=3,
            duration_seconds=1.5,
            model="tts-1",
            input_characters=13,
        )
        self.assertEqual(resp.audio_data, b"\x00\x01\x02")
        self.assertEqual(resp.format, "wav")
        self.assertEqual(resp.size_bytes, 3)
        self.assertEqual(resp.duration_seconds, 1.5)
        self.assertEqual(resp.model, "tts-1")
        self.assertEqual(resp.input_characters, 13)


class TestAudioTranscriptionRequest(unittest.TestCase):
    """Test the AudioTranscriptionRequest dataclass."""

    def test_creation(self):
        req = AudioTranscriptionRequest(
            model="whisper-1",
            file="https://example.com/audio.mp3",
        )
        self.assertEqual(req.model, "whisper-1")
        self.assertEqual(req.file, "https://example.com/audio.mp3")

    def test_defaults(self):
        req = AudioTranscriptionRequest(model="whisper-1", file="audio.mp3")
        self.assertIsNone(req.language)
        self.assertEqual(req.response_format, "json")
        self.assertIsNone(req.prompt)

    def test_custom_options(self):
        req = AudioTranscriptionRequest(
            model="assemblyai-best",
            file="https://example.com/audio.wav",
            language="en",
            response_format="text",
            prompt="Technical discussion about AI",
        )
        self.assertEqual(req.language, "en")
        self.assertEqual(req.response_format, "text")
        self.assertEqual(req.prompt, "Technical discussion about AI")


class TestAudioTranscriptionResponse(unittest.TestCase):
    """Test the AudioTranscriptionResponse dataclass."""

    def test_defaults(self):
        resp = AudioTranscriptionResponse()
        self.assertEqual(resp.text, "")
        self.assertIsNone(resp.language)
        self.assertIsNone(resp.duration_seconds)
        self.assertIsNone(resp.confidence)
        self.assertEqual(resp.model, "")

    def test_with_data(self):
        resp = AudioTranscriptionResponse(
            text="Hello, this is a test.",
            language="en",
            duration_seconds=5.2,
            confidence=0.95,
            model="whisper-1",
        )
        self.assertEqual(resp.text, "Hello, this is a test.")
        self.assertEqual(resp.language, "en")
        self.assertEqual(resp.duration_seconds, 5.2)
        self.assertEqual(resp.confidence, 0.95)
        self.assertEqual(resp.model, "whisper-1")


if __name__ == "__main__":
    unittest.main()
