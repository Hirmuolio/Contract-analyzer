#Esi calling 1.2


import json
import time
import base64
import random
import sys
import webbrowser

from datetime import datetime
from datetime import timedelta

from requests_futures.sessions import FuturesSession

session = FuturesSession(max_workers=90)


scopes = ''
user_agent = 'ESI calling script by Hirmuolio'
config = {}


def load_config(loaded_config):
	global config
	try:
		client_id = loaded_config['client_id']
		client_secret = loaded_config['client_secret']
		config = loaded_config
	except KeyError:
		#Config found but no wanted content
		print('  no client ID or secret found. \nRegister at https://developers.eveonline.com/applications to get them')
		
		client_id = input("Give your client ID: ")
		client_secret = input("Give your client secret: ")
		config = {"client_id":client_id, "client_secret":client_secret, 'authorizations':{}}
	return config

def set_user_agent(new_user_agent):
	global user_agent
	user_agent = new_user_agent
	

	
def logging_in(scopes):
	global config
	
	number_of_attempts = 1
	client_id = config['client_id']
	client_secret = config['client_secret']
	
	login_url = 'https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri=http://localhost/oauth-callback&client_id='+client_id+'&scope='+scopes

	webbrowser.open(login_url, new=0, autoraise=True)

	authentication_code = input("Give your authentication code: ")
	
	combo = base64.b64encode(bytes( client_id+':'+client_secret, 'utf-8')).decode("utf-8")
	authentication_url = "https://login.eveonline.com/oauth/token"
	
	#esi_response = grequests.post(authentication_url, headers =  {"Authorization":"Basic "+combo, "User-Agent":user_agent}, data = {"grant_type": "authorization_code", "code": authentication_code} ).send().response
	
	headers = json.dumps({"Authorization":"Basic "+combo, "User-Agent":user_agent})
	data = json.dumps({"grant_type": "authorization_code", "code": authentication_code})
	
	esi_response = make_call(url = authentication_url, headers = headers, data = data, calltype='post', job = 'exchange authorization code for tokens')[1]
	
	if esi_response.status_code in [200, 204, 304]:
		tokens = {}
		
		tokens['refresh_token'] = esi_response.json()['refresh_token']
		tokens['access_token'] = esi_response.json()['access_token']
		tokens['expiry_time'] = str( datetime.utcnow() + timedelta(0,esi_response.json()['expires_in']) )
		
		token_info = get_token_info(tokens)
		
		tokens['character_name'] = token_info['character_name']
		tokens['character_id'] = token_info['character_id']
		tokens['scopes'] = token_info['scopes']
		
		config['authorizations'][tokens['character_id']] = tokens
	else:
		print(' ', datetime.utcnow().strftime('%H:%M:%S'), 'Failed to log in. Error',esi_response.status_code, end="")
		#Second half of the error message. Some errors have no description so try to print it
		try:
			print(' -', esi_response.json()['error'])
		except:
			print('')
	return config
	
def check_tokens(authorizer_id):
	#Check if access token still good
	#If access token too old or doesn't exist generate new access token
	
	#refresh_token = tokens['refresh_token']
	#access_token = tokens['access_token'] (optional)
	#expiry_time = tokens['expiry_time'] (optional. Should exist with access token)
	global config
	
	try:
		tokens = config['authorizations'][str(authorizer_id)]
	except:
		print('  Error: This character has no authorization. Something is very broken.')
	
	number_of_attempts = 1
	
	
	#Check if token is valid
	#Needs to be done like this since the expiry time may or may not exist
	if 'expiry_time' in tokens:
		if datetime.utcnow() < datetime.strptime(tokens['expiry_time'], '%Y-%m-%d %H:%M:%S.%f'):
			return
	
	client_id = config['client_id']
	client_secret = config['client_secret']
	
	#No "expiry time" or the token has expired already
	#No valid access token. Make new.
	refresh_url = 'https://login.eveonline.com/oauth/token'
	combo = base64.b64encode(bytes( client_id+':'+client_secret, 'utf-8')).decode("utf-8")
	
	headers = json.dumps({"Authorization":"Basic "+combo, "User-Agent":user_agent})
	data = json.dumps({"grant_type": "refresh_token", "refresh_token": tokens['refresh_token']})
	
	esi_response = make_call(url = refresh_url, headers = headers, data = data, calltype='post', job = 'refresh authorization tokens')[1]
	
	#esi_response = grequests.post(refresh_url, headers =  {"Authorization":"Basic "+combo, "User-Agent":user_agent}, data = {"grant_type": "refresh_token", "refresh_token": tokens['refresh_token']} ).send().response
	
	if esi_response.status_code in [200, 204, 304]:
		config['authorizations'][str(authorizer_id)]['refresh_token']	= esi_response.json()['refresh_token']
		config['authorizations'][str(authorizer_id)]['access_token'] = esi_response.json()['access_token']
		config['authorizations'][str(authorizer_id)]['expiry_time'] = str( datetime.utcnow() + timedelta(0,esi_response.json()['expires_in']) )
	else:
		print(' ', datetime.utcnow().strftime('%H:%M:%S'), 'Failed to refresh tokens. Error',esi_response.status_code, end="")
		#Second half of the error message. Some errors have no description so try to print it
		try:
			print(' -', esi_response.json()['error'])
		except:
			print('')
		print('  Your login may have been invalidated.')
		

def get_token_info(tokens):
	#Uses the access token to get various info
	#character ID
	#character name
	#expiration time (not sure on format)
	#scopes
	#token type (char/corp)
	
	url = 'https://login.eveonline.com/oauth/verify'
	
	headers = json.dumps({"Authorization":"Bearer "+tokens['access_token'], "User-Agent":user_agent})
	
	esi_response = make_call(url = url, headers = headers, job = 'get token info')[1]
	
	#esi_response = grequests.get(url, headers =  {"Authorization":"Bearer "+tokens['access_token'], "User-Agent":user_agent}).send().response
	
	token_info = {}
	if esi_response.status_code in [200, 204, 304]:
		token_info['character_name'] = esi_response.json()['CharacterName']
		token_info['character_id'] = esi_response.json()['CharacterID']	
		token_info['expiration'] = esi_response.json()['ExpiresOn']	
		token_info['scopes'] = esi_response.json()['Scopes']	
		token_info['token_type'] = esi_response.json()['TokenType']	
	else:
		print(' ', datetime.utcnow().strftime('%H:%M:%S'), 'Failed to refresh tokens. Error',esi_response.status_code, end="")
		#Second half of the error message. Some errors have no description so try to print it
		try:
			print(' -', esi_response.json()['error'])
		except:
			print('')
		print('  This relaly should not happen.')
		input("Press enter to continue. This thing will probably crash now.")
	
	return token_info


def call_was_succesful(esi_response, job, attempts):
	#Error checking
	#Returns True if call was succesful
	#Returns false if call failed. Retry the call.
	#[200, 204, 304] = All OK
	#[404,  400] = not found or user error. Call was succesful. Check for these elsewhere
	#401 = unauthorized. Call was succesful. Check for these elsewhere.
	#402 = invalid autorization. Call was succesful. Check for these elsewhere.
	#420 = error limited. Wait the duration and retry.
	#[500, 503, 504] = Server problem. Just retry.
	
	if esi_response.status_code in [200, 204, 304, 400, 404]:
		return True
	else:
		#First part of error message
		print(' ', datetime.utcnow().strftime('%H:%M:%S'), 'Failed to ' + job +'. Error',esi_response.status_code, end="")
		
		#Second half of the error message. Some errors have no description so try to print it
		try:
			print(' -', esi_response.json()['error'])
		except:
			print(' - no error message')
		
		if esi_response.status_code in [500, 502, 503, 504]:
			time_to_wait = min( (2 ** attempts) + (random.randint(0, 1000) / 1000), 1800)
			print('  Retrying in', time_to_wait, 'second...')
			time.sleep(time_to_wait)
		elif esi_response.status_code == 402:
			#TODO: Refresh autorization
			print('Restart the script to get fresh authorization. If problem continues your character has no access to thir resource. Continuing script as if nothing happened (things may break)')
			return True #Call was still succesful so lets stop here
		elif esi_response.status_code == 402:
			print('Continuing script as if nothing happened (things may break)')
			return True #Call was still succesful so lets stop here
		elif esi_response.status_code == 420:
			time.sleep(esi_response.headers['x-esi-error-limit-reset']+1)
		else:
			#Some other error
			print('Unknown error. Retrying')
	return False
	


def make_call(url, headers = '', data = '', page = None, calltype='get', job = 'make ESI call'):
	#Makes single call to ESI and returns the used url and the response.
	#The dictionaries comes in as a string to avoid certain dictionary fuckery
	
	#headers = user agent and authorization token things
	#data = Login things
	
	#Gives up after 10 failures
	
	print('calling ', url, ' - page:', page)
	
	ans = requests.head(url, timeout=5)
	
	try:
		headers = json.loads(headers)
	except:
		headers = {}
	
	#Data is only used for logging in
	try:
		data = json.loads(data)
	except:
		data = {}
	
	if page != None:
		params={'page': page}
	else:
		params={}
	
	attempts = 0
	
	while attempts < 10:
		attempts +=  1
		
		#grequests.get(url, headers = headers).send().response
		try:
			if calltype == 'get':
				future = session.get(url, headers = headers, data = data, params = params)
			elif calltype == 'post':
				future = session.post(url, headers = headers, data = data, params = params)
			elif calltype == 'delete':
				future = session.delete(url, headers = headers, data = data, params = params)
			esi_response = future.result()
		except:
			# Maybe set up for a retry, or continue in a retry loop
			print('Exception on ', url, ' page', page, '. Ignoring...')
		
		if call_was_succesful(esi_response=esi_response, job=job, attempts=attempts):
			return [url, esi_response]
		
	#The following will run only if the call fails too many times.
	print('Unable to make ESI call after', attempts, 'attempts')
	print('Shit is broken')
	input("Press enter to continue (something is very broken)")
	return [url, esi_response]

	
def make_many_calls(urls, headers = '', calltype='get', job = 'make ESI call'):
	#Use this to call many different URLs at once
	#Returns the responses and the used urls
	
	#Show what is sent to CCP
	#print('  url = ', url,'\nHeaders = ', headers)
	#print('Making calls')
	
	
	try:
		headers = json.loads(headers)
	except:
		headers = {}
	
	
	futures = [] 
	responses = []
	for url in urls:
		futures.append(session.get(url, headers = headers))

	for future in futures:
		responses.append(future.result())
	
	check_errors = True
	error_check_rounds = 0
	
	number_of_responses = len(responses)
	#print('  Checking for errors...')
	
	while check_errors:
		check_errors = False
		sleep_time = 0
		refetch_urls = []
		refetch_indexs = []
		for index  in range(number_of_responses):
			try:
				if not responses[index].status_code in [200, 204, 304, 404, 400]:
					check_errors = True
					refetch_urls.append(urls[index])
					refetch_indexs.append(index)
					print('  Error -', responses[index].status_code, '. Refetching...')
					if error_check_rounds > 1:
						print(urls[index])
					if responses[index].status_code == 420:
						#error limit reached. Wait until reset and try again.
						sleep_time = responses[index].headers['x-esi-error-limit-reset']+1
			except:
				#The call failed completely
				check_errors = True
				print('  Error - failed call. Refetching page...')
				check_errors = True
				refetch_urls.append(urls[index])
				refetch_indexs.append(index)
					
			
		if check_errors == True:
			if len(refetch_urls) > 10:
				print('Lots of errors. This may take a while')
			print('  Refetching ', len(refetch_urls), ' urls...')
			
			if sleep_time != 0:
				print('Error limited. Waiting', sleep_time, 'seconds')
				time.sleep(sleep_time)
			elif error_check_rounds > 1:
				sleep_time = (2 ** error_check_rounds) + (random.randint(0, 1000) / 1000)
				print('Waiting', sleep_time, 'seconds')
				time.sleep(sleep_time)
				
			for index in range( len(refetch_urls) ):
				future = session.get(refetch_urls[index], headers = headers)
				esi_response = future.result()
				
				responses[refetch_indexs[index]] = esi_response

			error_check_rounds = error_check_rounds + 1
	
	return_array = []
	for index in range( len(urls) ):
		return_array.append( [urls[index], responses[index] ] )
	
	
	#print(f'Took {time2-time1:.2f} s')
	
	return return_array

def call_many_pages(url, headers = '', pages = None, calltype='get', job = 'make ESI call'):
	#Use this get many pages off of same url
	#Returns array with rest of the pages
	#print(url)
	
	try:
		headers = json.loads(headers)
	except:
		headers = {}
	
	futures = [] 
	responses = []
	for page in range(2, pages + 1):
		futures.append(session.get(url, headers = headers, params={'page': page}))

	for future in futures:
		responses.append(future.result())
		
	#print(responses)
	
	check_errors = True
	error_check_rounds = 0
	
	number_of_responses = len(responses)
	#print('  Checking for errors...')
	
	while check_errors:
		check_errors = False
		sleep_time = 0
		refetch_pages = []
		for index  in range(number_of_responses):
			try:
				if not responses[index].status_code in [200, 204, 304, 404, 400]:
					check_errors = True
					refetch_pages.append(index+2)
					print('  Error -', responses[index].status_code, '. Refetching...')
					if responses[index].status_code == 420:
						#error limit reached. Wait until reset and try again.
						sleep_time = responses[index].headers['x-esi-error-limit-reset']+1
			except:
				#The call failed completely
				check_errors = True
				print('  Error - failed call. Refetching page...')
				check_errors = True
				refetch_pages.append(index+2)
					
			
		if check_errors == True:
			if len(refetch_pages) > 10:
				print('Lots of errors. This may take a while')
			print('  Refetching ', len(refetch_pages), ' pages...')
			
			if sleep_time != 0:
				print('Error limited. Waiting', sleep_time, 'seconds')
				time.sleep(sleep_time)
			elif error_check_rounds > 1:
				sleep_time = (2 ** error_check_rounds) + (random.randint(0, 1000) / 1000)
				print('Waiting', sleep_time, 'seconds')
				time.sleep(sleep_time)
				
			
			for page in refetch_pages:
				future = session.get(url, headers = headers, params={'page': page})
				esi_response = future.result()
				
				responses[page-2] = esi_response
	
			error_check_rounds = error_check_rounds + 1
	
	
	
	return responses

def call_esi(scope, url_parameters = [], etag = None, authorizer_id = None, datasource = 'tranquility', calltype='get', job = ''):
	#scope = url part. Mark the spot of parameter with {par}
	#url_parameter = parameter that goes into the url. Can be array to make many calls
	#etag = TODO
	#authorizer_id = ID of the char whose authorization will be used
	
	#datasource. Default TQ
	#calltype = get, post or delete. Default get
	#job = string telling what is being done. Is displayed on error message.
	
	#un-authorized / authorized
	if authorizer_id == None:
		headers = {"User-Agent":user_agent}
		authorized = False
	else:
		check_tokens(authorizer_id)
		tokens = config['authorizations'][str(authorizer_id)]
		headers =  {"Authorization":"Bearer "+tokens['access_token'], "User-Agent":user_agent}
		authorized = True
	
	urls = []
	
	#Build the urls to call to
	#Also replace // with / to make things easier
	#url = 'https://' + ('esi.evetech.net'+scope+'/?datasource='+datasource).replace('{par}', str(url_parameter)).replace('//', '/')
	if len(url_parameters) == 0:
		url = 'https://' + ('esi.evetech.net'+scope+'/?datasource='+datasource).replace('//', '/')
		urls.append(url)
	else:
		for parameter in url_parameters:
			url = 'https://' + ('esi.evetech.net'+scope+'/?datasource='+datasource).replace('{par}', str(parameter)).replace('//', '/')
			#print(url)
			urls.append(url)
			
	responses = make_many_calls(urls, headers = headers, calltype=calltype, job = job)
	#print(responses)
			
	
	#Responses is an array of arrays.
	#Each array contains the call url and responses that correspond to the url.
	#If the response is only one page then the array contains only one response.
	#If multipage response then the array contains all the pages (done in next step).
	#Example:
	#[ ['url', page1], ['url', page1, page2, page3], ['url', page1] ]
	
	
	#Check if multipages.
	for index in range(len(responses)):
		#url = responses[index][0]
		#esi_response = responses[index][1]
		if 'X-Pages' in responses[index][1].headers:
			#Multipage thing. Get all the pages
			total_pages = int(responses[index][1].headers['X-Pages'])
			if total_pages > 1:
				print('Multipage response. Fetching ', total_pages, ' pages' )
				
				multipages = call_many_pages(responses[index][0], headers = headers, pages = total_pages, calltype=calltype, job = job)
				
				responses[index].extend( multipages )
			
	

	#Remove url from the responses
	
	#print(responses)
	for index in range( len(responses)):
		del responses[index][0]
		
	return responses
	
	
	
	
	
