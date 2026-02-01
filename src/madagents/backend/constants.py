#########################################################################
## Backend constants ####################################################
#########################################################################

BASE_WORKER_AGENTS = {
    "script_operator",
    "researcher",
    "pdf_reader",
    "madgraph_operator",
    "plotter",
    "user_cli_operator",
}

REVIEWER_AGENT = "reviewer"

KNOWN_AGENT_NAMES = BASE_WORKER_AGENTS | {
    "planner",
    "plan_updater",
    REVIEWER_AGENT,
    "orchestrator",
}

INTERRUPT_USER_MESSAGE = "I interrupt the workflow."

APP_CONFIG_KEY = "global"
