# Scheduler

The scheduler tool lets the agent create, manage, and run scheduled tasks. It supports:

- **Reminders**: send a message at a set time
- **Recurring tasks**: repeat on a fixed interval or a cron expression
- **Dynamic tool calls**: run another tool on a schedule and send the result (for example, read a schedule file)
- **Task management**: list, enable, disable, and delete tasks

```bash
pip install croniter>=2.0.0
```

The agent can create scheduled tasks from natural language. There are two kinds.

## Fixed message

Send a predefined message.

**Example:**

```
User: Remind me about the meeting every day at 9:00
Agent: [calls the scheduler tool]
      action: create
      name: Daily meeting reminder
      message: Time for the meeting!
      schedule_type: cron
      schedule_value: 0 9 * * *
```

## Dynamic tool call

Run a tool on a schedule and send the result.

**Example:**

```
User: Every day at 8:00, read today's schedule for me
Agent: [calls the scheduler tool]
      action: create
      name: Daily schedule
      tool_call:
        tool_name: read
        tool_params:
          file_path: ~/maia/schedule.txt
        result_prefix: 📅 Today's schedule
      schedule_type: cron
      schedule_value: 0 8 * * *
```

**Tool-call parameters:**

- `tool_name`: the tool to call (built-in tools such as `bash`, `read`, or `write`)
- `tool_params`: the tool's arguments (a dictionary)
- `result_prefix`: optional text placed before the result

**Note:** To use a skill (such as bocha-search), call the skill script through the `bash` tool.

## Cron expressions

```
0 9 * * *      # every day at 9:00
0 */2 * * *    # every 2 hours
30 8 * * 1-5   # weekdays at 8:30
0 0 1 * *      # the 1st of each month
```

## Interval in seconds

```
3600           # every hour
86400          # every day
1800           # every 30 minutes
```

## A specific time (ISO format)

```
2024-12-25T09:00:00
2024-12-31T23:59:59
```

## Managing tasks

```
User: Show my scheduled tasks
Agent: [calls the scheduler tool]
      action: list
```

```
User: Show details for task abc123
Agent: [calls the scheduler tool]
      action: get
      task_id: abc123
```

```
User: Delete task abc123
Agent: [calls the scheduler tool]
      action: delete
      task_id: abc123
```

```
User: Pause task abc123
Agent: [calls the scheduler tool]
      action: disable
      task_id: abc123

User: Resume task abc123
Agent: [calls the scheduler tool]
      action: enable
      task_id: abc123
```

## Storage

Tasks are stored in a JSON file:

```
~/maia/scheduler/tasks.json
```

**Fixed-message task:**

```json
{
  "id": "abc123",
  "name": "Daily reminder",
  "enabled": true,
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "schedule": {
    "type": "cron",
    "expression": "0 9 * * *"
  },
  "action": {
    "type": "send_message",
    "content": "Time for the meeting!",
    "receiver": "user-1",
    "receiver_name": "Alex",
    "is_group": false,
    "channel_type": "web"
  },
  "next_run_at": "2024-01-02T09:00:00",
  "last_run_at": "2024-01-01T09:00:00"
}
```

**Dynamic tool-call task:**

```json
{
  "id": "def456",
  "name": "Daily schedule",
  "enabled": true,
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "schedule": {
    "type": "cron",
    "expression": "0 8 * * *"
  },
  "action": {
    "type": "tool_call",
    "tool_name": "read",
    "tool_params": {
      "file_path": "~/maia/schedule.txt"
    },
    "result_prefix": "📅 Today's schedule",
    "receiver": "user-1",
    "receiver_name": "Alex",
    "is_group": false,
    "channel_type": "web"
  },
  "next_run_at": "2024-01-02T08:00:00"
}
```

## Background service

`SchedulerService` runs the tasks:

- Checks for due tasks every 30 seconds
- Runs due tasks automatically
- Computes the next run time
- Records run history and errors

The service starts when the agent initializes. No manual setup is required.

## Who receives the message

A scheduled task is delivered to the conversation where it was created:

- Created in a direct chat: sent to that user
- Created in a group chat: sent to that group
- The recipient is saved automatically at creation time

## More examples

```
User: Remind me to take my medicine every day at 8:00
Agent: Scheduled task created
       Task ID: a1b2c3d4
       Schedule: every day at 8:00
       Message: Time to take your medicine!
```

```
User: On weekdays at 6:00pm, remind me to finish work
Agent: [creates cron: 0 18 * * 1-5]
       Message: Time to wrap up for the day!
```

```
User: Remind me in 1 hour
Agent: [creates interval: 3600]
```

```
User: Every day at 8:00, read today's schedule for me
Agent: Scheduled task created
       Task ID: schedule001
       Schedule: every day at 8:00
       Tool: read(file_path='~/maia/schedule.txt')
       Prefix: 📅 Today's schedule
```

```
User: Back up my work files every night at 11:00
Agent: [creates cron: 0 23 * * *]
       Tool: bash(command='cp ~/maia/work.txt ~/maia/backup/work_$(date +%Y%m%d).txt')
       Prefix: ✅ Files backed up
```

```
User: Every Friday at 5:00pm, remind me to write the weekly report
Agent: [creates cron: 0 17 * * 5]
       Message: 📊 Time to write the weekly report!
```

```
User: On December 25 at 9:00am, wish me a merry Christmas
Agent: [creates once: 2024-12-25T09:00:00]
```

## Notes

1. **Timezone**: the system local timezone
2. **Precision**: the check interval is 30 seconds, so a run may be off by about ±30 seconds
3. **Persistence**: tasks are stored in a file and restored after a restart
4. **One-shot tasks**: disabled after they run, not deleted (you can delete them manually)
5. **Errors**: a failed run is recorded and does not affect other tasks

## Components

- **TaskStore**: persists tasks
- **SchedulerService**: background scheduler
- **SchedulerTool**: the agent tool
- **Integration**: connects the scheduler to AgentBridge

## Dependency

- `croniter`: parses cron expressions (about 50KB)
