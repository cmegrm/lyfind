# Simple Mac startup

**Send Mac users `Reunite_Mac.zip`.** The ordinary class ZIP remains the source/Windows package. The Mac package includes Python 3.12 for Apple Silicon and Intel, and is prepared for macOS 11 or newer.

1. Extract the ZIP in Finder.
2. Double-click **Reunite.app**.
3. The live site opens to **LPU / Guest** sign-in. On your first run, choose **CSA staff → Set up the first CSA administrator**. Later, sign in through **CSA staff** at the bottom. Startup needs no Terminal commands or separate Python installation.

The app copies its code and the correct bundled runtime into `~/Library/Application Support/Reunite` on first use. Later starts reuse the running server, or start it in the background if it is stopped. If port 8765 is occupied, the launcher selects another free local port and opens the right address.

## Controls

Open **Reunite Controls.app** for **Open website**, **Open testing workspace**, **Stop servers**, **Open saved files**, or **Set up local AI**. In the testing workspace, expand **Sample accounts**. Initial AI setup opens a browser progress page and automatically runs the dependency/model preparation. It needs internet and disk space on first use. The normal app can start in clearly labeled typed fallback mode before AI is installed.

Closing a browser tab does not stop the server. Use **Stop servers** when finished.

## Saved records

Use **Open saved files** to reach the `data` folder. Updates preserve that folder, `.env`, model files and the AI environment. Live records and testing records have separate databases and upload folders. A first-time Mac app installation starts with an empty live database. Preserve any database and matching uploads if you have records from an old extracted project.

Startup errors are written to `data/desktop-launch.log`. AI setup progress is stored in `data/ai-setup.log`.

## macOS approval

This academic package is unsigned and not notarized. macOS may require first-open approval. Follow [Apple's normal approval instructions](https://support.apple.com/102445) only for the copy your group trusts. The package does not disable Gatekeeper, remove quarantine flags or change security settings.

## Why the old launcher failed

The Windows-built ZIP stored `START_MAC.command` without Unix executable permissions. The new source ZIP preserves those permissions and LF line endings. The separate Mac package also supplies a Finder app launcher, its own Python runtimes and automatic browser opening.

## Verification and limits

See `TEST_RESULTS.txt` for the latest automated checks, including live and testing launcher isolation and saved data preservation. The Mac package is checked for valid property lists, Unix executable permissions, LF shell scripts, architecture-specific Mach-O Python executables and archive integrity. The bundled runtime licenses are retained.

Finder launch, Gatekeeper behavior and the Mac-specific AI installation have not been executed on a physical Mac in this Windows environment. These require the first launch on a groupmate's Mac; do not describe the package as Mac-tested yet.

Python runtime source: [Astral Python Standalone Builds](https://docs.astral.sh/python-build-standalone/), release 20261026. Both original download URLs and checksums are included in the Mac app resources.
