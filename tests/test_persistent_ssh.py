"""Unit tests for persistent_ssh module."""

import tempfile
import threading
import time
from ipaddress import IPv4Address
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from helper.misc import load_devices_creds as load_devices_from_csv
from libs.persistent_ssh import RECONNECT_DELAY_SECONDS, PersistentSSHConnection, PersistentSSHService
from models.env import EnvironmentsVariables
from models.main import Devices


class TestPersistentSSHConnection:
    """Test suite for PersistentSSHConnection class."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock device for testing."""
        return Devices(
            device_type="paloalto_panos",
            ip=IPv4Address("192.168.1.1"),
            username="admin",
            password="password",
            hostname="test-device",
            monitored=True,
        )

    @pytest.fixture
    def mock_env_vars(self):
        """Create mock environment variables."""
        env = MagicMock(spec=EnvironmentsVariables)
        env.file_paths = MagicMock()
        env.file_paths.sshd_config = Path("/tmp/sshd_config")
        env.conn = MagicMock()
        env.conn.conn_timeout = 30
        env.conn.read_timeout_override = 60
        return env

    def test_init(self, mock_device, mock_env_vars):
        """Test PersistentSSHConnection initialization."""
        conn = PersistentSSHConnection(mock_device, mock_env_vars)

        assert conn.device == mock_device
        assert conn.env_vars == mock_env_vars
        assert conn.connection is None
        assert conn._connected is False
        assert conn.lock is not None  # Just check lock exists

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_connect_success(self, mock_handler, mock_device, mock_env_vars):
        """Test successful connection."""
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "hostname: test-device"
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()

        assert conn._connected is True
        assert conn.connection is not None
        mock_handler.assert_called_once()

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_connect_failure(self, mock_handler, mock_device, mock_env_vars):
        """Test connection failure."""
        mock_handler.side_effect = Exception("Connection failed")

        conn = PersistentSSHConnection(mock_device, mock_env_vars)

        with pytest.raises(Exception, match="Connection failed"):
            conn.connect()

        assert conn._connected is False

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_connect_sets_hostname(self, mock_handler, mock_env_vars):
        """Test connection sets hostname if not already set."""
        device = Devices(
            device_type="paloalto_panos",
            ip=IPv4Address("192.168.1.1"),
            username="admin",
            password="password",
            hostname=None,
            monitored=False,
        )

        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "hostname: new-hostname"
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(device, mock_env_vars)
        conn.connect()

        assert device.hostname == "new-hostname"

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_disconnect(self, mock_handler, mock_device, mock_env_vars):
        """Test disconnecting from device."""
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "hostname: test-device"
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()
        conn.disconnect()

        assert conn._connected is False
        assert conn.connection is None
        mock_connection.disconnect.assert_called_once()

    def test_disconnect_when_not_connected(self, mock_device, mock_env_vars):
        """Test disconnect when not connected."""
        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        # Should not raise an error
        conn.disconnect()

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_is_alive_when_connected(self, mock_handler, mock_device, mock_env_vars):
        """Test is_alive when connection is active."""
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "hostname: test-device"
        mock_connection.is_alive.return_value = True
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()

        assert conn.is_alive() is True

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_is_alive_fallback(self, mock_handler, mock_device, mock_env_vars):
        """Test is_alive fallback when is_alive method not available."""
        mock_connection = MagicMock()
        # First call for connect, second for is_alive check
        mock_connection.send_command.side_effect = ["hostname: test-device", ""]
        # Remove is_alive attribute to test fallback
        del mock_connection.is_alive
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()

        # Should use fallback method
        result = conn.is_alive()
        assert result is True

    def test_is_alive_when_not_connected(self, mock_device, mock_env_vars):
        """Test is_alive when not connected."""
        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        assert conn.is_alive() is False

    @patch("libs.persistent_ssh.ConnectHandler")
    @patch("time.sleep")
    def test_reconnect(self, mock_sleep, mock_handler, mock_device, mock_env_vars):
        """Test reconnection logic."""
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "hostname: test-device"
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()
        conn.reconnect()

        # Verify disconnect was called
        mock_connection.disconnect.assert_called()
        # Verify sleep was called with correct delay
        mock_sleep.assert_called_once_with(RECONNECT_DELAY_SECONDS)
        # Verify reconnection occurred
        assert conn._connected is True

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_execute_commands_success(self, mock_handler, mock_device, mock_env_vars):
        """Test executing commands successfully."""
        mock_connection = MagicMock()
        # Mock returns hostname during connect, then command results
        mock_connection.send_command.side_effect = ["hostname: test-device", "CPU: 50%", "Memory: 60%"]
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()

        commands = [
            ("show cpu", None),
            ("show memory", None),
        ]

        result = conn.execute_commands_compatibility(commands)

        assert "show cpu" in result
        assert "show memory" in result
        assert "CPU: 50%" in result
        assert "Memory: 60%" in result

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_execute_commands_with_processor(self, mock_handler, mock_device, mock_env_vars):
        """Test executing commands with processor function."""
        mock_connection = MagicMock()
        # Since mock_device has hostname, connect won't call send_command
        mock_connection.send_command.return_value = "line1\nline2\nline3"
        mock_handler.return_value = mock_connection

        def processor(output):
            return output.upper()

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()

        commands = [("show info", processor)]
        result = conn.execute_commands_compatibility(commands)

        assert "LINE1\nLINE2\nLINE3" in result

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_execute_commands_failure(self, mock_handler, mock_device, mock_env_vars):
        """Test executing commands with failure."""
        mock_connection = MagicMock()
        # Return hostname during connect, then raise exception for command execution
        mock_connection.send_command.side_effect = ["hostname: test-device", Exception("Command failed")]
        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_device, mock_env_vars)
        conn.connect()

        commands = [("show error", None)]
        result = conn.execute_commands_compatibility(commands)

        assert "ERROR" in result
        assert "Command failed" in result

    def test_execute_commands_not_connected(self, mock_device, mock_env_vars):
        """Test executing commands when not connected."""
        conn = PersistentSSHConnection(mock_device, mock_env_vars)

        commands = [("show test", None)]

        with pytest.raises(ConnectionError):
            conn.execute_commands_compatibility(commands)


class TestPersistentSSHService:
    """Test suite for PersistentSSHService class."""

    @pytest.fixture
    def mock_devices(self):
        """Create mock devices for testing."""
        return [
            Devices(
                device_type="paloalto_panos",
                ip=IPv4Address("192.168.1.1"),
                username="admin",
                password="password",
                hostname="device1",
                monitored=True,
            ),
            Devices(
                device_type="paloalto_panos",
                ip=IPv4Address("192.168.1.2"),
                username="admin",
                password="password",
                hostname="device2",
                monitored=False,
            ),
        ]

    @pytest.fixture
    def mock_env_vars(self):
        """Create mock environment variables."""
        env = MagicMock(spec=EnvironmentsVariables)
        env.file_paths = MagicMock()
        env.file_paths.sshd_config = Path("/tmp/sshd_config")
        env.file_paths.output_dir = Path("/tmp/output")
        env.conn = MagicMock()
        env.conn.conn_timeout = 30
        env.conn.read_timeout_override = 60
        env.conn.num_of_threads = 4  # ThreadPoolExecutor requires an actual integer value
        env.compatibility_mode = True  # Default to compatibility mode to avoid InfluxDB setup
        return env

    def test_init(self, mock_devices, mock_env_vars):
        """Test PersistentSSHService initialization."""
        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)

        assert service.devices == mock_devices
        assert service.env_vars == mock_env_vars
        assert service.interval == 60
        assert service.connections == {}

    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_initialize_connections(self, mock_conn_class, mock_devices, mock_env_vars):
        """Test initializing connections to all devices."""
        mock_conn = MagicMock()
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)
        service.initialize_connections()

        # Should create connections for all devices
        assert len(service.connections) == 2
        assert "192.168.1.1" in service.connections
        assert "192.168.1.2" in service.connections

    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_initialize_connections_with_failures(self, mock_conn_class, mock_devices, mock_env_vars):
        """Test initializing connections with some failures."""
        mock_conn = MagicMock()
        mock_conn.connect.side_effect = [Exception("Failed"), None]
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)
        service.initialize_connections()

        # Only one connection should succeed
        assert len(service.connections) == 1
        assert "192.168.1.2" in service.connections

    def test_cleanup_connections(self, mock_devices, mock_env_vars):
        """Test cleaning up all connections."""
        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)

        # Add mock connections
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        service.connections = {"192.168.1.1": mock_conn1, "192.168.1.2": mock_conn2}

        service.cleanup_connections()

        mock_conn1.disconnect.assert_called_once()
        mock_conn2.disconnect.assert_called_once()
        assert service.connections == {}

    def test_get_commands_for_device_monitored(self, mock_env_vars):
        """Test getting commands for monitored device."""
        device = Devices(
            device_type="paloalto_panos",
            ip=IPv4Address("192.168.1.1"),
            username="admin",
            password="password",
            hostname="device1",
            monitored=True,
        )

        service = PersistentSSHService([device], mock_env_vars, interval=60)
        commands = list(service.get_commands_for_device(device))

        # Monitored devices should have additional command
        assert len(commands) == 5
        # Verify resource monitoring command is included
        assert any("resource-monitor" in cmd[0] for cmd in commands)

    def test_get_commands_for_device_not_monitored(self, mock_env_vars):
        """Test getting commands for non-monitored device."""
        device = Devices(
            device_type="paloalto_panos",
            ip=IPv4Address("192.168.1.1"),
            username="admin",
            password="password",
            hostname="device1",
            monitored=False,
        )

        service = PersistentSSHService([device], mock_env_vars, interval=60)
        commands = list(service.get_commands_for_device(device))

        # Non-monitored devices should have fewer commands
        assert len(commands) == 4
        # Verify resource monitoring command is NOT included
        assert not any("resource-monitor" in cmd[0] for cmd in commands)

    @patch("libs.persistent_ssh.PersistentSSHConnection")
    @patch("builtins.open")
    def test_run_monitoring_cycle(self, mock_open, mock_conn_class, mock_devices, mock_env_vars):
        """Test running one monitoring cycle."""
        mock_conn = MagicMock()
        mock_conn.is_alive.return_value = True
        mock_conn.execute_commands_compatibility.return_value = "Test output"
        mock_conn.device = mock_devices[0]

        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)
        service.connections = {"192.168.1.1": mock_conn}

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        service.run_monitoring_cycle()

        mock_conn.is_alive.assert_called_once()
        mock_conn.execute_commands_compatibility.assert_called_once()
        mock_file.write.assert_called()

    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_run_monitoring_cycle_with_reconnect(self, mock_conn_class, mock_devices, mock_env_vars):
        """Test monitoring cycle with reconnection."""
        mock_conn = MagicMock()
        mock_conn.is_alive.return_value = False
        mock_conn.execute_commands_compatibility.return_value = "Test output"
        mock_conn.device = mock_devices[0]

        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)
        service.connections = {"192.168.1.1": mock_conn}

        with patch("builtins.open"):
            service.run_monitoring_cycle()

        # Should attempt to reconnect
        mock_conn.reconnect.assert_called_once()

    @patch("helper.misc.load_devices_creds")
    @patch("models.env.EnvironmentsVariables")
    @patch("pathlib.Path.exists")
    def test_reload_config(self, mock_path_exists, mock_env_class, mock_load_creds, mock_devices, mock_env_vars):
        """Test reloading configuration."""
        # Setup initial service
        service = PersistentSSHService(mock_devices[:1], mock_env_vars, interval=60)

        # Add mock connection
        mock_conn = MagicMock()
        service.connections = {"192.168.1.1": mock_conn}

        # Setup mocks for reload
        new_device = Devices(
            device_type="paloalto_panos",
            ip=IPv4Address("192.168.1.3"),
            username="admin",
            password="password",
            hostname="device3",
            monitored=False,
        )
        mock_load_creds.return_value = [mock_devices[0], new_device]
        mock_env_class.return_value = mock_env_vars
        mock_path_exists.return_value = False  # Simpler: assume .env doesn't exist

        # Reload configuration
        service.reload_config()

        # Verify devices were reloaded
        mock_load_creds.assert_called_once()

        # Verify devices list was updated
        assert len(service.devices) == 2

    @patch("helper.misc.load_devices_creds")
    @patch("models.env.EnvironmentsVariables")
    @patch("pathlib.Path.exists")
    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_reload_config_adds_new_device(
        self, mock_conn_class, mock_path_exists, mock_env_class, mock_load_creds, mock_devices, mock_env_vars
    ):
        """Test reload adds new devices and connects to them."""
        # Setup initial service with one device
        service = PersistentSSHService([mock_devices[0]], mock_env_vars, interval=60)
        service.connections = {}

        # Setup mocks - add a new device
        new_device = Devices(
            device_type="paloalto_panos",
            ip=IPv4Address("192.168.1.3"),
            username="admin",
            password="password",
            hostname="device3",
            monitored=False,
        )
        mock_load_creds.return_value = [mock_devices[0], new_device]
        mock_env_class.return_value = mock_env_vars
        mock_path_exists.return_value = False

        # Create mock connection
        mock_new_conn = MagicMock()
        mock_conn_class.return_value = mock_new_conn

        # Reload configuration
        service.reload_config()

        # Verify new connection was created
        assert mock_conn_class.call_count >= 1
        mock_new_conn.connect.assert_called()

    @patch("helper.misc.load_devices_creds")
    @patch("models.env.EnvironmentsVariables")
    @patch("pathlib.Path.exists")
    def test_reload_config_removes_old_device(
        self, mock_path_exists, mock_env_class, mock_load_creds, mock_devices, mock_env_vars
    ):
        """Test reload removes devices that are no longer in CSV."""
        # Setup initial service with two devices
        service = PersistentSSHService(mock_devices, mock_env_vars, interval=60)

        # Add mock connections for both devices
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        service.connections = {"192.168.1.1": mock_conn1, "192.168.1.2": mock_conn2}

        # Setup mocks - only return first device
        mock_load_creds.return_value = [mock_devices[0]]
        mock_env_class.return_value = mock_env_vars
        mock_path_exists.return_value = False

        # Reload configuration
        service.reload_config()

        # Verify second device was disconnected
        mock_conn2.disconnect.assert_called_once()

        # Verify only one connection remains
        assert len(service.connections) == 1
        assert "192.168.1.1" in service.connections
        assert "192.168.1.2" not in service.connections


class TestLoadDevicesFromCSV:
    """Test suite for load_devices_from_csv function."""

    def test_load_devices_success(self):
        """Test loading devices from CSV successfully."""
        csv_content = """device_type,ip,username,password,hostname,monitored
paloalto_panos,192.168.1.1,admin,pass123,device1,true
paloalto_panos,192.168.1.2,admin,pass456,device2,false
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        try:
            devices = load_devices_from_csv(csv_path)

            assert len(devices) == 2
            assert devices[0].hostname == "device1"
            assert devices[0].monitored is True
            assert devices[1].hostname == "device2"
            assert devices[1].monitored is False
        finally:
            csv_path.unlink()

    def test_load_devices_empty_file(self):
        """Test loading from empty CSV."""
        csv_content = "device_type,ip,username,password,hostname,monitored\n"

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        try:
            devices = load_devices_from_csv(csv_path)
            assert len(devices) == 0
        finally:
            csv_path.unlink()

    def test_load_devices_with_missing_fields(self):
        """Test loading devices with optional fields missing.

        Note: CSV empty fields become empty strings, not None.
        """
        csv_content = """device_type,ip,username,password,hostname,monitored
paloalto_panos,192.168.1.1,admin,pass123,,
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        try:
            devices = load_devices_from_csv(csv_path)

            assert len(devices) == 1
            # Empty CSV field becomes empty string
            assert devices[0].hostname == ""
            assert devices[0].monitored is False  # Default value
        finally:
            csv_path.unlink()


class TestThreadSafetyAndConcurrency:
    """Test suite for thread-safe concurrent operations."""

    @pytest.fixture
    def mock_devices(self):
        """Create multiple mock devices for concurrency testing."""
        return [
            Devices(
                device_type="paloalto_panos",
                ip=IPv4Address(f"192.168.1.{i}"),
                username="admin",
                password="password",
                hostname=f"device{i}",
                monitored=True,
            )
            for i in range(1, 11)  # 10 devices
        ]

    @pytest.fixture
    def mock_env_vars_with_influxdb(self):
        """Create mock environment variables with InfluxDB configuration."""
        env = MagicMock(spec=EnvironmentsVariables)
        env.file_paths = MagicMock()
        env.file_paths.sshd_config = Path("/tmp/sshd_config")
        env.file_paths.output_dir = Path("/tmp/output")
        env.conn = MagicMock()
        env.conn.conn_timeout = 30
        env.conn.read_timeout_override = 60
        env.conn.num_of_threads = 10
        env.compatibility_mode = False
        env.influxdb = MagicMock()
        env.influxdb.url = "http://localhost:8086"
        env.influxdb.token = "test-token"
        env.influxdb.org = "test-org"
        env.influxdb.bucket = "test-bucket"
        env.influxdb.connection_pool_maxsize = 10
        env.influxdb.batch_size = 500
        env.influxdb.flush_interval_ms = 10000
        env.influxdb.max_retries = 2
        env.influxdb.timeout_ms = 30000
        env.influxdb.conn_params.return_value = {
            "url": "http://localhost:8086",
            "token": "test-token",
            "org": "test-org",
            "timeout": 30000,
            "enable_gzip": True,
            "connection_pool_maxsize": 10,
        }
        return env

    @pytest.fixture
    def mock_env_vars_compatibility(self):
        """Create mock environment variables for compatibility mode."""
        env = MagicMock(spec=EnvironmentsVariables)
        env.file_paths = MagicMock()
        env.file_paths.sshd_config = Path("/tmp/sshd_config")
        env.file_paths.output_dir = Path("/tmp/output")
        env.conn = MagicMock()
        env.conn.conn_timeout = 30
        env.conn.read_timeout_override = 60
        env.conn.num_of_threads = 10
        env.compatibility_mode = True
        return env

    @patch("libs.persistent_ssh.InfluxDBClient")
    def test_influxdb_client_initialization(self, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb):
        """Test InfluxDB client is initialized with correct parameters."""
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        service = PersistentSSHService(mock_devices, mock_env_vars_with_influxdb, interval=60)

        # Verify InfluxDB client was initialized
        assert service.influxdb_client is not None
        assert service.write_api is not None
        mock_influxdb_client.assert_called_once()

        # Verify connection parameters
        call_kwargs = mock_influxdb_client.call_args[1]
        assert call_kwargs["url"] == "http://localhost:8086"
        assert call_kwargs["token"] == "test-token"
        assert call_kwargs["org"] == "test-org"
        assert call_kwargs["connection_pool_maxsize"] == 10

    @patch("libs.persistent_ssh.InfluxDBClient")
    def test_influxdb_write_options_configuration(
        self, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test write API is configured with proper batching options."""
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        _ = PersistentSSHService(mock_devices, mock_env_vars_with_influxdb, interval=60)

        # Verify write_api was called with WriteOptions
        mock_client.write_api.assert_called_once()
        write_options = mock_client.write_api.call_args[1]["write_options"]

        # Verify WriteOptions configuration
        assert write_options.batch_size == 500
        assert write_options.flush_interval == 10000
        assert write_options.max_retries == 2

    def test_service_has_write_locks(self, mock_devices, mock_env_vars_with_influxdb):
        """Test service initializes thread locks for concurrent writes."""
        with patch("libs.persistent_ssh.InfluxDBClient"):
            service = PersistentSSHService(mock_devices, mock_env_vars_with_influxdb, interval=60)

            # Verify locks exist
            assert hasattr(service, "_write_lock")
            assert hasattr(service, "_file_write_lock")
            assert hasattr(service, "_reload_lock")
            # Check locks have acquire/release methods (duck typing)
            assert callable(getattr(service._write_lock, "acquire", None))
            assert callable(getattr(service._write_lock, "release", None))
            assert callable(getattr(service._file_write_lock, "acquire", None))
            assert callable(getattr(service._file_write_lock, "release", None))
            assert callable(getattr(service._reload_lock, "acquire", None))
            assert callable(getattr(service._reload_lock, "release", None))

    @patch("libs.persistent_ssh.InfluxDBClient")
    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_concurrent_influxdb_writes_use_lock(
        self, mock_conn_class, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test concurrent InfluxDB writes are serialized with lock."""
        # Setup mocks
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        mock_conn = MagicMock()
        mock_conn.is_alive.return_value = True
        mock_conn.execute_commands.return_value = {"cpu": 50.0, "memory": 60.0}
        mock_conn.device.hostname = "test-device"
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices[:3], mock_env_vars_with_influxdb, interval=60)
        service.connections = {
            "192.168.1.1": mock_conn,
            "192.168.1.2": mock_conn,
            "192.168.1.3": mock_conn,
        }

        # Use a custom lock to track acquisitions
        original_lock = service._write_lock
        tracked_lock = MagicMock(wraps=original_lock)
        service._write_lock = tracked_lock

        # Run monitoring cycle with multiple devices
        service.run_monitoring_cycle()

        # Verify lock was used (both __enter__ and __exit__ for context manager)
        assert tracked_lock.__enter__.call_count == 3
        assert tracked_lock.__exit__.call_count == 3

    @patch("builtins.open", create=True)
    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_concurrent_file_writes_use_lock(
        self, mock_conn_class, mock_open, mock_devices, mock_env_vars_compatibility
    ):
        """Test concurrent file writes in compatibility mode are serialized with lock."""
        mock_conn = MagicMock()
        mock_conn.is_alive.return_value = True
        mock_conn.execute_commands_compatibility.return_value = "Test output"
        mock_conn.device.hostname = "test-device"
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices[:3], mock_env_vars_compatibility, interval=60)
        service.connections = {
            "192.168.1.1": mock_conn,
            "192.168.1.2": mock_conn,
            "192.168.1.3": mock_conn,
        }

        # Use a custom lock to track acquisitions
        original_lock = service._file_write_lock
        tracked_lock = MagicMock(wraps=original_lock)
        service._file_write_lock = tracked_lock

        # Mock file handle
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Run monitoring cycle
        service.run_monitoring_cycle()

        # Verify lock was used (both __enter__ and __exit__ for context manager)
        assert tracked_lock.__enter__.call_count == 3
        assert tracked_lock.__exit__.call_count == 3

    @patch("libs.persistent_ssh.InfluxDBClient")
    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_multiple_devices_processed_concurrently(
        self, mock_conn_class, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test multiple devices are processed in parallel."""
        # Setup mocks
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        # Track which devices are being processed and when
        processing_times = {}
        processing_lock = threading.Lock()

        def create_mock_conn(device):
            mock_conn = MagicMock()
            mock_conn.is_alive.return_value = True
            mock_conn.device = device

            def execute_commands(*args):
                with processing_lock:
                    processing_times[str(device.ip)] = time.time()
                # Simulate some work
                time.sleep(0.1)
                return {"cpu": 50.0}

            mock_conn.execute_commands = execute_commands
            return mock_conn

        service = PersistentSSHService(mock_devices[:5], mock_env_vars_with_influxdb, interval=60)
        service.connections = {str(device.ip): create_mock_conn(device) for device in mock_devices[:5]}

        start_time = time.time()
        service.run_monitoring_cycle()
        end_time = time.time()

        # If processed serially, would take 5 * 0.1 = 0.5s
        # If processed in parallel, should take ~0.1s (plus overhead)
        # We allow generous margin for CI/slow machines
        assert (
            end_time - start_time < 0.5
        ), f"Devices should be processed concurrently (took {end_time - start_time:.2f}s)"

        # Verify all devices were processed
        assert len(processing_times) == 5

    @patch("libs.persistent_ssh.InfluxDBClient")
    def test_cleanup_flushes_pending_writes(self, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb):
        """Test cleanup properly flushes pending writes before closing."""
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        service = PersistentSSHService(mock_devices, mock_env_vars_with_influxdb, interval=60)

        # Cleanup connections
        with patch("time.sleep"):  # Speed up test
            service.cleanup_connections()

        # Verify flush was called before close
        mock_write_api.flush.assert_called_once()
        mock_write_api.close.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("libs.persistent_ssh.InfluxDBClient")
    def test_cleanup_handles_flush_errors_gracefully(
        self, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test cleanup continues even if flush fails."""
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_write_api.flush.side_effect = Exception("Flush failed")
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        service = PersistentSSHService(mock_devices, mock_env_vars_with_influxdb, interval=60)

        # Should not raise exception
        with patch("time.sleep"):
            service.cleanup_connections()

        # Verify close was still attempted
        mock_client.close.assert_called_once()
        assert service.influxdb_client is None
        assert service.write_api is None

    @patch("libs.persistent_ssh.InfluxDBClient")
    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_influxdb_write_error_does_not_stop_monitoring(
        self, mock_conn_class, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test InfluxDB write errors don't stop the monitoring cycle."""
        mock_client = MagicMock()
        mock_write_api = MagicMock()
        mock_write_api.write.side_effect = Exception("Write failed")
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        mock_conn = MagicMock()
        mock_conn.is_alive.return_value = True
        mock_conn.execute_commands.return_value = {"cpu": 50.0}
        mock_conn.device.hostname = "test-device"
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices[:2], mock_env_vars_with_influxdb, interval=60)
        service.connections = {"192.168.1.1": mock_conn, "192.168.1.2": mock_conn}

        # Should not raise exception
        service.run_monitoring_cycle()

        # Verify both devices were processed despite write errors
        assert mock_conn.execute_commands.call_count == 2

    @patch("libs.persistent_ssh.InfluxDBClient")
    def test_no_influxdb_client_in_compatibility_mode(
        self, mock_influxdb_client, mock_devices, mock_env_vars_compatibility
    ):
        """Test InfluxDB client is not initialized in compatibility mode."""
        service = PersistentSSHService(mock_devices, mock_env_vars_compatibility, interval=60)

        # Verify InfluxDB client was NOT initialized
        assert service.influxdb_client is None
        assert service.write_api is None
        mock_influxdb_client.assert_not_called()

    @patch("libs.persistent_ssh.InfluxDBClient")
    def test_influxdb_initialization_failure_handled_gracefully(
        self, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test service continues if InfluxDB client initialization fails."""
        mock_influxdb_client.side_effect = Exception("Connection failed")

        # Should not raise exception
        service = PersistentSSHService(mock_devices, mock_env_vars_with_influxdb, interval=60)

        # Service should still be created, but without InfluxDB client
        assert service.influxdb_client is None
        assert service.write_api is None

    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_ssh_connection_disconnect_with_resource_cleanup(
        self, mock_conn_class, mock_devices, mock_env_vars_compatibility
    ):
        """Test SSH connections are properly cleaned up with garbage collection."""
        mock_conn = MagicMock()
        mock_conn.disconnect = MagicMock()
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices[:3], mock_env_vars_compatibility, interval=60)
        service.connections = {
            "192.168.1.1": mock_conn,
            "192.168.1.2": mock_conn,
            "192.168.1.3": mock_conn,
        }

        # Cleanup
        with patch("gc.collect") as mock_gc:
            service.cleanup_connections()

        # Verify all connections were disconnected
        assert mock_conn.disconnect.call_count == 3
        # Verify garbage collection was called
        mock_gc.assert_called()

    @patch("libs.persistent_ssh.ConnectHandler")
    def test_ssh_disconnect_closes_all_channels(self, mock_handler, mock_devices, mock_env_vars_compatibility):
        """Test disconnect closes all SSH channels and connections."""
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "hostname: test-device"

        # Create mock remote connections
        mock_remote_conn = MagicMock()
        mock_remote_conn_pre = MagicMock()
        mock_connection.remote_conn = mock_remote_conn
        mock_connection.remote_conn_pre = mock_remote_conn_pre

        mock_handler.return_value = mock_connection

        conn = PersistentSSHConnection(mock_devices[0], mock_env_vars_compatibility)
        conn.connect()

        # Disconnect
        with patch("gc.collect"):
            conn.disconnect()

        # Verify all connections were closed
        mock_connection.disconnect.assert_called_once()
        mock_remote_conn.close.assert_called_once()
        mock_remote_conn_pre.close.assert_called_once()

    @patch("libs.persistent_ssh.InfluxDBClient")
    @patch("libs.persistent_ssh.PersistentSSHConnection")
    def test_write_lock_prevents_race_conditions(
        self, mock_conn_class, mock_influxdb_client, mock_devices, mock_env_vars_with_influxdb
    ):
        """Test write lock prevents data races during concurrent writes."""
        mock_client = MagicMock()
        mock_write_api = MagicMock()

        # Simulate slow write operation
        write_order = []
        lock = threading.Lock()

        def slow_write(*args, **kwargs):
            with lock:
                write_order.append("start")
            time.sleep(0.05)
            with lock:
                write_order.append("end")

        mock_write_api.write = slow_write
        mock_client.write_api.return_value = mock_write_api
        mock_influxdb_client.return_value = mock_client

        mock_conn = MagicMock()
        mock_conn.is_alive.return_value = True
        mock_conn.execute_commands.return_value = {"cpu": 50.0}
        mock_conn.device.hostname = "test-device"
        mock_conn_class.return_value = mock_conn

        service = PersistentSSHService(mock_devices[:3], mock_env_vars_with_influxdb, interval=60)
        service.connections = {
            "192.168.1.1": mock_conn,
            "192.168.1.2": mock_conn,
            "192.168.1.3": mock_conn,
        }

        service.run_monitoring_cycle()

        # Verify writes were serialized (each complete before next starts)
        # Pattern should be: start, end, start, end, start, end
        for i in range(0, len(write_order), 2):
            if i + 1 < len(write_order):
                assert write_order[i] == "start"
                assert write_order[i + 1] == "end"
