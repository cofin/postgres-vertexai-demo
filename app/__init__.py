import multiprocessing
import platform

from app import agents, cli, config, db, lib, schemas, server, services, utils

__all__ = (
    "agents",
    "cli",
    "config",
    "db",
    "lib",
    "schemas",
    "server",
    "services",
    "utils",
)

if platform.system() == "Darwin":
    multiprocessing.set_start_method("fork", force=True)
