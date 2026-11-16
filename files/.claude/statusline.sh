#!/usr/bin/env bash
input=$(cat)

j() { echo "$input" | jq -r "$1" 2>/dev/null; }

model=$(j '.model.display_name // "Claude"')
dir=$(j '.workspace.current_dir // .cwd // empty')
pct=$(j '.context_window.used_percentage // 0')
cost=$(j '.cost.total_cost_usd // 0')
ms=$(j '.cost.total_duration_ms // 0')
five=$(j '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(j '.rate_limits.five_hour.resets_at // empty')
week=$(j '.rate_limits.seven_day.used_percentage // empty')

pct=$(printf '%.0f' "$pct" 2>/dev/null || echo 0)
[ "$pct" -gt 100 ] && pct=100
[ "$pct" -lt 0 ] && pct=0

name=$(basename "${dir:-$PWD}")
branch=""
if [ -n "$dir" ] && git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
  branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
    || git -C "$dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
fi

# Context bar (10 wide)
width=10
filled=$(( pct * width / 100 ))
bar_f=""; bar_e=""
for ((i=0;i<filled;i++)); do bar_f+="█"; done
for ((i=filled;i<width;i++)); do bar_e+="█"; done

secs=$(( ${ms%.*} / 1000 ))
mins=$(( secs / 60 ))
rem=$(( secs % 60 ))

CY=$'\033[36m'; GR=$'\033[92m'; DG=$'\033[32;2m'; YE=$'\033[33m'; GY=$'\033[90m'
MA=$'\033[35m'; RD=$'\033[91m'; RS=$'\033[0m'
SEP=" ${GY}|${RS} "

# Color usage: normal <70, yellow 70-89, red 90+
ucolor() { local p=${1%.*}; if [ "$p" -ge 90 ]; then echo "$RD"; elif [ "$p" -ge 70 ]; then echo "$YE"; else echo "$MA"; fi; }

effort=$(j '.effort.level // empty')

out="${CY}[${model}]${RS}"
[ -n "$effort" ] && out+=" ${MA}${effort}${RS}"
out+=" 📁 ${name}"
[ -n "$branch" ] && out+="${SEP}🌿 ${branch}"
out+="${SEP}${GR}${bar_f}${DG}${bar_e}${RS} ${pct}%"
out+="${SEP}${YE}$(printf '$%.2f' "$cost")${RS}"
out+="${SEP}⏱️ ${mins}m ${rem}s"

# Subscription usage (only shown for Pro/Max plans)
if [ -n "$five" ]; then
  f=$(printf '%.0f' "$five")
  usage="⚡ 5h $(ucolor "$f")${f}%${RS}"
  if [ -n "$five_reset" ]; then
    left=$(( five_reset - $(date +%s) ))
    [ "$left" -gt 0 ] && usage+=" ${GY}($((left/3600))h$(( (left%3600)/60 ))m)${RS}"
  fi
  if [ -n "$week" ]; then
    w=$(printf '%.0f' "$week")
    usage+=" · 7d $(ucolor "$w")${w}%${RS}"
  fi
  out+="${SEP}${usage}"
fi

printf '%s\n' "$out"
