# DGM / Velmod velocity model extraction

## Description

This module provides functionality to extract seismic velocity profiles (1-D), sections (2-D), cubes (3-D), etc., from the DGM-diep V5 (stratigraphic units) and VELMOD3.1 (P-wave) models.

## Configuration

Package configuration is specified in [config/config.json](config/config.json).
This contains the current URLs of the relevant files.

A python environment can be created using the either pip, using [requirements.txt](requirements.txt) or conda using [environment.yml](environment.yml), i.e.:
```
conda env create --file environment.yml
conda activate dgm_velmod_sampler
```
or:
```
pip install -r requirements.txt
```

Download and extraction of the relevant files can be taken care of by the supplied [scripts/configure.py](scripts/configure.py) script.
```
python scripts/configure.py
```
The creation of xarray files representing DGM5 and VELMOD3.1 is taken care of by the [scripts/convert.py](scripts/convert.py) script, which also make use of the [config/config.json](config/config.json) file for the paths.
```
python scripts/convert.py
```
If desired the installation and conversion can be tested with the following command.
```
pytest --cov=.
```
After the above steps, the models can be used, following the examples in [examples/examples.ipnb](examples/examples.ipynb).

## Usage

See [examples/examples.ipnb](examples/examples.ipynb) for usage examples.

## Roadmap

At some point, the package may include code for the generation of random realizations of velocities within the uncertainty specifications of VELMOD3.1 and the generation of S-wave velocities on the basis of S-to-P relations.

At some point, the package may include the VELMOD 4b velocity models.

## License

MIT License

Copyright (c) 2023-2025 TNO

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
