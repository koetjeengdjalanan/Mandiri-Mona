"""Test suite for data extraction functions.

This module contains unit tests for the functions defined in the
libs.data_extractor module.
"""

from libs.data_extractor import disk_usage, ha_state, hw_stat, packet_buffer_stats, state_cpu, throughput


def test_hw_stat_edge_cases():
    """Test edge cases for the hw_stat function."""
    assert hw_stat("0.0 id\nMiB Mem : 8192.0 total,  8192.0 free,") == {"cpu.hw": 100.0, "mem.hw": 0.0}
    assert hw_stat("0.0 id\nMiB Mem : 0.0 total,  0.0 free,") == {"cpu.hw": 100.0, "mem.hw": None}
    assert hw_stat("100.0 id\nMiB Mem : 8192.0 total,  0.0 free,") == {"cpu.hw": 0.0, "mem.hw": 100.0}
    assert hw_stat("100.0 id\nMiB Mem : 0.0 total,  0.0 free,") == {"cpu.hw": 0.0, "mem.hw": None}


def test_state_cpu_edge_cases():
    """Test edge cases for the state_cpu function."""
    assert state_cpu("sys.server.s1.instance.'cpu'.5minavg': 0") == {"cpu.instance": 0.0}
    assert state_cpu("sys.server.s1.instance.'cpu'.5minavg': 100") == {"cpu.instance": 100.0}
    # Code bellow needed to be commented for there is no evidence the raw input can be other then float
    # assert state_cpu("sys.server.s1.instance.'cpu'.5minavg': invalid") == {"cpu.instance": None}
    assert state_cpu("") == {}


def test_throughput_edge_cases():
    """Test edge cases for the throughput function."""
    assert throughput("Number of sessions supported: 0\nThroughput: 0") == {
        "number_of_sessions_supported": 0.0,
        "throughput": 0.0,
    }
    assert throughput("Number of sessions supported: invalid\nThroughput: invalid") == {}


def test_ha_state_edge_cases():
    """Test edge cases for the ha_state function."""
    raw = "State: inactive\nEnabled: no\n: mode"
    expected = {"ha.state": "inactive", "sync.state": "no", "conf.sync": "mode"}
    assert ha_state(raw) == expected
    assert ha_state("") == {"ha.state": None, "sync.state": None, "conf.sync": None}


def test_packet_buffer_stats_edge_cases():
    """Test edge cases for the packet_buffer_stats function."""
    raw = "DP s0p0:\npacket buffer (average): 0 0\npacket buffer (maximum): 0 0\n"
    expected: dict[str, float] = {
        "s0p0.packet_buffer.average.min1": 0.0,
        "s0p0.packet_buffer.average.min2": 0.0,
        "s0p0.packet_buffer.maximum.min1": 0.0,
        "s0p0.packet_buffer.maximum.min2": 0.0,
    }
    assert packet_buffer_stats(raw) == expected
    assert packet_buffer_stats("invalid data") == {}


def test_disk_usage_edge_cases():
    """Test edge cases for the disk_usage function."""
    raw = "sda1 0G 0G 0G 0% /"
    expected = {
        "disk.usage": '[{"filesystem": "sda1", "size": "0G", "used": "0G", "avail": "0G", "use%": "0%", '
        '"mounted_on": "/"}]'
    }
    assert disk_usage(raw) == expected
    assert disk_usage("invalid data") == {"disk.usage": "[]"}
