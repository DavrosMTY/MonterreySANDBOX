#!/usr/bin/env bash
# Official portable version matching the validated renderer; ephemeral runner disk.
set -euo pipefail
: "${RUNNER_TEMP:?GitHub runner temporary directory is required}"
: "${GITHUB_PATH:?GitHub path file is required}"
mow_blender_version=4.3.2
mow_blender_archive="blender-${mow_blender_version}-linux-x64.tar.xz"
mow_blender_root="$RUNNER_TEMP/monterrey-blender"
mkdir -p "$mow_blender_root"
cd "$mow_blender_root"
curl --fail --location --retry 2 --output "$mow_blender_archive" "https://download.blender.org/release/Blender4.3/$mow_blender_archive"
curl --fail --location --retry 2 --output official.sha256 "https://download.blender.org/release/Blender4.3/blender-${mow_blender_version}.sha256"
awk -v archive="$mow_blender_archive" '$2 == archive || $2 == "*" archive {print}' official.sha256 > selected.sha256
test -s selected.sha256
sha256sum --check selected.sha256
tar --extract --xz --file="$mow_blender_archive"
printf '%s\n' "$mow_blender_root/blender-${mow_blender_version}-linux-x64" >> "$GITHUB_PATH"
"$mow_blender_root/blender-${mow_blender_version}-linux-x64/blender" --version
