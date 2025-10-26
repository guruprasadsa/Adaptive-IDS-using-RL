#!/usr/bin/env python3
"""
Quick script to add API keys to database
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.api_keys import APIKeyManager

# Database connection string (inside Docker network)
os.environ['DATABASE_URL'] = 'postgresql://adaptive_ids:idspassword@postgres:5432/adaptive_ids'

def main():
    print("Creating API keys...")
    
    manager = APIKeyManager()
    
    # Create API keys for services
    services = [
        {
            'service_name': 'model-service',
            'scopes': ['model:predict', 'model:train', 'model:metrics'],
            'ttl_days': 90
        },
        {
            'service_name': 'alerting-service',
            'scopes': ['alerts:create', 'alerts:update', 'alerts:read'],
            'ttl_days': 90
        },
        {
            'service_name': 'feature-extractor',
            'scopes': ['features:extract', 'features:read'],
            'ttl_days': 90
        }
    ]
    
    keys_created = []
    for service_config in services:
        raw_key, api_key_obj = manager.generate_key(**service_config)
        keys_created.append({
            'service': service_config['service_name'],
            'key_id': api_key_obj.key_id,
            'raw_key': raw_key
        })
        print(f"\n✅ Created API key for {service_config['service_name']}")
        print(f"   Key ID: {api_key_obj.key_id}")
        print(f"   API Key: {raw_key}")
        print(f"   Expires: {api_key_obj.expires_at}")
    
    print("\n" + "="*80)
    print("API Keys Created Successfully!")
    print("="*80)
    print("\nAdd these to your .env file:")
    print(f"MODEL_SERVICE_API_KEY={keys_created[0]['raw_key']}")
    print(f"ALERTING_SERVICE_API_KEY={keys_created[1]['raw_key']}")
    print(f"FEATURE_EXTRACTOR_API_KEY={keys_created[2]['raw_key']}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
