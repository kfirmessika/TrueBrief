---
name: read-summarize
description: Read and summarize files, logs, or large amounts of text using read-only tools and the Haiku model.
parameters:
  - name: path
    type: string
    required: true
    default: ""
  - name: focus
    type: string
    required: false
    default: "general summary"
allowed-tools: Read, Grep, Glob
model: haiku
---

# /read-summarize Command

This slash command allows the user to explicitly request a reading and summarization of a file or folder path. It utilizes only read-only tools (`Read`, `Glob`, `Grep`) and runs on the cost-effective `haiku` model.

## Instructions
1. **Retrieve Content**: Use `Read` to get the content of the file at `path`. If `path` is a directory or if you need to locate files, use `Glob` and `Grep` as needed. Do NOT use write or execution tools.
2. **Focus Area**: Tailor the summary based on the `focus` parameter if provided (e.g., focus on errors, configurations, functions, etc.).
3. **Structured Summary**: Output a clear, structured summary:
   - **File / Path Analyzed**: `path`
   - **Executive Summary**: High-level overview.
   - **Key Content**: Bullet points highlighting key details, findings, or code structure.
