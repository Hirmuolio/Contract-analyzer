#!/usr/bin/env python3

import json
import esi_calling
import requests
import datetime

def fetch_contracts(region_id):
	#10000044 = Solitude
	print('fetching contracts')
	
	all_contracts = []
	
	#/v1/contracts/public/{par}/
	response = esi_calling.call_esi(scope = '/v1/contracts/public/{par}/', url_parameter=region_id, job = 'get region contracts')
	
	all_contracts.extend(response.json())
	total_pages = int(response.headers['X-Pages'])
	print('total number of pages:'+str(total_pages))
	
	#Import rest of the pages
	responses = []
	for page in range(2, total_pages + 1):
		print('\rimportin page: '+str(page)+'/'+str(total_pages), end="")
		response = esi_calling.call_esi(scope = '/v1/contracts/public/{par}/', url_parameter=region_id, parameters = {'page': page}, job = 'get region contracts')
		responses.append(response)
	for response in responses:
		data = response.json()
		all_contracts.extend(data)
	print('. Got {:,d} contracts.'.format(len(all_contracts)))
	return all_contracts


def import_orders(region_id):
	#'10000044' Solitude
	#10000002 = Jita
	print('importin page 1')
	all_orders = []
	
	response = esi_calling.call_esi(scope = '/v1/markets/{par}/orders/', url_parameter=region_id, job = 'get market orders')
	
	all_orders.extend(response.json())
	total_pages = int(response.headers['X-Pages'])
	print('total number of pages:'+str(total_pages))
	
	responses = []
	for page in range(2, total_pages + 1):
		print('\rimportin page: '+str(page)+'/'+str(total_pages), end="")
		
		response = esi_calling.call_esi(scope = '/v1/markets/{par}/orders/', url_parameter=region_id, parameters = {'page': page}, job = 'get market orders')
		
		responses.append(response)
	for response in responses:
		data = response.json()
		all_orders.extend(data)
	print('. Got {:,d} orders.'.format(len(all_orders)))
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
	

	if contract["type"] != 'item_exchange':
		return {'profit_sell': 0, 'profit_buy':0}

	contract_id = contract['contract_id']
	cost = contract['price'] - contract['reward']
	
	#items 
	# /v1/contracts/public/items/{par}/
	response = esi_calling.call_esi(scope = '/v1/contracts/public/items/{par}/', url_parameter=contract_id, job = 'get region contract items')
	raw_items = response.json()
	
	value_sell = 0
	value_buy = 0
	
	for item_dict in raw_items:
		if 'is_blueprint_copy' in item_dict:
			continue
		quantity = item_dict['quantity']
		type_id = item_dict['type_id']
		
		if str(type_id) in item_prices:
			if 'sell_price' in item_prices[str(type_id)]:
				value_sell = value_sell + quantity * item_prices[str(type_id)]['sell_price']
			if 'buy_price' in item_prices[str(type_id)]:
				value_buy = value_buy + quantity * item_prices[str(type_id)]['buy_price']
	
	
	profit = {'profit_sell': value_sell - cost, 'profit_buy':value_buy - cost}
	return profit



def import_prices():
	#Import Jita prices and save
	print('Importing market prices')
	orders = import_orders(10000002)
	item_prices = get_item_prices(orders)
	with open('item_prices.json', 'w') as outfile:
		json.dump(item_prices, outfile, indent=4)

def analyze_contracts():
	all_contracts = fetch_contracts(10000002)
		
	contract_values = {}
	profitables = {'profit_sell':{}, 'profit_buy':{}}
	number_of_contracts = len(all_contracts)
	index = 1
	for contract in all_contracts:
		print('impoting ', index, '/', number_of_contracts)
		index = index + 1
		
		profit = evaluate_contract( contract)
		
		contract_values[contract['contract_id']] = {'profit_sell':profit['profit_sell'], 'profit_buy':profit['profit_buy']}
		with open('contract_values.json', 'w') as outfile:
				json.dump(contract_values, outfile, indent=4)
		
		if profit['profit_buy'] > 0:
			#profitable contract
			clickable = "<url=contract:30003576//" + str(contract['contract_id']) + ">Profit sell</url>" + str(round(profit['profit_buy']) )
			profitables['profit_buy'][contract['contract_id']] = clickable
			with open('profit.txt', 'w') as outfile:
				json.dump(profitables, outfile, indent=4)
				
		elif profit['profit_sell'] > 0:
			#profitable contract
			clickable = "<url=contract:30003576//" + str(contract['contract_id']) + ">Profit sell</url>" + str(round(profit['profit_sell']) )
			profitables['profit_sell'][contract['contract_id']] = clickable
			with open('profit.txt', 'w') as outfile:
				json.dump(profitables, outfile, indent=4)
	print('Analysis completed')

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
		main_menu()
	else:
		print('Invalid region. Try again')
		region_selection()
	

				
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
	item_prices = json.load(open('item_prices.json'))
except:
	print('No market prices found')
	import_prices()

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
	
main_menu()



print('done')



































