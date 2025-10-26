"""
Schema Registry Client
Helpers for integrating with Confluent Schema Registry for Avro schema versioning.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from confluent_kafka.schema_registry import SchemaRegistryClient, Schema
    from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
    SCHEMA_REGISTRY_AVAILABLE = True
except ImportError:
    SCHEMA_REGISTRY_AVAILABLE = False
    SchemaRegistryClient = None
    Schema = None
    AvroSerializer = None
    AvroDeserializer = None

logger = logging.getLogger(__name__)


class SchemaRegistry:
    """
    Wrapper for Confluent Schema Registry operations.
    Manages schema registration, versioning, and serialization.
    """
    
    def __init__(self, registry_url: str = "http://localhost:8081"):
        """
        Initialize Schema Registry client.
        
        Args:
            registry_url: Schema Registry endpoint
        """
        if not SCHEMA_REGISTRY_AVAILABLE:
            raise ImportError(
                "confluent-kafka not available. Install with: pip install confluent-kafka"
            )
        
        self.registry_url = registry_url
        self.client = SchemaRegistryClient({'url': registry_url})
        self._schema_cache: Dict[str, Schema] = {}
        
        logger.info(f"Initialized Schema Registry client: {registry_url}")
    
    def load_schema_file(self, schema_path: Path) -> str:
        """
        Load Avro schema from file.
        
        Args:
            schema_path: Path to .avsc file
        
        Returns:
            Schema string
        """
        with open(schema_path, 'r') as f:
            schema_dict = json.load(f)
        return json.dumps(schema_dict)
    
    def register_schema(self, subject: str, schema_path: Path) -> int:
        """
        Register or update schema in the registry.
        
        Args:
            subject: Subject name (typically topic-value or topic-key)
            schema_path: Path to .avsc schema file
        
        Returns:
            Schema ID
        """
        schema_str = self.load_schema_file(schema_path)
        schema = Schema(schema_str, schema_type="AVRO")
        
        try:
            schema_id = self.client.register_schema(subject, schema)
            self._schema_cache[subject] = schema
            logger.info(f"Registered schema: {subject} (ID: {schema_id})")
            return schema_id
        except Exception as e:
            logger.error(f"Failed to register schema {subject}: {e}")
            raise
    
    def get_schema(self, subject: str, version: Optional[int] = None) -> Schema:
        """
        Get schema from registry.
        
        Args:
            subject: Subject name
            version: Specific version (None for latest)
        
        Returns:
            Schema object
        """
        cache_key = f"{subject}:{version}" if version else subject
        
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]
        
        try:
            if version:
                schema = self.client.get_version(subject, version)
            else:
                schema = self.client.get_latest_version(subject)
            
            self._schema_cache[cache_key] = schema
            logger.debug(f"Fetched schema: {subject} (version: {schema.version})")
            return schema
        except Exception as e:
            logger.error(f"Failed to get schema {subject}: {e}")
            raise
    
    def get_serializer(self, subject: str, to_dict: Optional[callable] = None) -> AvroSerializer:
        """
        Get Avro serializer for a subject.
        
        Args:
            subject: Subject name
            to_dict: Optional function to convert object to dict
        
        Returns:
            AvroSerializer instance
        """
        schema = self.get_schema(subject)
        return AvroSerializer(
            self.client,
            schema.schema.schema_str,
            to_dict=to_dict
        )
    
    def get_deserializer(self, subject: str, from_dict: Optional[callable] = None) -> AvroDeserializer:
        """
        Get Avro deserializer for a subject.
        
        Args:
            subject: Subject name
            from_dict: Optional function to convert dict to object
        
        Returns:
            AvroDeserializer instance
        """
        schema = self.get_schema(subject)
        return AvroDeserializer(
            self.client,
            schema.schema.schema_str,
            from_dict=from_dict
        )
    
    def list_subjects(self) -> list:
        """List all registered subjects"""
        try:
            subjects = self.client.get_subjects()
            logger.info(f"Found {len(subjects)} subjects")
            return subjects
        except Exception as e:
            logger.error(f"Failed to list subjects: {e}")
            raise
    
    def get_versions(self, subject: str) -> list:
        """Get all versions for a subject"""
        try:
            versions = self.client.get_versions(subject)
            logger.info(f"Subject {subject} has {len(versions)} versions")
            return versions
        except Exception as e:
            logger.error(f"Failed to get versions for {subject}: {e}")
            raise
    
    def test_compatibility(self, subject: str, schema_path: Path) -> bool:
        """
        Test if a schema is compatible with existing versions.
        
        Args:
            subject: Subject name
            schema_path: Path to new schema file
        
        Returns:
            True if compatible
        """
        schema_str = self.load_schema_file(schema_path)
        schema = Schema(schema_str, schema_type="AVRO")
        
        try:
            is_compatible = self.client.test_compatibility(subject, schema)
            logger.info(f"Schema compatibility test for {subject}: {is_compatible}")
            return is_compatible
        except Exception as e:
            logger.error(f"Failed to test compatibility for {subject}: {e}")
            raise


def register_all_schemas(registry_url: str = "http://localhost:8081", schema_dir: Optional[Path] = None) -> Dict[str, int]:
    """
    Register all schemas in the schemas directory.
    
    Args:
        registry_url: Schema Registry endpoint
        schema_dir: Directory containing .avsc files (default: current dir)
    
    Returns:
        Dict mapping subject names to schema IDs
    """
    if schema_dir is None:
        schema_dir = Path(__file__).parent
    
    registry = SchemaRegistry(registry_url)
    
    # Schema files and their subjects
    schemas_to_register = {
        "flows.features-value": schema_dir / "flow_features.avsc",
        "predictions-value": schema_dir / "prediction.avsc",
        "alerts-value": schema_dir / "alert.avsc",
    }
    
    results = {}
    for subject, schema_path in schemas_to_register.items():
        if not schema_path.exists():
            logger.warning(f"Schema file not found: {schema_path}")
            continue
        
        try:
            schema_id = registry.register_schema(subject, schema_path)
            results[subject] = schema_id
            print(f"✓ Registered {subject}: ID {schema_id}")
        except Exception as e:
            logger.error(f"Failed to register {subject}: {e}")
            print(f"✗ Failed to register {subject}: {e}")
    
    return results


def main():
    """CLI entry point for schema registration"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Schema Registry Management")
    parser.add_argument(
        '--url',
        default='http://localhost:8081',
        help='Schema Registry URL'
    )
    parser.add_argument(
        '--register',
        action='store_true',
        help='Register all schemas'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all subjects'
    )
    parser.add_argument(
        '--subject',
        help='Subject name for specific operations'
    )
    parser.add_argument(
        '--versions',
        action='store_true',
        help='List versions for subject'
    )
    
    args = parser.parse_args()
    
    if not SCHEMA_REGISTRY_AVAILABLE:
        print("Error: confluent-kafka not installed", file=sys.stderr)
        print("Install with: pip install confluent-kafka", file=sys.stderr)
        return 1
    
    try:
        registry = SchemaRegistry(args.url)
        
        if args.register:
            print(f"Registering schemas to {args.url}...")
            results = register_all_schemas(args.url)
            print(f"\n✓ Registered {len(results)} schemas")
            return 0
        
        if args.list:
            subjects = registry.list_subjects()
            print(f"Subjects ({len(subjects)}):")
            for subject in subjects:
                print(f"  - {subject}")
            return 0
        
        if args.versions and args.subject:
            versions = registry.get_versions(args.subject)
            print(f"Versions for {args.subject} ({len(versions)}):")
            for version in versions:
                print(f"  - Version {version}")
            return 0
        
        parser.print_help()
        return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
