"""Extractors for system data metrics, intended for influxDB usage."""

import json
import logging
import re

__all__: list[str] = [
    "hw_stat",
    "state_cpu",
    "throughput",
    "ha_state",
    "packet_buffer_stats",
    "disk_usage",
]

LOGGER = logging.getLogger("mandiri-mona.data_extractor")


def hw_stat(raw: str) -> dict[str, float | None]:
    r"""
    Extract hardware statistics (CPU and memory usage) from raw system output.

    Parses raw hardware statistics string to extract CPU idle percentage and memory
    usage percentage. Returns a dictionary containing normalized metrics where values
    are between 0-100 or None if metrics cannot be extracted.

    Args:
        raw: Raw string output containing hardware statistics (e.g., from top/free commands).

    Returns:
        A dictionary with keys:
            - "cpu.hw": CPU usage percentage (0-100) or None if not found
            - "mem.hw": Memory usage percentage (0-100) or None if not found

    Example:
        >>> hw_stat("90.5 id\\nMiB Mem : 8192.0 total,  2048.0 free,")
        {'cpu.hw': 9.5, 'mem.hw': 75.0}
    """
    res: dict[str, float | None] = {}
    expression: dict[str, re.Pattern[str]] = {
        "cpu.hw": re.compile(r"([\d\.]+)\sid", re.MULTILINE),
        "mem.hw": re.compile(r"MiB Mem : ([\d\.]+)\stotal,\s+([\d\.]+)\sfree,", re.MULTILINE),
    }

    cpu_hw: float | None = next(((100 - float(x)) for x in expression["cpu.hw"].findall(raw)), None)
    mem_hw: float | None = None
    if (_ := expression["mem.hw"].findall(raw)) != [] and len(_[0]) == 2:
        if (
            isinstance(tot := next((float(x) for x in [_[0][0]]), False), float)
            and isinstance(free := next((float(x) for x in [_[0][1]]), False), float)
            and tot > 0
        ):
            mem_hw = ((tot - free) / tot) * 100

    res["cpu.hw"] = cpu_hw
    res["mem.hw"] = mem_hw

    return res


def state_cpu(raw: str) -> dict[str, float | None]:
    r"""
    Extract CPU state metrics from raw system data.

    Parses a raw string containing system metrics and extracts CPU-related
    values using regex pattern matching. Returns a dictionary with CPU metrics
    where keys are prefixed with 'cpu.' and values are float representations
    of the extracted metrics.

    Args:
        raw (str): Raw system data string containing CPU metrics in the format
                    matching the pattern 'sys.+s1.(\\w+).+\'cpu\'.+\\dminavg\'\\:\\s?(\\d)'

    Returns:
        dict[str, float]: Dictionary mapping CPU metric names (prefixed with 'cpu.')
                            to their corresponding float values. Returns an empty
                            dictionary if no matches are found.

    Example:
        >>> data = "sys.server.s1.instance.'cpu'.5minavg': 75"
        >>> result = state_cpu(data)
        >>> result
        {'cpu.instance': 75.0}
    """
    res: dict[str, float | None] = {}

    expression: re.Pattern[str] = re.compile(r"^sys.+s1.(\w+).+\'cpu\'.+\dminavg\'\:\s?(\d+)", re.MULTILINE)
    subs_string: list[tuple[str, str]] = expression.findall(raw)

    for key, val in subs_string:
        try:
            res[f"cpu.{key}"] = float(val)
        except ValueError as err:
            res[f"cpu.{key}"] = None
            LOGGER.warning(f"ValueError converting CPU metric '{key}' with value '{val}': {err}")
        finally:
            continue

    return res


def throughput(raw: str) -> dict[str, float | None]:
    r"""
    Extract throughput metrics from raw output string.

    Parses raw text output to extract specific throughput-related metrics including
    number of sessions, packet rate, and throughput values. Converts numeric values
    to floats and handles conversion errors gracefully.

    Args:
        raw: Raw output string containing throughput metrics in "key: value" format.

    Returns:
        A dictionary mapping cleaned metric names (lowercase with underscores) to their
        numeric values as floats, or None if conversion fails.

    Examples:
        >>> raw = "Number of sessions supported: 1000\\nThroughput: 5000"
        >>> throughput(raw)
        {'number_of_sessions_supported': 1000.0, 'throughput': 5000.0}
    """
    included_output_list = ["Number of sessions supported", "Number of allocated sessions", "Packet rate", "Throughput"]
    expression = re.compile(r"^(.+)\:\s+(\d+)", re.MULTILINE)
    res: dict[str, float | None] = {}

    filtered_raw: str = "\n".join([line for line in raw.splitlines() if line.split(": ")[0] in included_output_list])
    subs_string: list[tuple[str, str]] = expression.findall(filtered_raw)

    for key, val in subs_string:
        key_cleaned = key.lower().replace(" ", "_")
        try:
            res[key_cleaned] = float(val)
        except ValueError as err:
            res[key_cleaned] = None
            LOGGER.warning(f"ValueError converting throughput metric '{key}' with value '{val}': {err}")
        finally:
            continue

    return res


def ha_state(raw: str) -> dict[str, str | None]:
    """
    Extract HA (High Availability) state information from a raw string.

    Parses a raw text string to extract HA state, enabled status, and mode information
    using regex pattern matching. Returns a dictionary with the extracted values, or None
    for any values that could not be found.

    Args:
        raw (str): Raw text containing HA state information with the format:
                    "State: <state>... Enabled: <enabled>... : <mode>"

    Returns:
        dict[str, str | None]: A dictionary containing:
            - "ha.state": The HA state value or None if not found
            - "sync.state": The enabled status value or None if not found
            - "conf.sync": The mode value or None if not found
    """
    expression = re.compile(r"State:\s(\w+)[\S\s]+Enabled:\s(\w+)[\S\s]+:\s(\w+)", re.MULTILINE)

    states = expression.findall(raw)
    state_list: list[str | None] = []
    if states:
        for i in range(3):
            try:
                state_list.append(states[0][i])
            except IndexError:
                state_list.append(None)
    else:
        # No matches found; default all HA-related states to None
        state_list = [None, None, None]

    return {"ha.state": state_list[0], "sync.state": state_list[1], "conf.sync": state_list[2]}


def packet_buffer_stats(raw: str) -> dict[str, float | None]:
    r"""
    Extract packet buffer statistics from raw text data.

    Parses raw text containing packet buffer statistics organized by DP (Data Port)
    sections and extracts metric values for each section. Returns a dictionary with
    keys formatted as "{dp}.{metric}.{section}.min2" mapped to their float values.

    Args:
        raw: Raw text string containing packet buffer statistics, potentially with
                multiple DP sections formatted as "DP <identifier>: ...".

    Returns:
        A dictionary mapping metric keys (format: "dp.metric.section.min2") to their
        corresponding float values. If a value cannot be converted to float, the key
        is mapped to None and a warning is logged.

    Raises:
        No explicit exceptions raised. ValueError during float conversion is caught
        and logged with None assigned to the metric key.

    Examples:
        >>> raw = "DP s0p0:\nPacket Buffer (Min 2): 5\nPacket Descriptor (Min 2): 0"
        >>> packet_buffer_stats(raw)
        {'s0p0.packet_buffer.min2': 5.0, 's0p0.packet_descriptor.min2': 0.0}
    """
    expression: dict[str, re.Pattern] = {
        "dp": re.compile(r"^DP\s(\w+).+$", re.MULTILINE),
        "per_section": re.compile(r"^(.+)\((.+)\).+\s+(\d)\s+(\d)", re.MULTILINE),
    }
    res: dict[str, float | None] = {}

    raw_split: list[str] = []
    dp_subs: list[str] = expression["dp"].findall(raw)
    if len(dp_subs) == 0:
        dp_subs = ["s0p0"]
        raw_split = [raw]
    else:
        raw_split = re.findall(r"(DP\s+[^:]+:(?:(?!DP\s+)[^\n]*\n)*)", raw, re.MULTILINE)

    for idx, dp in enumerate(dp_subs):
        vals: list[tuple[str, str, str, str]] = expression["per_section"].findall(raw_split[idx])
        for val in vals:
            metric: str = val[0].strip().lower().replace(" ", "_")
            metric: str = metric.replace("(", "").replace(")", "")
            mt_section: str = val[1].strip().lower().replace(" ", "_")
            for i in range(2, 4):
                try:
                    res[f"{dp}.{metric}.{mt_section}.min{i-1}"] = float(val[i])
                except ValueError as err:
                    res[f"{dp}.{metric}.{mt_section}.min{i-1}"] = None
                    LOGGER.warning(
                        f"ValueError converting packet buffer stat '{val[0]} {val[1]}' with value '{val[i]}': {err}"
                    )
                finally:
                    continue

    return res


def disk_usage(raw: str) -> dict[str, str]:
    """
    Parse disk usage information from raw command output and return structured data.

    Extracts filesystem disk usage statistics from the output of a disk usage command
    (e.g., `df` command output) using regex pattern matching. Each line is parsed to
    extract filesystem name, size, used space, available space, usage percentage, and
    mount point.

    Args:
        raw: A string containing raw disk usage command output with multiple lines,
                where each line contains space-separated columns for filesystem, size,
                used, available, usage percentage, and mount point.

    Returns:
        A dictionary with a single key "disk.usage" containing a JSON-formatted string
        representation of a list of dictionaries. Each dictionary represents one
        filesystem with keys: "filesystem", "size", "used", "avail", "use%",
        "mounted_on".
        {'disk.usage': '[{"filesystem": "sda1", "size": "100G", "used": "50G", "avail": "50G", "use%": "50%", "mounted_on": "/"}]'}

    Example:
        >>> raw = "sda1 100G 50G 50G 50% /"
        >>> disk_usage(raw)
        {'disk.usage': '[{"filesystem": "sda1", "size": "100G", "used": "50G", "avail": "50G", "use%", "mounted_on": "/"}]'}
    """  # noqa: E501
    res: list[dict[str, str]] = []
    expression = re.compile(
        r"^(\S+)\s+([\d\.]+\D?)\s+([\d\.]+\D?)\s+([\d\.]+\D?)\s+([\d\.]+\D?)\s+(\S+)$", re.MULTILINE
    )
    keys: list[str] = ["filesystem", "size", "used", "avail", "use%", "mounted_on"]

    subs_string: list[tuple[str, str, str, str, str, str]] = expression.findall(raw)
    for subs in subs_string:
        res.append(dict(zip(keys, subs)))

    return {"disk.usage": json.dumps(res)}
