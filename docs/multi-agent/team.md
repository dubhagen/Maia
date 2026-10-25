# Agent Teams

Maia is no longer a single Agent. You can create multiple Agents to form a team: each member has its own responsibilities, model, skills, and knowledge, working independently or being brought into the same session to collaborate.

## Why a Team

A team of specialized Agents is better suited to complex tasks that span different business domains, for the following reasons:

- **Focused context**: an Agent with too many responsibilities pulls in a lot of irrelevant context, which hurts quality and drives up token cost. Split by domain, each Agent keeps its context focused, answers more accurately, and costs less.
- **Complementary capabilities**: each Agent can be bound to a different model and skill set, and through division of labor, collaboration, or even cross-review, the team can handle tasks a single Agent would struggle with.
- **Data and permission isolation**: each Agent has its own workspace, and its memory, sessions, and output files are not visible to others, which fits boundaries drawn by role or by customer.
- **Better presentation**: the web console and the local terminal can each talk to a different Agent, or a whole team can share one conversation.

For users who only use a single Agent, the experience stays the same; team-related features appear only after you create a second Agent.

## Creating an Agent

Click Create on the "Agent Team" page in the Web console or desktop client to add an Agent. An Agent is made up of the following parts:

- **Name and avatar**: the identity within the team, shown in chat bubbles, the member list, and channel bindings.
- **Responsibilities**: one sentence describing what the Agent handles. It helps you tell members apart and is used to decide who a task should go to during collaboration.
- **Default model**: you can assign a model to this Agent individually. The default Agent follows the global configuration.
- **Skills and knowledge**: these can be shared with the team, or an Agent can have its own dedicated knowledge base that stays isolated from the others.
- **Copy from an existing Agent**: when creating a new Agent, you can copy an existing Agent's configuration, skills, and knowledge as a starting point.

Management → Agents shows the team on the left and the selected member on the right. The default member is Maia. Profile holds the name, responsibilities, avatar, and default model. Skills and Core files are the other two tabs. Core files include `AGENT.md` and `RULE.md`.

![Agents page, default Maia profile](../images/screenshots/agents.png)

*Agent Team with the default Maia profile: name, responsibilities, and default model*

Once created, the Agent appears in the team list. Click a member to edit that profile.

> **Note.** There is always a default Agent in the team. It is the fallback for new sessions and elsewhere, follows the global model configuration, and cannot be deleted.

### Knowledge Base: Shared or Independent

Every non-default Agent can choose a knowledge base mode:

- **Shared**: reads and writes the same knowledge base as the team, which fits scenarios where everyone works with the same materials.
- **Independent**: has a dedicated knowledge base isolated from other members, which fits cases where materials differ significantly across domains.

You can switch between the two modes at any time; when switching back to shared, the content of the independent base is preserved.

## Joining Sessions and Group Chats

When creating a session, you can have a single Agent talk with you, or start a group chat with multiple Agents.

In an existing session, the Agent selector at the bottom left of the input box lets you:

- **Switch Agent**: an empty session can switch its Agent directly; a session that already has content starts a new conversation with the new Agent, while the existing history stays with the original Agent.
- **Add member**: add another Agent to the current session, turning it into a group chat.
- **Remove member**: remove a member from the current session.

In a group chat, each Agent answers with its own configured model, and the bubble shows which Agent is speaking. Members in the same session read the same record and can see what others have said. The new-chat welcome screen is a single empty chat. It does not show a group.

> **Note.** Group chats do not use the session-level model selection; each Agent uses its own configured default model, so no model selector appears in a group chat.

## Channel Integration

Chat uses the web console. The local terminal is the other surface. Management → Channels shows those two. Team members are added on the Agents page and in a group chat.

Use `@` and a member's name inside a group chat to direct a turn. The lead Agent can still hand work to another member of that session.

## Collaboration

Multiple Agents in the same session collaborate in two ways.

### 1. Directing with @

In a group chat, use `@` followed by a member's name to hand the current turn to a specific Agent. Typing `@` brings up the members in the current session to choose from, and once sent, the bubble carries the avatar of the directed Agent to mark who is responsible for that turn.

### 2. Lead Agent and Delegation

A group chat always has a lead Agent (the owner). Unless the user `@`s someone else, it receives every task. Delegation lets the lead Agent hand a task outside its own domain to a more suitable member:

- **Decide**: after receiving a task, the lead Agent decides automatically, answering directly if the task is within its domain and forwarding it to a more suitable member in the session otherwise.
- **Execute**: the delegated member completes the task in its own workspace and returns the result to the lead Agent.
- **Reply**: the lead Agent consolidates the results and replies to the user, who always faces a single entry point.

Details such as the delegation scope, chain depth, and time budget are handled by the [agent_delegate tool](../tools/delegate.md) and can be adjusted in the configuration. The Agents page shows who is on the team. It does not show a delegation in progress.

## Differences from Sub-Agents

Agent teams and [sub-Agents](./subagent.md) both share the workload, but they serve different purposes:

| | Team member | Sub-Agent |
| --- | --- | --- |
| Lifecycle | Persistent, configured in advance | Created temporarily for one task, then discarded |
| Identity | Has a name and avatar, and appears in the team list | Anonymous, not in the list |
| Workspace | Independent | Shared with the lead Agent |
| Memory | Independent | Has no memory of its own |
| Use case | Long-term specialization, external-facing service | Splitting your own work to run in parallel, isolating large amounts of intermediate work |

> In short: use team collaboration when the task itself belongs to another persistent Agent (one that holds the relevant knowledge, permissions, or customer relationship); use a sub-Agent when you just want to split your own task to run in parallel and speed things up.
