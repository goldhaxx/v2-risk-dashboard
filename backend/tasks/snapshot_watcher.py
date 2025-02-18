import asyncio
import glob
import logging

from backend.state import BackendState

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SnapshotWatcher:
    def __init__(self, state: BackendState, check_interval: int = 60):
        self.state = state
        self.interval = check_interval
        self.task: asyncio.Task | None = None
        self.is_running = False
        self.last_loaded_snapshot = None

    async def start(self):
        if self.is_running:
            return

        self.is_running = True
        self.task = asyncio.create_task(self._run())
        logger.info("Snapshot watcher started")

    async def stop(self):
        if not self.is_running:
            return

        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        while self.is_running:
            try:
                newest_pickle = self._get_newest_pickle()
                if newest_pickle and newest_pickle != self.last_loaded_snapshot:
                    logger.info(f"Found newer pickle snapshot: {newest_pickle}")
                    await self.state.load_pickle_snapshot(newest_pickle)
                    self.last_loaded_snapshot = newest_pickle
                    logger.info("Successfully switched to new snapshot")

                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error checking/loading snapshot: {e}")
                await asyncio.sleep(10)

    def _get_newest_pickle(self) -> str | None:
        try:
            pickle_paths = sorted(glob.glob("pickles/*"))
            return pickle_paths[-1] if pickle_paths else None
        except Exception as e:
            logger.error(f"Error getting newest pickle: {e}")
            return None
