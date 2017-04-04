import unicodecsv as csv
import datetime
import requests
import pickle
import facepy
import sqlite3
import json 
import sys
import os
import re

class Post:
	def __init__(self, data):
		self.text = None
		self.id = None
		self.link = None
		self.creator = None
		self.type = None
		self.insight = False

		self.timestamp = datetime.datetime.strptime(data['created_time'], '%Y-%m-%dT%H:%M:%S+0000')

		# link not always present
		if data.has_key('link'):
			self.link = data['link']

		if data.has_key('message'):
			self.text = data['message']
			
			# find shortener
			if re.search('https://nrch.nl/', self.text):
				match = re.search('https://nrch.nl/', self.text)
				short = self.text[match.start():match.end() + 4]
				self.link = requests.get(short).url
		
		# posts sometimes do not have a message
		if data.has_key('status_type'):
			if data['status_type'] != 'shared_story':
				if data.has_key('message'):
					self.text = data['message']

		# admin creator datapoint not always present
		if data.has_key('admin_creator'):
			self.creator = data['admin_creator']['name']
		
		self.id = data['id']
		self.type = data['type']

	def get_insight(self):
		metrics = ['post_impressions', 'post_consumptions', 'post_consumptions_by_type']
		output = {}

		for m in metrics: 
			data = graph.get(self.id + '/insights/' + m)

			if m == 'post_consumptions_by_type':
				output['link_click'] = data['data'][0]['values'][0]['value']['link clicks']
			else:
				output[m] = data['data'][0]['values'][0]['value']

		self.impressions = output['post_impressions']
		self.consumptions = output['post_consumptions']
		self.clicks = output['link_click']

		shares = graph.get(self.id + '?fields=shares')

		if shares.has_key('shares'):
			self.shares = shares['shares']['count']
		else:
			self.shares = None
		
		self.insight = True

	def to_file(self):
		# check for keys, or process what to write to csv as arg

		if 'output.csv' not in os.listdir('.'):
			with open('output.csv', 'w') as csv_out:
				writer = csv.writer(csv_out, delimiter='\t')
				writer.writerow(['Article', 'Facebook ID', 'Impressions', 'Consumptions', 'Shares', 'Clicks'])	

		if self.insight != True: 
			self.get_insight()
	
		out = [self.link, self.id, self.impressions, self.consumptions, self.shares, self.clicks]

		with open('output.csv', 'a') as csv_out:
			writer = csv.writer(csv_out, delimiter='\t')
			writer.writerow(out)

	def to_list(self):
		if self.insight == True:
			return [	self.id,
						self.type,
						self.link,
						self.creator,
						self.text,
						self.insight,
						self.impressions,
						self.consumptions,
						self.shares,
						self.clicks
					]
		else:
			return [	self.id,
						self.type,
						self.link,
						self.creator,
						self.text,
						self.insight,
						None,
						None,
						None,
						None
					]

	def to_sql(self):
		# check for db
		if 'facebook.db' not in os.listdir('.'):
			conn = sqlite3.connect('facebook.db')
			c = conn.cursor()
			c.execute('''CREATE TABLE Facebook 
							(	id text,
								type text,
								link text,
								creator text,
								message text,
								insight boolean,
								impressions real,
								consumptions real,
								shares real,
								clicks real
							)
						''')
			conn.commit()
		else:
			conn = sqlite3.connect('facebook.db')
			c = conn.cursor()
			
		c.execute('SELECT id FROM facebook')

		# c.fetchall() returns a tuple?
		ids = [id[0] for id in c.fetchall()]

		if self.id in ids:
			t = (self.id, )
			c.execute('SELECT * FROM facebook WHERE id=?', t)
			if self.insight == False:
				self.get_insight()
				c.execute("INSERT INTO facebook VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", self.to_list())
			else:
				'%s already processed' % self.id
		else:
			c.execute("INSERT INTO facebook VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", self.to_list())

		conn.commit()


def getToken():
	token = raw_input('Token expired. Enter new token\nGet one here: https://developers.facebook.com/tools/explorer/\n> ')
	pickle.dump(token, open('token.p', 'wb'))
	return token

def auth():
	""" auth works with a local pickle file with the access token, if access token expires, script prompts user with new input from cli """
	print 'Authenticating with Facebook...\n'

	try:
		token = pickle.load(open('token.p', 'rb'))
	except IOError:
		token = getToken()

	if token:
		try:
			graph = facepy.GraphAPI(token)
			profile = graph.get('nrc')
		except facepy.exceptions.OAuthError:
			token = getToken()

	return facepy.GraphAPI(token)

graph = auth()
profile = graph.get('nrc')
posts = graph.get(profile['id'] + '/posts')

database = []
dates = []

while posts.has_key('paging'):
	
	for post in posts['data']:
		post_obj = Post(post)
		database.append(post_obj)	
		post_obj.to_sql()

		if post_obj.timestamp.date() not in dates:
			print 'Processing:', post_obj.timestamp.date()
		
		dates.append(post_obj.timestamp.date())

	posts = requests.get(posts['paging']['next']).json()	
	print '* Crawled %i posts' % len(database)
	
	# build sql database
