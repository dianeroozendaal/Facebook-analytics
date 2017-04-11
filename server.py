from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, jsonify
from wtforms.validators import DataRequired
from wtforms import StringField
from flask_wtf import Form
import sqlite3
import os

app = Flask(__name__)

class SearchForm(Form):
    search = StringField('search', validators=[DataRequired()])

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'facebook.db'),
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'

))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()

    g.sqlite_db.row_factory = sqlite3.Row
    return g.sqlite_db

def query_db(query, args=(), one=False):
	cur = get_db().execute(query, args)
	rv = cur.fetchall()
	cur.close()
	return (rv[0] if rv else None) if one else rv    


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route('/', methods=['POST', 'GET'])
def index():
	db = get_db()
	posts = query_db('SELECT * FROM facebook ORDER BY time_stamp DESC')
	search_form = SearchForm()	
	num_post = 20

	return render_template('show_posts.html', posts=posts[:num_post], form=search_form)
    
@app.route('/search/', methods=['POST'])
def handle_data():
	keys = [ 'id', 'type', 'timestamp', 'c_time', 'week_day', 'mod_time', 'link', 'creator', 'text', 'impressions', 'consumptions', 'shares', 'clicks']
	url = (request.form['search'], )
	db = get_db()
	app.logger.info('Looking for URL: %s', request.form['search'])
	
	post = query_db('SELECT * FROM facebook WHERE link = ?', url)
	app.logger.info('Matched: %i' % len(post))
	
	if len(post) > 0:
		post_dict = dict(zip(keys, post[0]))
		
		# same week day
		print 'Looking for day: %i' % post_dict['week_day']
		data = query_db('SELECT impressions, consumptions, shares, clicks FROM facebook WHERE week_day = ?', (post_dict['week_day'], ))
		
		x = []
		for d in data:
			nums = []
			for num in d:
				if num == None:
					num = 0
				nums.append(num)
			x.append(nums)

		data = x
		for d in data:
			if data.index(d) == 0:
				day = { 'impressions' : [d[0]],
						'consumptions' : [d[1]],
						'shares' : [d[2]],
						'clicks' : [d[3]]
						 }

			day['impressions'].append(d[0])
			day['consumptions'].append(d[1])
			day['shares'].append(d[2])
			day['clicks'].append(d[3])

		day['impressions'] = sum(day['impressions']) / len(day['impressions'])
		day['consumptions'] = sum(day['consumptions']) / len(day['consumptions'])
		day['shares'] = sum(day['shares']) / len(day['shares'])
		day['clicks'] = sum(day['clicks']) / len(day['clicks'])

		app.logger.info('Results: %s' % post)
	else:
		day = None
	search_form = SearchForm()	

	return render_template('show_posts.html', posts=post, form=search_form, day=day)

