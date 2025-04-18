from flask import Flask, render_template, request, send_file, session, redirect, url_for, jsonify, flash
import pandas as pd
import plotly.graph_objects as go
import os
from werkzeug.utils import secure_filename
import io
import tempfile
import logging
import time
import threading
import uuid
import numpy as np
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your_default_secret_key")

ALLOWED_EXTENSIONS = {'csv'}
UPLOAD_FOLDER = tempfile.mkdtemp()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Initialize a cache for recently uploaded datasets
class DatasetCache:
    def __init__(self, max_size=5):
        self.cache = {}
        self.max_size = max_size
        self.lock = threading.Lock()
    
    def get(self, key):
        with self.lock:
            return self.cache.get(key)
    
    def set(self, key, value):
        with self.lock:
            if len(self.cache) >= self.max_size:
                # Remove oldest item when cache is full
                oldest = list(self.cache.keys())[0]
                del self.cache[oldest]
            self.cache[key] = value

dataset_cache = DatasetCache()

# Forecasting cache for performance optimization
forecast_cache = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_date_column(df):
    """Attempts multiple date formats to convert the Date column."""
    date_formats = ['%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
    
    for fmt in date_formats:
        try:
            df['Date'] = pd.to_datetime(df['Date'], format=fmt)
            logger.info(f"Successfully parsed dates using format: {fmt}")
            return df, None
        except Exception as e:
            continue
    
    # If all formats fail, try pandas' flexible parser
    try:
        df['Date'] = pd.to_datetime(df['Date'])
        logger.info("Successfully parsed dates using pandas' flexible parser")
        return df, None
    except Exception as e:
        return df, f"Failed to parse date column: {str(e)}"

def validate_dataset(df):
    """Validates that the dataset has the required columns and formats."""
    required_columns = {'Date', 'Product', 'Demand', 'Inventory'}
    
    # Check for missing columns
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        return False, f"Missing required columns: {', '.join(missing)}"
    
    # Process date column
    df, date_error = preprocess_date_column(df)
    if date_error:
        return False, date_error
    
    # Convert numeric columns
    try:
        df['Demand'] = pd.to_numeric(df['Demand'])
        df['Inventory'] = pd.to_numeric(df['Inventory'])
    except Exception as e:
        return False, f"Error converting numeric columns: {str(e)}"
    
    # Check for missing values
    missing_values = df[list(required_columns)].isnull().sum()
    if missing_values.sum() > 0:
        missing_cols = ", ".join(f"{col} ({count} missing)" 
                              for col, count in missing_values.items() 
                              if count > 0)
        return False, f"Dataset contains missing values: {missing_cols}"
    
    # Ensure there are enough data points for each product
    products = df['Product'].unique()
    for product in products:
        product_data = df[df['Product'] == product]
        if len(product_data) < 10:  # Minimum data points needed for forecasting
            return False, f"Not enough data points for product '{product}'. At least 10 required, got {len(product_data)}."
    
    # Standardize date format to the model's expected format
    df['Date'] = df['Date'].dt.strftime('%d-%m-%Y')
    
    return True, df

# Load default dataset and get unique products
try:
    data = pd.read_csv("demand_inventory.csv")
    data['Date'] = pd.to_datetime(data['Date'], format='%d-%m-%Y')
    products = sorted(data['Product'].unique())
except Exception as e:
    logger.error(f"Error loading default dataset: {str(e)}")
    data = pd.DataFrame(columns=['Date', 'Product', 'Demand', 'Inventory'])
    products = []

@app.route("/", methods=["GET"])
def index():
    """Home page with product selection and forecasting form."""
    return render_template("index.html", products=products)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    """Dedicated page for uploading and preprocessing datasets."""
    error_message = None
    success_message = None
    preview_data = None
    upload_products = None
    
    if request.method == "POST":
        # Check if a file was uploaded
        if 'dataset' not in request.files:
            error_message = "No file part in the request"
        else:
            file = request.files['dataset']
            if file.filename == '':
                error_message = "No file selected"
            elif file and allowed_file(file.filename):
                try:
                    # Process the uploaded file
                    filename = secure_filename(file.filename)
                    logger.info(f"Processing uploaded file: {filename}")
                    
                    # Read the file
                    df = pd.read_csv(file)
                    
                    # Preprocess column names (case-insensitive mapping)
                    rename_map = {}
                    for col in df.columns:
                        col_lower = col.lower()
                        if 'product' in col_lower or 'item' in col_lower:
                            rename_map[col] = 'Product'
                        elif 'demand' in col_lower or 'sales' in col_lower or 'unit' in col_lower:
                            rename_map[col] = 'Demand'
                        elif 'inventory' in col_lower or 'stock' in col_lower:
                            rename_map[col] = 'Inventory'
                        elif 'date' in col_lower:
                            rename_map[col] = 'Date'
                    
                    # Apply detected column mappings
                    if rename_map:
                        df = df.rename(columns=rename_map)
                    
                    # Validate the dataset
                    valid, result = validate_dataset(df)
                    
                    if valid:
                        # Generate a unique ID for this dataset
                        cache_id = str(uuid.uuid4())
                        # Store validated dataframe in cache
                        dataset_cache.set(cache_id, result)
                        session['uploaded_dataset_id'] = cache_id
                        
                        # Create preview data
                        preview_data = result.head(5).to_html(
                            classes="table table-striped table-hover", 
                            index=False
                        )
                        
                        upload_products = sorted(result['Product'].unique())
                        success_message = f"Dataset successfully processed with {len(result)} rows and {len(upload_products)} products"
                    else:
                        error_message = result
                        
                except Exception as e:
                    logger.error(f"Error processing uploaded file: {str(e)}")
                    error_message = f"Error processing file: {str(e)}"
            else:
                error_message = f"Invalid file type. Please upload a CSV file."
    
    # If we have a dataset in the session, retrieve it for preview
    elif 'uploaded_dataset_id' in session:
        cache_id = session['uploaded_dataset_id']
        cached_df = dataset_cache.get(cache_id)
        
        if cached_df is not None:
            preview_data = cached_df.head(5).to_html(
                classes="table table-striped table-hover",
                index=False
            )
            upload_products = sorted(cached_df['Product'].unique())
            success_message = f"Using previously uploaded dataset with {len(cached_df)} rows and {len(upload_products)} products"
    
    return render_template(
        "upload.html", 
        error_message=error_message,
        success_message=success_message,
        preview_data=preview_data,
        products=upload_products
    )

@app.route("/predict", methods=["POST"])
def predict():
    """Generate forecast based on selected parameters."""
    start_time = time.time()
    
    try:
        # Get form data
        product = request.form['product']
        days = int(request.form['days'])
        show_graph = 'showGraph' in request.form
        
        logger.info(f"Forecasting for product: {product}, days: {days}")
        
        # Check if we should use an uploaded dataset
        if 'uploaded_dataset_id' in session:
            cache_id = session['uploaded_dataset_id']
            logger.info(f"Using uploaded dataset with ID: {cache_id}")
            
            df = dataset_cache.get(cache_id)
            if df is None:
                return render_template("error.html", 
                    error_message="Uploaded dataset no longer available. Please upload again.")
            
            # Verify product exists in the dataset
            if product not in df['Product'].unique():
                return render_template("error.html", 
                    error_message=f"Selected product '{product}' not found in uploaded dataset")
            
            # Ensure Date is in datetime format for the forecasting function
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
            
            # Use imported forecast_demand function
            from forecast import forecast_demand
            result = forecast_demand(product, days, data=df)
        else:
            # Use default dataset
            from forecast import forecast_demand
            result = forecast_demand(product, days)
        
        # Prepare CSV data
        csv_data = ["Date,Value"]
        historical_data = list(zip(result["historical_dates"], result["historical_values"]))
        forecast_data = list(zip(result["forecast_dates"], result["forecast_values"]))
        
        for date, value in historical_data:
            csv_data.append(f'"{date}",{value}')
        for date, value in forecast_data:
            csv_data.append(f'"{date}",{value}')
            
        csv_content = "\n".join(csv_data)
        
        end_time = time.time()
        processing_time = round(end_time - start_time, 2)
        logger.info(f"Forecast completed in {processing_time} seconds")
        
        return render_template(
            "results.html",
            product=product,
            days=days,
            show_graph=show_graph,
            order_quantity=result["order_quantity"],
            reorder_point=result["reorder_point"],
            safety_stock=result["safety_stock"],
            total_cost=result["total_cost"],
            historical_data=historical_data,
            forecast_data=forecast_data,
            csv_data=csv_content,
            processing_time=processing_time
        )
    except Exception as e:
        logger.error(f"Error in predict route: {str(e)}")
        return render_template("error.html", error_message=str(e))

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Dashboard showing combined forecasts for all products."""
    try:
        # Determine which dataset to use
        if 'uploaded_dataset_id' in session:
            cache_id = session['uploaded_dataset_id']
            df = dataset_cache.get(cache_id)
            if df is None:
                return render_template("error.html", 
                    error_message="Uploaded dataset no longer available. Please upload again.")
            
            use_products = sorted(df['Product'].unique())
            # Ensure Date is in datetime format
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
        else:
            use_products = products
            df = None
        
        # Prepare data for the dashboard
        forecasts = []
        demand_forecasts = []
        
        # Import forecasting function
        from forecast import forecast_demand
        
        # Generate forecasts for each product (with 30-day default horizon)
        for product in use_products:
            try:
                if df is not None:
                    f = forecast_demand(product, 30, data=df)
                else:
                    f = forecast_demand(product, 30)
                
                forecasts.append(f)
                forecast_series = pd.Series(
                    f["forecast_values"],
                    index=f["forecast_dates"]
                )
                demand_forecasts.append((product, forecast_series))
            except Exception as e:
                logger.error(f"Error forecasting for {product}: {str(e)}")
        
        total_forecasted_demand = sum(sum(f["forecast_values"]) for f in forecasts)
        inventory_levels = {product: f["order_quantity"] for product, f in zip(use_products, forecasts)}
        
        # Generate combined plot
        fig = go.Figure()
        for product, series in demand_forecasts:
            series = series.sort_index()
            fig.add_trace(go.Scatter(
                x=series.index,
                y=series.values,
                mode='lines+markers',
                name=product
            ))
        
        fig.update_layout(
            title="Forecasted Demand for All Products",
            xaxis_title="Date",
            yaxis_title="Forecasted Demand",
            legend_title="Product",
            width=1000,
            height=600
        )
        
        # Save plot to HTML string
        plot_html = fig.to_html(full_html=False)
        
        # Get dataset source for UI display
        dataset_source = "Uploaded Dataset" if 'uploaded_dataset_id' in session else "Default Dataset"
        
        return render_template("dashboard.html", 
                           total_forecasted_demand=total_forecasted_demand,
                           inventory_levels=inventory_levels,
                           plot_html=plot_html,
                           dataset_source=dataset_source)
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        return render_template("error.html", error_message=str(e))

@app.route("/clear_dataset", methods=["POST"])
def clear_dataset():
    """Clear the uploaded dataset and return to default."""
    if 'uploaded_dataset_id' in session:
        del session['uploaded_dataset_id']
    return redirect(url_for('index'))

@app.route("/download_forecast_csv/<product>/<int:days>")
def download_forecast_csv(product, days):
    """Download forecast results as CSV file."""
    try:
        # Determine which dataset to use
        if 'uploaded_dataset_id' in session:
            cache_id = session['uploaded_dataset_id']
            df = dataset_cache.get(cache_id)
            if df is None:
                return render_template("error.html", 
                    error_message="Uploaded dataset no longer available. Please upload again.")
            
            # Verify product exists in the dataset
            if product not in df['Product'].unique():
                return render_template("error.html", 
                    error_message=f"Selected product '{product}' not found in uploaded dataset")
            
            # Ensure Date is in datetime format
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
            
            # Import forecasting function
            from forecast import forecast_demand
            
            # Generate forecast
            result = forecast_demand(product, days, data=df)
        else:
            # Use default dataset
            from forecast import forecast_demand
            result = forecast_demand(product, days)
        
        # Create DataFrame from forecast results
        historical_df = pd.DataFrame({
            'Date': result["historical_dates"],
            'Type': ['Historical'] * len(result["historical_dates"]),
            'Value': result["historical_values"]
        })
        
        forecast_df = pd.DataFrame({
            'Date': result["forecast_dates"],
            'Type': ['Forecast'] * len(result["forecast_dates"]),
            'Value': result["forecast_values"]
        })
        
        # Combine historical and forecast data
        combined_df = pd.concat([historical_df, forecast_df])
        
        # Create a BytesIO object to store the CSV
        csv_buffer = io.BytesIO()
        combined_df.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_buffer.seek(0)
        
        # Create a filename with date stamp
        today = datetime.now().strftime('%Y%m%d')
        filename = f"{product}_forecast_{today}.csv"
        
        return send_file(
            csv_buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error generating CSV: {str(e)}")
        return render_template("error.html", error_message=str(e))

@app.route("/download_all_forecasts")
def download_all_forecasts():
    """Download forecasts for all products as a single CSV."""
    try:
        # Determine which dataset to use
        from forecast import forecast_demand
        
        if 'uploaded_dataset_id' in session:
            cache_id = session['uploaded_dataset_id']
            df = dataset_cache.get(cache_id)
            if df is None:
                return render_template("error.html", 
                    error_message="Uploaded dataset no longer available. Please upload again.")
            
            use_products = sorted(df['Product'].unique())
            # Ensure Date is in datetime format
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
        else:
            use_products = products
            df = None
        
        # Generate forecasts for each product
        all_forecasts = []
        
        for product in use_products:
            try:
                if df is not None:
                    result = forecast_demand(product, 30, data=df)
                else:
                    result = forecast_demand(product, 30)
                
                # Create DataFrame for this product's forecast
                product_df = pd.DataFrame({
                    'Date': result["forecast_dates"],
                    'Product': [product] * len(result["forecast_dates"]),
                    'Forecast': result["forecast_values"]
                })
                
                all_forecasts.append(product_df)
                
            except Exception as e:
                logger.error(f"Error forecasting for {product}: {str(e)}")
        
        # Combine all product forecasts
        if all_forecasts:
            combined_df = pd.concat(all_forecasts)
            
            # Create a BytesIO object to store the CSV
            csv_buffer = io.BytesIO()
            combined_df.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_buffer.seek(0)
            
            # Create a filename with date stamp
            today = datetime.now().strftime('%Y%m%d')
            filename = f"all_products_forecast_{today}.csv"
            
            return send_file(
                csv_buffer,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
        else:
            return render_template("error.html", error_message="No forecasts could be generated")
    except Exception as e:
        logger.error(f"Error generating CSV for all products: {str(e)}")
        return render_template("error.html", error_message=str(e))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)