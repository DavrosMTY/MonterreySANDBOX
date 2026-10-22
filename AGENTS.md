# Monterrey Open World: repository workflow

GitHub `DavrosMTY/MonterreySANDBOX` is the primary repository. Preserve all local
work, historical deliveries and source provenance. Use this existing checkout;
do not create worktrees unless explicitly requested.

Work through branches and Pull Requests. Fetch `origin/main` before starting new
work. The initial synchronization uses `development` from the current main; later
tasks use focused branches from the appropriate reviewed base. Commit completed,
validated work, push the task branch and open/update its PR when authorized by the
user's ongoing GitHub workflow. Never commit directly to main, force-push, rewrite
history, reset user changes or merge a PR without explicit authorization.

Read README.md, docs/GEO003_DIAGNOSTICO.md and docs/GITHUB_WORKFLOW.md. Run the
pinned Python environment and meaningful existing tests. Unreal 5.6/Windows is
unavailable in the cloud environment: do not claim engine compilation, import,
collision cooking or gameplay without actual execution evidence.

Keep caches, installed dependencies, credentials, large models, renders and ZIPs
out of Git. Only the explicit license-reviewed pilot inputs may be committed.
Retain Copernicus/ODbL notices. Publish reproducible large deliverables as Releases
after checking limits; do not use paid services or LFS/Actions artifact storage
without verifying the applicable quotas. Preserve original delivery hashes as
references and label regenerated artifacts with their source commit and own hashes.

The geospatial contract is EPSG:32614 / EGM2008, ENU metres internally, Unreal
X=east/Y=south/Z=up in cm. Corrected DSM is procedural, not a measured DTM. WORLD001
uses excavated static terrain, not the original uncut Landscape. Follow per-road
QA exclusions; offline acceptance does not certify a fully drivable world.


The owner has chosen to keep the restriction on Actions creating/approving PRs.
Do not enable that repository setting or retry PR creation through Actions. Use
existing authenticated direct GitHub access for authorized PR operations. If it
is unavailable, report the precise blocker without requesting tokens in chat.
Verify that an actual PR exists before reporting a PR URL; a compare form is not a PR.


FREE-001 supersedes earlier paid-infrastructure proposals: current budget is
strictly USD 0. Do not provision paid cloud, activate card-required trials or
install Unreal without a compatible authorized environment. UE5.6.1 remains the
target; Three.js is a separate geographic validation viewer. Source branches keep
generated models excluded. The dedicated generated gh-pages hosting branch may
contain the small license-reviewed gzip sectors under the 50 MiB deployment cap;
never replace authoritative GIS/UE assets or force-push deployment history.
