"""Top navigation bar component."""

import dash_bootstrap_components as dbc
from dash import html


def create_navbar() -> dbc.Navbar:
    """Return the top navigation bar with links to all pages."""
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("InvestView", href="/", className="fw-bold"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Dashboard", href="/")),
                dbc.NavItem(dbc.NavLink("Positions", href="/positions")),
                dbc.NavItem(dbc.NavLink("Charts", href="/charts")),
                dbc.NavItem(dbc.NavLink("Macro", href="/macro")),
                dbc.NavItem(dbc.NavLink("Sync", href="/sync")),
            ], navbar=True),
        ]),
        color="primary",
        dark=True,
        className="mb-4",
    )
