# Feature Specification: Reviewed Import Refresh

**Input**: User description: "Refresh imported specifications through an explicit reviewed delta."

## User Scenarios & Testing

### User Story 1 - Review an imported specification change (Priority: P1)

A delivery lead can inspect a proposed import delta before an Intent Kit graph is changed.

**Why this priority**: Imported requirements must remain traceable without silent graph mutation.

**Independent Test**: Change a functional requirement, generate a proposal, and confirm the graph does not change until the reviewed proposal is explicitly applied.

**Acceptance Scenarios**:

1. **Given** an imported feature, **When** its specification changes, **Then** Intent Kit produces a reviewable update proposal.
2. **Given** a reviewed proposal, **When** the source or graph changes again, **Then** Intent Kit rejects the stale proposal.

## Requirements

### Functional Requirements

- **FR-001**: System MUST generate a deterministic source-and-graph delta before refreshing imported records.
- **FR-002**: System MUST preserve stable graph identifiers and locally maintained policy metadata for matching source records after an approved refresh.
- **FR-003**: System MUST record source digests, impact context, proof gaps, and explicit apply requirements in every synchronization proposal.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A reviewed proposal is the only path that updates an imported graph record.
- **SC-002**: A source change after review causes application to fail until a new proposal is generated.
