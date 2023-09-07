# general
import numpy as np 
import pandas as pd 
import json


import warnings
warnings.filterwarnings(action='ignore',category=FutureWarning)

def process_last_point(ts,ts_dates):
    ts_dates = pd.to_datetime(ts_dates)
    ts_panda = pd.Series(index = ts_dates, data = ts)
    OD = UnivariateOutlierDetection(ts_panda)
    OD.AutomaticallySelectDetectors()
    last_point_scores = OD.LastOutlierScore().iloc[0,:]
    result = OD.InterpretPointScore(last_point_scores)
    return result



class UnivariateOutlierDetection:

    # imported outlier detection methods
    from .univariate_STD import STD
    from .univariate_IF import IF
    from .univariate_PRO import PRO
    from .univariate_PRE import PRE
    from .univariate_preprocessors import pp_average, pp_power, pp_median, pp_volatility, pp_difference, pp_season_subtract
    

    # series has to have an index in pandas datetime format
    def __init__(self, series):
        if not isinstance(series, pd.Series):
            raise TypeError("Passed series is not a pd.Series.")
        if not isinstance(series.index, pd.DatetimeIndex):
            raise TypeError("Index of passed series is not a pd.DatetimeIndex.")
        if not pd.api.types.is_numeric_dtype(series):
            raise TypeError("Passed series is not numeric.")
        
        # Check for duplicate indices:
        duplicated_indices = series.index.duplicated()
        if duplicated_indices.sum() > 0:
            warnings.warn(f"Warning: passed series contains duplicated indices. Removing duplicates, keeping firsts only.\n")
            series = series[~duplicated_indices]
            
        self.series = series  

        self.min_training_data = 5

        nans = series.isna() 
        nan_times = nans[nans==True].index.to_list()

        if len(nan_times) > 0:
            warnings.warn(f"Warning: passed series contains {len(nan_times)} nans:\n{nan_times}\n")

        self.SetStandardDetectors()



    def GetSeries(self):
        return self.series
    
    def AddDetector(self, new_detector):
        self.num_detectors += 1
        new_detector.append(new_detector[0]) # store the name before turning into a function
        new_detector.append(self.num_detectors) # 1, 2, 3 ... detector ID
        new_detector[0] = getattr(self, new_detector[0])
        self.detectors.append(new_detector)
        

    def ClearDetectors(self):
        self.detectors = []
        self.num_detectors = 0


    def SetStandardDetectors(self):
        self.ClearDetectors()
        self.AddDetector(['STD', [1], [], 5])
        self.AddDetector(['PRE', [10], [], 0.05])
        self.AddDetector(['IF', [0.05], [], None])

    
    
    def LastOutlierScore(self, window = None):
        if window == None:
            window = self.series.index.to_list()
        #print(window)
        training = window[:-1]
        #print(training[-1])
        test = window[-1:]
        #print(test)
        return self.WindowOutlierScore(training, test)
    

    def InterpretPointScore(self, scores):
        message_detail = []

        isOutlier = False

        type_seasonal = False
        type_density = False

        detector_responses = []



        high_level_description = ""

        max_level_STD = 0.0
        max_level_PRE = 0.0

        for detector in self.detectors:

            # response structure for each detector: [value, algorithm_name, algorithm_parameters, isOutlier]

 


            current_response = []

            isOutlierCurrent = False

            type = detector[4]
            ID = detector[5]
            threshold = detector[3]
            preprocessor = detector[2]
            args = detector[1]

            column = "D_" + str(ID)

            
            val = scores[column]

            if type == "STD":
                max_level_STD = max(max_level_STD, np.abs(val))
            if type == "PRE":
                max_level_PRE = max(max_level_PRE, np.abs(val))

            full_name = type + "_" + "".join(str(e) for e in args) + "_" + "".join(str(e) for e in preprocessor) + "_" + str(threshold)

            #print(f"Checking detector {full_name}")


            if type == 'PRE':
                val = np.abs(val)
                if val >= 1.0 + threshold:
                    message_detail.append(f"A value this extreme was never seen before. It deviates by at least {((val-1.0)*100):.0f}% from the previously seen value range. " + full_name)
                    isOutlier = True
                    isOutlierCurrent = True
                if val == 1:
                    message_detail.append(f"A similar value has never been observed before, but it is within the previously observed data range. " + full_name)
                    isOutlier = True
                    isOutlierCurrent = True

            if type == 'STD':
                #print(val)
                val = np.abs(val)
                if val >= threshold:
                    isOutlier = True
                    isOutlierCurrent = True
                    m = []
                    m.append(f"Density outlier detected of {val:.1f} sigma. " + full_name)
                    #val2 = np.abs(scores['PRE[10][A10]'])
                    #if val2 < 1:
                    #    m.append(f'But a similar contextual outlier has been seen before in {((1.0 - val2)*100):.0f}% of measurements.')
                    message_detail.append(' '.join(m))
        
            if type == 'PRO':
                val = np.abs(val)
                if val >= threshold:
                    message_detail.append(f"Contextual outlier (via Prophet) detected with strength {val:.1f}. " + full_name)
                    isOutlier = True
                    isOutlierCurrent = True

            if isOutlierCurrent:
                for p in preprocessor:
                    if p[0] == 'season_subtract':
                        type_seasonal = True
                    if p[0] == 'average':
                        type_density = True


            current_response.append(val)
            current_response.append(type)
            current_response.append([args, preprocessor, threshold])
            current_response.append(isOutlierCurrent)
# The structure of result.responses should be as follows:
# [
#   {
#     "Value": 0.1, # numeric score from the 
#     "Algorithm": "Prophet",
#     "Detail": {
#       "type": "15"
#     },
#     "Anomaly": true
#   },   

            detail_dic = {"Arguments": args, "Preprocesor": preprocessor, "Threshold": threshold}

            current_response_dic ={ 
                "Value": val, 
                "Algorithm": type, 
                "Detail": detail_dic, 
                "Anomaly": isOutlierCurrent
            } 

            detector_responses.append(current_response_dic)

        if type_seasonal and type_density:
            high_level_description = "Seasonal / density outlier"
        elif type_seasonal:
            high_level_description = "Seasonal outlier"
        elif type_density:
            high_level_description = "Density outlier"
        elif isOutlier:
            high_level_description = "Range outlier"

        # preliminary anomaly strength counter. 
        max_level = max((max_level_PRE - 1.0) * 5.0, max_level_STD)

        return isOutlier, max_level, message_detail, json.dumps(detector_responses, indent = 4) 

#        val = np.abs(scores['STD[1][V20M20]'])
#        if val >= thresh_STD_1_V20M20:
#            isOutlier=True
#            m = []
#            m.append(f"Median volatility outlier of strength {val:.1f} detected.")
#            val2 = np.abs(scores['PRE[10][V20M20]'])
#            if val2 < 1:
#                m.append(f'But a similar average volatility outlier has been seen before in {((1.0 - val2)*100):.0f}% of measurements.')
#            message.append(' '.join(m))

#        val = np.abs(scores['PRE[10][V20M20]'])
#        if val >= thresh_PRE_10_V20M20:
#            isOutlier=True
#            message.append(f"Median volatility exceeds previous range by {((val-1.0)*100):.0f}%.")

    

#        val = np.abs(scores['STD[1][s1440]'])
#        if val >= thresh_STD_1_s1440:
#            m = []
#            isOutlier=True
#            m.append(f'Contextual outlier of {val:.1f} sigma detected.')
#            val2 = np.abs(scores['PRE[10][s1440]'])
#            if val2 < 1:
#                m.append(f'But a similar contextual outlier has been seen before in {((1.0 - val2)*100):.0f}% of measurements.')
#            message.append(' '.join(m))

#        val = np.abs(scores['PRE[10][s1440]'])
#        if val >= thresh_PRE_10_s1440:
#            message.append(f"Contextual outlier detected that deviates at least {((val-1.0)*100):.0f}% from the previously seen value range.")
#            isOutlier = True
            

        
        

    def WindowOutlierScore(self, training, test):

        perform_detection = True

        nans = self.series[training].isna() 
        nan_times = nans[nans==True].index.to_list()
        if len(nan_times) > 0:
            warnings.warn(f"Warning: training data contains {len(nan_times)} out of {len(training)} NaNs:\n{nan_times}\n")
        if len(nan_times) == len(training):
            warnings.warn(f"Warning: No valid training data! Output will be NaN only!\n")
            perform_detection = False
        if len(training) - len(nan_times) < self.min_training_data:
            warnings.warn(f"Warning: Non NaN training data less than {self.min_training_data}. No testing performed. Output will be NaN only!\n")
            perform_detection = False


        nans = self.series[test].isna() 
        nan_times = nans[nans==True].index.to_list()
        if len(nan_times) > 0:
            warnings.warn(f"Warning: test data contains {len(nan_times)} out of {len(test)} nans:\n{nan_times}\n")
        if len(nan_times) == len(test):
            warnings.warn(f"Warning: No valid test data! Output will be NaN only!\n")
            perform_detection = False


        result = pd.DataFrame(index = test)

        for detector_tuple in self.detectors:
            detector = detector_tuple[0]
            arguments = detector_tuple[1]
            preprocessor = detector_tuple[2]
            name = detector.__name__ + "["
            for x in arguments:
                name = name + str(x) + ","
            name = name[:-1]
            name += "]"

            name = "D_" + str(detector_tuple[5])
            
            if perform_detection:
                if preprocessor:
                    perform_detection_after_preprocessing = True
                    processed_series = self.series.copy()
                    #name += "["
                    skip = 0 # we skip this many from the beginning of the series in the training data to avoid boundary effects
                    for p in preprocessor:
                        #print("Preprocessing:")
                        #print(p)
                        pp_type = p[0]
                        pp_args = p[1]
                        #print(pp_args)
                        #name += p[0] + ' '.join(str(e) for e in p[1])

                        pp_func = getattr(self, 'pp_' + pp_type)

                        #pp_args = 10

                        #print(pp_func)

                        processed_series, critical_error, add_skip = pp_func(processed_series, pp_args)

                        skip += add_skip
                        if critical_error:
                            perform_detection_after_preprocessing = False

                    #name += "]"


                    # other name instead
                    #print(detector[5])
                    #name = "D_" + str(detector_tuple[5]) # 

                    if len(training) - len(nan_times) - skip < self.min_training_data:
                        warnings.warn(f"Warning: Non NaN training data less than {self.min_training_data}. No testing performed. Output will be NaN only!\n")
                        perform_detection_after_preprocessing = False

                    if perform_detection_after_preprocessing:
                        result[name] = detector(processed_series, training[skip:], test, arguments)
                    else:
                        result[name] = np.nan
                else:
                    result[name] = detector(self.series, training, test, arguments)
            else:
                result[name] = np.nan

        return result


    def AutomaticallySelectDetectors(self, sigma_STD = 5, deviation_PRE = 0.05, periods_necessary_for_average = 3):
        self.ClearDetectors()
        # find most often occurring time difference in nanoseconds and store in time_diff_ns
        time_differences_ns = np.diff(self.series.index).astype(int)
        unique, counts = np.unique(time_differences_ns, return_counts=True)
        dic = dict(zip(unique, counts))
        max = - 1
        time_diff_ns = 0
        for key, value in dic.items():
            if value > max:
                max = value
                time_diff_ns = key


       
        time_diff_min = time_diff_ns / 1000 / 1000 / 1000 / 60

        time_diff_hours = time_diff_min / 60

        print(f"Time difference: {time_diff_min} minutes")

        min_per_hour = 60

        min_per_day = 24 * 60

        min_per_week = 24 * 60 * 7

        min_per_month = 24 * 60 * 7 * 30.5

        min_per_year = 24 * 60 * 365

        num_data = len(self.series)

        average_length = []

        season = None


        if time_diff_min < 60:
            # average over hour
            if num_data >= periods_necessary_for_average * min_per_hour / time_diff_min:
                average_length.append(int(min_per_hour / time_diff_min))
                season = int(min_per_hour / time_diff_min)
            # average over day
            if num_data >= periods_necessary_for_average * min_per_day / time_diff_min:
                #average_length.append(int(min_per_day / time_diff_min))
                season = int(min_per_day / time_diff_min)
            # average over week
            if num_data >= periods_necessary_for_average * min_per_week / time_diff_min:
                #average_length.append(int(min_per_week / time_diff_min))
                season = int(min_per_week / time_diff_min)

        # OSKAR type hourly data
        if time_diff_min == 60:
            # average over day
            if num_data >= periods_necessary_for_average * min_per_day / time_diff_min:
                average_length.append(int(min_per_day / time_diff_min))
                season = int(min_per_day / time_diff_min)
            # average over week
            if num_data >= periods_necessary_for_average * min_per_week / time_diff_min:
                #average_length.append(int(min_per_week / time_diff_min))
                season = int(min_per_week / time_diff_min)
            # average over month
            if num_data >= periods_necessary_for_average * min_per_month / time_diff_min:
                #average_length.append(int(min_per_month / time_diff_min))
                season = int(min_per_month / time_diff_min)

        if time_diff_min == 24 * 60:
            # average over week
            if num_data >= periods_necessary_for_average * min_per_week / time_diff_min:
                average_length.append(int(min_per_week / time_diff_min))
                season = int(min_per_week / time_diff_min)
            # average over month
            if num_data >= periods_necessary_for_average * min_per_month / time_diff_min:
                #average_length.append(int(min_per_month / time_diff_min))
                season = int(min_per_month / time_diff_min)
            # average over year
            if num_data >= periods_necessary_for_average * min_per_year / time_diff_min:
                #average_length.append(int(min_per_year / time_diff_min))
                season = int(min_per_year / time_diff_min)
            

        
            

        # decompose strategy from subday to dayly

        # from daily to weekly / monthly / yearly depending on period lengh

        # try differences with a given time series of first doing weekly then yearly, or just yearly. 

        # Maybe downsample to month first, then do yearly seasonality subtraction 


        self.AddDetector(['STD', [1], [], sigma_STD])
        self.AddDetector(['PRE', [10], [], 1.0 + deviation_PRE])

        # Add average detectors:

        for a in average_length:
            self.AddDetector(['STD', [1], [['average', [a]]], sigma_STD])
            self.AddDetector(['PRE', [10], [['average', [a]]], 1.0 + deviation_PRE])

        if not season == None:
            self.AddDetector(['STD', [1], [['season_subtract', [season]]], sigma_STD])
            self.AddDetector(['PRE', [10], [['season_subtract', [season]]], 1.0 + deviation_PRE])


    def PrintDetectors(self):
        for d in self.detectors:
            print(d) 

    def GetDetectorNames(self):
        names = []
        for detector in self.detectors:
            
            type = detector[4]
            ID = detector[5]
            threshold = detector[3]
            preprocessor = detector[2]
            args = detector[1]

            full_name = f"D{ID}: " + type + "_" + "".join(str(e) for e in args) + "_" + "".join(str(e) for e in preprocessor) + "_" + str(threshold)
            names.append(full_name)
        return names
