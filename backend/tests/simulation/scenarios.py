"""Headless simulation scenario registry.

Each SimScenario defines one marketer workflow test.  The scenario_prompt is
fed to DriverLLM, which simulates the marketer.  required_tools lists the tool
names that MUST appear in the run's tool-call trace for the scenario to pass.

This file is also the canonical reference for developer-agent validation:
run any scenario via the CLI with:

    python -m scripts.headless_run --scenario <id> --verbose

Prerequisites (live environment):
    LLM_API_KEY       -OpenAI-compatible key for both pipeline LLM and driver LLM
    DATABASE_URL      -PostgreSQL connection string
    HEADLESS_SITE_ID  -real Sitecore XM Cloud site ID
    HEADLESS_PAGE_ID  -any valid page ID on that site
    SITECORE_CM_HOST, SITECORE_AGENTS_API_BASE_URL, AUTHOR_APP_ID,
    AUTHOR_APP_CLIENT_CREDENTIALS, SITECORE_ORGANIZATION_ID
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SimScenario:
    id: str
    name: str
    description: str
    scenario_prompt: str
    max_turns: int = 20
    required_tools: frozenset[str] = field(default_factory=frozenset)
    saves_artifact: bool = False
    files_source: str | None = None


# ─── Scenario definitions ────────────────────────────────────────────────────

SCENARIOS: dict[str, SimScenario] = {}


def _reg(s: SimScenario) -> SimScenario:
    SCENARIOS[s.id] = s
    return s


S01_SESSION_START = _reg(SimScenario(
    id="session-start",
    name="Session Start -Pipeline Status Scan",
    description=(
        "Verifies that the assistant always opens by calling scan_content_project_status "
        "and returns a readable phase status summary before offering to help."
    ),
    scenario_prompt="""\
You work for Acme Corp, a B2B SaaS company that makes project management software
for construction teams. You have just opened the AI marketing assistant for the
first time this week and want to know where your marketing pipeline stands.

Your goal: Ask the assistant to show you the current status of the marketing
pipeline for your site. Review the phase status table it returns and confirm you
can see which phases are complete, in-progress, or not started.

Your scenario is complete once the assistant has shown you a pipeline status
summary listing phases with their completion state.
""",
    max_turns=5,
    required_tools=frozenset({"scan_content_project_status"}),
    saves_artifact=False,
))

S02_RESEARCH_FULL = _reg(SimScenario(
    id="research-full",
    name="Research Phase -AI Web Research from Scratch",
    description=(
        "End-to-end Research phase: marketer provides context, assistant runs web "
        "search queries, synthesizes a Research Brief, gets approval, and saves it "
        "to the Sitecore media library."
    ),
    scenario_prompt="""\
You work for Acme Corp, a B2B SaaS company that makes project management software
for construction teams. You're starting a new Q3 campaign targeting mid-market
construction firms with 50-500 employees.

Your goal: Complete the Research phase and save a Research Brief to Sitecore.

Background you know when asked:
- Product category: construction project management software
- Main competitors: Procore, Buildertrend, CoConstruct
- Target audience: Project managers and field supervisors at general contractors
- Key differentiator: mobile-first design, offline sync for job sites with poor connectivity
- Geographic focus: North America (US + Canada)

When the assistant offers to run competitive research or web searches, say yes.
When the assistant asks you to provide any additional context, answer with the
details above.
When the assistant presents a Research Brief draft for your approval, review it
briefly and then approve it ("looks good, please save it").

Your scenario is complete once the assistant confirms the Research Brief has been
saved to the Sitecore media library and shows you the file path.
""",
    max_turns=20,
    required_tools=frozenset({
        "scan_content_project_status",
        "search_market_research",
        "save_phase_artifact",
    }),
    saves_artifact=True,
))

S03_BRIEF_ENTRY = _reg(SimScenario(
    id="brief-entry",
    name="Brief Entry Point -Existing Brief Paste",
    description=(
        "Marketer skips Research/Strategy/BrandVoice and pastes a pre-written "
        "campaign brief directly. Verifies the assistant accepts the brief entry "
        "point, saves only the Brief artifact, and does not force earlier phases."
    ),
    scenario_prompt="""\
You work for a digital agency preparing a holiday campaign for a retail client.
You already have a completed campaign brief written by your strategy team and
want to skip directly to saving it.

Your goal: Skip the Research, Strategy, and Brand Voice phases and save your
existing campaign brief to Sitecore.

When the assistant shows you the pipeline status, tell it you already have a
campaign brief ready to use and want to skip directly to the Brief phase.

When the assistant asks for the brief content, provide exactly this text:

---
Q4 Holiday Campaign Brief -RetailBrand
Campaign goal: Drive 20% more online sales during November–December.
Primary audience: Gift buyers aged 25–45, household income $75k+.
Channels: Email, paid social (Instagram/Facebook), display retargeting.
Key messages: Quality gifts, fast free shipping, exclusive loyalty rewards.
Budget: $150,000 total. Timeline: November 1 – December 31.
CTA: "Shop the Gift Guide" landing page.
---

When the assistant presents the draft Brief artifact for your approval, approve
it and ask to save it.

Your scenario is complete once the assistant confirms the Campaign Brief has been
saved to the Sitecore media library.
""",
    max_turns=12,
    required_tools=frozenset({
        "scan_content_project_status",
        "save_phase_artifact",
    }),
    saves_artifact=True,
))

S04_BRAND_VOICE_EXISTING_KIT = _reg(SimScenario(
    id="brand-voice-kit",
    name="Brand Voice Phase -Use Existing Stream Brand Kit",
    description=(
        "Marketer connects an existing Sitecore Stream brand kit and saves a "
        "Brand Voice Summary. Verifies list_org_brand_kits and get_brand_voice_summary "
        "are called before save_phase_artifact."
    ),
    scenario_prompt="""\
You work for Acme Corp. You want to align your marketing content with your
company's existing brand guidelines stored in Sitecore Stream.

Your goal: Complete the Brand Voice phase using an existing brand kit and save
a Brand Voice Summary to Sitecore.

When the assistant shows the pipeline status, ask it to help you with the
Brand Voice phase.
When the assistant shows you a list of available brand kits, select the first
one listed (or the "Acme" kit if available).
When the assistant presents the brand voice summary for your approval, review it
and approve it ("that looks right, save it").

If no brand kits exist, describe your brand voice as:
"Professional and approachable. Data-driven but human. We speak to busy
construction managers who don't have time for jargon -we're direct, practical,
and back up claims with real numbers. Tone: confident, not arrogant."
Then ask the assistant to save that as the Brand Voice Summary.

Your scenario is complete once the assistant confirms the Brand Voice Summary
has been saved to the Sitecore media library.
""",
    max_turns=15,
    required_tools=frozenset({
        "scan_content_project_status",
        "list_org_brand_kits",
        "save_phase_artifact",
    }),
    saves_artifact=True,
))

S05_STRATEGY = _reg(SimScenario(
    id="strategy",
    name="Strategy Phase -Full Marketing Strategy",
    description=(
        "Marketer completes the Strategy phase with goal/KPI/positioning details. "
        "Verifies the assistant reads the Research artifact first (if present), "
        "asks the right strategy questions, and saves the Marketing Strategy doc."
    ),
    scenario_prompt="""\
You work for Acme Corp. You're developing a marketing strategy for your
construction project management software targeting mid-market firms.

Your goal: Complete the Strategy phase and save a Marketing Strategy document.

When the assistant asks about strategic goals, answer:
- Expand into the mid-market segment (50-500 employee construction firms)
- Reduce trial-to-paid churn by 15% within 6 months
- Grow marketing-qualified leads (MQLs) by 30% year-over-year

When asked about KPIs, answer:
- Trial signups per month (target: 250)
- Demo requests per month (target: 80)
- Customer acquisition cost (target: under $1,200)
- Net Promoter Score (target: 45+)

When asked about positioning, answer:
"Acme is the project management platform built for how construction teams
actually work -mobile-first, offline-capable, and designed for the job site,
not the office."

When asked about messaging pillars, answer:
- Reliability (works offline, syncs when connected)
- Simplicity (field crews can learn it in an hour)
- Compliance (built-in RFI tracking, change order logs)

When the assistant presents the Marketing Strategy draft, approve it and ask
to save it.

Your scenario is complete once the assistant confirms the Marketing Strategy
document has been saved to the Sitecore media library.
""",
    max_turns=18,
    required_tools=frozenset({
        "scan_content_project_status",
        "save_phase_artifact",
    }),
    saves_artifact=True,
))

S06_CAMPAIGN_PERSONALIZATION = _reg(SimScenario(
    id="campaign-personalization",
    name="Campaign Phase -Personalization Rules Tactic",
    description=(
        "Marketer requests a Personalization Rules plan. Verifies the assistant "
        "reads the Brief artifact, generates a Campaign plan with personalization "
        "tactic sections, and saves it after approval."
    ),
    scenario_prompt="""\
You work for Acme Corp. Your campaign brief for the construction PM software
campaign is ready and you want to create a personalization strategy.

Your goal: Complete the Campaign phase with a Personalization Rules plan and
save it to Sitecore.

When the assistant shows the pipeline status, tell it you want to work on
campaign tactics, specifically personalization rules.

When asked about your brief or campaign context:
- Campaign: Q3 Expansion into mid-market construction
- Audience: Construction PMs and field supervisors at 50-500 employee firms
- Channels: LinkedIn, email nurture, retargeting display

When asked about personalization strategy, answer:
- Segment 1: Company size -SMB (<50 employees) vs Mid-Market (50-500)
  Show SMB users simpler plans; Mid-Market users enterprise ROI messaging
- Segment 2: Job role -Project Manager vs Field Supervisor
  PMs see scheduling/reporting features; Supervisors see mobile/offline features
- Segment 3: Engagement -New visitor vs Returning (>2 visits)
  New: product overview + trial CTA; Returning: case studies + demo CTA

When the assistant presents the Campaign Plan draft, approve it and ask to
save it.

Your scenario is complete once the assistant confirms the Campaign Plan has been
saved to the Sitecore media library.
""",
    max_turns=18,
    required_tools=frozenset({
        "scan_content_project_status",
        "get_phase_artifact_content",
        "save_phase_artifact",
    }),
    saves_artifact=True,
))

S07_LANGUAGE_MANAGEMENT = _reg(SimScenario(
    id="language-management",
    name="Site Language Management -Add fr-CA",
    description=(
        "Marketer checks which languages the site supports, then adds French Canadian "
        "(fr-CA) if not already present. Verifies get_site_context, list_site_languages, "
        "and add_language_to_site tool calls."
    ),
    scenario_prompt="""\
You work for an international marketing team expanding your Sitecore site to
support French Canadian visitors.

Your goal: Check what languages your marketing site currently supports, then
add French Canadian (fr-CA) if it is not already enabled.

When the assistant shows you the current language list:
- If fr-CA is already listed, tell the assistant no further action is needed
  and that you've confirmed it's already there.
- If fr-CA is NOT listed, ask the assistant to add it.

After the assistant attempts to add fr-CA, confirm you've seen the result
(success or error).

Your scenario is complete once the assistant has shown you the current language
list AND you've confirmed the final state of fr-CA support.
""",
    max_turns=10,
    required_tools=frozenset({
        "get_site_context",
        "list_site_languages",
    }),
    saves_artifact=False,
))

S08_OVERWRITE_EXISTING = _reg(SimScenario(
    id="overwrite-existing",
    name="Overwrite Existing Artifact -Research Brief Refresh",
    description=(
        "Verifies that re-running the Research phase on a site that already has a "
        "Research Brief silently overwrites it (overwriteExisting=true) without "
        "blocking or requiring extra confirmation beyond the standard approval gate."
    ),
    scenario_prompt="""\
You work for Acme Corp. You completed your Research Brief three months ago but
new competitor products have launched and you want to refresh it.

Your goal: Return to the Research phase, update the Research Brief with
fresh competitive intelligence, and overwrite the existing Sitecore artifact.

When the assistant shows the pipeline status and flags an existing Research Brief,
tell it you want to refresh/update it.
When asked about the new competitive landscape:
- New competitor: BuildSmart (launched Jan 2025), targets enterprise (1000+ employees)
- Procore released a new AI scheduling module in Q1 2025
- Market shift: more firms requiring BIM integration
Provide these updates as additional context.
When the assistant offers to do new web research, agree.
When the updated Research Brief draft is presented, approve it and ask to save
(overwrite) it.

Your scenario is complete once the assistant confirms the Research Brief has
been saved (overwritten) to the Sitecore media library.
""",
    max_turns=20,
    required_tools=frozenset({
        "scan_content_project_status",
        "search_market_research",
        "save_phase_artifact",
    }),
    saves_artifact=True,
))


S09_CREATE_TEST_SITE = _reg(SimScenario(
    id="create-test-site",
    name="Create Test Collection and Site",
    description=(
        "Marketer provisions a new 'test' collection and a campaign microsite within it. "
        "Verifies list_all_sites is called first to check for duplicates, then "
        "create_marketing_site is called with the confirmed name and collection."
    ),
    scenario_prompt="""\
You work for Acme Corp. You want to create a sandbox Sitecore site to preview
your Q3 construction campaign before going live on the main site.

Your goal: Create a new collection named "test" and a site named
"acme-q3-campaign-test" within it.

When the assistant offers to check existing sites first, agree -you want to
confirm the site doesn't already exist.
When the assistant asks you to confirm the site name and collection before
creating, confirm with:
- Site name: acme-q3-campaign-test
- Collection: test
- Language: en

If the site already exists, tell the assistant to skip creation and proceed.
If it's new, confirm the creation.

Your scenario is complete once the assistant confirms the site was created (or
already existed) and shows you the site's id.
""",
    max_turns=10,
    required_tools=frozenset({
        "list_all_sites",
        "create_marketing_site",
    }),
    saves_artifact=False,
))

S10_CAMPAIGN_PAGE_STRUCTURE = _reg(SimScenario(
    id="campaign-page-structure",
    name="Build Campaign Page Structure from Brief",
    description=(
        "Marketer creates a 3-page structure (Home, Campaign Landing, Thank You) "
        "on the test campaign site based on the campaign brief. Verifies that the "
        "assistant reads the brief first, uses get_insert_options to discover "
        "templates, and calls create_page for each page with marketer approval."
    ),
    scenario_prompt="""\
You work for Acme Corp. Your campaign brief for the Q3 construction PM software
campaign has been saved in Sitecore. You now want to build a basic page structure
on your test microsite to preview the campaign.

Your goal: Create three pages on your test site (id: acme-q3-campaign-test):
1. Campaign Home page (landing page for the campaign)
2. Feature Details page (showcasing the mobile/offline features)
3. Thank You page (post-form-submission confirmation)

When the assistant asks which environment to use, say "master" (staging).
When the assistant presents available page templates from get_insert_options,
select or accept the most appropriate ones for each page type.
When the assistant asks you to confirm each page creation, approve them.
If the assistant reads the campaign brief first to inform the page naming,
confirm the names it suggests.

Your scenario is complete once the assistant confirms all three pages have been
created and provides their page IDs.
""",
    max_turns=20,
    required_tools=frozenset({
        "get_insert_options",
        "create_page",
    }),
    saves_artifact=False,
))

S11_POPULATE_PAGE_CONTENT = _reg(SimScenario(
    id="populate-page-content",
    name="Populate Page Content from Campaign Brief",
    description=(
        "Marketer uses the campaign brief to populate headline, body copy, and CTA "
        "field values on existing campaign pages. Verifies get_phase_artifact_content "
        "is called first to read the brief, then update_page_fields is called with "
        "content derived from it."
    ),
    scenario_prompt="""\
You work for Acme Corp. Your campaign pages are created and you want to fill them
with content derived from your campaign brief.

Your goal: Populate content fields on your campaign landing page using the
campaign brief as the source of truth.

When the assistant asks which page to update, tell it the Campaign Home /
landing page.
When the assistant reads the campaign brief to extract content, let it proceed.
When the assistant proposes field values based on the brief, review them:
- Headline: should reference construction PM, mobile-first, or key differentiator
- Body copy: should match the brief's key messages
- CTA: should reference the brief's call-to-action (e.g. "Start Free Trial")
Approve the proposed field values (or suggest one small tweak, then approve).
When the assistant asks for the page ID, provide: "campaign-home-page-001"
When the assistant asks for the language, say "en"

Your scenario is complete once the assistant confirms the page fields have been
updated.
""",
    max_turns=15,
    required_tools=frozenset({
        "get_phase_artifact_content",
        "update_page_fields",
    }),
    saves_artifact=False,
))

S12_FULL_MICROSITE_SETUP = _reg(SimScenario(
    id="full-microsite-setup",
    name="Full Campaign Microsite -Site + Pages + Content",
    description=(
        "End-to-end microsite provisioning: read campaign brief → create test site → "
        "discover page templates → create page structure → populate content fields. "
        "This is the developer-agent integration smoke test for the full "
        "site-authoring workflow."
    ),
    scenario_prompt="""\
You work for Acme Corp. You want to stand up a complete campaign microsite from
scratch, using your saved campaign brief as the content source.

Your goal: Create a new test collection and site, build a 3-page structure, and
populate the landing page with content from the campaign brief.

Step-by-step guidance:
1. Ask the assistant to check existing sites and then create a new test site.
   - Site name: acme-campaign-microsite-test
   - Collection: test
   - Language: en
2. After the site is created, ask the assistant to create pages on it.
   Create: Campaign Landing, About the Product, Contact/CTA page.
   Environment: master (staging)
3. After pages are created, ask the assistant to populate the Campaign Landing
   page fields using the campaign brief. Provide page ID "microsite-landing-001"
   if asked.
4. Approve content suggestions from the brief and confirm each step.

If any step fails (e.g. site already exists), tell the assistant to proceed
with what's there and continue to the next step.

Your scenario is complete once all three pages are created AND at least one
page's fields have been updated with content from the campaign brief.
""",
    max_turns=30,
    required_tools=frozenset({
        "create_marketing_site",
        "get_insert_options",
        "create_page",
        "get_phase_artifact_content",
        "update_page_fields",
    }),
    saves_artifact=False,
))

S13_AB_TEST_VARIANT = _reg(SimScenario(
    id="ab-test-variant",
    name="A/B Test Page Variant -Duplicate and Differentiate",
    description=(
        "Marketer duplicates the campaign landing page to create an A/B test variant, "
        "then updates the variant's headline and CTA fields with a different message. "
        "Verifies search_pages, duplicate_page, and update_page_fields are all called."
    ),
    scenario_prompt="""\
You work for Acme Corp. You have a campaign landing page and want to create an
A/B test with an alternative headline and CTA.

Your goal: Find the campaign landing page, duplicate it to create a Variant B,
then update Variant B with different content.

When the assistant asks what to search for, say "campaign landing" on site
"acme-q3-campaign-test" in environment "master".
When the assistant shows you matching pages, pick the Campaign Landing / Home page.
When the assistant asks you to confirm the duplication, approve it.
After duplication, when the assistant asks what to change for Variant B, provide:
- Headline variant: "Built for the Job Site, Not the Office"
  (vs the control headline which is more product-feature focused)
- CTA variant: "See It In Action" instead of "Start Free Trial"
When the assistant proposes the updated fields for Variant B, approve them.

Your scenario is complete once the assistant confirms Variant B page fields
have been updated with the alternative headline and CTA.
""",
    max_turns=15,
    required_tools=frozenset({
        "search_pages",
        "duplicate_page",
        "update_page_fields",
    }),
    saves_artifact=False,
))


S14_IMAGE_SEARCH_FIND_SELECT = _reg(SimScenario(
    id="image-search-find-select",
    name="Image Search -Find and Select Images by Description",
    description=(
        "Marketer searches the media library for campaign-relevant images using "
        "natural-language descriptions. Verifies search_site_images is called with "
        "a descriptive query, the assistant returns at least one result with a "
        "media_path, and the marketer is able to select one for use."
    ),
    scenario_prompt="""\
You work for Acme Corp. You are building a campaign page for your construction
project management software and need to find relevant images in your Sitecore
media library to use on the page.

Your goal: Search for images that would work for a construction-industry
campaign and select one to note for placement on your landing page.

When the assistant is ready to help, ask it to search for images that show:
"construction workers collaborating on a job site with mobile devices"

If the search returns results, look at the media paths provided and select
the first image returned (or the one with the highest relevance score).
Tell the assistant which one you want to use and note its media_path.

If the search returns no results (empty index), ask the assistant why and
confirm whether the image index needs to be populated first.
Your scenario is complete once the assistant has returned image search results
(or clearly explained why none were found), and you have acknowledged the result.
""",
    max_turns=10,
    required_tools=frozenset({
        "search_site_images",
    }),
    saves_artifact=False,
))

S15_IMAGE_SEARCH_POPULATE_COMPONENT = _reg(SimScenario(
    id="image-search-populate-component",
    name="Image Search -Find Image and Set on Page Component",
    description=(
        "End-to-end image search and placement: marketer searches for an image by "
        "description, receives ranked results with media paths, selects one, and "
        "uses update_page_fields to set that image on a campaign page component. "
        "Validates the full search-to-placement workflow."
    ),
    scenario_prompt="""\
You work for Acme Corp. You want to find a hero image for your campaign landing
page and set it directly on the page component.

Your goal: Search for a suitable hero image, pick one from the results, then
update the page's Hero Image field with the chosen image's media_path.

Step-by-step:
1. Ask the assistant to search for an image matching:
   "modern construction project management software dashboard on a tablet"
2. When results come back, pick the image with the highest score, or the
   first result if scores are equal. Remember its media_path.
3. Ask the assistant to set that image as the Hero Image on your campaign page.
   When asked for the page ID, provide: "campaign-home-page-001"
   When asked for the field name, provide: "HeroImage"
   When asked for the field value, provide the media_path from step 2.
4. Confirm the page field update was successful.

If the image search returns no results, ask the assistant to index the media
library first (just a small batch of 10 images), then retry the search.

Your scenario is complete once update_page_fields has been called with a
media_path value from the image search results.
""",
    max_turns=18,
    required_tools=frozenset({
        "search_site_images",
        "update_page_fields",
    }),
    saves_artifact=False,
))


def get_scenario(scenario_id: str) -> SimScenario:
    """Look up a scenario by ID, raising KeyError with a helpful message."""
    if scenario_id not in SCENARIOS:
        known = ", ".join(sorted(SCENARIOS))
        raise KeyError(f"Unknown scenario {scenario_id!r}. Known: {known}")
    return SCENARIOS[scenario_id]
