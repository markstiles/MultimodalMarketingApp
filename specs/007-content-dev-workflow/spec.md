# Feature Specification: Content Development Workflow

**Feature Branch**: `007-content-dev-workflow`

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "A guided, intent-driven multi-phase workflow that helps marketers develop content strategy and execution the way SpecKit guides a developer through building an app. The workflow moves through six phases: Research → Strategy → Structure → Content → Variation/Personalization/Experimentation → Execution. The assistant detects content development intent conversationally and guides the marketer through each phase. At the end of each phase, a structured artifact (brief, strategy document, plan) is generated, reviewed by the marketer, and uploaded to the Sitecore media library at a conventional path: /sitecore/media library/Project/{tenant-name}/{site-name}/Content Strategy/{phase}/. The assistant detects existing artifacts in the media library to determine which phase the marketer should work on next. If phase N-1 artifacts are more than 12 months old when the marketer begins phase N, the assistant surfaces a staleness warning before proceeding. Scope covers larger strategy work: full content strategies, editorial calendars, campaign briefs, competitive analysis — not just page-level copy. There is no dedicated brief API; all artifacts are uploaded to the media library."

## Clarifications

### Session 2026-06-19

- Q: Should the artifact filename within each phase folder be fixed/predictable or marketer-controlled? → A: Fixed canonical filename per phase — the assistant always writes and looks for a canonical name.
- Q: In the Research phase, does the assistant query live external data or conduct a conversational questionnaire? → A: Both in sequence — run available data tools (GA4, SEO, competitive analysis) first, then ask the marketer to fill in context the tools cannot answer.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Marketer Starts a New Content Development Project (Priority: P1)

A marketer wants to develop content for their site but isn't sure where to start. They ask the assistant to help them build a content strategy or create a content plan. The assistant detects the intent, scans the media library for any existing project artifacts for this site, and finds none. It explains the six-phase workflow, proposes starting with Research, and walks the marketer through gathering competitive intelligence, audience insights, and existing site performance data. By the end of the session, the marketer has a Research Brief that is reviewed, approved, and saved to the media library — their content project is now officially underway.

**Why this priority**: This is the entry point for all content development work. Every subsequent phase depends on the project being initiated and research being captured. Without this, the rest of the workflow has nothing to build on.

**Independent Test**: With no existing content strategy artifacts for a site, ask the assistant to help create a content plan. Verify the assistant proposes starting with Research, walks through the phase activities, produces a Research Brief for review, and — after confirmation — saves the artifact to `/sitecore/media library/Project/{tenant}/{site}/Content Strategy/Research/`.

**Acceptance Scenarios**:

1. **Given** no existing content strategy artifacts for the active site, **When** the marketer asks the assistant to help develop content or create a strategy, **Then** the assistant explains the six-phase workflow and proposes starting at Research.
2. **Given** the marketer agrees to begin, **When** the Research phase starts, **Then** the assistant first runs available data tools (site performance analytics, SEO analysis, competitive analysis) to gather objective data, then asks the marketer targeted questions to fill in context the tools cannot answer (audience segments, campaign goals, brand positioning) — before generating any artifact.
3. **Given** the marketer has answered the Research questions, **When** the assistant generates the Research Brief, **Then** it presents the full artifact for review before asking for confirmation to save.
4. **Given** the marketer approves the Research Brief, **When** the artifact is saved, **Then** it is uploaded to the correct media library path and the assistant confirms the save and explains that the next phase is Strategy.
5. **Given** the marketer declines or requests revisions to the Research Brief, **When** feedback is provided, **Then** the assistant revises the artifact and presents the updated version for review — no artifact is saved until the marketer explicitly approves.

---

### User Story 2 - Marketer Resumes an In-Progress Content Project (Priority: P2)

A marketer completed their Research phase two weeks ago and returns to the assistant ready to develop their content strategy. They ask the assistant to continue their content project. The assistant scans the media library, finds the Research Brief, confirms it is recent, presents a project status summary, and offers to begin the Strategy phase — picking up exactly where the marketer left off without any manual configuration.

**Why this priority**: Real content development happens across multiple sessions over days or weeks. The workflow only delivers value if it reliably resumes. Phase detection and status awareness are what distinguish this from a simple content generation tool.

**Independent Test**: With a Research Brief already saved in the media library for a site, start a new assistant session and ask to continue the content project. Verify the assistant detects the existing artifact, presents a phase status summary, and offers to proceed to Strategy without the marketer needing to explain their history.

**Acceptance Scenarios**:

1. **Given** one or more phase artifacts exist in the media library for the active site, **When** the marketer asks to continue their content project, **Then** the assistant presents a project status overview listing which phases have artifacts and their approximate age.
2. **Given** the project status is presented, **When** the marketer confirms they want to continue, **Then** the assistant proposes the next incomplete phase and begins it without requiring the marketer to re-explain prior work.
3. **Given** a phase artifact is found but the preceding phase's artifact is more than 12 months old, **When** the marketer attempts to advance to the next phase, **Then** the assistant surfaces a staleness warning — explaining that the prior phase's artifact may be outdated — and offers the marketer the choice to proceed anyway, return to the prior phase, or review the stale artifact first.
4. **Given** the marketer chooses to review a stale artifact, **When** they request it, **Then** the assistant retrieves and summarizes the artifact's key findings so the marketer can decide whether to revise it.

---

### User Story 3 - Marketer Works Through a Strategy Phase (Priority: P2)

A marketer's Research Brief is complete. They ask the assistant to develop their content strategy. The assistant references the Research Brief's findings — audience insights, competitive gaps, content opportunities — and guides the marketer through defining content goals, KPIs, messaging pillars, and editorial themes. The resulting Content Strategy Document ties back to the research, is presented for review, revised if needed, and saved to the media library — ready to drive the Structure phase.

**Why this priority**: The middle phases (Strategy, Structure, Content) are where the majority of the workflow value is delivered. Strategy in particular is the phase that gives the rest of the workflow direction. It shares P2 priority with Resume because both are essential for a working multi-session workflow.

**Independent Test**: With a Research Brief in the media library, ask the assistant to build a content strategy. Verify the assistant references the Research Brief's findings, guides through goal-setting and messaging, produces a Content Strategy Document that explicitly ties to the research, and saves it after marketer approval.

**Acceptance Scenarios**:

1. **Given** a Research Brief exists, **When** the Strategy phase begins, **Then** the assistant summarizes the relevant Research findings before asking Strategy questions — the marketer does not need to re-input research data.
2. **Given** the marketer answers the Strategy questions, **When** the Content Strategy Document is generated, **Then** it explicitly references the audience, competitive context, and opportunities identified in the Research Brief.
3. **Given** the Content Strategy Document is presented, **When** the marketer requests a revision to a specific section, **Then** the assistant updates that section and re-presents the document — the marketer can revise as many times as needed before approving.
4. **Given** the marketer approves the Content Strategy Document, **When** it is saved, **Then** the assistant confirms the save, notes the media library path, and explains that the next phase is Structure.

---

### User Story 4 - Marketer Skips or Returns to a Phase (Priority: P3)

An experienced marketer already has a content strategy from a prior exercise and only needs help with the Structure and Content phases. They want to skip Research and Strategy and start at Structure. The assistant warns them that downstream phases typically build on earlier ones, but allows them to proceed at their own discretion. Similarly, a marketer who wants to revisit their Strategy after new competitive information emerges can return to the Strategy phase, update the artifact, and continue forward.

**Why this priority**: The workflow must be a guide, not a gate. Requiring every phase in strict sequence would frustrate experienced marketers who have existing strategy work. Flexibility is important, but the quality warnings are how the assistant earns trust.

**Independent Test**: Ask the assistant to skip directly to the Structure phase with no prior artifacts. Verify the assistant surfaces a quality warning but proceeds when the marketer confirms. Then ask the assistant to go back and complete the Research phase — verify it does so and updates the project status accordingly.

**Acceptance Scenarios**:

1. **Given** no Research or Strategy artifacts exist, **When** a marketer asks to skip directly to Structure, **Then** the assistant warns that Structure typically builds on Research and Strategy findings and asks for confirmation before proceeding without them.
2. **Given** the marketer confirms they want to skip, **When** the Structure phase begins, **Then** the assistant proceeds and notes in its questions that it will need additional context that would normally come from prior phases.
3. **Given** a previously completed phase artifact exists, **When** the marketer asks to return to and revise that phase, **Then** the assistant retrieves the existing artifact, presents it for review, and allows the marketer to update it — saving the revised artifact at the same media library path.

---

### Edge Cases

- What if the media library path for the content project does not yet exist? The assistant creates the folder structure when saving the first artifact for a site.
- What if an artifact is found in the media library but cannot be read or extracted? The assistant treats the phase as having an unreadable artifact, informs the marketer, and offers to regenerate it from scratch.
- What if the marketer has multiple active content projects for the same site? The current scope assumes one active content development project per site. The marketer can archive the existing artifacts and start fresh, or the assistant will work with the most recently modified artifacts.
- What if the Execution phase completes work directly in Sitecore rather than through the assistant? The assistant cannot detect Sitecore-side changes it did not make; the marketer can confirm the Execution phase as complete manually, and the assistant saves an Execution Checklist artifact at that point.
- What if the marketer provides conflicting direction during a phase that contradicts an earlier phase's artifact? The assistant surfaces the conflict, references the relevant prior artifact, and asks the marketer to resolve it before generating the phase output.
- What if the tenant or site name cannot be resolved from the session context? The assistant asks the marketer to confirm the site name before attempting any media library operations for this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect content development intent from natural conversation and activate the guided workflow without requiring a specific command or keyword.
- **FR-002**: At the start of any content development interaction, the system MUST scan the conventional media library path for the active site to detect existing phase artifacts and their modification dates.
- **FR-003**: The system MUST present a project status overview — listing each phase, whether an artifact exists, and the artifact's approximate age — before beginning any phase work in a session where prior artifacts are found.
- **FR-004**: The system MUST guide the marketer through each phase conversationally, gathering inputs before generating an artifact; it MUST NOT generate an artifact without first gathering the phase-appropriate inputs.
- **FR-005**: Phase artifacts MUST incorporate findings from prior completed phases where relevant; the assistant MUST reference prior artifacts rather than asking the marketer to re-input information already captured.
- **FR-006**: At the end of each phase, the system MUST present the generated artifact in full for marketer review before offering to save it.
- **FR-007**: The marketer MUST be able to request revisions to a generated artifact any number of times before approving; the system MUST NOT save the artifact until the marketer explicitly confirms.
- **FR-008**: All artifact uploads to the media library MUST require explicit marketer confirmation and MUST be saved to a fixed, canonical path: `/sitecore/media library/Project/{tenant-name}/{site-name}/Content Strategy/{phase}/{canonical-filename}`. Each phase has exactly one canonical filename (e.g., `research-brief.docx` for the Research phase); the assistant always writes to and reads from this fixed path — the marketer does not control the filename.
- **FR-009**: The system MUST detect when phase N-1 artifacts are more than 12 months old at the time the marketer attempts to begin phase N, and MUST surface a staleness warning before proceeding.
- **FR-010**: The staleness warning MUST offer the marketer three options: proceed to phase N anyway, return to phase N-1 to revise the stale artifact, or review the stale artifact's contents before deciding.
- **FR-011**: The system MUST allow the marketer to skip phases, with a warning about downstream quality impact; skipping MUST require marketer confirmation and MUST NOT be the default path.
- **FR-012**: The system MUST allow the marketer to return to any previously completed phase and revise its artifact; a revised artifact MUST overwrite the previous version at the same media library path after confirmation.
- **FR-013**: If the media library folder for a phase does not exist, the system MUST create it before saving the artifact.
- **FR-014**: The Execution phase MUST produce an Execution Checklist artifact summarizing the Sitecore content actions to be taken, in addition to guiding the actual content creation steps using the assistant's existing content authoring tools.
- **FR-015**: The system MUST resolve tenant name and site name from the active Sitecore session context; if resolution fails, the system MUST ask the marketer to confirm the site before performing media library operations.
- **FR-016**: During the Research phase, the system MUST attempt to gather objective data via available analysis tools (site analytics, SEO, competitive analysis) before presenting marketer questions; if any tool is unavailable or returns no data, the system MUST note the gap and proceed with marketer input alone — the Research phase MUST NOT be blocked by tool unavailability.

### Key Entities

- **ContentProject**: A named content development initiative scoped to a specific tenant and site. Defined by the presence of at least one phase artifact at the conventional media library path. Has no explicit database record — the media library artifacts are the source of truth.
- **PhaseArtifact**: A structured document produced at the end of a workflow phase. Has a phase type, a fixed canonical media library path, a creation date, a modification date, and a staleness status (current or stale, where stale = older than 12 months). Each phase has exactly one canonical filename; the artifact is overwritten at the same fixed path on revision. Saved in the Sitecore media library.
- **WorkflowPhase**: One of the six content development phases (Research, Strategy, Structure, Content, Variation, Execution). Each phase has a defined set of input questions, expected artifact output, and dependency on prior phases.
- **PhaseStatus**: The computed state of a phase for a content project — Not Started (no artifact), In Progress (session active), Complete (artifact saved), or Stale (artifact exists but is older than 12 months).
- **ContentProjectSummary**: The assistant's representation of a content project's current state, derived by scanning the media library. Contains the list of phases with their statuses and artifact ages. Presented to the marketer at the start of a content development session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A marketer with no existing project artifacts can complete the Research phase and have a Research Brief saved to the media library within a single conversation session.
- **SC-002**: When returning to an existing project, the assistant identifies the current phase and presents a project status overview within the first response — the marketer does not need to explain their history.
- **SC-003**: 100% of phase artifact saves require explicit marketer confirmation — no artifact reaches the media library without approval.
- **SC-004**: 100% of attempts to advance to a phase where the preceding phase artifact is more than 12 months old surface a staleness warning before any phase work begins.
- **SC-005**: Generated phase artifacts incorporate references to prior phases' findings — a Content Strategy Document produced after a Research Brief always references the audience and competitive context from the brief.
- **SC-006**: A marketer can resume a content project across separate sessions with no loss of progress — the media library artifacts serve as the complete project record.
- **SC-007**: Phase skip requests always result in a quality warning being shown before the marketer can confirm; the marketer is never silently advanced past a phase.

## Assumptions

- Tenant name and site name are available from the active Sitecore session context (iframe-injected in production, environment variable in local mode); the marketer does not need to specify them manually in normal use.
- Phase artifacts are stored as Word documents (`.docx`) with fixed canonical filenames per phase; this format is readable by the document extraction capability (spec 004) and familiar to business users for review and editing outside the assistant. The canonical names for the six phases are: Research → `research-brief.docx`, Strategy → `content-strategy.docx`, Structure → `content-structure.docx`, Content → `content-plan.docx`, Variation → `variation-plan.docx`, Execution → `execution-checklist.docx`. These filenames are the contract; the assistant always reads from and writes to these exact names within the phase folder.
- The 12-month staleness threshold applies uniformly across all phases in v1; phase-specific thresholds are a future enhancement.
- The media library folder structure (`/sitecore/media library/Project/{tenant}/{site}/Content Strategy/{phase}/`) is created by the assistant on first use; pre-existing folder structure at this path is not assumed.
- A single active content project per site is in scope for v1; multiple concurrent projects for the same site are out of scope and would require a project-naming or subdirectory convention.
- The Execution phase differs from other phases: it produces an Execution Checklist artifact but also triggers actual Sitecore content operations (page creation, component population) using the assistant's existing authoring tools, each with their own confirmation gates.
- Phase artifacts from prior sessions are retrieved via media library search at the conventional path; the assistant reads artifact metadata (name, modified date) to determine phase status without necessarily downloading and extracting every document on each session start.
- Brand kit alignment (spec 005) is incorporated into the Strategy and Content phases where a brand kit has been selected; the workflow does not mandate brand kit use but surfaces the option.
- The Research phase uses available analysis tools (site analytics, SEO, competitive analysis) as primary data sources before asking the marketer questions. If these tools are not available or not yet implemented, the Research phase degrades gracefully to a pure conversational questionnaire — tool availability does not block the workflow.
- The workflow does not replace ad-hoc content generation in the assistant; marketers can still generate one-off pages or components outside the workflow. The workflow is offered when multi-phase content development intent is detected.
