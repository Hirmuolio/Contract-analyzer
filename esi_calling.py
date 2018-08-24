#Esi calling 1.2

import requests
import json
import time
import base64
import random
import sys
import webbrowser

from datetime import datetime
from datetime import timedelta

user_agent = 'something from Hirmuolio'

def set_user_agent(new_user_agent):
	global user_agent
	user_agent = new_user_agent
	

def error_handling(esi_response, number_of_attempts, tokens = None, scope = None, job = None):
	#Call this function to decide what to do on error
	#Some arbitrary maximum try ammount
	if number_of_attempts == 50:
		print('There has been 50 failed attemts to call ESI. Something may be wrong.')
		input('Press enter to continue trying...')
		number_of_attempts = 1
	
	if job != '':
		job_description = 'Failed to ' + job
	
	print(datetime.utcnow().strftime('%H:%M:%S'), job_description+'. Error',esi_response.status_code, end="")
	
	#Some errors have no description so try to print it
	try:
		print(' -', esi_response.json()['error'])
	except:
		#No error description from ESI
		print('')
		
	if esi_response.status_code == 420:
		#error limit reached. Wait until reset and try again.
		time.sleep(esi_response.headers['x-esi-error-limit-reset']+1)
	elif esi_response.status_code in [400, 401, 403]:
		#Authorization not working
		#Check if access token expired (can be fixed)
		#Check if scopes are valid (can't be fixed)
		#If can't be fixed then exit
		print('Your authorization is the problem. Make sure your client ID and secret key are valid and that you logged the right char.')
		input('Press enter to continue trying (won\'t work. Just close the script and redo login or client ID/secret)...')
	
	else:
		#500 = internal server error (downtime?)
		#502 = bad gateway
		#503 = service unavailable
		#Other errors
		#Lets just wait a sec and try again and hope for best
		time_to_wait = (2 ** number_of_attempts) + (random.randint(0, 1000) / 1000)
		print('Retrying in', time_to_wait, 'second...')
		time.sleep((2 ** number_of_attempts) + (random.randint(0, 1000) / 1000))


def logging_in(scopes, client_id, client_secret):
	number_of_attempts = 1
	login_url = 'https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri=http://localhost/oauth-callback&client_id='+client_id+'&scope='+scopes

	webbrowser.open(login_url, new=0, autoraise=True)

	authentication_code = input("Give your authentication code: ")
	
	combo = base64.b64encode(bytes( client_id+':'+client_secret, 'utf-8')).decode("utf-8")
	authentication_url = "https://login.eveonline.com/oauth/token"
	
	esi_response = requests.post(authentication_url, headers =  {"Authorization":"Basic "+combo, "User-Agent":user_agent}, data = {"grant_type": "authorization_code", "code": authentication_code} )
	
	if esi_response.status_code != 200:
		error_handling(esi_response, number_of_attempts, job = 'log in')
	else:
		tokens = {}
		tokens['refresh_token'] = esi_response.json()['refresh_token']
		tokens['access_token'] = esi_response.json()['access_token']
		tokens['expiry_time'] = str( datetime.utcnow() + timedelta(0,esi_response.json()['expires_in']) )

	
	return tokens
	
	
def check_tokens(tokens, client_secret, client_id):
	#Check if access token still good
	#If access token too old or doesn't exist generate new access token
	
	#refresh_token = tokens['refresh_token']
	#access_token = tokens['access_token'] (optional)
	#expiry_time = tokens['expiry_time'] (optional. Should exist with access token)
	
	number_of_attempts = 1
	
	
	#Check if token is valid
	#Needs to be done like this since the expiry time may or may not exist
	if 'expiry_time' in tokens:
		if datetime.utcnow() < datetime.strptime(tokens['expiry_time'], '%Y-%m-%d %H:%M:%S.%f'):
			valid = True
		else:
			valid = False
	else:
		valid = False
		
			
	
	if not valid:
		#No "expiry time" or the token has expired already
		#No valid access token. Make new.
		refresh_url = 'https://login.eveonline.com/oauth/token'
		combo = base64.b64encode(bytes( client_id+':'+client_secret, 'utf-8')).decode("utf-8")
		
		trying = True
		while trying == True:
			esi_response = requests.post(refresh_url, headers =  {"Authorization":"Basic "+combo, "User-Agent":user_agent}, data = {"grant_type": "refresh_token", "refresh_token": tokens['refresh_token']} )
			
			if esi_response.status_code != 200:
				error_handling(esi_response, number_of_attempts, tokens, scope = None, job = 'refresh tokens')
			else:
				#Success
				trying = False
			number_of_attempts = number_of_attempts + 1
			
		tokens['refresh_token']	= esi_response.json()['refresh_token']
		tokens['access_token'] = esi_response.json()['access_token']
		tokens['expiry_time'] = str( datetime.utcnow() + timedelta(0,esi_response.json()['expires_in']) )
		
	return tokens
		

def get_token_info(tokens):
	#Uses the access token to get various info
	#character ID
	#character name
	#expiration time (not sure on format)
	#scopes
	#token type (char/corp)
	
	url = 'https://login.eveonline.com/oauth/verify'
	
	trying = True
	while trying == True:
		esi_response = requests.get(url, headers =  {"Authorization":"Bearer "+tokens['access_token'], "User-Agent":user_agent})
		
		if esi_response.status_code != 200:
			error_handling(esi_response, number_of_attempts, tokens, scope = None, job = 'get token info')
		else:
			#Success
			trying = False
			
	token_info = {}
	token_info['character_name'] = esi_response.json()['CharacterName']
	token_info['character_id'] = esi_response.json()['CharacterID']	
	token_info['expiration'] = esi_response.json()['ExpiresOn']	
	token_info['scopes'] = esi_response.json()['Scopes']	
	token_info['token_type'] = esi_response.json()['TokenType']	
	
	return token_info
		
def call_esi(scope, url_parameter = '', parameters={}, etag = None, tokens = None, datasource = 'tranquility', calltype='get', job = ''):
	#scope = url part. Mark the spot of parameter with {par}
	#url_parameter = parameter that goes into the url
	#parameters = json parameters to include (pages mostly)
	#etag = TODO
	#tokens = json that contains refresh token. Optinally also access token and its expiration time if they already exist.
	#refresh_token = tokens['refresh_token']
	#access_token = tokens['access_token'] (optional)
	#expiry_time = tokens['expiry_time'] (optional. Should exist with access token)
	
	#datasource. Default TQ
	#calltype = get, post or delete. Default get
	#job = string telling what is being done. Is displayed on error message.
	
	number_of_attempts = 0
		
	
	#Build the url to call to
	#Also replace // with / to make things easier
	url = 'https://' + ('esi.evetech.net'+scope+'/?datasource='+datasource).replace('{par}', str(url_parameter)).replace('//', '/')

	
	#print(url)
	
	#un-authorized / authorized
	if tokens == None:
		headers = {"User-Agent":user_agent}
	else:
		headers =  {"Authorization":"Bearer "+tokens['access_token'], "User-Agent":user_agent}
	
	trying = True
	while trying == True:
		#Make the call based on calltype
		if calltype == 'get':
			esi_response = requests.get(url, headers = headers, params = parameters)
		elif calltype == 'post':
			esi_response = requests.post(url, headers = headers, params = parameters)
		elif calltype == 'delete':
			esi_response = requests.post(url, headers = headers, params = parameters)
		
		#200 = ok
		#204 = ok
		#304 = no change
		#404 = not found
		#400 = bad request. User is stupid
		if esi_response.status_code in [200, 204, 304]:
			#All OK
			trying = False
		elif esi_response.status_code in [404,  400]:
			#print('404 not found')
			trying = False
		else:
			error_handling(esi_response, number_of_attempts, tokens, scope, job)

		number_of_attempts = number_of_attempts + 1
		
	return esi_response
	
	
	
	
	
