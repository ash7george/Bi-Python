import pandas as pd
import plotly.express as px
from flask import Flask, request, render_template
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Your Tableau embed code
TABLEAU_EMBED_CODE = '''
<div class='tableauPlaceholder' id='viz1729614426279' style='position: relative'>
    <noscript><a href='#'><img alt=' ' src='https://public.tableau.com/static/images/Bi/BirdStrikesUSA/Dashboard1/1_rss.png' style='border: none' /></a></noscript>
    <object class='tableauViz' style='display:none;'>
        <param name='host_url' value='https%3A%2F%2Fpublic.tableau.com%2F' />
        <param name='embed_code_version' value='3' />
        <param name='site_root' value='' />
        <param name='name' value='BirdStrikesUSA/Dashboard1' />
        <param name='tabs' value='yes' />
        <param name='toolbar' value='yes' />
        <param name='static_image' value='https://public.tableau.com/static/images/Bi/BirdStrikesUSA/Dashboard1/1.png' />
        <param name='animate_transition' value='yes' />
        <param name='display_static_image' value='yes' />
        <param name='display_spinner' value='yes' />
        <param name='display_overlay' value='yes' />
        <param name='display_count' value='yes' />
        <param name='language' value='en-US' />
        <param name='filter' value='fullscreen=yes' />
    </object>
</div>
<script type='text/javascript'>
    var divElement = document.getElementById('viz1729614426279');
    var vizElement = divElement.getElementsByTagName('object')[0];
    if (divElement.offsetWidth > 800) {
        vizElement.style.minWidth='1366px';vizElement.style.maxWidth='100%';vizElement.style.minHeight='818px';vizElement.style.maxHeight=(divElement.offsetWidth*0.75)+'px';
    } else if (divElement.offsetWidth > 500) {
        vizElement.style.minWidth='1366px';vizElement.style.maxWidth='100%';vizElement.style.minHeight='818px';vizElement.style.maxHeight=(divElement.offsetWidth*0.75)+'px';
    } else {
        vizElement.style.width='100%';vizElement.style.minHeight='2250px';vizElement.style.maxHeight=(divElement.offsetWidth*1.77)+'px';
    }
    var scriptElement = document.createElement('script');
    scriptElement.src = 'https://public.tableau.com/javascripts/api/viz_v1.js';
    vizElement.parentNode.insertBefore(scriptElement, vizElement);
</script>
'''

@app.route('/')
def upload_file():
    return render_template('upload.html')

@app.route('/visualize', methods=['POST'])
def visualize():
    if 'file' not in request.files:
        return "No file part"

    file = request.files['file']

    if file.filename == '':
        return "No selected file"

    # Load the data
    df = pd.read_excel(file)

    # Ensure FlightDate is a datetime, coerce errors to NaT
    df['FlightDate'] = pd.to_datetime(df['FlightDate'], errors='coerce')

    # Drop rows with NaT in FlightDate
    df.dropna(subset=['FlightDate'], inplace=True)

    # Count occurrences by FlightDate
    daily_counts = df['FlightDate'].value_counts().reset_index()
    daily_counts.columns = ['FlightDate', 'Count']
    daily_counts['FlightDate'] = pd.to_datetime(daily_counts['FlightDate'])

    # Prepare data for the Random Forest model
    daily_counts.sort_values('FlightDate', inplace=True)
    daily_counts['Day'] = (daily_counts['FlightDate'] - daily_counts['FlightDate'].min()).dt.days

    # Train-test split
    X = daily_counts[['Day']]
    y = daily_counts['Count']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train the Random Forest model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Make predictions
    y_pred = model.predict(X_test)

    # Calculate statistics
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Make future predictions
    future_days = np.arange(X['Day'].max() + 1, X['Day'].max() + 31).reshape(-1, 1)  # Predict for the next 30 days
    future_counts = model.predict(future_days)

    # Prepare future data for visualization
    future_dates = pd.date_range(start=daily_counts['FlightDate'].max() + pd.Timedelta(days=1), periods=30)
    future_df = pd.DataFrame({'FlightDate': future_dates, 'Predicted Count': future_counts})

    # Create visualizations
    figures = []

    # Plot future predictions
    fig = px.line(future_df, x='FlightDate', y='Predicted Count', title='Predicted Future Bird Strikes', markers=True)
    figures.append(fig)

    # Wildlife strikes by species
    if 'Wildlife: Species' in df.columns:
        species_count = df['Wildlife: Species'].value_counts().reset_index()
        species_count.columns = ['Wildlife Species', 'Count']
        fig = px.bar(species_count, x='Wildlife Species', y='Count', title='Wildlife Strikes by Species', color='Count')
        figures.append(fig)

    # Weather conditions
    if 'Conditions: Sky' in df.columns:
        weather_count = df['Conditions: Sky'].value_counts().reset_index()
        weather_count.columns = ['Weather Condition', 'Count']
        fig = px.bar(weather_count, x='Weather Condition', y='Count', title='Wildlife Strikes by Weather Condition', color='Count')
        figures.append(fig)

    # Airport names
    if 'Airport: Name' in df.columns:
        airport_count = df['Airport: Name'].value_counts().reset_index()
        airport_count.columns = ['Airport Name', 'Count']
        fig = px.bar(airport_count, x='Airport Name', y='Count', title='Wildlife Strikes by Airport', color='Count')
        figures.append(fig)

    # Pilot warned
    if 'Pilot warned of birds or wildlife?' in df.columns:
        warning_count = df['Pilot warned of birds or wildlife?'].value_counts().reset_index()
        warning_count.columns = ['Pilot Warned', 'Count']
        fig = px.bar(warning_count, x='Pilot Warned', y='Count', title='Pilot Warnings about Wildlife', color='Count')
        figures.append(fig)

    # Generate HTML for each figure
    figures_html = ''.join([fig.to_html(full_html=False) for fig in figures])

    # Include the statistics in the HTML response
    stats_html = f'''
    <h2>Model Statistics</h2>
    <ul>
        <li>Mean Absolute Error (MAE): {mae:.2f}</li>
        <li>Mean Squared Error (MSE): {mse:.2f}</li>
        <li>R-squared (R²): {r2:.2f}</li>
    </ul>
    '''

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Visualizations</title>
    </head>
    <body>
        <h1>Visualizations</h1>
        <h2>-</h2>
        {TABLEAU_EMBED_CODE}
        <br>
        {stats_html}
        <br>
        {figures_html}
        <br>
        <a href="/">Upload another file</a>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)

#http://127.0.0.1:5000/