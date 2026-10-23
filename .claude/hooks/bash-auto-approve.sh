#!/usr/bin/env bash
# PreToolUse(Bash) auto-approver.
#
# Reads the Claude Code hook payload on stdin and decides the WHOLE Bash command
# in one shot — so a COMPOUND command (cd X && a && b || c | d) is judged as a
# single unit and never needs each sub-command to match a per-command allow rule.
# That is exactly what a plain `Bash(cd:*)` allow rule cannot do, and why compound
# dev commands used to prompt every time.
#
#   - deny : git push, and recursive rm (rm -r / rm -R / rm -rf) — irreversible
#   - ask  : other rm, and destructive / outbound verbs (sudo dd mkfs kill curl wget …)
#   - allow: everything else (cd, ruff, mypy, pytest, git status/add/commit, mv, grep, …)
#
# On any parsing trouble it stays silent (empty output, exit 0) so Claude Code falls
# back to its normal permission flow — fail safe, never fail open.

cmd="$(jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

emit() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":"%s"}}\n' "$1" "$2"
}

# --- deny: never auto-approve these ---
if printf '%s' "$cmd" | grep -Eq '(^|[;&|(`[:space:]])git[[:space:]]+push([[:space:]]|$)'; then
  emit deny "git push is not auto-approved (push manually when you mean to)"
  exit 0
fi
if printf '%s' "$cmd" | grep -Eq '(^|[;&|(`[:space:]])rm[[:space:]]+-[a-zA-Z]*[rR]'; then
  emit deny "recursive rm (rm -r / rm -rf) is not auto-approved"
  exit 0
fi

# --- ask: other rm, destructive or outbound; let the human glance ---
if printf '%s' "$cmd" | grep -Eq '(^|[;&|(`[:space:]])(rm|sudo|dd|mkfs|shutdown|reboot|kill|pkill|chown|curl|wget)([[:space:]]|$)|:[[:space:]]*\(\)[[:space:]]*\{|>[[:space:]]*/dev/(sd|nvme|disk)'; then
  emit ask "potentially destructive or outbound command — please confirm"
  exit 0
fi

# --- allow: normal dev work, cd-prefixed or compound ---
emit allow "auto-approved dev command"
exit 0