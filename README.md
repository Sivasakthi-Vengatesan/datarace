# DataRace — Automated Database Concurrency Bug Discovery & Minimal Reproduction Engine

<div align="center">

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests Status](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?logo=vercel)](https://datarace-liard.vercel.app)
[![UI](https://img.shields.io/badge/UI-Win95%20Retro%20Workbench-teal.svg)](ui/)

<p align="center">
  <strong>Automated detection, deterministic replay, and delta-debugging reduction of application-level SQL race conditions and serializability violations.</strong>
</p>

[**Explore Live Web UI**](https://datarace-liard.vercel.app) • [**System Architecture**](#-system-architecture--workflow) • [**Quick Start**](#-quick-start) • [**Benchmarks**](#-canonical-benchmark-suite-10-real-world-cases) • [**Contributing**](CONTRIBUTING.md)

</div>

---

## ⚡ Executive Overview

**DataRace** is an automated database concurrency bug discovery and deterministic reproduction engine. Unlike generic database consistency fuzzers (such as Jepsen/Elle or Hermitage) which test whether the database engine itself complies with its isolation specification under network partitions, **DataRace targets application-level transaction bugs**.

In production web applications (FastAPI, Django, Rails, Spring Boot), 99% of concurrency catastrophes (overselling inventory, double-spending gift cards, booking races, lost account balances) happen when the underlying database is operating **completely correctly** under default isolation (such as PostgreSQL's default `READ COMMITTED`), but the **application business logic** makes invalid serializability assumptions.

DataRace bridges this gap by:
1. **Tracing Transactions Non-Invasively**: Capturing SQL queries, read/write item sets ($R(x), W(x)$), parameters, and transaction boundaries directly from application integration tests.
2. **Building the Direct Serialization Graph ($DSG$)**: Constructing Adya dependency edges ($ww, wr, rw$) and detecting cycles that prove isolation violations ($G0$ Lost Update, $G1c$ Inconsistent Read, $G2$ Write Skew).
3. **Conflict-Directed Dynamic Partial-Order Reduction (DPOR)**: Bounding context switches ($k \le 2$) and generating prioritized schedules that reverse conflicting operations without combinatorial explosion.
4. **Deterministic Multi-Thread Barrier Replay**: Forcing concurrent database connections into the exact candidate schedule using synchronization gates to guarantee 100% reproducible execution.
5. **Delta Debugging ($ddmin$) Schedule Minimization**: Pruning multi-thread executions down to the 2-to-4 operation minimal failing counterexample with actionable remediation advice.

---

## 📐 System Architecture & Workflow

```mermaid
flowchart TD
    subgraph Tracing["1. Non-Invasive Tracing"]
        APP["Application Tests / Workload"] --> TRACER["SQL Tracer & Interceptor"]
        TRACER --> OPS["Extracted Operation Log<br/>[R(x), W(x), LOCK, COMMIT]"]
    end

    subgraph Analysis["2. Dependency & Graph Analysis"]
        OPS --> DSG["Direct Serialization Graph (DSG)"]
        DSG --> ADYA["Adya Anomaly Classifier<br/>(G0, G1c, G2, P3, Deadlock)"]
    end

    subgraph DPOR["3. DPOR Schedule Generation"]
        ADYA --> SCHEDULER["Conflict-Directed DPOR"]
        SCHEDULER --> EXPLORE["Exploration Tree<br/>(Bound: k ≤ 2 context switches)"]
        EXPLORE --> CANDIDATES["Prioritized Interleaving Schedules"]
    end

    subgraph Replay["4. Deterministic Replay Engine"]
        CANDIDATES --> BARRIER["Multi-Thread Barrier Replay"]
        BARRIER --> DB[("Database Sandbox (SQLite/PG)")]
        DB --> INV_CHECK["Domain Invariant Evaluator"]
    end

    subgraph Minimization["5. Delta Debugging (ddmin) & Reporting"]
        INV_CHECK -- "Invariant Broken" --> REDUCER["Delta Debugger (ddmin)"]
        REDUCER --> MIN_TRACE["Minimal Reproducing Trace<br/>(2–4 operations)"]
        MIN_TRACE --> CLI["CLI Terminal Explorer"]
        MIN_TRACE --> UI["Win95 Retro Workbench UI"]
    end

    style Tracing fill:#1e1e2e,stroke:#89b4fa,stroke-width:2px,color:#cdd6f4
    style Analysis fill:#1e1e2e,stroke:#a6e3a1,stroke-width:2px,color:#cdd6f4
    style DPOR fill:#1e1e2e,stroke:#f9e2af,stroke-width:2px,color:#cdd6f4
    style Replay fill:#1e1e2e,stroke:#eba0ac,stroke-width:2px,color:#cdd6f4
    style Minimization fill:#1e1e2e,stroke:#cba6f7,stroke-width:2px,color:#cdd6f4
```

### Concurrency Interleaving & Anomaly Sequence

```mermaid
sequenceDiagram
    autonumber
    participant T1 as Transaction 1 (Thread A)
    participant DB as Shared Database
    participant T2 as Transaction 2 (Thread B)

    Note over T1, T2: Initial Balance: $100 (x = 100)
    T1->>DB: READ(x) -> 100
    T2->>DB: READ(x) -> 100
    Note over T1: Computes x - 40 = 60
    T1->>DB: WRITE(x, 60)
    T1->>DB: COMMIT
    Note over T2: Computes x - 50 = 50 (based on stale read!)
    T2->>DB: WRITE(x, 50)
    T2->>DB: COMMIT
    Note over DB: Final Balance: $50 (Expected: $10) — G0 Lost Update Anomaly!
```

---

## 🚀 Quick Start

### 1. Run Python Concurrency Benchmark Suite
```bash
# Run all 10 canonical concurrency benchmarks
python cli/main.py benchmark

# Explore conflict graph and DPOR schedules for a specific benchmark
python cli/main.py explore 01_banking_lost_update
```

### 2. Run Pytest Test Suite
```bash
python -m pytest
```

### 3. Launch Retro 90s Windows 95 Workbench UI
```bash
# Live deployment is available at https://datarace-liard.vercel.app
cd ui
npm install
npm run dev
```

### 4. Docker Environment
```bash
docker compose up --build
```

---

## 🔬 Mathematical Formalisms

### 1. Operations & Transactions
A transaction $T_i$ is a sequence of operations:
$$T_i = \langle o_{i,1}, o_{i,2}, \dots, o_{i,m} \rangle$$
where $o_{i,k} \in \{\text{BEGIN}, \text{READ}(x), \text{WRITE}(x), \text{LOCK}(x), \text{COMMIT}, \text{ABORT}\}$.

### 2. Dependency Relations (Adya Formalism)
- **Write-Write Dependency ($ww$)**: $T_i \xrightarrow{ww} T_j$ if $T_i$ writes version $x_u$ and $T_j$ overwrites it with $x_v$.
- **Write-Read Dependency ($wr$)**: $T_i \xrightarrow{wr} T_j$ if $T_i$ writes version $x_u$ and $T_j$ reads $x_u$.
- **Read-Write Anti-Dependency ($rw$)**: $T_i \xrightarrow{rw} T_j$ if $T_i$ reads version $x_u$ and $T_j$ overwrites $x_u$ with $x_v$.

### 3. Cycle Classification
- **Lost Update ($G0 / P4$)**: Cycle contains $rw$ and $ww$ edges targeting the same entity key.
- **Write Skew ($G2 / A5B$)**: Cycle contains $\ge 2$ $rw$ anti-dependencies on disjoint modified items.
- **Inconsistent Read ($G1c / P2$)**: Cycle contains mixed $wr$ and $rw$ edges.
- **Serializability ($SER$)**: $DSG(H)$ is strictly acyclic.

---

## 📊 Canonical Benchmark Suite (10 Real-World Cases)

| # | Benchmark Case | Category | Anomaly Type | Min Steps | Discovered In |
|---|---|---|---|---|---|
| **01** | `01_banking_lost_update` | Financial | Lost Update ($G0$) | 4 ops | 4.3ms |
| **02** | `02_ticket_double_booking` | E-Commerce | Double Allocation | 6 ops | 3.2ms |
| **03** | `03_coupon_reuse` | Promo Fraud | Promo Double-Spend | 6 ops | 2.3ms |
| **04** | `04_wallet_write_skew` | Banking | Write Skew ($G2$) | 6 ops | 2.3ms |
| **05** | `05_ecommerce_overselling` | Inventory | Overselling Race | 6 ops | 2.3ms |
| **06** | `06_phantom_read_budget` | Accounting | Phantom Insertion ($P3$) | 6 ops | 2.4ms |
| **07** | `07_transfer_deadlock` | Concurrency | Deadlock Cycle | 5 ops | 6.6ms |
| **08** | `08_job_queue_double_claim` | Task Queue | Double Claim | 6 ops | 1.7ms |
| **09** | `09_rate_limiter_bypass` | Security | Limit Overdraft | 6 ops | 2.0ms |
| **10** | `10_auction_bid_snooping` | Realtime | Stale Bid Overwrite | 4 ops | 3.1ms |

---

## 🛠️ Automated Remediation Guidelines

| Anomaly Pattern | Root Cause | Recommended Fix |
|---|---|---|
| **Lost Update ($G0$)** | Unlocked read followed by computed write | Use `SELECT ... FOR UPDATE` or atomic `UPDATE account SET balance = balance - :amount WHERE balance >= :amount` |
| **Write Skew ($G2$)** | Cross-row invariant verification without locking read set | Promote transaction to `SERIALIZABLE` or lock rows with shared/exclusive locks |
| **Double Booking / Allocation** | Unconstrained `SELECT` before `INSERT` | Use database uniqueness constraints or advisory locks |
| **Deadlock Cycle** | Inconsistent resource acquisition ordering | Enforce global lock ordering (e.g., sort account IDs before locking) |

---

## 🏛️ Project Directory Structure

```
datarace/
├── core/                   # Core data models: Transaction, Operation, ConflictEdge, Schedule
├── tracer/                 # Non-invasive SQL parser and SQLAlchemy / DB-API interception hooks
├── analyzer/               # Direct Serialization Graph (DSG) & Adya cycle anomaly detector
├── scheduler/              # Conflict-Directed Dynamic Partial-Order Reduction (DPOR) scheduler
├── replay/                 # Deterministic multi-thread barrier coordinator and sandbox runner
├── invariants/             # Declarative SQL & Python domain invariant engine
├── reducer/                # Delta Debugging (ddmin) transaction schedule minimizer
├── benchmarks/             # 10 canonical concurrency bug benchmarks with ground truth fixes
├── cli/                    # Rich developer command-line interface
├── tests/                  # Pytest automated test suite
├── ui/                     # Retro 90s Windows 95 Nostalgia Web Workbench (Vite + React)
├── export_ui_data.py       # Engine-to-UI data exporter
└── conftest.py             # Pytest configuration
```

---

## 📜 License
MIT License.
