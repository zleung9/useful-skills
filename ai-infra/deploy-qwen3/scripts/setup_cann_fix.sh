#!/usr/bin/env bash
# setup_cann_fix.sh — create the ASCEND_HOME_PATH wrapper for CANN 8.5.0
# (blocker #14: ATB libmki.so platform_config fix).
#
# PROBLEM: libmki.so (used by ATB) constructs the path
#   $ASCEND_HOME_PATH/runtime/data/platform_config
# but CANN 8.5.0 installs the SoC .ini configs at
#   /usr/local/Ascend/cann-8.5.0/aarch64-linux/data/platform_config
# (the runtime/ dir has NO data/ subdir). ATB then fails
# "Initialize platform manager" -> ReshapeAndCacheNdKernel not found ->
# atb::OperationSetup segfault in the mki logger during inference.
#
# FIX: /usr/local is root-owned (no symlink possible there), so create a
# user-local wrapper $HOME/cann-fix that mirrors cann-8.5.0 via symlinks to
# every real subdir, PLUS a real runtime/data/platform_config symlink to the
# actual .ini dir. Then export ASCEND_HOME_PATH=$HOME/cann-fix in the launch
# script (after sourcing the CANN set_env scripts). Only libmki.so reads this
# at runtime; the graph-engine libs (aoe/metadef/data_flow/tsdclient/mmpa)
# are not exercised under --enforce-eager.
set -e
CANN=/usr/local/Ascend/cann-8.5.0
FIX=${1:-$HOME/cann-fix}

rm -rf "$FIX"
mkdir -p "$FIX"

# Symlink every top-level entry of cann-8.5.0 into the wrapper.
for entry in "$CANN"/*; do
  name=$(basename "$entry")
  ln -sf "$entry" "$FIX/$name"
done

# Replace the symlinked runtime/ with a real dir that adds data/platform_config.
rm -f "$FIX/runtime"
mkdir -p "$FIX/runtime/data"
# Re-symlink the real runtime subdirs.
for sub in bin include lib64; do
  [ -e "$CANN/runtime/$sub" ] && ln -sf "$CANN/runtime/$sub" "$FIX/runtime/$sub"
done
# The crucial addition: runtime/data/platform_config -> the real SoC .ini dir.
ln -sf "$CANN/aarch64-linux/data/platform_config" "$FIX/runtime/data/platform_config"

echo "cann-fix wrapper created at $FIX"
echo "  platform_config -> $(readlink "$FIX/runtime/data/platform_config")"
ls "$FIX/runtime/data/platform_config" | head -3
echo "Add to your launch script AFTER sourcing CANN set_env:"
echo "  export ASCEND_HOME_PATH=$FIX"
