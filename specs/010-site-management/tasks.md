# Tasks: Guided Site & Collection Management

**Input**: Design documents from `specs/010-site-management/`

**Prerequisites**: spec.md ✅

**Organization**: Phase 1 covers all site management tools that have been implemented. Phase 2 adds Agent API operations that are not yet built.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)

---

## Phase 1: Site Management Tools (Implemented)

**Purpose**: All tools in this phase are already registered in `backend/app/clients/tools.py` and implemented in `backend/app/services/sites_service.py` and `backend/app/clients/sites.py`.

- [X] T001 [P] Implement `get_site_context` @tool — resolves site name and collection for a given site_id; `backend/app/clients/sites.py`
- [X] T002 [P] Implement `list_all_sites` @tool — returns all sites in the active environment; `backend/app/clients/sites.py`
- [X] T003 [P] Implement `list_site_collections` @tool — returns all site collections; `backend/app/clients/sites.py`
- [X] T004 [P] Implement `create_site_collection` @tool — creates a new site collection; `backend/app/clients/sites.py`
- [X] T005 [P] Implement `get_site_templates` @tool — returns available site templates; `backend/app/clients/sites.py`
- [X] T006 [P] Implement `get_environment_languages` @tool — returns languages available in the environment; `backend/app/clients/sites.py`
- [X] T007 [P] Implement `validate_site_name` @tool — validates a proposed site name against Sitecore naming rules; `backend/app/clients/sites.py`
- [X] T008 [P] Implement `create_marketing_site` @tool — creates a new site within a collection; `backend/app/clients/sites.py`
- [X] T009 [P] Implement `delete_marketing_site` @tool — deletes an existing site; `backend/app/clients/sites.py`
- [X] T010 [P] Implement `list_site_languages` @tool — returns languages configured for a site; `backend/app/clients/sites.py`
- [X] T011 [P] Implement `add_language_to_site` @tool — adds a language to an existing site; `backend/app/clients/sites.py`
- [X] T012 [P] Implement `set_fallback_language` @tool — sets the fallback language for a site; `backend/app/clients/sites.py`
- [X] T013 [P] Implement `remove_language_from_site` @tool — removes a language from a site; `backend/app/clients/sites.py`
- [X] T014 Register all Phase 1 tools in `backend/app/clients/tools.py`

---

## Phase 2: Agent API Site Operations

> Job operations (get_job, list_jobs, revert_job) use the Sitecore Agent API. They allow the assistant to track and undo async operations initiated by other tools.

- [ ] T015 [P] Add `get_site_id_from_item` @tool — Agent API `GET /api/v1/sites/site-id-from-item/{itemId}`; reverse lookup to find which site owns a given content item ID; add service function to `backend/app/services/sites_service.py` and register in `backend/app/clients/tools.py`
- [ ] T016 [P] Add `get_job` @tool — Agent API `GET /api/v1/jobs/{jobId}`; retrieves status of an async job; add service function to `backend/app/services/sites_service.py` and register in `backend/app/clients/tools.py`
- [ ] T017 [P] Add `list_jobs` @tool — Agent API `GET /api/v1/jobs`; lists recent async jobs; add service function to `backend/app/services/sites_service.py` and register in `backend/app/clients/tools.py`
- [ ] T018 Add `revert_job` @tool — Agent API `POST /api/v1/jobs/{jobId}/revert`; reverts the changes made by an async job (undo); add service function to `backend/app/services/sites_service.py` and register in `backend/app/clients/tools.py`
