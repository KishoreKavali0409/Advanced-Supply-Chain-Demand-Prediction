from flask import Flask, render_template, request, send_file, session, redirect, url_for
import pandas as pd
import plotly.graph_objects as go
from forecast import forecast_demand
import os
from werkzeug.utils import secure_filename
import io
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure secret key

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_dataset(df):
    required_columns = {'Date', 'Product', 'Demand', 'Inventory'}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    # Check date format
    try:
        pd.to_datetime(df['Date'], format='%d-%m-%Y')
    except Exception:
        raise ValueError("Date column must be in format DD-MM-YYYY")
    # Check for missing values
    if df[list(required_columns)].isnull().any().any():
        raise ValueError("Dataset contains missing values in required columns")
    return True

# Load default dataset and get unique products
data = pd.read_csv("demand_inventory.csv")
products = sorted(data['Product'].unique())

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", products=products)

@app.route("/predict", methods=["POST"])
def predict():
    try:
        product = request.form['product']
        days = int(request.form['days'])
        show_graph = 'showGraph' in request.form

        # Check if a file was uploaded
        if 'dataset' in request.files:
            file = request.files['dataset']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Read uploaded file into DataFrame
                df = pd.read_csv(file)
                
                # Preprocess dataset columns to match expected format
                rename_map = {
                    'Product ID': 'Product',
                    'Units Sold': 'Demand',
                    'Inventory Level': 'Inventory'
                }
                df = df.rename(columns=rename_map)
                
                # Convert Date column to expected format if needed
                try:
                    df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
                except Exception:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df['Date'] = df['Date'].dt.strftime('%d-%m-%Y')
                    df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
                
                # Validate dataset
                validate_dataset(df)
                
                # Use uploaded dataset for forecasting
                # Filter products from uploaded dataset
                uploaded_products = sorted(df['Product'].unique())
                if product not in uploaded_products:
                    raise ValueError(f"Selected product '{product}' not found in uploaded dataset")
                # Forecast using uploaded data
                result = forecast_demand(product, days, data=df)
                # After successful upload and forecast, redirect to homepage
                return render_template("index.html", products=uploaded_products)
            else:
                raise ValueError("Invalid file uploaded. Please upload a CSV file.")
        else:
            # Use default dataset
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

        return render_template(
            "results.html",
            product=product,
            show_graph=show_graph,
            order_quantity=result["order_quantity"],
            reorder_point=result["reorder_point"],
            safety_stock=result["safety_stock"],
            total_cost=result["total_cost"],
            historical_data=historical_data,
            forecast_data=forecast_data,
            csv_data=csv_content
        )
    except Exception as e:
        print(f"Error in predict route: {str(e)}")
        return render_template("error.html", error_message=str(e))

@app.route("/generate_combined_plot")
def generate_combined_plot():
    # Get all products
    products = sorted(data['Product'].unique())
    demand_forecasts = []
    
    # Get forecasts for all products
    for product in products:
        result = forecast_demand(product, 30)  # Using 30 days as default
        forecast_series = pd.Series(
            result["forecast_values"],
            index=result["forecast_dates"]
        )
        demand_forecasts.append((product, forecast_series))
    
    # Create combined figure
    fig = go.Figure()
    
    for product, series in demand_forecasts:
        series = series.sort_index()  # Ensure chronological order
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode='lines+markers',
                name=product
            )
        )
    
    fig.update_layout(
        title="Forecasted Demand for All Products",
        xaxis_title="Date",
        yaxis_title="Forecasted Demand",
        legend_title="Product",
        width=1000,
        height=600
    )
    
    # Save as HTML
    output_path = "static/combined_forecast.html"
    fig.write_html(output_path)
    
    # Return the HTML file
    return send_file(output_path, as_attachment=False)

@app.route("/dashboard", methods=["GET"])
def dashboard():
    # Prepare data for the dashboard
    forecasts = [forecast_demand(product, 30) for product in products]
    total_forecasted_demand = sum(sum(f["forecast_values"]) for f in forecasts)
    inventory_levels = {product: f["order_quantity"] for product, f in zip(products, forecasts)}

    # Generate combined plot
    demand_forecasts = []
    for product, f in zip(products, forecasts):
        forecast_series = pd.Series(
            f["forecast_values"],
            index=f["forecast_dates"]
        )
        demand_forecasts.append((product, forecast_series))
    
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

    return render_template("dashboard.html", 
                         total_forecasted_demand=total_forecasted_demand,
                         inventory_levels=inventory_levels,
                         plot_html=plot_html)

from flask import redirect, url_for

from flask import redirect, url_for

@app.route("/upload_forecast", methods=["GET"])
def upload_forecast():
    global uploaded_dataset
    products = sorted(uploaded_dataset['Product'].unique()) if uploaded_dataset is not None else None
    return render_template("upload_forecast.html",
                           products=products,
                           forecast_result=None,
                           selected_product=None,
                           days=None,
                           error_message=None)

@app.route("/upload_forecast/upload", methods=["POST"])
def upload_forecast_upload():
    global uploaded_dataset
    error_message = None
    if 'dataset' not in request.files:
        error_message = "No file part in the request."
        return render_template("upload_forecast.html", error_message=error_message)
    file = request.files['dataset']
    if file and allowed_file(file.filename):
        try:
            df = pd.read_csv(file)
            rename_map = {
                'Product ID': 'Product',
                'Units Sold': 'Demand',
                'Inventory Level': 'Inventory'
            }
            df = df.rename(columns=rename_map)
            try:
                df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
            except Exception:
                df['Date'] = pd.to_datetime(df['Date'])
                df['Date'] = df['Date'].dt.strftime('%d-%m-%Y')
                df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
            validate_dataset(df)
            uploaded_dataset = df
            return redirect(url_for('upload_forecast'))
        except Exception as e:
            error_message = f"Error processing file: {str(e)}"
            return render_template("upload_forecast.html", error_message=error_message)
    else:
        error_message = "Invalid file uploaded. Please upload a CSV file."
        return render_template("upload_forecast.html", error_message=error_message)

@app.route("/upload_forecast/forecast", methods=["POST"])
def upload_forecast_forecast():
    global uploaded_dataset
    error_message = None
    forecast_result = None
    selected_product = request.form.get("product")
    days = request.form.get("days")
    if uploaded_dataset is None:
        error_message = "No dataset uploaded. Please upload a dataset first."
        return render_template("upload_forecast.html", error_message=error_message)
    try:
        days = int(days)
        if selected_product not in uploaded_dataset['Product'].unique():
            error_message = f"Selected product '{selected_product}' not found in uploaded dataset."
        else:
            forecast_result = forecast_demand(selected_product, days, data=uploaded_dataset)
    except Exception as e:
        error_message = f"Error during forecasting: {str(e)}"
    products = sorted(uploaded_dataset['Product'].unique())
    return render_template("upload_forecast.html",
                           error_message=error_message,
                           products=products,
                           forecast_result=forecast_result,
                           selected_product=selected_product,
                           days=days)

@app.route("/download_forecast_csv")
def download_forecast_csv():
    global uploaded_dataset
    # This route assumes forecast_result is stored globally or passed via session - for simplicity, not implemented here
    # User can implement this as needed
    return "Download functionality not implemented yet."

if __name__ == "__main__":
    app.run(debug=True)
