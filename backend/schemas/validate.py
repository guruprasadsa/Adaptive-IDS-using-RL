#!/usr/bin/env python
"""
Schema Validator CLI
Validates JSON payloads against Avro schemas and Pydantic models.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from fastavro import parse_schema, validate
    AVRO_AVAILABLE = True
except ImportError:
    AVRO_AVAILABLE = False
    print("Warning: fastavro not installed. Install with: pip install fastavro", file=sys.stderr)

from schemas.models import FlowFeatures, Prediction, Alert


# Schema file paths
SCHEMA_DIR = Path(__file__).parent
SCHEMAS = {
    "flow_features": SCHEMA_DIR / "flow_features.avsc",
    "prediction": SCHEMA_DIR / "prediction.avsc",
    "alert": SCHEMA_DIR / "alert.avsc",
}

# Example file paths
EXAMPLES = {
    "flow_features": SCHEMA_DIR / "examples" / "flow_features_example.json",
    "prediction": SCHEMA_DIR / "examples" / "prediction_example.json",
    "alert": SCHEMA_DIR / "examples" / "alert_example.json",
}

# Pydantic model mapping
MODELS = {
    "flow_features": FlowFeatures,
    "prediction": Prediction,
    "alert": Alert,
}


def load_schema(schema_name: str) -> Dict[str, Any]:
    """Load and parse Avro schema"""
    schema_path = SCHEMAS.get(schema_name)
    if not schema_path or not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_name}")
    
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    if AVRO_AVAILABLE:
        return parse_schema(schema)
    return schema


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file"""
    with open(file_path, 'r') as f:
        return json.load(f)


def validate_avro(data: Dict[str, Any], schema_name: str) -> bool:
    """
    Validate data against Avro schema.
    
    Returns:
        True if valid, False otherwise
    """
    if not AVRO_AVAILABLE:
        print("⚠ Skipping Avro validation (fastavro not installed)", file=sys.stderr)
        return True
    
    try:
        schema = load_schema(schema_name)
        validate(data, schema)
        print(f"✓ Avro schema validation passed: {schema_name}")
        return True
    except Exception as e:
        print(f"✗ Avro schema validation failed: {schema_name}", file=sys.stderr)
        print(f"  Error: {e}", file=sys.stderr)
        return False


def validate_pydantic(data: Dict[str, Any], schema_name: str) -> bool:
    """
    Validate data using Pydantic model.
    
    Returns:
        True if valid, False otherwise
    """
    model_class = MODELS.get(schema_name)
    if not model_class:
        print(f"⚠ No Pydantic model found for: {schema_name}", file=sys.stderr)
        return True
    
    try:
        # Create model instance
        instance = model_class.from_dict(data)
        
        # Serialize back to dict
        serialized = instance.to_dict()
        
        print(f"✓ Pydantic validation passed: {schema_name}")
        print(f"  Model: {model_class.__name__}")
        
        # Check round-trip consistency (ignore None values)
        original_keys = set(k for k, v in data.items() if v is not None)
        serialized_keys = set(k for k, v in serialized.items() if v is not None)
        
        if original_keys == serialized_keys:
            print(f"  ✓ Round-trip serialization consistent")
        else:
            missing = original_keys - serialized_keys
            extra = serialized_keys - original_keys
            if missing:
                print(f"  ⚠ Keys missing after round-trip: {missing}")
            if extra:
                print(f"  ⚠ Extra keys after round-trip: {extra}")
        
        return True
        
    except Exception as e:
        print(f"✗ Pydantic validation failed: {schema_name}", file=sys.stderr)
        print(f"  Error: {e}", file=sys.stderr)
        return False


def validate_file(file_path: str, schema_name: str, skip_avro: bool = False, skip_pydantic: bool = False) -> bool:
    """
    Validate a JSON file against schema.
    
    Args:
        file_path: Path to JSON file
        schema_name: Schema name (flow_features, prediction, alert)
        skip_avro: Skip Avro validation
        skip_pydantic: Skip Pydantic validation
    
    Returns:
        True if all validations pass
    """
    print(f"\nValidating: {file_path}")
    print(f"Schema: {schema_name}")
    print("-" * 60)
    
    try:
        data = load_json(file_path)
    except Exception as e:
        print(f"✗ Failed to load JSON: {e}", file=sys.stderr)
        return False
    
    results = []
    
    if not skip_avro:
        results.append(validate_avro(data, schema_name))
    
    if not skip_pydantic:
        results.append(validate_pydantic(data, schema_name))
    
    all_passed = all(results)
    
    if all_passed:
        print(f"\n✓ All validations passed for {schema_name}")
    else:
        print(f"\n✗ Some validations failed for {schema_name}", file=sys.stderr)
    
    return all_passed


def validate_examples() -> bool:
    """Validate all example JSON files"""
    print("\n" + "=" * 60)
    print("Validating Example Payloads")
    print("=" * 60)
    
    results = []
    for schema_name, example_path in EXAMPLES.items():
        if not example_path.exists():
            print(f"⚠ Example not found: {example_path}", file=sys.stderr)
            continue
        
        result = validate_file(str(example_path), schema_name)
        results.append(result)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ All example validations passed")
        return True
    else:
        print("✗ Some example validations failed", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate JSON payloads against Adaptive IDS schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a specific file
  python validate.py --file data.json --schema flow_features
  
  # Validate all examples
  python validate.py --examples
  
  # Skip Avro validation
  python validate.py --file data.json --schema prediction --skip-avro
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='JSON file to validate'
    )
    
    parser.add_argument(
        '--schema', '-s',
        type=str,
        choices=list(SCHEMAS.keys()),
        help='Schema name to validate against'
    )
    
    parser.add_argument(
        '--examples', '-e',
        action='store_true',
        help='Validate all example payloads'
    )
    
    parser.add_argument(
        '--skip-avro',
        action='store_true',
        help='Skip Avro schema validation'
    )
    
    parser.add_argument(
        '--skip-pydantic',
        action='store_true',
        help='Skip Pydantic model validation'
    )
    
    parser.add_argument(
        '--list-schemas',
        action='store_true',
        help='List available schemas'
    )
    
    args = parser.parse_args()
    
    # List schemas
    if args.list_schemas:
        print("Available schemas:")
        for name, path in SCHEMAS.items():
            status = "✓" if path.exists() else "✗"
            print(f"  {status} {name}: {path}")
        return 0
    
    # Validate examples
    if args.examples:
        success = validate_examples()
        return 0 if success else 1
    
    # Validate specific file
    if args.file and args.schema:
        success = validate_file(args.file, args.schema, args.skip_avro, args.skip_pydantic)
        return 0 if success else 1
    
    # No action specified
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
