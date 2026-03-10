# ModelMesh Claude Code Skills

This folder contains Claude Code skill definitions for working with ModelMesh.
Each `.md` file is a self-contained skill that Claude Code can load and execute.

## Available Skills

| Skill | File | Description |
|---|---|---|
| **Install** | `install.md` | Install ModelMesh into any project (Python, TypeScript, or Docker) |
| **Configure** | `configure.md` | Generate modelmesh.yaml config with providers, models, pools |
| **Integrate** | `integrate.md` | Replace existing AI SDK calls with ModelMesh routing |
| **Deploy Proxy** | `deploy-proxy.md` | Set up and deploy the Docker OpenAI proxy |
| **Test** | `test.md` | Run ModelMesh test suite and verify integration |

## Usage with Claude Code

These skills can be loaded as custom commands in Claude Code. To use:

1. Copy the desired skill `.md` file into your project's `.claude/` directory
2. Or reference them directly when asking Claude Code for help

## How Skills Work

Each skill file contains:
- **Context**: What ModelMesh is and how it works
- **Decision tree**: Questions to ask the user to determine the right approach
- **Implementation steps**: Exact commands and code to execute
- **Verification**: How to confirm the integration works
