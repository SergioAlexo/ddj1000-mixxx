# Shared settings for the Ghidra wrappers. Override any of these in the environment.
#   GHIDRA_HOME        Ghidra install folder (contains support/analyzeHeadless)
#   DDJ_GHIDRA_PROJECT folder that holds (or will hold) the DDJ1000 Ghidra project
#   DDJ_FW_IMAGES      folder with the split firmware images (tools/updsplit.py output)
FW=$(cd "$(dirname "$0")/.." && pwd)
GHIDRA_HOME=${GHIDRA_HOME:-"$HOME/Applications/ghidra_12.1.4_PUBLIC"}
DDJ_GHIDRA_PROJECT=${DDJ_GHIDRA_PROJECT:-"$FW/ghidra-project"}
DDJ_FW_IMAGES=${DDJ_FW_IMAGES:-"$FW/images"}
SCRIPTS="$FW/ghidra"
if [ -z "$JAVA_HOME" ] && [ -x /usr/libexec/java_home ]; then
  export JAVA_HOME=$(/usr/libexec/java_home)
fi
HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"
mkdir -p "$DDJ_GHIDRA_PROJECT"
