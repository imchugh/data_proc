# -*- coding: utf-8 -*-
"""
Created on Mon Aug 24 12:13:41 2015

@author: imchugh
"""

import numpy as np
import operator
import copy as cp
import pdb

#------------------------------------------------------------------------------
# Numpy functions

def count_nans_in_array(arr):
    
    index = ~np.isnan(arr)
    start_len = len(arr)
    end_len = len(arr[index])
    
    return {'Total_obs': start_len,
            'Avail_obs': end_len,
            'Pct_avail_obs': round(end_len / float(start_len) * 100, 1)}

def set_numpy_array_to_nan(data_array, boolean_index):
    
    data_array[~boolean_index] = np.nan
    return data_array

def subset_numpy_array(data_array, boolean_index):
    
    return data_array[boolean_index]
    
def threshold_numpy_array(data_array, threshold, operation):
    """
    Creates a boolean index indicating whether values of numpy array are 
    greater than, less than, equal to or not equal to a given threshold
    Pass: 1) data_array - a numpy arrays of data
          2) threshold - numerical value of desired threshold
          3) operator - which data to keep (choices are <, >, ==, !=)
    Returns: numpy boolean array
    """
    ops = {">": operator.gt, "<": operator.lt, "==": operator.eq, 
           "!=": operator.ne}
    return ops[operation](data_array, threshold)

#------------------------------------------------------------------------------
# Basic Numpy array dictionary filtering functions 
#   Note that it is assumed that all dictionary
#   keys contain numpy arrays of equal length - indexing will most likely fail 
#   out of range if non-equal length arrays are contained in dict)

def set_numpy_dict_to_nan(data_dict, boolean_index):
    
    for var in data_dict.keys():
        data_dict[var] = set_numpy_array_to_nan(data_dict[var], [boolean_index])
    return data_dict

def subset_numpy_dict(data_dict, boolean_index):
    
    return {var: subset_numpy_array(data_dict[var], boolean_index) 
            for var in data_dict.keys()}

#------------------------------------------------------------------------------
# Higher level Numpy array dictionary filtering functions
#   Note that it is assumed that all dictionary
#   keys contain numpy arrays of equal length - indexing will most likely fail 
#   out of range if non-equal length arrays are contained in dict)

def sort_dict_on_index_variable(data_dict, sort_var):
    """
    Sorts a dictionary of equal-length numpy arrays on the basis of a
    sorting variable
    Pass: 1) data_dict - a dictionary containing arrays
          2) sort_var - the variable whose sorted order will dictate the 
                        ordering of all others (str)
    Returns: sorted dictionary
    """
    index = data_dict[sort_var].argsort()
    for key in data_dict.keys():
        data_dict[key] = data_dict[key][index]
    return data_dict

def subset_arraydict_on_nan(data_dict, var_list = False, condition = 'any', 
                            subset = True):
    """
    Removes all cases where either any or all variables (casewise) in array 
    are nan and return remaining data (ignores non-numeric dtypes)
    """    
    boolean_list = []
    these_vars = var_list if var_list else data_dict.keys()
    for var in these_vars:
        try:
            boolean_list.append(~np.isnan(data_dict[var]))
        except:
            continue
    if condition == 'any':
        all_boolean_index = [all(rec) for rec in zip(*boolean_list)]
    elif condition == 'all':
        all_boolean_index = [any(rec) for rec in zip(*boolean_list)]
    else:
        raise Exception('Valid keywords are "any" or "all"')    
    
    boolean_index = np.array(all_boolean_index)
    if subset:
        return subset_numpy_dict(data_dict, boolean_index)
    else:
        return boolean_index
    
def subset_arraydict_on_threshold(data_dict, threshold_var, threshold, 
                                  keep_cond, drop = False):
    """
    Pass: 1) data_dict - a dictionary containing numpy data arrays
          2) threshold_var - namestring of variable that is used for thresholding
          3) threshold - numerical value of desired threshold
          4) keep_cond - which data to keep (choices are <, >, ==, !=)
          5) drop - optional kwarg (default = False) specifying whether to drop
                    filtered data or set to nan
    Returns: filtered data dictionary
    """
    boolean_index = threshold_numpy_array(data_dict[threshold_var], threshold,
                                          keep_cond)
    if drop:
        return subset_numpy_dict(data_dict, boolean_index)
    else:
        return set_numpy_dict_to_nan(data_dict, boolean_index)

def subset_datayear_from_arraydict(data_dict, date_time_var, year = None):
    """
    Pass: 1) data_dict - a dictionary containing arrays, one of which must be a 
             python datetime;
          2) date_time_var - namestring of datetime variable
          3) year to be returned as optional kwarg
    Returns: if year is specified, return the same dictionary structure with 
             only data for that year; if no year is specified, return a 
             dictionary with each data year contained as the value with the 
             year as the key
    """    
    years_array = np.array([date_.year for date_ in data_dict[date_time_var]])
    if not year:
        year_list = set(list(years_array))    
    else:
        if not isinstance(year, list): year = [year]
    
    new_dict = {}
    for yr in year_list:
        year_index = years_array == yr            
        new_dict[yr] = subset_numpy_dict(data_dict, year_index)

    return new_dict
    
#------------------------------------------------------------------------------
    
#------------------------------------------------------------------------------
    
def IQR_filter(data_array, outlier_value = 1.5, minimum_data_avail = 50,
               inplace = True):
    
    valid_data_array = data_array[~np.isnan(data_array)]
    
    if not len(valid_data_array) / float(len(data_array)) * 100 > minimum_data_avail:
        print 'Percentage of valid data below minimum threshold - returning...'
        return

    lo_qtl = np.percentile(valid_data_array, 25)
    hi_qtl = np.percentile(valid_data_array, 75)
    qtl_range = hi_qtl - lo_qtl
    lo_threshold = lo_qtl - outlier_value * qtl_range
    hi_threshold = hi_qtl + outlier_value * qtl_range
    print 'Lower threshold is ' + str(lo_threshold)
    print 'Upper threshold is ' + str(hi_threshold)
    lo_bool_array = data_array < lo_threshold
    hi_bool_array = data_array > hi_threshold
    all_bool_array = lo_bool_array | hi_bool_array
    if not inplace:
        new_array = cp.copy(data_array)
    else:
        new_array = data_array
    new_array[all_bool_array] = np.nan
    
    return new_array

def slide_IQR_filter(data_array, outlier_value = 2, window_size = 11,
                     inplace = True):

    if window_size > len(data_array):
        raise Exception('Window size cannot exceed array size! Quitting...')

    if window_size == len(data_array):
        iter_array = np.array([0])
    else:
        if window_size % 2 == 0:
            window_size = window_size + 1
            if window_size == len(data_array):
                iter_array = np.array([0])
        else:
            iter_array = np.arange(0, len(data_array) - window_size)

    # Create lower and upper threshold arrays
    lo_threshold_array = np.empty(len(data_array))
    lo_threshold_array[:] = np.nan
    hi_threshold_array = np.empty(len(data_array))
    hi_threshold_array[:] = np.nan

    # Calculate outliers for each window
    rslt_index_int = int(window_size / 2)
    for i in iter_array:
        this_array = data_array[i: i + window_size]
        lo_qtl = np.percentile(this_array, 25)
        hi_qtl = np.percentile(this_array, 75)
        qtl_range = hi_qtl - lo_qtl
        lo_threshold_array[i + rslt_index_int] = lo_qtl - outlier_value * qtl_range
        hi_threshold_array[i + rslt_index_int] = hi_qtl + outlier_value * qtl_range

    # Fill gaps using median of low and high thresholds over whole array
    lo_median = np.median(lo_threshold_array[~np.isnan(lo_threshold_array)])
    lo_threshold_array[np.isnan(lo_threshold_array)] = lo_median
    hi_median = np.median(hi_threshold_array[~np.isnan(hi_threshold_array)])
    hi_threshold_array[np.isnan(hi_threshold_array)] = hi_median    

    # Create boolean array (where values outside range will be True)
    bool_array = ((data_array < lo_threshold_array) |
                  (data_array > hi_threshold_array))
    
    
    # Filter original series (or copy if requested)
    if not inplace:
        new_array = cp.copy(data_array)
        new_array[bool_array] = np.nan
        return new_array
    else:
        data_array[bool_array] = np.nan
        return