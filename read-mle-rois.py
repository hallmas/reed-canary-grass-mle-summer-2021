# ----===USER SETTINGS===----

#PATH FOR THE TEMPORARY LAYERS (string (must be a valid directory with a '/' at the end; example: "c:/rcg/"))
directory = "c:/qgis-mle/"
#This directory will determine where the temporary layers are placed.
#THIS MUST BE SET TO A VALID DIRECTORY for this script to run.
#However, the directory does not need to already exist, as the script will create a new directory if it's not already there

#ROI CLASS IDENTIFIER (string)
roi_class_identifier = "class-id"
#This string is used to determine the class of each ROI, the name of the field (attribute), whose value is set to a number for the class of the ROI
#This will be set to the attribute name that identifies the roi feature within the mle-roi shapefile

#TREATMENT AREA IDENTIFIER (string)
treatment_area_identifier = "PlotName"
#This script was made to iterate over treatment areas and provide results for each of these treatments,
#This will be set to the attribute name that identifies the treatment area feature within the treatment-areas shapefile

#ROI VALIDIATION PROPORTION (min = 0, max = 1)
roi_validation_proportion = 0.33
#Determines the proption of ROIs in each class that will be selected for validation
#Example: If roi_validation_proportion == 0.33, then 1/3 of the ROIs will be used for
#validation, and the remaining 2/3 will be used for classifiction

#ROI VALIDATION SELECTION PSEUDO-RANDOM (True/False)
roi_validation_pseudo_random = True
#If True, the random selection will only be re shuffled when ROIs are added or removed
#If False, every time the program is run (even if the ROIs are not changed) the selection
#of which are used for validation/classification will be shuffled again, which will yield different results

#MINIMUM PROBABILITY PER BAND (min = 0, max = 1)
mle_minimum_probability = 0.001
#Upon iteration of the Normal Distribution Probability Density Function (NDPDF) at all the bands within 1 pixel, the determined
#probability (equal to (the result of NDPDF) ^ (the number of bands)) must be greater than (mle_minimum_probability) ^ (the number of bands)
#otherwise, the pixel will be classified as "unclassified"



#--=ADDITIONAL DEBUG OPTIONS=--

#PIXEL READ LOOP MAX (min = 0, max = infinity)
pixel_read_loop_max = 1000
#IF NOT DEBUGGING, LEAVE THIS AT 0
#If this set to 0, all pixels will be read as normal
#If this is set to above 0, only that many pixels will be read before the algorithm stops early.

#PIXEL READ PROPORTION (min = 0, max = 1)
pixel_read_proportion = 0.125
#IF NOT DEBUGGING, LEAVE THIS AT 1
#If this is set to a value below 1, only that proportion of pixels will be read,
#When this is below 1, pixels can also be skipped for validation, so this really messes with the validation results


#--==end of user settings==--

#Imports, etc.
from PIL import Image as im
import urllib.request
import random
import numpy as np
from matplotlib.pyplot import imshow
import os
import math
import time

from osgeo import gdal
gdal.AllRegister()

#Create the directory if it doesn't already exist
if not os.path.exists(directory):
    os.mkdir(directory)
if not os.path.exists(directory+"temp/"):
    os.mkdir(directory+"temp/")
if not os.path.exists(directory+"temp/shapes"):
    os.mkdir(directory+"temp/shapes")
if not os.path.exists(directory+"temp/visual_output"):
    os.mkdir(directory+"temp/visual_output")

#Start a timer
start_time = time.time()

#Define the bands that will be used with a dictionary.
#Format: 
#band_info = {
#    band_number: [wavelength(nm), "wavelength(nm) as string", "empty value that will later hold this band's raster layer"]
#}
band_info  = {
	1: [550,"550",""],
	2: [650,"650",""],
	3: [710,"710",""],
	4: [850,"850",""]
}

#These 4 variables will all later be set the their apporopriate shapefiles
#An empty string is only used for a placeholder until the script can find the layers
roi_shapefile = ""
merged_roi_shapefile_classification = ""
merged_roi_shapefile_validation = ""
treatment_areas = ""

#Class_statistics is a dictionary that will later be filled,
#this will be used to store the statistics calculated on the "merged-rois-classification" shapefile,
#for faster access in the MLE calculation
class_statistics_dict = {}
#These indeces are used as keys in the class_statistics_dict dictionary
index_mean = 0
index_stdev = 1


#This dictonary will be used to sort the ROIs from the "mle-roi" shapefile,
#so that some can be used for training, and some for validation
class_roi_dict = {}
#These indeces are used as keys in the class_roi_dict dictionary
index_training_roi = 1
index_validation_roi = 2

#The numbers will be used in the Normal_Distribution_Probability_Density function
euler = math.e
pi = math.pi

#Make a string to track all of the missing layers as an error message. The program will only run if this reamins empty
missing_layers_error_message = ""

print("Reading Layers and setting variables...")
#Read and set variables that were unset above
#the layers variable will be used to access all the map layers in the current QGIS project
layers = QgsProject.instance().mapLayers().values()
#This will loop over every band, searching for map layers with the string "(wavelength)nm" in their title, such as "550nm"
for b in band_info:
    for layer in layers:
        if band_info[b][1]+"nm" in layer.name():
            #Once a layer is found that matches the criterion, the third value in the band_info dictionary will be set to that layer, so it can be accessed later
            band_info[b][2] = layer
for layer in layers:
    if "mle-roi" in layer.name():
        #the variable roi_shapefile is set so that the ROIs can be accessed later
        roi_shapefile = layer
    #CHANGE TO treatment-areas
    if "treatment-areas" in layer.name():
        #the variable roi_shapefile is set so that the treatment areas can be accessed later
        treatment_areas = layer

#All the layers will be printed if they were found, and appened to the error message if they were not
for b in band_info:
    #error messages for missing rasters
    if band_info[b][2] == "":
        missing_layers_error_message = missing_layers_error_message+"\nERROR: "+band_info[b][1]+"nm Raster Not found!\n'"+band_info[b][1]+"nm' must be in the title of a single raster layer.\n"
    else:
        print(band_info[b][1]+" tif layer: "+band_info[b][2].name())

#error message for missing Roi shapefile
if roi_shapefile == "":
    missing_layers_error_message = missing_layers_error_message+"\nERROR: mle-roi shapefile not found!\n'mle-roi' must be in the title of a single shapefile layer.\n"
else:
    print("ROI Shapefile: "+roi_shapefile.name())
   
#error message for missing treatment areas shapefile
if treatment_areas == "":
    missing_layers_error_message = missing_layers_error_message+"\nERROR: treatment-areas shapefile not found!\n'treatment-areas' must be in the title of a single shapefile layer.\n"
else:
    print("Treatment Areas: "+treatment_areas.name())




#If the error message is not empty, then print it. Otherwise, continue
if missing_layers_error_message != "":
    print(missing_layers_error_message)
else:

    #Set the raster pixel scales for x and y, read directly from the raster's properties
    raster_pixel_scale_x = band_info[1][2].rasterUnitsPerPixelX()
    raster_pixel_scale_y = band_info[1][2].rasterUnitsPerPixelY()
    #If the Debug option for reading only a portion of the pixels is set, then adjust the raster
    #pixel scales to be larger, so more distance is covered with each iteration of the pixel read for loop
    if pixel_read_proportion < 1:
        square_pixel_scale = raster_pixel_scale_x * raster_pixel_scale_y
        proportion_of_squared_pixel_size = square_pixel_scale / pixel_read_proportion
        #This also accurately adjusts for area, so that the set proportion is equal to the two-dimensional proportion because pixels are 2D
        scaled_pixel_scale_xy = math.pow(proportion_of_squared_pixel_size,0.5)
        raster_pixel_scale_x = scaled_pixel_scale_xy
        raster_pixel_scale_y = scaled_pixel_scale_xy
    #Print variables to confirm they were set
    print("raster pixel scale x: "+str(raster_pixel_scale_x))
    print("raster pixel scale y: "+str(raster_pixel_scale_y))


    print("Layers read and variables set.\n\n")
    #If this script was previously ran in the same instance, the temporary layers will remain, so remove them if they exist, counting how many were deleted
    print("Clearing Temporary Layers...")
    num_layers_cleared = 0
    for layer in layers:
        if "merged-rois" in layer.name():
            QgsProject.instance().removeMapLayer(layer.id())
            num_layers_cleared += 1
    print("Temporary Layers Cleared: "+str(num_layers_cleared)+".\n\n")


    #Count the total number of ROIs, this number will only be used to seed the selection for ROIs for validation
    print("Counting ROIs...")
    num_rois = 0
    for roi in roi_shapefile.getFeatures():
        num_rois += 1
        # print("ROI class: "+str(roi.attribute(roi_class_identifier)))
    print(str(num_rois)+" ROIs Counted.\n\n")


    #This function will return a list of unique colors from a number n.
    #The colors returned will be as different as possible, given n
    #This function could definetley be shortned to a fraction of the lines
    def Generate_Class_Colors(n):
        class_colors_tbl = {
            -1: [0,0,0]
        }
        for i in range(1,n+1):
            r = 0
            g = 0
            b = 0
            #p represents the proprtion of the current iteration, if there are 2 colors (n = 2),
            #p will first be 0.5 and then 1
            p = i/n
            #This six state conditional has one condition for each of the 6 "phases" in the color variation method used
            #one phase each for increase/decrease of r/g/b, (2*3 = 6) 
            if p > 0 and p <= 1/6:
                r = 255
                g = 1530*p
                b = 0
            elif p > 1/6 and p <= 2/6:
                r = 255-(1530*(p-(1/6)))
                g = 255
                b = 0
            elif p > 2/6 and p <= 3/6:
                r = 0
                g = 255
                b = 1530*(p-(2/6))
            elif p > 3/6 and p <= 4/6:
                r = 0
                g = 255-(1530*(p-(3/6)))
                b = 255
            elif p > 4/6 and p <= 5/6:
                r = 1530*(p-(4/6))
                g = 0
                b = 255
            elif p > 5/6 and p <= 1:
                r = 255
                g = 0
                b = 255-(1530*(p-(5/6)))
            class_colors_tbl[i] = [math.floor(r),math.floor(g),math.floor(b)]
        # print(class_colors_tbl)
        return class_colors_tbl


    #Count the number of unique classes among the ROIs in the roi-shapefile
    print("Counting Number of Classes...")
    unique_roi_ids = []
    for roi in roi_shapefile.getFeatures():
        roi_id = roi.attribute(roi_class_identifier)
        if not roi_id in unique_roi_ids:
            unique_roi_ids.append(roi_id)
    #adjust the minimum probability for one band by putting it the power of the number of bands
    mle_adjusted_minimum_probability = math.pow(mle_minimum_probability,len(unique_roi_ids))
    #create a list of unique colors for each class
    class_colors = Generate_Class_Colors(len(unique_roi_ids))
    print(str(len(unique_roi_ids))+" Classes Counted.\n\n")
    print(class_colors)




    
    #make an image for each class, so the color can be quantified
    
    print("Creating an image with the color of each class")
    output_image_dir = directory+"temp/visual_output/"+time.strftime("%Y-%m-%d_%H-%M-%S",time.localtime())
    os.mkdir(output_image_dir)
    class_color_image_dimensions = 128
    #loop over every class
    for class_id in unique_roi_ids:
        class_color = class_colors[class_id]
        #Create an image 128x128
        class_color_image_array = np.zeros((class_color_image_dimensions,class_color_image_dimensions,3),dtype=np.uint8)
        #loop over every x and y to fill the image with the class color
        for x in range(0,class_color_image_dimensions):
            for y in range(0,class_color_image_dimensions):
                class_color_image_array[x,y] = class_color
        class_color_image = im.fromarray(class_color_image_array,'RGB')
        class_color_image_filename = "class_"+str(class_id)+"_color.png"
        class_color_image_filename_path = output_image_dir+"/"+class_color_image_filename
        class_color_image.save(class_color_image_filename_path,'PNG',quality=100)
        print("class color saved as "+class_color_image_filename_path)



    print("Sorting ROIs for training/validation...")
    #Make a simple list, and fill it with every ROI from roi-shapefile
    shuffled_feature_list = []
    for roi in roi_shapefile.getFeatures():
        shuffled_feature_list.append(roi)
    #Now shuffle the simple list, this one will be used in the ROI sorting
    if roi_validation_pseudo_random:
        random.seed(num_rois) 
    random.shuffle(shuffled_feature_list)
    #Every class must be iterated over so that each ROI of that class can be assigned to classification or validation
    for class_id in unique_roi_ids:
        #the class_roi_dict dictionary's first index is the class identified, then each entry contains
        #a list of all the ROIs that belong to this class, stored as "QgsFeature"s
        class_roi_dict[class_id] = {
            index_training_roi: [],
            index_validation_roi: []
        }
        #Now, each roi from the shuffled roi list is iterated over
        for roi in shuffled_feature_list:
            #Because every single ROI (regardless of class) is iterated over during each class id iteration,
            #We have to check of the current ROI's id matches the current class's ID
            if class_id == roi.attribute(roi_class_identifier):
                #Find the lists of the current ROI assignments within this class, one for classification, and one for validation
                class_training_list = class_roi_dict[class_id][index_training_roi]
                class_validation_list = class_roi_dict[class_id][index_validation_roi]
                #Get these lists' lengths
                class_training_length = len(class_training_list)
                class_validation_length = len(class_validation_list)
                #The first ROI will always be assigned to classification, and the second to validation, regardless of the proportion.
                if class_training_length == 0:
                    class_training_list.append(roi)
                elif class_validation_length == 0:
                    class_validation_list.append(roi)
                #If there is already one ROI for classification and one for verification, then the roi_validation_proportion will be used to sort the rest
                else:
                    if class_validation_length < class_training_length * roi_validation_proportion:
                        class_validation_list.append(roi)
                    else:
                        class_training_list.append(roi)
    print("ROIs sorted.\n\n")



    print("Merging training ROIs for statistics collection...")
    #The ROIs need to be merged, so that the mean and stdev can be calculated for the population of all pixels in all ROIs of the same class
    #Create a new layer for the merged ROIs
    shape_directory = directory+"temp/shapes/"+time.strftime("%Y-%m-%d_%H-%M-%S/",time.localtime())
    os.mkdir(shape_directory)
    #temp_fields will store the fields for the temporary layer. These are copied from the fields in the mle-roi shapefile
    temp_fields = roi_shapefile.fields()
    #This is a simple for loop so that two merged shapefile layers can be created
    #This short dictionary contains the info for the differences between the two layers
    #One is for classification, and one is for validation
    merged_roi_info = {
        index_training_roi: ["classification"],
        index_validation_roi: ["validation"]
    }
    for roi_type in merged_roi_info:
        #First we specify the directory to the shapefile, then create the shapefile 
        filename = shape_directory+"merged-rois-"+merged_roi_info[roi_type][0]+".shp"
        writer = QgsVectorFileWriter(filename,"UTF-8",temp_fields,QgsWkbTypes.Polygon,QgsCoordinateReferenceSystem("EPSG:2913"),"ESRI Shapefile")
        for class_id in unique_roi_ids:
            print("Adding class "+str(class_id)+" to "+merged_roi_info[roi_type][0]+".shp")
            
            #rois will be the list of roi geometries that need to be merged
            rois = class_roi_dict[class_id][roi_type]
            
            #For every class id, one feature is added to the merged shapefile. 
            feature = QgsFeature(roi_shapefile.fields(),class_id)
            #The first attribute (indexed from 0) will be set to the class id, so that it can be properly read later
            feature.setAttribute(0,class_id)
            #Setting the geometry to an existing geometry (Is the only way I could find) to properly initialize it
            merged_roi = QgsGeometry(rois[0].geometry())
            #Because of this, the geometry is initially set to the geometry from only the first roi (on the line above),
            #then the for loop will add the rest of the geometries, skipping the first one so it isn't added a second time
            skip = True
            for roi in rois:
                if skip:
                    skip = False
                else:
                    roi_geom = roi.geometry()
                    merged_roi.addPartGeometry(roi_geom)
            #Now we set the new feature's geometry to the geometry that contains all the rois of the class merged into one
            feature.setGeometry(merged_roi)
            #Now the new feature will be added to the temporary layer
            writer.addFeature(feature)
        #Finally, the layer is added to the project and the writer is deleted
        iface.addVectorLayer(filename,"","ogr")
        del(writer)



    #Identify the new layer as the shapefile that will be used for statistics collections
    for layer in QgsProject.instance().mapLayers().values():
        if "merged-rois-classification" in layer.name():
            merged_roi_shapefile_classification = layer
        elif "merged-rois-validation" in layer.name():
            merged_roi_shapefile_validation = layer
    print("ROIs merged, ready to collect statistics.\n\n")



    print("Calculating Mean and StDev...")
    #This for loop simply runs that zonal statistics tool on each of the new merged shapes.
    #Zonal statistics will output the results of the statistics by automatically adding new attributes to the shapefile (merged_roi_shapefile_classification) used
    #This needs to loop over every band so, the difference between each iteration is the raster layer to collect statistics from
    for b in band_info:
        QgsZonalStatistics(
            #The first argument to QgsZonalStatistics() is the shapefile to collect statistics inside of (meaning the pixels in the raster that overlap this shapefile will be the sample)
            merged_roi_shapefile_classification,
            #The second argument is the raster layer whose pixels will be read
            band_info[b][2],
            #The third argument is the prefix on the title of the attribute column that will be added to the shapefile to sotre the results
            band_info[b][1]+"_",
            #The fourth argument is the band within the raster to read.
            #Because this script is built to used multiple raster layers, each with one band, this value is always 1
            1,
            #The fifth argument is which statistics to calculate, this also determines the suffix the the appened attribute's title
            QgsZonalStatistics.Statistics(QgsZonalStatistics.Mean)
        ).calculateStatistics(None)
        #Same thing as acove, only difference this time is StDev is calculated instead of Mean
        QgsZonalStatistics(
            merged_roi_shapefile_classification,
            band_info[b][2],
            band_info[b][1]+"_",
            1,
            QgsZonalStatistics.Statistics(QgsZonalStatistics.StDev)
        ).calculateStatistics(None)
    print("Calculated Mean and StDev.\n\n")



    print("Generating Statistics Dictionary...")
    #The dictionary that will store the statistics for quick access must now be filled by reading the attributes that were appended
    #to the shapefile by QgsZonalStatistics()
    merged_features = merged_roi_shapefile_classification.getFeatures()
    for class_id in unique_roi_ids:
        for merged_roi in merged_features:
            if class_id == merged_roi.attribute(roi_class_identifier):
                current_class_stats = {}
                for b in band_info:
                    wavelength_num = band_info[b][0]
                    wavelength_string = band_info[b][1]
                    current_class_stats[wavelength_num] = {
                        index_mean: merged_roi[wavelength_string+"_mean"],
                        index_stdev: merged_roi[wavelength_string+"_stdev"],
                    }
                class_statistics_dict[class_id] = current_class_stats
                break
    # print(class_statistics_dict)
    print("Statistics Dictionary Generated\n\n")



    #Actual equation for probability of a particular variable (band) for a given item (pixel).
    def Normal_Distribution_Probability_Density(x,mean,sd):
        return (1/(sd*(math.pow(2*pi,0.5))))*math.pow(euler,(-1/2)*math.pow(((x-mean)/(sd)),2))

    #this function will actually consider the values at all bands in the table passed into it
    #This function is ran once for every pixel read,
    #so this function is only classifiying one pixel each time it is called
    def MLE(value_list):
        #initilize the highest found likelihood to 0
        max_likelihood = 0.0
        #Initilize the class id identified to -1. if not one class exceeds the minimum likelihood, we will return 0 for unclassified
        max_likelilood_class_id = -1
        #loop over all class ids
        for class_id in unique_roi_ids:
            #access the dictionary at the index of the current class to get the mean and stdev
            class_stats = class_statistics_dict[class_id]
            #because this probability will be multipled by the probabilty at each band, initilize it to 1
            total_class_probability = 1
            for b in band_info:
                #Band_info is indexed from 1, while value list is indexed from 0,
                #so subtract 1 from b to index the value list
                current_pixel_value = value_list[b-1]
                #get the num of the wavelength to access that band in the stats dictionary
                wavelength = band_info[b][0]
                band_stats = class_stats[wavelength]
                band_mean = band_stats[index_mean]
                band_stdev = band_stats[index_stdev]
                #Now pass the pixel's value, class's mean at this band, and class's stdev at this band into the NPDFunction
                current_band_probability = Normal_Distribution_Probability_Density(current_pixel_value,band_mean,band_stdev)
                #Multiply the class's total probability for all bands together
                total_class_probability *= current_band_probability
                
            #now that we have to collective probabilities from this class multiplied together, we can see if it exceeds
            #the minimum probability and the highest proability (maximum likelihood) found from all classes
            if total_class_probability >= mle_adjusted_minimum_probability and total_class_probability > max_likelihood:
                #If so, update the class that has now been deemed to be most likely the true container of this pixel
                max_likelihood = total_class_probability
                max_likelilood_class_id = class_id
        #After iterating over all classes, return the id of the class that had the estimated maximum likelihood based off of the NPDF
        return max_likelilood_class_id

    #This dictionary will store the number of classified pixels,
    #and the class that they were classified into as well as the treatment group they were read from
    print("Generating Dictionary to Track Classified Pixels...")
    classified_pixel_dictionary = {}
    for feature in treatment_areas.getFeatures():
        plotname = feature.attribute(treatment_area_identifier)
        #Initilize index -1 to zero to represent unclassifed pixels
        plot_counts = {
            -1: 0
        }
        for class_id in unique_roi_ids:
            plot_counts[class_id] = 0
        classified_pixel_dictionary[plotname] = plot_counts
        # print(classified_pixel_dictionary)
    print("Empty Classified Pixel Dictionary Generated.\n\n")


    #This function will space the text in the printing of the confusion matrix
    def SpaceText(val,num_chars,first_char,last_char):
        text = str(val)
        for i in range(len(text),num_chars):
            if i%2 == 0:
                text = text+" "
            else:
                text = " "+text
        return first_char+text+last_char
    
    #the confusion matrix will be generated as a dictionary
    print("Generating Confusion Matrix to Validate Classified Pixels...")
    cm_characters_per_entry = 5
    confusion_matrix = {}
    #one row and column for each class,
    #and 1 column (but no row) for unclassified (-1)
    for class_id in unique_roi_ids:
        matrix_row = {
            -1: 0
        }
        for class_id_2 in unique_roi_ids:
            matrix_row[class_id_2] = 0
        confusion_matrix[class_id] = matrix_row
    print("Confusion Matrix Generated.\n\n")


    #the image bounds must be calculated, finding the smallest and largest x and y values of all pixels that will be read
    #this is so an array can be generated to store the classified pixels' values,
    #this array will later be transformed into and saved as an image
    print("Calculating Bounds for output image...")
    output_image_x_min = 9999999999
    output_image_x_max = 0
    output_image_y_min = 9999999999
    output_image_y_max = 0
    #To find these bounds, this for loop iterates over the bounding boxes of all the treatment areas
    for treatment_area in treatment_areas.getFeatures():
        treatment_area_geometry = treatment_area.geometry()
        bbox = treatment_area_geometry.boundingBox()
        x_min = bbox.xMinimum()
        x_max = bbox.xMaximum()
        y_min = bbox.yMinimum()
        y_max = bbox.yMaximum()
        if x_min < output_image_x_min:
            output_image_x_min = x_min
        if x_max > output_image_x_max:
            output_image_x_max = x_max
        if y_min < output_image_y_min:
            output_image_y_min = y_min
        if y_max > output_image_y_max:
            output_image_y_max = y_max
    print("mins: "+str(output_image_x_min)+","+str(output_image_y_min))
    print("maxs: "+str(output_image_x_max)+","+str(output_image_y_max))
    
    #For the image, we will also store the x and y offsets of each tretment area's bonding box from the minimum corner of the entire image
    treatment_area_offsets = {}
    for treatment_area in treatment_areas.getFeatures():
        treatment_area_geometry = treatment_area.geometry()
        bbox = treatment_area_geometry.boundingBox()
        x_min = bbox.xMinimum()
        x_max = bbox.xMaximum()
        y_min = bbox.yMinimum()
        y_max = bbox.yMaximum()
        
        #The locations need to be rounded because pixels values are placed into an array of integers
        treatment_area_x_offset = math.ceil((x_min-output_image_x_min)/raster_pixel_scale_x)
        treatment_area_y_offset = math.ceil((y_min-output_image_y_min)/raster_pixel_scale_y)
        treatment_area_offsets[treatment_area.attribute(treatment_area_identifier)] = [treatment_area_x_offset,treatment_area_y_offset]
    
    #more simple calculations to find the x and y bounds of the image
    output_image_x_range = output_image_x_max - output_image_x_min
    output_image_y_range = output_image_y_max - output_image_y_min
    
    output_image_x_pixels = math.ceil(output_image_x_range / raster_pixel_scale_x)
    output_image_y_pixels = math.ceil(output_image_y_range / raster_pixel_scale_y)
    
    #For some reason, the array swaps the x and y axis and also inverts the x axis.
    #This is why output_image_y_pixels is the first asrgument and ...image_x_pix... is the second
    output_image_array = np.zeros((output_image_y_pixels,output_image_x_pixels,3),dtype=np.uint8)
    
    print("Empty Output Image Array created with bounds: x = "+str(output_image_x_pixels)+", y = "+str(output_image_y_pixels))


    #Now we actually iterate over the pixels to classify them
    print("Reading pixels in treatment areas...")
    #pixel_read_loop_break is used as debug option to compare to pixel_read_loop_max to stop early if needed
    pixel_read_loop_break = 0
    #Loop over every treatment area
    for treatment_area in treatment_areas.getFeatures():
        #compare for the early exit debug setting
        if pixel_read_loop_break < pixel_read_loop_max or pixel_read_loop_max < 1:
            #treatment_group is the treatment group identifier
            treatment_group = str(treatment_area.attribute(treatment_area_identifier))
            print("Plot Name: "+treatment_group)
            #Prepare a dictionary to add up the classified pixel counts
            plot_counts = classified_pixel_dictionary[treatment_group]
            #get the geometry of the treatment area
            treatment_area_geometry = treatment_area.geometry()
            #Find the bounding box of the geometry and maxs/mins of the bounding box
            bbox = treatment_area_geometry.boundingBox()
            x_min = bbox.xMinimum()
            x_max = bbox.xMaximum()
            y_min = bbox.yMinimum()
            y_max = bbox.yMaximum()
            #calculate the number of pixels in the x and y dimension
            x_range = math.ceil((x_max-x_min)/raster_pixel_scale_x)
            y_range = math.ceil((y_max-y_min)/raster_pixel_scale_y)
            #find the offset of the treatment area, so we can write the pixels to the output image in the right spot
            treatment_area_x_offset = treatment_area_offsets[treatment_area.attribute(treatment_area_identifier)][0]
            treatment_area_y_offset = treatment_area_offsets[treatment_area.attribute(treatment_area_identifier)][1]
            #loop over all the x values in the bounding box
            for x in range(0,x_range):
                #x_scaled is used for absolute location of the read pixel,
                #while x is used to find where to place the pixel in the output image
                x_scaled = x * raster_pixel_scale_x
                for y in range(0,y_range):
                    #another check to exit if we have exceeded the debug limit for max pixels read
                    if pixel_read_loop_break < pixel_read_loop_max or pixel_read_loop_max < 1:
                        y_scaled = y * raster_pixel_scale_y
                        #Find the absolute position of the pixel to be read
                        sample_point = QgsPointXY(x_min+x_scaled,y_min+y_scaled)
                        #create a geometry at this pixels location
                        sample_point_geom = QgsGeometry.fromPointXY(sample_point)
                        #skip pixel will remain false if the pixel is in the treatment area and not in a training ROI
                        skip_pixel = False
                        #use this new geometry to check if the pixel is within the treatment group
                        #(all pixels read will be in the bounding box, but not all will be in the treatment group)
                        if sample_point_geom.within(treatment_area_geometry):
                            #ensure the read pixel is not an any training rois
                            for merged_feat in merged_roi_shapefile_classification.getFeatures():
                                if sample_point_geom.within(merged_feat.geometry()):
                                    skip_pixel = True
                                    break
                        else:
                            skip_pixel = True
                        #skip pixel will remain false if the pixel is in the treatment area and not in a training ROI
                        if not skip_pixel:
                            #create an empty liast that will store the pixel's value in all 4 rasters
                            pixel_value_table = []
                            #now fill the list with the appropriate values
                            for b in band_info:
                                val,res = band_info[b][2].dataProvider().sample(sample_point,1)
                                pixel_value_table.append(val)
                            #use the MLE function to find the ID of the pixel
                            classified_id = MLE(pixel_value_table)
                            #increment the count at the current class
                            plot_counts[classified_id] += 1
                            #Fill the array at this location with the correct pixels
                            output_image_array[output_image_y_pixels-(treatment_area_y_offset+y),treatment_area_x_offset+x] = class_colors[classified_id]
                            #now check if the pixel that was just classified is within a validation ROI
                            for merged_feat in merged_roi_shapefile_validation.getFeatures():
                                if sample_point_geom.within(merged_feat.geometry()):
                                    #if the pixel was in a validation ROI, then increment the confusion matrix
                                    #at the row of the ROi and the column of the identified class
                                    row = merged_feat.attribute(roi_class_identifier)
                                    column = classified_id
                                    confusion_matrix[row][column] += 1
                                    break
                            
                            pixel_read_loop_break += 1
            #Now print the counts of each class in this treatment area
            for class_id in plot_counts:
                class_name = "Unclassified"
                if class_id > 0:
                    class_name = "Class "+str(class_id)
                print("\t"+class_name+": "+str(plot_counts[class_id]))
        else:
            print("Stopping after "+str(pixel_read_loop_max)+" pixels")
            break
    print("Treatment area pixels read.")


    #Print the matrix
    cm_column_labels = " Pred. unclas."
    for class_id in unique_roi_ids:
        cm_column_labels = cm_column_labels+SpaceText(class_id,cm_characters_per_entry," "," ")
    print(cm_column_labels)
    for row in confusion_matrix:
        row_string = SpaceText(row,cm_characters_per_entry," ",":")
        column_pos = 1
        for column in confusion_matrix[row]:
            row_string = row_string+SpaceText(confusion_matrix[row][column],cm_characters_per_entry,"[","]")
        print(row_string)
    
    #n = the total number of values in the confusion matrix (true positive + false positive + true negative + false negative)
    n = 0
    
    #p0 = the toal number of values in the diagonal of the matrix (true positive)
    p0 = 0
    
    #pe = 
    pe = 0
    #To calculate pe, we need to store the totals for every row and every column, this will be done with two dictionaries
    cm_row_total_dict = {}
    cm_column_total_dict = {}
    for class_id in unique_roi_ids:
        cm_row_total_dict[class_id] = 0
        cm_column_total_dict[class_id] = 0
    
    #k = 
    k = 0
    #Loop over the matrix again, this time to calculate K
    for row in confusion_matrix:
        for column in confusion_matrix[row]:
            #Skip unclassified pixels (stores at column -1)
            if column != -1:
                value = confusion_matrix[row][column]
                n += value
                #This conditional tests if we are currently in a diagonal
                # print(row,column,value)
                if row == column:
                    p0 += value
                #Now we update the totals for the current row and column
                cm_row_total_dict[row] += value
                cm_column_total_dict[column] += value
    if n > 0:
        p0 /= n
    
        #pe equals (the sum of all classes' row totals time column totals) divided by n^2
        for class_id in unique_roi_ids:
            pe += (cm_row_total_dict[class_id] * cm_column_total_dict[class_id])
        
        pe /= (n*n)
        
        k = (p0-pe)/(1-pe)
    
    
    print("p0: "+str(p0))
    print("pe: "+str(pe))
    print("k: "+str(k))

    end_time = time.time()
    
    time_elapsed = end_time - start_time
    time_elapsed_adjusted = time_elapsed / 60
    
    if time_elapsed_adjusted < 1:
        print("Done. Took "+str(time_elapsed)+" seconds.")        
    else:
        print("Done. Took "+str(time_elapsed_adjusted)+" minutes.") 
    
    
    #Precision and recall
    #Precision: Positive predicted values (tp)/(tp+fp)
    #Recall: tp/(tp+fn)
    print("Calculating Precision and Recall...")
    for class_id in unique_roi_ids:
        print("Class "+str(class_id)+":")
        tp = confusion_matrix[class_id][class_id]
        fp = 0 #All in the column (except the diagonal)
        fp += confusion_matrix[class_id][-1]
        for class_id_2 in unique_roi_ids:
            if class_id_2 != class_id:
                fp += confusion_matrix[class_id][class_id_2]
        fn = 0 #All in the row (except the diagonal)
        for class_id_2 in unique_roi_ids:
            if class_id_2 != class_id:
                fn += confusion_matrix[class_id_2][class_id]
        if tp+fp > 0:
            precision = tp/(tp+fp)
            print("\tPrecision: "+str(precision))
        else:
            print("\tPrecision: divide by 0 error")
        if tp+fn > 0:
            recall = tp/(tp+fn)
            print("\tRecall: "+str(recall))
        else:
            print("\tRecall: divide by 0 error")
        
    print("Precision and Recall Done.")
    
    print("Saving output Image...")  
    #Make an image from the array that stored the location and class of each pixel
    output_image = im.fromarray(output_image_array,'RGB')
    output_image_filename = "classified_output.png"
    output_image_path = output_image_dir+"/"+output_image_filename
    output_image.save(output_image_path,'PNG',quality=100)
    print("Output saved as "+output_image_path)
