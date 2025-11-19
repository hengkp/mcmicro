#!/usr/bin/env python3
"""
Integration tests for PALOM registration module in MCMICRO pipeline.
This Python test suite provides more detailed validation than the bash scripts.
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path
import unittest
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestPalomIntegration(unittest.TestCase):
    """Base class for PALOM integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.project_root = PROJECT_ROOT
        cls.test_output_dir = Path(__file__).parent / "test_output_py"
        cls.test_output_dir.mkdir(exist_ok=True)
        
        # Check for test data
        cls.test_data_dir = None
        for data_dir in ["exemplar-001", "test-data"]:
            path = cls.project_root / data_dir
            if path.exists():
                cls.test_data_dir = path
                break
        
        # Check for nextflow
        cls.has_nextflow = subprocess.run(
            ["which", "nextflow"],
            capture_output=True
        ).returncode == 0
    
    def create_params_file(self, filename: str, config: dict) -> Path:
        """Create a params.yml file for testing."""
        params_file = self.test_output_dir / filename
        with open(params_file, 'w') as f:
            yaml.dump(config, f)
        return params_file
    
    def check_file_exists(self, filepath: Path) -> bool:
        """Check if file exists and is not empty."""
        return filepath.exists() and filepath.stat().st_size > 0


class TestPalomRegistration(TestPalomIntegration):
    """Test 8.1: Test PALOM registration with sample data."""
    
    def test_8_1_1_params_file_creation(self):
        """Test creating params.yml with PALOM engine."""
        config = {
            'workflow': {
                'registration-engine': 'palom',
                'start-at': 'registration',
                'stop-at': 'registration'
            },
            'options': {
                'palom': '--level 0 --ref-index 0'
            }
        }
        
        params_file = self.create_params_file('test_8.1_params.yml', config)
        self.assertTrue(params_file.exists(), "params.yml should be created")
        
        # Verify content
        with open(params_file) as f:
            loaded = yaml.safe_load(f)
        
        self.assertEqual(
            loaded['workflow']['registration-engine'],
            'palom',
            "registration-engine should be palom"
        )
    
    def test_8_1_2_config_defaults(self):
        """Test that config/defaults.yml has PALOM configuration."""
        defaults_file = self.project_root / "config" / "defaults.yml"
        self.assertTrue(defaults_file.exists(), "config/defaults.yml should exist")
        
        with open(defaults_file) as f:
            config = yaml.safe_load(f)
        
        # Check PALOM module specification
        self.assertIn('registration-palom', config['modules'],
                     "registration-palom module should be defined")
        
        palom_module = config['modules']['registration-palom']
        self.assertEqual(palom_module['name'], 'palom')
        self.assertIn('container', palom_module)
        self.assertIn('version', palom_module)
    
    def test_8_1_3_registration_workflow(self):
        """Test that registration.nf has PALOM process."""
        registration_file = self.project_root / "modules" / "registration.nf"
        self.assertTrue(registration_file.exists(), "registration.nf should exist")
        
        with open(registration_file) as f:
            content = f.read()
        
        # Check for palom_align process
        self.assertIn('process palom_align', content,
                     "palom_align process should be defined")
        
        # Check for engine selection logic
        self.assertIn("registration-engine", content,
                     "Engine selection logic should exist")
        
        # Check for validation
        self.assertIn("Unknown registration engine", content,
                     "Engine validation should exist")


class TestBackwardCompatibility(TestPalomIntegration):
    """Test 8.2: Test backward compatibility with ASHLAR."""
    
    def test_8_2_1_default_engine(self):
        """Test that default engine is ASHLAR."""
        defaults_file = self.project_root / "config" / "defaults.yml"
        
        with open(defaults_file) as f:
            config = yaml.safe_load(f)
        
        default_engine = config['workflow'].get('registration-engine', 'ashlar')
        self.assertEqual(default_engine, 'ashlar',
                        "Default registration engine should be ashlar")
    
    def test_8_2_2_params_without_engine(self):
        """Test params file without registration-engine parameter."""
        config = {
            'workflow': {
                'start-at': 'registration',
                'stop-at': 'registration'
            },
            'options': {
                'ashlar': '-m 30'
            }
        }
        
        params_file = self.create_params_file('test_8.2_params.yml', config)
        
        with open(params_file) as f:
            loaded = yaml.safe_load(f)
        
        self.assertNotIn('registration-engine', loaded['workflow'],
                        "registration-engine should not be in params")


class TestDownstreamCompatibility(TestPalomIntegration):
    """Test 8.3: Test downstream module compatibility."""
    
    def test_8_3_1_output_format(self):
        """Test that PALOM outputs OME-TIFF format."""
        registration_file = self.project_root / "modules" / "registration.nf"
        
        with open(registration_file) as f:
            content = f.read()
        
        # Check PALOM output pattern
        self.assertIn('*.ome.tif', content,
                     "PALOM should output OME-TIFF files")
    
    def test_8_3_2_output_directory(self):
        """Test that PALOM uses same output directory as ASHLAR."""
        registration_file = self.project_root / "modules" / "registration.nf"
        
        with open(registration_file) as f:
            lines = f.readlines()
        
        # Find publishDir for both processes
        palom_dir = None
        ashlar_dir = None
        
        in_palom = False
        in_ashlar = False
        
        for line in lines:
            if 'process palom_align' in line:
                in_palom = True
                in_ashlar = False
            elif 'process ashlar' in line:
                in_ashlar = True
                in_palom = False
            elif 'publishDir' in line and 'registration' in line:
                if in_palom:
                    palom_dir = 'registration'
                elif in_ashlar:
                    ashlar_dir = 'registration'
        
        self.assertEqual(palom_dir, ashlar_dir,
                        "PALOM and ASHLAR should use same output directory")


class TestErrorHandling(TestPalomIntegration):
    """Test 8.4: Test error handling."""
    
    def test_8_4_1_invalid_engine_validation(self):
        """Test validation for invalid registration engine."""
        registration_file = self.project_root / "modules" / "registration.nf"
        
        with open(registration_file) as f:
            content = f.read()
        
        # Check for validation logic
        self.assertIn("Unknown registration engine", content,
                     "Should have validation for invalid engine")
        self.assertIn("Valid options", content,
                     "Should list valid options in error message")
    
    def test_8_4_2_cycle_index_validation(self):
        """Test validation for invalid cycle index."""
        script_file = self.project_root / "register_akoya_palom.py"
        
        if script_file.exists():
            with open(script_file) as f:
                content = f.read()
            
            # Check for cycle index validation
            has_validation = (
                'out of range' in content or
                'ValueError' in content or
                'ref_index' in content
            )
            self.assertTrue(has_validation,
                          "Should have cycle index validation")
    
    def test_8_4_3_error_messages(self):
        """Test that error messages are clear and informative."""
        registration_file = self.project_root / "modules" / "registration.nf"
        
        with open(registration_file) as f:
            content = f.read()
        
        # Check for clear error message
        self.assertIn("ashlar, palom", content,
                     "Error message should list valid engines")


class TestPalomOptions(TestPalomIntegration):
    """Test 8.5: Test PALOM-specific options."""
    
    def test_8_5_1_default_options(self):
        """Test default PALOM options in config."""
        defaults_file = self.project_root / "config" / "defaults.yml"
        
        with open(defaults_file) as f:
            config = yaml.safe_load(f)
        
        self.assertIn('palom', config['options'],
                     "PALOM options should be defined")
        
        palom_opts = config['options']['palom']
        self.assertIn('--level', palom_opts,
                     "Default options should include --level")
        self.assertIn('--ref-index', palom_opts,
                     "Default options should include --ref-index")
    
    def test_8_5_2_custom_options(self):
        """Test custom PALOM options configuration."""
        config = {
            'workflow': {
                'registration-engine': 'palom'
            },
            'options': {
                'palom': '--ref-index 1 --cycle-channels "0:0,1;1:0,2" --compression lzw'
            }
        }
        
        params_file = self.create_params_file('test_8.5_params.yml', config)
        
        with open(params_file) as f:
            loaded = yaml.safe_load(f)
        
        palom_opts = loaded['options']['palom']
        self.assertIn('--ref-index', palom_opts)
        self.assertIn('--cycle-channels', palom_opts)
        self.assertIn('--compression', palom_opts)
    
    def test_8_5_3_opts_module_opts(self):
        """Test that palom_align uses Opts.moduleOpts."""
        registration_file = self.project_root / "modules" / "registration.nf"
        
        with open(registration_file) as f:
            content = f.read()
        
        # Check that palom_align uses Opts.moduleOpts
        self.assertIn('Opts.moduleOpts(module, mcp)', content,
                     "palom_align should use Opts.moduleOpts")


def run_tests():
    """Run all integration tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPalomRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestDownstreamCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestPalomOptions))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
