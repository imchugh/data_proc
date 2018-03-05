#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 25 12:29:02 2018

@author: ian
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.formula.api import ols

import DataIO as io
reload(io)

#------------------------------------------------------------------------------
# Class init
#------------------------------------------------------------------------------
class random_error(object):
    
    def __init__(self, dataframe, configs_dict = False, num_bins = 50,
                 noct_threshold = 10,
                 t_threshold = 3, ws_threshold = 1, k_threshold = 35):
        
        if not configs_dict:
            configs_dict = {'flux_name': 'Fc',
                            'mean_flux_name': 'Fc_SOLO',
                            'windspeed_name': 'Ws',
                            'temperature_name': 'Ta',
                            'insolation_name': 'Fsd',
                            'QC_name': 'Fc_QCFlag',
                            'QC_code': 0}
        
        # Get and check the interval
        interval = int(filter(lambda x: x.isdigit(), 
                              pd.infer_freq(dataframe.index)))
        assert interval % 30 == 0
        recs_per_day = 1440 / interval
        self.recs_per_day = recs_per_day
        self.df = dataframe
        self.configs_dict = configs_dict
        self.num_bins = num_bins
        self.noct_threshold = noct_threshold
        self.t_threshold = t_threshold
        self.ws_threshold = ws_threshold
        self.k_threshold = k_threshold
        self.binned_error = self.get_flux_binned_sigma_delta()

#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Class methods
#------------------------------------------------------------------------------

    #--------------------------------------------------------------------------        
    def convert_names_and_QC(self):
        
        new_names_dict = {'flux_name': 'flux',
                          'mean_flux_name': 'flux_mean',
                          'QC_name': 'QC',
                          'windspeed_name': 'Ws',
                          'temperature_name': 'Ta',
                          'insolation_name': 'Fsd'}

        internal_dict = self.configs_dict.copy()
        try:
            QC_code = internal_dict.pop('QC_code')
            assert 'QC_name' in internal_dict.keys()
        except (KeyError, AssertionError):
            QC_code = None
            new_names_dict.pop('QC_name')
        old_names = [internal_dict[name] for name in 
                     sorted(internal_dict.keys())]
        new_names = [new_names_dict[name] for name in 
                     sorted(new_names_dict.keys())]
        sub_df = self.df[old_names].copy()
        sub_df.columns = new_names
        if not QC_code is None:
            sub_df.loc[sub_df.QC != QC_code, 'flux'] = np.nan
            sub_df.drop('QC', axis = 1, inplace = True)
        return sub_df
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    def get_flux_binned_sigma_delta(self):    

        #----------------------------------------------------------------------
        # Nested functions
        #----------------------------------------------------------------------
        
        #----------------------------------------------------------------------
        # Bin day and night data
        def bin_time_series():
            
            def get_sigmas(df):
                def calc(s):
                    return abs(s - s.mean()).mean() * np.sqrt(2)
                return pd.DataFrame({'sigma_delta': 
                                      map(lambda x: 
                                          calc(df.loc[df['quantile_label'] == x, 
                                                      'flux_diff']), 
                                          df['quantile_label'].unique()
                                          .categories),
                                     'mean': 
                                      map(lambda x: 
                                          df.loc[df['quantile_label'] == x,
                                                 'flux_mean'].mean(),
                                          df['quantile_label'].unique()
                                          .categories)})

            noct_df = filter_df.loc[filter_df.Fsd_mean < self.noct_threshold, 
                                    ['flux_mean', 'flux_diff']]
            day_df = filter_df.loc[filter_df.Fsd_mean > self.noct_threshold, 
                                   ['flux_mean', 'flux_diff']]
                    
            nocturnal_propn = float(len(noct_df)) / len(filter_df)
            num_cats_night = int(round(self.num_bins * nocturnal_propn))
            num_cats_day = self.num_bins - num_cats_night
            
            noct_df['quantile_label'] = pd.qcut(noct_df.flux_mean, num_cats_night, 
                                                labels = np.arange(num_cats_night))
            noct_group_df = get_sigmas(noct_df)
#            noct_group_df = noct_group_df.loc[noct_group_df['mean'] > 0]
    
            day_df['quantile_label'] = pd.qcut(day_df.flux_mean, num_cats_day, 
                                               labels = np.arange(num_cats_day))
            day_group_df = get_sigmas(day_df)
#            day_group_df = day_group_df.loc[day_group_df['mean'] < 0]

            return day_group_df, noct_group_df
        #----------------------------------------------------------------------

        #----------------------------------------------------------------------    
        def difference_time_series():
            diff_df = pd.DataFrame(index = work_df.index)
            for var in ['flux', 'Ta', 'Fsd', 'Ws']:
                var_name = var + '_diff'
                temp = work_df[var] - work_df[var].shift(self.recs_per_day) 
                diff_df[var_name] = temp if var == 'flux' else abs(temp)
            diff_df['flux_mean'] = (work_df['flux_mean'] + work_df['flux_mean']
                                    .shift(self.recs_per_day)) / 2
            diff_df['Fsd_mean'] = (work_df['Fsd'] + 
                                   work_df['Fsd'].shift(self.recs_per_day)) / 2
            return diff_df
        #----------------------------------------------------------------------
        
        #----------------------------------------------------------------------
        def filter_time_series():
            bool_s = ((diff_df['Ws_diff'] < self.ws_threshold) & 
                      (diff_df['Ta_diff'] < self.t_threshold) & 
                      (diff_df['Fsd_diff'] < self.k_threshold))
            return pd.DataFrame({var: diff_df[var][bool_s] for var in 
                                 ['flux_diff', 'flux_mean', 
                                  'Fsd_mean']}).dropna()
        #----------------------------------------------------------------------
        
        #----------------------------------------------------------------------
        # Main routine
        #----------------------------------------------------------------------

        work_df = self.convert_names_and_QC()
        diff_df = difference_time_series()
        filter_df = filter_time_series()
        day_df, noct_df = bin_time_series()
        return {'day': day_df, 'night': noct_df}
    
    #-------------------------------------------------------------------------- 

    #--------------------------------------------------------------------------
    # Do plotting
    #--------------------------------------------------------------------------
    def plot_data(self, flux_units = '\mu mol\/CO_2\/m^{-2}\/s^{-1}'):
        
        data_dict = self.binned_error
        stats_dict = self.get_regression_statistics()
        
        colour_dict = {'day': 'C1', 'night': 'C0'}
        
        x_min = min(map(lambda x: data_dict[x]['mean'].min(), 
                        data_dict.keys()))
        x_max = max(map(lambda x: data_dict[x]['mean'].max(), 
                        data_dict.keys()))
        y_max = max(map(lambda x: data_dict[x]['sigma_delta'].max(), 
                        data_dict.keys()))
        
        fig, ax1 = plt.subplots(1, 1, figsize = (14, 8))
        fig.patch.set_facecolor('white')
        ax1.xaxis.set_ticks_position('bottom')
        ax1.set_xlim([round(x_min * 1.05), round(x_max * 1.05)])
        ax1.set_ylim([0, round(y_max * 1.05)])
        ax1.yaxis.set_ticks_position('left')
        ax1.spines['right'].set_visible(False)
        ax1.spines['top'].set_visible(False)
        ax1.tick_params(axis = 'y', labelsize = 14)
        ax1.tick_params(axis = 'x', labelsize = 14)
        ax1.set_xlabel('$flux\/({})$'.format(flux_units), fontsize = 18)
        ax1.set_ylabel('$\sigma[\delta]\/({})$'.format(flux_units), 
                       fontsize = 18)
        ax2 = ax1.twinx()
        ax2.spines['right'].set_position('zero')
        ax2.spines['left'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        ax2.set_ylim(ax1.get_ylim())
        ax2.tick_params(axis = 'y', labelsize = 14)
        plt.setp(ax2.get_yticklabels()[0], visible = False)
        text_list = []
        for state in data_dict.keys():
            stats = stats_dict[state]
            df = data_dict[state]
            x = np.linspace(df['mean'].min(), df['mean'].max(), 2)
            y = x * stats.slope + stats.intercept
            ax1.plot(df['mean'], df['sigma_delta'], 'o', 
                     mfc = colour_dict[state], mec = 'black')
            ax1.plot(x, y, color = colour_dict[state])
            text_list.append('${0}: a = {1}, b = {2}, r^2 = {3}$'
                             .format(state[0].upper() + state[1:],
                                     str(round(stats.slope, 2)),
                                     str(round(stats.intercept, 2)),
                                     str(round(stats.rvalue ** 2, 2))))
        text_str = '\n'.join(text_list)
        props = dict(boxstyle = 'round', facecolor = 'None', alpha = 0.5)
        ax1.text(0.05, 0.175, text_str, transform=ax1.transAxes, fontsize=14,
                verticalalignment='top', bbox=props)
        return fig
    #--------------------------------------------------------------------------
    
    #--------------------------------------------------------------------------
    # Calculate basic regression statistics
    def get_regression_statistics(self):
        
        data_dict = self.binned_error
#        for state in data_dict.keys():
#            ols.
        return {state: stats.linregress(data_dict[state]['mean'],
                                        data_dict[state]['sigma_delta'])
                for state in data_dict.keys()}
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # Estimate sigma_delta for a time series using regression coefficients
    #--------------------------------------------------------------------------
    def estimate_sigma_delta(self):
        
        """Calculates sigma_delta value for each member of a time series"""
        
        work_df = self.convert_names_and_QC()
        stats_dict = self.get_regression_statistics()
        work_df.loc[np.isnan(work_df.flux), 'flux_mean'] = np.nan
        work_df['sigma_delta'] = np.nan
        work_df.loc[work_df.Fsd < self.noct_threshold, 'sigma_delta'] = (
            work_df.flux_mean * stats_dict['night'].slope +
            stats_dict['night'].intercept)
        work_df.loc[work_df.Fsd > self.noct_threshold, 'sigma_delta'] = (
            work_df.flux_mean * stats_dict['day'].slope +
            stats_dict['day'].intercept)
        if any(work_df['sigma_delta'] < 0):
            n_below = len(work_df['sigma_delta'][work_df['sigma_delta'] < 0])
            print ('Warning: approximately {0} estimates of sigma_delta have value ' 
                   'less than 0 - setting to mean of all other values'
                   .format(str(n_below)))
            work_df.loc[work_df['sigma_delta'] < 0, 'sigma_delta'] = (
                work_df['sigma_delta']).mean()
        return work_df['sigma_delta']
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # Generate scaled noise realisation for time series
    #--------------------------------------------------------------------------
    def estimate_random_error(self):
        
        """ Generate single realisation of random error for time series """
        sigma_delta_series = self.estimate_sigma_delta()
        return pd.Series(np.random.laplace(0, sigma_delta_series / np.sqrt(2)),
                         index = sigma_delta_series.index)
    #--------------------------------------------------------------------------

    #------------------------------------------------------------------------------
    # Propagate random error
    #--------------------------------------------------------------------------
    def propagate_random_error(self, n_trials, scaling_coefficient = 1):
        """ Run Monte Carlo-style trials to assess uncertainty due to 
        random error over entire dataset
        
        Args:
            * n_trials (int):  number of trials over which to compound the sum.
            * scaling_coefficient (int or float): scales summed value to required \
            units.
        
        Returns:
            * float: scaled estimate of 2-sigma bounds of all random error\
            trial sums.
        """
        
        sigma_delta_series = self.estimate_sigma_delta()
        crit_t = stats.t.isf(0.025, n_trials)  
        results_list = []
        for this_trial in xrange(n_trials):
            results_list.append(pd.Series(np.random.laplace(0, 
                                                            sigma_delta_series / 
                                                            np.sqrt(2))).sum() *
                                scaling_coefficient)
        return round(float(pd.DataFrame(results_list).std() * crit_t), 2)
    #--------------------------------------------------------------------------


    '''
    Calculates regression for sigma_delta on flux magnitude 
    
    Args:
        * df (pandas dataframe): dataframe containing the required data, with \
        names defined in the configuration dictionary (see below).
        * config_dict (dictionary): dictionary for specifying naming convention \
        for dataset passed to the function; keys must use the default names \
        (specified below) expected by the script, and the values specify the \
        name the relevant variable takes in the dataset; default names are as \
        follows:\n
            - flux_name: the turbulent flux for which to calculate random \
            error 
            - mean_flux_name: the flux series to use for calculating the \
            bin average for the flux when estimating sigma_delta \
            (since the turbulent flux already contains random error, a \
            model series is generally recommended for this purpose)
            - windspeed_name
            - temperature_name
            - insolation_name
            - QC_name: (optional) if passed, used as a filter variable \
            for the flux variable (if QC_code is not present, this is \
            ignored, and no warning or error is raised)
            - QC_code: (optional, int) if passed, all flux records that \
            coincide with the occurrence of this code in the QC variable \
            are retained, and all others set to NaN
    Kwargs:
        * return_data (bool): if True attaches bin averaged flux and \
        sigma_delta estimates to the returned results dictionary
        * return_plot (bool): if True attaches plot of sigma_delta as a \
        function of flux magnitude to the returned results dictionary
        * t_threshold (int): user-set temperature difference threshold \
        default = 3superscriptoC)
        * ws_threshold (int): user-set wind speed difference threshold \
        (default = 1m s\^{-1})
        * k_threshold (int): user set insolation difference threshold \
        (default = 35Wm-2)
    '''