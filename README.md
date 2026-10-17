#AI Gateway

A terminal-first way to work with browser-based AI on your own codebase.

AI Gateway connects your terminal to an AI chat session already open in Chrome. It helps you ask questions about a project, provide relevant file context, keep reusable project notes, and propose code changes without having to manually copy and paste everything into a browser chat.

The aim is to make browser-based AI more useful for real development work—while keeping the developer in control of which context is shared and which file changes are applied.

Table of contents

Why AI Gateway?

What can you do with it?

Ask questions about your code

Make targeted code changes

Maintain reusable project knowledge

Work across more than one project

How it fits together

Command overview

Design principles

Current status and limitations

Project structure

Where setup instructions belong

License

Why AI Gateway?

Using an AI chat while coding often means repeatedly switching windows, pasting code, explaining the project again, and manually transferring suggested changes back into files.

AI Gateway brings several of those steps into one terminal workflow:

Work from your terminal. Send prompts to the chat session in your browser without manually moving every request between the terminal and browser.

Give AI relevant project context. Register your own project directories and refer to specific files in your prompt.

Spend less time repeating project background. Keep project knowledge in local memory files and choose when a memory snapshot should be included in a request.

Review changes before they reach your files. Use the explicit edit workflow to inspect a proposed change and its explanation, then approve or reject it.

Keep projects organized. Configure multiple workspaces and reference files using stable numeric IDs.

Reuse browser-based AI access. The current workflow uses an existing signed-in Chrome session rather than requiring an AI API key from AI Gateway itself.

What can you do with it?

Ask questions about your code

Register a project folder as a workspace, then reference a file in a natural-language prompt. The gateway can attach the referenced file's contents as context, so you can ask about implementation details without manually pasting the file.

Example:

Explain the authentication flow in <1/src/auth.js>

Here, 1 is the workspace ID and src/auth.js is the path relative to that workspace. File references use the form <workspace_id/relative/path> and can be combined in one prompt.

Make targeted code changes

Enter edit mode, describe the change, and reference the file you want to modify. The gateway uses a structured edit workflow to validate the model's proposal and show the intended change for approval before applying it.

Example:

/edit
Add input validation to <1/src/auth.js> and preserve the existing behavior.

Review every proposed diff. AI Gateway is designed to keep you in the approval loop; it does not make model-generated code automatically trustworthy.

Maintain reusable project knowledge

Project memory lets you keep durable notes about architecture, decisions, conventions, and progress on your own machine. You control when that context is supplied to a normal prompt, rather than sending all local memory files with every request.

The /save command asks the current browser conversation to identify useful long-term project knowledge and attempts to save a validated proposal to local memory files.

Work across more than one project

Configure multiple workspace directories. The gateway assigns each one a numeric ID, which you can use to refer to files unambiguously.

/workspace add "D:\Projects\backend"
/workspace add "D:\Projects\frontend"
/workspace

Workspace configuration only registers directories for gateway workflows; removing a workspace does not delete its files.

How it fits together

At a high level, AI Gateway connects a few pieces:

Browser transport connects to an already-running Chrome session using Playwright.

Prompt and context assembly combines your request with the file context you explicitly reference and any memory snapshot that is enabled for that request.

Project memory manages local notes and the rules for injecting those notes into prompts.

Workspace and file tools resolve file references and prepare structured edits.

Edit review validates the proposed change and asks for approval before writing it.

The intent is to keep browser interaction, context handling, memory, workspace management, and file editing as separate responsibilities so each area can evolve without unnecessarily disturbing the others.

Command overview

Commands currently available in the CLI include:

Command

What it helps you do

/workspace

See configured workspaces and their status.

/workspace add <directory>

Register a project directory.

/workspace remove <id>

Remove a directory from the workspace configuration.

/workspace clear

Clear all workspace entries without deleting project files.

/edit

Enter the controlled file-edit workflow.

/cancel

Leave edit mode.

/memory use

Include project memory with the next normal prompt only.

/memory on

Enable memory mode.

/memory off

Disable future memory injection.

/memory refresh

Queue the current memory snapshot for the next prompt.

/save

Extract durable knowledge from the current browser conversation and attempt to save a validated memory proposal.

/exit

Exit the CLI.

Planned: /commands will provide an in-terminal command index with syntax, descriptions, and examples. Focused help such as /commands memory or /commands workspace can make individual workflows easier to discover. This help command is not implemented in the current CLI yet.

Design principles

Developer control: memory injection is explicit, and proposed file edits require review.

Local-first project state: workspace settings and project memory are kept locally by default.

Explicit file references: the gateway should use files you identify, not guess which project file you meant.

Focused responsibilities: browser transport, context assembly, memory, workspaces, and editing are separate components.

Provider-agnostic direction: the architecture aims to support different browser-based AI providers over time.

Current status and limitations

AI Gateway is an active development project, not a finished or universally compatible coding agent.

The current workflow has been developed around ChatGPT in Chrome. Other providers should not be considered supported until their flows have been tested.

Browser interaction depends on the chat website's interface, which can change and break automation.

Chrome must remain open and reachable through remote debugging, with a valid signed-in session when required.

Browser service usage limits and account restrictions still apply. AI Gateway does not bypass them.

The in-terminal /commands help feature and detailed setup documentation are still planned.

Model responses and suggested edits can be incorrect. Review changes and use version control or backups for important work.

Project structure

AI-gateway/
├── browser/       # Chrome connection and browser-chat transport
├── context/       # Prompt/context assembly and memory-session behavior
├── files/         # File references, edit protocol, validation, diffs and writes
├── memory/        # Project-memory prompts, parsing, management and saving
├── terminal/      # CLI display functions and edit approval
├── workspace/     # Workspace registration, validation and persistence
├── main.py        # Interactive CLI workflow
└── requirements.txt

Where setup instructions belong

This README focuses on what AI Gateway does and how it can help. Detailed installation, Chrome configuration, and environment-specific troubleshooting will be documented separately in SETUP.md.

License

No license file is currently present in the repository. Until a license is added, do not assume that the code is available for unrestricted reuse, redistribution, or modification.
