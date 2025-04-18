import os
import base64
import tempfile
import logging
from datetime import datetime
from io import BytesIO
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.platypus.flowables import HRFlowable
from xhtml2pdf import pisa
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure Jinja2 environment
env = Environment(loader=FileSystemLoader('templates'))

def create_forecast_report_platypus(product, days, forecast_results, dataset_source="Default Dataset"):
    """
    Generate a detailed PDF report for a product forecast using ReportLab Platypus.
    
    Args:
        product (str): The product name
        days (int): Number of forecast days
        forecast_results (dict): Dictionary with forecast data and metrics
        dataset_source (str): Source of the dataset used
        
    Returns:
        BytesIO: PDF report as a BytesIO object
    """
    try:
        logger.info(f"Generating PDF report for {product} with {days} days forecast")
        
        # Create BytesIO object to store the PDF
        buffer = BytesIO()
        
        # Create the PDF document using ReportLab
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
            title=f"Demand Forecast Report - {product}"
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading_style = styles['Heading1']
        subheading_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Create custom styles
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.gray,
            spaceAfter=12
        )
        
        table_title_style = ParagraphStyle(
            'TableTitle',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=6
        )
        
        # Store elements for the PDF
        elements = []
        
        # Add title
        elements.append(Paragraph(f"Demand Forecast Report", title_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Add report metadata
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        elements.append(Paragraph(f"Product: <b>{product}</b>", normal_style))
        elements.append(Paragraph(f"Forecast Period: {days} days", normal_style))
        elements.append(Paragraph(f"Report Generated: {current_date}", normal_style))
        elements.append(Paragraph(f"Data Source: {dataset_source}", normal_style))
        elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.gray, spaceBefore=10, spaceAfter=10))
        
        # Add executive summary
        elements.append(Paragraph("Executive Summary", heading_style))
        
        # Calculate summary metrics
        avg_forecast = np.mean(forecast_results["forecast_values"])
        forecast_trend = forecast_results["forecast_values"][-1] - forecast_results["forecast_values"][0]
        trend_direction = "upward" if forecast_trend > 0 else "downward" if forecast_trend < 0 else "stable"
        
        summary_text = f"""
        The forecast for <b>{product}</b> over the next {days} days shows an average daily demand of 
        <b>{avg_forecast:.2f}</b> units with a {trend_direction} trend. Based on this forecast, an order quantity 
        of <b>{forecast_results["order_quantity"]} units</b> is recommended with a reorder point of 
        <b>{forecast_results["reorder_point"]:.2f} units</b>.
        """
        elements.append(Paragraph(summary_text, normal_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Add key metrics as a table
        elements.append(Paragraph("Key Metrics", subheading_style))
        
        metrics_data = [
            ["Metric", "Value", "Description"],
            ["Order Quantity", f"{forecast_results['order_quantity']} units", "Recommended order size for optimal inventory"],
            ["Reorder Point", f"{forecast_results['reorder_point']:.2f} units", "Inventory level at which to place new orders"],
            ["Safety Stock", f"{forecast_results['safety_stock']:.2f} units", "Buffer stock to prevent stockouts"],
            ["Total Cost", f"${forecast_results['total_cost']:.2f}", "Estimated inventory holding and stockout costs"]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2*inch, 1.5*inch, 3*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Generate forecast visualization
        elements.append(Paragraph("Demand Forecast Visualization", subheading_style))
        
        # Create a Plotly figure for the forecast
        fig = go.Figure()
        
        # Add historical data
        historical_dates = [datetime.strptime(d, '%Y-%m-%d') for d in forecast_results["historical_dates"]]
        fig.add_trace(go.Scatter(
            x=historical_dates,
            y=forecast_results["historical_values"],
            name='Historical Demand',
            line=dict(color='blue', width=2),
            mode='lines+markers'
        ))
        
        # Add forecast data
        forecast_dates = [datetime.strptime(d, '%Y-%m-%d') for d in forecast_results["forecast_dates"]]
        fig.add_trace(go.Scatter(
            x=forecast_dates,
            y=forecast_results["forecast_values"],
            name='Forecast',
            line=dict(color='orange', width=2, dash='dot'),
            mode='lines+markers'
        ))
        
        # Add reorder point line
        all_dates = historical_dates + forecast_dates
        fig.add_trace(go.Scatter(
            x=[all_dates[0], all_dates[-1]],
            y=[forecast_results["reorder_point"], forecast_results["reorder_point"]],
            name='Reorder Point',
            line=dict(color='red', width=1, dash='dash'),
        ))
        
        # Update layout
        fig.update_layout(
            title=f'Demand Forecast for {product}',
            xaxis_title='Date',
            yaxis_title='Demand (Units)',
            legend=dict(orientation="h", y=1.1),
            width=500,
            height=400,
            margin=dict(l=40, r=20, t=60, b=40),
        )
        
        # Save the figure to a temporary file
        img_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name
        fig.write_image(img_path)
        
        # Add the image to the PDF
        elements.append(Image(img_path, width=450, height=300))
        elements.append(Spacer(1, 0.2*inch))
        
        elements.append(Paragraph("Forecast Data Table", subheading_style))
        elements.append(Paragraph("The following table shows the forecasted demand values for the next " + str(days) + " days:", normal_style))
        
        # Create a table for forecast data
        forecast_table_data = [["Date", "Forecasted Demand"]]
        for date, value in zip(forecast_results["forecast_dates"], forecast_results["forecast_values"]):
            forecast_table_data.append([date, f"{value:.2f}"])
        
        # Split the data into chunks if too large
        max_rows_per_table = 15
        if len(forecast_table_data) > max_rows_per_table + 1:
            current_row = 1
            while current_row < len(forecast_table_data):
                end_row = min(current_row + max_rows_per_table, len(forecast_table_data))
                chunk = [forecast_table_data[0]] + forecast_table_data[current_row:end_row]
                
                forecast_data_table = Table(chunk, colWidths=[2.5*inch, 2*inch])
                forecast_data_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ]))
                elements.append(forecast_data_table)
                elements.append(Spacer(1, 0.2*inch))
                
                if end_row < len(forecast_table_data):
                    elements.append(PageBreak())
                    elements.append(Paragraph("Forecast Data Table (continued)", subheading_style))
                
                current_row = end_row
        else:
            forecast_data_table = Table(forecast_table_data, colWidths=[2.5*inch, 2*inch])
            forecast_data_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ]))
            elements.append(forecast_data_table)
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Recommendations section
        elements.append(PageBreak())
        elements.append(Paragraph("Recommendations", heading_style))
        
        recommendations_text = f"""
        Based on the forecast analysis, we recommend the following actions:
        <br/><br/>
        1. <b>Inventory Management:</b> Maintain a safety stock of {forecast_results["safety_stock"]:.2f} units to prevent stockouts.
        <br/><br/>
        2. <b>Order Planning:</b> Place orders of {forecast_results["order_quantity"]} units when inventory reaches the reorder point of {forecast_results["reorder_point"]:.2f} units.
        <br/><br/>
        3. <b>Cost Optimization:</b> The estimated total cost for this inventory strategy is ${forecast_results["total_cost"]:.2f}, which balances holding costs and stockout risks.
        """
        elements.append(Paragraph(recommendations_text, normal_style))
        
        # Notes and assumptions
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Notes and Assumptions", subheading_style))
        
        notes_text = """
        This forecast is based on the following assumptions:
        <br/><br/>
        • Historical demand patterns will continue to be relevant for future demand.
        <br/>
        • The lead time for replenishment is constant.
        <br/>
        • A service level of 95% is targeted (5% acceptable stockout risk).
        <br/>
        • The forecast does not account for unexpected market disruptions or special events.
        <br/><br/>
        For best results, the forecast should be regularly updated as new data becomes available.
        """
        elements.append(Paragraph(notes_text, normal_style))
        
        # Footer with report generation info
        elements.append(Spacer(1, 0.5*inch))
        elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.gray, spaceBefore=10, spaceAfter=10))
        elements.append(Paragraph(f"Report generated by Smart Demand Forecast on {current_date}", info_style))
        
        # Build the PDF
        doc.build(elements)
        
        # Clean up the temporary image file
        try:
            os.unlink(img_path)
        except Exception as e:
            logger.warning(f"Error removing temporary image: {str(e)}")
        
        # Reset buffer position to the beginning
        buffer.seek(0)
        logger.info(f"PDF report for {product} generated successfully")
        
        return buffer
    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        raise e

def generate_html_report(product, days, forecast_results, dataset_source="Default Dataset"):
    """
    Generate an HTML report that can be converted to PDF with xhtml2pdf
    
    Args:
        product (str): The product name
        days (int): Number of forecast days
        forecast_results (dict): Dictionary with forecast data and metrics
        dataset_source (str): Source of the dataset used
        
    Returns:
        str: HTML content for the report
    """
    try:
        logger.info(f"Generating HTML report for {product}")
        
        # Instead of using a Plotly image, create an HTML table representation of the data
        # This avoids the need for kaleido or other image export libraries
        
        # Convert dates to proper format for display
        historical_dates = [datetime.strptime(d, '%Y-%m-%d').strftime('%b %d, %Y') for d in forecast_results["historical_dates"][-7:]]  # Show last 7 days of historical data
        forecast_dates = [datetime.strptime(d, '%Y-%m-%d').strftime('%b %d, %Y') for d in forecast_results["forecast_dates"]]
        
        # Create HTML for the chart visualization
        chart_html = """
        <div style="margin: 20px auto; max-width: 800px;">
            <h3 style="text-align: center;">Demand Forecast Visualization for {}</h3>
            <div style="display: flex; margin-bottom: 10px;">
                <div style="width: 50%; text-align: center;">
                    <div style="display: inline-block; width: 12px; height: 12px; background-color: #2c3e50; margin-right: 5px;"></div>
                    <span>Historical Data (Last 7 days)</span>
                </div>
                <div style="width: 50%; text-align: center;">
                    <div style="display: inline-block; width: 12px; height: 12px; background-color: #e74c3c; margin-right: 5px;"></div>
                    <span>Forecast Data</span>
                </div>
            </div>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Period</th>
                    <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Date</th>
                    <th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Demand</th>
                    <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Visual Indicator</th>
                </tr>
        """.format(product)
        
        # Add historical data rows
        for i, (date, value) in enumerate(zip(historical_dates, forecast_results["historical_values"][-7:])):
            bar_width = min(int(value / 2), 100)  # Scale the bar width
            chart_html += f"""
                <tr>
                    <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">Historical</td>
                    <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">{date}</td>
                    <td style="padding: 8px; text-align: right; border: 1px solid #ddd;">{value:.2f}</td>
                    <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">
                        <div style="background-color: #2c3e50; height: 15px; width: {bar_width}%;"></div>
                    </td>
                </tr>
            """
        
        # Add a separator row
        chart_html += """
            <tr>
                <td colspan="4" style="padding: 4px; background-color: #f8f9fa; text-align: center; border: 1px solid #ddd; font-style: italic;">
                    Forecast begins
                </td>
            </tr>
        """
        
        # Add forecast data rows (limit to first 14 days for readability)
        display_days = min(14, len(forecast_dates))
        for i, (date, value) in enumerate(zip(forecast_dates[:display_days], forecast_results["forecast_values"][:display_days])):
            bar_width = min(int(value / 2), 100)  # Scale the bar width
            chart_html += f"""
                <tr>
                    <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">Forecast</td>
                    <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">{date}</td>
                    <td style="padding: 8px; text-align: right; border: 1px solid #ddd;">{value:.2f}</td>
                    <td style="padding: 8px; text-align: left; border: 1px solid #ddd;">
                        <div style="background-color: #e74c3c; height: 15px; width: {bar_width}%;"></div>
                    </td>
                </tr>
            """
        
        # Add note if forecast is truncated
        if display_days < len(forecast_dates):
            chart_html += f"""
                <tr>
                    <td colspan="4" style="padding: 4px; background-color: #f8f9fa; text-align: center; border: 1px solid #ddd; font-style: italic;">
                        {len(forecast_dates) - display_days} more days of forecast data not shown in this visualization
                    </td>
                </tr>
            """
        
        # Close the table
        chart_html += """
            </table>
        </div>
        """
        
        # Use the HTML table as our chart image
        img_src = ""  # No image needed
        chart_visualization = chart_html
        
        # Prepare data for the template
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Calculate summary metrics
        avg_forecast = np.mean(forecast_results["forecast_values"])
        total_forecast = sum(forecast_results["forecast_values"])
        forecast_trend = forecast_results["forecast_values"][-1] - forecast_results["forecast_values"][0]
        trend_direction = "increasing" if forecast_trend > 0 else "decreasing" if forecast_trend < 0 else "stable"
        
        # Prepare forecast table data (limit to 20 rows for PDF readability)
        max_table_rows = 20
        if len(forecast_results["forecast_dates"]) > max_table_rows:
            forecast_table = list(zip(
                forecast_results["forecast_dates"][:max_table_rows], 
                forecast_results["forecast_values"][:max_table_rows]
            ))
            table_truncated = True
        else:
            forecast_table = list(zip(
                forecast_results["forecast_dates"], 
                forecast_results["forecast_values"]
            ))
            table_truncated = False
        
        # Render the HTML template
        template = env.get_template('report_template.html')
        html_content = template.render(
            product=product,
            days=days,
            current_date=current_date,
            dataset_source=dataset_source,
            order_quantity=forecast_results["order_quantity"],
            reorder_point="{:.2f}".format(forecast_results["reorder_point"]),
            safety_stock="{:.2f}".format(forecast_results["safety_stock"]),
            total_cost="{:.2f}".format(forecast_results["total_cost"]),
            avg_forecast="{:.2f}".format(avg_forecast),
            total_forecast="{:.2f}".format(total_forecast),
            trend_direction=trend_direction,
            forecast_trend="{:.2f}".format(abs(forecast_trend)),
            chart_visualization=chart_visualization,
            forecast_table=forecast_table,
            table_truncated=table_truncated
        )
        
        return html_content
    
    except Exception as e:
        logger.error(f"Error generating HTML report: {str(e)}")
        raise e

def html_to_pdf(html_content):
    """
    Convert HTML content to a PDF file using xhtml2pdf
    
    Args:
        html_content (str): HTML content to convert
        
    Returns:
        BytesIO: PDF file as BytesIO object
    """
    result = BytesIO()
    pdf_status = pisa.CreatePDF(html_content, dest=result)
    
    if pdf_status.err:
        logger.error("Error converting HTML to PDF")
        raise Exception("Error converting HTML to PDF")
    
    result.seek(0)
    return result

def generate_pdf_report(product, days, forecast_results, dataset_source="Default Dataset", use_html=True):
    """
    Main function to generate a PDF report using either direct ReportLab or HTML-based approach
    
    Args:
        product (str): The product name
        days (int): Number of forecast days
        forecast_results (dict): Dictionary with forecast data and metrics
        dataset_source (str): Source of the dataset used
        use_html (bool): Whether to use the HTML-based approach or direct ReportLab
        
    Returns:
        BytesIO: PDF report as a BytesIO object
    """
    if use_html:
        html_content = generate_html_report(product, days, forecast_results, dataset_source)
        return html_to_pdf(html_content)
    else:
        return create_forecast_report_platypus(product, days, forecast_results, dataset_source)