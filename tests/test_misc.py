"""Unit tests for miscellaneous helper functions."""

import csv
import tempfile
from ipaddress import IPv4Address
from pathlib import Path

import pytest

from helper.misc import load_devices_creds
from models.main import Devices


class TestLoadDevicesCreds:
    """Test suite for load_devices_creds function."""

    @pytest.fixture
    def temp_csv_file(self):
        """Create a temporary CSV file with valid device credentials."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "device_type",
                    "ip",
                    "username",
                    "password",
                    "hostname",
                    "monitored",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "device_type": "router",
                    "ip": "192.168.1.1",
                    "username": "admin",
                    "password": "secure_pass",
                    "hostname": "Router1",
                    "monitored": "true",
                }
            )
            writer.writerow(
                {
                    "device_type": "switch",
                    "ip": "192.168.1.2",
                    "username": "user",
                    "password": "pass123",
                    "hostname": "Switch1",
                    "monitored": "false",
                }
            )
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    @pytest.fixture
    def temp_csv_with_missing_optional(self):
        """Create a temporary CSV file with missing optional fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "device_type",
                    "ip",
                    "username",
                    "password",
                    "hostname",
                    "monitored",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "device_type": "firewall",
                    "ip": "10.0.0.1",
                    "username": "fwadmin",
                    "password": "fwpass",
                    "hostname": "",
                    "monitored": "true",
                }
            )
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    def test_load_devices_creds_valid_file(self, temp_csv_file):
        """Test loading valid device credentials from CSV file."""
        devices = load_devices_creds(temp_csv_file)

        assert len(devices) == 2
        assert isinstance(devices[0], Devices)
        assert isinstance(devices[1], Devices)

    def test_load_devices_creds_first_device(self, temp_csv_file):
        """Test first device data is correctly loaded."""
        devices = load_devices_creds(temp_csv_file)

        device = devices[0]
        assert device.device_type == "router"
        assert device.ip == IPv4Address("192.168.1.1")
        assert device.username == "admin"
        assert device.password == "secure_pass"
        assert device.hostname == "Router1"
        assert device.monitored is True

    def test_load_devices_creds_second_device(self, temp_csv_file):
        """Test second device data is correctly loaded."""
        devices = load_devices_creds(temp_csv_file)

        device = devices[1]
        assert device.device_type == "switch"
        assert device.ip == IPv4Address("192.168.1.2")
        assert device.username == "user"
        assert device.password == "pass123"
        assert device.hostname == "Switch1"
        assert device.monitored is False

    def test_load_devices_creds_monitored_true(self, temp_csv_file):
        """Test monitored field parsing for 'true' value."""
        devices = load_devices_creds(temp_csv_file)
        assert devices[0].monitored is True

    def test_load_devices_creds_monitored_false(self, temp_csv_file):
        """Test monitored field parsing for 'false' value."""
        devices = load_devices_creds(temp_csv_file)
        assert devices[1].monitored is False

    def test_load_devices_creds_file_not_found(self):
        """Test FileNotFoundError is raised for non-existent file."""
        non_existent_path = Path("/tmp/non_existent_file_12345.csv")
        with pytest.raises(FileNotFoundError, match="File not found"):
            load_devices_creds(non_existent_path)

    def test_load_devices_creds_missing_hostname(self, temp_csv_with_missing_optional):
        """Test loading device with empty hostname field."""
        devices = load_devices_creds(temp_csv_with_missing_optional)

        assert len(devices) == 1
        device = devices[0]
        assert device.device_type == "firewall"
        assert device.ip == IPv4Address("10.0.0.1")
        # Empty string from CSV becomes empty string, not None (as per csv.DictReader behavior)
        assert device.hostname == ""

    def test_load_devices_creds_empty_file(self):
        """Test loading an empty CSV file with only headers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "device_type",
                    "ip",
                    "username",
                    "password",
                    "hostname",
                    "monitored",
                ],
            )
            writer.writeheader()
            temp_path = Path(f.name)

        try:
            devices = load_devices_creds(temp_path)
            assert len(devices) == 0
        finally:
            temp_path.unlink()

    def test_load_devices_creds_monitored_case_insensitive(self):
        """Test monitored field parsing is case-insensitive."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "device_type",
                    "ip",
                    "username",
                    "password",
                    "hostname",
                    "monitored",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "device_type": "router",
                    "ip": "192.168.1.1",
                    "username": "admin",
                    "password": "pass",
                    "hostname": "Router1",
                    "monitored": "TRUE",
                }
            )
            writer.writerow(
                {
                    "device_type": "switch",
                    "ip": "192.168.1.2",
                    "username": "user",
                    "password": "pass",
                    "hostname": "Switch1",
                    "monitored": "False",
                }
            )
            temp_path = Path(f.name)

        try:
            devices = load_devices_creds(temp_path)
            assert devices[0].monitored is True
            assert devices[1].monitored is False
        finally:
            temp_path.unlink()

    def test_load_devices_creds_returns_list(self, temp_csv_file):
        """Test that the function returns a list."""
        result = load_devices_creds(temp_csv_file)
        assert isinstance(result, list)

    def test_load_devices_creds_all_devices_are_devices_instances(self, temp_csv_file):
        """Test all loaded items are Devices model instances."""
        devices = load_devices_creds(temp_csv_file)
        assert all(isinstance(device, Devices) for device in devices)

    @pytest.fixture
    def temp_csv_with_broken_ip(self):
        """Create a temporary CSV file with invalid IP address."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "device_type",
                    "ip",
                    "username",
                    "password",
                    "hostname",
                    "monitored",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "device_type": "router",
                    "ip": "999.999.999.999",  # Invalid IP
                    "username": "admin",
                    "password": "pass",
                    "hostname": "Router1",
                    "monitored": "true",
                }
            )
            writer.writerow(
                {
                    "device_type": "switch",
                    "ip": "10.1.1.22",
                    "username": "user",
                    "password": "pass",
                    "hostname": "Switch1",
                    "monitored": "false",
                }
            )
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    def test_load_devices_creds_skips_invalid_ip_continues_processing(self, temp_csv_with_broken_ip: Path):
        """Test that invalid IP entries are skipped and valid entries are still loaded."""
        devices = load_devices_creds(temp_csv_with_broken_ip)
        # Only the valid entry should be loaded
        assert len(devices) == 1
        assert devices[0].ip == IPv4Address("10.1.1.22")
