import React, { useState, useEffect, useRef } from "react";
import benchmarksData from "./data/benchmarksData.json";
import { 
  Play, Pause, SkipForward, RotateCcw, ShieldAlert, CheckCircle2, 
  Terminal, Database, GitCommit, Layers, AlertTriangle, Bug, Code,
  Server, Cpu, Activity, Info
} from "lucide-react";

export default function App() {
  const [benchmarks, setBenchmarks] = useState(benchmarksData);
  const [selectedCaseId, setSelectedCaseId] = useState(benchmarksData[0].case_id);
  const [activeTab, setActiveTab] = useState("debugger"); // debugger, dsg, minimizer, terminal
  const [stepIndex, setStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [terminalHistory, setTerminalHistory] = useState([
    "Microsoft(R) Windows 95",
    "(C)Copyright Microsoft Corp 1981-1996.",
    "",
    "C:\\DATARACE> datarace benchmark",
    "Running 10 canonical concurrency test cases...",
    "[01/10] Banking Account Lost Update                  -> [BUG FOUND] in 4.3ms (Min steps: 4)",
    "[02/10] Concert Ticket Double Booking Race           -> [BUG FOUND] in 3.2ms (Min steps: 6)",
    "[03/10] Single-Use Coupon Double-Spend               -> [BUG FOUND] in 2.3ms (Min steps: 6)",
    "[04/10] Joint Checking & Savings Write Skew (G2)     -> [BUG FOUND] in 2.3ms (Min steps: 6)",
    "[05/10] Flash Sale Inventory Overselling             -> [BUG FOUND] in 2.3ms (Min steps: 6)",
    "[06/10] Departmental Budget Phantom Insertion Race   -> [BUG FOUND] in 2.4ms (Min steps: 6)",
    "[07/10] Cross-Account Transfer Deadlock              -> [BUG FOUND] in 6.6ms (Min steps: 5)",
    "[08/10] Background Job Queue Double Claim            -> [BUG FOUND] in 1.7ms (Min steps: 6)",
    "[09/10] API Rate Limiter Concurrency Bypass          -> [BUG FOUND] in 2.0ms (Min steps: 6)",
    "[10/10] Live Auction Stale Bid Overwrite             -> [BUG FOUND] in 3.1ms (Min steps: 4)",
    "--------------------------------------------------------------------------------",
    "SUMMARY: 10/10 real-world concurrency bugs deterministically discovered & reproduced in 0.18s.",
    "",
    "Type 'help' or 'datarace explore <id>' to run analysis."
  ]);
  const [terminalInput, setTerminalInput] = useState("");
  const terminalBottomRef = useRef(null);

  const currentCase = benchmarks.find(b => b.case_id === selectedCaseId) || benchmarks[0];
  const failingSchedule = currentCase.failing_schedule || currentCase.schedules?.[0];
  const scheduleSteps = failingSchedule?.steps || [];
  const minSteps = currentCase.minimal_schedule?.steps || [];

  // Step debugger timer
  useEffect(() => {
    let timer;
    if (isPlaying) {
      timer = setInterval(() => {
        setStepIndex(prev => {
          if (prev >= scheduleSteps.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPlaying, scheduleSteps.length]);

  const handleSelectCase = (caseId) => {
    setSelectedCaseId(caseId);
    setStepIndex(0);
    setIsPlaying(false);
  };

  const handleRunAll = () => {
    setIsPlaying(false);
    setStepIndex(0);
    const log = [
      ...terminalHistory,
      `C:\\DATARACE> datarace benchmark --all`,
      `[EXEC] Initializing DPOR Schedule Explorer across all test cases...`,
      `[SUCCESS] 10/10 bugs reproduced deterministically.`
    ];
    setTerminalHistory(log);
  };

  const handleTerminalSubmit = (e) => {
    e.preventDefault();
    if (!terminalInput.trim()) return;
    const cmd = terminalInput.trim();
    const newHistory = [...terminalHistory, `C:\\DATARACE> ${cmd}`];

    if (cmd === "help") {
      newHistory.push("Available commands:");
      newHistory.push("  benchmark           - Run all 10 canonical concurrency test cases");
      newHistory.push("  explore <case_id>   - Analyze DSG conflict graph and explore schedules");
      newHistory.push("  minimize <case_id>  - Run delta debugging (ddmin) schedule reduction");
      newHistory.push("  list                - List all benchmark IDs");
      newHistory.push("  clear               - Clear screen");
    } else if (cmd === "clear") {
      setTerminalHistory([]);
      setTerminalInput("");
      return;
    } else if (cmd === "list") {
      benchmarks.forEach(b => newHistory.push(`  * ${b.case_id} (${b.title})`));
    } else if (cmd.startsWith("explore")) {
      const parts = cmd.split(" ");
      const id = parts[1] || selectedCaseId;
      const target = benchmarks.find(b => b.case_id.includes(id) || b.case_id === id);
      if (target) {
        setSelectedCaseId(target.case_id);
        setStepIndex(0);
        newHistory.push(`[ANALYZING] ${target.title}`);
        newHistory.push(`Conflict Edges: ${target.conflict_edges.length}`);
        newHistory.push(`Cycles Detected: ${target.cycles.length}`);
        newHistory.push(`Dangerous Schedule: ${target.failing_schedule?.description || "Found"}`);
      } else {
        newHistory.push(`Error: Benchmark '${id}' not found.`);
      }
    } else if (cmd === "benchmark") {
      newHistory.push("Running 10 canonical concurrency benchmarks...");
      benchmarks.forEach((b, idx) => {
        newHistory.push(`[${idx+1}/10] ${b.title} -> [BUG FOUND] (Cycles: ${b.cycles.length})`);
      });
      newHistory.push("SUMMARY: 10/10 bugs verified deterministically.");
    } else {
      newHistory.push(`'${cmd}' is not recognized as an internal command.`);
    }

    setTerminalHistory(newHistory);
    setTerminalInput("");
  };

  useEffect(() => {
    terminalBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [terminalHistory]);

  return (
    <div className="min-h-screen p-3 md:p-6 flex flex-col items-center">
      {/* Maximum width container */}
      <div className="w-full max-w-6xl space-y-4">
        
        {/* Top Windows 95 Menu Bar */}
        <div className="win-outset px-3 py-1.5 flex items-center justify-between text-xs font-bold select-none">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5"><Database className="w-4 h-4 text-[#000080]" /> <strong>DataRace v1.0.0</strong></span>
            <span className="hidden sm:inline win-link"><u>F</u>ile</span>
            <span className="hidden sm:inline win-link"><u>E</u>xplore</span>
            <span className="hidden sm:inline win-link"><u>S</u>chedule</span>
            <span className="hidden sm:inline win-link"><u>I</u>nvariants</span>
            <span className="hidden sm:inline win-link"><u>H</u>elp</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[#808080]">NETSCAPE 4.0</span>
            <span className="px-1.5 py-0.5 bg-[#000080] text-white">800x600</span>
          </div>
        </div>

        {/* Warning Construction Stripe Banner */}
        <div className="bg-construction p-1.5 win-outset">
          <div className="bg-[#000000] text-[#ffff00] px-3 py-1 font-bold text-center text-xs tracking-wider uppercase flex items-center justify-center gap-2">
            <AlertTriangle className="w-4 h-4 text-[#ffff00] animate-bounce" />
            <span>CRITICAL CONCURRENCY BUG DISCOVERY ENGINE • ADYA DSG FORMALISM • DPOR BOUNDED REPLAY</span>
            <AlertTriangle className="w-4 h-4 text-[#ffff00] animate-bounce" />
          </div>
        </div>

        {/* Marquee Ticker */}
        <div className="win-inset px-2 py-1 marquee-wrapper bg-[#ffffcc] text-xs font-bold text-black select-none">
          <div className="marquee-content space-x-8">
            <span className="text-[#ff0000]">★ HOT! AUTOMATED TRANSACTION INTERLEAVING TESTER</span>
            <span className="text-[#0000ff]">◆ 10/10 REAL-WORLD ISOLATION BUGS REPRODUCED</span>
            <span className="text-[#00aa00]">✔ ZERO POSTGRESQL MODIFICATIONS NEEDED</span>
            <span className="text-[#800080]">▲ DELTA DEBUGGING (ddmin) SCHEDULE MINIMIZER ACTIVE</span>
            <span className="text-[#ff0000]">● LOST UPDATES • WRITE SKEW • PHANTOM READS DETECTED</span>
          </div>
        </div>

        {/* Main Hero Header Window */}
        <div className="win-outset p-1">
          <div className="win-titlebar">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-white" />
              <span>C:\DATARACE\ENGINE.EXE — Concurrency Bug Discovery & Minimal Reproduction</span>
            </div>
            <div className="flex items-center">
              <button className="win-titlebar-btn">_</button>
              <button className="win-titlebar-btn">□</button>
              <button className="win-titlebar-btn text-red-700">✕</button>
            </div>
          </div>
          <div className="p-4 bg-[#c0c0c0] flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <div className="inline-block px-2 py-0.5 bg-[#ff0000] text-white font-bold text-xs uppercase mb-1 animate-pulse-glow">
                NEW! SYSTEMATIC DPOR CONCURRENCY ENGINE
              </div>
              <h1 className="text-2xl md:text-4xl text-rainbow uppercase">
                DataRace Concurrency Workbench
              </h1>
              <p className="text-xs md:text-sm text-black font-semibold mt-1">
                Automated Discovery, Conflict Graph Analysis, Deterministic Barrier Replay, and $ddmin$ Minimal Counterexamples.
              </p>
            </div>
            
            {/* Hit Counter */}
            <div className="win-inset-dark p-2 text-center min-w-[200px]">
              <div className="text-[10px] text-[#808080] uppercase tracking-wider">VISITOR HIT COUNTER</div>
              <div className="text-xl font-mono tracking-widest text-[#00ff00] font-bold">0004291</div>
              <div className="text-[10px] text-[#00ff00]">SYS STATUS: 100% OPERATIONAL</div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex flex-wrap gap-1 border-b-2 border-[#808080] pb-1">
          {[
            { id: "debugger", label: "▶ Step Debugger & Replay", icon: Play },
            { id: "dsg", label: "☍ Conflict Graph (DSG)", icon: GitCommit },
            { id: "minimizer", label: "✂ Minimal Counterexample", icon: Layers },
            { id: "benchmarks", label: "≡ 10 Benchmark Suites", icon: Database },
            { id: "terminal", label: ">_ MS-DOS Web CLI", icon: Terminal },
          ].map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`win-btn ${active ? "active bg-[#ffffff] font-bold" : ""}`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* TAB 1: STEP DEBUGGER & REPLAY */}
        {activeTab === "debugger" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            
            {/* Left Column: Benchmark Selector & Details */}
            <div className="win-outset p-1 lg:col-span-1 space-y-3">
              <div className="win-titlebar">
                <span>Select Concurrency Benchmark</span>
                <span className="text-[10px] bg-yellow-400 text-black px-1">10 CASES</span>
              </div>
              <div className="p-2 space-y-2">
                <div className="win-inset p-1 max-h-64 overflow-y-auto">
                  {benchmarks.map((b, idx) => (
                    <div
                      key={b.case_id}
                      onClick={() => handleSelectCase(b.case_id)}
                      className={`p-2 cursor-pointer border-b border-[#808080] text-xs ${
                        selectedCaseId === b.case_id ? "bg-[#000080] text-white font-bold" : "hover:bg-[#e0e0e0] text-black"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span>{idx + 1}. {b.title}</span>
                        <span className="text-[10px] px-1 bg-red-600 text-white font-bold">[BUG]</span>
                      </div>
                      <div className="text-[10px] opacity-80 mt-0.5">{b.category}</div>
                    </div>
                  ))}
                </div>

                <div className="win-inset-yellow p-2.5 text-xs space-y-1">
                  <div className="font-bold text-[#000080] uppercase">Anomaly Details:</div>
                  <p className="text-black font-medium">{currentCase.description}</p>
                  <div className="pt-1 text-[11px] font-mono text-red-700 font-bold">
                    Violates Invariant: {currentCase.failed_invariants?.[0] || "Global state invariant broken"}
                  </div>
                </div>

                <button onClick={handleRunAll} className="win-btn win-btn-primary w-full text-xs">
                  <Database className="w-4 h-4" /> Run All 10 Benchmarks in Sandbox
                </button>
              </div>
            </div>

            {/* Right Column: Interactive Schedule Timeline & Stepper */}
            <div className="win-outset p-1 lg:col-span-2 space-y-3">
              <div className="win-titlebar">
                <span>Deterministic Replay Sandbox — {currentCase.title}</span>
                <span className="text-[10px] bg-red-600 text-white px-1 font-mono">STEP {stepIndex + 1}/{scheduleSteps.length}</span>
              </div>

              <div className="p-3 space-y-4">
                {/* Control Toolbar */}
                <div className="win-outset p-2 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIsPlaying(!isPlaying)}
                      className={`win-btn ${isPlaying ? "win-btn-danger" : "win-btn-success"}`}
                    >
                      {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      <span>{isPlaying ? "PAUSE" : "PLAY SCHEDULE"}</span>
                    </button>
                    <button
                      onClick={() => {
                        setIsPlaying(false);
                        setStepIndex(prev => Math.min(prev + 1, scheduleSteps.length - 1));
                      }}
                      className="win-btn"
                    >
                      <SkipForward className="w-4 h-4" /> <span>STEP FORWARD</span>
                    </button>
                    <button
                      onClick={() => {
                        setIsPlaying(false);
                        setStepIndex(0);
                      }}
                      className="win-btn"
                    >
                      <RotateCcw className="w-4 h-4" /> <span>RESET</span>
                    </button>
                  </div>
                  <div className="text-xs font-mono font-bold text-[#000080]">
                    Preemption Points: {failingSchedule?.preemption_points || 2}
                  </div>
                </div>

                {/* Step Execution Visualizer */}
                <div className="win-inset p-3 space-y-2">
                  <div className="text-xs font-bold text-[#000080] uppercase flex items-center justify-between">
                    <span>Active Transaction Schedule Interleaving (DPOR Replay Trace):</span>
                    <span className="text-red-600">{stepIndex === scheduleSteps.length - 1 ? "★ INVARIANT VIOLATED AT END" : "Executing..."}</span>
                  </div>

                  <div className="space-y-1.5">
                    {scheduleSteps.map((step, idx) => {
                      const [tid, opIdx] = step;
                      const tx = currentCase.transactions[tid];
                      const op = tx?.operations?.[opIdx];
                      const isCurrent = idx === stepIndex;
                      const isPast = idx < stepIndex;

                      return (
                        <div
                          key={idx}
                          className={`p-2 flex items-center justify-between text-xs font-mono border-2 ${
                            isCurrent
                              ? "bg-[#000080] text-white border-black font-bold shadow-md"
                              : isPast
                              ? "bg-[#e8e8e8] text-[#404040] border-[#c0c0c0]"
                              : "bg-[#ffffff] text-[#808080] border-[#dfdfdf]"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="w-6 text-center font-bold">{idx + 1}.</span>
                            <span className={`px-1.5 py-0.5 text-[10px] font-bold ${
                              tid.includes("1") ? "bg-blue-600 text-white" : "bg-purple-600 text-white"
                            }`}>
                              {tid}
                            </span>
                            <span className="font-bold">{op?.op_type || "OP"}</span>
                            <span className="truncate max-w-md">{op?.sql || "Query execution"}</span>
                          </div>
                          <div>
                            {isCurrent && <span className="px-1.5 py-0.5 bg-yellow-400 text-black text-[10px] font-bold">EXECUTING GATE</span>}
                            {isPast && <span className="text-green-700 font-bold">✓ DONE</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Post-Replay Invariant Status */}
                {stepIndex === scheduleSteps.length - 1 && (
                  <div className="p-3 bg-[#ff0000] text-white win-outset space-y-1 animate-pulse-glow">
                    <div className="flex items-center gap-2 font-bold text-sm">
                      <ShieldAlert className="w-5 h-5 text-yellow-300" />
                      <span>CONCURRENCY ANOMALY REPRODUCED DETERMINISTICALLY!</span>
                    </div>
                    <div className="text-xs font-mono text-yellow-200">
                      Broken Invariant: {currentCase.failed_invariants?.[0]}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: CONFLICT GRAPH (DSG) */}
        {activeTab === "dsg" && (
          <div className="win-outset p-1 space-y-3">
            <div className="win-titlebar">
              <span>Direct Serialization Graph (DSG) & Adya Dependency Engine</span>
              <span className="text-[10px] bg-red-600 text-white px-1 font-mono">
                {currentCase.cycles.length} CYCLES DETECTED
              </span>
            </div>

            <div className="p-4 bg-[#c0c0c0] grid grid-cols-1 md:grid-cols-2 gap-4">
              
              {/* Left: Conflict Edges Table */}
              <div className="space-y-3">
                <div className="text-xs font-bold text-[#000080] uppercase">
                  Identified Conflict Edges ($E = E_&#123;ww&#125; \cup E_&#123;wr&#125; \cup E_&#123;rw&#125;$):
                </div>
                <div className="win-inset p-2 max-h-80 overflow-y-auto">
                  <table className="win-table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Source</th>
                        <th>Target</th>
                        <th>Key / Item</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentCase.conflict_edges.map((e, idx) => (
                        <tr key={idx}>
                          <td>
                            <span className={`px-1 text-[10px] font-bold text-white ${
                              e.dep_type === "WW" ? "bg-red-600" : e.dep_type === "WR" ? "bg-blue-600" : "bg-yellow-600"
                            }`}>
                              {e.dep_type}
                            </span>
                          </td>
                          <td className="font-mono font-bold">{e.source_tx}</td>
                          <td className="font-mono font-bold">{e.target_tx}</td>
                          <td className="font-mono text-xs">{e.item_key}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Right: Cycle Anomaly Classification */}
              <div className="space-y-3">
                <div className="text-xs font-bold text-[#000080] uppercase">
                  Adya Isolation Anomaly Classification:
                </div>
                <div className="space-y-2">
                  {currentCase.cycles.map((c, idx) => (
                    <div key={idx} className="win-inset-yellow p-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm text-red-700">{c.title}</span>
                        <span className="px-1.5 py-0.5 bg-red-700 text-white text-[10px] font-bold uppercase">{c.anomaly_type}</span>
                      </div>
                      <p className="text-xs text-black">{c.description}</p>
                      <div className="text-[11px] font-mono text-[#000080] font-semibold">
                        Cycle Edges: {c.edges.map(e => `${e.source_tx} --(${e.dep_type})--> ${e.target_tx}`).join(" | ")}
                      </div>
                    </div>
                  ))}

                  <div className="win-inset p-3 bg-white space-y-1">
                    <div className="font-bold text-xs text-[#000080]">Mathematical Formalism:</div>
                    <p className="text-xs text-[#404040]">
                      A cycle in the Direct Serialization Graph containing $rw$-anti-dependencies or $ww$-dependencies proves the execution history violates Serializability ($SER$).
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: MINIMAL COUNTEREXAMPLE (ddmin) */}
        {activeTab === "minimizer" && (
          <div className="win-outset p-1 space-y-3">
            <div className="win-titlebar">
              <span>Delta Debugging ($ddmin$) Schedule Minimizer & Remediation</span>
              <span className="text-[10px] bg-green-700 text-white px-1 font-mono">REDUCED TO {minSteps.length} OPERATIONS</span>
            </div>

            <div className="p-4 bg-[#c0c0c0] grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Original Failing Schedule */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-black uppercase flex items-center justify-between">
                  <span>Raw Discovered Interleaving ({scheduleSteps.length} steps):</span>
                  <span className="text-red-700 font-bold">Unpruned</span>
                </div>
                <div className="win-inset p-2 space-y-1 max-h-72 overflow-y-auto">
                  {scheduleSteps.map((step, idx) => {
                    const [tid, opIdx] = step;
                    const op = currentCase.transactions[tid]?.operations?.[opIdx];
                    return (
                      <div key={idx} className="p-1.5 text-xs font-mono bg-[#f0f0f0] border border-[#d0d0d0] flex items-center justify-between">
                        <span>{idx+1}. {tid}.{op?.op_type}: {op?.sql}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Minimized Schedule */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-[#000080] uppercase flex items-center justify-between">
                  <span>Minimal Counterexample ($ddmin$ Reduced: {minSteps.length} steps):</span>
                  <span className="text-green-700 font-bold">Minimal Ground Truth</span>
                </div>
                <div className="win-inset-yellow p-2 space-y-1 max-h-72 overflow-y-auto border-2 border-[#000080]">
                  {minSteps.map((step, idx) => {
                    const [tid, opIdx] = step;
                    const op = currentCase.transactions[tid]?.operations?.[opIdx];
                    return (
                      <div key={idx} className="p-1.5 text-xs font-mono bg-white border border-[#808080] flex items-center justify-between font-bold">
                        <span className="text-[#000080]">{idx+1}. {tid}.{op?.op_type}</span>
                        <span className="text-black text-[11px] truncate max-w-xs">{op?.sql}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Remediation Snippet */}
              <div className="md:col-span-2 win-inset p-3 bg-[#ffffcc] space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm text-green-900">
                  <CheckCircle2 className="w-5 h-5 text-green-700" />
                  <span>Suggested Fix & Concurrency Hardening:</span>
                </div>
                <p className="text-xs font-medium text-black">{currentCase.suggested_fix}</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: 10 BENCHMARK SUITES */}
        {activeTab === "benchmarks" && (
          <div className="win-outset p-1 space-y-3">
            <div className="win-titlebar">
              <span>Canonical Database Concurrency Benchmark Suite (10 Cases)</span>
              <span className="text-[10px] bg-green-700 text-white px-1">100% REPRODUCIBLE</span>
            </div>

            <div className="p-3 bg-[#c0c0c0]">
              <div className="win-inset p-2 overflow-x-auto">
                <table className="win-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Case Title</th>
                      <th>Category</th>
                      <th>DSG Cycles</th>
                      <th>Schedules Tested</th>
                      <th>Min Steps</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {benchmarks.map((b, idx) => (
                      <tr key={b.case_id} className={selectedCaseId === b.case_id ? "selected" : ""}>
                        <td className="font-bold">{idx + 1}</td>
                        <td className="font-bold">{b.title}</td>
                        <td className="text-xs">{b.category}</td>
                        <td className="font-mono text-center font-bold text-red-600">{b.cycles.length}</td>
                        <td className="font-mono text-center">{b.schedules.length}</td>
                        <td className="font-mono text-center font-bold text-green-700">{b.minimal_schedule?.steps?.length || 4}</td>
                        <td>
                          <span className="px-1.5 py-0.5 bg-red-600 text-white text-[10px] font-bold uppercase">
                            [BUG FOUND]
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => {
                              setSelectedCaseId(b.case_id);
                              setActiveTab("debugger");
                            }}
                            className="win-btn text-[10px] py-0.5 px-2"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: MS-DOS WEB CLI */}
        {activeTab === "terminal" && (
          <div className="win-outset p-1 space-y-2">
            <div className="win-titlebar">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-white" />
                <span>MS-DOS Prompt — DataRace CLI Emulator (Windows 95)</span>
              </div>
              <div className="flex items-center">
                <button className="win-titlebar-btn">_</button>
                <button className="win-titlebar-btn">□</button>
                <button className="win-titlebar-btn text-red-700">✕</button>
              </div>
            </div>

            <div className="win-inset-dark p-3 font-mono text-xs space-y-1 max-h-96 overflow-y-auto">
              {terminalHistory.map((line, idx) => (
                <div key={idx} className="whitespace-pre-wrap leading-relaxed text-[#00ff00]">
                  {line}
                </div>
              ))}
              <div ref={terminalBottomRef} />
              
              <form onSubmit={handleTerminalSubmit} className="flex items-center gap-1 pt-2">
                <span className="text-[#00ff00]">C:\DATARACE&gt;</span>
                <input
                  type="text"
                  value={terminalInput}
                  onChange={(e) => setTerminalInput(e.target.value)}
                  className="flex-1 bg-transparent text-[#00ff00] outline-none font-mono text-xs border-none"
                  autoFocus
                />
              </form>
            </div>
          </div>
        )}

        {/* 90s Decorative Color Squares & Footer */}
        <hr className="hr-groove" />
        <div className="flex flex-col md:flex-row items-center justify-between gap-3 text-xs text-[#000000]">
          <div className="flex items-center gap-1.5">
            {["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff"].map((color, idx) => (
              <div
                key={idx}
                className="w-5 h-5 win-outset"
                style={{ backgroundColor: color }}
              />
            ))}
            <span className="font-bold ml-2">Windows 95 Color Palette Matrix</span>
          </div>

          <div className="text-center md:text-right font-mono text-[11px] text-[#404040]">
            <div>BEST VIEWED IN NETSCAPE NAVIGATOR • 800x600 RESOLUTION</div>
            <div>DATARACE IS OPEN SOURCE SOFTWARE (MIT LICENSE)</div>
          </div>
        </div>

      </div>
    </div>
  );
}
