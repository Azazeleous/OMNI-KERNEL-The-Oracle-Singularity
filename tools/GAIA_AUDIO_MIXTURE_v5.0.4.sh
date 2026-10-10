#!/usr/bin/env bash
# [SS][TDOC-AUDIO-MIXTURE-V5.0.4] Diagnostic, auxiliary recognizer, model and SSH launchers.
(
gaia_audio_mixture_v504() {
  set -uo pipefail
  umask 077
  local nx_root="${AE:-$HOME/Æ}" nx_stage nx_target nx_stamp nx_downloads nx_action="${1:-diagnose}" nx_input nx_db nx_rc
  for nx_cmd in bash mkdir mktemp cp mv chmod cmp date rm; do
    command -v "$nx_cmd" >/dev/null || { printf 'BLOCKED: Missing %s\n' "$nx_cmd" >&2; return 1; }
  done
  mkdir -p -- "$nx_root/autonomous" "$nx_root/logs" "$nx_root/downloads" || return 1
  nx_root="$(cd -- "$nx_root" && pwd)" || return 1
  nx_target="$nx_root/autonomous/GAIA_AUDIO_MIXTURE_v5.0.4.sh"
  nx_stamp="$(date -u +%Y%m%dT%H%M%SZ).$BASHPID"
  nx_stage="$(mktemp "$nx_root/autonomous/.audio-mixture.XXXXXX")" || return 1
  {
    printf '#!/usr/bin/env bash\n# [SS][TDOC-AUDIO-MIXTURE-V5.0.4]\n(\n'
    declare -f gaia_audio_diag_v504 gaia_audio_mixture_v504
    printf '\ngaia_audio_mixture_v504 "$@"\n)\n'
  } > "$nx_stage" || { rm -f -- "$nx_stage"; return 1; }
  bash -n "$nx_stage" || { rm -f -- "$nx_stage"; return 1; }
  if [[ -e "$nx_target" ]] && ! cmp -s "$nx_stage" "$nx_target"; then
    cp -p -- "$nx_target" "$nx_target.backup.$nx_stamp" || return 1
  fi
  chmod 700 "$nx_stage" && mv -f -- "$nx_stage" "$nx_target" || return 1
  nx_downloads="${NEXUS_AUDIO_DOWNLOADS:-$nx_root/downloads}"
  if [[ -z "${NEXUS_AUDIO_DOWNLOADS:-}" && -d "$HOME/storage/downloads" && -w "$HOME/storage/downloads" ]]; then nx_downloads="$HOME/storage/downloads"; fi
  mkdir -p -- "$nx_downloads" || return 1
  if [[ -e "$nx_downloads/GAIA_AUDIO_MIXTURE_v5.0.4.sh" ]] && ! cmp -s "$nx_target" "$nx_downloads/GAIA_AUDIO_MIXTURE_v5.0.4.sh"; then
    cp -p -- "$nx_downloads/GAIA_AUDIO_MIXTURE_v5.0.4.sh" "$nx_downloads/GAIA_AUDIO_MIXTURE_v5.0.4.sh.backup.$nx_stamp" || return 1
  fi
  cp -- "$nx_target" "$nx_downloads/GAIA_AUDIO_MIXTURE_v5.0.4.sh" || return 1
  case "$nx_action" in
    diagnose) gaia_audio_diag_v504 ;;
    abracadabra)
      # Read a supplied audio file; physical capture belongs to the feedback checker.
      if [[ "${2:-}" != register && "${2:-}" != recognise ]]; then
        printf 'Usage: bash %s abracadabra register|recognise AUDIO_FILE\n' "$nx_target" >&2; return 2
      fi
      for nx_cmd in python3 song_recogniser realpath timeout; do
        command -v "$nx_cmd" >/dev/null || { printf 'BLOCKED: Missing %s; Abracadabra has not run.\n' "$nx_cmd" >&2; return 1; }
      done
      [[ -f "${3:-}" ]] || { printf 'BLOCKED: Supply an existing audio file.\n' >&2; return 2; }
      nx_input="$(realpath -e -- "$3")" || return 1
      # This upstream bug was observed in the inspected 0.1 source. Do not silently accept it.
      timeout --foreground 8s python3 -c 'from abracadabra.fingerprint import hash_point_pair as h; assert h((1000,0),(1100,1)) != h((1000,0),(1100,2)), "Abracadabra time delta is discarded; repair and verify the installed library first"' || return 1
      nx_db="$nx_root/state/audio-mixture-v5.0.4/abracadabra"
      mkdir -p -- "$nx_db" || return 1
      cd -- "$nx_db" || return 1
      mkdir .writer-lock 2>/dev/null || { printf 'BLOCKED: Abracadabra database is busy; inspect a stale lock before retrying.\n' >&2; return 1; }
      trap 'rmdir .writer-lock 2>/dev/null || true' EXIT
      if [[ "$2" == register ]]; then
        if [[ -f hash.db ]]; then
          timeout --foreground 8s python3 -c 'import sqlite3,sys; a=sqlite3.connect("hash.db", timeout=5); b=sqlite3.connect(sys.argv[1]); a.backup(b); b.close(); a.close()' "hash.db.backup.$nx_stamp" || return 1
        else
          timeout --foreground 15s song_recogniser initialise || return 1
        fi
      elif [[ ! -f hash.db ]]; then
        printf 'BLOCKED: Register reference audio before recognition.\n' >&2; return 1
      fi
      printf 'COMPONENT=abracadabra; acoustic_playback_verified=false\n' >&2
      timeout --foreground 120s song_recogniser "$2" "$nx_input"
      nx_rc=$?
      rmdir .writer-lock 2>/dev/null || true
      trap - EXIT
      return "$nx_rc"
      ;;
    omniaudio)
      command -v nexa >/dev/null || { printf 'BLOCKED: A compatible Nexa OmniAudio runtime is not installed.\n' >&2; return 1; }
      printf 'COMPONENT=NexaAI/OmniAudio-2.6B; acoustic_playback_verified=false\n' >&2
      # Explicit mode only. The installed SDK may download weights; compatibility is unverified here.
      nexa run omniaudio -st
      ;;
    ssh)
      shift
      [[ "$#" -gt 0 ]] || { printf 'BLOCKED: Supply the existing SSH alias or user@host, with -p PORT if needed. No credentials are logged.\n' >&2; return 2; }
      command -v ssh >/dev/null || { printf 'BLOCKED: ssh is unavailable.\n' >&2; return 1; }
      ssh -o ConnectTimeout=8 -o ConnectionAttempts=1 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 "$@"
      ;;
    help|--help|-h)
      printf 'Usage: bash %s [diagnose|abracadabra register|recognise AUDIO_FILE|omniaudio|ssh SSH_ARGUMENTS]\n' "$nx_target"
      ;;
    *) printf 'Unknown action: %s\n' "$nx_action" >&2; return 2 ;;
  esac
}

gaia_audio_diag_v504() {
  set -uo pipefail
  umask 077
  export LC_ALL=C
  local nx_root="${AE:-$HOME/Æ}" nx_cmd nx_stage nx_target nx_stamp nx_dir nx_log nx_step nx_rc nx_latest="" nx_path nx_downloads
  for nx_cmd in bash mkdir mktemp tee tail grep cp mv chmod cmp date rm; do
    command -v "$nx_cmd" >/dev/null || { printf 'BLOCKED: Missing %s\n' "$nx_cmd" >&2; return 1; }
  done
  mkdir -p -- "$nx_root/autonomous" "$nx_root/logs" "$nx_root/downloads" || return 1
  nx_root="$(cd -- "$nx_root" && pwd)" || return 1
  nx_stamp="$(date -u +%Y%m%dT%H%M%SZ).$BASHPID"
  nx_target="$nx_root/autonomous/GAIA_AUDIO_DIAG_v5.0.4.sh"
  nx_stage="$(mktemp "$nx_root/autonomous/.audio-diag.XXXXXX")" || return 1
  {
    printf '#!/usr/bin/env bash\n# [SS][TDOC-AUDIO-DIAG-V5.0.4]\n(\n'
    declare -f gaia_audio_diag_v504
    printf '\ngaia_audio_diag_v504 "$@"\n)\n'
  } > "$nx_stage" || { rm -f -- "$nx_stage"; return 1; }
  bash -n "$nx_stage" || { rm -f -- "$nx_stage"; return 1; }
  if [[ -e "$nx_target" ]] && ! cmp -s -- "$nx_stage" "$nx_target"; then
    cp -p -- "$nx_target" "$nx_target.backup.$nx_stamp" || return 1
  fi
  chmod 700 "$nx_stage" && mv -f -- "$nx_stage" "$nx_target" || return 1
  nx_downloads="${NEXUS_AUDIO_DOWNLOADS:-$nx_root/downloads}"
  if [[ -z "${NEXUS_AUDIO_DOWNLOADS:-}" && -d "$HOME/storage/downloads" && -w "$HOME/storage/downloads" ]]; then nx_downloads="$HOME/storage/downloads"; fi
  mkdir -p -- "$nx_downloads" || return 1
  if [[ -e "$nx_downloads/GAIA_AUDIO_DIAG_v5.0.4.sh" ]] && ! cmp -s -- "$nx_target" "$nx_downloads/GAIA_AUDIO_DIAG_v5.0.4.sh"; then
    cp -p -- "$nx_downloads/GAIA_AUDIO_DIAG_v5.0.4.sh" "$nx_downloads/GAIA_AUDIO_DIAG_v5.0.4.sh.backup.$nx_stamp" || return 1
  fi
  cp -- "$nx_target" "$nx_downloads/GAIA_AUDIO_DIAG_v5.0.4.sh" || return 1
  nx_dir="$(mktemp -d "$nx_root/logs/audio-diag-v5.0.4.$nx_stamp.XXXXXX")" || return 1
  nx_log="$nx_dir/report.txt"
  gaia_diag_query_v504() {
    nx_step="$1"; shift
    printf '\n[%s]\n' "$nx_step" | tee -a "$nx_log" || return 125
    if ! command -v "$1" >/dev/null; then
      printf 'MISSING: %s\n' "$1" | tee -a "$nx_log"
      return 127
    fi
    if ! command -v timeout >/dev/null; then
      printf 'SKIPPED: timeout unavailable; this query was not allowed to hang.\n' | tee -a "$nx_log"
      return 127
    fi
    timeout --foreground 6s "$@" 2>&1 | tee "$nx_dir/$nx_step.txt" -a "$nx_log"
    local nx_pipe=("${PIPESTATUS[@]}")
    nx_rc="${nx_pipe[0]}"
    [[ "${nx_pipe[1]}" -eq 0 ]] || return 125
    printf 'EXIT=%s\n' "$nx_rc" | tee -a "$nx_log" || return 125
    return "$nx_rc"
  }
  printf 'AUDIO_DIAGNOSTIC_VERSION=5.0.4\nPREFIX=%s\nacoustic_playback_verified=false\n' "${PREFIX:-unset}" | tee -a "$nx_log" || return 1
  printf '\n[EXECUTABLES]\n' | tee -a "$nx_log"
  for nx_cmd in python3 ffmpeg pulseaudio pactl pacat aplay arecord termux-microphone-record termux-media-player termux-volume song_recogniser nexa ssh timeout; do
    printf '%s: %s\n' "$nx_cmd" "$(command -v "$nx_cmd" || printf 'MISSING')" | tee -a "$nx_log"
  done
  shopt -s nullglob
  for nx_path in "$nx_root"/logs/termux-audio-v5.0.3.*/recovery.log; do
    if [[ -z "$nx_latest" || "$nx_path" -nt "$nx_latest" ]]; then nx_latest="$nx_path"; fi
  done
  printf '\n[LATEST_FAILURE]\n' | tee -a "$nx_log"
  if [[ -n "$nx_latest" ]]; then
    printf 'FILE=%s\n' "$nx_latest" | tee -a "$nx_log"
    tail -n 45 -- "$nx_latest" | tee -a "$nx_log"
  else
    printf 'No saved v5.0.3 recovery log found under the current AE root.\n' | tee -a "$nx_log"
  fi
  # Queries only: no reinstall, server restart, module loading, volume changes or recording.
  if [[ "${PREFIX:-}" =~ ^/data/(data|user/[0-9]+)/[^/]*termux[^/]*/files/usr$ ]]; then
    gaia_diag_query_v504 PACKAGE_AUDIT dpkg --audit || true
    gaia_diag_query_v504 PACKAGE_STATUS dpkg-query -W '-f=${binary:Package}\t${Status}\t${Version}\n' python termux-api ffmpeg pulseaudio || true
    gaia_diag_query_v504 ANDROID_MEDIA_VOLUME termux-volume || true
    gaia_diag_query_v504 MICROPHONE_API termux-microphone-record -i || true
    gaia_diag_query_v504 NATIVE_PLAYER_API termux-media-player info || true
    printf '\n[INSTALLED_ANDROID_SINK_MODULES]\n' | tee -a "$nx_log"
    local nx_modules=("$PREFIX"/lib/pulseaudio/modules/module-{aaudio,sles}-sink.so "$PREFIX"/lib/pulse-*/modules/module-{aaudio,sles}-sink.so)
    if [[ "${#nx_modules[@]}" -eq 0 ]]; then printf 'No AAudio/OpenSL ES sink module files found.\n' | tee -a "$nx_log"; fi
    for nx_path in "${nx_modules[@]}"; do printf '%s\n' "$nx_path" | tee -a "$nx_log"; done
    if [[ -r "$PREFIX/etc/pulse/default.pa" ]]; then
      printf '\n[ANDROID_SINK_CONFIGURATION]\n' | tee -a "$nx_log"
      grep -nE '^[[:space:]]*(load-module[[:space:]]+module-(sles|aaudio|null)-sink|set-default-sink)' "$PREFIX/etc/pulse/default.pa" | tee -a "$nx_log" || true
    fi
  fi
  gaia_diag_query_v504 PULSE_DAEMON pulseaudio --check || true
  if gaia_diag_query_v504 PULSE_ENDPOINT pactl info; then
    gaia_diag_query_v504 PULSE_SINKS pactl list short sinks || true
    gaia_diag_query_v504 PULSE_MODULES pactl list short modules || true
    gaia_diag_query_v504 DEFAULT_SINK pactl get-default-sink || true
    gaia_diag_query_v504 DEFAULT_SINK_MUTE pactl get-sink-mute @DEFAULT_SINK@ || true
    gaia_diag_query_v504 DEFAULT_SINK_VOLUME pactl get-sink-volume @DEFAULT_SINK@ || true
  fi
  if command -v aplay >/dev/null; then gaia_diag_query_v504 ALSA_PLAYBACK_DEVICES aplay -l || true; fi
  if command -v arecord >/dev/null; then gaia_diag_query_v504 ALSA_CAPTURE_DEVICES arecord -l || true; fi
  printf '\nDIAGNOSTIC_COMPLETE; playback has not been verified.\nREPORT=%s\nPaste LATEST_FAILURE and the failed query output above.\n' "$nx_log" | tee -a "$nx_log" || return 1
  printf '%s AUDIO_DIAG v5.0.4 %s\n' "$nx_stamp" "$nx_log" >> "$nx_root/logs/ss_activity_$(date -u +%Y%m%d).log" || return 1
}

gaia_audio_mixture_v504 "$@"
)
