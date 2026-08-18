from pathlib import Path
from typing import Any

import yaml


CONFIG_DIRECTORY = Path(__file__).parent / "config"


def load_yaml_config(filename: str) -> dict[str, Any]:
    config_path = CONFIG_DIRECTORY / filename
    if not config_path.is_file():
        raise FileNotFoundError(
            f"YAML config not found: {config_path}"
        )
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Failed to parse YAML config {filename}") from error

    if not isinstance(config, dict):
        raise ValueError(f"Invalid YAML config in {filename}: must be a mapping")

    return config


def get_agent_config(agent_name: str) -> dict[str, Any]:
    agents_config = load_yaml_config("agents.yaml")

    agent_config = agents_config.get(agent_name)
    if not isinstance(agent_config, dict):
        raise ValueError(f"Agent configuration not found: {agent_name}")

    return agent_config


def get_task_config(task_name: str) -> dict[str, Any]:
    tasks_config = load_yaml_config("tasks.yaml")

    task_config = tasks_config.get(task_name)
    if not isinstance(task_config, dict):
        raise ValueError(f"Task configuration not found: {task_name}")

    return task_config

def render_task_config(task_name: str,**template_values: str) -> dict[str, Any]:
    task_config = get_task_config(task_name)
    rendered_config: dict[str, Any] = {}                                                                                                
                                                                                                                                          
    for field_name, field_value in task_config.items():                                                                                 
        if not isinstance(field_value, str):                                                                                            
            raise ValueError(                                                                                                           
                f"Task field '{field_name}' in {task_name} must be a string."                                                           
            )                                                                                                                           
                                                                                                                                          
        try:                                                                                                                            
            rendered_config[field_name] = field_value.format(**template_values)                                                         
        except KeyError as error:                                                                                                       
            missing_value = error.args[0]                                                                                               
            raise ValueError(                                                                                                           
                f"Missing template value '{missing_value}' for task: {task_name}"                                                       
            ) from error                                                                                                                
                                                                                                                                          
    return rendered_config 