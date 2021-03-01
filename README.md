# Creates static tiles for SouthFACT
The idea here is to use QGIS to style the images then use the QGIS python API to create the tiles.  

#### Assumes
* Docker is installed
* AWS cli is installed and configured
* Linux is the Operation System (or on MAC terminal)
* Using Amazon Web Services

#### To DO
* Automate GeoTiff SouthFACT Change Images Copt from Drive to AWS
* Automate GeoTiff SouthFACT Change Images from AWS
* Automate updload to AWS


## Run Scripts
Run the following scripts from the terminal, or set as cron job, currently I would run each one separately unless you run on am xtra-large AWS server.
```
./process_latest_change_swirall.sh
./process_latest_change_ndvi.sh
./process_latest_change_swirthreshold.sh
./process_latest_change_ndmi.sh
```


## Create a AWS bucket to store your tiles
1. Its a good idea to name the bucket with domain and subdomain so it can be served i.e. ```tiles.southfact.com``` (only do this once)
2. Upload the entire folder created in the bash scripts below
* use the aws cli to do this

## Note
The process will remove all blank images from the tile cached to save space. It is up to ***you*** to redirect the missing tiles to a one single blank.png.  

In Amazons s3 we do it with this by going to the bucket properties and:

Adding this redirection rule:  
```
<RoutingRules>
  <RoutingRule>
    <Condition>
      <HttpErrorCodeReturnedEquals>404</HttpErrorCodeReturnedEquals>
    </Condition>
    <Redirect>
      <ReplaceKeyWith>blank.png</ReplaceKeyWith>
      <HttpRedirectCode>302</HttpRedirectCode>
    </Redirect>
  </RoutingRule>
</RoutingRules>
```

Add this as the index document: ```blank.png``` (blank.png must be in the route of the bucket hosting the tile directories)

![blank.png](aws-blankpng-redirect.png?raw=true "blank.png")

