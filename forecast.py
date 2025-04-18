# forecast.py

import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
import plotly.graph_objects as go
from datetime import datetime
import logging
import functools
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create LRU cache for forecasts to avoid redundant calculations
@functools.lru_cache(maxsize=50)
def cached_forecast(product, future_steps, data_key=None):
    """Cached version of forecast_demand to improve performance for repeated queries."""
    if data_key:
        # If using custom data, we need to handle it differently
        # as pandas DataFrame is not hashable for caching
        if not isinstance(data_key, str):
            return forecast_demand(product, future_steps, data=data_key)
        
        # Load data from cache or file based on the key
        try:
            from pandas import read_csv
            data = read_csv(data_key)
            return forecast_demand(product, future_steps, data=data)
        except Exception as e:
            logger.error(f"Error in cached_forecast: {str(e)}")
            raise e
    else:
        # Use default data
        return forecast_demand(product, future_steps)

def forecast_demand(product, future_steps, data=None):
    """
    Generate demand forecasts for the specified product.
    
    Args:
        product (str): The product name to forecast
        future_steps (int): Number of days to forecast into the future
        data (DataFrame, optional): Custom dataset to use instead of default
        
    Returns:
        dict: Dictionary containing forecast results and metrics
    """
    start_time = time.time()
    logger.info(f"Starting forecast for {product} with {future_steps} days horizon")
    
    if data is None:
        try:
            from pandas import read_csv
            data = read_csv("demand_inventory.csv")
            data['Date'] = pd.to_datetime(data['Date'], format='%d-%m-%Y')
        except Exception as e:
            logger.error(f"Error loading default dataset: {str(e)}")
            raise e
    
    # Filter and prepare data for the selected product
    product_data = data[data['Product'] == product].copy()
    if len(product_data) == 0:
        raise ValueError(f"No data found for product: {product}")
    
    product_data = product_data.sort_values('Date')
    time_series = product_data.set_index('Date')['Demand']
    
    # Check if we have enough data points
    if len(time_series) < 10:
        raise ValueError(f"Not enough data points for product '{product}'. Need at least 10, got {len(time_series)}.")
    
    # Optimize SARIMAX model parameters based on time series characteristics
    # This is a simplified approach - for a full solution we would use auto_arima
    order = (1, 1, 1)
    seasonal_order = (1, 1, 1, 7)  # Assuming weekly seasonality
    
    # Fit SARIMAX model with progress logging
    logger.info(f"Fitting SARIMAX model for {product}")
    try:
        model = SARIMAX(
            time_series, 
            order=order, 
            seasonal_order=seasonal_order,
            enforce_stationarity=False,  # Allow non-stationary behavior
            enforce_invertibility=False   # Allow non-invertible behavior
        )
        model_fit = model.fit(disp=False, maxiter=200)
        
        # Forecast future demand
        predictions = model_fit.predict(
            start=len(time_series), 
            end=len(time_series) + future_steps - 1
        ).astype(int)
        
        # Ensure predictions are non-negative
        predictions = np.maximum(predictions, 0)
        
        future_dates = pd.date_range(
            start=time_series.index[-1] + pd.DateOffset(days=1), 
            periods=future_steps, 
            freq='D'
        )
        forecasted_demand = pd.Series(predictions, index=future_dates)
        
        # Inventory calculations with improved metrics
        lead_time = 1  # Default lead time (days)
        service_level = 0.95  # 95% service level
        holding_cost = 0.1  # Cost of holding inventory
        stockout_cost = 10  # Cost of stockout
        
        initial_inventory = product_data['Inventory'].iloc[-1]
        
        # Calculate safety stock based on forecast variability
        forecast_std = forecasted_demand.std()
        z = np.abs(np.percentile(np.random.normal(0, 1, 10000), 100 * service_level))
        
        # Economic Order Quantity calculation (simplified)
        order_quantity = np.ceil(forecasted_demand.mean() * 2 + z * forecast_std).astype(int)
        reorder_point = forecasted_demand.mean() * lead_time + z * forecast_std * np.sqrt(lead_time)
        safety_stock = reorder_point - forecasted_demand.mean() * lead_time
        
        # Cost calculations
        total_holding_cost = holding_cost * (initial_inventory + 0.5 * order_quantity)
        stockout_probability = 1 - service_level
        expected_stockout = stockout_probability * forecasted_demand.mean() * lead_time
        total_stockout_cost = stockout_cost * expected_stockout
        total_cost = total_holding_cost + total_stockout_cost
        
        # Create interactive Plotly figure with improved visualization
        fig = go.Figure()
        
        # Add historical data
        fig.add_trace(go.Scatter(
            x=time_series.index,
            y=time_series.values,
            name='Historical Demand',
            line=dict(color='blue', width=2),
            mode='lines+markers'
        ))
        
        # Add forecast data
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=predictions,
            name='Forecast',
            line=dict(color='orange', width=2, dash='dot'),
            mode='lines+markers'
        ))
        
        # Add confidence intervals
        forecast_std = max(forecast_std, 5)  # Minimum std to make interval visible
        
        upper_bound = predictions + 1.96 * forecast_std
        lower_bound = np.maximum(predictions - 1.96 * forecast_std, 0)  # Ensure non-negative
        
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=upper_bound,
            fill=None,
            mode='lines',
            line=dict(width=0),
            showlegend=False
        ))
        
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=lower_bound,
            fill='tonexty',
            mode='lines',
            line=dict(width=0),
            fillcolor='rgba(255,165,0,0.2)',
            name='95% Confidence Interval'
        ))
        
        # Show reorder point as a horizontal line
        fig.add_trace(go.Scatter(
            x=[time_series.index[0], future_dates[-1]],
            y=[reorder_point, reorder_point],
            mode='lines',
            line=dict(color='red', width=1, dash='dash'),
            name='Reorder Point'
        ))
        
        # Update layout for better visualization
        fig.update_layout(
            title=f'Demand Forecast for {product}',
            xaxis_title='Date',
            yaxis_title='Demand',
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=20, r=20, t=60, b=20),
            plot_bgcolor='white'
        )
        
        # Convert figure to JSON for frontend rendering
        plot_json = fig.to_json()
        
        end_time = time.time()
        logger.info(f"Forecast for {product} completed in {end_time - start_time:.2f} seconds")
        
        # Format dates for output
        historical_dates = [d.strftime('%Y-%m-%d') for d in time_series.index.tolist()]
        forecast_dates = [d.strftime('%Y-%m-%d') for d in future_dates.tolist()]
        
        return {
            "order_quantity": int(order_quantity),
            "reorder_point": round(float(reorder_point), 2),
            "safety_stock": round(float(safety_stock), 2),
            "total_cost": round(float(total_cost), 2),
            "plot_json": plot_json,
            "forecast_dates": forecast_dates,
            "forecast_values": predictions.tolist(),
            "historical_dates": historical_dates,
            "historical_values": time_series.values.tolist()
        }
    
    except Exception as e:
        logger.error(f"Error during forecasting for {product}: {str(e)}")
        raise ValueError(f"Error during forecasting: {str(e)}")