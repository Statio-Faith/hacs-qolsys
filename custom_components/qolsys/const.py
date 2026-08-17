DOMAIN = "qolsys"
PLATFORMS = ["alarm_control_panel", "binary_sensor"]

# Config entry keys
CONF_PANEL_HOST = "panel_host"
CONF_PANEL_PORT = "panel_port"
CONF_PANEL_TOKEN = "panel_token"
CONF_PANEL_USER_CODE = "panel_user_code"
CONF_HA_USER_CODE = "ha_user_code"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_DISARM_REQUIRED = "code_disarm_required"
CONF_CODE_TRIGGER_REQUIRED = "code_trigger_required"
CONF_ARM_AWAY_EXIT_DELAY = "arm_away_exit_delay"
CONF_ARM_STAY_EXIT_DELAY = "arm_stay_exit_delay"
CONF_ARM_AWAY_BYPASS = "arm_away_bypass"
CONF_ARM_STAY_BYPASS = "arm_stay_bypass"
CONF_DEFAULT_TRIGGER_COMMAND = "default_trigger_command"
CONF_DEFAULT_SENSOR_DEVICE_CLASS = "default_sensor_device_class"
CONF_ENABLE_STATIC_SENSORS = "enable_static_sensors_by_default"
CONF_PANEL_UNIQUE_ID = "panel_unique_id"
CONF_PANEL_DEVICE_NAME = "panel_device_name"
CONF_ARM_TYPE_CUSTOM_BYPASS = "arm_type_custom_bypass"

# Defaults
DEFAULT_PORT = 12345
DEFAULT_PANEL_UNIQUE_ID = "qolsys_panel"
DEFAULT_PANEL_DEVICE_NAME = "Qolsys Panel"
DEFAULT_SENSOR_DEVICE_CLASS = "safety"
DEFAULT_ARM_TYPE_CUSTOM_BYPASS = "arm_away"

# Dispatcher signal format strings — call .format(entry_id=...) etc. before use
SIGNAL_PANEL_STATE_UPDATE = "qolsys_panel_state_{entry_id}"
SIGNAL_PARTITION_UPDATE = "qolsys_partition_{entry_id}_{partition_id}"
SIGNAL_SENSOR_UPDATE = "qolsys_sensor_{entry_id}_{zone_id}"
