# Test Suite for PRESEIS Model Building

This directory contains tests for the PRESEIS model-building package surface and its compatibility path.

## Test Files

### Core Functionality Tests

- **test_conversion.py** - Tests for model conversion (DGM, VELMOD 3.1/3.2/4.0, Groningen)
  - Model structure validation
  - k-value correctness
  - Version compatibility
  - Groningen-specific validation
  
- **test_sampling.py** - Basic velocity sampling tests
  - Grid-based sampling
  - Coordinate system handling
  
- **test_sampling_advanced.py** - Advanced sampling functionality
  - Multiple coordinate input
  - CRS transformation during sampling
  - Surface and deep depth sampling
  - Vs parameter handling
  - All model types (VELMOD 3.1/3.2/4.0, Groningen)

### Utility and Support Tests

- **test_utils.py** - Utility function tests
  - Path management (get_package_root, get_data_dir, etc.)
  - Configuration loading
  - Model config retrieval
  - Error handling for invalid inputs

- **test_download.py** - Download functionality tests
  - Basic download
  - Force re-download
  - Slow test marker for full downloads

### Coordinate System Tests

- **test_coordinate_transforms.py** - CRS transformation tests
  - WGS84 to UTM transformation
  - RD to UTM transformation
  - Native UTM coordinates
  - Array coordinate transformation
  - CRS inference and validation

### Vp-Vs Relationship Tests

- **test_vs_relationships.py** - Comprehensive Vp-Vs calculation tests
  - Linear relationship: `Vs = vs_intercept + vs_slope * Vp`
  - Constant ratio: `Vs = Vp / vs_slope`
  - Depth-dependent ratio: `Vs = Vp / (vs_intercept + vs_slope * depth)`
  - Constant Vs values
  - Groningen embedded relationships
  - Parameter override warnings
  - Validation of positive Vs values
  - Vp/Vs ratio bounds checking

## Running Tests

### Setup requirements and expected behavior

- You can run the default suite without running `make setup` first.
- Tests that require processed model files skip when data is missing (for example sampling/CRS/Vp-Vs tests).
- Some tests intentionally trigger download/convert flows (`test_download.py`, `test_download_sources.py`, parts of `test_conversion.py`) and may require network access.
- By default, slow tests are excluded via pytest config (`addopts = "-m 'not slow'"` in `pyproject.toml`).

### Run all tests
```bash
pytest tests/
```

This uses the default marker selection from `pyproject.toml` and excludes `@pytest.mark.slow` tests unless you override markers explicitly.

### Run specific test file
```bash
pytest tests/test_utils.py -v
```

### Run with coverage
```bash
pytest tests/ --cov=preseis --cov-report=term-missing --cov-report=html
```

### Exclude slow tests
```bash
pytest tests/ -m "not slow"
```

### Run only slow tests
```bash
pytest tests/ -m "slow"
```

## Test Markers

- `@pytest.mark.slow` - Tests that take significant time (downloads, full conversions)

## Test Coverage

The test suite now covers:

1. **Utility Functions** (100% coverage)
   - All path management functions
   - Configuration loading
   - Model config retrieval
   - Error handling

2. **Coordinate Transformations** (~90% coverage)
   - WGS84 ↔ UTM31
   - RD ↔ UTM31
   - CRS validation
   - Array transformations

3. **Velocity Sampling** (~85% coverage)
   - Basic sampling
   - Multi-point sampling
   - Grid sampling
   - Depth ranges

4. **Vp-Vs Relationships** (~95% coverage)
   - All relationship types (linear, ratio_constant, ratio_depth, constant)
   - Embedded relationships (Groningen)
   - User-provided parameters (VELMOD)
   - Parameter validation
   - Warning system

5. **Model Conversion** (~80% coverage)
   - DGM conversion
   - VELMOD 3.1, 3.2, 4.0 conversion (comprehensive)
   - Groningen conversion with Vp-Vs relationships
   - Model structure validation (version-specific)
   - k-value validation across versions

6. **Download** (~70% coverage)
   - Basic download functionality
   - Force re-download
   - Configuration-based downloads

## Fixtures

Common fixtures are defined in `conftest.py`:
- `test_models` - Loads available velocity models
- `test_data` - Loads test models with optional Groningen
- `velmod_and_dgm` - Loads VELMOD31 and DGM5

## Test Data

Tests use:
- Downloaded models in `data/raw/`
- Converted models in `data/processed/`

## Coverage Goals

Current coverage: **~85%** (estimated)

All velocity models tested:
- VELMOD 3.1 (with DGM-5)
- VELMOD 3.2 (with DGM-5)
- VELMOD 4.0 (standalone)
- Groningen 2017 (with embedded Vp-Vs relationships)

## Contributing

When adding new tests:
1. Follow existing naming conventions
2. Add docstrings explaining what is tested
3. Use appropriate markers (@pytest.mark.slow for time-intensive tests)
4. Add fixtures to conftest.py if reusable across multiple test files
5. Aim for both happy path and error condition coverage
