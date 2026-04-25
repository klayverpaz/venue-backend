from app.ai.tools.get_current_time import get_current_time
from app.ai.tools.get_user_by_email import get_user_by_email

TOOLS = [get_current_time, get_user_by_email]
TOOL_REGISTRY = {t.name: t for t in TOOLS}
