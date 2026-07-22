---
name: read-summarize
description: Summarize large amounts of file content, data, or text information. Triggered when there is a significant volume of information to read and summarize.
allowed-tools: Read, Grep, Glob
model: haiku
---

# Read and Summarize Skill

This skill is designed to read and summarize large files, logs, or text. It operates on the `haiku` model with read-only permissions (`Read`, `Glob`, `Grep`).

## Instructions
1. Use `Read` to extract the contents of the target files. Use `Glob` or `Grep` if you need to search files or patterns.
2. Provide a concise, structured summary of the content.
