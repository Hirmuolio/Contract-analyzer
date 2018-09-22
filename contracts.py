#!/usr/bin/env python3

import json
from datetime import datetime
import requests
import gzip
from multiprocessing import Pool

import esi_calling

esi_calling.set_user_agent('Hirmuolio/Contract-analyzer')

def fetch_contracts(region_id):
	#10000044 = Solitude
	print('fetching contracts for region ID', region_id)
	
	all_contracts = []
	
	if str(region_id) in region_cache:
		#Region already cached. Check if has expired
		time_now = datetime.utcnow()
		#Sun, 26 Aug 2018 18:24:35 GMT
		#datetime.strptime(expires, '%a, %d %b %Y %H:%M:%S GMT')
		contract_expires = datetime.strptime(region_cache[str(region_id)]['expires'], '%a, %d %b %Y %H:%M:%S GMT')
		if contract_expires > time_now:
			time_delta = contract_expires - time_now
			print('Using cached data. New data available in ', str(time_delta).split('.', 2)[0])
			all_contracts = region_cache[str(region_id)]['contracts']
			return all_contracts
		else:
			print('region cache expired. ', end = '')
	else:
		print('Importing region from ESI.')
	
	response_array = esi_calling.call_esi(scope = '/v1/contracts/public/{par}/', url_parameter=region_id, job = 'get region contracts')
	expires = response_array[0].headers['expires']
	
	for response in response_array:
		all_contracts.extend(response.json())
	print('Got {:,d} contracts.'.format(len(all_contracts)))
	
	
	
	region_cache[str(region_id)] = {}
	region_cache[str(region_id)]['expires'] = expires
	region_cache[str(region_id)]['contracts'] = all_contracts
	
	#with open('region_cache.json', 'w') as outfile:
	#	json.dump(region_cache, outfile, indent=4)
	with gzip.GzipFile('region_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(region_cache).encode('utf-8')) 
	
	return all_contracts


def import_orders(region_id):
	#'10000044' Solitude
	#10000002 = Jita
	all_orders = []
	
	response_array = esi_calling.call_esi(scope = '/v1/markets/{par}/orders/', url_parameter=region_id, job = 'get market orders')
	
	for response in response_array:
		all_orders.extend(response.json())
	print('Got {:,d} orders.'.format(len(all_orders)))
	return all_orders

def get_item_prices(response):
	item_prices = {}
	for index in range(0, len(response)):
		type_id = response[index]['type_id']
	
		if not str(type_id) in item_prices:
			item_prices[str(type_id)] = {}
	
		#add price info
		if response[index]['is_buy_order'] == True:
			if 'buy_price' in item_prices[str(type_id)]:
				item_prices[str(type_id)]['buy_price'] = max(response[index]['price'], item_prices[str(type_id)]['buy_price'])
			else:
				item_prices[str(type_id)]['buy_price'] = response[index]['price']
		else:
			if 'sell_price' in item_prices[str(type_id)]:
				item_prices[str(type_id)]['sell_price'] = min(response[index]['price'], item_prices[str(type_id)]['sell_price'])
			else:
				item_prices[str(type_id)]['sell_price'] = response[index]['price']
	return item_prices

def evaluate_contract(contract):
	default_profit = {'profit_sell': [0, 0], 'profit_buy': [0, 0]}
	
	if contract["type"] != 'item_exchange':
		return default_profit
	contract_id = str(contract['contract_id'])
	cost = contract['price'] - contract['reward']
	
	if contract_id in contract_cache:
		all_items = contract_cache[contract_id]['items']
	else:
		contract_cache[contract_id] = {}
		contract_cache[contract_id]['expires'] = contract['date_expired']
		all_items = []

		try:
			response_array = esi_calling.call_esi(scope = '/v1/contracts/public/items/{par}/', url_parameter=contract_id, job = 'get contract items')
		except:
			print('ESI call failed, skipping this contract', contract_id)
			return default_profit
		
		try:
			response_code = response_array[0].status_code
		except:
			#For some reason some things are not as multipage response so no array is returned.
			response_code = response_array.status_code
			#print(response_code)
		
		if response_code in [204, 400, 403, 404,]:
			#Expired recently or empty
			contract_cache[contract_id]['items'] = []
			return default_profit
			
		for response in response_array:
			all_items.extend(response.json())
		contract_cache[contract_id]['items'] = all_items
	value_sell = 0
	value_buy = 0
	for item_dict in all_items:
		if 'is_blueprint_copy' in item_dict:
			continue
		quantity = item_dict['quantity']
		type_id = item_dict['type_id']
		
		if item_dict["is_included"] == False:
			quantity = -quantity
		
		if str(type_id) in item_prices:
			if 'sell_price' in item_prices[str(type_id)]:
				value_sell = value_sell + quantity * item_prices[str(type_id)]['sell_price']
			if 'buy_price' in item_prices[str(type_id)]:
				value_buy = value_buy + quantity * item_prices[str(type_id)]['buy_price']
	
	
	profit = {'profit_sell': [value_sell - cost, round(100*(value_sell - cost)/(cost+0.01))] , 'profit_buy':[value_buy - cost, round(100*(value_buy - cost)/(cost+0.01))]}

	return profit

def import_prices():
	#Import Jita prices and save
	# 10000044 = Solitude
	# 10000002 = Forge (Jita)
	global item_prices
	print('Importing market prices')
	orders = import_orders(10000002)
	item_prices = get_item_prices(orders)
	#with open('item_prices.json', 'w') as outfile:
	#	json.dump(item_prices, outfile, indent=4)
	with gzip.GzipFile('item_prices.gz', 'w') as outfile:
		outfile.write(json.dumps(item_prices).encode('utf-8')) 

def contract_profit_mapper(contract):
	return (contract, evaluate_contract(contract))

def analyze_contracts():
	#Analyze all the contracts one by one
	
	region_id = regions[config['region']]
	all_contracts = fetch_contracts(region_id)
	
	profitable_buy = ''
	profitable_sell = ''
	
	profit_buy_contracts_array = []
	profit_buy_percentage_array = []
	
	profit_sell_contracts_array = []
	profit_sell_percentage_array = []
	
	good_contracts = {}
	
	number_of_contracts = len(all_contracts)
	index = 1

	with Pool() as pool:
		mapped_contracts = pool.map_async(
			contract_profit_mapper, all_contracts).get()

	for kvp in mapped_contracts:
		contract = kvp[0]
		profit = kvp[1]

		#print('\rimportin page: '+str(page)+'/'+str(total_pages), end="")
		print('\ranalyzing ', index, '/', number_of_contracts, end="")
		index = index + 1
		
		
		if profit['profit_buy'][0] > 0:		
			profit_isk = profit['profit_buy'][0]
			if profit_isk > 1000000000: #1b
				profit_isk = str( round(profit_isk / 1000000000)) + ' billion isk'
			elif profit_isk > 1000000: #1m
				profit_isk = str( round(profit_isk / 1000000)) + ' million isk'
			elif profit_isk > 1000: #1k
				profit_isk = str( round(profit_isk / 1000)) + ' thousand isk'
			else:
				profit_isk = str( round( profit_isk) ) + ' isk'
			
			profit_buy_contracts_array.append( contract['contract_id'] )
			profit_buy_percentage_array.append( profit['profit_buy'][1] ) 
			
			good_contracts[ contract['contract_id'] ] = {'profit_isk':profit_isk, 'percentage':str( profit['profit_buy'][1])}
			
			#string = '<url=contract:30003576//' + str(contract['contract_id']) + '>' + profit_isk + '</url> ' + str( round(profit['profit_buy'][1]) ) + '%'
			#profitable_buy = profitable_buy + '\n' + string
				
		elif profit['profit_sell'][0] > 0:
			profit_isk = profit['profit_sell'][0]
			if profit_isk > 1000000000: #1b
				profit_isk = str( round(profit_isk / 1000000000)) + ' billion isk'
			elif profit_isk > 1000000: #1m
				profit_isk = str( round(profit_isk / 1000000)) + ' million isk'
			elif profit_isk > 1000: #1k
				profit_isk = str( round(profit_isk / 1000)) + ' thousand isk'
			else:
				profit_isk = str( round( profit_isk) ) + ' isk'
			
			profit_sell_contracts_array.append( contract['contract_id'] )
			profit_sell_percentage_array.append( profit['profit_sell'][1] ) 
			
			good_contracts[ contract['contract_id'] ] = {'profit_isk':profit_isk, 'percentage':str( profit['profit_sell'][1])}
			
			#string = '<url=contract:30003576//' + str(contract['contract_id']) + '>' + profit_isk + '</url> ' + str( round( profit['profit_sell'][1] ) ) + '%'
			#profitable_sell = profitable_sell + '\n' + string
		
		if index%1000 == 0:
			#Save the cache every 1000th contract. Just in case.
			with gzip.GzipFile('contract_cache.gz', 'w') as outfile:
				outfile.write(json.dumps(contract_cache).encode('utf-8')) 
	
	#Sort by percentage
	profit_buy_percentage_array, profit_buy_contracts_array = zip(*sorted(zip(profit_buy_percentage_array, profit_buy_contracts_array)))
	profit_sell_percentage_array, profit_sell_contracts_array = zip(*sorted(zip(profit_sell_percentage_array, profit_sell_contracts_array)))
	
	profit_buy_contracts_array = list(profit_buy_contracts_array)
	profit_sell_contracts_array = list(profit_sell_contracts_array)
	
	profit_buy_contracts_array.reverse()
	profit_sell_contracts_array.reverse()
	
	
	#profit buy
	for contract_id in profit_buy_contracts_array:
		string = '<url=contract:30003576//' + str(contract_id) + '>' + good_contracts[contract_id]['profit_isk'] + '</url> ' + good_contracts[contract_id]['percentage'] + '%'
		profitable_buy = profitable_buy + '\n' + string
	
	#profit sell
	for contract_id in profit_sell_contracts_array:
		string = '<url=contract:30003576//' + str(contract_id) + '>' + good_contracts[contract_id]['profit_isk'] + '</url> ' + good_contracts[contract_id]['percentage'] + '%'
		profitable_sell = profitable_sell + '\n' + string
		

	full_string = 'Profitable to sell to Jita buy orders:' + profitable_buy + '\n\nProfitable sell as Jita sell order' + profitable_sell
	with open('profitable.txt', 'w') as outfile:
		outfile.write(full_string)
	
	#with open('contract_cache.json', 'w') as outfile:
	#		json.dump(contract_cache, outfile, indent=4)
	with gzip.GzipFile('contract_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(contract_cache).encode('utf-8')) 
	print('\nAnalysis completed')

def import_regions():
	response = esi_calling.call_esi(scope = '/v1/universe/regions/', job = 'get regions')
	
	regions = {}
	for region_id in response.json():
		print('importing a region name...')
		response = esi_calling.call_esi(scope = '/v1/universe/regions/{par}/', url_parameter=region_id, job = 'get region name')
		region_name = response.json()["name"]
		regions[region_name] = region_id
		
	with open('regions.json', 'w') as outfile:
		json.dump(regions, outfile, indent=4)
	return regions
	
def region_selection():
	print('Valid regions: ', list(regions) )
	user_input = input("Type in the region to import ")
	
	if user_input in regions:
		config['region'] = user_input
		with open('config.json', 'w') as outfile:
			json.dump(config, outfile, indent=4)
		main_menu()
	else:
		print('Invalid region. Try again')
		region_selection()
	
def clean_cache():
	#deletes old entries from the caches
	
	time_now = datetime.utcnow()
	
	#Individual contract cache
	deletable_contracts = []
	for contract_id in contract_cache:
		contract_expires = datetime.strptime(contract_cache[contract_id]['expires'], '%Y-%m-%dT%H:%M:%SZ') 
		if time_now > contract_expires:
			deletable_contracts.append(contract_id)
	for contract_id in deletable_contracts:
		contract_cache.pop(contract_id, None)
	#with open('contract_cache.json', 'w') as outfile:
	#	json.dump(contract_cache, outfile, indent=4)
	with gzip.GzipFile('contract_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(contract_cache).encode('utf-8')) 
	
	#region contract cache
	deletable_regions = []
	for region_id in region_cache:
		expires = datetime.strptime(region_cache[region_id]['expires'], '%a, %d %b %Y %H:%M:%S GMT') 
		if time_now > expires:
			deletable_regions.append(region_id)
	for region_id in deletable_regions:
		region_cache.pop(region_id, None)
	#with open('region_cache.json', 'w') as outfile:
	#	json.dump(region_cache, outfile, indent=4)
	with gzip.GzipFile('region_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(region_cache).encode('utf-8')) 
	
				
def main_menu():
	print('[R] Region to import contracts from (currently: ', config['region'], ')\n[M] Market data reimport\n[S] Start contract analysis')
	user_input = input("[R/M/S] ")
	if user_input in ['R', 'r']:
		region_selection()
	elif user_input in ['M', 'm']:
		import_prices()
		main_menu()
	elif user_input in ['S', 's']:
		analyze_contracts()
		main_menu()
	else:
		main_menu()
#--------------------------
#Start the thing
#--------------------------

try:
	#item_prices = json.load(open('item_prices.json'))
	with gzip.GzipFile('item_prices.gz', 'r') as fin:
		item_prices = json.loads(fin.read().decode('utf-8'))
except:
	print('No market prices found')
	item_prices = {}
	import_prices()

try:
	#contract_cache = json.load(open('contract_cache.json'))
	with gzip.GzipFile('contract_cache.gz', 'r') as fin:
		contract_cache = json.loads(fin.read().decode('utf-8'))
except:
	contract_cache = {}

try:
	#region_cache = json.load(open('region_cache.json'))
	with gzip.GzipFile('region_cache.gz', 'r') as fin:
		region_cache = json.loads(fin.read().decode('utf-8'))
except:
	region_cache = {}
	
try:
	regions = json.load(open('regions.json'))
except:
	print('No regions found')
	regions = import_regions()
	
try:
	config = json.load(open('config.json'))
except:
	config = {'region':'The Forge'}
	with open('config.json', 'w') as outfile:
		json.dump(config, outfile, indent=4)

clean_cache()

main_menu()



print('done')



































