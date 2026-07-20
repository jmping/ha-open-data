# Architecture Roadmap

## Phase 1 - Foundation (complete)
- Provider abstraction
- Portal vs dataset entries
- Reference parsing
- Discovery
- Manual dataset add

## Phase 2 - Adaptive datasets (in progress)
- Dataset intelligence cache
- Adaptive pagination
- Ordering inference
- Location ranking

## Phase 3 - Capability model
- Provider capability negotiation
- Offset/cursor/filter abstraction
- Background profiling scheduler
- Smarter polling strategies

## Phase 4 - Semantic model
- Observable discovery
- Field classification
- Stream grouping
- Entity recommendations

## Phase 5 - Intelligence
- Schema cache
- Statistics cache
- Update cadence learning
- Confidence-driven optimization

## Phase 6 - Providers
- ArcGIS
- OpenDataSoft
- SensorThings
- CSV/JSON
- Generic REST

Each phase should be independently testable, mergeable, and leave the integration in a usable state.