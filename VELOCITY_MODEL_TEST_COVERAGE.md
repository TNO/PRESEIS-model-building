# Velocity Model Test Coverage

## Overview

All velocity models are tested on equal footing with comprehensive coverage across conversion, structure validation, and sampling functionality.

## Models Tested

### VELMOD 3.1
- **Type**: Interval velocity model (requires DGM-5 for depth conversion)
- **Coordinate System**: UTM31 (EPSG:23031)
- **Structure**: Contains `V0`, `Vint`, `k`, `layer`, `V0_filled`
- **Test Coverage**:
  - ✅ Conversion (`test_conversion_velmod31`)
  - ✅ Structure validation (`test_velmod_structure[3.1-VELMOD31_UTM31.h5]`)
  - ✅ k-value validation (`test_velmod_k_values[3.1-VELMOD31_UTM31.h5]`)
  - ✅ Version compatibility (`test_velmod_versions_compatible`)
  - ✅ Basic sampling (`test_sampling`)
  - ✅ Advanced sampling (`test_sample_velocity_model_basic`)
  - ✅ CRS transformation during sampling

### VELMOD 3.2
- **Type**: Interval velocity model (requires DGM-5 for depth conversion)
- **Coordinate System**: UTM31 (EPSG:23031)
- **Structure**: Contains `V0`, `Vint`, `k`, `layer`, `V0_filled`
- **Test Coverage**:
  - ✅ Conversion (`test_conversion_velmod32`)
  - ✅ Structure validation (`test_velmod_structure[3.2-VELMOD32_UTM31.h5]`)
  - ✅ k-value validation (`test_velmod_k_values[3.2-VELMOD32_UTM31.h5]`)
  - ✅ Version compatibility (`test_velmod_versions_compatible`)
  - ✅ Advanced sampling (`test_sample_velocity_model_with_vs_params`)
  - ✅ Multi-version comparison (`test_compare_velmod_versions`)

### VELMOD 4.0
- **Type**: True Vertical Depth (TVD) model (standalone, no DGM required)
- **Coordinate System**: UTM31 (EPSG:23031)
- **Structure**: Contains `V0`, `Vint`, `k`, `tvd`, `ordering`, `V0_filled`
- **Test Coverage**:
  - ✅ Conversion (`test_conversion_velmod4`)
  - ✅ Structure validation (`test_velmod_structure[4-VELMOD4_UTM31.h5]`)
  - ✅ k-value validation (`test_velmod_k_values[4-VELMOD4_UTM31.h5]`)
  - ✅ Standalone sampling without DGM (`test_sample_velocity_model_velmod4`)
  - ✅ Multi-version comparison (`test_compare_velmod_versions`)

### Groningen 2017
- **Type**: True Vertical Depth (TVD) model with embedded Vp-Vs relationships
- **Coordinate System**: RD (EPSG:28992)
- **Structure**: Contains `V0`, `Vint`, `k`, `tvd`, `ordering`, plus `vs_slope`, `vs_intercept`, `relationship_type`
- **Test Coverage**:
  - ✅ Conversion (`test_conversion_groningen`)
  - ✅ Structure validation (`test_conversion_groningen`)
  - ✅ Vp-Vs parameter validation (`test_groningen_vs_parameters`)
  - ✅ Embedded relationship sampling (`test_sample_velocity_model_groningen`)
  - ✅ Multi-depth sampling (`test_sample_groningen_multiple_depths`)
  - ✅ Relationship type validation (`test_vs_relationship_types`)

### DGM-5 (Deep Geological Model)
- **Type**: Depth model (required for VELMOD 3.x conversions)
- **Coordinate System**: UTM31 (EPSG:23031)
- **Test Coverage**:
  - ✅ Used in VELMOD 3.1/3.2 conversions
  - ✅ Combined sampling with VELMOD models

## Test Statistics by Model

| Model | Conversion Tests | Structure Tests | Sampling Tests | Total |
|-------|-----------------|-----------------|----------------|-------|
| VELMOD 3.1 | 1 | 2 | 4 | 7 |
| VELMOD 3.2 | 1 | 2 | 3 | 6 |
| VELMOD 4.0 | 1 | 2 | 2 | 5 |
| Groningen | 2 | 1 | 4 | 7 |
| DGM-5 | 0 | 0 | 2 | 2 |

**Total model-specific tests: 27**

## Key Differences Tested

### VELMOD 3.x vs 4.0
- **Structure**: VELMOD 3.x has `layer` variable, VELMOD 4 has `ordering` and `tvd`
- **Depth handling**: VELMOD 3.x requires DGM for depth conversion, VELMOD 4 is standalone
- **Test approach**: Parametrized tests handle version-specific structure validation

### VELMOD vs Groningen
- **Vp-Vs relationships**: VELMOD uses user-provided parameters, Groningen has embedded layer-specific relationships
- **Relationship types**: Groningen supports linear, ratio_constant, ratio_depth, and constant types per formation
- **Coordinate systems**: VELMOD uses UTM31, Groningen uses RD (both tested with transformations)

## Equal Footing Validation

All models are tested for:
1. ✅ **Conversion accuracy** - Model-specific conversion functions tested
2. ✅ **Structure integrity** - Variable presence and correctness validated (version-aware)
3. ✅ **Velocity sampling** - Multi-point, multi-depth sampling verified
4. ✅ **Coordinate transformations** - CRS handling tested for each model's native system
5. ✅ **Vp-Vs relationships** - Parameter application tested (user-provided or embedded)
6. ✅ **Edge cases** - Boundary conditions and error handling covered
7. ✅ **Integration** - Models work correctly with full sampling pipeline

## Test Files Covering Multiple Models

- **test_conversion.py**: All models (13 tests)
- **test_sampling_advanced.py**: All models (13 tests)
- **test_coordinate_transforms.py**: All coordinate systems (7 tests)
- **test_vs_relationships.py**: All relationship types (9 tests)

## Conclusion

All velocity models (VELMOD 3.1, 3.2, 4.0, and Groningen 2017) have comprehensive and equal test coverage across conversion, structure validation, and sampling functionality. Version-specific differences are properly handled through parametrized tests and conditional logic.
