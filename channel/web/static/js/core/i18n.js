/* Translation table and the t() / applyI18n() helpers.
   Split out of console.js. These are classic scripts sharing one global
   scope; see channel/web/README.md before changing the load order. */

// =====================================================================
// i18n
// =====================================================================
const I18N = {
    en: {
        chat_scroll_to_bottom: 'Scroll to bottom',
        console: 'Console',
        nav_chat: 'Chat', nav_manage: 'Management', nav_monitor: 'Monitor',
        menu_chat: 'Chat', menu_agents: 'Agents', menu_config: 'Config', menu_skills: 'Capabilities',
        agents_page_title: 'Agent Team', agents_page_desc: 'Manage the Agents on your team',
        agents_create: 'New Agent',
        agents_name_placeholder: 'Agent name',
        agents_name_required: 'Please enter a name',
        agents_stale: 'The list changed; please refresh and try again',
        agents_id_placeholder: 'Auto-generated if left blank',
        agents_id_tip: 'A unique identifier, fixed once created. Lowercase letters, digits and hyphens (-) only, e.g. ops-agent. Left blank, it is derived from the name.',
        agents_id_invalid: 'The id must start with a letter or digit and use only letters, digits, underscores and hyphens (max 64)',
        agents_avatar: 'Avatar',
        agents_tab_profile: 'Profile',
        agents_tab_skills: 'Skills',
        agents_tab_files: 'Core files',
        agents_core_edit: 'Edit',
        agents_core_preview: 'Preview',
        agents_core_file_agent: 'Persona',
        agents_core_file_user: 'User info',
        agents_core_file_rule: 'Workspace rules',
        agents_core_file_memory: 'Long-term memory',
        agents_default: 'Default',
        agents_archived: 'Archived',
        agents_chat: 'Start chat',
        agents_copy_id: 'Copy ID',
        agents_delete: 'Delete',
        agents_delete_title: 'Delete Agent',
        agents_delete_confirm: 'Delete Agent "{name}"? Its workspace and conversations will be removed for good.',
        agents_pick_hint: 'Pick Agents',
        agents_clone_label: 'Copy from an existing agent',
        agents_clone_hint: 'Copy its config, skills and knowledge as a starting point',
        agents_avatar_upload: 'Upload image',
        agents_clone_none: 'Blank',
        agents_clone_from: '{name}',
        agents_name: 'Name',
        agents_saved: 'Saved',
        agents_save_failed: 'Save failed',
        agents_no_desc: 'No responsibilities yet',
        agents_description: 'Responsibilities',
        agents_description_placeholder: 'What this Agent handles and when it should be used',
        agents_description_hint: 'Used for task assignment when Agents collaborate',
        agents_model: 'Default model',
        agents_model_follows_global: 'Follow the configured model',
        agents_model_default_hint: 'Uses the primary model. Change it under Model config.',
        agents_skills_all: 'Use every installed skill',
        agents_knowledge: 'Knowledge base',
        agents_knowledge_shared: 'Shared',
        agents_knowledge_own: 'Own',
        agents_knowledge_hint: 'Shared: read and write the same knowledge base as the team\nOwn: a private base, isolated from others',
        agents_knowledge_working: 'Working…',
        agents_knowledge_failed: 'Switch failed',
        agents_skills_pick: 'Only the skills checked below',
        agents_empty: 'No Agents yet. Create one to start a team.',
        agents_select_hint: 'Pick an Agent on the left to configure it',
        agents_pick_tip: 'Switch current Agent',
        composer_current_agent: 'Current Agent',
        team_members: 'In this conversation',
        team_invite: 'Add to chat',
        team_remove: 'Remove from this chat',
        composer_agent_owner: 'Owner',
        channel_bound_agent: 'Bind agent',
        channel_bound_default: 'default',
        channel_bound_agent_hint: 'first pick is the default agent: it receives messages and can delegate to the rest',
        channel_team_none: 'None',
        channel_team_no_candidates: 'No agents available',
        settings_tab_basic: 'General',
        settings_tab_models: 'Models',
        knowledge_shared_hint: 'Knowledge is shared by every Agent. Open it from the Knowledge page.',
        menu_memory: 'Memory', menu_knowledge: 'Knowledge', menu_channels: 'Channels', menu_tasks: 'Tasks',
        menu_logs: 'Logs',
        models_title: 'Models',
        models_desc: 'Manage chat, image, voice, embedding and search capabilities in one place',
        models_section_vendors: 'Provider Credentials',
        models_section_vendors_desc: 'Configured once, shared by multiple model capabilities',
        models_section_capabilities: 'Capabilities',
        models_add_vendor: 'Add Provider',
        models_provider: 'Provider',
        models_model: 'Model',
        models_voice: 'Voice',
        models_configured: 'configured',
        models_not_configured: 'not configured',
        models_pick_to_configure: 'pick to configure',
        models_clear_credential: 'Clear credentials',
        models_base_default_hint: 'Leave blank to use the official default base URL',
        models_catalog: 'Model catalog',
        models_catalog_advanced: '(Advanced · optional)',
        models_tag_text: 'Text',
        models_catalog_add: 'Add model',
        models_catalog_discover: 'Discover models',
        models_catalog_discovering: 'Discovering…',
        models_catalog_discovered: 'Added {n} models',
        models_catalog_discover_pick: 'Choose models to add',
        models_catalog_discover_apply: 'Add selected',
        models_catalog_discover_cancel: 'Cancel',
        models_catalog_discover_none: 'No new models found',
        models_catalog_window: 'Context window',
        models_catalog_output: 'Max output',
        models_catalog_no_budget: 'Context window and max output do not apply to this model type',
        models_catalog_custom_hint: 'Add a model list for this custom provider so you can pick models from a dropdown on the chat page; leave empty to type the model name manually',
        models_catalog_name_ph: 'Model name',
        models_catalog_reset: 'Restore defaults',
        models_tag_chat: 'Main Model',
        models_tag_vision: 'Image Understanding',
        models_tag_video: 'Video Understanding',
        models_tag_image: 'Image Generation',
        models_tag_embedding: 'Embedding',
        models_tag_asr: 'Speech Recognition',
        models_tag_tts: 'Speech Synthesis',
        models_base_default: 'Default',
        models_custom_vendor_label: 'Custom',
        models_custom_name: 'Name',
        models_custom_delete: 'Delete',
        models_custom_delete_confirm_title: 'Delete custom provider',
        models_custom_delete_confirm_msg: 'Delete this custom provider? This cannot be undone.',
        models_custom_name_required: 'Name is required',
        models_custom_base_required: 'API Base is required',
        models_custom_edit_title: 'Edit custom provider',
        models_custom_add_title: 'Add custom provider',
        models_capability_chat: 'Main Model',
        models_capability_chat_desc: 'Used for basic chat and agent reasoning',
        models_capability_chat_fallback: 'Main Model Fallback',
        models_capability_chat_fallback_desc: 'Takes over only after the main model fails for good',
        models_fallback_enable: 'Enable the fallback model',
        models_fallback_config: 'Fallback',
        models_fallback_config_tip: 'Configure the main-model fallback (takes over after the main model fails)',
        models_fallback_modal_title: 'Main Model Fallback',
        models_fallback_modal_desc: 'When the main model still fails after exhausting its retries, the next model in the fallback chain is tried in order until one succeeds or the chain runs out.',
        models_fallback_badge_on: 'Fallback on',
        models_fallback_chain_title: 'Fallback chain (tried in order)',
        models_fallback_chain_desc: 'If the first one fails, the second is tried, and so on — the longer the chain, the more backups a turn has',
        models_fallback_chain_add: 'Add a fallback model',
        models_fallback_chain_empty: 'No fallback models yet — add one below',
        models_fallback_chain_link: 'Fallback {{n}}',
        models_fallback_chain_move_up: 'Move up',
        models_fallback_chain_move_down: 'Move down',
        models_fallback_chain_remove: 'Remove',
        models_fallback_chain_incomplete: 'Enabling the fallback needs at least one complete provider + model entry',
        models_capability_vision: 'Image Understanding',
        models_capability_vision_desc: 'Recognizes image content, used by image recognition tools',
        models_capability_image: 'Image Generation',
        models_capability_image_desc: 'Generates images, used by image generation skills',
        models_auto_using: 'Preferred',
        models_capability_asr: 'Speech Recognition',
        models_capability_asr_desc: 'Voice to text',
        models_capability_tts: 'Speech Synthesis',
        models_capability_tts_desc: 'Text to voice',
        models_capability_embedding: 'Embedding',
        models_capability_embedding_desc: 'Used for vectorized retrieval of memory and knowledge',
        models_capability_search: 'Web Search',
        models_capability_search_desc: 'Real-time web retrieval, used by search tools',
        models_strategy_auto: 'auto',
        models_search_strategy_label: 'Strategy',
        models_search_strategy_fixed: 'Pinned',
        models_search_strategy_auto_hint: 'Auto-pick from configured providers',
        models_search_strategy_fixed_hint: 'Always use a specific provider',
        models_pending_config: 'Pending setup',
        models_search_available_label: 'Available:',
        models_search_none_configured: 'No search provider enabled yet — click add.',
        models_search_add_provider: 'Add provider',
        models_search_add_desc: 'Set the SearXNG instance URL',
        models_search_searxng_title: 'Configure SearXNG Instance URL',
        models_search_searxng_desc: 'Enter the URL of your self-hosted SearXNG instance (no API key required).',
        models_search_anonymous_badge: 'anonymous',
        models_search_anonymous_disable: 'Disable anonymous',
        models_search_edit_hint: 'Click to edit',
        models_search_disable_hint: 'Disable (keeps the credential)',
        models_search_enable_hint: 'Disabled, click to enable',
        models_unavailable: 'unavailable',
        models_set_via_env: 'enable via environment variable',
        models_dim_label: 'dim',
        models_save_success: 'Saved',
        models_save_failed: 'Save failed',
        models_cleared: 'Cleared',
        models_clear_failed: 'Clear failed',
        models_embedding_change_title: 'Change embedding model',
        models_embedding_change_msg: 'Switching the embedding model invalidates the existing index — a rebuild will be needed. Continue?',
        models_embedding_saved_title: 'Embedding model updated',
        models_embedding_saved_msg: 'Send /memory rebuild-index in the chat to rebuild the index.',
        models_embedding_saved_ok: 'Go',
        models_pick_provider: 'Pick a provider',
        models_manage_api_key: 'Manage API keys',
        models_clear_confirm_title: 'Clear provider credentials',
        models_clear_confirm_msg: 'Remove this provider\'s API Key and Base URL? Capabilities relying on it will stop working.',
        cancel: 'Cancel',
        save: 'Save',
        ok: 'OK',
        knowledge_title: 'Knowledge', knowledge_desc: 'Browse and explore your knowledge base',
        knowledge_tab_docs: 'Documents', knowledge_tab_graph: 'Graph',
        knowledge_loading: 'Loading knowledge base...', knowledge_loading_desc: 'Knowledge pages will be displayed here',
        knowledge_select_hint: 'Select a document to view', knowledge_empty_hint: 'No knowledge pages yet',
        knowledge_empty_guide: 'Send documents, links or topics to the agent in chat, and it will automatically organize them into your knowledge base.',
        knowledge_go_chat: 'Start a conversation',
        knowledge_new: 'New',
        knowledge_new_category: 'New category',
        knowledge_new_document: 'New document',
        knowledge_import_documents: 'Import documents',
        welcome_subtitle: 'I can help you answer questions, manage your computer, create and execute skills, and keep growing through <br> long-term memory and a personal knowledge base.',
        example_sys_title: 'System', example_sys_text: 'Show me the files in the workspace',
        example_task_title: 'Scheduler', example_task_text: 'Remind me to check the server in 5 minutes',
        example_code_title: 'Coding', example_code_text: 'Search today\'s AI news and generate a visual report webpage',
        example_knowledge_title: 'Knowledge', example_knowledge_text: 'Show me the current knowledge base',
        example_skill_title: 'Skills', example_skill_text: 'Show current tools and skills',
        example_web_title: 'Commands', example_web_text: 'Show all commands',
        slash_help: 'Show this help',
        slash_status: 'Show running status',
        slash_context: 'Show conversation context',
        slash_context_clear: 'Clear conversation context',
        slash_compact: 'Summarize older turns to free up context',
        slash_skill_list: 'List installed skills',
        slash_skill_list_remote: 'List the configured registry',
        slash_skill_search: 'Search skills',
        slash_skill_install: 'Install a skill (name or GitHub URL)',
        slash_skill_uninstall: 'Uninstall a skill',
        slash_skill_info: 'Show skill details',
        slash_skill_enable: 'Enable a skill',
        slash_skill_disable: 'Disable a skill',
        slash_memory_dream: 'Trigger memory distillation (optional days, default 3)',
        slash_knowledge: 'Show knowledge base stats',
        slash_knowledge_list: 'Show knowledge base file tree',
        slash_knowledge_on: 'Enable knowledge base',
        slash_knowledge_off: 'Disable knowledge base',
        slash_config: 'Show current config',
        slash_cancel: 'Abort the running Agent task',
        slash_steer: 'Inject guidance into the running Agent task',
        steer_active: 'Steer active task',
        slash_logs: 'Show recent logs',
        slash_version: 'Show version',
        input_placeholder: 'Type a message, / for commands, @ to reference a file',
        input_placeholder_team: 'Type a message, / for commands, @ to mention an Agent or a file',
        config_title: 'Configuration', config_desc: 'Manage model and agent settings',
        config_model: 'Model Configuration', config_agent: 'Agent Configuration',
        config_language: 'Language', config_language_hint: 'Language for the UI, command text, system prompts and more (synced with the top-right switch)',
        config_system: 'System',
        config_task_notify: 'Task Notifications', config_task_notify_hint: 'Show a browser notification when a task finishes or fails while the window is in the background; click to open the session',
        config_task_notify_sound: 'Notification Sound', config_task_notify_sound_hint: 'Turn off the alert sound while keeping notifications',
        config_task_notify_blocked: 'Notifications are blocked by the browser. Click the icon on the left of the address bar → Notifications → Allow, then reload.',
        notify_task_done: 'Task finished',
        notify_task_error: 'Task failed',
        config_model_advanced: 'Advanced',
        config_channel: 'Channel Configuration',
        config_agent_enabled: 'Agent Mode',
        config_max_tokens: 'Max Context Tokens', config_max_tokens_hint: 'Cap on the context input budget; history is compacted once reached, to control cost. Still clamped below the model window. Set 0 to disable the cap and follow the model window',
        config_max_turns: 'Max Memory Turns', config_max_turns_hint: 'One Q&A pair = one turn, auto-compressed when exceeded',
        config_max_steps: 'Max Steps', config_max_steps_hint: 'Max tool calls the Agent can make in a single conversation',
        config_enable_thinking: 'Deep Thinking', config_enable_thinking_hint: 'Enable deep thinking mode',
        config_reasoning_effort: 'Reasoning Effort', config_reasoning_effort_hint: 'Sent as the active provider\'s native enum value',
        config_subagent: 'Sub Agents', config_subagent_hint: 'Hand self-contained tasks to sub agents, which run in parallel and report back only their conclusions',
        config_self_evolution: 'Self-Evolution', config_self_evolution_hint: 'Auto-review idle conversations to consolidate memory, improve skills, and follow up on unfinished tasks',
        evolution_badge: 'Self-learned',
        config_channel_type: 'Channel Type',
        config_provider: 'Provider', config_model_name: 'Model',
        config_custom_model_hint: 'Enter custom model name',
        config_save: 'Save', config_saved: 'Saved',
        config_save_error: 'Save failed',
        config_custom_option: 'Custom',
        config_custom_tip: 'API must follow OpenAI protocol.',
        config_security: 'Security', config_password: 'Password',
        config_password_hint: 'Leave empty to disable password protection',
        config_api: 'Chat API', config_api_desc: 'Call your Agent through an OpenAI-compatible API', config_api_docs: 'Docs',
        config_api_base_url: 'Base URL', config_api_copy: 'Copy', config_api_example: 'Example',
        config_api_key_hint: 'Anyone with this key can use your Agent. Keep it secret.',
        config_api_example_hint: 'model: the model to use; the Agent\'s own model if left out\nagent_id: the Agent that answers; the default Agent if left out (copy IDs on the Agents page)',
        config_api_regenerate: 'Regenerate',
        config_api_regenerate_confirm: 'The current key stops working at once. Update any app that uses it.',
        config_api_disable: 'Turn off Chat API', config_api_disable_ok: 'Turn off',
        config_api_disable_confirm: 'The Agent can no longer be reached through the API. The key is kept and works again once the API is back on.',
        config_api_enable: 'Turn on Chat API', config_api_enable_ok: 'Turn on',
        config_api_enable_confirm: 'Once on, the Agent can be reached through the API. Continue?',
        config_permission: 'Default permissions',
        config_permission_hint: 'The default scope for new chats: which files the agent may change and which commands it may run',
        config_permission_desc: 'New chats start with this; each chat can be changed under the input box',
        config_password_changed: 'Password updated',
        config_password_cleared: 'Password cleared',
        config_password_security_warning: '⚠️ Warning: Password is now empty and the port is exposed. Consider restarting the service or adjusting the listening address binding.',
        skills_title: 'Capabilities', skills_desc: 'Manage the built-in tools, MCP tools, and skills your agent can use', skills_hub_btn: 'Registry',
        skills_loading: 'Loading skills...', skills_loading_desc: 'Skills will be displayed here after loading',
        skills_empty: 'No skills installed yet', skills_empty_hint: 'Install one from a skill market, or upload your own',
        tools_section_title: 'Built-in Tools', tools_loading: 'Loading tools...',
        tools_show_all: 'Show all', tools_collapse: 'Show less', tools_empty: 'No built-in tools', tools_load_failed: 'Failed to load',
        skills_section_title: 'Skills', skill_enable: 'Enable', skill_disable: 'Disable',
        skill_click_enable: 'Click to enable', skill_click_disable: 'Click to disable',
        skill_toggle_error: 'Operation failed, please try again',
        skill_open_hint: 'Click to view this skill',
        skill_edit_hint: 'Edit skill',
        skill_back: 'Back to list',
        skill_load_failed: 'Could not read the skill',
        skill_builtin_readonly: 'Built-in skill, read-only',
        skill_files_title: 'Skill files',
        skill_files_collapse: 'Collapse file list',
        skill_files_expand: 'Expand file list',
        skill_file_not_text: 'This file is not text and cannot be shown here',
        skill_new_name: 'Name',
        skill_new_name_hint: 'Becomes the skill directory: lowercase letters, digits and hyphens',
        skill_new_name_dir: 'Directory',
        skill_new_name_invalid: 'The name needs latin letters or digits',
        skill_new_desc: 'Description',
        skill_new_desc_hint: 'The description is what tells the agent when to use this skill, so say what it does and when',
        skill_new_desc_required: 'A description is required',
        skill_new_body: 'Instructions',
        skill_new_body_hint: 'The body of SKILL.md. Can be left empty and written later in the skill view',
        skill_new_files: 'Files', skill_new_files_add: 'Add', skill_new_files_pick: 'Choose files',
        skill_new_files_pick_folder: 'Choose folder',
        skill_new_files_hint: 'Scripts, templates and other resources, bundled into the skill directory',
        skill_new_submit: 'Create', skill_new_created: 'Skill created',
        skill_new_failed: 'Could not create the skill, please try again',
        skill_upload_too_many: 'Upload at most {max} files at a time',
        skill_upload_file_too_large: '{name} exceeds {max}MB',
        skill_upload_total_too_large: 'Total upload size cannot exceed {max}MB',
        mcp_section_title: 'MCP Tools',
        mcp_add: 'Add MCP', mcp_add_title: 'Add MCP tool', mcp_edit: 'Edit MCP tool',
        mcp_empty: 'No MCP tools connected yet', mcp_empty_hint: 'Fill in the form, or paste the JSON config an MCP directory gives you',
        mcp_test: 'Test connection', mcp_testing: 'Connecting and listing tools...', mcp_save: 'Save', mcp_cancel: 'Cancel', mcp_delete: 'Delete',
        mcp_saved: 'MCP tool saved', mcp_saved_tools: 'Saved. {n} tool(s) found.', mcp_save_anyway: 'Save anyway',
        mcp_check_failed: 'The connection check failed. Fix the config, or save anyway.',
        mcp_status_ready: 'Ready', mcp_status_pending: 'Loading', mcp_status_failed: 'Failed',
        mcp_status_needs_auth: 'Needs auth', mcp_status_disabled: 'Disabled', mcp_status_idle: 'Idle',
        mcp_tab_form: 'Form', mcp_advanced: 'Advanced',
        mcp_field_name: 'Name', mcp_field_name_ph: 'e.g. fetch', mcp_field_type: 'Transport', mcp_field_command: 'Command',
        mcp_field_args: 'Args (one per line)', mcp_field_env: 'Env (KEY=value per line)',
        mcp_field_url: 'URL', mcp_field_headers: 'Headers (KEY=value per line)', mcp_field_scope: 'OAuth scope',
        mcp_field_prefix: 'Tool name prefix', mcp_field_timeout: 'Timeout (seconds)', mcp_field_disabled: 'Disabled',
        mcp_transport_stdio_hint: 'Local command', mcp_transport_remote_hint: 'Remote server',
        mcp_json_hint: 'Paste a config in the mcpServers format. Several servers can be added at once.',
        mcp_json_invalid: 'Invalid JSON', mcp_json_empty: 'Enter an MCP config',
        mcp_json_need_name: 'Missing a name. Use the {"mcpServers": {"name": {...}}} format.',
        mcp_json_multi_to_form: 'This config has several MCP tools and can only be saved in JSON mode',
        mcp_json_edit_single: 'Only one MCP tool can be edited at a time',
        mcp_name_required: 'Enter a name', mcp_name_exists: 'An MCP tool named {name} already exists. Rename it or edit the existing one.',
        mcp_test_ok: 'Connected', mcp_test_fail: 'Connection failed', mcp_test_tools: 'Tools',
        mcp_test_no_tools: 'Connected, but the server offers no tools',
        mcp_test_needs_auth: 'Needs OAuth authorization. Save it, then follow the prompt in the chat.',
        mcp_save_error: 'Save failed', mcp_load_failed: 'Could not read the MCP config',
        mcp_delete_confirm: 'Delete this MCP tool?',
        skill_add: 'Add skill', skill_add_tab_market: 'From a market', skill_add_tab_upload: 'Upload', skill_add_tab_create: 'Write one',
        skill_source: 'Source', skill_source_local: 'Uploaded',
        skill_value_hub: 'Skill name', skill_value_github: 'Repository or folder URL',
        skill_hint_hub: 'The skill name on the registry you configured',
        skill_hint_github: 'A repository URL, a folder URL (/tree/branch/path), or owner/repo',
        skill_fetch: 'Fetch preview', skill_fetching: 'Fetching...',
        skill_upload_drop: 'Drop a skill here, or', skill_upload_pick_file: 'choose a file', skill_upload_pick_folder: 'a folder',
        skill_upload_types: '.zip / .tar.gz archive, a SKILL.md, or a whole skill folder, up to 50 MB',
        skill_uploading: 'Reading...', skill_upload_too_large: 'Files exceed 50 MB',
        skill_preview_title: 'Review before installing', skill_preview_found: '{n} skill(s) found',
        skill_preview_warning: 'Skills can include scripts the agent will run. Install only from sources you trust, after checking the content.',
        skill_preview_exists: 'Installed, will be replaced', skill_preview_files: '{n} file(s)', skill_preview_select_all: 'Select all',
        skill_preview_show_files: 'Files', skill_preview_truncated: 'Long file: only the first 64 KB is shown',
        skill_preview_no_md: 'No SKILL.md',
        skill_back_edit: 'Back', skill_confirm_install_n: 'Install {n}', skill_installing: 'Installing...',
        skill_installed_title: 'Installed', skill_installed_desc: '{n} skill(s) installed', skill_done: 'Done',
        skill_install_error: 'Install failed', skill_delete: 'Uninstall',
        skill_delete_confirm: 'Uninstall this skill?', skill_delete_error: 'Uninstall failed',
        memory_title: 'Memory', memory_desc: 'View agent memory files and contents',
        memory_tab_files: 'Memory Files', memory_tab_dreams: 'Self-Evolution',
        memory_loading: 'Loading memory files...', memory_loading_desc: 'Memory files will be displayed here',
        memory_back: 'Back to list',
        memory_col_name: 'Filename', memory_col_type: 'Type', memory_col_size: 'Size', memory_col_updated: 'Updated',
        channels_title: 'Web console', channels_desc: 'Chat uses the web console. The local terminal is still available.',
        channels_add: 'Connect', channels_disconnect: 'Disconnect',
        channels_save: 'Save', channels_saved: 'Saved', channels_save_error: 'Save failed',
        channels_restarted: 'Saved & Restarted',
        channels_connect_btn: 'Connect', channels_cancel: 'Cancel',
        channel_rename: 'Rename channel',
        channels_select_placeholder: 'Select a channel to connect...',
        channels_empty: 'No channels connected', channels_empty_desc: 'Click the "Connect" button above to get started',
        channels_disconnect_confirm: 'This channel will stop receiving messages. Disconnect it?',
        channels_disconnect_error: 'Failed to disconnect',
        channels_connected: 'Connected', channels_connecting: 'Connecting...',
        tasks_title: 'Scheduled Tasks', tasks_desc: 'View and manage scheduled tasks',
        tasks_coming: 'Coming Soon', tasks_coming_desc: 'Scheduled task management will be available here',
        tasks_tab_tasks: 'Tasks', tasks_tab_records: 'History',
        records_desc: 'Execution history of scheduled tasks',
        records_loading: 'Loading history...', records_empty: 'No executions yet',
        records_empty_guide: 'Once tasks run, both successful and failed executions show up here',
        records_status_done: 'Success', records_status_error: 'Failed', records_status_running: 'Running',
        records_trigger_scheduled: 'Scheduled', records_trigger_manual: 'Manual',
        records_duration: 'Duration', records_no_output: '(no content)',
        records_load_more: 'Load more', records_delete: 'Delete',
        records_delete_confirm_title: 'Delete record', records_delete_confirm_msg: 'Delete this execution record? This cannot be undone.',
        records_delete_failed: 'Delete failed, please retry',
        record_detail_title: 'Execution detail', record_detail_loading: 'Loading detail...',
        record_detail_status: 'Status', record_detail_trigger: 'Trigger',
        record_detail_started: 'Started', record_detail_duration: 'Duration',
        record_detail_channel_type: 'Channel type', record_detail_channel_name: 'Channel name',
        record_detail_agent: 'Agent', record_detail_output: 'Delivered',
        record_detail_view_preview: 'Preview', record_detail_view_text: 'Text',
        record_detail_error: 'Error',
        record_channel_web_type: 'web', record_channel_web_name: 'Web',
        task_add_btn: 'Add Task',
        task_edit_title: 'Edit Task',
        task_add_title: 'Add Task',
        task_name: 'Task Name',
        task_enabled: 'Enable Task',
        task_schedule_type: 'Schedule Type',
        task_schedule_cron: 'Cron Expression',
        task_schedule_interval: 'Fixed Interval',
        task_schedule_once: 'One-time Task',
        task_cron_expression: 'Cron Expression',
        task_cron_hint: 'Format: minute hour day month weekday, e.g. "0 9 * * *" means daily at 9:00',
        task_interval_seconds: 'Interval (seconds)',
        task_interval_hint: 'Minimum 60 seconds, e.g. 3600 means once per hour',
        task_once_time: 'Execution Time',
        task_action_type: 'Task Type',
        task_action_send_message: 'Fixed Message',
        task_action_agent_task: 'AI Task',
        task_channel_type: 'Channel Type',
        task_channel_hint: 'Select the channel to send scheduled messages',
        task_message_content: 'Message Content',
        task_fixed_content: 'Fixed Content',
        task_task_description: 'Task Description',
        task_delete_btn: 'Delete Task',
        task_delete_confirm_title: 'Delete Task',
        task_delete_confirm_msg: 'Delete this scheduled task? This action cannot be undone.',
        task_run_now: 'Run now',
        task_run_confirm_title: 'Run task now',
        task_run_confirm_msg: 'This task will immediately send to its configured channel and receiver. Continue?',
        task_run_started: 'Run started',
        task_run_failed: 'Run failed',
        task_add_title: 'New Scheduled Task',
        task_add_btn: 'New Task',
        task_recipient: 'Recipient',
        task_recipient_hint: 'Pick a channel first, then a contact within it; the task will be pushed to them.',
        task_recipient_select: 'Select recipient',
        task_recipient_empty: 'No recipients yet. They must message the agent in the web console first.',
        task_recipient_group: 'Group',
        task_recipient_user: 'User',
        task_recipient_placeholder: 'Select a recipient',
        task_recipient_refresh: 'Refresh recipient list',
        task_recipient_pick_instance_first: 'Pick a channel first',
        task_recipient_empty_hint: 'No recipients on this channel yet — message the agent on this channel first.',
        task_instance: 'Channel',
        task_instance_tip: 'After picking a channel, choose a contact you have talked with there; the task result is pushed to them.',
        task_instance_placeholder: 'Select a channel',
        task_instance_empty: 'No channels available',
        task_instance_no_recipient: 'No recipients',
        task_instance_required: 'Please select a channel',
        task_recipient_required: 'Please select a recipient',
        logs_title: 'Logs', logs_desc: 'Real-time log output (run.log)',
        logs_live: 'Live', logs_coming_msg: 'Log streaming will be available here. Connects to run.log for real-time output similar to tail -f.',
        new_chat: 'New Chat',
        new_team_chat: 'Group chat',
        new_team_chat_hint: 'Pick the Agents for this conversation; the first is its main Agent.',
        new_team_chat_owner: 'Main',
        new_team_chat_start: 'Start chat',
        new_team_chat_min: 'Pick at least two Agents',
        session_history: 'History',
        ws_toggle: 'Workspace', ws_tab_preview: 'Preview', ws_tab_files: 'Files',
        timeline_nav: 'Jump to message',
        menu_artifacts: 'Artifacts', artifacts_title: 'Artifacts',
        artifacts_desc: 'Pages, images, videos and documents your agents made in chats, in one timeline',
        artifacts_filter_all: 'All', artifacts_filter_web: 'Pages', artifacts_filter_image: 'Images',
        artifacts_filter_media: 'Video & audio', artifacts_filter_doc: 'Documents', artifacts_filter_other: 'Other',
        artifacts_search: 'Search name or path', artifacts_scope_all: 'All agents',
        artifacts_empty_title: 'No artifacts yet',
        artifacts_empty_desc: 'From now on, the pages and documents your agents write, and the images and videos they send you, will be collected here by time.',
        artifacts_empty_action: 'Start a chat',
        artifacts_no_match: 'Nothing matches these filters', artifacts_clear_filters: 'Clear filters',
        artifacts_today: 'Today', artifacts_yesterday: 'Yesterday',
        artifacts_jump: 'Show in chat',
        artifacts_jump_unavailable: 'Made in another channel or a deleted conversation, so it can\'t be located',
        artifacts_missing: 'File moved or deleted',
        artifacts_remove: 'Remove from artifacts', artifacts_removed: 'Removed. The file itself is untouched.',
        artifacts_remove_title: 'Remove from artifacts?', artifacts_remove_ok: 'Remove',
        artifacts_remove_confirm: '"{name}" will no longer appear in Artifacts. The file itself is not deleted, and you can add it back from its file card in the conversation.',
        artifacts_add: 'Add to artifacts', artifacts_added: 'Added to artifacts',
        artifacts_pin: 'Pin to top', artifacts_unpin: 'Unpin', artifacts_pinned_group: 'Pinned',
        artifacts_pinned: 'Pinned to top', artifacts_unpinned: 'Unpinned',
        artifacts_rename: 'Rename', artifacts_rename_failed: 'Rename failed',
        menu_edit: 'Customize menu',
        menu_edit_desc: 'Drag to reorder and regroup, and put artifacts or web pages in the menu. The web console and the desktop app share it.',
        menu_add: 'Add',
        menu_add_group: 'Add group',
        menu_add_artifact: 'Artifact (HTML / Markdown)',
        menu_add_url: 'Web link',
        menu_add_builtin: 'Built-in page',
        menu_group_untitled: 'Untitled group',
        menu_group_title_ph: 'Group name',
        menu_group_keeps_pages: 'Move the built-in pages to another group first',
        menu_item_title_ph: 'Name',
        menu_open_embed: 'Embed',
        menu_open_tab: 'New tab',
        menu_hide: 'Hide',
        menu_show: 'Show',
        menu_required: 'This page can\'t be hidden',
        menu_remove: 'Remove',
        menu_drag: 'Drag to reorder',
        menu_icon: 'Icon',
        menu_icon_default: 'Default icon',
        menu_reset: 'Restore default',
        menu_reset_confirm: 'The menu goes back to the built-in one, and the artifacts and links you added are removed.',
        menu_save_failed: 'Couldn\'t save',
        menu_need_title: 'Enter a name',
        menu_need_group_title: 'Enter a group name',
        menu_need_url: 'Enter a link starting with http:// or https://',
        menu_builtin_page: 'Built-in page',
        menu_unsupported: 'Not available here; kept for the other app',
        menu_artifact_search: 'Search artifacts',
        menu_artifact_empty: 'No artifacts found',
        menu_already_added: 'Already in the menu',
        menu_page_missing: 'This item is no longer in the menu',
        menu_file_missing: 'The file no longer exists',
        menu_open_external: 'Open in new tab',
        menu_back_chat: 'Back to chat',
        menu_add_to_menu: 'Add to menu',
        artifacts_view_in: 'View in artifacts', artifacts_untitled: 'Untitled chat',
        artifacts_load_failed: 'Failed to load', artifacts_retry: 'Retry',
        image_unavailable: 'Image unavailable',
        artifacts_meta_session: 'Chat', artifacts_meta_size: 'Size',
        sidebar_collapse: 'Collapse sidebar', sidebar_expand: 'Expand sidebar',
        ws_default_workspace: 'Default', ws_sel_title: 'Select workspace',
        ws_sel_default_hint: 'Use the default workspace (~/maia)', ws_sel_recents: 'Recent',
        ws_sel_open: 'Open project…', ws_sel_new: 'New project', ws_sel_new_placeholder: 'Project name',
        ws_sel_create: 'Create', ws_sel_up: 'Up',
        ws_sel_new_subtitle: 'Creates a new project directory under {root}', ws_sel_new_hint: 'Project name only, no path separators',
        ws_sel_name_required: 'Please enter a project name', ws_sel_name_no_slash: 'Project name must not contain / or \\',
        ws_sel_open_here: 'Open this folder', ws_sel_dblclick_hint: 'Double-click to enter, single-click to select',
        ws_sel_no_subdirs: 'No sub-folders here', ws_sel_drives: 'This PC',
        ws_open_external: 'Open in new tab', ws_download: 'Download',
        ws_reveal: 'Show in folder', ws_reveal_failed: 'Could not open the folder',
        ws_close: 'Close', ws_refresh: 'Refresh', ws_preview: 'Preview',
        ws_search_placeholder: 'Search files',
        ws_preview_empty: 'Select a file to preview',
        ws_preview_failed: 'Preview failed',
        ws_link_not_found: 'File not found in the workspace',
        ws_no_inline_preview: 'No inline preview for this file type',
        ws_empty_dir: 'Empty directory', ws_no_results: 'No matching files',
        ws_truncated: 'Too many files, showing a subset',
        ws_edit: 'Edit', ws_edit_save: 'Save (Ctrl+S)', ws_edit_cancel: 'Leave editor',
        ws_edit_saved: 'Saved',
        ws_edit_load_failed: 'Could not open the editor',
        ws_edit_save_failed: 'Save failed',
        ws_edit_too_large: 'File is too large to edit in the panel',
        ws_edit_unsupported: 'This file type cannot be edited',
        ws_edit_encoding: 'This file is not UTF-8; editing would corrupt it',
        ws_edit_conflict_title: 'File changed on disk',
        ws_edit_conflict_msg: 'This file changed while you were editing it, most likely written by the agent. Overwriting discards the newer content on disk.',
        ws_edit_overwrite: 'Overwrite',
        ws_edit_discard_title: 'Discard unsaved changes?',
        ws_edit_discard_msg: 'This file has unsaved changes and continuing will lose them.',
        ws_edit_discard_ok: 'Discard',
        today: 'Today', yesterday: 'Yesterday', earlier: 'Earlier',
        session_pinned_group: 'Pinned',
        pin_session: 'Pin',
        unpin_session: 'Unpin',
        project_rename: 'Rename project',
        project_delete: 'Delete project',
        project_rename_title: 'Rename project',
        project_delete_title: 'Delete project',
        project_delete_confirm: 'Delete project “{name}”? Only the project record is removed — files on disk are kept, and its chats revert to the default workspace.',
        perm_menu_title: 'Permissions for this chat',
        perm_read_only: 'Read-only',
        perm_workspace_write: 'Workspace write',
        perm_full_access: 'Full access',
        perm_read_only_desc: 'Read and analyse only; no file is modified',
        perm_workspace_write_desc: 'Write freely inside this workspace; writes outside it are refused',
        perm_full_access_desc: 'No limits, anywhere on the machine (current default)',
        perm_follow_global: 'Follow global setting',
        perm_tip: 'Permissions: {name}',
        perm_denied_hint: 'This session is “{name}”, so the action was refused.',
        perm_denied_action: 'Adjust permissions',
        model_menu_title: 'Model for this chat',
        model_follow_global: 'Follow global setting',
        model_follow_agent: 'Follow the agent\u2019s default model',
        model_tip: 'Model: {name}',
        model_unset: 'Not set',
        session_settings_failed: 'Could not apply, please retry',
        delete_session_confirm: 'Delete this session? All messages will be removed.',
        delete_session_title: 'Delete Session',
        rename_session: 'Rename',
        delete_message_confirm: 'Delete this message?',
        delete_message_title: 'Delete Message',
        edit_disabled_reply_active: 'Reply is being generated; editing is temporarily unavailable.',
        delete_disabled_reply_active: 'Reply is being generated; deletion is temporarily unavailable.',
        untitled_session: 'New Chat',
        context_cleared: '— Context above has been cleared —',
        tip_new_chat: 'New Chat',
        tip_clear_context: 'Clear Context',
        ctx_usage_title: 'Context usage',
        ctx_system: 'System prompt',
        ctx_tools: 'Tools & skills',
        ctx_history: 'Conversation',
        ctx_free: 'Free',
        ctx_used_of: '{used} / {limit} used',
        ctx_estimated: 'estimated',
        ctx_restored: 'last run',
        ctx_empty: 'No context built for this session yet',
        ctx_error: 'Could not load context usage',
        ctx_act_compact: 'Compact', ctx_act_compact_tip: 'Summarize older turns to free up context',
        ctx_act_clear: 'Clear', ctx_act_clear_tip: 'Clear the current conversation context',
        ctx_act_adjust: 'Config', ctx_act_adjust_tip: 'Adjust the max context tokens',
        ctx_compacting: 'Compacting context…',
        ctx_compact_failed: 'Compaction failed, please try again',
        ctx_compact_noop: 'Context is already short, nothing to compact',
        ctx_compacted_divider: 'Context compacted ({before} → {after} messages)',
        ctx_busy_turn: 'A reply is being generated; please wait until it finishes',
        tip_attach: 'Add Attachment',
        tip_cancel: 'Cancel',
        tip_cancelled: 'Cancelled',
        attach_menu_file: 'Upload File',
        mic_idle_title: 'Click to record, click again to stop',
        mic_recording_title: 'Recording, click to stop',
        mic_busy_title: 'Transcribing…',
        mic_permission_denied: 'Cannot access microphone — check browser permissions',
        mic_too_short: 'Recording too short, please retry',
        mic_error: 'Speech recognition failed',
        optimize_idle_title: 'Optimize prompt',
        optimize_busy_title: 'Optimizing…',
        optimize_error: 'Prompt optimization failed',
        optimize_empty: 'Input is empty, nothing to optimize',
        speak_msg: 'Read this reply aloud',
        voice_reply_mode_label: 'Voice reply policy',
        voice_reply_off: 'Off',
        voice_reply_if_voice: 'Voice only if voice input',
        voice_reply_always: 'Always reply with voice',
        attach_menu_folder: 'Upload Folder',
        confirm_yes: 'Confirm',
        confirm_cancel: 'Cancel',
        error_send: 'Failed to send. Please try again.', error_timeout: 'Request timeout. Please try again.',
        reply_cancelled: 'Stopped', reply_interrupted: 'Interrupted', reply_running: 'Still running; refresh later to see the latest progress',
        msg_usage_total: 'Tokens', msg_usage_in: 'In', msg_usage_out: 'Out',
        msg_usage_cached: 'Cached', msg_usage_calls: '{n} model calls',
        error_connection_lost: 'Connection lost. The reply may still be in progress; refresh the page later to see it.',
        thinking_in_progress: 'Thinking...', thinking_done: 'Thought', thinking_duration: 'Duration',
        handoff_to: 'Handed to {name}',
        retrieval_selected: 'Selected {selected}/{total} MCP tools',
        retrieval_fallback: 'Using all {total} MCP tools',
        retrieval_selected_tools: 'Selected tools', retrieval_ranking: 'Relevance ranking',
        retrieval_fallback_reason: 'Fallback reason',
        edit_message: 'Edit message',
        regenerate_response: 'Regenerate',
        edit_save: 'Save and send',
        edit_cancel: 'Cancel',
        logout: 'Logout',
        update_check: 'Check for update',
        update_checking: 'Checking…',
        update_up_to_date: 'You are up to date',
        update_now: 'Update now',
        update_changelog: 'Release notes',
        update_error: 'Could not check for updates',
        update_unsupported: 'This install cannot self-update',
        update_confirm: 'This will pull the latest code and restart the service. Continue?',
        update_starting: 'Starting update…',
        update_in_progress: 'Updating…',
        update_reconnect: 'Service is restarting. Reconnecting…',
        update_done: 'Update complete',
        update_failed: 'Update failed',
        update_step_git_pull: 'Pulling latest code',
        update_step_install_deps: 'Installing dependencies',
        update_step_install_cli: 'Reinstalling the CLI',
        update_step_self_check: 'Checking the new code',
        update_step_restart: 'Restarting the service',
        update_step_starting: 'Preparing the update',
        update_step_done: 'Done',
        mermaid_code: 'Code',
        mermaid_preview: 'Preview',
        mermaid_preview_failed: 'Diagram could not be rendered',
    }
};

// English is the only console language.
let currentLang = 'en';

function t(key) {
    return (I18N.en && I18N.en[key]) || key;
}

function localizedLabel(label) {
    if (label && typeof label === 'object') {
        return label.en || '';
    }
    return label || '';
}

function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
        el.innerHTML = t(el.dataset.i18nHtml);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.dataset['i18nPlaceholder']);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = t(el.dataset['i18nTitle']);
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
        el.setAttribute('aria-label', t(el.dataset['i18nAriaLabel']));
    });
    document.querySelectorAll('[data-i18n-tip]').forEach(el => {
        el.setAttribute('data-tip', t(el.dataset['i18nTip']));
    });
    document.querySelectorAll('[data-tip-key]').forEach(el => {
        el.setAttribute('data-tooltip', t(el.dataset.tipKey));
    });
    installCfgTipPortal();
    installContextUsagePopover();
    if (typeof syncSidebarTips === 'function') syncSidebarTips();
    document.querySelectorAll('[id$="-status"]').forEach(el => {
        el.classList.add('opacity-0');
    });
    const docsLink = document.getElementById('docs-link');
    if (docsLink) docsLink.href = 'https://github.com/dubhagen/Maia/tree/master/docs';
    if (typeof relocalizeWorkspacePanel === 'function') relocalizeWorkspacePanel();
}

function setLanguage() {}
function syncLanguageToBackend(_lang, callback) { if (callback) callback(); }
function updateLangControls() {}
function _syncLangControls() {}
function toggleLangMenu() {}
function selectLanguage() {}

// Refresh JS-rendered views after a language switch. Each branch uses the
// lightweight in-memory re-render path (no extra network round-trips).
function rerenderDynamicViews() {
    // Models are a tab of the config view, not a view of their own.
    if (currentView === 'config' && typeof renderModelsView === 'function'
            && modelsState && (modelsState.providers || modelsState.capabilities)) {
        renderModelsView();
    }
    // Reload task list after language switch
    if (currentView === 'tasks') {
        tasksLoaded = false;
        loadTasksView();
    }
    // Reload skills and tools after language switch
    if (currentView === 'skills') {
        toolsLoaded = false;
        loadSkillsView();
    }
    // Reload channels after language switch
    if (currentView === 'channels') {
        loadChannelsView();
    }
    // Reload config after language switch
    if (currentView === 'config') {
        loadConfigView();
    }
    // Repaint the Agents workbench after a language switch. The grid, detail
    // pane and avatar picker are built from t() into innerHTML, so applyI18n()
    // (which only touches data-i18n nodes) can't relocalize them; re-render from
    // the in-memory catalog instead of refetching.
    if (currentView === 'agents') {
        renderAgentsGrid();
        if (selectedAdminAgentId) renderAgentDetail();
    }
    if (currentView === 'artifacts') rerenderArtifactsView();
}

// Floating tooltip portal for [data-tip-key] elements. Tooltip nodes are
// appended to <body> so they aren't clipped by overflow:hidden ancestors
// (e.g. the config panel's scroll container).
let _cfgTipPortalEl = null;
let _cfgTipPortalInstalled = false;
function installCfgTipPortal() {
    if (_cfgTipPortalInstalled) return;
    _cfgTipPortalInstalled = true;

    const showTip = (target) => {
        const text = target.getAttribute('data-tooltip');
        if (!text) return;
        if (!_cfgTipPortalEl) {
            _cfgTipPortalEl = document.createElement('div');
            _cfgTipPortalEl.className = 'cfg-tip-floating';
            document.body.appendChild(_cfgTipPortalEl);
        }
        _cfgTipPortalEl.textContent = text;
        const rect = target.getBoundingClientRect();
        // Render once to measure, then position relative to the target.
        _cfgTipPortalEl.style.left = '0px';
        _cfgTipPortalEl.style.top = '0px';
        _cfgTipPortalEl.classList.add('show');
        const tipRect = _cfgTipPortalEl.getBoundingClientRect();
        const pos = target.getAttribute('data-tooltip-pos');
        let left;
        let top;
        if (pos === 'right') {
            left = rect.right + 10;
            top = rect.top + rect.height / 2 - tipRect.height / 2;
        } else {
            left = rect.left + rect.width / 2 - tipRect.width / 2;
            // Clamp horizontally to the viewport with an 8px gutter.
            left = Math.max(8, Math.min(left, window.innerWidth - tipRect.width - 8));
            // Default above the target; place below when data-tooltip-pos="bottom".
            top = pos === 'bottom' ? rect.bottom + 6 : rect.top - tipRect.height - 6;
        }
        _cfgTipPortalEl.style.left = left + 'px';
        _cfgTipPortalEl.style.top = top + 'px';
    };
    // Runs on every scroll and pointerdown, so skip the DOM write when already
    // hidden: a no-op classList.remove still wakes the Tailwind runtime.
    const hideTip = () => {
        if (_cfgTipPortalEl && _cfgTipPortalEl.classList.contains('show')) {
            _cfgTipPortalEl.classList.remove('show');
        }
    };

    // Matches config keys and any element opting into the floating tooltip via
    // [data-tip-float] (used for dynamic tooltips like the workspace selector,
    // whose data-tooltip is set at runtime rather than from a translation key).
    const _tipSel = '[data-tip-key],[data-tip-float]';
    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest(_tipSel);
        if (target) showTip(target);
    });
    document.addEventListener('mouseout', (e) => {
        const target = e.target.closest(_tipSel);
        if (target) hideTip();
    });
    // Hide on scroll/resize so the tooltip doesn't drift away from its anchor,
    // and on press: a click may hide or move the anchor, so no mouseout follows.
    window.addEventListener('scroll', hideTip, true);
    window.addEventListener('resize', hideTip);
    document.addEventListener('pointerdown', hideTip, true);
}

