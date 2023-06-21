Instructions on use: https://docs.google.com/document/d/1k4T7pBsiyCaiF9smgR2OKtg_lHBtuwnwEB0EHXQpxI8/edit?usp=sharing
# Using Machine Imaging to Assess the Effectiveness of Herbicides on the Invasive Reed Canary Grass

## After a 9 month period for the capstone course, I was far from satisfied with the work that my group had completed. I got into contact with the project partner, Associate Professor Bogdan Strimbu, and we worked out a plan for me to finish the project over the 9 week summer term.
## In this time, essentially restarting from scratch, I was able to create a functioning and mostly automated method that could be entirely run from a single python script. Although this did require the user to do a few tasks within QGIS to get the script to function, these tasks required no knowledge of programming. 




An excerpt from my final instructions document:
`Explanation of Methods`
`This python script analyzes pixels in treatment areas by using a maximum likelihood estimation (MLE) via a normal distribution probability density function (NPDF).`


`Treatment Areas are the marked locations within the project that will actually be analyzed.`
`The script should run just as well with just 1 or a large number of treatment areas.`

`Regions of interest (ROIs) will be placed within the treatment area(s). These ROIs are the most essential part of the classification process, but some of the ROIs will be automatically selected for validation.`


`Classification ROIs are the ROIs that will be used to collect mean and standard deviation values. The statistics will then be used to classify all the remaining pixels within the treatment area(s).`


`Validation ROIs are the remaining ROIs. Each validation ROI will be used to compare the user’s identified class of that ROI to the class that the script assigned to each pixel in that validation ROI; this will provide an estimation on accuracy of the classification process.`

`A Confusion Matrix will be generated to store the results of the validation process.`
