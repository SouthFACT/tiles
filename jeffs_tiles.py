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

print("this is the version of gdal: " + str(gdal.VersionInfo()))
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
        tmp = '/app/' + uniqueHashTwo + '.tif'
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
        outputName = '/app/clipped_' + hash + '.tif'
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