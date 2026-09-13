# VayuDrishti 🌫️

### Delhi NCR Air Pollution Forecasting and Decision Support System

**Smart India Hackathon — SIH26082**
**Team: Vayu Vision**

VayuDrishti is a prototype for forecasting air pollution in the Delhi NCR region. It combines air-quality observations with weather, fire-detection and satellite aerosol information to estimate future PM2.5 levels and provide some context about the factors affecting the prediction.

The project is intended as a working prototype for the SIH problem statement, rather than a full atmospheric-chemistry simulation.

---

## Live Prototype

The current prototype is deployed on Render:

**https://vayudrishti-5.onrender.com**

The deployed application contains the current version of the VayuDrishti dashboard and its backend services.

---

## What problem are we trying to solve?

Air pollution in Delhi NCR does not depend on one factor.

Pollution levels can change with:

* recent PM2.5 levels
* wind speed and direction
* temperature and humidity
* atmospheric boundary layer conditions
* regional fire activity
* seasonal patterns
* other local and regional conditions

A normal AQI dashboard mainly tells a user what the pollution level is at the moment. For this project, we wanted to go one step further and estimate how PM2.5 may change in the near future.

We also wanted the dashboard to provide some explanation around the prediction instead of showing only a number.

---

## What the prototype does

The current version includes the following parts:

* PM2.5 forecasting for up to 72 hours
* Delhi NCR monitoring-station map
* Current pollutant readings
* Weather and wind information
* Fire-detection information from NASA FIRMS
* Satellite aerosol information
* SHAP-based explanations for model predictions
* Dispersion/inversion information using weather variables
* AQI-based alerts
* Regional decision-support information
* AQI-scaled health guidance
* Nearby pollution-source information
* A what-if scenario simulator
* Model performance and validation information
* Automatic data refresh for the supported live data sources

Some components are prototype-level implementations. The limitations section below explains the parts that are simplified compared with a production or research-grade atmospheric model.

---

## How the system works

At a high level, the pipeline is:

                    DATA SOURCES
                         |
       +-----------------+------------------+
       |                 |                  |
     OpenAQ          Open-Meteo          NASA FIRMS
       |                 |                  |
       +-----------------+------------------+
                         |
                  Data processing
                         |
                  Feature creation
                         |
                   XGBoost model
                         |
                  PM2.5 forecast
                         |
              +----------+----------+
              |                     |
          SHAP analysis        Dashboard
              |                     |
       Prediction factors     React + FastAPI


The main idea is to combine the recent pollution signal with environmental variables rather than relying only on the latest PM2.5 value.

---

## Data sources

The current project uses the following sources.

| Source                   | What we use it for                                                            
| ------------------------ | ------------------------------------------------------------------------------|
| OpenAQ                   | PM2.5 and other pollutant observations                                        |
| Open-Meteo               | Weather, wind, humidity, temperature, precipitation and PBL-related variables |
| NASA FIRMS               | Satellite-based active fire detections                                        |
| NASA LANCE / Earthdata   | Near-real-time satellite aerosol information                                  |
| OpenStreetMap / Overpass | Map information and nearby industrial-source data                             |

### OpenAQ

https://openaq.org/

OpenAQ is used for pollution observations. The project uses the available station measurements for building the historical dataset and updating the application.

### Open-Meteo

https://open-meteo.com/

Weather information is used for both historical feature generation and forecasting-related inputs.

### NASA FIRMS

https://firms.modaps.eosdis.nasa.gov/

FIRMS provides satellite-based active-fire detections, which can be useful when looking at regional fire activity around Delhi NCR.

### NASA Earthdata

https://earthdata.nasa.gov/

Satellite aerosol information is used as an additional regional signal.

### OpenStreetMap

https://www.openstreetmap.org/

OpenStreetMap data is used for map-related information and locating nearby pollution-relevant facilities.

### Data-source decision

We initially planned to use the CPCB/data.gov.in API directly for pollution data. During development, the API was not reliable enough for our collection pipeline because of intermittent failures.

We therefore used OpenAQ as the pollution-data access layer instead.

---

## Machine learning model

The main forecasting model is **XGBoost**.

The model uses recent pollution information together with environmental variables to predict future PM2.5.

The current implementation uses an autoregressive forecasting approach, where previous predictions can become inputs for later forecast steps.

The project also uses **SHAP** to inspect the contribution of model features to individual predictions.

This gives the dashboard a way to answer a question such as:

> Why is the predicted PM2.5 level changing?

rather than displaying only the predicted value.

---

## Model validation

The model was trained using historical data covering approximately 18.5 months, from February 2025 to September 2026, with the dataset described in the current project results containing **643,836 rows from 58 verified government stations**.

The project also includes a held-out winter validation period.

### January 2026 validation

January 2026 was kept separate from the training data for the reported validation.

| Model                | MAE (µg/m³) | RMSE (µg/m³) |         R² |
| -------------------- | ----------: | -----------: | ---------: |
| Persistence baseline |       17.06 |        31.78 |     0.8030 |
| Original model       |       36.38 |        58.53 |     0.3318 |
| **Current model**    |   **17.18** |    **30.70** | **0.8161** |

The persistence baseline is important here because it gives us a simple reference point: instead of trying to build a complex model, we can ask how well simply carrying the recent pollution value forward would perform.

The current model performs slightly better than that baseline on the reported validation metrics.

---

## Performance at higher PM2.5 levels

We also looked separately at higher pollution ranges because performance during severe pollution is particularly relevant to the problem.

| PM2.5 range   | Previous model MAE | Current model MAE |
| ------------- | -----------------: | ----------------: |
| 100–200 µg/m³ |              28.30 |             14.56 |
| 200–300 µg/m³ |              82.94 |             24.78 |
| 300+ µg/m³    |             208.37 |             70.52 |

The current model shows a substantial reduction in error in these ranges compared with the earlier model.

These numbers should be interpreted together with the overall validation results rather than as a claim that the model is accurate for every severe-pollution event.

---

## Why XGBoost?

For this prototype, XGBoost gave us a practical way to work with:

* nonlinear relationships
* mixed environmental features
* recent pollution history
* relatively structured tabular data
* feature-importance and explanation methods

It also allowed us to iterate on the feature set without building a much larger deep-learning pipeline.

The current project is therefore focused on getting a useful forecasting prototype working first, rather than claiming that it is the final possible model architecture.

---

## Explainability

The project uses **SHAP** to examine individual model predictions.

The explanation layer is intended to show which input variables had the largest influence on a particular prediction.

Examples of factors that can contribute include:

* recent PM2.5 trend
* wind conditions
* temperature
* humidity
* boundary-layer conditions
* fire-related signals
* other model features

SHAP explanations should be interpreted as explanations of the trained model's prediction, not as proof that a particular variable physically caused the pollution event.

---

## Atmospheric conditions

The prototype also uses weather information to classify conditions that can affect pollution dispersion.

Wind and planetary boundary layer information are particularly useful because stagnant conditions can allow pollutants to remain concentrated near the surface.

This part of the system is intended as an operational indicator rather than a replacement for a full atmospheric-chemistry simulation.

---

## Fire and aerosol information

Regional fire activity is included using NASA FIRMS data.

The dashboard can use fire detections together with wind information to provide context about whether detected fires may be relevant to downwind areas.

Satellite aerosol information is also included as an additional regional signal.

These sources are treated as supporting information. A fire detection by itself does not establish that the detected fire caused a particular station's PM2.5 value.

---

## Scenario simulator

The prototype contains a what-if scenario component related to the interaction between aerosols and atmospheric boundary-layer conditions.

This is a simplified, literature-informed proxy.

It should **not** be interpreted as a complete WRF-Chem simulation or as a full numerical weather-chemistry model.

A full two-way weather and chemistry simulation would require a substantially larger modelling and computational setup.

---

## Dashboard

The frontend is built using React and Vite.

The dashboard brings together:

* monitoring stations
* pollution readings
* forecasts
* weather information
* map layers
* fire information
* explanations
* alerts
* decision-support information
* model-performance information

The backend provides the API layer used by the frontend.

---

## Technology used

### Frontend

* React
* Vite
* Tailwind CSS
* Leaflet
* OpenStreetMap

### Backend

* Python
* FastAPI

### Machine learning

* XGBoost
* SHAP
* scikit-learn

### Data storage

The current prototype uses CSV-based storage.

This is sufficient for the current prototype and dataset workflow. A production-scale version would require a proper database and more robust data-management infrastructure.

---

## Repository structure

The repository is organized around the parts of the project that we developed during the implementation.

```text
VayuDrishti/
│
├── backend/
│   └── main.py
│
├── frontend/
│   └── src/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── models/
│
├── notebooks/
│
├── scripts/
│   ├── data fetching
│   ├── data preparation
│   ├── dataset building
│   └── model training
│
├── utils/
│   └── aqi.py
│
├── .env.example
├── requirements.txt
└── README.md
```

The exact contents of some directories may change as the prototype is developed further.

Large/raw data files are not intended to be committed unnecessarily. The `.gitignore` file is used for files that should remain local.

---

## Important files

### `backend/main.py`

Contains the FastAPI application and the API endpoints used by the dashboard.

### `frontend/`

Contains the React dashboard.

### `scripts/`

Contains the scripts used during data collection, preparation, feature creation and model training.

### `models/`

Contains trained model artifacts used by the application.

### `utils/aqi.py`

Contains the AQI conversion utility used by the application.

### `notebooks/`

Used for analysis and experimentation during development.

---

## API endpoints

The backend currently exposes endpoints for the main dashboard functions.

| Endpoint                              | Purpose                                                      |
| ------------------------------------- | ------------------------------------------------------------ |
| `GET /stations`                       | Returns active monitoring stations and their readings        |
| `GET /current/{station_name}`         | Returns current information for a station                    |
| `GET /forecast/{station_name}`        | Returns the PM2.5 forecast                                   |
| `GET /explain/{station_name}`         | Returns the model explanation                                |
| `GET /dispersion/{station_name}`      | Returns dispersion/inversion information                     |
| `GET /alerts`                         | Returns active alerts                                        |
| `GET /decision-support`               | Returns regional decision-support information                |
| `GET /health-advisory/{station_name}` | Returns AQI-based guidance                                   |
| `GET /nearby-sources/{station_name}`  | Returns nearby pollution-relevant sources                    |
| `GET /correlation/{station_name}`     | Returns historical temperature/PM2.5 correlation information |
| `GET /aerosol`                        | Returns the latest available aerosol information             |
| `POST /simulate`                      | Runs the what-if scenario simulation                         |
| `GET /data-status`                    | Reports data freshness/status                                |

---

## Running the project locally

### 1. Clone the repository

```bash
git clone https://github.com/niharika2006bathula-star/VayuDrishti.git
cd VayuDrishti
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Add API credentials

Create a `.env` file in the project root.

Use `.env.example` as the reference.

```env
OPENAQ_API_KEY=your_key_here
FIRMS_MAP_KEY=your_key_here
EARTHDATA_TOKEN=your_token_here
```

Do not commit the actual `.env` file or expose API keys publicly.

### 4. Start the backend

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The backend will be available at:

```text
http://localhost:8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite development server normally runs at:

```text
http://localhost:5173
```

---

## API credentials

The project currently uses credentials/tokens for some external data services.

### OpenAQ

https://explore.openaq.org/register

### NASA FIRMS

https://firms.modaps.eosdis.nasa.gov/api/

### NASA Earthdata

https://urs.earthdata.nasa.gov/users/new

Only the required credentials should be placed in the local `.env` file.

---

## Limitations

There are several important limitations in the current prototype.

### 1. This is not a full WRF-Chem implementation

The project includes a simplified scenario/proxy component related to aerosol and PBL interaction.

It does not perform a complete two-way coupled weather-chemistry simulation.

A full WRF-Chem implementation would require a substantially different modelling setup and is outside the scope of the current prototype.

### 2. Weather data is regional

The current implementation uses a regional weather signal rather than generating a completely independent weather forecast for every monitoring station.

### 3. Satellite aerosol resolution

The satellite aerosol information is regional and has approximately 1° spatial resolution in the current implementation.

It should therefore not be interpreted as station-level aerosol measurements.

### 4. CSV storage

The prototype currently uses CSV-based storage.

For a production deployment with substantially larger data volumes and concurrent users, this would need to be replaced with a database such as PostgreSQL.

### 5. Forecast uncertainty

The current uncertainty/confidence information is based on historical model-error behaviour. It should not be interpreted as a formal probabilistic forecast unless a dedicated probabilistic/quantile model is introduced.

### 6. Model generalization

The available historical period is still limited compared with the amount of data that would ideally be available for a long-term operational forecasting system.

More years and more winter seasons would allow stronger evaluation of year-to-year generalization.

---

## Current status

The project is currently at the **working prototype stage**.

The main pipeline from data sources → processing → model → API → dashboard has been implemented and deployed for demonstration.

The next improvements are mainly around improving forecasting robustness, expanding the historical dataset and moving some prototype components toward production-grade infrastructure.

---

## Roadmap

Possible next steps include:

* Add more years of historical data

* Include additional winter seasons in validation

* Improve multi-step forecasting

Test direct forecasting models for individual horizons

* Improve uncertainty estimation using quantile regression

* Improve station-specific weather inputs

* Improve the scenario simulator and its underlying assumptions

* Move from CSV storage to PostgreSQL

* Improve deployment reliability and monitoring

* Expand the system to support additional regions

---

## Scientific basis

The project uses the idea that pollution levels are influenced not only by emissions but also by meteorological and atmospheric conditions that affect dispersion.

The aerosol-PBL feedback component was informed by the following work:

**Koundal et al., "Urban morphology amplifies extreme winter PM2.5 pollution through wind-driven ventilation suppression over Delhi."**

DOI:

`10.2139/ssrn.6570028`

The cited work is used as scientific background for the simplified feedback concept; the current prototype should not be considered an implementation of the full research methodology.

---

## Acknowledgements

This project uses data and services provided by:

* OpenAQ
* Open-Meteo
* NASA FIRMS
* NASA LANCE / Earthdata
* OpenStreetMap contributors

We thank the organizations and open-data communities that make these datasets and services available.

---

## Team

**Team Vayu Vision**
## Team

**Team Vayu Vision**

* **Team Lead:** Gogga Pradeep
* **Bantu Tanu Sri**
* **Bathula Niharika**
* **Nenavath Savitha**
* **K.Raghavendra**
* **Shaik Yasar Arafath**

**Project:** VayuDrishti
**SIH Problem Statement:** SIH26082


**Project:** VayuDrishti
**SIH Problem Statement:** SIH26082

---

## License

## License

No open-source license has been selected for this project at this time.



