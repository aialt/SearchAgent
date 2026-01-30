import json
import logging
import os
import psutil
from typing import List, Union, Dict


from .types import HumanInputFormat, RunPaths


class LLMCallFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = json.loads(record.getMessage())
            return message.get("type") == "LLMCall"
        except (json.JSONDecodeError, AttributeError):
            return False


# Define recursive types for JSON structures
JsonPrimitive = Union[str, int, float, bool, None]
JsonList = List[Union[JsonPrimitive, "JsonDict", "JsonList"]]
JsonDict = Dict[str, Union[JsonPrimitive, JsonList, "JsonDict"]]
JsonData = Union[JsonDict, JsonList, str]


def json_data_to_markdown(data: JsonData) -> str:
    """
    Convert a dictionary, list, or JSON string to a nicely formatted Markdown string.
    Handles nested structures of dictionaries and lists.

    Args:
        data (JsonData): The data to convert, can be:
            - A dictionary with string keys and JSON-compatible values
            - A list of JSON-compatible values
            - A JSON string representing either of the above

    Returns:
        str: The formatted Markdown string.

    Raises:
        ValueError: If the input cannot be parsed or converted to markdown format.
        json.JSONDecodeError: If the input string is not valid JSON.
    """

    def format_dict(d: JsonDict, indent: int = 0) -> str:
        md = ""
        for key, value in d.items():
            md += "  " * indent + f"- {key}: "
            if isinstance(value, dict):
                md += "\n" + format_dict(value, indent + 1)
            elif isinstance(value, list):
                md += "\n" + format_list(value, indent + 1)
            else:
                md += f"{value}\n"
        return md

    def format_list(lst: JsonList, indent: int = 0) -> str:
        md = ""
        for item in lst:
            if isinstance(item, dict):
                md += "  " * indent + "- \n" + format_dict(item, indent + 1)
            elif isinstance(item, list):
                md += "  " * indent + "- \n" + format_list(item, indent + 1)
            else:
                md += "  " * indent + f"- {item}\n"
        return md

    try:
        if isinstance(data, str):
            data = json.loads(data)

        if isinstance(data, list):
            return format_list(data)
        elif isinstance(data, dict):
            return format_dict(data)
        else:
            raise ValueError(f"Expected dict, list or JSON string, got {type(data)}")

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON string: {str(e)}", e.doc, e.pos)
    except Exception as e:
        raise ValueError(f"Failed to convert to markdown: {str(e)}")


def dict_to_str(data: Union[JsonDict, str]) -> str:
    """
    Convert a dictionary or JSON string to a JSON string.

    Args:
        data (JsonDict | str): The dictionary or JSON string to convert.

    Returns:
        str: The input dictionary in JSON format.
    """
    if isinstance(data, dict):
        return json.dumps(data)
    elif isinstance(data, str):
        return data
    else:
        raise ValueError("Unexpected input type")


def get_internal_urls(inside_docker: bool, paths: RunPaths) -> List[str] | None:
    if not inside_docker:
        return None
    urls: List[str] = []
    for _, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == "AF_INET":
                urls.append(addr.address)

    hostname = os.getenv("HOSTNAME")
    if hostname is not None:
        urls.append(hostname)
    container_name = os.getenv("CONTAINER_NAME")
    if container_name is not None:
        urls.append(container_name)
    return urls
