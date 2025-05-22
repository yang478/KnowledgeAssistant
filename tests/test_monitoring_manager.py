"""Unit tests for the MonitoringManager class."""

import unittest
from unittest.mock import patch, MagicMock
import datetime
import logging # <-- Added import

# Ensure the monitoring_manager module can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from monitoring_manager.monitoring_manager import MonitoringManager
# Assuming ConfigManager is needed for initialization, even if not directly used by log method in current simple version
from config_manager.config_manager import ConfigManager


class TestMonitoringManager(unittest.TestCase):
    """Tests for the MonitoringManager."""

    def setUp(self):
        """Set up a MonitoringManager instance with a mock ConfigManager."""
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        # Simulate get_config for potential future use (e.g., log_level from config)
        self.mock_config_manager.get_config.return_value = "DEBUG" # Default to DEBUG for testing
        self.monitoring_manager = MonitoringManager(config_manager=self.mock_config_manager)

    # Remove @patch('builtins.print') - We should assert logger calls, not print
    @patch('datetime.datetime')
    def test_log_info_with_details(self, mock_datetime): # Removed mock_print
        """Test logging an INFO message with details."""
        # Arrange
        mock_now = datetime.datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        iso_timestamp = mock_now.isoformat()

        level = "info"
        message = "This is an info message."
        details = {"module": "TestModule", "user_id": "test_user"}
        expected_log_output = f"[{iso_timestamp}] [INFO] {message} | Details: {details}"

        # Act
        # Assert logger call
        with patch.object(self.monitoring_manager.logger, 'log') as mock_logger_log:
            self.monitoring_manager.log_info(message, context=details)
            mock_logger_log.assert_called_once_with(logging.INFO, message, exc_info=None, extra={'context': details})

    # Remove @patch('builtins.print')
    @patch('datetime.datetime')
    def test_log_warning_no_details(self, mock_datetime): # Removed mock_print
        """Test logging a WARNING message without details."""
        # Arrange
        mock_now = datetime.datetime(2023, 1, 1, 12, 5, 0)
        mock_datetime.now.return_value = mock_now
        iso_timestamp = mock_now.isoformat()

        level = "warning"
        message = "This is a warning message."
        expected_log_output = f"[{iso_timestamp}] [WARNING] {message}" # No details part

        # Act
        # Assert logger call
        with patch.object(self.monitoring_manager.logger, 'log') as mock_logger_log:
            self.monitoring_manager.log_warning(message) # details=None by default
            mock_logger_log.assert_called_once_with(logging.WARNING, message, exc_info=None)

    # Remove @patch('builtins.print')
    @patch('datetime.datetime')
    def test_log_error_with_empty_details(self, mock_datetime): # Removed mock_print
        """Test logging an ERROR message with empty details."""
        # Arrange
        mock_now = datetime.datetime(2023, 1, 1, 12, 10, 0)
        mock_datetime.now.return_value = mock_now
        iso_timestamp = mock_now.isoformat()
        
        level = "error"
        message = "This is an error message."
        details = {} # Empty details
        expected_log_output = f"[{iso_timestamp}] [ERROR] {message} | Details: {{}}"

        # Act
        # Assert logger call
        with patch.object(self.monitoring_manager.logger, 'log') as mock_logger_log:
            self.monitoring_manager.log_error(message, context=details)
            # When context is an empty dict, _log calls logger.log without the 'extra' argument.
            mock_logger_log.assert_called_once_with(logging.ERROR, message, exc_info=None)

    # Remove @patch('builtins.print')
    @patch('datetime.datetime')
    def test_log_debug_message(self, mock_datetime): # Removed mock_print
        """Test logging a DEBUG message."""
        # Arrange
        mock_now = datetime.datetime(2023, 1, 1, 12, 15, 0)
        mock_datetime.now.return_value = mock_now
        iso_timestamp = mock_now.isoformat()

        level = "debug"
        message = "This is a debug message."
        details = {"code_line": 42}
        expected_log_output = f"[{iso_timestamp}] [DEBUG] {message} | Details: {details}"

        # Act
        # Assert logger call
        with patch.object(self.monitoring_manager.logger, 'log') as mock_logger_log:
            self.monitoring_manager.log_debug(message, context=details)
            mock_logger_log.assert_called_once_with(logging.DEBUG, message, exc_info=None, extra={'context': details})
        
    # Remove @patch('builtins.print')
    @patch('datetime.datetime')
    def test_log_unknown_level_defaults_to_info_style_log(self, mock_datetime): # Removed mock_print
        """Test logging with an unknown level (should still log, perhaps as INFO or with level as is)."""
        # Current implementation converts level to uppercase.
        # Arrange
        mock_now = datetime.datetime(2023, 1, 1, 12, 20, 0)
        mock_datetime.now.return_value = mock_now
        iso_timestamp = mock_now.isoformat()

        level_int = logging.CRITICAL # An example of a level not explicitly handled but valid
        message = "This is a critical message."
        # The StructuredJsonFormatter uses record.levelname, which will be "CRITICAL"
        # if the level_int is logging.CRITICAL.
        expected_log_output = f"[{iso_timestamp}] [CRITICAL] {message}"

        # Act
        # Assert logger call
        with patch.object(self.monitoring_manager.logger, 'log') as mock_logger_log:
            self.monitoring_manager._log(level_int, message)
            mock_logger_log.assert_called_once_with(level_int, message, exc_info=None)

    # Placeholder for future test if log filtering based on config is implemented
    # def test_log_obeys_config_log_level(self):
    #     # This test would require MonitoringManager to actually use the log_level from config
    #     # For example, if config_level is INFO, DEBUG messages should not be printed.
    #     self.mock_config_manager.get_config.return_value = "INFO"
    #     # Re-initialize or set level on monitoring_manager if it supports dynamic level changes
    #     self.monitoring_manager_filtered = MonitoringManager(config_manager=self.mock_config_manager)
        
    #     with patch('builtins.print') as mock_print_filtered:
    #         self.monitoring_manager_filtered.log("debug", "This debug message should not appear.")
    #         mock_print_filtered.assert_not_called()
            
    #         self.monitoring_manager_filtered.log("info", "This info message should appear.")
    #         self.assertTrue(mock_print_filtered.called)
    #     pass


if __name__ == '__main__':
    unittest.main()
