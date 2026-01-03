# Smart Demand Forecast

Smart Demand Forecast is a Flask-based web application designed for demand forecasting and inventory management. It allows users to upload their own datasets, generate demand forecasts, view dashboards, and download detailed reports in PDF and CSV formats.

## Features

- Upload CSV datasets with product demand and inventory data.
- Validate and preprocess uploaded datasets.
- Generate demand forecasts for selected products over customizable time horizons.
- View interactive dashboards showing forecasted demand for all products.
- Download forecast results as CSV files.
- Generate comprehensive PDF reports with visualizations and key inventory metrics.
- Uses SARIMAX-based forecasting logic (in `forecast.py`).
- Caching mechanism for uploaded datasets to improve performance.

## Installation and Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create and activate a Python virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Set the `SESSION_SECRET` environment variable for Flask session security:
   ```bash
   export SESSION_SECRET="your_secret_key"  # On Windows use set instead of export
   ```

5. Run the Flask application:
   ```bash
   python app.py
   ```

6. Open your browser and navigate to `http://localhost:5000` to access the app.

## Usage Instructions

- **Home Page:** Select a product and forecast horizon to generate demand forecasts.
- **Upload Dataset:** Upload your own CSV file with columns `Date`, `Product`, `Demand`, and `Inventory`. The app validates and preprocesses the data.
- **Dashboard:** View combined forecasts for all products with interactive charts.
- **Download Forecasts:** Download forecast data as CSV files for individual products or all products.
- **Download Reports:** Generate and download detailed PDF reports with forecast visualizations and inventory recommendations.

## File Structure Overview

```
.
├── app.py                  # Main Flask application
├── forecast.py             # Forecasting logic using SARIMAX
├── report_generator.py     # PDF report generation utilities
├── demand_inventory.csv    # Default dataset
├── templates/              # HTML templates for the web UI
├── static/                 # Static assets (CSS, JS, images)
├── attached_assets/        # Additional assets and example files
├── DemandForecast.ipynb    # Jupyter notebook for data analysis/modeling
├── README.md               # Project documentation (this file)
└── requirements.txt        # Python dependencies
```

## Dependencies

- Flask
- pandas
- numpy
- plotly
- statsmodels
- reportlab
- xhtml2pdf
- Jinja2
- Werkzeug
- 
(Ensure to install all dependencies via `pip install -r requirements.txt`)

---

This project provides a comprehensive solution for demand forecasting and inventory optimization with an easy-to-use web interface and detailed reporting capabilities.
