# AI Gateway — Plan

## Goal
Build a ₹0 terminal-based gateway for students who cannot use paid/API coding agents. During development and testing, use the ChatGPT browser version only. Keep the architecture provider-agnostic so Claude and Gemini browser-based free models can be added later.

## Current Milestone
Finish the reliable ChatGPT browser ↔ terminal core before adding project files and long-term memory.

## Next Work
1. Make `--file` / file-context handling work.
2. Improve terminal Markdown rendering.
3. Add project-aware `.ai/` memory files.
4. Add persistent session/project state.
5. Later add Claude and Gemini provider adapters.

## Product Direction
The model is not the product. The gateway's value is the project-context layer that lets a student resume work with useful, structured project memory.
