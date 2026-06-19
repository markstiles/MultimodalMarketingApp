# Feature Specification: Brand Kit Integration

**Feature Branch**: `005-brand-kit-integration`

**Created**: 2026-06-18

**Status**: Draft

**Input**: User description: "Brand Kit Integration — a backend capability that connects the marketing assistant to Sitecore AI Skills Brand Management and Brand Review APIs. When a user initiates a content authoring task, the system retrieves available published brand kits from the Sitecore organization, allows the user to select one, and loads the relevant brand kit sections into the assistant's context based on the active task type. The sections to load are determined by the task instruction overlay (Track B): component population tasks load Tone of Voice, Do's and Don'ts, and Grammar; image-related tasks load Visual Guidelines and Brand Context; general writing tasks load all sections. After content is generated, the user can optionally request a brand compliance review that evaluates the generated content against the loaded brand kit sections using the Brand Review API, returning a 1–5 compliance score with reasons and improvement suggestions at both section and subsection level. Only Published brand kits should be made available for selection. The capability is split across two tracks: Track A provides backend Python tool functions for brand kit listing, section retrieval, and brand review; Track B provides task instruction overlay markdown files that specify which sections to request for each task type."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Marketer Aligns a Content Task to a Brand Kit (Priority: P1)

A marketer is working on a content authoring task — writing page copy, populating a component, or drafting a campaign — and wants the assistant's output to align with their organization's brand standards. The assistant offers to load a brand kit at the start of the task. The marketer chooses from the list of available brand kits and confirms the selection. The assistant then loads the relevant brand guidelines for that task type and incorporates them into its content generation, so the marketer's output reflects their organization's voice, tone, and style without manually referencing a brand guide document.

**Why this priority**: Brand alignment is the primary reason this feature exists. Without it, the assistant generates generic content that may not match the organization's standards. All other brand-related capabilities (compliance review, section scoping) build on this baseline.

**Independent Test**: With at least one Published brand kit in the Sitecore organization, initiate a component population task, select the brand kit when prompted, and verify the assistant acknowledges the selection, names the kit, and confirms which guideline areas have been loaded for this task type.

**Acceptance Scenarios**:

1. **Given** a marketer begins a content authoring task, **When** the assistant offers brand alignment, **Then** the marketer sees a list of available Published brand kits by name and can select one or decline.
2. **Given** the marketer selects a brand kit, **When** the selection is confirmed, **Then** the assistant names the selected kit and confirms which guideline areas have been loaded for the active task type.
3. **Given** a brand kit is loaded, **When** the assistant generates content, **Then** the assistant uses the loaded brand guidelines and the marketer does not need to re-select the kit for follow-up messages in the same task.
4. **Given** no Published brand kits exist in the organization, **When** brand kit selection is offered, **Then** the marketer is informed that no brand kits are available and the task proceeds without brand context.

---

### User Story 2 - Marketer Reviews Generated Content for Brand Compliance (Priority: P2)

After the assistant has generated a draft — page copy, a component's text, a campaign headline — the marketer wants to know how well it aligns with their brand standards before approving it. They ask the assistant to review the content for brand compliance. The assistant evaluates the draft against the loaded brand kit and returns a compliance score for each guideline area, explains where the content falls short, and suggests specific improvements. The marketer uses this feedback to refine the content or accept it with confidence.

**Why this priority**: The compliance review transforms the brand kit from passive context into an active quality gate. It gives the marketer confidence to publish or actionable guidance to revise. It depends on brand kit loading (P1) being complete.

**Independent Test**: With a brand kit loaded and a piece of generated text in the conversation, ask the assistant to review the content for brand compliance and verify the response includes at least one section score (1–5), a plain-language reason, and an improvement suggestion.

**Acceptance Scenarios**:

1. **Given** a brand kit is loaded and content has been generated, **When** the marketer requests a brand compliance review, **Then** the assistant evaluates the content and returns results within 15 seconds.
2. **Given** a brand compliance review completes, **When** results are displayed, **Then** each evaluated guideline area shows a score from 1 to 5, a plain-language explanation, and at least one specific improvement suggestion.
3. **Given** a brand compliance review completes, **When** results are displayed, **Then** the marketer can see feedback at both the guideline area (section) level and the individual guideline (subsection) level where available.
4. **Given** the marketer requests a compliance review before any brand kit has been loaded, **When** the request is received, **Then** the assistant prompts the marketer to select a brand kit first rather than proceeding without one.

---

### User Story 3 - Correct Guidelines Are Scoped to the Active Task Type (Priority: P3)

A marketer working on component population should automatically see writing and tone guidelines loaded — not visual design guidelines. A marketer working on an image-related task should automatically see visual guidelines loaded. The right brand content is scoped to the task at hand without the marketer needing to configure which sections to load. This ensures the assistant gives focused, relevant guidance rather than surfacing the entire brand kit.

**Why this priority**: This scoping behavior makes the brand kit feel intelligent and task-appropriate. Without it, all tasks load the full kit, which can be noisy. It is a configuration capability maintained by product owners and does not require marketer intervention.

**Independent Test**: Initiate a component population task with a brand kit selected and confirm the assistant references writing and tone guidelines but not visual design guidelines. Then initiate an image-related task and confirm visual guidelines appear instead.

**Acceptance Scenarios**:

1. **Given** a marketer is performing a component population task and selects a brand kit, **When** brand guidelines load, **Then** the guidelines cover tone, writing style, and grammar — not visual design.
2. **Given** a marketer is performing an image-related task and selects a brand kit, **When** brand guidelines load, **Then** the guidelines cover visual standards and brand context — not grammar rules.
3. **Given** a task type has no specific brand section configuration defined, **When** a brand kit is loaded, **Then** all available brand kit sections are loaded by default.
4. **Given** a product owner updates the section configuration for a task type in its instruction overlay file, **When** a marketer next uses that task type, **Then** the updated configuration is applied without a code deployment.

---

### Edge Cases

- What happens when a brand kit section exists in Sitecore but has no content populated yet? The assistant should load the sections that do have content, inform the marketer that certain guideline areas are empty, and continue without them.
- What happens when the Sitecore brand content service is unavailable? The assistant must notify the marketer, offer to proceed without brand context, and not silently omit brand guidelines or return an error.
- What happens when the marketer requests a compliance review and the content is very short (a single sentence or a few words)? The review should still run; the assistant may note that scores may be less reliable for minimal content.
- What happens when the brand kit the marketer selected becomes unpublished in Sitecore during their session? The assistant should warn the marketer at the next brand-related interaction and offer to select an available replacement.
- What happens when the marketer declines brand kit selection at task start? The task proceeds without brand context; the option to load a brand kit should remain available throughout the conversation.
- What happens when a task type instruction overlay lists section names that do not match any sections in the selected brand kit? The unmatched sections are skipped silently and the assistant loads whatever sections do match.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST retrieve only Published brand kits when presenting brand kit options to the marketer; Draft, In Process, and Failed kits MUST NOT appear.
- **FR-002**: The system MUST display brand kit names — and descriptions where available — to help marketers identify the correct kit to select.
- **FR-003**: When a brand kit is selected, the system MUST load only the guideline sections relevant to the active task type, not all sections by default.
- **FR-004**: The mapping of task types to brand kit sections MUST be defined in instruction overlay files, not in application source code, so product owners can update them without a code deployment.
- **FR-005**: Loaded brand guidelines MUST be provided to the assistant as content context — clearly framed as brand standards — not as instructions that alter the assistant's behavior or identity.
- **FR-006**: The selected brand kit and its loaded guidelines MUST persist for the duration of the active task; the marketer MUST NOT need to re-select the brand kit for follow-up messages within the same task session.
- **FR-007**: The system MUST allow the marketer to optionally request a brand compliance review after content has been generated.
- **FR-008**: Brand compliance reviews MUST evaluate content against the guideline sections that were loaded for the active task, not the full brand kit.
- **FR-009**: Brand compliance review results MUST include, for each evaluated guideline area: a compliance score from 1 to 5, a plain-language explanation, and at least one specific improvement suggestion.
- **FR-010**: Brand compliance review results MUST be available at both the guideline area (section) level and the individual guideline (subsection) level where subsection data is returned.
- **FR-011**: The system MUST handle the absence of Published brand kits gracefully — informing the marketer clearly and allowing the task to continue without brand context.
- **FR-012**: The system MUST handle Sitecore brand service unavailability gracefully — notifying the marketer and offering to proceed without brand context rather than failing silently or crashing.

### Key Entities

- **BrandKit**: A Published Sitecore brand kit available for selection. Has a name, optional description, organizational owner, and status. Only Published status kits are surfaced.
- **BrandKitSection**: A guideline area within a brand kit (e.g., Tone of Voice, Do's and Don'ts, Visual Guidelines, Grammar Checklists, Brand Context). Contains one or more subsections with content.
- **BrandKitSubsection**: An individual guideline entry within a section. Has a name and a content value defining a specific brand rule or standard.
- **ActiveBrandContext**: The brand kit and specific subset of sections currently loaded for the active task session. Persists across messages within the same task without requiring re-selection.
- **BrandReviewResult**: The output of a compliance review. Contains per-section compliance scores (1–5), plain-language reasons, improvement suggestions, and per-subsection detail where available.
- **TaskSectionMapping**: The configuration — maintained in task instruction overlay files — that maps a task type to the brand kit sections it should load. Falls back to all sections when no mapping exists for the active task.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Marketers can select a brand kit and have guidelines confirmed as loaded within 15 seconds of initiating brand kit selection.
- **SC-002**: Brand compliance review results are returned and displayed within 15 seconds of the marketer requesting a review.
- **SC-003**: 100% of brand compliance review results include a plain-language explanation and at least one improvement suggestion alongside each section score — no score is ever returned without an explanation.
- **SC-004**: Marketers do not need to re-select or re-trigger brand kit loading when sending follow-up messages within the same content task.
- **SC-005**: When no Published brand kits are available, 100% of brand kit selection attempts produce a specific, human-readable message — never an empty list or silent failure.
- **SC-006**: A marketer performing a component population task sees only writing and tone guidelines loaded — not visual design guidelines — confirming task-appropriate section scoping is working.

## Assumptions

- The Sitecore organization identifier is available from the marketer's authenticated session and does not need to be entered manually.
- Brand kit section names in Sitecore (e.g., "Tone of Voice", "Do's and Don'ts", "Visual Guidelines") are stable enough to serve as matching keys in task instruction overlays; if section names are found to vary across organizations, a future enhancement may introduce ID-based matching.
- A marketer uses at most one brand kit per task session; switching brand kits mid-task is out of scope for this spec.
- Brand compliance review is scoped to text content in this spec; image and document compliance review is a planned future enhancement.
- The typical brand compliance review response time is under 10 seconds; streaming compliance results are not needed.
- Instruction overlay files for task-to-section mappings are authored and maintained by product owners; no in-app editing UI for them is in scope.
- Sitecore brand content service authentication follows the same approach used by other Sitecore integrations already in the project; no new credential management is introduced.
- Brand kit section content is read-only from the assistant's perspective; this spec covers retrieval only. Writing or modifying brand kit content is out of scope and is covered by spec 006.
