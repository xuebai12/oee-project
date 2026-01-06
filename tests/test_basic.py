import pytest
import os
import yaml
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from oee.dashboardv1 import load_config

def test_load_config_defaults():
    """Test that defaults are returned when no config file exists."""
    # Temporarily rename config.yaml if it exists to test defaults
    if os.path.exists("config.yaml"):
        os.rename("config.yaml", "config.yaml.bak")
    
    try:
        config = load_config()
        assert config['production']['target_steps'] == 30
        assert config['production']['ideal_cycle_time'] == 20.0
    finally:
        if os.path.exists("config.yaml.bak"):
            os.rename("config.yaml.bak", "config.yaml")

def test_load_config_from_file():
    """Test that values are read from config.yaml."""
    # Create a temporary config file
    test_config = {
        'production': {
            'target_steps': 50,
            'ideal_cycle_time': 10.0
        }
    }
    
    # Backup existing
    if os.path.exists("config.yaml"):
        os.rename("config.yaml", "config.yaml.bak")
        
    try:
        with open("config.yaml", "w") as f:
            yaml.dump(test_config, f)
            
        config = load_config()
        assert config['production']['target_steps'] == 50
        assert config['production']['ideal_cycle_time'] == 10.0
        
    finally:
        # Restore
        if os.path.exists("config.yaml"):
            os.remove("config.yaml")
        if os.path.exists("config.yaml.bak"):
            os.rename("config.yaml.bak", "config.yaml")
