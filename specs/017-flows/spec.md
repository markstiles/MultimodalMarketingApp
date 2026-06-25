# Spec: Flows & Variants

## Overview

Expose Sitecore XM Cloud Flows (personalization-as-code rules attached to a page) and their variants through the marketing assistant. Flows define which content variant a visitor sees under a given condition; variants are the individual content branches within a flow.

This spec covers read-only access to flow definitions and variant lookup, plus the ability to configure (set up) a variant on a page component via the Agent API.

## User Stories

### US1 — Browse Page Flows

**As a** marketer, **I want to** see the flows configured on a given page **so that** I understand what personalization or variant logic is active.

**Acceptance criteria**:
- Given a page ID, I can list all flow definitions attached to that page
- Each flow shows its name, ID, and the number of variants it contains
- I can retrieve the full definition of a single flow including its condition rules and variant IDs

### US2 — Configure a Variant

**As a** marketer, **I want to** set up or update which content variant a flow delivers to a specific audience segment **so that** I can adjust personalization without leaving the chat interface.

**Acceptance criteria**:
- I can set up a variant on a flow using natural language ("set the hero banner to the summer variant for mobile visitors")
- The assistant confirms the change before calling any write API
- I can retrieve the current state of a specific variant after the change

## Out of Scope

- Creating or deleting flow definitions (flows are authored in the XM Cloud interface)
- Reporting on variant performance or analytics
- Condition template management (covered in spec 016)
