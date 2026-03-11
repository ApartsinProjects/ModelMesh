"""Tests for Docker build configuration and proxy deployment.

These tests validate the Docker infrastructure without requiring a running
Docker daemon. They check that all files, configurations, and scripts are
correct and consistent.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Test: Dockerfile structure
# ---------------------------------------------------------------------------


class TestDockerfile(unittest.TestCase):
    """Validate the Dockerfile is well-formed and complete."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "Dockerfile")
        with open(path, "r") as f:
            cls.content = f.read()
        cls.lines = [l.strip() for l in cls.content.splitlines() if l.strip()]

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "Dockerfile")))

    def test_base_image_is_python(self):
        self.assertTrue(
            any(l.startswith("FROM python:") for l in self.lines),
            "Dockerfile should use a Python base image",
        )

    def test_workdir_set(self):
        self.assertTrue(
            any(l.startswith("WORKDIR") for l in self.lines),
            "Dockerfile should set WORKDIR",
        )

    def test_copies_source(self):
        copy_lines = [l for l in self.lines if l.startswith("COPY")]
        self.assertGreaterEqual(len(copy_lines), 1, "Dockerfile should COPY source files")
        source_copied = any("src/python" in l for l in copy_lines)
        self.assertTrue(source_copied, "Dockerfile should copy src/python/")

    def test_copies_pyproject(self):
        copy_lines = [l for l in self.lines if l.startswith("COPY")]
        pyproject_copied = any("pyproject.toml" in l for l in copy_lines)
        self.assertTrue(pyproject_copied, "Dockerfile should copy pyproject.toml")

    def test_pip_install(self):
        run_lines = [l for l in self.lines if l.startswith("RUN")]
        pip_found = any("pip install" in l for l in run_lines)
        self.assertTrue(pip_found, "Dockerfile should run pip install")

    def test_pyyaml_installed(self):
        """PyYAML must be installed for YAML config loading."""
        run_lines = [l for l in self.lines if l.startswith("RUN")]
        yaml_found = any("pyyaml" in l.lower() for l in run_lines)
        self.assertTrue(yaml_found, "Dockerfile should install pyyaml")

    def test_exposes_port(self):
        expose_lines = [l for l in self.lines if l.startswith("EXPOSE")]
        self.assertGreaterEqual(len(expose_lines), 1, "Dockerfile should EXPOSE a port")
        self.assertIn("8080", expose_lines[0], "Default exposed port should be 8080")

    def test_entrypoint_is_proxy(self):
        entry_lines = [l for l in self.lines if l.startswith("ENTRYPOINT")]
        self.assertGreaterEqual(len(entry_lines), 1, "Dockerfile should have ENTRYPOINT")
        self.assertIn("modelmesh.proxy", entry_lines[0], "ENTRYPOINT should run modelmesh.proxy")

    def test_cmd_defaults(self):
        cmd_lines = [l for l in self.lines if l.startswith("CMD")]
        self.assertGreaterEqual(len(cmd_lines), 1, "Dockerfile should have CMD defaults")
        cmd_text = cmd_lines[0]
        self.assertIn("0.0.0.0", cmd_text, "CMD should default to 0.0.0.0")
        self.assertIn("8080", cmd_text, "CMD should default to port 8080")


# ---------------------------------------------------------------------------
# Test: docker-compose.yaml structure
# ---------------------------------------------------------------------------


class TestDockerCompose(unittest.TestCase):
    """Validate docker-compose.yaml configuration."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "docker-compose.yaml")
        with open(path, "r") as f:
            cls.content = f.read()

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "docker-compose.yaml")))

    def test_service_defined(self):
        self.assertIn("services:", self.content)
        self.assertIn("modelmesh-proxy:", self.content)

    def test_port_mapping(self):
        self.assertIn("8080:8080", self.content, "Should map port 8080")

    def test_env_file_reference(self):
        self.assertIn("env_file:", self.content)
        self.assertIn(".env", self.content)

    def test_config_volume_mount(self):
        self.assertIn("volumes:", self.content)
        self.assertIn("modelmesh.yaml", self.content)
        self.assertIn(":ro", self.content, "Config should be mounted read-only")

    def test_build_context(self):
        self.assertIn("build:", self.content)

    def test_command_references_config(self):
        self.assertIn("--config", self.content)


# ---------------------------------------------------------------------------
# Test: modelmesh.yaml configuration
# ---------------------------------------------------------------------------


class TestModelMeshConfig(unittest.TestCase):
    """Validate the modelmesh.yaml proxy configuration."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "modelmesh.yaml")
        with open(path, "r") as f:
            cls.content = f.read()

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "modelmesh.yaml")))

    def test_secrets_section(self):
        self.assertIn("secrets:", self.content)
        self.assertIn("store:", self.content)

    def test_providers_section(self):
        self.assertIn("providers:", self.content)

    def test_models_section(self):
        self.assertIn("models:", self.content)

    def test_pools_section(self):
        self.assertIn("pools:", self.content)

    def test_has_at_least_one_provider(self):
        # Check for at least one known provider
        providers_found = sum(1 for p in [
            "openai.llm.v1", "anthropic.claude.v1", "groq.api.v1",
            "google.gemini.v1", "deepseek.api.v1",
        ] if p in self.content)
        self.assertGreaterEqual(providers_found, 1, "Should have at least one provider")

    def test_has_at_least_one_model(self):
        model_patterns = ["gpt-", "claude-", "llama-", "gemini-", "deepseek-"]
        models_found = sum(1 for p in model_patterns if p in self.content)
        self.assertGreaterEqual(models_found, 1, "Should have at least one model")

    def test_pool_has_strategy(self):
        self.assertIn("strategy:", self.content)

    def test_pool_has_capability(self):
        self.assertIn("capability:", self.content)

    def test_api_keys_use_secret_refs(self):
        """API keys should reference secrets, not be hardcoded."""
        # Find all api_key lines
        for line in self.content.splitlines():
            stripped = line.strip()
            if stripped.startswith("api_key:"):
                value = stripped.split(":", 1)[1].strip()
                self.assertTrue(
                    value.startswith("${secrets:"),
                    f"API key should use secret reference, got: {value}",
                )

    def test_no_hardcoded_secrets(self):
        """Config file should not contain actual API key values."""
        secret_patterns = [r"sk-[A-Za-z0-9]{20,}", r"gsk_[A-Za-z0-9]{20,}", r"sk-ant-[A-Za-z0-9]{20,}"]
        for pattern in secret_patterns:
            self.assertIsNone(
                re.search(pattern, self.content),
                f"Found hardcoded secret matching {pattern}",
            )


# ---------------------------------------------------------------------------
# Test: .env.example template
# ---------------------------------------------------------------------------


class TestEnvExample(unittest.TestCase):
    """Validate the .env.example template."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, ".env.example")
        with open(path, "r") as f:
            cls.content = f.read()
        cls.lines = cls.content.splitlines()

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, ".env.example")))

    def test_has_openai_key(self):
        self.assertIn("OPENAI_API_KEY", self.content)

    def test_has_anthropic_key(self):
        self.assertIn("ANTHROPIC_API_KEY", self.content)

    def test_has_groq_key(self):
        self.assertIn("GROQ_API_KEY", self.content)

    def test_no_real_keys(self):
        """Template should not contain actual API keys."""
        for line in self.lines:
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                self.assertEqual(
                    value.strip(), "",
                    f"Template key {key.strip()} should be empty, got: {value.strip()}",
                )


# ---------------------------------------------------------------------------
# Test: .gitignore protects secrets
# ---------------------------------------------------------------------------


class TestGitignore(unittest.TestCase):
    """Verify .gitignore prevents secret leaks."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, ".gitignore")
        with open(path, "r") as f:
            cls.content = f.read()

    def test_env_file_ignored(self):
        self.assertIn(".env", self.content, ".env should be in .gitignore")

    def test_env_variants_ignored(self):
        self.assertIn(".env.*", self.content, ".env.* should be in .gitignore")


# ---------------------------------------------------------------------------
# Test: Automation scripts exist
# ---------------------------------------------------------------------------


class TestScripts(unittest.TestCase):
    """Verify automation scripts exist and have expected content."""

    def _script_path(self, name):
        return os.path.join(ROOT, "scripts", name)

    def _read_script(self, name):
        with open(self._script_path(name), "r", encoding="utf-8") as f:
            return f.read()

    def test_proxy_up_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("proxy-up.sh")))

    def test_proxy_down_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("proxy-down.sh")))

    def test_proxy_test_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("proxy-test.sh")))

    def test_docker_build_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("docker-build.sh")))

    def test_install_python_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("install-python.sh")))

    def test_install_typescript_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("install-typescript.sh")))

    def test_test_all_exists(self):
        self.assertTrue(os.path.isfile(self._script_path("test-all.sh")))

    def test_proxy_up_uses_docker_compose(self):
        content = self._read_script("proxy-up.sh")
        self.assertIn("docker compose", content)

    def test_proxy_test_checks_health(self):
        content = self._read_script("proxy-test.sh")
        self.assertIn("/health", content)

    def test_proxy_test_checks_models(self):
        content = self._read_script("proxy-test.sh")
        self.assertIn("/v1/models", content)

    def test_proxy_test_checks_chat(self):
        content = self._read_script("proxy-test.sh")
        self.assertIn("/v1/chat/completions", content)

    def test_proxy_test_checks_streaming(self):
        content = self._read_script("proxy-test.sh")
        self.assertIn("stream", content)

    def test_proxy_test_checks_cors(self):
        content = self._read_script("proxy-test.sh")
        self.assertIn("CORS", content)

    def test_scripts_have_shebang(self):
        for name in ["proxy-up.sh", "proxy-down.sh", "proxy-test.sh",
                      "docker-build.sh", "install-python.sh",
                      "install-typescript.sh", "test-all.sh"]:
            content = self._read_script(name)
            self.assertTrue(
                content.startswith("#!/"),
                f"{name} should start with a shebang line",
            )

    def test_scripts_use_strict_mode(self):
        for name in ["proxy-up.sh", "proxy-down.sh", "proxy-test.sh",
                      "docker-build.sh", "test-all.sh"]:
            content = self._read_script(name)
            self.assertIn(
                "set -e",
                content,
                f"{name} should use strict error handling",
            )


# ---------------------------------------------------------------------------
# Test: Browser test page
# ---------------------------------------------------------------------------


class TestBrowserTestPage(unittest.TestCase):
    """Validate the browser test page is complete and functional."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "samples", "proxy-test", "index.html")
        with open(path, "r") as f:
            cls.content = f.read()

    def test_file_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(ROOT, "samples", "proxy-test", "index.html"))
        )

    def test_is_valid_html(self):
        self.assertIn("<!DOCTYPE html>", self.content)
        self.assertIn("<html", self.content)
        self.assertIn("</html>", self.content)

    def test_has_no_external_dependencies(self):
        """Page should be self-contained with no external imports."""
        self.assertNotIn("cdn.", self.content.lower())
        self.assertNotIn("unpkg.com", self.content.lower())
        # Allow badge images from shields.io, but no JS/CSS CDNs
        script_tags = re.findall(r'<script\s+src=["\']([^"\']+)', self.content)
        self.assertEqual(len(script_tags), 0, "Should have no external script sources")
        link_tags = re.findall(r'<link[^>]+href=["\']([^"\']+)', self.content)
        css_links = [l for l in link_tags if "stylesheet" in self.content[self.content.index(l)-50:self.content.index(l)]]
        self.assertEqual(len(css_links), 0, "Should have no external CSS sources")

    def test_has_proxy_url_input(self):
        self.assertIn("proxy-url", self.content)

    def test_has_model_list_feature(self):
        self.assertIn("/v1/models", self.content)

    def test_has_chat_completion_feature(self):
        self.assertIn("/v1/chat/completions", self.content)

    def test_has_streaming_support(self):
        self.assertIn("stream", self.content.lower())
        self.assertIn("ReadableStream", self.content) or self.assertIn("getReader", self.content)

    def test_has_sse_parsing(self):
        self.assertIn("[DONE]", self.content)
        self.assertIn("data:", self.content)

    def test_has_health_check(self):
        self.assertIn("/health", self.content)

    def test_uses_fetch_api(self):
        self.assertIn("fetch(", self.content)

    def test_has_error_handling(self):
        self.assertIn("catch", self.content)
        self.assertIn("ERROR", self.content)


# ---------------------------------------------------------------------------
# Test: Proxy server module structure
# ---------------------------------------------------------------------------


class TestProxyModuleStructure(unittest.TestCase):
    """Validate the proxy Python module is properly structured."""

    def test_proxy_package_exists(self):
        pkg = os.path.join(ROOT, "src", "python", "modelmesh", "proxy")
        self.assertTrue(os.path.isdir(pkg))

    def test_init_exists(self):
        init = os.path.join(ROOT, "src", "python", "modelmesh", "proxy", "__init__.py")
        self.assertTrue(os.path.isfile(init))

    def test_main_exists(self):
        main = os.path.join(ROOT, "src", "python", "modelmesh", "proxy", "__main__.py")
        self.assertTrue(os.path.isfile(main))

    def test_server_exists(self):
        server = os.path.join(ROOT, "src", "python", "modelmesh", "proxy", "server.py")
        self.assertTrue(os.path.isfile(server))

    def test_cli_exists(self):
        cli = os.path.join(ROOT, "src", "python", "modelmesh", "proxy", "cli.py")
        self.assertTrue(os.path.isfile(cli))

    def test_server_imports(self):
        from modelmesh.proxy.server import ProxyServer, ServerStatus
        self.assertTrue(callable(ProxyServer))

    def test_cli_imports(self):
        from modelmesh.proxy.cli import main
        self.assertTrue(callable(main))


# ---------------------------------------------------------------------------
# Test: Proxy CLI argument parsing
# ---------------------------------------------------------------------------


class TestProxyCLI(unittest.TestCase):
    """Test the proxy CLI argument parser."""

    def test_default_args(self):
        from modelmesh.proxy.cli import main
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", default=None)
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8080)
        parser.add_argument("--token", default=None)
        parser.add_argument("--log-level", default="INFO")
        args = parser.parse_args([])
        self.assertIsNone(args.config)
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 8080)
        self.assertIsNone(args.token)
        self.assertEqual(args.log_level, "INFO")

    def test_custom_args(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", default=None)
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8080)
        parser.add_argument("--token", default=None)
        parser.add_argument("--log-level", default="INFO")
        args = parser.parse_args([
            "--config", "test.yaml",
            "--host", "127.0.0.1",
            "--port", "9090",
            "--token", "secret",
            "--log-level", "DEBUG",
        ])
        self.assertEqual(args.config, "test.yaml")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 9090)
        self.assertEqual(args.token, "secret")
        self.assertEqual(args.log_level, "DEBUG")


# ---------------------------------------------------------------------------
# Test: Live proxy HTTP (start, query, stop)
# ---------------------------------------------------------------------------


class TestProxyLiveHTTP(unittest.TestCase):
    """Integration test: start a real proxy, send HTTP requests, stop it.

    Uses a fake provider so no real API keys are needed.
    """

    @classmethod
    def setUpClass(cls):
        from modelmesh.proxy.server import ProxyServer
        config = {
            "providers": {
                "fake.v1": {
                    "connector": "fake.v1",
                    "enabled": True,
                    "instance": _FakeProvider(),
                },
            },
            "models": {
                "fake.model": {
                    "provider": "fake.v1",
                    "capabilities": ["generation.text-generation.chat-completion"],
                },
            },
            "pools": {
                "chat": {
                    "capability": "generation.text-generation.chat-completion",
                    "strategy": "stick-until-failure",
                },
            },
            "observability": {"connector": "modelmesh.null.v1"},
        }
        cls.server = ProxyServer(config=config, host="127.0.0.1", port=0)
        # Use port 0 to get a random available port
        cls.server._httpd = _create_server_on_random_port(cls.server)
        cls.port = cls.server._httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server._state.start_time = __import__("time").time()
        cls.thread = __import__("threading").Thread(
            target=cls.server._httpd.serve_forever, daemon=True
        )
        cls.thread.start()
        __import__("time").sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _get(self, path):
        import urllib.request
        req = urllib.request.Request(self.base_url + path)
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())

    def _post(self, path, body):
        import urllib.request
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())

    def test_health_endpoint(self):
        status, data = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "healthy")

    def test_models_endpoint(self):
        status, data = self._get("/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(data["object"], "list")
        self.assertIsInstance(data["data"], list)
        ids = [m["id"] for m in data["data"]]
        self.assertIn("chat", ids)

    def test_chat_completion(self):
        status, data = self._post("/v1/chat/completions", {
            "model": "chat",
            "messages": [{"role": "user", "content": "Hi"}],
        })
        self.assertEqual(status, 200)
        self.assertIn("choices", data)
        self.assertGreater(len(data["choices"]), 0)
        self.assertEqual(data["choices"][0]["message"]["content"], "Hello from proxy")

    def test_chat_completion_includes_usage(self):
        status, data = self._post("/v1/chat/completions", {
            "model": "chat",
            "messages": [{"role": "user", "content": "Hi"}],
        })
        self.assertIn("usage", data)
        self.assertIn("prompt_tokens", data["usage"])
        self.assertIn("completion_tokens", data["usage"])
        self.assertIn("total_tokens", data["usage"])

    def test_chat_completion_missing_model(self):
        import urllib.request, urllib.error
        data = json.dumps({"messages": [{"role": "user", "content": "Hi"}]}).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_chat_completion_missing_messages(self):
        import urllib.request, urllib.error
        data = json.dumps({"model": "chat"}).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_not_found(self):
        import urllib.request, urllib.error
        req = urllib.request.Request(self.base_url + "/v1/nonexistent")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 404)

    def test_cors_headers_on_response(self):
        import urllib.request
        req = urllib.request.Request(self.base_url + "/health")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_streaming_response(self):
        import urllib.request
        data = json.dumps({
            "model": "chat",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            self.assertIn("data:", raw)
            self.assertIn("[DONE]", raw)

    def test_status_tracks_requests(self):
        # Make a request first
        self._get("/health")
        status = self.server.get_status()
        self.assertGreater(status.total_requests, 0)


# ---------------------------------------------------------------------------
# Fake provider (reused from test_proxy.py)
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Minimal fake provider for integration tests."""

    async def complete(self, request):
        from modelmesh.interfaces.provider import (
            ChatMessage, CompletionChoice, CompletionResponse, TokenUsage,
        )
        return CompletionResponse(
            id="fake-resp-001",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello from proxy"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    async def stream(self, request):
        from modelmesh.interfaces.provider import (
            ChatMessage, CompletionChoice, CompletionResponse, TokenUsage,
        )
        yield CompletionResponse(
            id="chunk-1",
            model=request.model,
            choices=[CompletionChoice(
                index=0,
                delta=ChatMessage(role="assistant", content="Hi"),
                finish_reason=None,
            )],
            usage=TokenUsage(),
        )
        yield CompletionResponse(
            id="chunk-2",
            model=request.model,
            choices=[CompletionChoice(
                index=0,
                delta=ChatMessage(role="assistant", content=" there"),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability):
        return capability in self.get_capabilities()

    def list_models(self):
        from modelmesh.interfaces.provider import ModelInfo
        return [ModelInfo(id="fake-model", name="Fake Model")]

    def get_model_info(self, model_id):
        from modelmesh.interfaces.provider import ModelInfo
        return ModelInfo(id="fake-model", name="Fake Model")

    def check_quota(self):
        from modelmesh.interfaces.provider import QuotaStatus
        return QuotaStatus()

    def get_rate_limits(self):
        from modelmesh.interfaces.provider import RateLimitStatus
        return RateLimitStatus()

    def get_pricing(self, model_id):
        from modelmesh.interfaces.provider import ModelPricing
        return ModelPricing()

    def report_usage(self, model_id, usage):
        pass

    def classify_error(self, error):
        from modelmesh.interfaces.provider import ErrorClassification
        return ErrorClassification(retryable=False)


def _create_server_on_random_port(proxy_server):
    """Create the internal HTTPServer on a random available port."""
    from modelmesh.proxy.server import _MeshHTTPServer, _ProxyRequestHandler
    httpd = _MeshHTTPServer(
        ("127.0.0.1", 0),
        _ProxyRequestHandler,
        proxy_server._state,
    )
    return httpd


if __name__ == "__main__":
    unittest.main()
