# ModelMesh Starter Template

Get started with ModelMesh in 30 seconds.

## Python

```bash
# Copy the template
cp -r tools/starter-template/python/ my-ai-project/
cd my-ai-project

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your key

# Run it
python main.py
```

## TypeScript

```bash
# Copy the template
cp -r tools/starter-template/typescript/ my-ai-project/
cd my-ai-project

# Install dependencies
npm install

# Set your API key
cp .env.example .env
# Edit .env and add your key

# Run it
npx tsx main.ts
```

## What's Included

Each template provides:
- **`main.py` / `main.ts`** — Working example with chat completion
- **`.env.example`** — API key template
- **`requirements.txt` / `package.json`** — Dependencies
- **`test_main.py` / `main.test.ts`** — Test skeleton
- **`modelmesh.yaml`** — Starter configuration

## Customization

After copying, edit `modelmesh.yaml` to:
- Add more providers (Anthropic, Gemini, etc.)
- Configure rotation strategies
- Set budget limits
- Enable observability
