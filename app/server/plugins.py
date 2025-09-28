from litestar.plugins.htmx import HTMXPlugin
from litestar.plugins.problem_details import ProblemDetailsPlugin
from litestar.plugins.structlog import StructlogPlugin
from litestar_granian import GranianPlugin
from litestar_mcp import LitestarMCP
from sqlspec.extensions.litestar import DatabaseConfig, SQLSpec

from app import config

structlog = StructlogPlugin(config=config.log)
sqlspec = SQLSpec(config=DatabaseConfig(commit_mode="autocommit", config=config.db))
granian = GranianPlugin()
problem_details = ProblemDetailsPlugin(config=config.problem_details)
htmx = HTMXPlugin()
mcp = LitestarMCP(config=config.mcp)
