# AI Prompts  -  Homework 5

## Getting Started

**Prompt given:**

> Okay Claude, we are going to work in SOM AI Foundations today and complete Homework 5 for the class!

**Time given:** 2026-10-04 13:46:34 -04:00

**Notes:**

First prompt worked. This kickoff message started Homework 5; Claude created this prompt log.

## Project Background and Data Setup

**Prompt given:**

> Okay Claude, I'm going to give you a little background on the project before we get started. As always, we are going to work problem by problem, not create things all at once. throughout the course of the problems we are going to build an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so that a human can monitor the agents. I will want these agents to have full connectivity. There will be 5 agents (the Boss, Inventory, Accounting, Facilities, and Customer Service agents). Everything should talk to each other.
>
> In Homework 5 I added a data zip file, which you need to unzip. Once you unzip the file you will see a file Data/Campus\_Customs.db. Please make a copy of this database file called Data/Campus\_Customs\_New.db. the MCP server and backend should only ever alter the Campus\_Customs\_New file, never the original.
>
> Here are some general rules for the Project Shop (keep them in mind the whole time): the field desk.date\_today tells you what "today" is for the shop and should be used to determine what is overdue; vendor lead times come from the vendors table; a vendor will not ship new product while they still have an unpaid open invoice; human approval is required for any payments - never ever engage in payment activity without first asking an external human, and always update the relevant table if a payment is approved and made; if there is not enough cash, the pay tool must always refuse the payment so that we never go negative; we are not modeling revenue in this activity so we should never have cash come into the organization, only out; before we enact a full run to resolve tickets, please reset the database to it's original values; do not ever ever ever email customers or call real vendors - only ever drafts which stay here. Also, we will only use GPT luna for the agents in this project.

**Time given:** 2026-10-04 13:58:02 -04:00

**Notes:**

First prompt worked. Claude unzipped the data, created the working database copy, and recorded the shop rules used for the rest of the homework.

## Problem 1  -  Vibe Coder Prompts

**Prompt given:**

> Alright, lets begin Problem 1: Vibe Coder Prompts. You have already done this, but please confirm that you have built AI\_Prompts.md and are updating it as I give you prompts.

**Time given:** 2026-10-04 14:00:38 -04:00

**Notes:**

First prompt worked.

## Problem 2  -  Study the Campus Customs Database

**Prompt given:**

> Good. Now Problem 2: Study the Campus Customs Database. Please open data/campus\_customs.db and explore the tables and fields.
> Confirm that you've already copied the this original into campus\_customs\_new (ignore my changes in capitalization).
> Please also study the open tickets to understand how they link to tables.
> Create a folder Output and a Harness.md file in Output. in the markdown create a note for each table listing the fields included and a blurb about why this table is important for the agents we will create.

**Time given:** 2026-10-04 14:03:21 -04:00

**Notes:**

First prompt worked.

## Problem 3  -  Build the MCP Server

**Prompt given:**

> Good, on to Problem 3: Build the MCP Server:
> Please write an MCP Server in mcp\_server/ using FastMCP. This server should talk to data/campus\_customs\_new like I told you before, although you don't need to run it in this problem.
> all the agents I told you about will use the tools found in this server, so please write 3 tools you believe we will need for the tickets we have.
> Rules: keep the names clear, do not ever invent data, only use information given in the database.
> List the 3 MCP tools you build in Output/Harness (structure the harness by problem). For each tool please note what table it reads, which ticket it helps resolve, and one sentence only on why this tool is best for the ticket. be clear and direct, nothing as bland as "reads inventory."
> Please also add a short mcp\_server/README.md file which explains what the MCP server is for, which db files it uses, and its 3 tools

**Time given:** 2026-10-04 14:07:38 -04:00

**Prompt given:**

> okay Claude, I see that you say fastmcp isn't installed yet - can you please install it.

**Time given:** 2026-10-04 14:10:00 -04:00

**Notes:**

Two prompts. The first built the MCP server, its three tools, and the README. A second prompt was needed because fastmcp was not installed in the Python environment yet; it installed fastmcp, and Claude confirmed all three tools registered.

## Problem 4  -  Add the MCP Server to Vibe Coder and Test Each Tool

**Prompt given:**

> Great Claude, now let's do Problem 4: Add the MCP Server to Vibe Coder and Test Each Tool. I'm a bit confused on what this problem wants me to do so I am going to write to you exactly what my instructions are. Before you act, please describe to me how you interpret the instructions and what you are going to do. wait for my approval before you run: "In your vibe coder, add your MCP server to this project so the vibe coder can call the tools. save the connection JSON text in .mcp.json at the project root (or however your vibe coder saves local MCP server lists). with your vibe coder connected, test each of your three MCP tools. Save the evidence in Output/MCP\_Smoke.json. For ever tool include: The prompt you asked the vibe coder, the tool name, the tool output (must match values in data/campus\_customs\_new.db)

**Time given:** 2026-10-04 14:14:00 -04:00

**Prompt given:**

> Okay thanks Claude. One question - can you open the Homework 5 folder in this session? or open the session in Homework 5, however you need to do it so that we don't need 2 copies. Either way I approve of this plan an dunderstand that I will need to close and reopen Claude Code after you create the file. Make sure you have enough information to get back to work once I come back. I approve of option A and agree with your reasoning.

**Time given:** 2026-10-04 14:18:46 -04:00

**Prompt given:**

> Okay Claude I'm back, please continue problem 4.

**Time given:** 2026-10-04 14:22:06 -04:00

**Notes:**

Three prompts. The first asked Claude to explain its reading of the instructions and wait for approval. The second approved the plan, chose Option A (a pay\_bill refusal test, so no money moved), and moved the session into Homework 5 so only one .mcp.json was needed. The third came after restarting Claude Code (required to load the MCP server); it told Claude to continue, and Claude ran the three tool tests and saved MCP\_Smoke.json.

## Problem 5  -  Build the Agent Team and Grow the MCP Tools

**Prompt given:**

> Well done. Now to Problem 5: Build the Agent Team and Grow the MCP Tools. I now want to build the full agentic team for Campus Customs using PydanticAI. We will create 5 agents: a Boss who reads each ticket, decides who works on it, and makes final agentic calls; an Inventory agent who checks stock by SKU and size, spots shortfalls, and figures out which vendor restocks each item; an Accounting agent who watches cash and invoices, checks margins, and prepares payments or purchase orders for approval; a Facilities agent who handles the shop space side (leases, rent, etc); and a Customer Service agent who drafts messages for customers. Please include prompts, models, and agent loops so each of these individual agents can delegate work to each other and have full connectivity.
> Put all the agent prompts in Backend/Prompts/ with one file each per agent. put data types in backend/models.py and the agent files under backend/ (my changes in capitalization are not meaningful I'm just getting tired). Use my Portkey API Key and GPT luna.
> in each prompt please describe all the rules and instructions each agent needs. be descriptive and detailed so they understand their role.
> Please add any tools the agents will need to the MCP server so it works. all shop facts should come from the MCP server via data/campus\_customs\_new. please do not invent a second shop-tools layer bypassing MCP, MCP is our hub here.
> please wire the agents so they append to Output/Audit\_Trail.json as they run and make sure you record enough info for each agent-loop step to audit. append this file, don't wipe it after each run.
> Also, list each agent and each MCP tool added in Output/Harness along with which table each tool uses. Please include a safety section as well which notes the standard guardrails we want the agents to have if they had access to real customers and real money. also include safety instructions to limit token use.
> Finally, please update our MCP\_Server/README file so the tool list matches the new tools

**Time given:** 2026-10-04 14:30:05 -04:00

**Prompt given:**

> Okay Claude, is there anything else we need to do here before we move to Problem 6?

**Time given:** 2026-10-04 14:39:42 -04:00

**Notes:**

Two prompts. The first prompt built everything for this problem. The second only asked whether anything else was needed before Problem 6; nothing was required, and Claude listed optional cleanups.

## Problem 6  -  Plan the Three Tickets

**Prompt given:**

> Okay, let's do Problem 6: Plan the Three Tickets. before we wire the backend to work, please create Output/Desk\_Tickets.html which should be a page I can double click to open with one tab per ticket. please also include on the html an empty "cash" and "reflection" table for later problems. On each ticket tab, please create an Expected section of text and fill it with what we expect the team of agents to do when we run each ticket, including: who the boss should call first and why, all the expected agent delegations in detail, which MCP tools we expect the run to use. When we do the actual run, we will similarly add an Actual section to the tab which reports what actually happened. I don't think we will need every specialist on each ticket, so be diligent and think about what will reasonably happen and how to do these behaviors most efficiently

**Time given:** 2026-10-04 14:43:57 -04:00

**Notes:**

First prompt worked.

## Problem 7  -  Backend Routes

**Prompt given:**

> Good, now to Problem 7: Backend Routes. in the next problem we are going to create a React frontend dashboard, and in this problem we're going to create the backend for it to call. In backend/main.py, please use  FastAPI and add routes to do the following: Return the three tickets and whether each is open or resolved; take a ticket ID and run my agent team on the ticket; return recent agent events/actions so the board can refresh; approve a payment or purchase after a human clicks approve; return the current checking balance from cash\_accounts; reset the database to the original values when I want t try a fresh run. from the Backend/ folder, start the servier with uvicorn main:app --reload --port 8000. Finally, in Output/Harness.md please list each route in one line, including what URL it is and what it does

**Time given:** 2026-10-04 14:50:16 -04:00

**Notes:**

First prompt worked.

## Problem 8  -  Agent Dashboard

**Prompt given:**

> Good good, now Problem 8: Agent Dashboard. this is the step where be build the frontend dashboard in Frontend/ with React and Vite and TypeScript. it should call back to the routes we just built. Here are the essential features of the board, but feel free to add others you think I would find beneficial: list all three tickets; let me pick one ticket and start the agent team on it; show each agent and what they are saying/doing during the run; mark a ticket as resolved when the run is finished; show a short summary of all agent actions for the ticket; let a human approve a payment when asked; show the checking balance and update it after payments.
> Please tell the frontend to talk to the backend at http://localhost:8000. on the backend, allow the Vite page origin so the browser is allowed to call those routes. please start the board with npm run dev.
> I want to deviate from our space cowboy design guidelines here and instead make something that looks polished, architectural, and professional so that someone could work at it all day. I want rich, muted colors like black, white, and maroon and elegantly designed fonts/layout. the goal is sleek, elegant, and expensive (not tacky, definitley understated - wealth whispers). If you want to look at design firm websites like Studio Wu (https://www.studiowuinteriors.com/) for inspiration please do.
> Also, please write Output/Design.md and include what we chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why we did this. make sure you include the creative choices and how these choices make the dashboard feel enjoyable

**Time given:** 2026-10-04 15:00:32 -04:00

**Prompt given:**

> can we switch the sides of the right and left column, so the awaiting you/summary stuff is on the left. I think that's more natural for a user.

**Time given:** 2026-10-04 15:10:15 -04:00

**Notes:**

Two prompts. The first built the dashboard and Design.md. The second was a layout change after seeing the board: it moved the Awaiting You and Summary column to the left and the Docket to the right, and Claude updated Design.md to match.

## Problem 9  -  Resolve the Tickets

**Prompt given:**

> Okay great Claude, this design and style looks wonderful! Now let's do Problem 9: Resolve the Tickets. Before you do anything else, please reset our working database so that it's clean for a run. Make a note of the starting checking balance. Then, I want you to run all three tickets on the board until each is resolved. Please open Output/Desk\_Tickets.html and on each ticket tab, fill in the Actual section I told you about with information from this run: which agents actually worked, what they delegated, and which tools they used. don't change the expected section.
> On the Cash tab of Desk\_Tickets.html please itemize the money: the starting checking balance after the reset; how cash changed for each ticket when that ticket resolved and why the change was made; and the ending checking balance, which must match cash\_accounts in the working database. Don't make math mistakes

**Time given:** 2026-10-04 15:16:30 -04:00

**Prompt given:**

> I forgot to give you some additional activities for Problem 9 (consider this the same prompt/an extension of the one already sent). I also want you to save a couple files: Output/Resolved\_tickets.json which notes for each ticket the ID number, a short outcome description, which agents crontibuted, and if any human approvals were required; and Output/Resolved\_Board.html which should be  a page I can double click with a screenshot of my react board for each resolved ticket.
> Please append real runs to Output/Audit\_Trail.json and Finish Output/Harness so it covers tables, MCP tools, the five agents, API routes, the dashboard, and all safety rules.

**Time given:** 2026-10-04 15:16:30 -04:00

**Notes:**

Two prompts, sent back to back. The first was interrupted, so the second extended it with Resolved\_tickets.json, Resolved\_Board.html, the audit trail, and the final Harness. During the run Claude stopped and asked for human approval through the question prompt; the user approved both payments (APR-001 $840, APR-002 $2,400) and the restock PO, signing as Casey Brengman. Claude also fixed a gap in the Boss prompt: after the vendor was unblocked, the Boss had not requested a purchase order.

## Problem 10  -  Reflection

**Prompt given:**

> Okay well done Claude. Now to Problem 10: Reflection. Please open Output/Desk\_Tickets.html and fill in the Reflection tab with a detailed and thorough explanation of: how we would evaluate the performance of the agents on each ticket and why; how the actual plan compared to the expected plan for each ticket; what would have been simpler as one agent with tools rather than the system and why; three new problems Campus Customs might face that this agent team could solve as it is wit the tools we've built; and three new problems Campus Customs might face that this agent team could not solve with the tools we've built, and explain what tools or agents we would need to solve them. Please tie every answer back to this app and the three tickets we ran, using ticket tabs and the cash tab as evidence. Please don't be generic, reference details about Campus Customs and the experience we just went through.

**Time given:** 2026-10-04 15:41:24 -04:00

**Notes:**

First prompt worked.

## Problem 11  -  Submit to GitHub

**Prompt given:**

> Alright Claude, this has been great. Now let's do the last problem, Problem 11: Submit to GitHub. First, do a run through of everything we've built and make sure it's polished and ready for submission. In particular, look at AI\_Prompts and make sure that all my prompts have been included and that notes for each section are correct (if I needed more than one prompt, explain why and what the new prompt did; if not, say the first prompt worked). I want this whole project to be easy for a grader to read.
> Once you've done this, please push all my code to a public GitHub repo (needs to be public so a grader can clone it) and give me the repo URL. Please also put the URL in Output/Github\_URL.txt.
> As with the last homework, do not push my real .env file. I do however want you to include both database files in data/ (the og and the working copy).
> this image is the expectation for the file layout.

**Time given:** 2026-10-04 15:48:33 -04:00

**Notes:**

First prompt worked.
