#!/usr/bin/env bash
# TDOC GITHUB-SECURITY v1.0.0 — account settings, no secret retrieval or visibility changes.
set -uo pipefail
umask 077
main() {
  command -v gh >/dev/null && command -v python3 >/dev/null || { printf '%s\n' 'GitHub CLI and Python 3 are required.' >&2; return 1; }
  local mode="${1:---audit}" audit_dir previous_login owner repo safe_name blocked=0
  [[ "$mode" == --audit || "$mode" == --apply ]] || { printf '%s\n' 'Use --audit or --apply'; return 2; }
  audit_dir="${NEXUS_SECURITY_DIR:-$HOME/Æ/logs/github-security-$(date -u +%Y%m%dT%H%M%SZ)}"
  mkdir -p "$audit_dir" || return 1
  previous_login=$(gh api user --jq .login 2>/dev/null || true)
  for owner in Azazeleous machackabook crypticmetaverse thearchitectofgaia-boop; do
    if ! gh auth switch --hostname github.com --user "$owner" >/dev/null 2>&1; then
      printf '%s: authentication unavailable\n' "$owner"; blocked=$((blocked+1)); continue
    fi
    if ! gh api --paginate 'user/repos?affiliation=owner&per_page=100' --jq '.[].full_name' > "$audit_dir/$owner.repos"; then
      blocked=$((blocked+1)); continue
    fi
    while IFS= read -r repo; do
      [[ "$repo" == "$owner/"* && "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || continue
      safe_name=${repo//\//__}
      gh api "repos/$repo" --jq '{full_name,visibility,has_pages,security_and_analysis}' > "$audit_dir/$safe_name.before.json" || { blocked=$((blocked+1)); continue; }
      if [[ "$mode" == --apply ]]; then
        printf '%s\n' '{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}' > "$audit_dir/settings-request.json"
        if ! gh api --method PATCH "repos/$repo" --input "$audit_dir/settings-request.json" --silent; then
          printf '%s: scanning settings blocked or unsupported\n' "$repo"; blocked=$((blocked+1))
        fi
        gh api --method PUT "repos/$repo/vulnerability-alerts" --silent || blocked=$((blocked+1))
      fi
      gh api "repos/$repo" --jq '{full_name,visibility,has_pages,security_and_analysis}' > "$audit_dir/$safe_name.after.json" || blocked=$((blocked+1))
    done < "$audit_dir/$owner.repos"
  done
  if [[ -n "$previous_login" ]]; then gh auth switch --hostname github.com --user "$previous_login" >/dev/null 2>&1 || true; fi
  printf 'Settings receipts: %s; unavailable/unsupported operations: %s\n' "$audit_dir" "$blocked"
  printf '%s\n' 'Revocation, history scanning, MFA, branch protections and hosting response headers still need verification.'
  [[ "$blocked" == 0 ]]
}
main "$@"
