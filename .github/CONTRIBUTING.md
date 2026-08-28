# Contributing to Habitus AI 🏛️

Thank you for your interest in contributing to **Habitus AI**! We welcome contributions from developers, researchers, and community members.

---

## 🛠️ Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/munch2u-a11y/Habitus-AI.git
   cd habitus-ai
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in editable mode with development dependencies**:
   ```bash
   pip install -e '.[test]'
   ```

4. **Run the test suite**:
   ```bash
   python3 -m pytest
   ```

---

## 🧪 Testing Guidelines & TDD

We follow strict **Test-Driven Development (TDD)** principles:
- Every new feature or bugfix must include corresponding unit tests under `tests/`.
- Ensure all 15 structural invariants pass via `GraphRuntime.validate_invariants()`.
- Pull requests must maintain 100% passing tests across the test suite (`pytest`).

---

## 📝 Pull Request Workflow

1. Fork the repository and create a feature branch (`git checkout -b feature/my-feature`).
2. Implement your changes following standard Python (3.11+) type annotations.
3. Run `python3 -m pytest` to confirm all tests pass.
4. Push your branch and open a Pull Request describing your changes and technical rationale.

---

## 📄 License

By contributing to Habitus AI, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
