import os
import dash_auth
import csv
import re
import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import dash
from dash import dcc
from dash import html
from dash.dependencies import Output, Input, State
import pygame
import subprocess
import time

pygame.mixer.init()

VALID_USERNAME_PASSWORD_PAIRS = {
    'admin': 'snore123',
    'merchant': 'ilovesnores'
}

def get_folders():
    return [folder for folder in os.listdir(os.getcwd()) if os.path.isdir(folder) and folder != 'assets']

def create_figure(df, snore_events):
    fig = px.line(df, x='datetime', y='position')
    fig.update_traces(line=dict(color='#6c757d'))

    for event in snore_events:
        last_position_before_event = df.loc[df['datetime'] < event[0], 'position'].iloc[-1]
        fig.add_trace(go.Scatter(x=[event[0]], y=[last_position_before_event], mode='markers', marker=dict(size=20, color='#FF5733', symbol='diamond', opacity=0.6), name='Snore Event'))

    fig.update_xaxes(title_text="—————— TIME ——————")
    fig.update_yaxes(title_text="—— ORIENTATION ——")
    fig.update_layout(
        title_text=f"BODY ORIENTATION AND SNORE EVENTS FOR SESSION",
        showlegend=False,
        hovermode="closest",
        plot_bgcolor='#E6E6FA',
        margin=dict(t=50, b=50, l=50, r=50),
    )
    return fig

def create_semi_circle_polar_plot(df, snore_event_times):
    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=df['datetime'].apply(lambda x: x.timestamp()),
        theta=df['position'],
        mode='lines',
        line=dict(color='#6c757d')
    ))

    # Add snore events as separate traces
    for event in snore_event_times:
        # Find the closest previous data point to the event
        prev_point = df.loc[df['datetime'] <= event].iloc[-1]

        fig.add_trace(go.Scatterpolar(
            r=[prev_point['datetime'].timestamp(), event.timestamp()],
            theta=[prev_point['position'], prev_point['position']],
            mode='markers',
            marker=dict(size=20, color='#FF5733', symbol='diamond', opacity=0.6),
            line=dict(color='#FF5733', width=3),
            name='Snore Event',
            showlegend=False
        ))
    min_datetime = df['datetime'].min()
    max_datetime = df['datetime'].max()
    min_timestamp = int(min_datetime.replace(tzinfo=datetime.timezone.utc).timestamp())
    max_timestamp = int(max_datetime.replace(tzinfo=datetime.timezone.utc).timestamp())

    range_min = min_timestamp - (max_timestamp - min_timestamp) * 0.1  # <-- Adjust the range to start at a lower value

    time_labels = []
    time_ticks = []
    for i in range(0, 11):
        ts = min_timestamp + (max_timestamp - min_timestamp) * i / 10
        time_labels.append(datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime('%H:%M:%S'))
        time_ticks.append(ts)

    fig.update_layout(
        polar=dict(
            bgcolor="#E6E6FA",
            radialaxis=dict(
                visible=True,
                range=[range_min, max_timestamp],  # <-- Update the range here
                tickmode='array',
                tickvals=time_ticks,
                ticktext=time_labels,
                tickfont=dict(size=10),
                tickangle=-45,
                showline=True,
                linewidth=1,
                linecolor="rgba(0, 0, 0, 0)"
            ),
            angularaxis=dict(
                tickmode='array',
                tickvals=list(range(-90, 91, 30)),
                ticktext=list(map(str, range(-90, 91, 30))),
                tickfont=dict(size=16),
                direction="clockwise",
                period=180,
                nticks=20,
                showline=True,
                linewidth=1,
                linecolor="rgba(0, 0, 0, 0)"
            ),
            sector=[0, 180]
        ),
        showlegend=False,
        margin=dict(t=50, b=50, l=50, r=50),
    )

    return fig


app = dash.Dash(__name__, title='SNOREPHEUS HUB', suppress_callback_exceptions=True, external_stylesheets=[{'href': '/assets/style.css', 'rel': 'stylesheet'}])
app.title = 'SNOREPHEUS HUB'

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

app.layout = html.Div(children=[
    html.Img(
    src='/assets/snorpheus-logo.png',
    height='100px',
    width='500px',
    style={
        'position': 'absolute',
        'top': '0',
        'left': '0',
        'margin-top': '10px',
        'margin-left': '10px',
    }
    ),
    html.H1(children='—————— WELCOME TO THE SNOREPHEUS HUB ——————'),
    html.Div(children=[
        html.Div(children=[
            dcc.Dropdown(
                id='folder-dropdown',
                options=[{'label': folder, 'value': folder} for folder in get_folders()],
                placeholder='PLEASE SELECT A SESSION TO BEGIN ANALYSIS, OR CHECK-IN A DEVICE BELOW...',
            ),
        ], className='dropdown-wrapper'),
        html.Div(children=[
            html.Button('REFRESH', id='refresh-button', n_clicks=0, className='refresh'),
        ], className='refresh-button-wrapper'),
    ], className='dropdown-container'),
    html.Div(children=[
        dcc.Graph(id='position-graph'),
    ], className='graph-container'),
    html.Div(children=[
        dcc.Graph(id='semi-circle-polar-plot'),
    ], className='graph-container'),
    html.Div(children=[
        html.Div(id='message', className='message', children='PLEASE SELECT A SNORE EVENT TO PLAY AUDIO'),
        html.Button('REWIND', id='rewind-btn', className='rewind-btn', n_clicks=0),
        html.Button("\u00A0\u00A0STOP\u00A0\u00A0", id='stop-btn', className='rewind-btn', n_clicks=0)
    ], className='message-container'),
    html.Div(children=[
        dcc.Input(id='input-number-1', type='number', placeholder='ENTER DEVICE ID...'),
        dcc.Input(id='input-first', type='text', placeholder='ENTER PATIENT FIRST NAME...'),
        dcc.Input(id='input-last', type='text', placeholder='ENTER PATIENT LAST NAME...'),
        dcc.Input(id='input-gender', type='text', placeholder='ENTER PATIENT SEX...'),
        dcc.Input(id='input-number-2', type='number', placeholder='ENTER PATIENT WEIGHT...')
    ], className='input-container'),
    html.Div(children=[
        dcc.Loading(
            id='loading-spinner',
            type='circle',
            color='#6c5ce7',
            children=[
                html.Button('———————————— FETCH AND PROCESS NOW ————————————', id='execute-button',className='execute', n_clicks=0),
                html.Div(id='output-message', className='output-message', children=''),
            ]
        ),
    ], className='loading'),
    html.Div(children=[  # Add the footer
        html.P(children='Developed by Evan Rains and Noah Butler for use at the Merchant Clinic ©2023', className='footer-text')
    ], className='footer')
])

audio_loaded = False
@app.callback(
    [Output('position-graph', 'figure'), Output('message', 'children')],
    [Input('folder-dropdown', 'value'), Input('position-graph', 'clickData')])
def update_graph(folder, clickData):
    fig = go.Figure()  # Initialize an empty figure
    if folder is not None:
        with open(f'{folder}/position.txt', 'r') as f:
            reader = csv.reader(f)
            data = list(reader)

        df = pd.DataFrame(data, columns=['datetime', 'position'])
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d-%H:%M:%S')
        df['position'] = pd.to_numeric(df['position'])

        snore_events = []
        for file in os.listdir(folder):
            if file.endswith('.wav'):
                snore_events.append((datetime.datetime.strptime(file.split(".")[0], '%Y-%m-%d-%H:%M:%S'), os.path.join(folder, file)))

        fig = create_figure(df, snore_events)

        if clickData is not None:
            snore_event_time = clickData["points"][0]["x"]
            for event in snore_events:
                if event[0] == datetime.datetime.strptime(snore_event_time, '%Y-%m-%d %H:%M:%S'):
                    audio_file = event[1]
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(audio_file)
                    print('PLAYING')
                    pygame.mixer.music.play()
                    audio_loaded = True
                    message_time = snore_event_time.partition(" ")[2]
                    message = f"PLAYED SNORE EVENT AT {message_time}"
                    return [fig, message]

    return [fig, 'PLEASE SELECT A SNORE EVENT TO PLAY AUDIO']

@app.callback(
    Output('rewind-btn', 'n_clicks'),
    [Input('rewind-btn', 'n_clicks')])
def handle_rewind(n_clicks):
    global audio_loaded
    if n_clicks > 0 and audio_loaded:
        pygame.mixer.music.stop()
        pygame.mixer.music.rewind()
        pygame.mixer.music.play()
    return 0

@app.callback(
    Output('stop-btn', 'n_clicks'),
    [Input('stop-btn', 'n_clicks')])
def handle_stop(n_clicks):
    if n_clicks > 0:
        pygame.mixer.music.stop()
    return 0

@app.callback(
    Output('output-message', 'children'),
    [Input('execute-button', 'n_clicks')],
    [State('input-number-1', 'value'),
     State('input-first', 'value'),
     State('input-last', 'value'),
     State('input-gender', 'value'),
     State('input-number-2', 'value')]
)
def execute_script(n_clicks, input_number_1, input_first, input_last, input_gender, input_number_2):
    if n_clicks > 0:
        time.sleep(0.1)  # Add a small delay to allow the spinner to be displayed
        # Replace 'your_script.py' with the name of your script
        script_args = ['python', 'HUB.py', str(input_number_1), input_first, input_last, input_gender, str(input_number_2)]
        result = subprocess.run(script_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            last_line = result.stdout.strip().split('\n')[-1]
            return f'{last_line}'
        else:
            return f'There was an error executing the script. Exit code: {result.returncode}. Error: {result.stderr}'
    return ''

@app.callback(
    Output('semi-circle-polar-plot', 'figure'),
    [Input('folder-dropdown', 'value')])
def update_semi_circle_polar_plot(folder):
    if folder is not None:
        with open(f'{folder}/position.txt', 'r') as f:
            reader = csv.reader(f)
            data = list(reader)

        df = pd.DataFrame(data, columns=['datetime', 'position'])
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d-%H:%M:%S')
        df['position'] = pd.to_numeric(df['position'])

        snore_events = []
        for file in os.listdir(folder):
            if file.endswith('.wav'):
                snore_events.append(datetime.datetime.strptime(file.split(".")[0], '%Y-%m-%d-%H:%M:%S'))

        fig = create_semi_circle_polar_plot(df, snore_events)

    else:
        fig = go.Figure()

    # Trigger a plot update by modifying the 'figure' dictionary
    fig.update_layout(uirevision=True)

    return fig


@app.callback(
    Output('folder-dropdown', 'options'),
    [Input('refresh-button', 'n_clicks')]
)
def update_dropdown_options(n_clicks):
    return [{'label': folder, 'value': folder} for folder in get_folders()]

if __name__ == '__main__':
    app.run_server(debug=True)
