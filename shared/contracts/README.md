# Common contracts

`src/api.ts` is the source for the existing TypeScript media, group, scan, cleanup and settings types. Desktop imports it through `apps/desktop/frontend/src/types/api.ts`; avoid maintaining a second copy of the same definitions.

These types describe the current transport. The desktop Pydantic request validation and SQLAlchemy persistence models remain desktop implementation details. When Android is implemented, map media identifiers and permissions through its native adapter and introduce versioned schemas/code generation as needed. This directory contains no Android runtime or desktop filesystem code.
