"""
by: Aaron Finocchiaro
APCV 498 - Senior Capstone

A class designed to interact with the bls.gov API.
"""
import calendar
import json
import os
import pandas as pd
import pkg_resources
import re
import requests
from pyBLS import qcew_area_codes_df, oes_area_codes_df

BLS_URL = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'

#set plotting backend to plotly
pd.options.plotting.backend = "plotly"

class BlsData():
    """
    A class designed to interact with the Bureau of Labor Statistics public API and translate the data
    into a Pandas Dataframe.
    """
    def __init__(self, series_id_list=None, start_year=None, end_year=None, json_file=None,
            raw_data=None):
        
        self.series_id_list = series_id_list
        self.start_year = start_year
        self.end_year = end_year

        if not raw_data and series_id_list:
            self.raw_data = self._request_bls_data()
        else:
            self.raw_data = self._read_bls_file(raw_data)

        self.df = self._construct_df()
        self.locations = self.get_location()

    def _request_bls_data(self):
        headers = {
            'content-type' : 'application/json',
        }
        data = json.dumps({
            "seriesid" : self.series_id_list,
            "startyear" : self.start_year,
            "endyear" : self.end_year,
            "catalog" : False,
            "annualaverage" : False,
            "aspects" : False,
            "registrationKey" : os.environ.get('BLS_API_KEY'),
        })
        
        #make post request
        r = requests.post(BLS_URL, data=data, headers=headers)

        return r.json()['Results']['series']

    def _read_bls_file(self):
        """
        Reads from a previously constructed json file of BLS data and returns
        the json data in a list of dictionaries.
        """
        with open('raw_data3_3.json') as json_file:
            data = json.load(json_file)
        return data

    def write_to_bls_file(self, raw_data, file_name):
        """
        Writes raw data from BLS API out to a json file.
        """
        with open("file_name", 'w') as json_out:
            json.dump(self.raw_data, json_out, indent=4)

    def _construct_df(self):
        """
        Constructs a pandas dataframe from the raw data returned from the BLS
        API. 
        Returns a dataframe organized by the data frequency in organize_df()
        """
        #make an empty dataframe with desired cols
        cols = ['year', 'period']
        df = pd.DataFrame(columns=cols)

        #use for loop to create df
        for bls_series in self.raw_data:
            series_df = pd.DataFrame(bls_series['data'])
            series_df = series_df[cols + ['value']]
            series_df['value'] = pd.to_numeric(series_df['value'])
            series_df = series_df.rename(columns={'value' : bls_series['seriesID']})
            df = df.merge(right=series_df, on=['year', 'period'], how='outer')

        return self.organize_df(df)
    
    def organize_df(self, df):
        """
        Organizes pandas dataframe depending on the term of the data.
        Currently works for monthly and quarterly data.
        Returns a pandas dataframe.
        """
        #quarterly data
        if df.loc[0]['period'][0] == 'Q':
            df['period'] = df['period'].str.replace('0', '')
            df['date'] = df['year'].map(str)+ '-' +df['period'].map(str)
            df['date'] = pd.to_datetime(df['date'])

        #monthly data
        if df.loc[0]['period'][0] == 'M':
            df['period'] = df['period'].str.replace('M', '')
            df['date'] = df['period'].map(str)+ '-' +df['year'].map(str)
            df['date'] = pd.to_datetime(df['date'], format='%m-%Y')
        
        #annual data
        if df.loc[0]['period'][0] == 'A':
            df = df.rename(columns={'year':'date'}, errors='raise')

        #change index and sort
        df = df.set_index('date')
        df = df.sort_index()

        #drop extra cols
        df = df.drop(columns=['period', 'year'], errors='ignore')

        return df

    def create_graph(self, title, graph_type, clean_names=True, custom_column_names=None,
            transpose=False,):
        """
        Returns a graph-able plotly object from the given data and constructed
        dataframe. Renames columns based on the mapping of seriesIDs to locations
        from the BLS area codes.
        Arguments:
            - title = str; graph title
            - clean_names = bool; replace seriesIDs in df columns with location name
            - custom_column_names = dict; mapping of seriesID to custom defined column names
            - transpose = bool; transpose df to graph correctly
        Returns a plotly object.
        """
        plotting_df = self.df
        
        #replace column names with location names
        if clean_names and not custom_column_names:
            plotting_df = plotting_df.rename(columns=self.locations, errors="raise")
        
        #replace column names with a custom name
        if clean_names and custom_column_names:
            if type(custom_column_names) is not dict:
                raise TypeError("Custom column names must be of type dict.")
            plotting_df = plotting_df.rename(columns=custom_column_names, errors="raise")
        
        #transpose df, typically if length is 1
        if transpose:
            plotting_df = plotting_df.transpose()

        #return graph type
        if graph_type == 'line':
            return plotting_df.plot(title = title, template="simple_white")
        if graph_type == 'bar':
            return plotting_df.plot.bar(title = title, template="simple_white")
    
    def get_location(self):
        """
        Uses the area_titles.csv file from https://data.bls.gov/cew/doc/titles/area/area_titles.htm
        to create a dataframe of all area_codes that BLS uses. This returns a dict with the series
        IDs as keys and the location name as values.
        """
        series_id_locations = {}
        for series in self.series_id_list:
            if re.match('[EN|LA]', series[0:2]):
                if series[0:2] == 'EN':
                    area_code = re.search('^[A-Z]{3}([\d|U][\d|S]\d\d\d)', series).group(1)
                if series[0:2] == 'LA':
                    area_code = re.search('^[A-Z]{5}(\d\d\d\d\d)', series).group(1)
                series_id_locations[series] = qcew_area_codes_df.loc[area_code]['area_title']
            if re.match('OE', series[0:2]):
                area_code = re.search('^[A-Z]*(\d\d\d\d\d\d\d)', series).group(1)
                series_id_locations[series] = oes_area_codes_df.loc[area_code]['area_name']

        return series_id_locations


    
