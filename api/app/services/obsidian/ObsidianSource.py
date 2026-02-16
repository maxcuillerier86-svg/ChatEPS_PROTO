from __future__ import annotations

from app.services.obsidian.adapters.FileSystemAdapter import FileSystemAdapter
from app.services.obsidian.adapters.LocalRestApiAdapter import LocalRestApiAdapter
from app.services.obsidian.types import ObsidianConfig, ObsidianNote


class ObsidianSource:
    def __init__(self, cfg: ObsidianConfig):
        self.cfg = cfg

    async def read_notes(self) -> list[ObsidianNote]:
        if self.cfg.mode == "rest":
            return await LocalRestApiAdapter(self.cfg).read_notes()
        return FileSystemAdapter(self.cfg).read_notes()
