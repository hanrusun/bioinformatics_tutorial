"""``python -m curelab`` / ``curelab``: serve the game."""

from __future__ import annotations

import argparse
import os


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="curelab", description="Serve the Cure Lab game.")
    parser.add_argument("--host", default=os.environ.get("CURELAB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CURELAB_PORT", "8000")))
    parser.add_argument("--pack", help="pack directory (default: $CURELAB_PACK_DIR or packs/seurat)")
    parser.add_argument("--illnesses", help="illness directory (default: $CURELAB_ILLNESS_DIR or illnesses/)")
    parser.add_argument("--data", help="save directory (default: $CURELAB_DATA_DIR or ~/.curelab)")
    parser.add_argument("--web", help="built web UI directory (default: web/dist)")
    parser.add_argument("--unlock-all", action="store_true", help="unlock every campaign")
    args = parser.parse_args(argv)

    for flag, env in (
        (args.pack, "CURELAB_PACK_DIR"),
        (args.illnesses, "CURELAB_ILLNESS_DIR"),
        (args.data, "CURELAB_DATA_DIR"),
        (args.web, "CURELAB_WEB_DIR"),
    ):
        if flag:
            os.environ[env] = flag
    if args.unlock_all:
        os.environ["CURELAB_UNLOCK_ALL"] = "1"

    import uvicorn

    uvicorn.run("curelab.app:app_factory", factory=True, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
