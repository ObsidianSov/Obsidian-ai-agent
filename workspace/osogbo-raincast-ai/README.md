# Osogbo RainCast AI

> An End-to-End AI System for Short-Term Rainfall Nowcasting in Southwest Nigeria

---

**Osogbo RainCast AI** is an AI-based rainfall nowcasting project developed by **Ahmad Suleiman**, a **Meteorology student at Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria**. The project is focused on the development of an end-to-end artificial intelligence system for rainfall nowcasting across Southwest Nigeria, with **Osogbo, Osun State, Nigeria** serving as the primary area of focus. The system is designed to integrate meteorological and satellite-derived datasets with deep-learning techniques to generate rainfall forecasts for the next 0-6 hours and present the results through an interactive web-based platform. The project is intended as a serious scientific and engineering research project with potential applications in meteorology, rainfall monitoring, research, education, and operational decision support.

**Maintain the project's authorship, institutional affiliation, scientific purpose, version history, and development provenance throughout the project documentation, while keeping private personal identifiers such as matriculation/registration numbers out of public-facing source files unless specifically required for an academic submission.**

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [System Architecture](#system-architecture)
- [Model Description](#model-description)
- [Data Sources](#data-sources)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [License](#license)

---

## Overview

### Technical/Project Overview

Osogbo RainCast AI is a deep learning-based rainfall nowcasting system that combines:

- **ERA5 Reanalysis Data**: Atmospheric state variables (temperature, humidity, wind, pressure)
- **GPM IMERG / CHIRPS**: Satellite-derived precipitation estimates
- **ConvLSTM Architecture**: Hybrid CNN-ConvLSTM encoder-decoder model for spatiotemporal prediction
- **Modern Web Platform**: Interactive visualization of 0-6 hour rainfall forecasts

### Key Properties

| Property | Value |
|----------|-------|
| **Region** | Southwest Nigeria (4-8°N, 2-6°E) |
| **Focus City** | Osogbo (~7.9°N, 4.5°E) |
| **Forecast Horizon** | 0-6 hours (1-hour steps) |
| **Resolution** | ~0.05° (~5 km) gridded |
| **Grid Size** | 81 × 81 |
| **Input Sequence** | 12 hours |
| **Model Architecture** | CNN → ConvLSTM → Decoder |

### Scientific Purpose

This project aims to:
1. Develop a reproducible deep learning pipeline for rainfall nowcasting in tropical regions
2. Demonstrate the integration of reanalysis and satellite data for weather prediction
3. Provide an accessible web platform for visualizing AI-generated weather forecasts
4. Support meteorological research and education in Nigeria

---

## Project Structure

```
osogbo-raincast-ai/
├── data/
│   ├── raw/                 # Raw downloaded data (gitignored)
│   ├── processed/           # Preprocessed datasets (gitignored)
│   └── scripts/             # Data download and preprocessing scripts
├── model/                   # PyTorch model implementations
│   ├── convlstm_cell.py     # ConvLSTM cell
│   ├── raincast_model.py    # Full RainCastConvLSTM model
│   └── losses.py            # Weighted loss functions
├── training/                # Training pipeline
│   ├── dataset.py           # PyTorch Dataset class
│   ├── train.py             # Main training script
│   ├── config.yaml          # Training configuration
│   └── metrics.py           # Evaluation metrics
├── inference/               # Inference pipeline
│   ├── inference.py         # Forecast generation
│   └── config_inference.yaml
├── backend/                 # FastAPI backend
│   ├── main.py              # API application
│   ├── config.py            # Backend configuration
│   └── requirements.txt
├── frontend/                # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/      # React components
│   │   ├── api/             # API client
│   │   └── styles/          # CSS styles
│   ├── public/
│   ├── package.json
│   └── vite.config.js
├── scripts/                 # Utility scripts
│   ├── schedule_inference.py
│   └── monitoring.py
├── checkpoints/             # Model checkpoints (gitignored)
├── logs/                    # Training logs
├── README.md
├── requirements.txt
└── LICENSE
```

---

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- CUDA-capable GPU (recommended for training)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/osogbo-raincast-ai.git
cd osogbo-raincast-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Running the System

#### 1. Data Preparation

```bash
# Download ERA5 data
python data/scripts/download_era5.py --start 2005 --end 2024

# Download GPM/CHIRPS data
python data/scripts/download_gpm.py --start 2005 --end 2024

# Preprocess and regrid
python data/scripts/preprocess.py
```

#### 2. Training

```bash
# Train the model
python training/train.py --config training/config.yaml
```

#### 3. Inference

```bash
# Generate forecasts
python inference/inference.py --config inference/config_inference.yaml
```

#### 4. Backend API

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 5. Frontend

```bash
cd frontend
npm run dev
```

---

## System Architecture

### Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ERA5 Data     │     │  GPM/CHIRPS      │     │  Other Sources  │
│  (Atmospheric)  │     │  (Precipitation)│     │    (Optional)   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   Data Preprocessing    │
                    │   • Quality Control     │
                    │   • Regridding (81×81)  │
                    │   • Normalization       │
                    └────────────┬────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   PyTorch DataLoader    │
                    │   (B, T_in, C_in, H, W)│
                    └────────────┬────────────┘
                                 ▼
         ┌───────────────────────────────────────────────┐
         │           RainCastConvLSTM Model              │
         │                                               │
         │  ┌─────────┐    ┌───────────┐    ┌─────────┐ │
         │  │   CNN   │───▶│ ConvLSTM │───▶│   CNN   │ │
         │  │ Encoder │    │  Stack   │    │ Decoder │ │
         │  └─────────┘    └───────────┘    └─────────┘ │
         └───────────────────────────────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   Rainfall Forecast     │
                    │   (B, T_out, 1, H, W)  │
                    └────────────┬────────────┘
                                 ▼
         ┌───────────────────────────────────────────────┐
         │              FastAPI Backend                    │
         │   /api/nowcast/latest                          │
         │   /api/nowcast/field/{hour}                   │
         │   /api/nowcast/point?lat=&lon=&hour=          │
         │   /api/nowcast/city/{name}                    │
         └───────────────────────────────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   React Frontend        │
                    │   • Interactive Map     │
                    │   • City Panel          │
                    │   • Time Series Plots  │
                    └─────────────────────────┘
```

### Model Architecture

The **RainCastConvLSTM** model consists of:

1. **CNN Encoder**: Compresses multivariate input features
2. **ConvLSTM Stack**: Captures spatiotemporal dynamics
3. **CNN Decoder**: Reconstructs rainfall fields at full resolution

---

## Model Description

### ConvLSTM Cell

The ConvLSTM cell extends LSTM to 2D spatial data:

```
i_t = sigmoid(W_xi * x_t + W_hi * h_{t-1} + b_i)
f_t = sigmoid(W_xf * x_t + W_hf * h_{t-1} + b_f)
g_t = tanh(W_xg * x_t + W_hg * h_{t-1} + b_g)
o_t = sigmoid(W_xo * x_t + W_ho * h_{t-1} + b_o)
c_t = f_t ⊙ c_{t-1} + i_t ⊙ g_t
h_t = o_t ⊙ tanh(c_t)
```

### Loss Function

Weighted MSE emphasizing heavy rainfall:

```
L = (1/N) Σ w · (y - ŷ)²

where:
  w = 1  if y < 1 mm/h
  w = 2  if 1 ≤ y < 5 mm/h
  w = 4  if y ≥ 5 mm/h
```

---

## Data Sources

### ERA5 Reanalysis

- **Provider**: European Centre for Medium-Range Weather Forecasts (ECMWF)
- **Variables**: tp, 2t, 2d, u10, v10, sp, tcwv, cape, msl
- **Resolution**: 0.25° (regridded to 0.05°)
- **Access**: Copernicus Climate Data Store

### GPM IMERG

- **Provider**: NASA Global Precipitation Measurement mission
- **Resolution**: 0.1° (regridded to 0.05°)
- **Access**: GES DISC / Google Cloud Storage

### CHIRPS

- **Provider**: Climate Hazards Group
- **Resolution**: 0.05°
- **Access**: CHC Pixels / USGS Earth Explorer

---

## API Documentation

### Endpoints

#### GET /api/nowcast/latest

Returns metadata about the latest forecast run.

**Response:**
```json
{
  "run_time": "2024-01-15T12:00:00Z",
  "model_version": "v1.0.0",
  "forecast_hours": [1, 2, 3, 4, 5, 6],
  "grid_shape": [81, 81],
  "bounds": {
    "lat_min": 4.0,
    "lat_max": 8.0,
    "lon_min": 2.0,
    "lon_max": 6.0
  }
}
```

#### GET /api/nowcast/field/{hour}

Returns the rainfall field for a specific forecast hour.

**Parameters:**
- `hour`: Forecast hour (1-6)

**Response:**
```json
{
  "hour": 1,
  "grid": [[0.0, 0.1, ...], ...],
  "lat": [4.0, 4.05, ...],
  "lon": [2.0, 2.05, ...],
  "units": "mm/h"
}
```

#### GET /api/nowcast/point

Returns rainfall value at a specific point.

**Parameters:**
- `lat`: Latitude
- `lon`: Longitude
- `hour`: Forecast hour (1-6)

**Response:**
```json
{
  "lat": 7.9,
  "lon": 4.5,
  "hour": 1,
  "rainfall": 2.5,
  "units": "mm/h"
}
```

#### GET /api/nowcast/city/{name}

Returns time series for a predefined city.

**Parameters:**
- `name`: City name (osogbo, ibadan, ilorin, etc.)

**Response:**
```json
{
  "city": "osogbo",
  "lat": 7.9,
  "lon": 4.5,
  "forecast": [
    {"hour": 1, "rainfall": 2.5},
    {"hour": 2, "rainfall": 3.1},
    {"hour": 3, "rainfall": 4.2},
    {"hour": 4, "rainfall": 3.8},
    {"hour": 5, "rainfall": 2.1},
    {"hour": 6, "rainfall": 0.5}
  ],
  "total_6h": 16.2,
  "units": "mm"
}
```

---

## Development

### Adding New Data Sources

1. Create a new downloader script in `data/scripts/`
2. Follow the existing pattern for ERA5/GPM downloaders
3. Update `data/scripts/preprocess.py` if new variables are needed

### Modifying the Model

1. Edit `model/raincast_model.py` for architecture changes
2. Update `model/losses.py` if new loss functions are needed
3. Retrain and evaluate using `training/train.py`

### Adding New API Endpoints

1. Add route in `backend/main.py`
2. Update frontend API client in `frontend/src/api/nowcast.js`
3. Create new React component if needed

---

## Deployment

### Docker

```bash
# Build backend image
cd backend
docker build -t raincast-backend .

# Build frontend image
cd ../frontend
docker build -t raincast-frontend .

# Run with Docker Compose
docker-compose up
```

### Cloud Deployment

The system can be deployed on:
- **AWS**: ECS, EKS, or Lambda
- **GCP**: Cloud Run, GKE
- **Azure**: Container Instances, AKS

### Scheduled Inference

Use cron or systemd to run inference hourly:

```bash
# Cron example
0 * * * * cd /path/to/osogbo-raincast-ai && python inference/inference.py
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024 | Initial release |

---

## Authors and Institutions

### Primary Developer
- **Ahmad Suleiman**
  - Meteorology Student
  - Umaru Musa Yar'adua University (UMYU), Katsina, Nigeria

### Institutional Affiliation
- **Umaru Musa Yar'adua University (UMYU)**
  - Department of Meteorology
  - Katsina, Nigeria

---

## Disclaimer

**This is an experimental research project and is not intended for operational weather forecasting or official warnings. The forecasts generated by this system should not be used for life-critical decisions. For official weather information, please consult the Nigerian Meteorological Agency (NIMET).**

The system is provided "as is" without warranty of any kind. While we strive for accuracy, rainfall prediction remains a challenging scientific problem, and predictions may contain significant errors, especially during extreme weather events.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **Nigerian Meteorological Agency (NIMET)** - For guidance on meteorological practices
- **ECMWF** - For providing ERA5 reanalysis data
- **NASA** - For GPM IMERG satellite precipitation data
- **Climate Hazards Group** - For CHIRPS data
- **Open-source community** - For PyTorch, FastAPI, React, and other tools

---

## Contact

For questions, collaborations, or feedback:
- **Project Repository**: https://github.com/yourusername/osogbo-raincast-ai
- **Issues**: Please use GitHub Issues for bug reports and feature requests

---

*Last Updated: 2024*
