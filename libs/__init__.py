from typing import Callable

from .data_extractor import disk_usage, ha_state, hw_stat, packet_buffer_stats, state_cpu, throughput
from .device_comm import process_high_availability_state as ha_proc
from .device_comm import process_resource_utilization as resutil_proc
from .device_comm import process_system_info as sysinf_proc

# TODO: If there is no function assign to a command, then it should return the raw output as is with a lambda function.
COMMANDS_LIST: dict[str, list[tuple[str, Callable | None]]] = {
    "dep_format": [
        ("show system state | match 1minavg", None),
        ("show system disk-space", None),
        ("show session info", sysinf_proc),
        ("show high-availability state | match State:", ha_proc),
        ("show running resource-monitor minute last 2", resutil_proc),
    ],
    "influxdb_format": [
        ("show system resources", hw_stat),
        ("show system state | match 1minavg", state_cpu),
        ("show session info", throughput),
        (r'show high-availability state | match "State\|Enabled\|Running Configuration"', ha_state),
        ("show running resource-monitor minute last 2", packet_buffer_stats),
        ("show system disk-space", disk_usage),
        ("show system info | match operational-mode", None),
    ],
}
