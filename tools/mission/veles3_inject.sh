#!/bin/sh
# Re-push Veles 3's trans-Uranus injection after a re-fly.
# The GUID changes whenever the vessel is re-released, so it is READ, never pinned.
cd "$(dirname "$0")" || exit 1
VID=$(python -c "import sys;sys.path.insert(0,'.');from bridge import Bridge;print(Bridge().get('/nodes')['id'])") || exit 1
echo "active vessel id: $VID"
exec python plan.py depart --live --vessel-id "$VID" \
    --target Uranus --arrive 1988-06-18 \
    --peri 100000km --bplane prograde --horizon 200 --push
