# Startup Description: WhatsApp-Native AI Smart Home Platform for Indian Apartments

---

## The Idea in One Paragraph

We are building a smart home automation system for Indian residential
apartment buildings where residents control their entire home — lights, AC,
door locks, geysers, and more — through WhatsApp. No app download, no voice
assistant, no learning curve. The system is sold B2B to apartment
builders/developers who bundle it into new residential projects before
residents move in, marketed as a premium amenity that justifies higher
per-sqft pricing. The AI orchestration layer understands natural language
commands in English (and later Hindi) and executes them on locally-installed
smart hardware. Residents interact the same way they message their family —
just type or voice-note "turn on AC" and it happens.

---

## The Problem

**For builders/developers:**
The Indian premium residential market (₹1–3 Cr flats) is intensely
competitive. Builders need differentiating amenities to justify pricing
premiums and close sales faster. "Smart home" is one of the highest-impact
marketing lines in brochures today. However, existing solutions require
builders to work with complex enterprise vendors, go through long procurement
cycles, deal with proprietary apps residents don't use, and provide
post-installation support they're not equipped for. Most builders fake it —
adding "smart home ready wiring" (one extra conduit, ₹800/flat) and calling
it done. When a competitor launches a genuine smart home project and closes
faster at ₹150–200/sqft premium, that's the moment of acute pain.

**For residents:**
Premium flat buyers are promised "smart home living" in brochures and shown
Alexa demos in sample flats. At possession, they get a clunky proprietary app
that their spouse won't use, their domestic help can't operate, and that
breaks every time the Wi-Fi restarts. The Alexa dot ends up in a drawer. The
smart home panel becomes a very expensive light switch. The gap between what
premium housing is marketed as and what it actually delivers is the daily
frustration. The specific pain: domestic help manages the home during the day
but cannot use any smart home system. The owner is at work and cannot control
anything remotely in a way that actually works reliably.

---

## The Solution

A three-layer stack:

**Layer 1 — Hardware (installed in walls at construction)**
Smart Zigbee switches replacing standard switches, IR blasters for AC
control, smart door locks. All installed by us during building construction,
wired into the building's electrical infrastructure. Cannot be removed without
replacing all switchboards — this is structural lock-in.

**Layer 2 — Local intelligence (per-building server room)**
Home Assistant running on a mini-PC as the device control hub. Local LLM
inference (Qwen3 8B) on 3–4 RTX 4060 Ti GPUs per building for privacy and
reliability. No resident data leaves the building. Zigbee2MQTT manages the
device mesh. The building's server room hosts everything — no cloud dependency
for core functionality.

**Layer 3 — WhatsApp interface (resident-facing)**
OpenClaw (MIT-licensed AI agent gateway, launched January 2026) connects to
WhatsApp Business Cloud API and routes resident messages to the AI
orchestration layer. Resident texts "turn on AC" → WhatsApp webhook → command
parser → Home Assistant REST API → AC turns on → "AC turned on ✓" reply in
3 seconds. Supports text commands, voice notes (transcribed via Whisper
locally), scheduled automation ("every day at 6am turn on geyser"), and
context-aware commands ("I'm 15 minutes away, get the house ready").

---

## Why WhatsApp Specifically

India has 550M+ WhatsApp users. Open rate is 98%+. It is the single app
that spans every demographic — the tech-savvy owner, their elderly parent
visiting, and the domestic help who manages the home 8 hours a day. No
competitor has built smart home control on WhatsApp. Every existing system
requires a proprietary app. The switching cost from "do nothing" to "try our
product" is one WhatsApp message. This is our primary distribution and
retention moat.

---

## Business Model

**Revenue stream 1 — One-time hardware + installation (builder pays)**
₹8,000–12,000 per flat at project handover. Bundled into construction cost
by the builder, invisible to the buyer. Builder marks up 1.3–1.5× and
presents it as "complimentary smart home" in the brochure.

**Revenue stream 2 — Monthly recurring (collected via RWA)**
₹600 per flat per month:
- ₹300 as explicit "smart home service" line in monthly maintenance bill
- ₹300 as "smart home AMC" inside building maintenance charges
Both collected by the Resident Welfare Association (building management
committee) as part of standard monthly maintenance — same as CCTV AMC,
lift maintenance, water charges. One invoice per building, not 150 invoices.

**Unit economics for a 150-unit building:**
- One-time: ₹12,000/flat × 150 = ₹18 lakh at handover
- Monthly recurring: ₹600/flat × 150 = ₹90,000/month = ₹10.8 lakh/year

**Portfolio economics (5 buildings, Year 1):**
- One-time revenue: ₹90 lakh
- Annual recurring: ₹54 lakh, growing every year without incremental cost

**10-year compounding (20 buildings):**
- Monthly recurring: ₹18 lakh/month
- Annual: ₹2.16 Cr/year from installed base alone, plus new building revenue

---

## The Hardware Lock-in Moat

This is the most important strategic point. Once our Zigbee switches are
installed inside the walls of 150 flats, they are permanently there.
Replacing them requires hiring electricians to open every switchboard in every
flat, buying entirely new hardware, disrupting 150 families, getting RWA
approval, and the builder's reputation taking a hit. Nobody does this to save
₹600/month. Churn is structurally impossible. This turns the business into a
recurring revenue infrastructure company, not a software subscription that can
be cancelled with one click. Razor and blades model: hardware at near-cost,
software/service margin forever.

---

## Target Market

**Primary customer (who signs the check):** Indian apartment
builders/developers — specifically VP Sales or Head Marketing at mid-tier
developers doing 3–10 projects/year with 100–400 units each in Bangalore,
Pune, Mumbai, Gurgaon, and Hyderabad. Not the CMD of Lodha — the person at
a Puravankara or Kolte-Patil who personally lost a sales comparison to a
competitor's smart home project last quarter and has budget authority for
amenities.

**End user (who uses the product daily):** Dual-income couples in ₹1.5–3 Cr
flats, at least one working in tech or finance, domestic help managing the
home during the day, bought "smart home ready" but never set it up because
the vendor's app was terrible. Age 30–42.

**Market size:**
- India smart home market: USD 5.2B in 2025, growing at 29.1% CAGR
- Projected: USD 19.3B by 2030 (Mordor Intelligence)
- 459,650 apartments sold across top 7 Indian cities in 2024 (Anarock)
- Luxury segment (>₹2.5 Cr) grew 28% YoY in 2025
- New apartment launches: 419,170 units in 2025, weighted toward premium

---

## Competitive Landscape

**Direct competitors:**

*Silvan Innovation Labs (now Polycab):*
Founded 2008, Bangalore. The B2B builder-focused leader. Deployed 100,000+
devices across 8,000 homes. Blue-chip builder logos: Sobha, Lodha, Brigade,
Prestige, Tata Housing. 17 patents. Raised $4.31M from 8 investors including
Samsung Venture Investment at a $25M valuation in 2019. Acquired by Polycab
(India's largest wire/cable company) in June 2021 for just ₹18.2 Cr (~$2.5M)
— a 90% haircut from peak valuation. Why the low exit: pure hardware business,
no recurring software revenue, no AI layer, proprietary app residents don't use,
COVID timing. Now operates under Polycab's HOHM brand. Our advantage: WhatsApp
interface, AI orchestration, recurring software revenue from day one.

*Cubical Labs:*
Delhi, IIT-Guwahati incubated. ~1,500 homes, primarily NCR market. Proprietary
sub-GHz protocol. No WhatsApp, no AI.

*Keus, Wozart, BuildTrack:* Premium or mid-market players. No WhatsApp,
no AI orchestration, no builder-specific recurring revenue model.

*Legrand/Schneider/Havells:* Specified via MEP consultants. Strong brand,
weak software. No AI. No WhatsApp.

**Invisible competitors (more dangerous than named ones):**

*The builder's habit of doing nothing:* Adding "smart home ready wiring" to
the brochure costs ₹800/flat and gets 80% of the marketing benefit with 0%
execution risk. Our hardest competitor is inertia.

*MyGate:* Community management platform in 25,000+ societies with existing
WhatsApp integration for visitor alerts and RWA communication. One product
decision away from adding device control. If they do this, they compress our
market significantly. Must move before them.

*The building electrician:* Installs a ₹800 mechanical timer for the geyser.
Solves the specific problem. Zero app, zero subscription, zero failure.

**Whitespace we occupy:** No competitor has WhatsApp as a primary control
surface. No competitor has a local AI orchestration layer. No competitor has
a recurring software revenue model collected via RWA. These three together
are our differentiation.

---

## Technology Stack

- **OpenClaw** — MIT-licensed AI agent gateway (January 2026). Connects to
  25 messaging channels including WhatsApp natively. Routes messages to LLM
  runtime, executes tools. Think of it as the conversational brain.
- **Home Assistant** — Open-source local smart home control platform.
  Native MCP (Model Context Protocol) server support from v2025.2 enables
  LLM tool calling directly to devices. 3,000+ device integrations.
- **Qwen3 8B / local LLM** — Runs on RTX 4060 Ti GPU(s) in building server
  room. Handles natural language commands. No cloud dependency.
- **WhatsApp Business Cloud API** — Meta's official API. Service
  conversations (user-initiated) are free. No per-message cost for the
  core use case.
- **Zigbee2MQTT + Sonoff hardware** — Device mesh protocol and hardware.
  Penetrates Indian concrete construction well. Sub-₹2,000 per switch.
- **Broadlink RM4 Mini** — IR blaster for AC control. Works with any AC
  brand without native smart features. ₹1,800/unit.

---

## Founders

**Founder 1 (Tejas):** 20, sophomore CS at Penn State. Technical — systems
programming, AI/ML research. Based in US, manages software architecture
and investor relations. India-origin, family network in Indian real estate.

**Founder 2 (co-founder, India-based):** CS background, India. Has direct
builder/developer relationships through family network. Manages India
operations, hardware installation, builder sales, co-founder's family
is in construction/real estate adjacent space.

**Initial capital:** ₹1 lakh combined (₹50K from family, ₹50K savings).
Enough for Stage 0 demo deployment.

---

## Traction and Stage

Currently pre-revenue, pre-product. In planning/early build phase.

**Immediate next steps (Summer 2026):**
- Deploy MVP in family vacation home in Shimla, Himachal Pradesh as free
  test environment (no builder needed, no sales cycle, controlled conditions)
- Build WhatsApp webhook + Home Assistant integration + basic command parser
- Hardware: ₹18,000 (Pi, Zigbee dongle, 2 switches, IR blaster, smart lock)
- Target: 5 real users, Day-14 retention measured, first builder conversation

**First customer path:**
Co-founder's network includes a developer building a residential settlement.
This is the target for first pilot — 5–10 flats at cost of hardware, free
software, in exchange for letter of intent for full project rollout.

---

## Why Now

Three converging tailwinds:

1. **OpenClaw launched January 2026** — the WhatsApp-native AI orchestration
   layer we need didn't exist 12 months ago. We're among the first to apply
   it to hardware control.

2. **India luxury housing boom** — luxury flat sales grew 28% YoY in 2025.
   Builders are actively looking for premium amenity differentiation. The
   market is at the exact moment where smart home moves from nice-to-have
   to table-stakes for premium projects.

3. **Silvan/Polycab is distracted** — Polycab is a wire and cable company
   that bought Silvan for IoT optics. Their core competency is not AI,
   not WhatsApp, not software. The 2-year window before they build a serious
   software layer (if they ever do) is open now.

---

## Key Risks

1. **Builder sales cycle** — 6–18 months from first meeting to signed
   contract. Cash runway discipline is critical. Mitigated by: warm
   introductions through co-founder's network, approaching mid-tier
   developers (shorter cycles than Tier-1), and using the Shimla demo to
   create urgency through proof.

2. **WhatsApp API dependency** — Meta controls the platform. Policy changes
   can affect the business. Mitigated by: Telegram as backup channel
   (identical technical stack), on-premise Raspberry Pi as local fallback
   for basic command execution even without internet.

3. **Hardware reliability** — Consumer-grade IoT hardware fails in Indian
   conditions (humidity, dust, voltage fluctuations, heat). Mitigated by:
   commercial-grade hardware from v1, UPS backup for hubs, redundant Zigbee
   mesh, onsite AMC contract that covers replacements.

4. **Co-founder execution gap** — Neither founder has installed a smart home
   at building scale or managed electrician contractors. Mitigated by:
   Shimla property as a low-stakes first deployment, finding an experienced
   IoT/installation contractor as first key hire.

5. **MyGate expansion risk** — If MyGate adds device control, they have
   distribution we don't. Mitigated by: moving fast on builder lock-in
   (hardware in walls before MyGate is a threat), potentially approaching
   MyGate as a channel partner rather than competitor.

---

## The Exit

**Strategic acquirers:**
- Polycab (already bought Silvan, may want a software-first upgrade)
- Havells (building FMEG portfolio, no smart home software layer)
- Legrand (global smart home player, weak India software)
- NoBroker / MyGate (if pivoting to full building-tech stack)

**Comparable exit:** Silvan sold for ₹18.2 Cr with hardware-only, no
recurring revenue. A software+hardware business with 10,000 active units
and ₹2 Cr+ ARR would command ₹100–500 Cr depending on timing and bidder.

**VC path:** Seed at USD 1.5–2.5M after 3 builder pilot LOIs and Day-14
retention data. Series A at USD 10–15M on 15,000 committed units and
₹200+/flat MRR demonstrated.

---

## What We Need Business Analysis On

1. Is the revenue model (₹600/flat/month via RWA) structurally sound or
   does it have collection/enforcement weaknesses we haven't seen?

2. Is the builder sales motion (warm intros → pilot LOI → portfolio rollout)
   realistic for a 2-person team with limited India presence?

3. Are there other revenue streams we're not seeing — data, energy, insurance,
   adjacencies?

4. What's the right legal structure for a US-based founder running an India-
   operating company? (Delaware C-Corp with India subsidiary? Or start as
   Indian private limited?)

5. What's the fundraising sequencing — bootstrapped to first building, then
   angel, then seed? Or go to angel immediately after Shimla demo?

6. Are there regulatory risks (BIS certification for hardware, DPDP Act for
   resident data) that could kill the business or require significant spend?
