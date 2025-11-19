FROM continuumio/miniconda3:latest

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install conda dependencies
RUN conda install -y -c conda-forge \
    python=3.10 \
    tifffile \
    dask \
    numpy \
    scikit-image \
    zarr \
    && conda clean -afy

# Install palom via pip
RUN pip install --no-cache-dir "palom[all]"

# Copy registration script
COPY register_akoya_palom.py /usr/local/bin/register_akoya_palom.py
RUN chmod +x /usr/local/bin/register_akoya_palom.py

# Set working directory
WORKDIR /work

# Set entrypoint
ENTRYPOINT ["/bin/bash"]
