#!/usr/bin/python -O

# Version of algoRun to analize CSV data
# Filename:     algoRunCSV.py
# Author(s):    apadin
# Start Date:   6/8/2016


##############################  LIBRARIES  ##############################
import datetime as dt
import time
import sys
import json
import numpy as np
import grapher

from algoRunFunctions import train, severityMetric, runnable
from grapher import Grapher, CSV, DATE_FORMAT
import pickle

##############################  PARAMETERS  ##############################
THRESHOLD = 10000


##############################  INITIALIZE  ##############################

# Get commandline arguments
try:
    infile = sys.argv[1]
    outfile = sys.argv[2]
    granularity = int(sys.argv[3])
    training_window = int(sys.argv[4])
    forecasting_interval = int(sys.argv[5])
except:
    raise RuntimeError(
        "usage: %s <infile> <outfile> <granularity> <training_window> <forecasting_interval>"
        % sys.argv[0])

print ("Starting analysis on %s with settings %d %d %d..." 
       % (infile, granularity, training_window, forecasting_interval))


# Algorithm settings
forecasting_interval = forecasting_interval * 60 # forecasting interval in hours
matrix_length = forecasting_interval * training_window

# Get list of features (first columns is time)
infile = open(infile, 'r')
columns = infile.next().split(',')[1:]

print "The following features were found:", columns

granularity_in_seconds = granularity * 60

# Variables
X =  np.zeros([matrix_length, len(columns)], np.float32)
y_predictions = []
y_target = []
y_time = []
w_opt = []
a_opt = 0
b_opt = 0
mu = 0; sigma = 1000
w, L = (.84, 3.719) # EWMA parameters. Other pairs can also be used, see paper
Sn_1 = 0

row_count = 0
init_training = False


##############################  ANALYZE  ##############################
print "Beginning analysis..."
for line in infile:

    line = [float(i) for i in line.split(',')]
    cur_time = line[0]
    cur_row = row_count % matrix_length
    X_data = line[1:]

    if(row_count % 240 == 0):
        print "Trying time: %s " % dt.datetime.fromtimestamp(cur_time).strftime(DATE_FORMAT)

    # Update X
    X[cur_row] = X_data

    # Time to train:
    if(row_count % forecasting_interval == 0 and row_count >= matrix_length):
        data = X[cur_row:, :-1]
        data = np.concatenate((data, X[:cur_row, :-1]), axis=0)
        y = X[cur_row:, -1]
        y = np.concatenate((y, X[:cur_row, -1]), axis=0)

        if (init_training or runnable(data) > 0.5):

            # For BLR train
            w_opt, a_opt, b_opt, S_N = train(data, y)
            
            # For TF train            
            #w_opt, a_opt, b_opt, S_N = tf_train(data, y)
            init_training = 1
        
        '''
        else:
            notRunnableCount += 1
            if(notRunnableCount > 5):
                print "Data not runnable too many times! Exiting..."
        '''

    # Make a prediction
    if init_training:

        x_test = X[cur_row, :-1]
        prediction = max(0, np.inner(w_opt, x_test))
        target = X[cur_row, -1]

        y_time.append(cur_time)
        y_target.append(target)
        y_predictions.append(prediction)
        
        error = (prediction - target)
        sigma = np.sqrt(1/b_opt + np.dot(np.transpose(x_test),np.dot(S_N, x_test)))
        
        # Catching pathogenic cases where variance (ie, sigma) gets too small
        if sigma < 1:
            sigma = 1

        # Update severity metric
        mu = mu; sigma = sigma
        Sn, Zn = severityMetric(error, mu, sigma, w, Sn_1)
        Sn_1 = Sn

    #Increment and loop
    row_count += 1

# Close the input file
infile.close()
    
# Save data for later graphing
results = CSV(outfile)
results.clear()
results.append(y_time, y_target, y_predictions)