---
name: bigeye-config
description: Use when the user wants to configure the BigEye plugin's scope (workspace + filters), run the first-run wizard, or manage named profiles. Also auto-invoked by other BigEye skills when the config file is missing.
user-invocable: true
---

# BigEye Configuration

Owns the per-user profiles file at `~/.claude/bigeye-plugin/profiles.json`. This is the **only** skill that writes to that file.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared output formatting.

## Arguments

Parse `$ARGUMENTS` (space-separated). First token is the subcommand; anything after is arguments to that subcommand.

| Invocation | Behavior |
|---|---|
| (empty) or `show` | Print active profile name + all profiles in a table |
| `init` | Run wizard, write a profile, set as default. If a file already exists, ask whether to overwrite or add |
| `add <name>` | Run wizard, add a new profile without changing the default |
| `switch <name>` | Set `default_profile` to `<name>` |
| `edit <name>` | Re-run wizard against an existing profile |
| `delete <name>` | Remove a profile. Refuse if it is the default and no alternative exists |

## Config File

**Path:** `~/.claude/bigeye-plugin/profiles.json`

**Schema:**

```json
{
  "default_profile": "work-area",
  "profiles": {
    "work-area": {
      "workspace_id": 42,
      "data_source_ids": [17],
      "table_ids": [],
      "table_names": ["orders_main", "orders_virtual_recent"],
      "schema_names": [],
      "tags": []
    }
  }
}
```

**Field rules:**
- `default_profile` must reference a key in `profiles`.
- Each profile requires `workspace_id`. All other fields are optional arrays.
- Missing filter fields default to empty arrays when written.

## Procedure

### Subcommand: `show` (or no argument)

1. Use the `Read` tool to read `~/.claude/bigeye-plugin/profiles.json`. If the file doesn't exist, print:
   ```
   No BigEye profiles configured yet.
   Run `/bigeye-config init` to set one up.
   ```
   and stop.
2. Parse the JSON.
3. Print:
   ```
   ## BigEye Profiles

   Active (default): **{default_profile}**

   | Profile | Workspace | Sources | Tables | Schemas | Tags |
   |---------|-----------|---------|--------|---------|------|
   | {name} | {workspace_id} | {count} | {count} | {count} | {count} |
   ```
   One row per profile. Counts are the lengths of the corresponding arrays.

### Subcommand: `init`

1. Use the `Read` tool to check whether `~/.claude/bigeye-plugin/profiles.json` already exists.
2. If it exists, ask:
   ```
   A config file already exists. What would you like to do?
   1. Overwrite with a new default profile
   2. Add a new profile alongside the existing ones (same as `/bigeye-config add <name>`)
   3. Cancel
   ```
   - Option 1 → continue the wizard, then replace the file entirely with a single profile marked default.
   - Option 2 → ask for a profile name, then continue as in `add`.
   - Option 3 → stop.
3. If it does not exist, ask: "What would you like to name this profile? (default: `work-area`)" and use the answer as the profile name.
4. Run the **Wizard Flow** below to fill in fields.
5. Ensure the directory exists using the `Bash` tool:
   ```
   mkdir -p ~/.claude/bigeye-plugin
   ```
6. Use the `Write` tool to write `~/.claude/bigeye-plugin/profiles.json` with the final content.
7. Print:
   ```
   Wrote profile `{name}` to ~/.claude/bigeye-plugin/profiles.json (set as default).
   Try `/bigeye-triage` to see scoped issues.
   ```

### Subcommand: `add <name>`

1. Read the existing file. If it's missing, tell the user to run `/bigeye-config init` first and stop.
2. Run the Wizard Flow for the new profile.
3. Merge the new profile into `profiles` without changing `default_profile`.
4. Write the file.
5. Print confirmation.

### Subcommand: `switch <name>`

1. Read the file. If missing, tell the user to run `/bigeye-config init` first.
2. If `<name>` is not a key in `profiles`, print available profiles and ask the user to pick one. Stop without writing.
3. Update `default_profile` to `<name>` and write the file.
4. Print: `Switched default profile to \`{name}\`.`

### Subcommand: `edit <name>`

1. Read the file. If missing or `<name>` not in `profiles`, error as in `switch`.
2. Show the current profile values.
3. Run the Wizard Flow, pre-filling defaults from the current values (let the user press enter to keep each one).
4. Replace the profile in place. Do not change `default_profile`.
5. Write the file and print confirmation.

### Subcommand: `delete <name>`

1. Read the file. If missing or `<name>` not in `profiles`, error as above.
2. If `<name>` is the `default_profile` and there is only one profile, refuse: "Cannot delete the only profile. Run `/bigeye-config add <new>` first, then delete this one." Stop.
3. If `<name>` is the `default_profile` but other profiles exist, ask which profile to promote as the new default.
4. Remove the profile from `profiles` and update `default_profile` if needed.
5. Write the file and print confirmation.

## Wizard Flow

Ask one question at a time. Show the running summary after each answer.

1. **Workspace ID.** Ask: "What's your BigEye workspace_id? (integer)" Validate that the answer parses as an integer. Optionally, if the `mcp__bigeye__list_data_sources` tool is available, call it with `workspace_id: {answer}` to confirm the workspace is reachable — if it errors, warn the user but allow them to proceed.
2. **Data sources.** Ask: "Filter by data source? (y/n)" If yes, call `mcp__bigeye__list_data_sources` with the chosen `workspace_id`, show the result as a numbered list, and let the user pick one or more by index. Store the chosen integer IDs in `data_source_ids`.
3. **Tables.** Ask: "Filter by specific tables? (y/n)" If yes, ask for one name per line (blank line to finish). For each name, attempt to resolve it to a table ID using whichever of these MCP tools is available, in order: `mcp__bigeye-knowledgebase__search_metadata`, `mcp__bigeye__list_tables` (if present), else skip resolution. Store the original names in `table_names` and any resolved IDs in `table_ids`. Warn about unresolved names but don't block.
4. **Schemas.** Ask: "Filter by schema? (y/n)" If yes, ask for schema names (one per line). Store in `schema_names`.
5. **Tags.** Ask: "Filter by tags? (y/n)" If yes, ask for tag names (one per line). Store in `tags`.
6. **Summary and confirmation.** Show:
   ```
   Profile summary:
     workspace_id: {...}
     data_source_ids: [...]
     table_names: [...]
     table_ids: [...]
     schema_names: [...]
     tags: [...]

   Save this profile? (y/n)
   ```
   On `n`, restart the wizard. On `y`, continue to the caller's write step.

## Notes

- Always pretty-print JSON with 2-space indent when writing.
- Never include comments in the JSON file.
- When reading the file, handle `FileNotFoundError` by treating it as "no config yet."
- When the JSON fails to parse, print the parse error and suggest `/bigeye-config init` to recreate.
