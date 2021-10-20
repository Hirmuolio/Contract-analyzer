#!/usr/bin/env python3

import json
from datetime import datetime
from datetime import timedelta
import gzip
import sys

import esi_calling

esi_calling.set_user_agent('Hirmuolio/Contract-analyzer')

def print_time( message ):
	print(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), message)

def get_item_info(item_ids):
	#print('Getting item info for', len(item_ids), 'items')
	#Get attributes for item IDs listed
	#attributes are saved
	#/v3/universe/types/{type_id}/
	
	if len(item_ids) == 0:
		return
	
	urls = []
	for i_id in item_ids:
		url = esi_calling.construct_url( "/v3/universe/types/{}/", i_id )
		urls.append( url )
	response_array = esi_calling.call_many( urls )
	
	for response in response_array:
		#print(response)
		item_id = response.json()['type_id']
		item_cache[str(item_id)] = response.json()
	
	with gzip.GzipFile('item_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(item_cache, indent=2).encode('utf-8'))

def get_group_info(group_ids):
	#/v1/universe/groups/{group_id}/
	
	if len(group_ids) == 0:
		return
	elif len(group_ids) == 1:
		url = esi_calling.construct_url( "/v1/universe/groups/{}/", group_ids[0] )
		response = esi_calling.call_esi( url )
		group_id = response.json()['group_id']
		group_cache[str(group_id)] = response.json()
	else:
		urls = []
		for g_id in group_ids:
			url = esi_calling.construct_url( "/v1/universe/groups/{}/", g_id )
			urls.append( url )
		
		response_array = esi_calling.call_many( urls )
		
		for response in response_array:
			group_id = response.json()['group_id']
			group_cache[str(group_id)] = response.json()
	
	with gzip.GzipFile('group_cache.gz', 'w') as outfile:
		outfile.write(json.dumps(group_cache).encode('utf-8'))
	

def fetch_contracts(region_id):
	#10000044 = Solitude
	#Returns an array that contains all contracts of a region
	print_time('fetching contracts for region ID' + str(region_id) )
	
	all_contracts = []
	
	url = esi_calling.construct_url( '/v1/contracts/public/{}/', region_id )
	response_array = esi_calling.call_many_pages( url )
	
	for response in response_array:
		all_contracts.extend(response.json())
	print_time('Got {:,d} contracts.'.format(len(all_contracts)))
	
	
	return all_contracts


def import_orders(region_id):
	#'10000044' Solitude
	#10000002 = Jita
	print_time('fetching market for region ID' + str(region_id) )
	all_orders = []
	
	url = esi_calling.construct_url( '/v1/markets/{}/orders/', region_id )
	response_array = esi_calling.call_many_pages( url )
	
	for response in response_array:
		all_orders.extend(response.json())
	print_time('Got {:,d} orders.'.format(len(all_orders)))
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
	orders = import_orders(10000002)
	item_prices = get_item_prices(orders)
	#with open('item_prices.json', 'w') as outfile:
	#	json.dump(item_prices, outfile, indent=4)
	with gzip.GzipFile('item_prices.gz', 'w') as outfile:
		outfile.write(json.dumps(item_prices).encode('utf-8'))
	
	#Get attributes for all items listed on market
	print_time('Checking items')
	import_item_ids = []
	
	for key in item_prices:
		if not key in item_cache:
			import_item_ids.append(key)
	
	get_item_info(import_item_ids)
			
	#Get groups for all items and groups.
	import_group_ids = []
	
	for item_id in import_item_ids:
		group_id = str(item_cache[str(item_id)]['group_id'])
		if not group_id in group_cache:
			if not group_id in import_group_ids:
				import_group_ids.append( group_id )
	
	get_group_info(import_group_ids)
		
			

def evaluate_items(cost, contract_items):

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
			with gzip.GzipFile('item_cache.gz', 'w') as outfile:
				outfile.write(json.dumps(item_cache, indent=2).encode('utf-8'))
		if not str(item_cache[str(type_id)]['group_id']) in group_cache:
			print(". group not in group cache. Importing...")
			get_group_info([str(item_cache[str(type_id)]['group_id'])])
		
		if 'record_id' in item_dict:
			if group_cache[ str(item_cache[str(type_id)]['group_id']) ]['category_id'] == 8:
				#Do not value unstacked charges. They are most likely damaged
				continue
			if config['exlude_rigs'] and 'dogma_attributes' in item_cache[str(type_id)]:
				skip_item = False
				#Do not value unstacked rigs. They are fitted on the ship.
				# 1153 = Dogma attribute upgradeCost (rig calibration)
				for attribute in item_cache[str(type_id)]['dogma_attributes']:
					if attribute[ "attribute_id" ] == 1153:
						skip_item = True
				if skip_item:
					continue
		if item_cache[str(type_id)]['published'] == False:
			#Not on market
			continue
		
		if item_dict["is_included"] == False:
			if str(type_id) in item_prices:
				if 'sell_price' in item_prices[str(type_id)]:
					cost = cost + quantity * item_prices[str(type_id)]['sell_price']
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
			
		
	
	#Import items of contracts at once
	#Then evalueate them one by one
	
	contracts_to_import = len(uncached_contracts)
	print('Importing', contracts_to_import, 'contracts...')
	
	contract_ids = []
	for contract in uncached_contracts:
		if contract['type'] == 'item_exchange':
			contract_ids.append( str(contract['contract_id']) )
	
	urls = []
	response_array = []
	for c_id in contract_ids:
		url = esi_calling.construct_url( "/v1/contracts/public/items/{}/", c_id )
		urls.append( url )
	
	if contract_ids:
		response_array = esi_calling.call_many( urls )
	
	
		for response in response_array:
			for word in response.url.split("/"):
				if word.isdigit():
					c_id = word
					break
			
			if response.status_code in [204, 400, 403, 404,]:
				#[204, 400, 403, 404,] would mean expired or accepted contract. Leave [] for items.
				contract_cache[c_id]['items'] = []
			else:
				contract_cache[c_id]['items'] = response.json()
		
		with gzip.GzipFile('contract_cache.gz', 'w') as outfile:
			outfile.write(json.dumps(contract_cache, indent=2).encode('utf-8')) 
		
		
		#Check contracts for items that need to be imported (items that are not on market)
		print_time('\nchecking contracts for new items')
		print('  contracts:', len(contract_cache))
		all_items = []
		all_groups = []
		for contract_id in contract_cache:
			contract = contract_cache[contract_id]
			if 'items' in contract:
				for item_dict in contract['items']:
					type_id = item_dict['type_id']
					if not type_id in all_items:
						all_items.append(type_id)
		print_time('Found ' + str( len(all_items) ) + ' unique items in contracts. Checking items.')
		
		fetch_item_ids = []
		for type_id in all_items:
			if not str(type_id) in item_cache:
				fetch_item_ids.append(type_id)
		
		
		print('  importing item attributes for', len(fetch_item_ids), "items" )
		get_item_info(fetch_item_ids)
		
		fetch_group_ids = []
		for type_id in all_items:
			group_id = item_cache[ str(type_id) ]['group_id']
			if not group_id in group_cache:
				fetch_group_ids.append( group_id )
		
		print('  importing group attributes for', len(fetch_group_ids), "items" )
		get_group_info( fetch_group_ids )
		
		print_time('Item check done')
				
	
	number_of_contracts = len(all_contracts)
	index = 1
	
	
	#Now estimate the value of the contract
	for contract in all_contracts:
		print('  \ranalyzing ', index, '/', number_of_contracts, end="")
		index = index + 1
		
		if contract["type"] != "item_exchange":
			continue
		elif contract["start_location_id"] != 60003760 and config['jita_limit'] == True and config['region'] == 'The Forge':
			continue
		
		
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
		
	
	if len(profit_buy_contracts_array) == 0:
		print('  No profitable buy contracts')
	if len(profit_sell_contracts_array) == 0:
		print(" No profitable sell contracts" )
	else:	
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
	print_time('Importing regions')
	url = esi_calling.construct_url( '/v1/universe/regions/' )
	response = esi_calling.call_esi( url )
	
	regions = {}
	urls = []
	
	for r_id in response.json():
		url = esi_calling.construct_url( "/v1/universe/regions/{}/", r_id )
		urls.append( url )
	
	print('importing a region names...')
	response_array = esi_calling.call_many( urls )
	
	for response in response_array:
		for word in response.url.split("/"):
			if word.isdigit():
				region_id = word
				break
		region_name = response.json()["name"]
		regions[region_name] = region_id
		
	with open('regions.json', 'w') as outfile:
		json.dump(regions, outfile, indent=4)
	return regions
	
def region_selection():
	print('  Valid regions: ', list(regions) )
	user_input = input("Type in the region to import ")
	
	if user_input in regions:
		config['region'] = user_input
		with open('config.json', 'w') as outfile:
			json.dump(config, outfile, indent=4)
	else:
		print('  Invalid region. Try again')
		region_selection()
	
				
#--------------------------
#Preparations
#--------------------------

try:
	with gzip.GzipFile('item_cache.gz', 'r') as fin:
		item_cache = json.loads(fin.read().decode('utf-8'))
except:
	print_time('no item cache found')
	item_cache = {}

try:
	with gzip.GzipFile('group_cache.gz', 'r') as fin:
		group_cache = json.loads(fin.read().decode('utf-8'))
except:
	group_cache = {}

try:
	#item_prices = json.load(open('item_prices.json'))
	with gzip.GzipFile('item_prices.gz', 'r') as fin:
		item_prices = json.loads(fin.read().decode('utf-8'))
except:
	print_time('No market prices found')
	item_prices = {}
	import_prices()

try:
	#contract_cache = json.load(open('contract_cache.json'))
	print_time('loading cached contracts')
	with gzip.GzipFile('contract_cache.gz', 'r') as fin:
		contract_cache = json.loads(fin.read().decode('utf-8'))
except:
	print_time('No contract cache found')
	contract_cache = {}
	
#Delete old contracts
print_time('clening')
time_now = datetime.utcnow()
deletable_contracts = []
for contract_id in contract_cache:
	contract_expires = datetime.strptime(contract_cache[contract_id]['date_expired'], '%Y-%m-%dT%H:%M:%SZ') 
	if time_now - timedelta(0,600)  > contract_expires:
		deletable_contracts.append(contract_id)
print_time('Deleting ' + str(len(deletable_contracts) ) + ' expired contracts')
for contract_id in deletable_contracts:
	contract_cache.pop(contract_id, None)
print_time('Contract cache with ' + str(len( contract_cache )) + ' contacts')



	
try:
	regions = json.load(open('regions.json'))
except:
	print_time('No regions found')
	regions = import_regions()
	
try:
	config = json.load(open('config.json'))
except:
	#Default config
	config = {'region':'The Forge', "exlude_rigs": True, "jita_limit": True}
	with open('config.json', 'w') as outfile:
		json.dump(config, outfile, indent=4)


		

#-------------
#Start
#------------

while True:
	print('\n[R] Region to import contracts from (currently: ', config['region'], ')\n[J] Jita limiter (currently: ', config['jita_limit'], ')\n[E] Exclude fitted rigs (currently: ', config['exlude_rigs'], ')\n[M] Market data reimport\n[S] Start contract analysis')
	user_input = input("[R/M/S] ")
	if user_input in ['R', 'r']:
		region_selection()
	elif user_input in ['M', 'm']:
		import_prices()
	elif user_input in ['S', 's']:
		analyze_contracts()
	elif user_input in ['J', 'j']:
		config['jita_limit'] = not config['jita_limit']
		with open('config.json', 'w') as outfile:
			json.dump(config, outfile, indent=4)
	elif user_input in ['E', 'e']:
		config['exlude_rigs'] = not config['exlude_rigs']
		with open('config.json', 'w') as outfile:
			json.dump(config, outfile, indent=4)





































