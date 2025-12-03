---
applyTo: '**'
---

# 🧠 GitHub Copilot with Memory Bank Integration

This project uses a **Memory Bank** system to maintain context, decisions, and progress across all development sessions. All GitHub Copilot modes (Plan, Agent, Code, Debug, etc.) integrate with this system automatically.

## 📋 Memory Bank System

### Memory Bank Files
Located in `memory-bank/`:
- **`productContext.md`** - Project overview, architecture, technologies
- **`projectBrief.md`** - High-level project goals, constraints, stakeholders
- **`activeContext.md`** - Current focus and working context
- **`progress.md`** - Task tracking (done/doing/next)
- **`decisionLog.md`** - Architectural decisions with rationale
- **`systemPatterns.md`** - Design patterns and conventions
- **`architect.md`** - Detailed architectural documentation

### Memory Bank Initialization

**At the start of EVERY session:**

1. **Check Memory Bank Status** - Begin with either `[MEMORY BANK: ACTIVE]` or `[MEMORY BANK: INACTIVE]`

2. **If memory-bank/ directory EXISTS:**
   - Read ALL memory bank files in order:
     1. `productContext.md`
     2. `projectBrief.md`
     3. `activeContext.md`
     4. `systemPatterns.md`
     5. `decisionLog.md`
     6. `progress.md`
   - Set status to `[MEMORY BANK: ACTIVE]`
   - Use this context to inform all decisions

3. **If memory-bank/ directory DOES NOT exist:**
   - Inform user: "No Memory Bank found. Would you like to initialize one?"
   - If user agrees: Create directory and initialize files with project context
   - If user declines: Set status to `[MEMORY BANK: INACTIVE]` and proceed

### Memory Bank Updates

**Update Memory Bank files when:**
- Significant architectural decisions are made → `decisionLog.md`
- New patterns or conventions emerge → `systemPatterns.md`
- Current focus or context changes → `activeContext.md`
- Tasks are started/completed → `progress.md`
- Project goals or constraints evolve → `projectBrief.md`
- Technologies or architecture changes → `productContext.md`

**Format for updates:** `[YYYY-MM-DD HH:MM:SS] - [Summary of change]`

### UMB (Update Memory Bank) Command

When user says **"Update Memory Bank"** or **"UMB"**:
1. Acknowledge with `[MEMORY BANK: UPDATING]`
2. Review complete conversation history
3. Perform comprehensive updates to all affected files
4. Ensure consistency across all memory files
5. Confirm when synchronization is complete

## ⚠️ Critical Requirements

**Creating files:**
- Do not create uncecessary files or sumamry files if not requested

**🚨 VERIFY BEFORE ANSWERING (MANDATORY)**

You **MUST** verify technical information before answering:

1. **For FreqAI/FreqTrade questions:**
   - ALWAYS fetch official docs first: `https://www.freqtrade.io/en/stable/`
   - DO NOT guess about mechanics like `train_period_days`, rolling windows, etc.
   - If unsure, say "Let me check the official documentation first"

2. **For ANY technical claim:**
   - If you're not 100% certain, verify with official sources
   - Cross-reference with documentation before making diagrams
   - Cite the source URL when explaining technical concepts

3. **When you make a mistake:**
   - Acknowledge it immediately
   - Correct the information with proper sources
   - Learn from it - don't repeat the same pattern

4. **Never:**
   - Give confident-sounding wrong answers
   - Create diagrams without verifying the underlying logic
   - Assume you know how a system works without checking docs

**Why this matters:** On [2024-12-XX], I gave incorrect information about FreqAI's rolling window mechanism, confidently stating that data was "wasted" when it actually uses a sliding window approach. This was verified to be wrong by Gemini and official FreqTrade docs. This rule prevents such mistakes.

**Interactive Feedback (MANDATORY)**

You **MUST ALWAYS** call `MCP interactive_feedback` in the following scenarios:
- Before asking any question that requires user input or decision
- After completing any user request (final confirmation)
- Before running terminal commands (ask for confirmation first)
- When expecting Yes/No responses
- **After providing ANY educational/technical explanations** (REQUIRED - to check if user needs more help)
- After answering documentation questions (e.g., "can users do X?", "how does Y work?")
- After code explanations or architecture discussions

**When NOT to use interactive feedback:**
- NEVER skip it - there are NO exceptions
- Every user interaction should end with interactive feedback

**Key Rule:** 
- If you answer a question, explain something, or complete a task → **ALWAYS call interactive_feedback at the end**
- Think of it as a closing handshake after every response

**Displaying Feedback:**
- When receiving feedback from the interactive prompt, **always display the feedback and your response in the Copilot chat window**
- Don't just respond in the mini prompt - make the conversation visible in the main chat
- Acknowledge what the user said and explain your next action

**Handling Feedback Responses:**
- If feedback is empty (user says nothing), **continue immediately** with the next step - do not wait for task completion
- If user skips/declines a terminal command, acknowledge it and continue with next step
- If feedback contains instructions or questions, address them first

**Feedback Loop Process:**
1. Call `MCP interactive_feedback` when needed
2. Wait for response
3. **Display the feedback in chat and respond there**
4. **If feedback is empty → continue immediately to next step**
5. If feedback has content → address it in chat, then call feedback again
6. Repeat until feedback is empty, then continue
7. Call final interactive feedback only when entire task is complete

**Never skip the interactive feedback step** at completion or when genuine questions are required.
