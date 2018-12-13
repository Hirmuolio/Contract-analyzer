# Contract-analyzer

This python script will import all contracts of a single region and compare them to Forge (Jita is in there) prices of items. It will then give the user all the contracts that are cheaper than their contents.

## How to use
Simply run the contracts.py. 

On first run the script will start by importing the Forge (Jita) market data. The market data will be cached locally so it doesn't need to be rimported every time. When you want to get more recent market data choose `[M] Market data import` in main menu. You should reimport the market data every now and then to keep it up to date.

Select the region of which you want to import contracts of. You will need to write the name of the region exactly right.

Then start the import.

Results will be written in "profit.txt" in same folder. Copy the contents of this text file and paste it to mail writing window ingame. This will create clickable links to the contractrs.
If the profit.txt is too long to fit into the mail window you may need to copy-paste only part of it at a time.

At first the script may import lots of things like item attributes and groups without any progress bars. As long as it does not crash it will finish eventually. These will be cached so they do not need to be redownloaded.

### Incorrect results

The script has few cases where it will give incorrect results.
* All blueprint copies, abyssal modules and other items that are not available on Jita market are valued as worthless. If a contract wants to pay for a bluoeprint the script will think the payment is pure profit as you are giving worthless item in return.
* Only item exchange contracts are looked at. Auction and hauling contracts are ignored.
* The value estimations are based on the current highest buy order and current lowest sell order in Jita. The real value may be difrerent (beware the contract scam).
* All upackaged charge items are valued at zero isk. This to get rid of damaged ammo.
* The Forge region includes areas other than Jita.

## Requirements:
* Python 3
* Requests-futures https://github.com/ross/requests-futures
