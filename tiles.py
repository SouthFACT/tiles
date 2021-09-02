# import sys, os, glob, time, uuid, csv, warnings, itertools, processing, numpy, boto3, uuid
import sys, os, glob, time, uuid, csv, warnings, itertools, numpy, boto3, uuid
from osgeo import gdal
from osgeo import osr

start_time = time.time()

S3 = boto3.client('s3')
gdal.PushErrorHandler('CPLQuietErrorHandler')
gdal.UseExceptions()    # Enable exceptions

# warnings.filterwarnings("ignore", category=DeprecationWarning)  # ignore annoying Deprecation Warnings
warnings.filterwarnings("ignore")

def clipSource(imageSource, minX, maxX, minY, maxY, hash):
        print('grabbing image for processing tiles')
        # RasterFormat = 'GTiff'
        RasterFormat = 'VRT'
        PixelRes = 240
        AWSPrefix = '/vsis3/'

        # Open dataset from AWS EFS
        AWSRaster = gdal.Open(AWSPrefix + imageSource, gdal.GA_ReadOnly)
        print('AWSRaster' + AWSPrefix + imageSource)
        RasterProjection = AWSRaster.GetProjectionRef()
        print(RasterProjection)

        #create 3857 project definition
        epsg3857 = osr.SpatialReference()
        epsg3857.ImportFromEPSG(3857)

        #create 4326 project definition
        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        # Create clipped reprojected raster with unique hash
        outputName = '/tmp/' + hash + '.vrt'
        clippedImageForTileCreation = gdal.Warp(outputName,
                                                AWSRaster,
                                                format=RasterFormat,
                                                outputBoundsSRS=epsg4326,
                                                outputBounds=[minX, minY, maxX, maxY],
                                                xRes=PixelRes,
                                                yRes=PixelRes,
                                                srcSRS=RasterProjection,
                                                dstSRS=epsg3857,
                                                resampleAlg=gdal.GRA_Average,
                                                outputType=gdal.GDT_Byte,
                                                options=['COMPRESS=LZW'])

        # clippedImageForTileCreation = None # Close dataset
        # garbage collection for source tif
        del AWSRaster
        AWSRaster = None
        os.remove(outputName)
        return outputName

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    return "%d:%02d:%02d" % (hour, minutes, seconds)

# lambda hanlder function
def handler(event, context):
    # aws source based on AWS s3 folder/image.tif
    imageBucket = event['imageBucket']
    imageFile = event['imageFile']
    imageSource =  imageBucket + '/' + imageFile
    efsPath = event['efsPath']

    # the bounds of minX etc should be in WGS84 lat long and should be  a bounds of
    # equal to zoom level 7 box. the ideas is that the function will take in as argument a
    # the bounds for the entire tiled area so it can do it all at once in lambda
    # for southfact that is about 69 squares/processes once a day + one that does zoom-level 1-6
    minX = event['minX']
    maxX = event['maxX']
    minY = event['minY']
    maxY = event['maxY']

    #QGis style bucket, folder/filename.qml
    # of the options this is valid style file
    styleBucket = event['styleBucket']
    styleFile = event['styleFile']

    #tile cache bucket and folder
    tileBucket = event['tileBucket']
    tileFolder =  event['tileFolder']

    # zoom level to process
    zoomLevel = event['zoomLevel']

    # get arguments for tile
    extString = str(minX) + ',' + str(maxX) + ',' + str(minY) + ',' + str(maxY)

    s3 = boto3.client('s3')
    imageForTiles = clipSource(imageSource, minX, maxX, minY, maxY, uniqueHash)

    end_time = time.time()
    print("Took %s to create the tiles." % (convert(end_time-start_time)))
    return 0
