# forecast.py

import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
import plotly.graph_objects as go
from datetime import datetime

# Read and process the dataset
data = pd.read_csv("demand_inventory.csv")
data['Date'] = pd.to_datetime(data['Date'], format='%d-%m-%Y')

def forecast_demand(product, future_steps, data=None):
    if data is None:
        from pandas import read_csv
        data = read_csv("demand_inventory.csv")
    product_data = data[data['Product'] == product].copy()
    product_data = product_data.sort_values('Date')
    time_series = product_data.set_index('Date')['Demand']

    # Fit SARIMAX model
    model = SARIMAX(time_series, order=(1, 1, 1), seasonal_order=(1, 1, 1, 2))
    model_fit = model.fit(disp=False)

    # Forecast future demand
    predictions = model_fit.predict(len(time_series), len(time_series) + future_steps - 1).astype(int)
    future_dates = pd.date_range(start=time_series.index[-1] + pd.DateOffset(days=1), periods=future_steps, freq='D')
    forecasted_demand = pd.Series(predictions, index=future_dates)

    # Inventory calculations
    lead_time = 1
    service_level = 0.95
    holding_cost = 0.1
    stockout_cost = 10
    initial_inventory = product_data['Inventory'].iloc[-1]

    z = np.abs(np.percentile(forecasted_demand, 100 * (1 - service_level)))
    order_quantity = np.ceil(forecasted_demand.mean() + z).astype(int)
    reorder_point = forecasted_demand.mean() * lead_time + z
    safety_stock = reorder_point - forecasted_demand.mean() * lead_time
    total_holding_cost = holding_cost * (initial_inventory + 0.5 * order_quantity)
    total_stockout_cost = stockout_cost * max(0, forecasted_demand.mean() * lead_time - initial_inventory)
    total_cost = total_holding_cost + total_stockout_cost

    # Create interactive Plotly figure
    fig = go.Figure()
    
    # Add historical data
    fig.add_trace(go.Scatter(
        x=time_series.index,
        y=time_series.values,
        name='Historical Demand',
        line=dict(color='blue')
    ))
    
    # Add forecast data
    fig.add_trace(go.Scatter(
        x=future_dates,
        y=predictions,
        name='Forecast',
        line=dict(color='orange', dash='dot')
    ))
    
    # Add confidence interval (example)
    fig.add_trace(go.Scatter(
        x=future_dates,
        y=predictions * 1.1,
        fill=None,
        mode='lines',
        line=dict(width=0),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=future_dates,
        y=predictions * 0.9,
        fill='tonexty',
        mode='lines',
        line=dict(width=0),
        fillcolor='rgba(255,165,0,0.2)',
        name='Confidence Interval'
    ))
    
    # Update layout
    fig.update_layout(
        title=f'Demand Forecast for {product}',
        xaxis_title='Date',
        yaxis_title='Demand',
        hovermode='x unified',
        plot_bgcolor='white'
    )

    # Convert figure to JSON for frontend rendering
    plot_json = fig.to_json()

    return {
        "order_quantity": order_quantity,
        "reorder_point": round(reorder_point, 2),
        "safety_stock": round(safety_stock, 2),
        "total_cost": round(total_cost, 2),
        "plot_json": plot_json,
        "forecast_dates": future_dates.tolist(),
        "forecast_values": predictions.tolist(),
        "historical_dates": time_series.index.tolist(),
        "historical_values": time_series.values.tolist()
    }
