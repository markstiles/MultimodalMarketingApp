# Feature Specification: Marketing Pipeline

**Feature**: 012-marketing-pipeline  
**Date**: 2026-06-21  
**Status**: Draft

---

## Overview

Replace the generic six-phase content workflow with a purpose-built marketing pipeline that guides marketers from market research through campaign execution. The pipeline is grounded in real market data (via AI-assisted web research), anchored to the brand's voice, and structured to produce actionable campaign deliverables.

The five phases are:

1. **Research** — Competitive landscape, market fit, audience data (AI web search on marketer's behalf + marketer input)
2. **Strategy** — Positioning, target audience, strategic goals
3. **Brand Voice** — Connect or import brand guidelines via Sitecore Stream brand kit
4. **Brief** — Campaign brief bridging strategy and execution; also the entry point for marketers who already have a brief
5. **Campaign** — Three tactics: Funnel & Persona Blueprint, Personalization Rules, A/B Testing Plan

Marketers may enter the workflow at any phase. Each completed phase produces an artifact stored in the Sitecore media library and feeds into downstream phases automatically. Re-uploading or regenerating a phase artifact overwrites the previous version.

---

## Actors

- **Marketer** — primary user; may be a campaign strategist, brand manager, or content lead
- **System / Assistant** — guides the workflow, performs web research on behalf of the marketer, reads and writes Sitecore brand kits and media library artifacts

---

## User Stories

### US1 — Research with AI-Assisted Web Search

As a marketer, I want to gather competitive intelligence and market data before building a strategy, so that my decisions are grounded in real market context rather than assumptions.

**Acceptance criteria**:
- The assistant asks whether I already have competitive analysis data or would like it to research on my behalf
- If I choose AI research, the assistant searches the web for competitor positioning, market trends, and audience pain points relevant to my product/category
- I can provide competitor names, and the assistant enriches this with search results
- I can also provide my own data files or notes to supplement the AI research
- The research findings are synthesized into a Research Brief artifact
- The Research Brief is saved to the Sitecore media library after my explicit approval

### US2 — Marketing Strategy

As a marketer, I want to define my strategic positioning and goals informed by the Research Brief, so that all downstream content is aligned to business outcomes.

**Acceptance criteria**:
- The assistant reads the Research Brief (if it exists) and surfaces relevant findings as context without requiring me to re-enter them
- The assistant helps me define: target audience, positioning, differentiation, and 12-month goals
- The strategy document includes KPIs and success metrics
- The Marketing Strategy artifact is saved after my explicit approval

### US3 — Brand Voice via Sitecore Stream Brand Kit

As a marketer, I want to connect my brand guidelines to the pipeline so that all content outputs use the correct tone, language, and visual direction.

**Acceptance criteria**:
- The assistant checks the Sitecore Stream organization for existing brand kits
- If a matching brand kit exists, I can select it and the assistant reads its tone, context, and guidelines
- If no brand kit exists or I want to import new guidelines, I can upload brand documents (PDF) which are added to the brand kit
- The assistant reads the relevant brand kit sections (Brand Context, Tone of Voice, Do's and Don'ts) and produces a Brand Voice Summary artifact
- The Brand Voice Summary is saved to the Sitecore media library after my explicit approval

### US4 — Campaign Brief (and Flexible Entry Point)

As a marketer, I want to create or import a campaign brief, so that I have a focused document that bridges strategy and campaign execution.

**Acceptance criteria**:
- At the start of any session, if the marketer states they already have a brief, the workflow skips or fast-tracks earlier phases
- The brief is produced from strategy + brand voice context if those phases exist
- If entering at the Brief phase without prior phases, the assistant asks targeted questions to gather the missing strategic and brand context
- The Campaign Brief artifact is saved to the Sitecore media library after my explicit approval

### US5 — Campaign Tactics

As a marketer, I want a set of campaign deliverables covering funnel planning, personalization, and A/B testing, so that my campaign has a coherent execution plan across all tactics.

**Acceptance criteria**:
- The campaign phase produces three distinct tactic documents, each built from the Campaign Brief
- **Funnel & Persona Blueprint**: Maps audience segments to funnel stages and content touchpoints
- **Personalization Rules**: Defines which audience signals trigger which content variants
- **A/B Testing Plan**: Specifies hypotheses, variants, success metrics, and audience splits
- Each tactic document can be produced independently or together in one session
- All three tactic artifacts are saved to the Sitecore media library after explicit approval

### US6 — Flexible Entry Point

As a marketer, I want to start the pipeline at any phase, so that I don't have to repeat work I've already done.

**Acceptance criteria**:
- The assistant scans existing phase artifacts at the start of each session and presents a project status overview
- If I state I already have a brief, strategy, or other artifact, the assistant skips earlier phases
- If I skip a phase, the assistant asks compensating questions to gather context that would normally come from the skipped phase
- The assistant warns me when I skip a phase that would have informed a downstream phase, but does not block me

### US7 — Overwrite Resilience

As a marketer, I want to regenerate or update any phase artifact without creating duplicates, so that the media library always reflects the current state of my campaign thinking.

**Acceptance criteria**:
- Saving a phase artifact when one already exists at the same path silently overwrites it
- The assistant confirms after save: "Updated [phase name] artifact — previous version replaced"
- If the save fails, the assistant shows a specific error and offers retry or skip options

---

## Functional Requirements

### FR-001: Phase model
The pipeline has exactly five phases in this order: Research, Strategy, Brand Voice, Brief, Campaign. Each phase has a canonical artifact filename and a designated media library folder.

### FR-002: Session start scan
At the start of every marketing pipeline session, call `scan_marketing_project_status` to check all five phase artifacts and determine the next recommended phase.

### FR-003: Research — intent check
Before gathering any research data, the assistant asks: "Do you already have competitive analysis and market data, or would you like me to research your market and competitors?" The marketer's answer determines whether the assistant performs web searches.

### FR-004: Research — web search
When the marketer wants AI-assisted research, the assistant uses web search to gather:
- Competitor positioning and content strategy (requires competitor names from marketer)
- Market size, trends, and audience pain points for the product category
- Buying behavior signals relevant to the product
Web search results are synthesized into the Research Brief, not dumped verbatim.

### FR-005: Brand Voice — brand kit lookup
At the start of the Brand Voice phase, call `list_brand_kits` against the Sitecore Stream organization. Present any matching kits for the marketer to select. If the marketer's brand kit is not listed, offer to create one and import their brand documents.

### FR-006: Brand Voice — document import
When importing brand documents, accept PDF files from the marketer and upload them to the brand kit via the Document Management API. After upload, the assistant reads the brand kit sections to produce the Brand Voice Summary.

### FR-007: Brief — entry point detection
If a marketer states (in any phrasing) that they already have a brief, activate the Brief entry point: skip Research, Strategy, and Brand Voice, but ask compensating questions if the brief doesn't cover audience, positioning, or brand voice.

### FR-008: Campaign — tactic selection
The Campaign phase offers three tactic documents. The marketer selects which ones to produce in the current session. Each tactic reads the Campaign Brief for context.

### FR-009: Confirmation gate (all phases)
No phase artifact may be saved without explicit marketer approval. Present the full draft artifact before asking for approval. After approval, call `save_phase_artifact`. If the marketer requests changes, revise and re-present before saving.

### FR-010: Overwrite on re-save
When saving a phase artifact that already exists, pass `overwriteExisting: true` in the upload mutation. After a successful overwrite, confirm with the updated path and note that the previous version was replaced.

### FR-011: Skip flow
When a marketer skips a phase, warn about downstream quality impact, then proceed after confirmation. Add compensating questions in the phase that would have consumed the skipped artifact.

### FR-012: Brand review on content
When generating content for the Brief or Campaign phases, if a brand kit is linked for this project, optionally run a brand compliance review and surface the score and suggestions to the marketer.

---

## Out of Scope (v1)

- Multi-campaign tracking (one active campaign per site)
- Scheduling or publishing content directly (out of scope for this pipeline)
- Image generation or media creation
- Integration with external ad platforms (Google Ads, Meta, etc.)
- Approval workflow routing to other team members

---

## Success Criteria

### Measurable Outcomes

1. A marketer can go from zero context to a saved Campaign Brief in a single session without external tools
2. AI web research reduces the time to complete the Research phase compared to manual competitive analysis
3. All five phase artifacts are findable in the Sitecore media library at predictable paths after completion
4. Marketers who already have a brief can reach the Campaign phase in under 5 minutes without being forced through Research, Strategy, and Brand Voice

### Quality Gates

- No phase artifact is written without explicit marketer confirmation (constitution Principle I)
- No web searches are run without the marketer requesting them (FR-003)
- No brand documents are uploaded to Sitecore Stream without explicit marketer confirmation
- Phase context flows forward automatically — marketers never re-enter data captured in a prior phase

---

## Key Entities

| Entity | Description |
|--------|-------------|
| `MarketingProject` | Per-site collection of phase artifacts; state derived from media library scan |
| `ResearchBrief` | Research phase artifact; contains competitive, market, and audience findings |
| `MarketingStrategy` | Strategy phase artifact; positioning, goals, KPIs |
| `BrandVoiceSummary` | Brand Voice phase artifact; distilled brand kit: tone, context, do/don'ts |
| `CampaignBrief` | Brief phase artifact; campaign focus, audience, messaging hierarchy |
| `CampaignPlan` | Campaign phase artifact; contains one or more tactic documents |
| `BrandKit` | Sitecore Stream brand kit; managed via Brand Management API |
| `BrandDocument` | PDF uploaded to a brand kit; managed via Document Management API |

---

## New Infrastructure Requirements

### New environment variables

| Variable | Purpose |
|----------|---------|
| `TAVILY_API_KEY` | Web search API key (already set) |
| `SITECORE_ORGANIZATION_ID` | Required for Brand Management and Document Management API calls |

### New external APIs

| API | Usage |
|-----|-------|
| Tavily Search | AI web search for Research phase competitive analysis |
| Sitecore Stream Brand Management API (`edge-platform.sitecorecloud.io/stream/ai-brands-api`) | List, create, and read brand kits and their sections |
| Sitecore Stream Document Management API (`edge-platform.sitecorecloud.io/stream/ai-document-api`) | Upload brand documents (PDFs) to brand kits |
| Sitecore Stream Brand Review API (`edge-platform.sitecorecloud.io/stream/ai-skills-api`) | Score content against brand kit guidelines |

---

## Assumptions

- The Sitecore Stream organization has the same API credentials as the existing CM automation credentials (`SITECORE_CLIENT_ID_AUTOMATION` / `SITECORE_CLIENT_SECRET_AUTOMATION`)
- Brand documents uploaded via the Document Management API are PDFs (the API supports PDF and plain text)
- The `SITECORE_ORGANIZATION_ID` is stable per deployment and does not change between sessions
- One brand kit per site is the common case; if multiple exist, the marketer selects which to use
- Web search results are used to inform the research artifact, not stored raw

---

## Clarifications

### Session 2026-06-21

- Q: Should this replace the six-phase workflow (007) entirely, or run alongside it? → A: Replace it entirely; the new five-phase marketing pipeline supersedes the old generic workflow
- Q: Web search provider? → A: Tavily; `TAVILY_API_KEY` already set in environment
- Q: Brand Voice — write path? → A: Yes, the Brand Management and Document Management APIs both support writes; use them to create brand kits and import brand documents as PDFs
- Q: Entry point flexibility? → A: Yes; marketers may enter at any phase. Brief is the most common secondary entry point. Research, Strategy, and Brand Voice are skippable with compensating questions
- Q: Overwrite behavior? → A: Always overwrite; the upload mutation already passes `overwriteExisting: true`
