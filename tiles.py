import sys, os, glob, time, uuid, csv, warnings, itertools, processing, numpy, boto3, uuid

start_time = time.time()

S3 = boto3.client('s3')

from processing.core.Processing import Processing

from shutil import copyfile
from osgeo import gdal
from osgeo import osr
from qgis.utils import *
from qgis.core import (
    QgsApplication,
    QgsProcessing,
    QgsProcessingFeedback,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsMapRendererParallelJob,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsProject,
    QgsMapSettings,
    QgsField,
    QgsFields,
    QgsWkbTypes
)

from qgis.gui import (
    QgsMapCanvas
)

from qgis.analysis import QgsNativeAlgorithms
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QFileInfo
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtCore import QSize

gdal.PushErrorHandler('CPLQuietErrorHandler')
gdal.UseExceptions()    # Enable exceptions

# warnings.filterwarnings("ignore", category=DeprecationWarning)  # ignore annoying Deprecation Warnings
warnings.filterwarnings("ignore")

# See https://gis.stackexchange.com/a/155852/4972 for details about the prefix
QgsApplication.setPrefixPath('/usr', True)
# set view to 3857 this will virtually reproject "on the fly" the raster
crs = QgsCoordinateReferenceSystem('EPSG:4326')

# make sure the enviroment is setup to be no screen or code
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
qgs = QgsApplication([], False)
qgs.initQgis()

# Append the path where processing plugin can be found
sys.path.append('/docs/dev/qgis/build/output/python/plugins')
Processing.initialize()

# Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
# overall progress through the model
feedback = QgsProcessingFeedback()
outputs = {}
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
canvas = QgsMapCanvas()

# Get the project instance
project = QgsProject.instance()
canvas.show()

def clipSource(imageSource, minX, maxX, minY, maxY, hash):
        print('grabbing image for processing tiles')
        RasterFormat = 'GTiff'
        # RasterFormat = 'VRT'
        PixelRes = 240
        #AWSPrefix = '/vsis3/'

        # Open dataset from AWS EFS
        #AWSRaster = gdal.Open(AWSPrefix + imageSource, gdal.GA_ReadOnly)
        uniqueHashTwo = str(uuid.uuid4())
        tmp = '/mnt/efs/tmp/' + uniqueHashTwo + '.tif'
        print('temp name' + tmp)
        copyfile(imageSource, tmp)
        AWSRaster = gdal.Open(tmp, gdal.GA_ReadOnly)
        RasterProjection = AWSRaster.GetProjectionRef()

        #create 3857 project definition
        epsg3857 = osr.SpatialReference()
        epsg3857.ImportFromEPSG(3857)

        #create 4326 project definition
        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        # Create clipped reprojected raster with unique hash
        outputName = '/mnt/efs/tmp/clipped_' + hash + '.tif'
        print('creating vrt with name' +str(outputName))
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

        clippedImageForTileCreation = None # Close dataset
        # garbage collection for source tif
        del AWSRaster
        AWSRaster = None
        os.remove(tmp)
        return outputName

# add raster and se
def addRaster(imageForTiles):
    # add raster for tiling
    rasterTileLayer = QgsRasterLayer(imageForTiles, 'TileLayer', 'gdal')

    if not rasterTileLayer.isValid():
        print('Tile Layer failed to load!')
    else:
        QgsProject.instance().addMapLayer(rasterTileLayer)

    return rasterTileLayer

# sets up enviroment for pyqgis
# creates a virtual canvas for the map wich is just the raster
def setupEnviroment(rasterTileLayer):
        bb = rasterTileLayer.extent()
        canvas.setExtent( bb )
        canvas.refresh()
        canvas.zoomToFullExtent()
        canvas.refreshAllLayers()
        vlayer = rasterTileLayer
        settings = QgsMapSettings()
        settings.setLayers([vlayer])
        settings.setBackgroundColor(QColor(255, 255, 255))
        settings.setOutputSize(QSize(256, 256))
        settings.setExtent(vlayer.extent())
        render = QgsMapRendererParallelJob(settings)
        render.start()
        return canvas

# add QGIS style file to the image
def addStyle(qgisStylePath, rasterTileLayer):
    # Set style for raster layer
    alg_params = {
        'INPUT': rasterTileLayer,
        'STYLE': qgisStylePath
    }
    outputs['SetStyleForRasterLayer'] = processing.run('qgis:setstyleforrasterlayer', alg_params, feedback=feedback, is_child_algorithm=True)
    return outputs

def deleteEmptyTiles(arg):
    ext = arg['extString']
    zoom = arg['zoomLevel']
    OutputTileDirectory = arg['OutputTileDirectory']
    tileDelDir = OutputTileDirectory + '/' + str(zoom)


    # delete empty tile images
    print('...Starting deleting empty tiles for zoom level ' + str(zoom))
    deleteEmptyFile(tileDelDir)
    print('...Completed deleting empty tiles for zoom level ' + str(zoom))
    return 0

# uplopads the tiles to s3
def uploadTiles(arg):
    ext = arg['extString']
    zoom = arg['zoomLevel']
    tileBucket = arg['tileBucket']
    tileFolder = arg['tileFolder']
    OutputTileDirectory = arg['OutputTileDirectory']
    tileDir = OutputTileDirectory + '/' + str(zoom)

    s3 = boto3.client('s3')

    for root, dirs, files in os.walk(tileDir):
        nested_dir = root.replace(tileDir, '')
        if nested_dir:
            nested_dir = nested_dir.replace('/','',1) + '/'

            for file in files:
                complete_file_path = os.path.join(root, file)
                file = nested_dir + file if nested_dir else file
                s3FolderAndFile = tileFolder + '/' + str(zoom) + '/' + file
                s3.upload_file(complete_file_path, tileBucket, s3FolderAndFile)
                s3.put_object_acl( ACL='public-read', Bucket=tileBucket, Key=s3FolderAndFile )
                print('...uploading file for the tile ' + tileDir + ' to ' + tileBucket + '/' + s3FolderAndFile)
                try:
                    os.remove(complete_file_path)
                except OSError:
                    pass
    return 0

# sets up and creates the tiles for a canvas
def createTiles(arg):
    # line_no, line, zoom, OutputTileDirectory = arg
    ext = arg['extString']
    zoom = arg['zoomLevel']
    OutputTileDirectory = arg['OutputTileDirectory']

    print('...Starting tiles for ' + str(ext) + ' at zoom level ' + str(zoom))

    params = {
        'BACKGROUND_COLOR' : QColor(0, 0, 0, 0),
        'DPI' : int(96),
        'EXTENT' :  ext + '[EPSG:3857]', # tell qgis the extent is being passed in as wgs84 which is the only way this works
        'METATILESIZE' : int(4),
        'OUTPUT_DIRECTORY' : OutputTileDirectory,
        'QUALITY' : int(100),
        'TILE_FORMAT' : int(0), # 0 = png, 1 - jpg use png or dieeeeeeee
        'TILE_HEIGHT' : int(256),
        'TILE_WIDTH' : int(256),
        'TMS_CONVENTION' : True, # this makes it valid in most map api's
        'ZOOM_MAX' : zoom,
        'ZOOM_MIN' : zoom
    }

    # create tiles
    feedback = QgsProcessingFeedback()
    res = processing.run('qgis:tilesxyzdirectory', params)
    print('...Completed tiles for ' + str(ext) + ' at zoom level ' + str(zoom) + ' to ' + OutputTileDirectory)

    args = (zoom, OutputTileDirectory, )
    deleteEmptyTiles(arg)
    uploadTiles(arg)

    return 0

# there are always blank tiles, 100% blank we delete them to save space
# the tile server can use a default blank png to repace all of them
def deleteEmptyFile(dir):
    time.sleep(1) # slight delay so file is written
    walk_dir = dir #'/data/tiles/' + zoom
    for root, subdirs, files in os.walk(walk_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            ext = os.path.splitext(file_path)[-1].lower()

            if ext == '.png':
                try:
                    ds = gdal.Open(file_path, gdal.GA_ReadOnly)
                    if ds is None:
                        continue

                    mem_drv = gdal.GetDriverByName('MEM')
                    if mem_drv is None:
                        continue

                    getband = ds.GetRasterBand(4)
                    if getband is None:
                        continue

                    alphaband = getband.GetMaskBand()
                    if alphaband is None:
                        continue

                    alpha = alphaband.ReadRaster()
                    if alpha is None:
                        continue

                    data = ds.ReadAsArray()
                    if data is None:
                        continue

                    fullcount = numpy.count_nonzero(data)
                    if fullcount is None:
                        continue

                    count255 = numpy.count_nonzero(data==255)
                    if count255 is None:
                        continue

                    # Detect totally transparent tile and skip its creation
                    # we when full count is less than 900 probably a sliver remove
                    if fullcount == count255 or fullcount <= 800:
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass

                except RuntimeError:
                        continue


def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    return "%d:%02d:%02d" % (hour, minutes, seconds)

#lambda handler function
def handler(event, context):
    # get events passed into lambda via string like this:
    # {
    #   "maxX": "0",
    #   "maxY": "85.051128514163",
    #   "minX": "0",
    #   "minY": "-179.999996920672",
    #   "zoomLevel": "1",
    #   "imageBucket": "data.southfact.com",
    #   "imageFile": "current-year-to-date/swirLatestChangeL8CONUS.tif",
    #   "styleBucket": "data.southfact.com",
    #   "styleFile": "qgis-styles-for-tile-creation/SWIR_SOUTHFACT_nodata_0.qml",
    #   "tileBucket": "tiles.southfact.com",
    #   "tileFolder": "latest_change_SWIR_L8",
    #   "efsPath": "/mnt/efs/swirLatestChangeL8CONUS.tif"
    # }

    # create new hash so functions do not collide with each other
    uniqueHash = str(uuid.uuid4())

    # aws source based on AWS s3 folder/image.tif
    # imageBucket = event['imageBucket']
    # imageFile = event['imageFile']
    # imageSource =  imageBucket + '/' + imageFile
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

    # this will always be temp and then will aws sync to s3
    OutputTileDirectory = '/mnt/efs/tmp/' + uniqueHash
    if not os.path.exists(OutputTileDirectory):
        os.makedirs(OutputTileDirectory, exist_ok=True)

    arg = {
        'extString': extString,
        'zoomLevel': zoomLevel,
        'OutputTileDirectory': OutputTileDirectory,
        'tileBucket': tileBucket,
        'tileFolder': tileFolder
    }

    # so more can be done at the same time. Also hash the path so no collisions
    qgisStylePath = '/mnt/efs/tmp/qgisstyle' + uniqueHash + '.qml'

    s3 = boto3.client('s3')

    s3.download_file(styleBucket, styleFile, qgisStylePath)

    imageForTiles = clipSource(efsPath, minX, maxX, minY, maxY, uniqueHash)
    # if (event['whichVRT'] == 'first'):
    #     print('first VRT')
    #     imageForTiles = '/mnt/efs/tmp/clipped_-179.999996920672_0_0_85.051128514163.vrt'
    # else:
    #     print('used other maxY')
    #     imageForTiles = '/mnt/efs/tmp/clipped_-78.74999865_31.95216175_-75.9374987_34.30714334.vrt'
    # #imageForTiles = '/mnt/efs/tmp/clipped_-78.7499986531.95216175-75.937498734.30714334.vrt'
    # #imageForTiles = '/mnt/efs/tmp/clipped_-78.7499986531.95216175-75.937498734.30714334.vrt'
    rasterTileLayer = addRaster(imageForTiles)
    rasterCRS = rasterTileLayer.crs()

    # only process is projection is valid
    if rasterCRS.isValid():

        # setup enviroment for qgis map
        setupEnviroment(rasterTileLayer)
        addStyle(qgisStylePath, rasterTileLayer)

        createTiles(arg)
    else:
        print("The raster does not have a valid projection, it's likely you created it with software that created a custom or vendor specific projection. You shoould try reprojecting the image with gdal, gdalwarp to a defined proj4 projection, the site http://spatialreference.org/ref/epsg/3031/ can help find the correct and known EPSG code.")

    QgsApplication.exitQgis()
    end_time = time.time()
    print("Took %s to create the tiles." % (convert(end_time-start_time)))
    return 0