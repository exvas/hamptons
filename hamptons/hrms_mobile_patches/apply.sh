#!/usr/bin/env bash
# Re-apply hamptons patches to the HRMS mobile app (PWA at /hrms) and rebuild it.
# Run after every HRMS update (bench update / git reset of apps/hrms):
#   bash apps/hamptons/hamptons/hrms_mobile_patches/apply.sh
set -euo pipefail
BENCH="$(cd "$(dirname "$0")/../../../.." && pwd)"
HRMS="$BENCH/apps/hrms"
PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$HRMS"
for patch in "$PATCH_DIR"/*.patch; do
	name="$(basename "$patch")"
	if git apply --reverse --check "$patch" 2>/dev/null; then
		echo "already applied: $name"
	elif git apply --check "$patch"; then
		git apply "$patch" && echo "applied: $name"
	else
		echo "FAILED: $name no longer applies to this HRMS version; update the patch." >&2
		exit 1
	fi
done

cd "$HRMS/frontend"
yarn build
grep -q "Medical certificate is mandatory" "$HRMS"/hrms/public/frontend/assets/Form-*.js \
	&& echo "OK: mobile app rebuilt with hamptons patches" \
	|| { echo "FAILED: marker missing from build" >&2; exit 1; }
