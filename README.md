# Contract-analyzer

This python script will import all contracts of a single region and compare them to Forge (Jita is in there) prices of items. It will then give the user all the contracts that are cheaper than their contents.

## How to use
Simply run the contracts.py. 

The download will include market data but it will be outdated. In  the main menu choose `[M] Market data import` to import fresh market data of Jita. You should reimport the market data every now and then to keep it up to date.

Select the region of which you want to import contracts of. You will need to write the name of the region exactly right.

Then start the import.

Results will be written in "profit.txt" in same folder. Copy the contents of this text file and paste it to mail writing window ingame. This will create clickable links to the contractrs.
If the profit.txt is too long to fit into the mail window you may need to copy-paste only part of it at a time.

### Incorrect results

The script has few cases where it will give incorrect results.
* All blueprint copies, abyssal modules and other items that are not available on Jita market are valued as worthless. If a contract wants to pay for a bluoeprint the script will think the payment is pure profit as you are giving worthless item in return.
* Only item exchange contracts are looked at. Auction and hauling contracts are ignored.
* The value estimations are based on the current highest buy order and current lowest sell order in Jita. The real value may be difrerent (beware the contract scam).
* The Forge region includes areas other than Jita.

## Requirements:
* Python 3
* Requests http://docs.python-requests.org/en/master/
