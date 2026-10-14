# Configuration Files

## config.yaml

Main configuration file containing:
- Model definitions (DGM, VELMOD 3.1, VELMOD 3.2, VELMOD 4, Groningen)
- Download URLs
- File paths and naming conventions

## K-factor Files

The k-values define the velocity gradient in the linear depth parameterization:

```
V(z) = V₀ + k·z
```

where:
- V(z) is the P-wave velocity at depth z
- V₀ is the velocity at the top of the stratigraphic unit
- k is the velocity gradient (in s⁻¹)
- z is depth below the unit top

### velmod31_k.csv

K-values for VELMOD 3.1, manually extracted from:
- **Source**: [VELMOD 3.1 Technical Report (TNO 2017 R11014)](https://www.nlog.nl/sites/default/files/2018-11/060.26839%20R11014%20with%20erratum%20page%2067%20Doornenbal-final.sec_.pdf)
- **Location**: Table 1, page 8

### velmod32_k.csv

K-values for VELMOD 3.2, manually extracted from:
- **Source**: [VELMOD 3.2 Technical Report (TNO 2023 R12557)](https://www.nlog.nl/sites/default/files/2024-06/R12557%20VELMOD3_2_final_20240109.get_.pdf)
- **Location**: Table 3.1, page 8

### velmod4_k.csv

K-values for VELMOD 4, manually extracted from:
- **Source**: [VELMOD 4 Technical Report (TNO 2020 R10558)](https://www.nlog.nl/sites/default/files/2022-03/r10558_velmod-4_nam_final_public_report.pdf)
- **Location**: Step 5 workflow output (VELMOD 4b grids)

**Important**: VELMOD 4 provides some stratigraphic units as combined layers:
- **RN+RB** (Rijnland + Roer Base) - stored as separate RN and RB entries with individual k-values
- **S+AT** (Scruff + Altena) - stored as separate S and AT entries with individual k-values

During conversion, the combined units (RN+RB, S+AT) in the source ZMAP files are mapped to their primary units (RN, S) to maintain consistency with VELMOD 3.1/3.2 naming conventions. The k-values are preserved from the original separate unit definitions.

### groningen_k.csv

K-values for Groningen 2017 model, extracted from:
- **Source**: [NAM Groningen Velocity Model (September 2017)](https://nam-onderzoeksrapporten.data-app.nl/reports/download/groningen/en/3b4f8b0d-0277-40e0-8ff5-9a385c08327d)
- **Location**: sept2017_velo_model.xlsx, Technical Addendum to Winningsplan Groningen 2016

## Vp-Vs Relationship Files

### groningen_vp_vs.csv

Vp-Vs relationships for Groningen 2017 model. Unlike VELMOD (P-wave only), the Groningen model includes native S-wave velocities with formation-specific Vp-Vs relationships:

**Relationship types:**
- `linear`: Vs = a·Vp + b (linear relationship, coefficients a and b)
- `ratio_constant`: Vp/Vs = a (constant ratio)
- `ratio_depth`: Vp/Vs = a·z + b (depth-dependent ratio, z in meters)
- `constant`: Vs = a (constant velocity)

**Source**: NAM Technical Addendum to Winningsplan Groningen 2016, sept2017_velo_model.xlsx

## Notes

- The k-values represent velocity gradients and are essential for accurate velocity calculations at any depth within each stratigraphic unit
- VELMOD 3.2 k-values differ slightly from 3.1 due to model updates based on new data
- VELMOD 4 k-values are based on integrated seismic stacking velocities
- The ZE (Zechstein) unit has k=0 in all versions (constant velocity)
