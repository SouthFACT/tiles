# Creates static tiles for SouthFACT
The idea here is to use QGIS to style the images then use the QGIS python API to create the tiles.  

#### Assumes
* Docker is installed
* AWS cli is installed and configured
* Linux is the Operation System (or on MAC terminal)
* Using Amazon Web Services

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


# Create Lambda function for tile creations

### Push docker image and tile creation code to AWS ECR so we can use it in lambda function

#### set env variables for aws key and secret id for the ecr user obviously use the correct key id and key. do commit to GH
```
AWS_ACCESS_KEY_ID=[the correct AWS aws_access_key_id]
AWS_SECRET_ACCESS_KEY=[the correct AWS aws_secret_access_key]
AWS_REGION=us-east-1
```

#### login using the repository uri
you will need a AWS profile named southfactecr with the correct IAM permission to upload a container image
```
aws ecr get-login-password --region us-east-1 --profile southfactecr | docker login --username AWS --password-stdin 937787351555.dkr.ecr.us-east-1.amazonaws.com
```

#### in separate terminal with the correct IAM user default defend as environmental variables
```
docker build -t test-tiles-img . --build-arg AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID --build-arg AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
```

#### back on the original terminal window
```
docker tag test-tiles-img 937787351555.dkr.ecr.us-east-1.amazonaws.com/tiles-test
```

### pushes to the AWS repo
```
docker push 937787351555.dkr.ecr.us-east-1.amazonaws.com/tiles-test
```

## After the image is pushed you will need redeploy the image in the console

