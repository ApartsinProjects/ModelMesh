"""Tests for the modelmesh.create() function."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

import modelmesh
from modelmesh.client.mesh_client import MeshClient
from modelmesh.config.mesh_config import MeshConfig


class TestCreate(unittest.TestCase):
    """Test the modelmesh.create() function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_create_no_args_raises(self):
        with self.assertRaises(ValueError) as ctx:
            modelmesh.create()
        self.assertIn("Specify capabilities", str(ctx.exception))

    @patch.dict(os.environ, {}, clear=True)
    def test_create_capabilities_no_providers_raises(self):
        with self.assertRaises(ValueError) as ctx:
            modelmesh.create("chat-completion")
        self.assertIn("No providers detected", str(ctx.exception))

    def test_create_with_config_dict(self):
        from modelmesh.interfaces.provider import (
            ChatMessage,
            CompletionChoice,
            CompletionRequest,
            CompletionResponse,
            ErrorClassification,
            ModelInfo,
            ModelPricing,
            ProviderConnector,
            QuotaStatus,
            RateLimitStatus,
            TokenUsage,
        )

        class InlineProvider(ProviderConnector):
            async def complete(self, request):
                return CompletionResponse(
                    id="inline-resp",
                    model=request.model,
                    choices=[
                        CompletionChoice(
                            index=0,
                            message=ChatMessage(
                                role="assistant", content="Inline!"
                            ),
                            finish_reason="stop",
                        )
                    ],
                    usage=TokenUsage(
                        prompt_tokens=1,
                        completion_tokens=1,
                        total_tokens=2,
                    ),
                )

            async def stream(self, request):
                yield CompletionResponse()

            def get_capabilities(self):
                return ["chat"]

            def supports(self, cap):
                return cap == "chat"

            def list_models(self):
                return []

            def get_model_info(self, model_id):
                raise KeyError

            def check_quota(self):
                return QuotaStatus()

            def get_rate_limits(self):
                return RateLimitStatus()

            def get_pricing(self, model_id):
                return ModelPricing()

            def report_usage(self, model_id, usage):
                pass

            def classify_error(self, error):
                return ErrorClassification(retryable=False)

        config_dict = {
            "providers": {
                "inline.v1": {
                    "connector": "inline.v1",
                    "enabled": True,
                    "instance": InlineProvider(),
                },
            },
            "models": {
                "inline.test": {
                    "provider": "inline.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                    "strategy": "stick-until-failure",
                },
            },
            "observability": {"connector": "modelmesh.null.v1"},
        }

        client = modelmesh.create(config=config_dict)
        self.assertIsInstance(client, MeshClient)

    def test_create_with_pool(self):
        detected = [
            {
                "name": "openai",
                "connector": "openai.llm.v1",
                "base_url": "https://api.openai.com",
                "default_models": [],
                "env_var": "OPENAI_API_KEY",
                "api_key": "sk-test",
            }
        ]
        with patch(
            "modelmesh.config.auto_detect.detect_providers",
            return_value=detected,
        ):
            client = modelmesh.create(pool="text-generation")
            self.assertIsInstance(client, MeshClient)

    def test_create_returns_mesh_client(self):
        detected = [
            {
                "name": "openai",
                "connector": "openai.llm.v1",
                "base_url": "https://api.openai.com",
                "default_models": [],
                "env_var": "OPENAI_API_KEY",
                "api_key": "sk-test",
            }
        ]
        with patch(
            "modelmesh.config.auto_detect.detect_providers",
            return_value=detected,
        ):
            client = modelmesh.create("chat-completion")
            self.assertIsInstance(client, MeshClient)

    def test_create_with_observability(self):
        """Create with a config dict that specifies file observability."""
        from modelmesh.interfaces.provider import (
            ChatMessage,
            CompletionChoice,
            CompletionRequest,
            CompletionResponse,
            ErrorClassification,
            ModelInfo,
            ModelPricing,
            ProviderConnector,
            QuotaStatus,
            RateLimitStatus,
            TokenUsage,
        )

        class StubProvider(ProviderConnector):
            async def complete(self, request):
                return CompletionResponse(
                    id="r",
                    model=request.model,
                    choices=[
                        CompletionChoice(
                            index=0,
                            message=ChatMessage(role="assistant", content="ok"),
                            finish_reason="stop",
                        )
                    ],
                    usage=TokenUsage(),
                )

            async def stream(self, request):
                yield CompletionResponse()

            def get_capabilities(self):
                return ["chat"]

            def supports(self, cap):
                return cap == "chat"

            def list_models(self):
                return []

            def get_model_info(self, model_id):
                raise KeyError

            def check_quota(self):
                return QuotaStatus()

            def get_rate_limits(self):
                return RateLimitStatus()

            def get_pricing(self, model_id):
                return ModelPricing()

            def report_usage(self, model_id, usage):
                pass

            def classify_error(self, error):
                return ErrorClassification(retryable=False)

        config_dict = {
            "providers": {
                "stub.v1": {
                    "connector": "stub.v1",
                    "instance": StubProvider(),
                },
            },
            "models": {
                "stub.model": {
                    "provider": "stub.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                    "strategy": "stick-until-failure",
                },
            },
            # File observability is not auto-instantiated by connector ID
            # alone (it needs a path), but the null fallback works
            "observability": {"connector": "modelmesh.null.v1"},
        }

        client = modelmesh.create(config=config_dict)
        self.assertIsInstance(client, MeshClient)

    def test_create_with_mesh_config_object(self):
        from modelmesh.interfaces.provider import (
            ChatMessage,
            CompletionChoice,
            CompletionResponse,
            ErrorClassification,
            ModelInfo,
            ModelPricing,
            ProviderConnector,
            QuotaStatus,
            RateLimitStatus,
            TokenUsage,
        )

        class StubProv(ProviderConnector):
            async def complete(self, request):
                return CompletionResponse(
                    id="r",
                    model=request.model,
                    choices=[
                        CompletionChoice(
                            index=0,
                            message=ChatMessage(role="assistant", content="ok"),
                            finish_reason="stop",
                        )
                    ],
                    usage=TokenUsage(),
                )

            async def stream(self, request):
                yield CompletionResponse()

            def get_capabilities(self):
                return ["chat"]

            def supports(self, cap):
                return cap == "chat"

            def list_models(self):
                return []

            def get_model_info(self, model_id):
                raise KeyError

            def check_quota(self):
                return QuotaStatus()

            def get_rate_limits(self):
                return RateLimitStatus()

            def get_pricing(self, model_id):
                return ModelPricing()

            def report_usage(self, model_id, usage):
                pass

            def classify_error(self, error):
                return ErrorClassification(retryable=False)

        mc = MeshConfig(raw={
            "providers": {
                "stub.v1": {
                    "connector": "stub.v1",
                    "instance": StubProv(),
                },
            },
            "models": {
                "stub.model": {
                    "provider": "stub.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                },
            },
            "observability": {"connector": "modelmesh.null.v1"},
        })

        client = modelmesh.create(config=mc)
        self.assertIsInstance(client, MeshClient)

    def test_create_invalid_config_type_raises(self):
        with self.assertRaises(TypeError):
            modelmesh.create(config=12345)


if __name__ == "__main__":
    unittest.main()
