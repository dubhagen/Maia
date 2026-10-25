"""
Scheduler tool for creating and managing scheduled tasks
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from croniter import croniter
from agent.tools.scheduler.time_utils import (
    display_local,
    format_scheduled_time,
    next_cron_occurrence,
    parse_scheduled_time,
    resolve_timezone,
    scheduled_reference_time,
    task_timezone,
    utc_now,
)

from agent.tools.base_tool import BaseTool, ToolResult
from bridge.context import Context
from common.log import logger


class _SchedulerError(str):
    """A refused operation, retaining the helpers' existing text interface."""


class SchedulerTool(BaseTool):
    """
    Tool for managing scheduled tasks (reminders, notifications, etc.)
    """
    
    name: str = "scheduler"
    description: str = (
        "Create, look up, and manage scheduled tasks (reminders, recurring jobs, and similar).\n\n"
        "⚠️ Important: use this tool only when something should run later or on a schedule (a reminder, every day, every week, in X minutes, or at a certain time). "
        "How to use it:\n"
        "- Create: action='create', name='task name', message/ai_task='content', schedule_type='once/interval/cron', schedule_value='...'\n"
        "- Look up: action='list' / action='get', task_id='task id'\n"
        "- Manage: action='delete/enable/disable', task_id='task id'\n\n"
        "Schedule types:\n"
        "- once: runs one time. A relative time (+5s, +10m, +1h, +1d) or an ISO time\n"
        "- interval: a fixed gap in seconds. 3600 means every hour\n"
        "- cron: a cron expression. '0 8 * * *' means every day at 08:00\n\n"
        "Note: 'in X seconds' is once plus a relative time. 'every X seconds' is interval.\n"
        "For Web cross-channel delivery, call action='list_recipients' first, "
        "then create a task (fixed message or ai_task) using the returned channel_type and receiver."
    )
    params: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "list_recipients", "get", "delete", "enable", "disable"],
                "description": "What to do: create, list, get, delete, enable, disable"
            },
            "task_id": {
                "type": "string",
                "description": "Task id (for get, delete, enable, and disable)"
            },
            "name": {
                "type": "string",
                "description": "Task name (for create)"
            },
            "message": {
                "type": "string",
                "description": "Fixed message text (use this or ai_task, not both)"
            },
            "ai_task": {
                "type": "string",
                "description": (
                    "What the agent should do when the task fires (use this or message, not both): which action to take and what to deliver. "
                    "Do not repeat the schedule time. The schedule decides that."
                )
            },
            "schedule_type": {
                "type": "string",
                "enum": ["cron", "interval", "once"],
                "description": "Schedule type for create: cron (a cron expression), interval (seconds between runs), once (one time)"
            },
            "schedule_value": {
                "type": "string",
                "description": "Schedule value: a cron expression, a gap in seconds, or a time (+5s, +10m, +1h, or ISO)"
            },
            "silent": {
                "type": "boolean",
                "default": False,
                "description": "Silent mode (default false): when true, the task runs normally but its result is not pushed. Set true only when the user explicitly says they don't need the result; reminder, notification and broadcast tasks must keep it false"
            },
            "channel_type": {
                "type": "string",
                "description": "Target channel type for a Web-created cross-channel task. Use list_recipients first."
            },
            "instance_id": {
                "type": "string",
                "description": "The specific channel instance the recipient belongs to, as returned by list_recipients. Required when a channel type runs more than one instance; the same receiver on two instances is two different targets. Omit for a single-instance channel."
            },
            "timezone": {
                "type": "string",
                "description": "Optional IANA timezone (e.g. Asia/Shanghai) used for cron wall-clock times and naive ISO timestamps"
            },
            "receiver": {
                "type": "string",
                "description": "Trusted target receiver returned by list_recipients. It cannot be an arbitrary user ID."
            },
        },
        "required": ["action"]
    }
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        
        # Will be set by agent bridge
        self.task_store = None
        self.recipient_store = None
        self.current_context = None
    
    def execute(self, params: dict) -> ToolResult:
        """
        Execute scheduler operations
        
        Args:
            params: Dictionary containing:
                - action: Operation type (create/list/get/delete/enable/disable)
                - Other parameters depending on action
            
        Returns:
            ToolResult object
        """
        # Extract parameters
        action = params.get("action")
        kwargs = params
        
        if not self.task_store:
            return ToolResult.fail("Error: the scheduler is not initialized")
        
        try:
            if action == "create":
                result = self._create_task(**kwargs)
            elif action == "list":
                result = self._list_tasks(**kwargs)
            elif action == "list_recipients":
                result = self._list_recipients(**kwargs)
            elif action == "get":
                result = self._get_task(**kwargs)
            elif action == "delete":
                result = self._delete_task(**kwargs)
            elif action == "enable":
                result = self._enable_task(**kwargs)
            elif action == "disable":
                result = self._disable_task(**kwargs)
            else:
                return ToolResult.fail(f"Unknown operation: {action}")
            if isinstance(result, _SchedulerError):
                return ToolResult.fail(str(result))
            return ToolResult.success(result)
        except Exception as e:
            logger.error(f"[SchedulerTool] Error: {e}")
            return ToolResult.fail(f"Operation failed: {str(e)}")
    
    def _create_task(self, **kwargs) -> str:
        """Create a new scheduled task"""
        name = kwargs.get("name")
        message = kwargs.get("message")
        ai_task = kwargs.get("ai_task")
        schedule_type = kwargs.get("schedule_type")
        schedule_value = kwargs.get("schedule_value")
        timezone_name = kwargs.get("timezone")
        
        # Validate required fields
        if not name:
            return _SchedulerError("Error: missing task name (name)")
        
        # Check that exactly one of message/ai_task is provided
        if not message and not ai_task:
            return _SchedulerError("Error: provide message (a fixed message) or ai_task (an AI task)")
        if message and ai_task:
            return _SchedulerError("Error: provide only one of message and ai_task")
        
        if not schedule_type:
            return _SchedulerError("Error: missing schedule type (schedule_type)")
        if not schedule_value:
            return _SchedulerError("Error: missing schedule value (schedule_value)")
        
        # Validate schedule
        schedule = self._parse_schedule(schedule_type, schedule_value, timezone_name)
        if not schedule:
            return _SchedulerError(f"Error: invalid schedule - type: {schedule_type}, value: {schedule_value}")
        
        # Get context info for receiver
        if not self.current_context:
            return _SchedulerError("Error: could not get the current conversation")
        
        context = self.current_context

        target_channel = kwargs.get("channel_type")
        target_receiver = kwargs.get("receiver")
        # A channel type can run several instances; delivery must go back through
        # the exact one that saw the contact. When the caller does not name an
        # instance (legacy single-instance channel), it equals the channel type.
        target_instance = kwargs.get("instance_id") or target_channel
        target = None
        if target_channel or target_receiver:
            if context.get("channel_type") != "web":
                return _SchedulerError("Error: cross-channel recipients can only be selected from the Web console")
            if not target_channel or not target_receiver:
                return _SchedulerError("Error: channel_type and receiver must be provided together")
            if not self.recipient_store:
                return _SchedulerError("Error: trusted recipient directory is unavailable")
            target = self.recipient_store.get(target_instance, target_receiver)
            if not target:
                return _SchedulerError("Error: target is not in the trusted recipient directory; use list_recipients")
        
        # Create task
        task_id = str(uuid.uuid4())[:8]
        
        # Capture the real chat session_id at task creation time so that scheduler
        # can later inject the delivered output into the user's actual conversation
        # (in group chats, session_id is not the same as receiver).
        notify_session_id = target["session_id"] if target else context.get("session_id")
        receiver = target["receiver"] if target else context.get("receiver")
        receiver_name = target["name"] if target else self._get_receiver_name(context)
        is_group = target["is_group"] if target else context.get("isgroup", False)
        channel_type = target["channel_type"] if target else self.config.get("channel_type", "unknown")
        # The instance to deliver back through: the target's own for a
        # cross-channel task, else this conversation's. Defaults to the channel
        # type so a legacy single-instance channel keeps resolving as before.
        instance_id = (
            target.get("instance_id") if target else context.get("instance_id")
        ) or channel_type

        # Build action based on message or ai_task
        if message:
            action = {
                "type": "send_message",
                "content": message,
                "receiver": receiver,
                "receiver_name": receiver_name,
                "is_group": is_group,
                "channel_type": channel_type,
                "instance_id": instance_id,
                "notify_session_id": notify_session_id,
            }
        else:  # ai_task
            action = {
                "type": "agent_task",
                "task_description": ai_task,
                "receiver": receiver,
                "receiver_name": receiver_name,
                "is_group": is_group,
                "channel_type": channel_type,
                "instance_id": instance_id,
                "notify_session_id": notify_session_id,
            }
            # silent only applies to ai_task; fixed messages always deliver
            if kwargs.get("silent", False):
                action["silent"] = True
        
        
        
        # The Agent this task runs as. Stored on the task (not implied by which
        # file it lives in) so the global scheduler can scope execution to it and
        # so re-binding a channel instance to a different Agent never moves data.
        owner_agent_id = self._resolve_owner_agent_id(context, target)

        task_data = {
            "id": task_id,
            "name": name,
            "agent_id": owner_agent_id,
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "schedule": schedule,
            "action": action
        }
        
        # Calculate initial next_run_at
        next_run = self._calculate_next_run(task_data)
        if next_run:
            # A one-time task whose run time has already passed would be
            # stored all the same, then deleted on the service's first
            # tick once the catch-up window has passed
            # (SchedulerService._is_task_due): the reminder never fires
            # and only a server-side log says why. Refuse it here, where
            # the caller can still pick another time - the service's own
            # _calculate_next_run answers a past run_at with no next run.
            # Compared in the task's own mode (aware UTC for a declared
            # zone, naive local otherwise) so a zoned task cannot raise
            # a naive/aware TypeError.
            if schedule.get("type") == "once" and next_run <= scheduled_reference_time(
                task_data, datetime.now()
            ):
                return _SchedulerError(
                    f"Error: that time is already past ({schedule.get('run_at')}). "
                    "A one-time task has to be in the future. Pick a future time "
                    "or a relative time such as +10m."
                )
            task_data["next_run_at"] = next_run.isoformat()
        
        # Save task
        self.task_store.add_task(task_data)
        
        # Format response
        schedule_desc = self._format_schedule_description(schedule)
        receiver_desc = task_data["action"]["receiver_name"] or task_data["action"]["receiver"]
        
        if message:
            content_desc = f"💬 Fixed message: {message}"
        else:
            content_desc = f"🤖 AI task: {ai_task}"

        # Warn the user at creation time so a mistaken silent flag is easy to spot
        silent_desc = "\n🔇 Silent mode: the result is not sent after the task runs" if action.get("silent") else ""

        return (
            f"✅ Scheduled task created\n\n"
            f"📋 Task ID: {task_id}\n"
            f"📝 Name: {name}\n"
            f"⏰ Schedule: {schedule_desc}\n"
            f"👤 Recipient: {receiver_desc}\n"
            f"{content_desc}{silent_desc}\n"
            f"🕐 Next run: {next_run.astimezone().strftime('%Y-%m-%d %H:%M:%S') if next_run else 'unknown'}"
        )
    
    def _list_tasks(self, **kwargs) -> str:
        """List all tasks"""
        tasks = self.task_store.list_tasks()
        
        if not tasks:
            return "📋 No scheduled tasks"
        
        lines = [f"📋 Scheduled tasks ({len(tasks)} total)\n"]
        
        for task in tasks:
            status = "✅" if task.get("enabled", True) else "❌"
            schedule_desc = self._format_schedule_description(task.get("schedule", {}))
            next_run = task.get("next_run_at")
            next_run_str = display_local(next_run, task_timezone(task)).strftime('%m-%d %H:%M') if next_run else "unknown"
            
            lines.append(
                f"{status} [{task['id']}] {task['name']}\n"
                f"   ⏰ {schedule_desc} | Next: {next_run_str}"
            )
        
        return "\n".join(lines)

    def _list_recipients(self, **kwargs) -> str:
        """List trusted targets available to the Web scheduler."""
        if not self.current_context or self.current_context.get("channel_type") != "web":
            return _SchedulerError("Error: trusted recipients can only be listed from the Web console")
        if not self.recipient_store:
            return _SchedulerError("Error: trusted recipient directory is unavailable")
        recipients = self.recipient_store.list()
        if not recipients:
            return "No trusted recipients yet. A recipient must contact Maia first."
        lines = ["Trusted scheduler recipients:"]
        for item in recipients:
            kind = "group" if item["is_group"] else "user"
            instance_id = item.get("instance_id") or item["channel_type"]
            lines.append(
                f"- {item['name']} ({kind}): channel_type={item['channel_type']}, "
                f"instance_id={instance_id}, receiver={item['receiver']}"
            )
        return "\n".join(lines)
    
    def _get_task(self, **kwargs) -> str:
        """Get task details"""
        task_id = kwargs.get("task_id")
        if not task_id:
            return _SchedulerError("Error: missing task id (task_id)")
        
        task = self.task_store.get_task(task_id)
        if not task:
            return _SchedulerError(f"Error: task '{task_id}' does not exist")
        
        status = "enabled" if task.get("enabled", True) else "disabled"
        schedule_desc = self._format_schedule_description(task.get("schedule", {}))
        action = task.get("action", {})
        next_run = task.get("next_run_at")
        zone = task_timezone(task)
        next_run_str = display_local(next_run, zone).strftime('%Y-%m-%d %H:%M:%S') if next_run else "unknown"
        last_run = task.get("last_run_at")
        last_run_str = display_local(last_run, zone).strftime('%Y-%m-%d %H:%M:%S') if last_run else "never"
        
        return (
            f"📋 Task details\n\n"
            f"ID: {task['id']}\n"
            f"Name: {task['name']}\n"
            f"Status: {status}\n"
            f"Schedule: {schedule_desc}\n"
            f"Recipient: {action.get('receiver_name', action.get('receiver'))}\n"
            f"Message: {action.get('content')}\n"
            f"Next run: {next_run_str}\n"
            f"Last run: {last_run_str}\n"
            f"Created: {display_local(task['created_at']).strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def _delete_task(self, **kwargs) -> str:
        """Delete a task"""
        task_id = kwargs.get("task_id")
        if not task_id:
            return _SchedulerError("Error: missing task id (task_id)")
        
        task = self.task_store.get_task(task_id)
        if not task:
            return _SchedulerError(f"Error: task '{task_id}' does not exist")
        
        self.task_store.delete_task(task_id)
        return f"✅ Task '{task['name']}' ({task_id}) deleted"
    
    def _enable_task(self, **kwargs) -> str:
        """Enable a task"""
        task_id = kwargs.get("task_id")
        if not task_id:
            return _SchedulerError("Error: missing task id (task_id)")
        
        task = self.task_store.get_task(task_id)
        if not task:
            return _SchedulerError(f"Error: task '{task_id}' does not exist")
        
        self.task_store.enable_task(task_id, True)
        return f"✅ Task '{task['name']}' ({task_id}) enabled"
    
    def _disable_task(self, **kwargs) -> str:
        """Disable a task"""
        task_id = kwargs.get("task_id")
        if not task_id:
            return _SchedulerError("Error: missing task id (task_id)")
        
        task = self.task_store.get_task(task_id)
        if not task:
            return _SchedulerError(f"Error: task '{task_id}' does not exist")
        
        self.task_store.enable_task(task_id, False)
        return f"✅ Task '{task['name']}' ({task_id}) disabled"
    
    def _parse_schedule(
        self, schedule_type: str, schedule_value: str, timezone_name: str = None
    ) -> Optional[dict]:
        """Parse and validate schedule configuration."""
        try:
            zone = resolve_timezone(timezone_name) if timezone_name else None

            if schedule_type == "cron":
                # Validate the cron expression and preserve the declared IANA
                # zone. Without a declared zone, keep the legacy naive mode.
                croniter(schedule_value)
                schedule = {"type": "cron", "expression": schedule_value}
                if timezone_name:
                    schedule["timezone"] = timezone_name.strip()
                return schedule

            if schedule_type == "interval":
                seconds = int(schedule_value)
                if seconds <= 0:
                    return None
                return {"type": "interval", "seconds": seconds}

            if schedule_type == "once":
                # Support relative times such as "+5s", "+10m", "+1h", "+1d".
                if schedule_value.startswith("+"):
                    import re
                    match = re.match(r'\+(\d+)([smhd])', schedule_value)
                    if not match:
                        logger.error(
                            f"[SchedulerTool] Invalid relative time format: {schedule_value}"
                        )
                        return None

                    amount = int(match.group(1))
                    unit = match.group(2)
                    now = utc_now() if zone is not None else datetime.now()
                    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
                    if unit not in seconds_per_unit:
                        return None
                    target_time = now + timedelta(
                        seconds=seconds_per_unit[unit] * amount
                    )

                    schedule = {
                        "type": "once",
                        "run_at": format_scheduled_time(target_time),
                    }
                    if timezone_name:
                        schedule["timezone"] = timezone_name.strip()
                    return schedule

                parsed = parse_scheduled_time(schedule_value, zone)
                if zone is not None:
                    run_at = format_scheduled_time(parsed)
                else:
                    # Preserve the scheduler's legacy local wall clock when no
                    # IANA zone was declared. An input with an offset is still
                    # normalized to a concrete local wall time.
                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone().replace(tzinfo=None)
                    run_at = parsed.isoformat()

                schedule = {"type": "once", "run_at": run_at}
                if timezone_name:
                    schedule["timezone"] = timezone_name.strip()
                return schedule

            return None
        except Exception as e:
            logger.error(f"[SchedulerTool] Invalid schedule: {e}")
            return None

    def _calculate_next_run(self, task: dict) -> Optional[datetime]:
        """Calculate next run time for a task."""
        schedule = task.get("schedule", {})
        schedule_type = schedule.get("type")
        now = scheduled_reference_time(task, datetime.now())

        if schedule_type == "cron":
            expression = schedule.get("expression")
            return next_cron_occurrence(expression, now, task_timezone(task))

        if schedule_type == "interval":
            seconds = schedule.get("seconds", 0)
            return now + timedelta(seconds=seconds)

        if schedule_type == "once":
            run_at_str = schedule.get("run_at")
            return parse_scheduled_time(run_at_str, task_timezone(task))

        return None

    def _format_schedule_description(self, schedule: dict) -> str:
        """Format schedule as human-readable description"""
        schedule_type = schedule.get("type")
        
        if schedule_type == "cron":
            expr = schedule.get("expression", "")
            zone_name = schedule.get("timezone")
            # Try to provide friendly description
            if expr == "0 9 * * *":
                return "Every day at 9:00"
            elif expr == "0 */1 * * *":
                return "Every hour"
            elif expr == "*/30 * * * *":
                return "Every 30 minutes"
            else:
                return f"Cron: {expr} ({zone_name})" if zone_name else f"Cron: {expr}"
        
        elif schedule_type == "interval":
            seconds = schedule.get("seconds", 0)
            if seconds >= 86400:
                days = seconds // 86400
                return f"Every {days} day(s)"
            elif seconds >= 3600:
                hours = seconds // 3600
                return f"Every {hours} hour(s)"
            elif seconds >= 60:
                minutes = seconds // 60
                return f"Every {minutes} minute(s)"
            else:
                return f"Every {seconds} second(s)"
        
        elif schedule_type == "once":
            run_at = schedule.get("run_at", "")
            try:
                zone = resolve_timezone(schedule["timezone"]) if schedule.get("timezone") else None
                dt = display_local(run_at, zone)
                return f"Once ({dt.strftime('%Y-%m-%d %H:%M')})"
            except Exception:
                return "Once"
        
        return "Unknown"
    
    def _get_receiver_name(self, context: Context) -> str:
        """Get receiver name from context"""
        try:
            msg = context.get("msg")
            if msg:
                if context.get("isgroup"):
                    return msg.other_user_nickname or "group"
                else:
                    return msg.from_user_nickname or "user"
        except Exception:
            pass
        return "Unknown"

    def _resolve_owner_agent_id(self, context: Context, target: Optional[dict]) -> str:
        """Which Agent the new task runs as.

        For a cross-channel task the owner is the Agent the target's channel
        instance is bound to (delivery and identity should match how an inbound
        message from that instance would route). For a normal conversation task
        it is simply the Agent handling this conversation. Falls back to the
        ambient runtime identity, then the default Agent.
        """
        # Cross-channel: derive from the target instance's binding.
        if target:
            iid = (target.get("instance_id") or "").strip()
            if iid:
                try:
                    from channel.channel_instances import get_instance
                    from config import conf as _conf

                    inst = get_instance(_conf(), iid)
                    if inst and getattr(inst, "agent_id", ""):
                        return inst.agent_id
                except Exception:
                    pass
        # Conversation task: the Agent on the context, else ambient identity.
        agent_id = (context.get("agent_id") if context else "") or ""
        if not agent_id:
            try:
                from common.runtime_identity import current_identity

                agent_id = current_identity().agent_id or ""
            except Exception:
                agent_id = ""
        if agent_id:
            return agent_id
        try:
            from agent.registry import get_agent_registry

            return get_agent_registry().default_agent_id
        except Exception:
            return ""
