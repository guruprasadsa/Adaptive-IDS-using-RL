"""
Interactive Alerting Integration Setup Script
Helps configure external integrations for the Adaptive IDS alerting pipeline.
"""
import os
import sys
import json
from pathlib import Path

# Color codes for Windows terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def get_input(prompt, default=None):
    """Get user input with optional default value."""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    return input(f"{prompt}: ").strip()

def get_yes_no(prompt, default='n'):
    """Get yes/no input."""
    response = get_input(prompt + " (y/n)", default).lower()
    return response in ['y', 'yes']

def configure_email():
    """Configure email integration."""
    print_header("Email Notification Setup")
    
    if not get_yes_no("Enable email notifications?", 'n'):
        return {'EMAIL_ENABLED': 'false'}
    
    print_info("\nEmail Provider Options:")
    print("  1. Gmail")
    print("  2. Office365")
    print("  3. Custom SMTP Server")
    
    choice = get_input("\nSelect provider", "1")
    
    config = {'EMAIL_ENABLED': 'true'}
    
    if choice == '1':
        print_info("\nGmail Setup Instructions:")
        print("  1. Enable 2FA: https://myaccount.google.com/security")
        print("  2. Generate App Password: https://myaccount.google.com/apppasswords")
        print("  3. Use app password (not your regular password)")
        
        config['SMTP_HOST'] = 'smtp.gmail.com'
        config['SMTP_PORT'] = '587'
        config['SMTP_TLS'] = 'true'
        config['SMTP_USER'] = get_input("\nGmail address")
        config['SMTP_PASSWORD'] = get_input("App password")
        
    elif choice == '2':
        config['SMTP_HOST'] = 'smtp.office365.com'
        config['SMTP_PORT'] = '587'
        config['SMTP_TLS'] = 'true'
        config['SMTP_USER'] = get_input("\nOffice365 email")
        config['SMTP_PASSWORD'] = get_input("Password")
        
    else:
        config['SMTP_HOST'] = get_input("\nSMTP host")
        config['SMTP_PORT'] = get_input("SMTP port", "587")
        config['SMTP_TLS'] = 'true' if get_yes_no("Use TLS?", 'y') else 'false'
        config['SMTP_USER'] = get_input("SMTP username")
        config['SMTP_PASSWORD'] = get_input("SMTP password")
    
    config['EMAIL_FROM'] = get_input("From address", config['SMTP_USER'])
    config['EMAIL_TO'] = get_input("To addresses (comma-separated)", "security@example.com")
    config['EMAIL_CC'] = get_input("CC addresses (optional)", "")
    
    print_success("\n✓ Email configuration complete")
    return config

def configure_syslog():
    """Configure syslog integration."""
    print_header("Syslog Integration Setup")
    
    if not get_yes_no("Enable syslog forwarding?", 'n'):
        return {'SYSLOG_ENABLED': 'false'}
    
    config = {'SYSLOG_ENABLED': 'true'}
    
    config['SYSLOG_HOST'] = get_input("\nSyslog server hostname or IP")
    config['SYSLOG_PORT'] = get_input("Syslog port", "6514")
    
    if get_yes_no("\nUse TLS encryption?", 'n'):
        print_info("\nTLS Certificate Paths (leave empty to skip):")
        config['SYSLOG_CLIENT_CERT'] = get_input("Client certificate path", "")
        config['SYSLOG_CLIENT_KEY'] = get_input("Client key path", "")
        config['SYSLOG_CA_CERT'] = get_input("CA certificate path", "")
    
    print_success("\n✓ Syslog configuration complete")
    return config

def configure_splunk():
    """Configure Splunk HEC integration."""
    print_header("Splunk HEC Setup")
    
    if not get_yes_no("Enable Splunk integration?", 'n'):
        return {'SPLUNK_ENABLED': 'false'}
    
    print_info("\nSplunk Setup Steps:")
    print("  1. Settings > Data Inputs > HTTP Event Collector")
    print("  2. Click 'New Token'")
    print("  3. Name: adaptive-ids")
    print("  4. Source Type: ids:alert")
    print("  5. Select Index (create 'ids_alerts' if needed)")
    print("  6. Copy Token Value")
    print("  7. Enable HEC in Global Settings")
    
    config = {'SPLUNK_ENABLED': 'true'}
    config['SPLUNK_HEC_URL'] = get_input("\nSplunk HEC URL", 
                                          "https://splunk.example.com:8088/services/collector")
    config['SPLUNK_HEC_TOKEN'] = get_input("HEC Token")
    config['SPLUNK_INDEX'] = get_input("Index name", "ids_alerts")
    config['SPLUNK_VERIFY_SSL'] = 'true' if get_yes_no("Verify SSL?", 'y') else 'false'
    
    print_success("\n✓ Splunk configuration complete")
    return config

def configure_elastic():
    """Configure Elastic SIEM integration."""
    print_header("Elastic SIEM Setup")
    
    if not get_yes_no("Enable Elastic integration?", 'n'):
        return {'ELASTIC_ENABLED': 'false'}
    
    print_info("\nElastic API Key Creation:")
    print("  Run in Kibana Dev Tools:")
    print('  POST /_security/api_key')
    print('  {')
    print('    "name": "adaptive-ids",')
    print('    "role_descriptors": {')
    print('      "ids-writer": {')
    print('        "index": [{')
    print('          "names": ["ids-alerts*"],')
    print('          "privileges": ["create_index", "write", "index"]')
    print('        }]')
    print('      }')
    print('    }')
    print('  }')
    
    config = {'ELASTIC_ENABLED': 'true'}
    config['ELASTIC_URL'] = get_input("\nElasticsearch URL", 
                                       "https://elastic.example.com:9200")
    config['ELASTIC_API_KEY'] = get_input("API Key (id:api_key format)")
    config['ELASTIC_INDEX'] = get_input("Index name", "ids-alerts")
    config['ELASTIC_VERIFY_SSL'] = 'true' if get_yes_no("Verify SSL?", 'y') else 'false'
    
    print_success("\n✓ Elastic configuration complete")
    return config

def save_env_file(config, filename='.env.alerting'):
    """Save configuration to .env file."""
    env_path = Path(filename)
    
    with open(env_path, 'w') as f:
        f.write("# Alerting Service - External Integrations Configuration\n")
        f.write("# Generated by setup_alerting_integrations.py\n\n")
        
        for key, value in config.items():
            f.write(f"{key}={value}\n")
    
    print_success(f"\n✓ Configuration saved to {filename}")

def test_configuration():
    """Run integration test."""
    print_header("Test Configuration")
    
    if not get_yes_no("Run integration test now?", 'y'):
        return
    
    print_info("\nRestarting alerting service with new configuration...")
    os.system("docker compose restart alerting-service")
    
    print_info("Waiting for service to start...")
    import time
    time.sleep(5)
    
    print_info("Running integration test...")
    os.system("python backend/alerting/test_integration.py")
    
    print_info("\nCheck service logs:")
    print("  docker compose logs -f alerting-service")

def main():
    print_header("Adaptive IDS - Alerting Integration Setup")
    
    print("This script will help you configure external integrations for the")
    print("alerting pipeline. You can enable one or more integrations.\n")
    
    all_config = {}
    
    # Configure each integration
    print_info("Configure each integration:")
    
    # 1. Email
    email_config = configure_email()
    all_config.update(email_config)
    
    # 2. Syslog
    syslog_config = configure_syslog()
    all_config.update(syslog_config)
    
    # 3. Splunk
    splunk_config = configure_splunk()
    all_config.update(splunk_config)
    
    # 4. Elastic
    elastic_config = configure_elastic()
    all_config.update(elastic_config)
    
    # Save configuration
    print_header("Save Configuration")
    
    if get_yes_no("Save configuration to .env.alerting?", 'y'):
        save_env_file(all_config)
        
        print_info("\nNext steps:")
        print("  1. Update docker-compose.yml alerting-service section:")
        print("     env_file:")
        print("       - .env.alerting")
        print("  2. Restart service: docker compose restart alerting-service")
        print("  3. Test: python backend/alerting/test_integration.py")
    
    # Test
    test_configuration()
    
    print_header("Setup Complete")
    print_success("Alerting integrations configured successfully!")
    
    print("\nMonitoring:")
    print("  • Service logs: docker compose logs -f alerting-service")
    print("  • Alerts table: docker compose exec postgres psql -U adaptive_ids -d adaptive_ids -c 'SELECT * FROM alerts ORDER BY created_at DESC LIMIT 10;'")
    print("  • DLQ: docker compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic alerts.dlq --from-beginning")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"\nError: {e}")
        sys.exit(1)
