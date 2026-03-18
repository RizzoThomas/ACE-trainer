# Product Definition

## Project Name

**Assetto telemetry tracker**

## Project Description

A desktop application that tracks and analyzes vehicle telemetry data from Assetto Corsa racing simulations. Built as a Windows .exe for easy distribution to sim racers.

## Problem Statement

There's no easy way to compare telemetry data between different sessions or drivers. Sim racers struggle to analyze their lap times, vehicle telemetry (RPM, gear, speed, pressures) in a unified, real-time dashboard.

## Target Users

- **Primary**: Sim racers looking to improve their lap times
- **Secondary**: Racing teams analyzing performance data

## Key Goals

1. Create a Python-based .exe application that reads Shared Memory from Assetto Corsa, ACC, and AC Evo
2. Display real-time telemetry: RPM, gear, speed, tire pressures
3. Provide setup export functionality
4. Leverage existing PDF documentation and .pyd shared memory library

## Success Metrics

- Real-time data refresh rate < 100ms
- Accurate telemetry capture from all supported Assetto Corsa variants
- Intuitive UI for non-technical sim racers
- Reliable .exe distribution with no external dependencies
