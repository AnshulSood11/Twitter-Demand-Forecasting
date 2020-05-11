import sys
import traceback
from datetime import datetime as dt
from datetime import date, timedelta
import time

import pandas as pd
from nltk import tokenize
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import GetOldTweets3 as got
import re

import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

FA = "https://use.fontawesome.com/releases/v5.12.1/css/all.css"

app = dash.Dash(
	__name__,
	meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
	external_stylesheets=[dbc.themes.BOOTSTRAP, FA]
)
server = app.server

locations = pd.read_csv("./data/world-cities_csv.csv")['name']
location_options = [{"label": i, "value": i} for i in locations]
location_options = sorted(location_options, key=lambda x: x["label"].upper())
location_search = ""

countries = pd.read_csv("./data/countries.csv")['Name']
country_options = [{"label": i, "value": i} for i in countries]

default_start_date = date.today()
default_end_date = default_start_date - timedelta(10)

products = ["iPhone", "Samsung Phone", "OnePlus"]
product_options = [{"label": i, "value": i} for i in products]
product_options = sorted(product_options, key=lambda x: x["label"].upper())
product_search = ""

processing_info = ">>> "
new_line = "\n>>> "
running_state = [False]  # as a list(mutable type) so that it can replicate pass by reference

max_tweets_values = [100, 500, 1000, 2000, 5000, 0]

net_scores = []

data_frames = []


def description_card():
	"""

	:return: A Div containing dashboard title & descriptions.
	"""
	return html.Div(
		id="description-card",
		children=[

			html.H3("Welcome to the Twitter Analytics dashboard"),
			html.Div(
				id="intro",
				children="Explore current and past social trends for products by location"
						 " and leverage them to estimate demand and optimize"
						 " your inventory",
			),
		],
	)


def generate_control_card():
	"""

	:return: A Div containing controls for graphs.
	"""
	return html.Div(
		id="control-card",
		children=[
			html.Div([
				dcc.Dropdown(
					id="location-select",
					options=location_options,
					placeholder="Store Location",
					value='Delhi',
					style={'width': '200px'}
				),
				html.Button([html.I(id='add-location-button', className="fa fa-plus-square fa-3x")],
							style={'margin': '0', 'padding': '0', 'border': '0'}
							),
				html.Div(id='hidden-text-location', style={'display': 'none'}),
				html.Span(style={'width': '50px'}),
				dcc.Dropdown(
					id="country-select",
					options=country_options,
					placeholder="Country",
					value='India',
					style={'width': '200px'}
				),
			], style=dict(display='flex')),
			html.Br(),
			html.B(id="select-timeframe-label", children="Select Time Frame"),
			html.P(),
			dcc.DatePickerRange(
				id="date-picker-select",
				start_date=dt(default_end_date.year, default_end_date.month, default_end_date.day),
				end_date=dt(default_start_date.year, default_start_date.month, default_start_date.day),
				min_date_allowed=dt(2008, 1, 1),
				max_date_allowed=dt(default_start_date.year, default_start_date.month, default_start_date.day),
				initial_visible_month=dt(2020, default_start_date.month, 1),
			),
			html.Br(),
			html.Br(),
			html.B(id="select-products-label", children="Select Products"),
			html.P(),
			dbc.Tooltip(
				"Choose the products for which you want to compare sentiment-scores"
				"\nTo add a new product, enter the name and press +",
				target="select-products-label",
				style={'font-size': 12, 'text-align': 'justify'}
			),
			html.Div([
				dcc.Dropdown(
					id="product-select",
					options=sorted(product_options, key=lambda x: x["label"]),
					value=products,
					multi=True,
					style={'width': '300px'}
				),
				html.Button([html.I(id='add-product-button', className="fa fa-plus-square fa-3x")],
							style={'margin': '0', 'padding': '0', 'border': '0'}
							),
				html.Div(id='hidden-text-product', style={'display': 'none'}),
			], style=dict(display='flex')),
			html.Br(),
			html.Div([
				html.Div([
					html.B(id="max-tweets-label", children="Max_tweets"),
					dbc.Tooltip(
						"Set limit for max number of tweets to be mined for each product. (More tweets take more time)",
						target="max-tweets-label",
						style={'font-size': 12, 'text-align': 'justify'}
					),
				]),
				html.Span(style={'width': '50px'}),
				html.Div([
					dcc.Slider(
						id='max-tweets-selector',
						min=0,
						max=5,
						step=None,
						marks={
							0: {'label': '100'},
							1: {'label': '500'},
							2: {'label': '1000'},
							3: {'label': '2000'},
							4: {'label': '5000'},
							5: {'label': 'no_limit'},
						},
						value=5
					)
				], style={'width': 300}),
			], style={'display': 'flex'}),

			html.Br(),
			html.Br(),
			html.Div(
				id="query-btn-outer",
				children=dbc.Button(children="Query", id="query-btn", outline=True, color="primary",
									style={'width': 100}),
				style={'display': 'flex', 'justify-content': 'center'}
			),
		],
	)


def generate_processing_window():
	"""

	:return: A Div containing live updates about what the program is doing
	"""
	return html.Div(
		id="processing-window",
		children=[
			html.Br(),
			html.Div([
				dcc.Textarea(
					id='processing-textarea',
					style={'width': 600, 'height': 200}
				),
				dcc.Interval(
					id='processing-interval',
					interval=1000,
					n_intervals=0,
					disabled=True
				)
			])
		]
	)


def generate_bar_graph():
	return html.Div(
		className="eight columns",
		children=[
			dcc.Graph(
				id="bar-graph",
				hoverData=None,
				figure=go.Figure(
					data=[go.Bar(x=products, y=[])]
				),
			),
			html.Div(id='hidden-text-graph', style={'display': 'none'}),
			dcc.Interval(
				id='graph-interval',
				interval=1000,
				n_intervals=0,
				disabled=True
			)
		],
		style={'padding': '10px 0px 0px 0px'}
	)


def generate_pie_chart():
	return html.Div(
		className="four columns",
		children=[
			dcc.Graph(
				id="pie-chart",
			)
		], style={'padding': '10px 0px 0px 0px'}
	)


def generate_scatter_graph():
	return html.Div([dcc.Graph(
		id='scatter-graph'
	)],
		style={'padding': '10px 10px 30px 10px'}
	)


app.layout = html.Div(
	id="app-container",
	children=[
		# Header
		html.Div(
			id="header",
			className="header",
			children=[
				html.H5("Twitter Analytics for Demand Forecasting"),
			],
		),
		# Left column
		html.Div(
			id="left-column",
			className="four columns",
			children=[description_card(), generate_control_card(), generate_processing_window()]
		),
		# Right column
		html.Div(
			id="right-column",
			className="eight columns",
			children=[
				html.Div(
					id="right-column-upper",
					# className="eight columns",
					children=[generate_bar_graph(), generate_pie_chart()],
					style={'display': 'inline-block'}
				),
				html.Div(
					id="right-column-lower",
					# className="eight columns",
					children=[generate_scatter_graph()],
				)
			]
		),
		# Footer
		html.Div(
			id="footer",
			className="footer",
			children=[
				html.B("View Code on :"), html.A('Github', href='https://github.com/AnshulSood11', target='_blank')
			],
			style={},
		),

	],
)


@app.callback(
	Output('hidden-text-location', 'children'),
	[Input("location-select", "search_value")]
)
def update_location_search(search_value):
	if not search_value:
		return ""

	global location_search
	location_search = search_value
	return ""


@app.callback(
	[Output('location-select', 'options'),
	 Output('location-select', 'value')],
	[Input('add-location-button', 'n_clicks')],
	[State('location-select', 'options'),
	 State('location-select','value')]
)
def update_locations(n_clicks, existing_options, selected_location):
	if n_clicks is None:
		raise PreventUpdate
	global location_search
	location_search = re.sub(' +', ' ', location_search)
	location_search = location_search.lstrip()
	location_search = location_search.rstrip()

	for o in existing_options:
		if o["label"].lower() == location_search.lower():
			location_search = ''
			return existing_options,selected_location

	s = ""
	for word in location_search.split():
		s += word.capitalize()
		s += " "
	s = s.rstrip()
	existing_options.append({'label': s, 'value': s})
	sorted_options = sorted(existing_options, key=lambda x: x["label"].upper())
	location_search = ''
	return sorted_options, s


@app.callback(
	Output('hidden-text-product', 'children'),
	[Input("product-select", "search_value")]
)
def update_product_search(search_value):
	if not search_value:
		return ""

	global product_search
	product_search = search_value
	return ""


@app.callback(
	[Output('product-select', 'options'),
	 Output('product-select', 'value')],
	[Input('add-product-button', 'n_clicks')],
	[State('product-select', 'options'),
	 State('product-select', 'value')],
)
def update_products(n_clicks, existing_options, selected_products):
	if n_clicks is None:
		raise PreventUpdate

	global product_search
	product_search = re.sub(' +', ' ', product_search)
	product_search = product_search.lstrip()
	product_search = product_search.rstrip()

	for o in existing_options:
		if o["label"].lower() == product_search.lower():
			product_search = ''
			return existing_options, selected_products

	existing_options.append({'label': product_search, 'value': product_search})
	sorted_options = sorted(existing_options, key=lambda x: x["label"].upper())
	selected_products.append(product_search)
	product_search = ''
	return sorted_options,selected_products


@app.callback(
	[Output('processing-interval', 'disabled'),
	 Output('graph-interval', 'disabled'),
	 Output('query-btn', 'children'),
	 Output('query-btn', 'color'),
	 ],
	[Input("query-btn", "n_clicks_timestamp"),
	 Input('processing-interval', 'n_intervals')
	 ]
)
def start_processing_interval(time_stamp, n):
	if time_stamp is None:
		raise PreventUpdate

	global processing_info, running_state

	if (int(round(time.time() * 1000)) - 100) < time_stamp:  # if btn is pressed

		if not running_state[0]:  # if query btn is pressed
			running_state[0] = True
			return False, False, "Interrupt", "danger"
		else:  # if Interrupt btn is pressed
			running_state[0] = False
			processing_info += "\n --- Interrupted ---"
			time.sleep(1)
			return True, True, "Query", "primary"
	if running_state[0]:
		return False, False, "Interrupt", "danger"
	else:
		return True, True, "Query", "primary"


@app.callback(
	Output('processing-textarea', 'value'),
	[Input('processing-interval', 'n_intervals')]
)
def update_processing_window(n):
	global processing_info, new_line
	return processing_info


@app.callback(
	Output("bar-graph", "figure"),
	[Input('graph-interval', 'n_intervals')],
	[State("product-select", "value"), ]
)
def update_bar_graph(n, selected_products):
	fig = go.Figure()
	fig.add_trace(go.Bar(x=selected_products, y=net_scores))
	fig.update_layout(
		title='Net Sentiment Scores',
		title_x=0.5,
		bargap=0.2,
		xaxis=dict(title_text='Product'),
		yaxis=dict(title_text='Sentiment Score')
	)
	return fig


@app.callback(
	Output('pie-chart', 'figure'),
	[Input('bar-graph', 'hoverData')]
)
def update_pie_chart(hoverData):
	if hoverData is not None:
		index = hoverData['points'][0]['pointIndex']
		scores = data_frames[index]['score']
		pos = sum(score >= 0 for score in scores)
		neg = scores.count() - pos
		values = [pos, neg]
		fig = go.Figure()
		fig.add_trace(go.Pie(labels=['Positive', 'Negative'],
							 values=values,
							 hoverinfo='label+percent',
							 textinfo='value'))
		fig.update_layout(
			title='{}'.format(hoverData['points'][0]['x']),
			xaxis=dict(showgrid=False, zeroline=False),
			yaxis=dict(showgrid=False, zeroline=False),
		)
		return fig
	else:
		fig = go.Figure()
		fig.update_layout(
			title='Positive vs Negative sentiments',
			title_x = 0.5,
			xaxis=dict(showgrid=False, zeroline=False),
			yaxis=dict(showgrid=False, zeroline=False))
		return fig


@app.callback(
	Output('scatter-graph', 'figure'),
	[Input('bar-graph', 'hoverData')]
)
def update_scatter_graph(hoverData):
	if hoverData is not None:
		index = hoverData['points'][0]['pointIndex']
		df = data_frames[index]
		df['date'] = df['date'].apply(lambda s: s[:10])
		df = df.groupby(['date'])['score'].sum().reset_index()

		values = df['score']
		labels = [s.split(' ')[0] for s in df['date']]
		fig = go.Figure()
		fig.add_trace(go.Scatter(x=labels,
								 y=values,
								 mode='lines+markers'))
		fig.update_layout(
			title='Trends for {}'.format(hoverData['points'][0]['x']),
			title_x=0.5,
			xaxis=dict(title_text='Day'),
			yaxis=dict(title_text='Sentiment Score (day-wise)')
		)
		return fig
	else:
		fig = go.Figure()
		fig.update_layout(
			title='Trends',
			title_x=0.5,
			xaxis=dict(showgrid=False, zeroline=False, title_text='Day'),
			yaxis=dict(showgrid=False, zeroline=False, title_text='Net Sentiment (per day)')
		)
		return fig


@app.callback(

	Output('hidden-text-graph', 'children'),
	[
		Input("query-btn", "n_clicks"),
	],
	state=[State("date-picker-select", "start_date"),
		   State("date-picker-select", "end_date"),
		   State("location-select", "value"),
		   State("country-select", "value"),
		   State("product-select", "value"),
		   State("max-tweets-selector", "value"),
		   ]
)
def perform_queries(n_clicks, start, end, location, country, selected_products, max_tweets):
	global processing_info, net_scores, data_frames, running_state

	if n_clicks is None:
		raise PreventUpdate

	time.sleep(1)  # give time so that the change in running_state from start_processing_interval gets reflected here also

	if running_state[0] is True:
		processing_info = ">>> "
		if location is None:
			processing_info += "Location cannot be empty" + new_line
			running_state[0] = False
			raise PreventUpdate
		elif country is None:
			processing_info += "Country cannot be empty" + new_line
			running_state[0] = False
			raise PreventUpdate

		processing_info += "Performing Queries" + new_line
		net_scores = []
		data_frames = []

		for product_index in range(len(selected_products)):
			query_twitter(start, end, location, country, selected_products[product_index], max_tweets)
			# tweets = pd.read_csv(product + ".csv")
			tweets = data_frames[product_index]
			scores = []
			net_score = 0
			sid = SentimentIntensityAnalyzer()
			for i in range(len(tweets)):
				lines_list = tokenize.sent_tokenize(tweets['text'][i])
				score = 0

				for sentence in lines_list:
					ss = sid.polarity_scores(sentence)
					score += ss['compound']

				score /= len(lines_list)
				score = score * (tweets['retweets'][i] + tweets['favorites'][i] + 1)
				score = round(score, 2)
				scores.append(score)
				net_score += score

			data_frames[product_index]['score'] = scores
			net_scores.append(round(net_score, 2))

		print(net_scores)
		processing_info += "{}".format(net_scores) + new_line
		processing_info += "Done\n"
		time.sleep(1)
		running_state[0] = False
		return ""
	else:
		return ""


def query_twitter(start, end, location, country, product, max_tweets):
	# global outputFile, outputFileName
	global processing_info, new_line, data_frames
	max_tweets = max_tweets_values[max_tweets]
	columns = ['date', 'username', 'to', 'replies', 'retweets', 'favorites', 'text', 'geo', 'mentions', 'hashtags',
			   'id', 'permalink']
	row_list = []
	try:
		tweetCriteria = got.manager.TweetCriteria()
		# outputFileName = 'old_tweets.csv'

		usernames = set()
		username_files = set()
		tweetCriteria.querySearch = product.lower()
		tweetCriteria.since = start
		tweetCriteria.until = end
		tweetCriteria.near = location + " ," + country
		tweetCriteria.maxTweets = max_tweets
		tweetCriteria.lang = "en"
		# outputFileName = product + ".csv"
		# outputFile = open(outputFileName, "w+", encoding="utf8")
		# outputFile.write('date,username,to,replies,retweets,favorites,text,geo,mentions,hashtags,id,permalink\n')

		cnt = 0

		def receiveBuffer(tweets):
			global processing_info
			nonlocal cnt

			for t in tweets:
				data = [t.date.strftime("%Y-%m-%d %H:%M:%S"),
						t.username,
						t.to or '',
						t.replies,
						t.retweets,
						t.favorites,
						'"' + t.text.replace('"', '""') + '"',
						t.geo,
						t.mentions,
						t.hashtags,
						t.id,
						t.permalink]
				# data[:] = [i if isinstance(i, str) else str(i) for i in data]
				# outputFile.write(','.join(data) + '\n')
				row_list.append(dict(zip(columns, data)))

			# outputFile.flush()
			cnt += len(tweets)

			if running_state[0] is False:
				raise PreventUpdate

			if sys.stdout.isatty():
				print("\rSaved %i" % cnt, end='', flush=True)
				if cnt < 100:
					processing_info += "\tDowloaded {}".format(cnt)
				else:
					processing_info = "\n".join(processing_info.split("\n")[0:-1])
					processing_info += "\n\tDowloaded {}".format(cnt)
			else:
				print(cnt, end=' ', flush=True)

		print("Downloading tweets for {}".format(product))
		processing_info += "Downloading tweets for {} ...\n".format(product)
		got.manager.TweetManager.getTweets(tweetCriteria, receiveBuffer, state=running_state)

	# except KeyboardInterrupt:
	# 	print("\r\nInterrupted.\r\n")

	except PreventUpdate:
		print("Interrupted")
		raise PreventUpdate

	except Exception as err:
		print(traceback.format_exc())
		print(str(err))

	finally:
		processing_info += new_line
		df = pd.DataFrame(row_list)
		data_frames.append(df)


# if "outputFile" in locals():
# 	outputFile.close()
# 	print()
# 	print('Done. Output file generated "%s".' % outputFileName)

# Run the server
if __name__ == "__main__":
	app.run_server(debug=True, port=8000, host='127.0.0.1')