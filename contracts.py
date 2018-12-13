#!/usr/bin/env python3

import json
from datetime import datetime
import gzip
import sys

import esi_calling

esi_calling.set_user_agent('Hirmuolio/Contract-analyzer')

def get_item_info(item_ids):
	#print('Getting item info for', len(item_ids), 'items')
	#Get attributes for item IDs listed
	#attributes are saved
	#/v3/universe/types/{type_id}/
	
	if len(item_ids) == 0:
		return
	
	response_array = esi_calling.call_esi(scope = '/v3/universe/types/{par}/', url_parameters=item_ids, job = 'get item infos')
	
	for array in response_array:
		response = (array[0]).json()
		#print(response)
		item_id = response['type_id']
		item_cache[str(item_id)] = response
	with gzip.GzipFile('item_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(item_cache, indent=2).encode('utf-8'))

def get_group_info(group_ids):
	#/v1/universe/groups/{group_id}/
	
	if len(group_ids) == 0:
		return
	
	response_array = esi_calling.call_esi(scope = '/v1/universe/groups/{par}/', url_parameters=group_ids, job = 'get group info')
	
	
	for array in response_array:
		response = (array[0]).json()
		group_id = response['group_id']
		group_cache[str(group_id)] = response
	with gzip.GzipFile('group_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(group_cache).encode('utf-8'))
	

def fetch_contracts(region_id):
	#10000044 = Solitude
	#Returns an array that contains all contracts of a region
	print('fetching contracts for region ID', region_id)
	
	all_contracts = []
	
	
	response_array = esi_calling.call_esi(scope = '/v1/contracts/public/{par}/', url_parameters=[region_id], job = 'get region contracts')[0]
	expires = response_array[0].headers['expires']
	
	for response in response_array:
		all_contracts.extend(response.json())
	print('Got {:,d} contracts.'.format(len(all_contracts)))
	
	
	return all_contracts


def import_orders(region_id):
	#'10000044' Solitude
	#10000002 = Jita
	all_orders = []
	
	response_array = esi_calling.call_esi(scope = '/v1/markets/{par}/orders/', url_parameters=[region_id], job = 'get market orders')[0]
	#print(response_array)
	
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



def import_prices():
	#Import Jita prices and save
	# 10000044 = Solitude
	# 10000002 = Forge (Jita)
	item_prices = {}
	print('Importing market prices')
	orders = import_orders(10000002)
	item_prices = get_item_prices(orders)
	#with open('item_prices.json', 'w') as outfile:
	#	json.dump(item_prices, outfile, indent=4)
	with gzip.GzipFile('item_prices.gz', 'w') as outfile:
		outfile.write(json.dumps(item_prices).encode('utf-8'))
	
	#Get attributes for all items listed on market
	
	import_ids = []
	counter = 0
	#len(item_prices)
	print('')
	for key in item_prices:
		counter += 1
		print('\rChecking item ', counter, '/', len(item_prices), end="", flush=True)
		if not key in item_cache:
			import_ids.append(key)
		
		if len(import_ids) == 300 or counter == len(item_prices):
			get_item_info(import_ids)
			import_ids = []
			
	#Get groups for all items and groups.
	import_ids = []
	counter = 0
	for item_id in item_cache:
		counter += 1
		group_id = str(item_cache[str(item_id)]['group_id'])
		if not group_id in group_cache:
			import_ids.append( group_id )
		
		if len(import_ids) == 300 or counter == len(item_prices):
			print('importing', len(import_ids), 'groups' )
			get_group_info(import_ids)
			import_ids = []
		
			


def evaluate_items(cost, contract_items):
	
	dots = 0

	#contract_cache[contract_id]['items'] = contract_items
	
	#print(json.dumps(contract_items, indent=4))
	
	value_sell = 0
	value_buy = 0
	for item_dict in contract_items:
		if 'is_blueprint_copy' in item_dict:
			#Do not valye BPCs
			continue
		quantity = item_dict['quantity']
		type_id = item_dict['type_id']
		
		if not str(type_id) in item_cache:
			print(' ', type_id, 'Item not in item cache')
			get_item_info([type_id])
		if not str(item_cache[str(type_id)]['group_id']) in group_cache:
			print('group not in group cache. Importing...')
			get_group_info([str(item_cache[str(type_id)]['group_id'])])
		
		if 'record_id' in item_dict:
			if group_cache[ str(item_cache[str(type_id)]['group_id']) ]['category_id'] == 8:
				#Do not value unstacked charges. They are most likely damaged
				continue
		if item_cache[str(type_id)]['published'] == False:
			#Not on market
			continue
		
		if item_dict["is_included"] == False:
			if str(type_id) in item_prices:
				if 'sell_price' in item_prices[str(type_id)]:
					cost += quantity * item_prices[str(type_id)]['sell_price']
		else:
			if str(type_id) in item_prices:
				if 'sell_price' in item_prices[str(type_id)]:
					value_sell = value_sell + quantity * item_prices[str(type_id)]['sell_price']
				if 'buy_price' in item_prices[str(type_id)]:
					value_buy = value_buy + quantity * item_prices[str(type_id)]['buy_price']
	
	#profit  [profit, percentage], [profit, percentage]
	#sell_profit = value_sell - cost
	#sell_profit_percentage = round(100*(sell_profit)/(cost+0.01))
	profit = {'profit_sell': [value_sell - cost, round(100*(value_sell - cost)/(cost+0.01))] , 'profit_buy':[value_buy - cost, round(100*(value_buy - cost)/(cost+0.01))]}

	return profit
	
def analyze_contracts():
	#Import all the contracts
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
	print('')
	
	uncached_contracts = []
	
	for contract in all_contracts:
		contract_id = str(contract['contract_id'])
		if not contract_id in contract_cache:
			uncached_contracts.append(contract)
			contract_cache[contract_id] = contract
			
		
	
	#Import items of 10 contracts at once
	#Then evalueate them one by one
	
	contracts_to_import = len(uncached_contracts)
	print('Importing', contracts_to_import, 'contracts...')
	counter = 0
	ids = []
	print(len(uncached_contracts))
	print('')
	for contract in uncached_contracts:
		counter += 1
		
		if contract['type'] == 'item_exchange':
			ids.append( str(contract['contract_id']) )
			
		if len(ids) == 200 or counter == len(uncached_contracts):
			print('\rImporting ', counter, '/', len(uncached_contracts), end="", flush=True)
			small_contract_items = []
			response_array = esi_calling.call_esi(scope = '/v1/contracts/public/items/{par}/', url_parameters=ids, job = 'get contract items')
			
			for index in range(len(ids)):
				contract_cache[ids[index]]['items'] = []
				contract_items = []
				if not response_array[index][0].status_code in [204, 400, 403, 404,]:
					#[204, 400, 403, 404,] would mean expired or accepted contract. Leave [] for items.
					for response in response_array[index]:
						contract_items.extend(response.json())
						
					contract_cache[ids[index]]['items'].extend(contract_items)
			ids = []
				#Save the cache after every bulk import just in case.
	with gzip.GzipFile('contract_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(contract_cache, indent=2).encode('utf-8')) 
	
	#All contracts are now in cache
	uncached_contracts = []
	
	
	with gzip.GzipFile('asd.gz', 'w') as outfile:
		outfile.write(json.dumps({'a':all_contracts}, indent=2).encode('utf-8'))
	
	#Check contracts for items that need to be imported (items that are not on market)
	print('\nchecking contracts for new items')
	print('contracts:', len(contract_cache))
	all_items = []
	fetch_ids = []
	for contract_id in contract_cache:
		contract = contract_cache[contract_id]
		if 'items' in contract:
			for item_dict in contract['items']:
				type_id = item_dict['type_id']
				if not type_id in all_items:
					all_items.append(type_id)
	print('Found', len(all_items), 'unique items in contracts. Checking items.')
	counter = 0
	for type_id in all_items:
		counter +=1
		if not str(type_id) in item_cache:
			fetch_ids.append(type_id)
			
		if len(fetch_ids)==100 or (counter == len(all_items) and len(fetch_ids) != 0 ):
			get_item_info(fetch_ids)
			fetch_ids = []
	print('Item check done')
				
	
	number_of_contracts = len(all_contracts)
	index = 1
	
	
	#Now estimate the value of the contract
	for contract in all_contracts:
		print('\ranalyzing ', index, '/', number_of_contracts, end="")
		index = index + 1
		
		contract_id = str(contract['contract_id'])
		
		if 'items' in contract_cache[contract_id]:
			contract_items = contract_cache[contract_id]['items']
			cost = contract['price'] - contract['reward']
			
			profit = evaluate_items(cost=cost, contract_items=contract_items)
		else:
			profit = {'profit_sell': [0,0] , 'profit_buy':[0,0]}
		
		
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
	

def import_regions():
	response = esi_calling.call_esi(scope = '/v1/universe/regions/', job = 'get regions')
	
	regions = {}
	for region_id in response.json():
		print('importing a region name...')
		response = esi_calling.call_esi(scope = '/v1/universe/regions/{par}/', url_parameters=[region_id], job = 'get region name')
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
	else:
		print('Invalid region. Try again')
		region_selection()
	
				
#--------------------------
#Preparations
#--------------------------

try:
	with gzip.GzipFile('item_cache.gz', 'r') as fin:
		item_cache = json.loads(fin.read().decode('utf-8'))
except:
	print('no item cache found')
	item_cache = {}

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
	
	#Delete old contracts
	print('clening')
	time_now = datetime.utcnow()
	deletable_contracts = []
	for contract_id in contract_cache:
		contract_expires = datetime.strptime(contract_cache[contract_id]['date_expired'], '%Y-%m-%dT%H:%M:%SZ') 
		if time_now > contract_expires:
			deletable_contracts.append(contract_id)
	print('Deleting', len(deletable_contracts), 'expired contracts')
	for contract_id in deletable_contracts:
		contract_cache.pop(contract_id, None)
	with gzip.GzipFile('contract_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(contract_cache).encode('utf-8')) 
except:
	print('No contract cache found')
	contract_cache = {}


	
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

try:
	with gzip.GzipFile('group_cache.gz', 'r') as fin:
		group_cache = json.loads(fin.read().decode('utf-8'))
except:
	group_cache = {}
		

#-------------
#Start
#------------

while True:
	print('\n[R] Region to import contracts from (currently: ', config['region'], ')\n[M] Market data reimport\n[S] Start contract analysis')
	user_input = input("[R/M/S] ")
	if user_input in ['R', 'r']:
		region_selection()
	elif user_input in ['M', 'm']:
		import_prices()
	elif user_input in ['S', 's']:
		analyze_contracts()





































