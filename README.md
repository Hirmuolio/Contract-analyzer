# Contract-analyzer

This python script will import all contracts of a single region and compare them to Forge (Jita is in there) prices of items. It will then give the user all the contracts that are cheaper than their contents.

## How to use
Simply run the contracts.py. 

On first run the script will start by importing the Forge (Jita) market data. The market data will be cached locally so it doesn't need to be rimported every time. When you want to get more recent market data choose `[M] Market data import` in main menu. You should reimport the market data every now and then to keep it up to date.

Select the region of which you want to import contracts of. You will need to write the name of the region exactly right.

You may also enable/disable the "Jita limiter". When this is enabled the script will ignore contracts in Forge region that are not located in Jita 4-4. This setting has no effect in other regions.

You may also enable/disable the "Exclude fitted rigs" option. With this enabled the script will ignore rigs that are fitted on ships. More specifically it will ignore rigs that are not packaged, AFAIK fitting them on ships is only way to unpackage them.

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
* When items are removed from market the old market orders will stay up. As a result the script will think that expired cerebral accelerators are still traded and gives them some value. To fix this you will need to delete the item cache. This will force the script to refresh the attributes for all items and it will then see that those items are not supposed to be on market anymore.
* Sometimes the script crashes for no good reason. Rerunning the script makes it work (probably something to do with cache. Happens usually on the first run).

## Requirements:
* Python 3
* Request futures https://github.com/ross/requests-futures
* Requests-futures https://github.com/ross/requests-futures
