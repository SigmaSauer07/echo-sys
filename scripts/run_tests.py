#!/usr/bin/env python3
"""
Test Runner for AlsaniaMCP

Comprehensive test runner that handles different test types,
generates reports, and validates system integrity.
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestRunner:
    """Comprehensive test runner for AlsaniaMCP"""
    
    def __init__(self):
        self.project_root = project_root
        self.backend_root = self.project_root / "backend"
        self.test_results = {}
        
    def run_unit_tests(self, verbose: bool = False) -> bool:
        """Run unit tests"""
        print("🧪 Running unit tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "backend/tests/unit/",
            "-m", "unit",
            "--tb=short"
        ]
        
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
        
        self.test_results['unit_tests'] = {
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        if result.returncode == 0:
            print("✅ Unit tests passed")
        else:
            print("❌ Unit tests failed")
            if verbose:
                print(result.stdout)
                print(result.stderr)
        
        return result.returncode == 0
    
    def run_integration_tests(self, verbose: bool = False) -> bool:
        """Run integration tests"""
        print("🔗 Running integration tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "backend/tests/integration/",
            "-m", "integration",
            "--tb=short"
        ]
        
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
        
        self.test_results['integration_tests'] = {
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        if result.returncode == 0:
            print("✅ Integration tests passed")
        else:
            print("❌ Integration tests failed")
            if verbose:
                print(result.stdout)
                print(result.stderr)
        
        return result.returncode == 0
    
    def run_docker_tests(self, verbose: bool = False) -> bool:
        """Run Docker integration tests"""
        print("🐳 Running Docker integration tests...")
        
        # Check if Docker is available
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Docker not available, skipping Docker tests")
            return True
        
        cmd = [
            "python", "-m", "pytest",
            "backend/tests/docker/",
            "-m", "docker",
            "--tb=short"
        ]
        
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
        
        self.test_results['docker_tests'] = {
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        if result.returncode == 0:
            print("✅ Docker tests passed")
        else:
            print("❌ Docker tests failed")
            if verbose:
                print(result.stdout)
                print(result.stderr)
        
        return result.returncode == 0
    
    def run_coverage_report(self) -> bool:
        """Generate coverage report"""
        print("📊 Generating coverage report...")
        
        cmd = [
            "python", "-m", "pytest",
            "backend/tests/",
            "--cov=backend",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--tb=no",
            "-q"
        ]
        
        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Coverage report generated")
            print("📁 HTML report: htmlcov/index.html")
        else:
            print("❌ Coverage report generation failed")
        
        return result.returncode == 0
    
    def validate_imports(self) -> bool:
        """Validate all imports work correctly"""
        print("📦 Validating imports...")
        
        try:
            # Test core imports
            from backend.core.plugins import PluginManager, ServiceContainer, EventBus
            from backend.core.imports import safe_import, get_import_manager
            
            # Test plugin interfaces
            from backend.core.plugins.interfaces import IPlugin, IAgentPlugin
            
            print("✅ Core imports validated")
            return True
            
        except ImportError as e:
            print(f"❌ Import validation failed: {e}")
            return False
    
    def validate_docker_build(self) -> bool:
        """Validate Docker builds work"""
        print("🔨 Validating Docker builds...")
        
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Docker not available, skipping build validation")
            return True
        
        # Test MCP service build
        cmd = ["docker-compose", "build", "mcp"]
        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Docker builds validated")
            return True
        else:
            print("❌ Docker build validation failed")
            print(result.stderr)
            return False
    
    def run_linting(self) -> bool:
        """Run code linting"""
        print("🧹 Running code linting...")
        
        # Check if flake8 is available
        try:
            cmd = ["python", "-m", "flake8", "backend/", "--max-line-length=100", "--ignore=E203,W503"]
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Linting passed")
                return True
            else:
                print("⚠️ Linting issues found:")
                print(result.stdout)
                return False
                
        except FileNotFoundError:
            print("⚠️ flake8 not available, skipping linting")
            return True
    
    def generate_report(self) -> None:
        """Generate comprehensive test report"""
        print("\n" + "="*60)
        print("📋 TEST REPORT SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['success'])
        
        print(f"Total test suites: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "No tests run")
        
        print("\nDetailed Results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        print("\n" + "="*60)
    
    def run_all_tests(self, verbose: bool = False, skip_docker: bool = False) -> bool:
        """Run all tests and validations"""
        print("🚀 Starting comprehensive test suite for AlsaniaMCP")
        print("="*60)
        
        start_time = time.time()
        all_passed = True
        
        # Validation tests
        all_passed &= self.validate_imports()
        
        if not skip_docker:
            all_passed &= self.validate_docker_build()
        
        # Unit tests
        all_passed &= self.run_unit_tests(verbose)
        
        # Integration tests
        all_passed &= self.run_integration_tests(verbose)
        
        # Docker tests (if not skipped)
        if not skip_docker:
            all_passed &= self.run_docker_tests(verbose)
        
        # Code quality
        self.run_linting()  # Don't fail on linting issues
        
        # Coverage report
        self.run_coverage_report()
        
        # Generate report
        self.generate_report()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n⏱️ Total execution time: {duration:.2f} seconds")
        
        if all_passed:
            print("🎉 All tests passed! System is ready for deployment.")
        else:
            print("💥 Some tests failed. Please review the results above.")
        
        return all_passed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="AlsaniaMCP Test Runner")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--docker", action="store_true", help="Run only Docker tests")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker tests")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report only")
    parser.add_argument("--validate", action="store_true", help="Run validation tests only")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.unit:
        success = runner.run_unit_tests(args.verbose)
    elif args.integration:
        success = runner.run_integration_tests(args.verbose)
    elif args.docker:
        success = runner.run_docker_tests(args.verbose)
    elif args.coverage:
        success = runner.run_coverage_report()
    elif args.validate:
        success = runner.validate_imports() and runner.validate_docker_build()
    else:
        success = runner.run_all_tests(args.verbose, args.skip_docker)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
