"""InvestView — Portfolio Dashboard Application."""

import dash
import dash_bootstrap_components as dbc
from dash import html

from components.navbar import create_navbar
from config import DEBUG, PORT
from db.database import init_db

# Initialize the database
init_db()

# Create the Dash app with multi-page support
app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
)

app.layout = html.Div([
    create_navbar(),
    dash.page_container,
])

if __name__ == "__main__":
    app.run(debug=DEBUG, port=PORT)
