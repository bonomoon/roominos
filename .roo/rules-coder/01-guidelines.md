# Coder Mode Guidelines (GPT-OSS Optimized)

## Process: Always Follow This Order

1. **Read** the target file first
2. **Plan** your change in text (explain what you will do)
3. **Edit** using search_and_replace with exact matching text
4. **Verify** by reading the file again to confirm
5. **Complete** with attempt_completion when done

## Tool Usage Rules

### search_and_replace (preferred for modifications)
- Use for ALL modifications to existing files
- The search text must EXACTLY match what is in the file
- Include enough context lines to make the match unique
- Change only what is needed, keep surrounding code untouched

### write_to_file (only for NEW files)
- Use ONLY when creating a completely new file
- Never use to overwrite an existing file with full content
- Always include proper file headers and encoding declarations

### read_file (always use first)
- Read BEFORE every edit — no exceptions
- If the file is large, read the relevant section

## Scope Control

- ONE file per response. Finish one file completely before moving to the next.
- ONE logical change per edit. Don't combine unrelated changes.
- If the task requires changes to multiple files, list all files that need changes first, then edit them one at a time.
- **MAX 2 files per conversation.** After creating 2 files, use attempt_completion and tell the user to start a New Task for the next batch.
- Do NOT use update_todo_list. Just create files directly.

## Language-Specific Notes

### Java / Spring
- Respect the existing code style (indentation, brace placement)
- Preserve existing imports — add new ones, don't reorganize
- Be aware of JDK version: JDK 8 (no var, no records), JDK 17 (sealed classes, text blocks), JDK 21 (virtual threads, pattern matching)
- Spring annotations: use existing patterns in the project

### C / Pro*C
- Preserve existing preprocessor directives
- Pro*C: do not modify EXEC SQL sections unless specifically asked
- Be careful with memory allocation — match malloc with free
- Preserve existing header include order

## Error Recovery

If an edit fails:
1. Re-read the file to see the current state
2. Identify why the search text didn't match
3. Adjust the search text to match exactly
4. Try the edit again

Do NOT guess or assume file contents. Always read first.
