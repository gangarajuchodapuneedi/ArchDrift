# Architecture Decision Records (ADRs)

## Why ADRs Exist

When we intentionally change architecture rules or module dependencies, we write an ADR first. This captures:
- **What** changed and why
- **Who** made the decision
- **When** it was approved
- **What** the consequences are

ADRs help teams understand why architecture evolved and prevent accidental drift from becoming permanent.

## ADR Workflow

### 1. Create ADR in Proposed Status

When you want to change architecture (add a new module edge, remove a dependency, etc.):

1. Copy `000-template.md` to a new file: `001-your-change-name.md`
2. Fill in the template with your proposal
3. Set status to `Proposed`
4. Commit to your branch

### 2. Review in Pull Request

Include the ADR in your PR:
- Link to the ADR file in the PR description
- Explain how the PR implements the ADR
- Get team review on both code and architecture decision

### 3. Accept (Immutable)

Once approved:
1. Update ADR status to `Accepted`
2. Merge the PR
3. The ADR becomes immutable (don't edit it after acceptance)

### 4. If Changed Later: New ADR Supersedes Old

If you need to change an accepted ADR:
1. Create a new ADR (e.g., `002-update-to-new-approach.md`)
2. Reference the old ADR in the "Links" section
3. Set old ADR status to `Superseded`
4. Set new ADR status to `Accepted` after approval

## Linking ADRs to ArchDrift

When ArchDrift detects a `needs_review` classification (allowed edges changed), it means architecture evolved. For these changes:

1. **Require an ADR**: Add a check in your PR template or CI to require an ADR when `needs_review` drifts appear.
2. **Reference in PR**: Link the ADR in your PR description.
3. **Update Baseline**: After ADR is accepted, update `allowed_rules.json` and regenerate/approve baseline if needed.

### Example Workflow

1. PR introduces new edge: `ui` → `api` (previously forbidden)
2. ArchDrift detects `needs_review` classification
3. Author creates `001-ui-to-api-edge.md` with status `Proposed`
4. Team reviews ADR and PR together
5. ADR accepted → update `allowed_rules.json` → regenerate baseline
6. Merge PR

This keeps architecture changes intentional and documented.

