import os
import json
from config import pconf, plugin_config, conf, write_plugin_config  # noqa: F401  # re-exported via `from .plugin import *`
from common.atomic_write import write_json_atomic
from common.log import logger


class Plugin:
    def __init__(self):
        self.handlers = {}

    def load_config(self) -> dict:
        """Load this plugin's config dict."""
        
        plugin_conf = pconf(self.name)
        if not plugin_conf:
            
            plugin_config_path = os.path.join(self.path, "config.json")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8-sig") as f:
                    plugin_conf = json.load(f)

                
                write_plugin_config({self.name: plugin_conf})
        return plugin_conf

    def save_config(self, config: dict):
        try:
            write_plugin_config({self.name: config})
            
            global_config_path = "./plugins/config.json"
            if os.path.exists(global_config_path):
                write_json_atomic(global_config_path, plugin_config)
            
            plugin_config_path = os.path.join(self.path, "config.json")
            if os.path.exists(plugin_config_path):
                write_json_atomic(plugin_config_path, config)

        except Exception as e:
            logger.warn("save plugin config failed: {}".format(e))

    def get_help_text(self, **kwargs):
        return "No help is available."

    def reload(self):
        pass
