import Agently
import utils.yaml_reader as yaml
from utils.logger import Logger
from workflows import main_workflow
from utils.path import root_path
import sys

# Settings and Logger
settings = "./SETTINGS.yaml"
if len(sys.argv) == 2:
    settings = sys.argv[1]
SETTINGS = yaml.read(settings)
logger = Logger(console_level = "DEBUG" if SETTINGS.IS_DEBUG else "INFO")

# Agent Factory
agent_factory = (
    Agently.AgentFactory(is_debug=SETTINGS.IS_DEBUG)
        .set_settings("current_model", SETTINGS.MODEL_PROVIDER)
        .set_settings(f"model.{ SETTINGS.MODEL_PROVIDER }.auth", SETTINGS.MODEL_AUTH)
        .set_settings(f"model.{ SETTINGS.MODEL_PROVIDER }.url", SETTINGS.MODEL_URL if hasattr(SETTINGS, "MODEL_URL") else None)
        .set_settings(f"model.{ SETTINGS.MODEL_PROVIDER }.options", SETTINGS.MODEL_OPTIONS if hasattr(SETTINGS, "MODEL_OPTIONS") else {})
)

# Start Workflow
main_workflow.start(
    agent_factory=agent_factory,
    SETTINGS=SETTINGS,
    root_path=root_path,
    logger=logger,
)