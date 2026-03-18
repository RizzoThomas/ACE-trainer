# Workflow

## Testing Policy

**TDD Strictness**: Flexible — tests are recommended for complex logic but not enforced for all implementation.

- Core telemetry parsing and shared memory interfacing should have unit tests
- GUI components are typically harder to test; use integration tests where practical
- pytest and pytest-qt are the recommended testing tools

## Commit Strategy

**Conventional Commits** — use standardized commit message format:

```
feat: add real-time RPM gauge display
fix: handle shared memory read timeouts gracefully
docs: update API documentation for setup export
refactor: simplify telemetry data structure
test: add unit tests for lap time calculation
```

Benefits:
- Automated changelog generation
- Clear commit history for debugging
- Easy identification of breaking changes

## Code Review Requirements

**Required for non-trivial changes** — all changes that meet any of these criteria need review:

- Modifications to shared memory reading code
- New GUI components or major UI changes
- Database schema changes
- Build/packaging configuration changes
- Performance-critical optimizations

Self-review is acceptable for:
- Minor bug fixes (typos, simple conditional fixes)
- Documentation updates
- Configuration tweaks with no functional impact

## Verification Checkpoints

**After each phase completion** — manual verification is required when finishing:

1. **Phase: Shared Memory Integration**
   - Verify telemetry data reads correctly from all supported games
   - Check data values match expected ranges (RPM 0-15000, speed 0-350 km/h, etc.)

2. **Phase: GUI Development**
   - Test UI responsiveness under real telemetry load
   - Verify all visualizations update smoothly
   - Check window resizing and layout behavior

3. **Phase: Data Persistence**
   - Confirm laps and setups save correctly to SQLite
   - Test export functionality produces valid files

4. **Phase: Packaging**
   - Test .exe on clean Windows system
   - Verify all dependencies are bundled correctly
   - Check file size and startup time

## Task Lifecycle

1. **Create track** via `/conductor:new-track`
2. **Break into tasks** with clear acceptance criteria
3. **Implement with TDD** where appropriate
4. **Self-review** code against quality standards
5. **Request code review** if change is non-trivial
6. **Manual verification** at phase boundaries
7. **Mark task complete** and update track status
8. **Merge to main** when all tasks in track are done

## Branch Strategy

- `main` — production-ready code
- `feature/xxx` — feature development (created by `/conductor:new-track`)
- `bugfix/xxx` — hotfixes

## Quality Gates

Before merging any feature:
- [ ] All automated tests pass
- [ ] Code review completed (if required)
- [ ] Manual verification checkpoint passed
- [ ] Documentation updated (if user-facing changes)
- [ ] No merge conflicts with main
