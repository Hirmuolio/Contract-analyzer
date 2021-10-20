
import json
import urllib
import base64
import hashlib
import secrets
import sys
import webbrowser
import requests
import random
import time

from datetime import datetime
from requests_futures.sessions import FuturesSession
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError, JWTClaimsError
from datetime import timedelta


user_agent = 'Hirmuolio-ESI-calling'
def set_user_agent( new_user_agent : str ):
	global user_agent
	user_agent = new_user_agent
	

#----
# SSO code begins
# Largely copied from the document example
#----

# Persistent config saved into json file
# Looks something like this:
# { "client_id": X,
# "tokens": {
#           "[char_id]":{
#             "character_id": "X",
#             "character_name": "X",
#             "refresh_token": "X",
#             "expires_at": "X"
#             }
#  }
config = {}

# Current access tokens stored here (not saved in json)
# Looks something like this:
# "[char_id]": {
#  "access_token": "X",
#  "expires_at": "X"
tokens = {}

def load_esi_config():
	global config
	
	save_required : bool = False
	try:
		config = json.load(open('esi_config.json'))
		
		authed = ""
		keys = config["tokens"].keys()
		for key in keys:
			authed += "\n" + config["tokens"][key]["character_name"] + " (" + config["tokens"][key]["character_id"] + ")"
		print( "Authorized characters:", authed )
	except:
		# Make default config
		config = {"tokens": {} }
		save_required = True
	
	# Require input for missing things
	if 'client_id'  not in config:
		print('  no client ID found. \nRegister at https://developers.eveonline.com/applications to get it')
		config['client_id'] = input("Give your client ID: ")
		save_required = True
	
	if save_required:
		save_esi_config()

def save_esi_config():
	with open('esi_config.json', 'w') as outfile:
			json.dump(config, outfile, indent=2)

def get_authorized():
	# Returns list of authorized character IDs
	return list( config["tokens"].keys() )

def get_access_token( character_id : str ):
	if character_id not in config["tokens"]:
		print( "Error - Trying to get tokens for unauthorized character" )
		sys.exit(1)
	
	if character_id not in tokens:
		# Not refresed logged in on this run
		refres_pkce( character_id )
	
	if datetime.now() > str_time_to_datetime( tokens[character_id]["expires_at"] ):
		refres_pkce( character_id )
	return tokens[character_id]["access_token"]

def log_in_pkce( scopes : list ):
	global config
	global tokens
	
	# Execute logging in.
	# Creates auth_code that is valid for 20 minutes
	
	# Generate the PKCE code challenge
	random = base64.urlsafe_b64encode(secrets.token_bytes(32))
	m = hashlib.sha256()
	m.update(random)
	d = m.digest()
	code_challenge = base64.urlsafe_b64encode(d).decode().replace("=", "")
	
	# print_auth_url
	base_auth_url = "https://login.eveonline.com/v2/oauth/authorize/"
	redirect_url = "http://localhost/oauth-callback"
	# scopes = "esi-characters.read_blueprints.v1 esi-characters.read_blueprints.v1"
	params = {
		"response_type": "code",
		"redirect_uri": redirect_url,
		"client_id": config['client_id'],
		"state": "unique-state"
	}
	if scopes:
		scope_str = ""
		for scop in scopes:
			scope_str += " " + scop
		params["scope"] = scope_str

	if code_challenge:
		params.update({
			"code_challenge": code_challenge,
			"code_challenge_method": "S256"
		})

	string_params = urllib.parse.urlencode(params)
	full_auth_url = "{}?{}".format(base_auth_url, string_params)
	# end
	
	webbrowser.open( full_auth_url, new=0, autoraise=True)
	
	auth_code = input("Copy the \"code\" query parameter and enter it here: ")
	
	code_verifier = random
	
	form_values = {
		"grant_type": "authorization_code",
		"client_id": config['client_id'],
		"code": auth_code,
		"code_verifier": code_verifier
	}
	
	# send_token_request
	
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"Host": "login.eveonline.com",
	}

	sso_response = requests.post(
		"https://login.eveonline.com/v2/oauth/token",
		data=form_values,
		headers=headers,
	)

	sso_response.raise_for_status()
	#end
	
	# handle_sso_token_response
	if sso_response.status_code == 200:
		data = sso_response.json()
		access_token = data["access_token"]
		refresh_token = data["refresh_token"]
		expires_str = str( datetime.now() + timedelta(0, data['expires_in']) )

		print("Verifying access token JWT...")

		jwt = validate_eve_jwt(access_token)
		character_id = jwt["sub"].split(":")[2]
		character_name = jwt["name"]
		
		config["tokens"][ str( character_id ) ] = {
			"character_id": character_id,
			"character_name": character_name,
			"refresh_token": refresh_token,
		}
		
		tokens[ str( character_id ) ] = {
			"access_token": access_token,
			"expires_at": expires_str
		}
		
		save_esi_config()
	else:
		print("\nSomething went wrong! Here's some debug info to help you out:")
		print("\nSent request with url: {} \nbody: {} \nheaders: {}".format(
			sso_response.request.url,
			sso_response.request.body,
			sso_response.request.headers
		))
		print("\nSSO response code is: {}".format(sso_response.status_code))
		print("\nSSO response JSON is: {}".format(sso_response.json()))

def refres_pkce( character_id : str ):
	global config
	global tokens
	refresh_token = config["tokens"][ character_id ][ "refresh_token" ]
	
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"Host": "login.eveonline.com",
	}
	
	form_values = {
		"grant_type": "refresh_token",
		"client_id": config['client_id'],
		"refresh_token": refresh_token
	}
	
	sso_response = requests.post(
		"https://login.eveonline.com/v2/oauth/token",
		data=form_values,
		headers=headers,
	)
	
	if sso_response.status_code == 200:
		data = sso_response.json()
		access_token = data["access_token"]
		refresh_token = data["refresh_token"]
		expires_str = str( datetime.now() + timedelta(0, data['expires_in']) )

		print("Verifying access token JWT...")

		jwt = validate_eve_jwt(access_token)
		character_id = jwt["sub"].split(":")[2]
		character_name = jwt["name"]
		
		config["tokens"][ str( character_id ) ] = {
			"character_id": character_id,
			"character_name": character_name,
			"refresh_token": refresh_token,
		}
		
		tokens[ str( character_id ) ] = {
			"access_token": access_token,
			"expires_at": expires_str
		}
		
		save_esi_config()
	else:
		print("\nSomething went wrong! Here's some debug info to help you out:")
		print("\nSent request with url: {} \nbody: {} \nheaders: {}".format(
			sso_response.request.url,
			sso_response.request.body,
			sso_response.request.headers
		))
		print("\nSSO response code is: {}".format(sso_response.status_code))
		print("\nSSO response JSON is: {}".format(sso_response.json()))

def validate_eve_jwt(jwt_token):
	#Validate a JWT token retrieved from the EVE SSO.

	#Args:
	#	jwt_token: A JWT token originating from the EVE SSO
	#Returns
	#	dict: The contents of the validated JWT token if there are no
	#		  validation errors
	#

	jwk_set_url = "https://login.eveonline.com/oauth/jwks"

	res = requests.get(jwk_set_url)
	res.raise_for_status()

	data = res.json()

	try:
		jwk_sets = data["keys"]
	except KeyError as e:
		print("Something went wrong when retrieving the JWK set. The returned "
			  "payload did not have the expected key {}. \nPayload returned "
			  "from the SSO looks like: {}".format(e, data))
		sys.exit(1)

	jwk_set = next((item for item in jwk_sets if item["alg"] == "RS256"))

	try:
		return jwt.decode(
			jwt_token,
			jwk_set,
			algorithms=jwk_set["alg"],
			issuer="login.eveonline.com"
		)
	except ExpiredSignatureError:
		print("The JWT token has expired: {}")
		sys.exit(1)
	except JWTError as e:
		print("The JWT signature was invalid: {}").format(str(e))
		sys.exit(1)
	except JWTClaimsError as e:
		try:
			return jwt.decode(
						jwt_token,
						jwk_set,
						algorithms=jwk_set["alg"],
						issuer="https://login.eveonline.com"
					)
		except JWTClaimsError as e:
			print("The issuer claim was not from login.eveonline.com or "
				  "https://login.eveonline.com: {}".format(str(e)))
			sys.exit(1)

#----
# SSO code ends
#----

def str_time_to_datetime( time_string : str ):
	# This format is used in login responses only
	return datetime.strptime( time_string, '%Y-%m-%d %H:%M:%S.%f')


def timestamped_print( message : str ):
	print(datetime.now().strftime('%H:%M:%S'), message)

def construct_url( endpoint : str, parameter : str = "" ):
	# Endpoint should be something like "/v1/contracts/public/{}/" where {} is replaced by the parameter
	base_url = "esi.evetech.net/"
	
	url = "https://" + ( base_url + endpoint ).replace('//', '/')
	return url.format( parameter )

def error_handling( esi_response, attempts ):
	# Checks errors and may wait
	# Returns True if call was succesful
	
	sleep_time = error_handling_futures( esi_response, attempts )
	
	if sleep_time > 0:
		timestamped_print( '  Retrying in ' + str(sleep_time) + ' second...' )
		time.sleep(sleep_time)
		return False
	else:
		return True

def error_handling_futures( esi_response, attempts ):
	# Checks errors
	# Returns how long to wait before doing more requests.
	
	if "warning" in esi_response.headers:
		timestamped_print( "Warning: ", esi_response.headers["warning"] )
	
	if esi_response.status_code in [200, 204, 304, 400, 404]:
		# Call was succesful. Or at least somewhat succesful.
		return 0
	else:
		time_to_wait  = 0.01
		#First part of error message
		error_msg = "Failed ESI call: "
		error_msg += str(esi_response.status_code)
		
		#Second half of the error message. Some errors have no description so try to print it
		try:
			error_msg += " - " + esi_response.json()['error']
		except:
			pass
		
		timestamped_print( error_msg )
		
		if esi_response.status_code in [500, 502, 503, 504]:
			# Server is having bad time. Just wait and retry.
			time_to_wait = min( (2 ** attempts) * (random.randint(0, 100) / 1000), 1800)
			return time_to_wait
		elif esi_response.status_code == 402:
			input("Authorization issue. Press any key to exit script.")
			sys.exit(1)
		elif esi_response.status_code == 420:
			# Error limit reached. Wait and resume.
			time_to_wait = esi_response.headers['x-esi-error-limit-reset']+1
			return time_to_wait
		else:
			#Some other error
			print('Unknown error.')
	return time_to_wait

def check_server_status():
	call_url = 'https://esi.evetech.net/v2/status/'
	headers = {"User-Agent":user_agent}
	
	# Loop through calls until server responds OK
	while True:
		esi_response = requests.get(call_url, headers=headers)
		
		if "warning" in esi_response.headers:
			timestamped_print( "Warning: ", esi_response.headers["warning"] )
		
		if esi_response.status_code != 200:
			timestamped_print( str(res.status_code) + " - Server not OK. Waiting 1 minute" )
			time.sleep( 60 )
		else:
			break

def call_esi( call_url : str, authorized_character_id : str = '' ):
	# Makes single call to ESI
	# Pages are not handled
	# Keeps retrying until call is succesful
	# Returns the response
	
	headers = {"User-Agent":user_agent}
	if authorized_character_id:
		token = get_access_token( authorized_character_id )
		headers["Authorization"] = "Bearer {}".format( token )
	
	done = False
	attempts = 0;
	while not done:
		res = requests.get(call_url, headers=headers)
		done = error_handling( res, attempts )
		attempts += 1
	
	return res

def call_many( call_urls : list[str], authorized_character_id : str = '' ):
	# Makes many ESI calls to many URLs
	# Pags are not handled
	# Returns list of responses
	# The returned responses may be in any order
	
	if not call_urls:
		return []
	
	if len(call_urls) == 1:
		return [ call_esi( call_urls[0], authorized_character_id ) ]
	
	headers = {"User-Agent":user_agent}
	if authorized_character_id:
		token = get_access_token( authorized_character_id )
		headers["Authorization"] = "Bearer {}".format( token )
	
	workers = min( 90, len(call_urls) )
	session = FuturesSession(max_workers=workers)
	
	all_calls_done = False
	returns = []
	remaining = call_urls
	
	total_calls = len(call_urls)
	done_calls = 0
	
	timestamped_print( "Making " + str( len(call_urls) ) + " calls..."  )
	
	while not all_calls_done:
		active = remaining[:500]
		remaining = remaining[500:]
		
		print( "\r ", done_calls, '/', total_calls, "      ", end="", flush=True)
		
		futures = []   # List of [future, url] pairs
		responses = [] # List of [response, url] pairs
		
		for url in active:
			futures.append( session.get(url, headers = headers) )
		
		for future in futures:
			responses.append( future.result() )
		
		sleep_time = 0
		error_count = 0
		for response in responses:
			wait = error_handling_futures( response, 0 )
			if( wait != 0 ):
				error_count += 1
				remaining.append( response.url )
				sleep_time = max( wait, sleep_time )
			else:
				done_calls += 1
				returns.append( response )
		if( sleep_time > 0 ):
			# Retry errored urls
			# TODO better handling for situations where there are lots of errors across multiple calls
			if error_count > 5:
				sleep_time = max( 1, sleep_time )
			elif error_count > 10:
				sleep_time = max( 5, sleep_time )
			elif error_count > 20:
				sleep_time = max( 10, sleep_time )
			
			if sleep_time > 2:
				timestamped_print( "There were {1} errors. Resuming calls in {0:.1f} seconds...".format( sleep_time, error_count ) )
			time.sleep( sleep_time )
		if not remaining:
			# Everything is done
			all_calls_done = True
	print( "calls done" )
	return returns

def call_many_pages( call_url : str, authorized_character_id : str = '' ):
	# Calls all pages for one URL
	# Returns list of responses
	# The returned responses may be in any order
	
	headers = {"User-Agent":user_agent}
	if authorized_character_id:
		token = get_access_token( authorized_character_id )
		headers["Authorization"] = "Bearer {}".format( token )
	
	page_1 = call_esi( call_url, authorized_character_id )
	
	pages = []
	if 'x-pages' in page_1.headers:
		pages = list( range( 2, int( page_1.headers['x-pages'] ) + 1 ) )
	
	# Get the rest of the pages
	
	session = FuturesSession()
	returns = [ page_1 ]
	done = False
	loops_done = 0;
	while not done:
		timestamped_print( "Fetching " + str( len( pages ) ) + " pages..."  )
		futures = []   # List of [future, url] pairs
		responses = [] # List of [response, url] pairs
		
		for page in pages:
			futures.append( [ session.get(call_url, headers = headers, params={'page': page}), page ] )
		pages = []
		
		for future in futures:
			responses.append( [ future[0].result(), future[1] ] )
		
		sleep_time = 0
		for response in responses:
			wait = error_handling_futures( response[0], loops_done )
			if( wait != 0 ):
				pages.append( response[1] )
				sleep_time = max( wait, sleep_time )
			else:
				returns.append( response[0] )
		if( pages ):
			# Retry errored urls
			timestamped_print( "Refetching erroreed calls in " + str( sleep_time ) + " seconds..." )
			time.sleep( sleep_time )
			
			loops_done += 1
		else:
			# Everything is done
			done = True
	
	return returns
	