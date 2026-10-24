
# app/security/policies.py

# Permissions for the five supported ChronoShield domains.

ROLE_PERMISSIONS = {
    "parking_agent": {
        "parking": {"read", "update"},
    },
    "traffic_agent": {
        "traffic": {"read", "update", "change_signal"},
    },
    "water_agent": {
        "water": {"read", "update"},
    },
    "ev_charger_agent": {
        "ev_chargers": {"read", "update"},
    },
    "energy_grid_agent": {
        "energy_grid": {"read", "update","change_grid_settings",},
    },
    "admin": {
        "parking": {"read", "update"},
        "traffic": {"read", "update", "change_signal"},
        "water": {"read", "update"},
        "ev_chargers": {"read", "update"},
        "energy_grid": {"read", "update","change_grid_settings",},
    },
}

# Sensitive operations requiring human approval.
SENSITIVE_ACTIONS = {
    ("parking", "update"),
    ("traffic", "change_signal"),
    ("water", "update"),
    ("ev_chargers", "update"),
    ("energy_grid", "change_grid_settings"),
}

# The only supported domains.
VALID_DOMAINS = {
    "parking",
    "traffic",
    "water",
    "ev_chargers",
    "energy_grid",
}

# Recognized actions.
VALID_ACTIONS = {
    "read",
    "update",
    "change_signal",
    "change_grid_settings",
}
