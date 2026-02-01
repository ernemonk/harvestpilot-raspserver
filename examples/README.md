# Examples

This directory contains example configurations, usage patterns, and demonstrations.

## 📁 Example Files

### Configuration Examples
- **`examples_dynamic_config.py`** — Shows how to use dynamic configuration
  - Loading config from files
  - Overriding with environment variables
  - Creating custom device profiles
  - Example:
    ```bash
    python examples/examples_dynamic_config.py
    ```

## 🎓 What You'll Learn

Each example demonstrates:
- How to configure the system
- How to override defaults
- How to create custom setups
- How to extend the framework

## 🚀 Running Examples

```bash
# From repo root
python examples/examples_dynamic_config.py

# Or with Python module syntax
python -m examples.examples_dynamic_config
```

## 📋 Before Running Examples

Ensure:
1. Dependencies installed: `pip install -r requirements.txt`
2. Basic configuration in `.env` or `config/.env.local`
3. For hardware examples: Raspberry Pi with GPIO available

## 🔧 Using Examples in Your Code

Examples are meant to be **referenced and adapted**, not run directly on production.

For production, see:
- [../docs/SETUP_YOUR_PI.md](../docs/SETUP_YOUR_PI.md) — Production setup
- [../deployment/README.md](../deployment/README.md) — Deployment scripts
- [../REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) — Project structure

## 📖 Documentation

See [../REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) for the complete project layout.
