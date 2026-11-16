# Cross-cutting conventions (default baseline)

These defaults apply when the runtime has not injected project-specific
conventions for the current project. Follow them as a maintainer who expects
this code to outlive today's task.

## Layering and SOLID

- One module, one purpose. Extend via composition; never grow a central
  switch or an ever-growing utility module.
- Depend on abstractions, not concrete implementations:
  - consumers depend on a data-provider/interface, not on a concrete client,
  - persistence is reached through repository interfaces bound to the storage
    technology of the project, and routers/controllers/handlers stay thin and
    delegate to service boundaries.
- Never leak internal persistence entities (ORM rows, db records, models) to
  external-facing layers. Shape response objects (DTOs, serializers) at the
  boundary layer that serves them.
- Data access lives in the project's repositories/dao layer only. Routes,
  controllers, and UI code never touch the database or ORM directly.
- Discover the project's actual layering by reading its structure before your
  first edit, then follow it exactly. When the project's own conventions
  differ from these defaults, the project wins.

## Contracts stay aligned

- After ANY change to an interface across a boundary (API response, shared
  schema, emitted event, inter-process payload), update the consuming side's
  type definitions, client wrapper, and schemas in the same change set.
- Declared shapes must match the real shapes exactly: no "approximately
  correct" types, no fields the producer never sends, no unchecked casts to
  paper over a mismatch.

## No dead code, no loose ends

- Treat unused imports, unused types, and unreachable branches as errors, not
  style issues; static analysis and strict compilation should stay clean.
- Delete code you replace. Do not leave commented-out blocks, unused helpers,
  or TODO comments behind - finished means finished.

## Descriptive names

- No single-letter or cryptic identifiers anywhere. This includes short
  callbacks (mapper calls, filters, event handlers): write `project`, `user`,
  `error`, `event` - never `p`, `u`, `e`, `a`.
- If the project enforces naming or complexity rules via linters or hooks on
  changed files, never disable, skip, or bypass them to make an error go away.
  Fix the code instead.

## Verify before you declare done

- Discover the project's toolchain from its configuration files (test runner,
  type checker, linter) and run the checks that cover the files you touched,
  plus the test suite. Fix every failure you caused.
- Your final summary must list, per changed file, what changed and which check
  covers it. If you could not run a check, say so explicitly instead of
  claiming success.
