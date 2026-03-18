# Specification: Shared Memory Core Module

**Track ID:** shared-memory-core_20250318
**Type:** Feature
**Created:** 2025-03-18
**Status:** Draft

## Summary

Analyze the provided PDF documentation and create a core Python module that uses `mmap` and `struct` (or `ctypes.Structure`) to read and map Shared Memory sections (Physics, Graphics, Static) from Assetto Corsa, ACC, and AC Evo. This module will be the foundation for all telemetry data access in the application.

## Context

From `conductor/product.md`:
> "Python .exe application that reads Shared Memory from Assetto Corsa, ACC, and AC Evo to display telemetry (RPM, gear, speed, pressures) and export setups."

This track delivers the low-level data access layer that makes telemetry data available to higher-level components (UI, exporters, database). The existing `aclib_shared_memory.pyd` library provides one possible implementation, but we will prioritize a pure Python `mmap`/`struct` approach for maximum compatibility and maintainability, with optional fallback to the .pyd library if needed.

## User Story

As a developer, I want to have a reliable interface to the game's Shared Memory so that I can provide real-time telemetry data (RPM, speed, tyre pressures) to the dashboard and export vehicle setups.

## Problem Description

The Assetto Corsa family of games exposes telemetry data through Windows shared memory segments. We need a robust, thread-safe Python module that can:
- Locate and open these shared memory regions
- Parse binary data structures according to the PDF specification
- Detect when the game process starts or stops
- Provide mock data for UI development when the game isn't running
- Support all three game variants (AC, ACC, AC Evo)

## Acceptance Criteria

- [ ] `SharedMemoryReader` class can successfully connect to game memory segments (Physics, Graphics, Static)
- [ ] Data structures (PhysicsData, GraphicsData, StaticData) correctly map all fields with proper types and offsets per PDF specification
- [ ] The module can detect if the game is running or disconnected, and handle reconnection without crashing
- [ ] All telemetry data is accessible as native Python objects (int, float, bool) with appropriate units (RPM, km/h, etc.)
- [ ] `MockSharedMemoryReader` subclass provides realistic sample data for UI testing when the game is off
- [ ] Reader is thread-safe: concurrent reads from a background thread do not corrupt data or cause race conditions
- [ ] Hot-plugging works: game can start/stop while reader is running, reader automatically reconnects or raises appropriate exceptions
- [ ] Module has no dependencies beyond Python standard library (ctypes, mmap, struct, threading, time, etc.)
- [ ] Comprehensive unit tests cover parsing logic, connection handling, and mock mode

## Dependencies

None. This is a foundational module with no external dependencies beyond Python standard library.

## Out of Scope

- GUI and dashboard components (PyQt6 code belongs in separate tracks)
- Database storage and SQLite integration
- Complex telemetry analysis or lap comparisons
- Setup file exporting/writing logic
- Direct interaction with `aclib_shared_memory.pyd` (optional fallback may be added later, but `mmap`/`struct` is primary)
- Performance optimizations beyond baseline thread-safety and correct parsing
- Support for unreleased or undocumented game versions

## Technical Notes

**Must use**: `mmap` and `struct` (or `ctypes.Structure`) for binary parsing. High performance and no external dependencies are critical.

**Hot-plugging requirement**: The reader must detect when the game process creates or destroys the shared memory segment. This likely requires polling with a configurable interval, or using OS-level file system watchers if feasible on Windows. The reader should not crash if the memory segment disappears mid-read — instead, raise a `SharedMemoryDisconnectedError` and allow reconnection.

**Thread-safety**: The reader will be instantiated in a background thread that polls at ~60Hz. All public methods must be safe to call from any thread. Use locks where necessary, but avoid global interpreter lock (GIL) contention. Consider using a `threading.Lock` around mmap access if needed.

**Mock mode**: For UI development and testing when the game isn't running, provide a `MockSharedMemoryReader` that returns deterministic, realistic data (e.g., RPM ramping up, speed varying, gear changes). This allows developers to work without having the game launched.

**Data validation**: All parsed values should be validated against plausible ranges (e.g., RPM 0-15000, speed 0-400 km/h). Out-of-range values should raise `DataParseError` with context, not silently corrupted.

**Game variants**: The PDF documentation should describe differences between AC, ACC, and AC Evo shared memory layouts. The implementation should abstract these differences behind a common interface, with subclasses or strategy pattern for each game variant. The reader should auto-detect which game is running based on memory layout or process name.

---
_Generated by Conductor. Review and edit as needed._
