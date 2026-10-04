# Design  -  The Agent Desk

The dashboard (`frontend/`, React + Vite + TypeScript) is where a human watches the Campus Customs agent team work and signs off on anything involving money. For this problem we set aside the project's space-cowboy style on purpose. Someone may sit at this screen all day, so it should feel calm, precise, and quietly expensive, like the reception desk of an architecture studio. Studio Wu's interiors were the reference: generous negative space, a restrained palette, fine lines instead of boxes, and serif type that does the decorating.

## The look

**Palette: ink, paper, and one maroon.**
- **Paper** `#F5F2EC`, a warm off-white instead of stark screen white. It is easier on the eyes over long sessions and reads like heavy stock.
- **Ink** `#161514` for type, rules, and the primary button. It is almost black and slightly warm.
- **Maroon** `#5E1A24` is the only accent, and it is used sparingly: the selected ticket's edge, the hover state of buttons, the top rule on anything awaiting your signature, a pulsing dot while an agent works, and the balance as it changes. Because it is rare, maroon always means "look here."
- **Hairlines** `#DCD5CA` divide everything. There are no drop shadows, no rounded cards, and no gradients except a whisper on final-call lines. Structure comes from thin rules, like an architectural drawing.

**Type: three faces with three jobs.**
- **Cormorant Garamond**, a high-contrast serif, for headings, ticket subjects, the balance, and the agents' own words. It gives the page its editorial, gallery-placard elegance.
- **Inter** in small, widely tracked capitals for labels ("CHECKING", "REQUESTER", "BEGIN RUN"). Wide tracking is the quiet luxury signal you see on high-end letterhead and storefronts.
- **IBM Plex Mono** for machine facts: ticket numbers, timestamps, tool names, tool output. Anything a computer said is set in mono, so you can tell at a glance what is data and what is judgment.

## Layout

A three-column floor plan under a masthead, laid out like a working desk:

| Zone | What's there | Why |
|---|---|---|
| **Masthead** | "The Agent Desk" in large serif; an *Operator* name field; the **checking balance** set large on the right | The two things you always need (who is signing and how much money there is) never scroll away. |
| **Docket** (right) | The three tickets as a stacked list: number in mono, subject in serif, type and requester below, status in small caps. *Reset to original data* sits quietly at the bottom. | It reads like a printed docket or a matter list. Selecting a ticket gives it a maroon edge, like a bookmark. |
| **The Floor** (center) | The selected ticket's header and facts, the *Begin run* button, the **agent roster**, and the live **feed** of everything the team says and does | This is the stage. It gets the most width and the most whitespace. |
| **Awaiting You / Summary / Drafts / Ledger** (left) | Pending payment approvals and PO drafts, the Boss's final call, the customer drafts, and a ledger of payment decisions | Everything that needs a human sits in one tinted column, so your responsibilities are physically separated from the agents' chatter. It sits on the left, where the eye lands first, because what needs your signature matters most. |

## How agents read differently

Each agent has an identity carried by a **monogram** (an italic serif initial in a thin circle: *B, I, A, F, C*) and a **muted tone**. The tones are earthy enough to read as one family and distinct enough to tell apart:

| Agent | Tone | Idea |
|---|---|---|
| Boss | Maroon `#5E1A24` | The house color: the Boss speaks for the shop. |
| Inventory | Slate `#3F4B55` | Shelving, steel, the stockroom. |
| Accounting | Forest `#3D4A3A` | Ledger green, old banking. |
| Facilities | Umber `#7A6A58` | Stone, timber, the building itself. |
| Customer Service | Mauve `#7D5A63` | The warmest tone, for the agent that talks to people. |

**The roster** shows all five agents as a row of placards. An agent that wasn't needed stays faded and reads *Not called*. That matters because Problem 6 planned for the team to skip specialists, and the board makes that visible. A working agent shows a slowly pulsing maroon dot, and a finished one shows a solid ink dot. Under each name is that agent's latest line in italic serif, so you can follow the whole team by scanning one row.

**The feed** gives each kind of step its own voice:
- **What an agent says** (its reasoning and its final report) is in **italic serif**. It reads like a quotation, because it is the agent's judgment.
- **Tool calls and results** are in **small mono gray**: quiet, factual, and there if you want to audit them.
- **Hand-offs** are marked with a maroon arrow ("→ Hands to Accounting") followed by the task in serif.
- **Delegation depth is shown as indentation.** When the Boss hands work to Accounting, Accounting's steps are indented beneath it, so the conversation reads as a nested outline of who asked whom.
- **The Boss's final call** sits on a soft card tint, as the closing line of the scene.
- **Problems** (a refused hand-off, a retry, an error) are in maroon.

While the team works, the feed polls every 1.5 seconds and scrolls itself. Three small maroon dots breathe at the bottom, and a fine maroon light sweeps along the active ticket's edge in the docket. That's enough motion to feel alive without being distracting.

## How resolved tickets show up

A resolved ticket stays in the docket but steps back: its subject turns gray with a single **thin maroon strikethrough** (the way you'd cross an item off a fine-paper to-do list), and its status reads **✓ RESOLVED** in forest green. It is clearly done but still there for reference. *Mark resolved* appears only after a run finishes, and it requires an operator name, so a human, not an agent, closes the ticket.

## How cash shows up

- The **checking balance** is the largest number on the screen, set in serif with tabular figures, top right, with "as of" the shop's desk date beneath.
- When a payment goes through, the balance **turns maroon for a moment** and then settles back to ink, so you notice the change without an alarm.
- **Awaiting You** shows each payment request as a card with a maroon top rule: the approval id, the amount in large serif, what it pays (rent or invoice), which ticket asked, and Accounting's reason. If a request is larger than the balance, a maroon warning appears before you click.
- *Approve & pay* records your name and then pays through the MCP `pay_bill` tool. *Decline* is a plain text link: approving is the deliberate, solid action, and declining is the quiet escape.
- The **Ledger** keeps every payment decision, with paid amounts shown as plain ink negatives (−$840.00) in serif. Since cash only ever goes out in this shop, every entry is a subtraction.

## Extras we added because they help at the desk

- **Operator name** in the masthead, remembered between visits. Every approval and resolution is signed with it.
- **Summary panel**: the Boss's decision in serif, the outcome, which agents worked, tool calls per agent, actions taken, and a maroon-edged *Needs a human* box.
- **Drafts panel**: every customer message for the ticket, expandable to read the full text, and labeled *never sent*.
- **Token count** next to the step count, so the cost of each run is always visible.
- **Reset** with a confirmation, kept small at the bottom of the docket so it's never clicked by accident.
- **Replays**: selecting a ticket shows its most recent run from the audit trail, so the board is useful even when nothing is running.

## Why it feels good to use

- **Calm by default, loud only when needed.** With one accent color used rarely, the eye goes straight to what matters: your selection, money waiting on you, or a problem.
- **It reads like a story, not a log.** Serif quotations, indented hand-offs, and a final call make each run feel like reading a well-edited transcript of a meeting.
- **You can trust it at a glance.** Mono means machine fact, serif means judgment, and maroon means attention. Once you learn those three rules, the whole board makes sense.
- **Wealth whispers.** There are no badges, emojis, or bright status chips. Instead there is whitespace, hairlines, tracked capitals, and good type, which is the vocabulary of a quiet, well-run studio.
