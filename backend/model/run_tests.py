"""
Test Runner for Phase 4 Components
Run all tests for A3C Router, DQN Specialist, Replay Buffer, and Calibration
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_all_tests():
    """Run all component tests"""
    print("="*70)
    print("Phase 4 Component Test Suite")
    print("="*70)
    print()
    
    try:
        import pytest
    except ImportError:
        print("ERROR: pytest not installed. Install with: pip install pytest")
        return False
    
    # Test files
    test_dir = Path(__file__).parent / 'tests'
    test_files = [
        test_dir / 'test_agents.py',
        test_dir / 'test_replay.py',
        test_dir / 'test_calibration.py'
    ]
    
    # Check if test files exist
    for test_file in test_files:
        if not test_file.exists():
            print(f"ERROR: Test file not found: {test_file}")
            return False
    
    print(f"Running tests from {test_dir}")
    print()
    
    # Run pytest
    args = [
        str(test_dir),
        '-v',              # Verbose
        '--tb=short',      # Short traceback
        '-x',              # Stop on first failure
        '--color=yes'      # Colored output
    ]
    
    result = pytest.main(args)
    
    print()
    print("="*70)
    if result == 0:
        print("✅ All tests PASSED!")
    else:
        print("❌ Some tests FAILED")
    print("="*70)
    
    return result == 0


def run_specific_test(test_name):
    """Run a specific test file"""
    import pytest
    
    test_dir = Path(__file__).parent / 'tests'
    test_file = test_dir / f'test_{test_name}.py'
    
    if not test_file.exists():
        print(f"ERROR: Test file not found: {test_file}")
        return False
    
    print(f"Running tests from {test_file}")
    print()
    
    result = pytest.main([str(test_file), '-v', '--tb=short', '--color=yes'])
    
    return result == 0


def check_imports():
    """Check if all required modules can be imported"""
    print("Checking module imports...")
    print()
    
    modules = [
        ('torch', 'PyTorch'),
        ('numpy', 'NumPy'),
        ('sklearn', 'scikit-learn'),
        ('matplotlib', 'Matplotlib'),
    ]
    
    all_ok = True
    
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            print(f"✅ {display_name:20s} - OK")
        except ImportError:
            print(f"❌ {display_name:20s} - MISSING")
            all_ok = False
    
    print()
    
    # Check our components
    print("Checking Phase 4 components...")
    print()
    
    components = [
        ('model.agents.a3c_router', 'A3C Router'),
        ('model.agents.dqn_specialist', 'DQN Specialist'),
        ('model.replay.prioritized_buffer', 'Replay Buffer'),
        ('model.utils.calibration', 'Calibration Utils'),
    ]
    
    for module_name, display_name in components:
        try:
            __import__(module_name)
            print(f"✅ {display_name:20s} - OK")
        except ImportError as e:
            print(f"❌ {display_name:20s} - FAILED: {e}")
            all_ok = False
    
    print()
    return all_ok


def main():
    """Main test runner"""
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        
        if test_name == '--check':
            # Check imports only
            success = check_imports()
            sys.exit(0 if success else 1)
        else:
            # Run specific test
            success = run_specific_test(test_name)
            sys.exit(0 if success else 1)
    else:
        # Check imports first
        if not check_imports():
            print("ERROR: Some required modules are missing!")
            sys.exit(1)
        
        print()
        print("="*70)
        print()
        
        # Run all tests
        success = run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
