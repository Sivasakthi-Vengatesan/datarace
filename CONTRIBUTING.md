# Contributing to DataRace

Thank you for your interest in contributing to **DataRace**! DataRace is designed to advance automated database concurrency verification, Dynamic Partial-Order Reduction (DPOR), and deterministic bug reproduction.

---

## 🛠️ Development Setup

### 1. Prerequisites
- **Python**: 3.10, 3.11, or 3.12
- **Node.js**: 18+ (for Web Workbench UI)
- **Git**

### 2. Clone and Setup Environment
```bash
# Clone repository
git clone https://github.com/Sivasakthi-Vengatesan/datarace.git
cd datarace

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov ruff mypy
```

### 3. UI Setup (Optional)
```bash
cd ui
npm install
npm run dev
```

---

## 🧪 Testing & Verification

Before submitting a pull request, ensure all tests pass:

```bash
# Run pytest suite
python -m pytest tests/ -v

# Run benchmark verification
python cli/main.py benchmark
```

---

## 📁 Repository Structure & Subsystems

| Subsystem | Path | Description |
|---|---|---|
| **Core Models** | `core/` | `Transaction`, `Operation`, `Schedule`, and `ConflictEdge` definitions |
| **Tracer** | `tracer/` | SQL interception hooks and read/write set extraction |
| **Analyzer** | `analyzer/` | Serialization graph builder and Adya anomaly classifier |
| **Scheduler** | `scheduler/` | Conflict-directed DPOR schedule generation with bounded context switching |
| **Replay** | `replay/` | Multi-thread barrier coordination and deterministic sandbox runner |
| **Invariants** | `invariants/` | Domain invariant evaluation engine |
| **Reducer** | `reducer/` | Delta debugging ($ddmin$) schedule minimizer |
| **Benchmarks** | `benchmarks/` | Canonical concurrency bug scenarios |
| **UI** | `ui/` | Retro Windows 95 interactive visualizer |

---

## 🧩 Adding a New Concurrency Benchmark

1. Create a new scenario folder in `benchmarks/` (e.g. `benchmarks/11_custom_race_condition/`).
2. Implement:
   - `schema.sql`: Initial table schemas and records.
   - `workload.py`: Multi-transaction concurrent workload functions.
   - `invariant.py`: Expected consistency condition assertion.
   - `fix.py`: Serialized or properly isolated implementation.
3. Register the new benchmark in `benchmarks/__init__.py`.
4. Add automated test coverage in `tests/test_benchmarks.py`.

---

## 📝 Commit Conventions

We follow Conventional Commits:
- `feat:` New features or algorithms
- `fix:` Bug fixes in tracing, scheduling, or minimization
- `docs:` Documentation and benchmark writeups
- `test:` Additional test cases
- `refactor:` Code reorganization without behavioral changes
- `chore:` Dependency and configuration updates
