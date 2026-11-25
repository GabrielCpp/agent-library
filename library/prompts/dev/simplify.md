---
agent: agent
description: Refactor and simplify the current branch
---

**Analyze and simplify the code in the current branch:**

Please review all modified files in this branch and help me refactor the code with the following objectives:

1. **Remove Redundant Code**
   - Identify and eliminate duplicate logic, repeated code blocks, and unnecessary repetition
   - Consolidate similar implementations into shared utilities
   - Remove redundant imports, variables, and type definitions

2. **Remove Dead Code**
   - Find and remove unused functions, methods, and variables
   - Identify unreachable code paths and obsolete logic
   - Remove commented-out code blocks that are no longer needed
   - Eliminate unused imports and dependencies

3. **Consolidate Over-Engineered Functions**
   - Identify functions that are too granular or don't provide meaningful abstraction
   - Merge small helper functions that are only called once into their parent functions
   - Simplify wrapper functions that add no value
   - Reduce unnecessary function nesting

4. **Create Reusable Patterns**
   - Extract common patterns into utility functions or shared modules
   - Identify repeated business logic that should be centralized
   - Create generic, reusable implementations instead of specific one-off solutions
   - Suggest where dependency injection or composition could improve reusability

5. **Split long functions into smaller, focused functions**
   - Identify functions that exceed 30 lines of code
   - Break them down into smaller functions that each handle a single responsibility
   - Ensure each new function has a clear purpose and descriptive name
   - Maintain readability and logical flow while splitting

**For each simplification:**
- Explain what you're changing and why
- Ensure the refactoring maintains the same functionality
- Preserve error handling and edge cases
- Keep test coverage intact

Start by listing all files that need attention, then proceed file by file with specific recommendations.

---

Notes
- The main branch in develop in olymopus repo: git diff --name-only origin/develop...HEAD