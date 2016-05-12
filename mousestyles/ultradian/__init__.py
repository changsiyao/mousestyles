from __future__ import print_function, absolute_import, division

from gatspy.periodic import LombScargleFast
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import chi2

import mousestyles.data as data

INTERVAL_FEATURES = ["AS", "F", "M_AS", "M_IS", "W"]
ALL_FEATURES = ["AS", "F", "M_AS", "M_IS", "W", "Distance"]


def aggregate_interval(strain, mouse, feature, bin_width):
    """
    Aggregate the interval data based on n-minute time
    intervals, return a time series.

    Parameters
    ----------
    strain: int
        nonnegative integer indicating the strain number
    mouse: int
        nonnegative integer indicating the mouse number
    feature: {"AS", "F", "M_AS", "M_IS", "W"}
        "AS": Active state probalibity
        "F": Food consumed (g)
        "M_AS": Movement outside homebase
        "M_IS": Movement inside homebase
        "W": Water consumed (g)
    bin_width: number of minutes of time interval for data aggregation

    Returns
    -------
    ts: pandas.tseries
        a pandas time series of length 12(day)*24(hour)*60(minute)/n
    """
    # Input Check

    if (not isinstance(strain, int)) or (strain < 0):
        raise ValueError(
            'Strain must be a non-negative integer')
    if (not isinstance(mouse, int)) or (mouse < 0):
        raise ValueError(
            'Mouse value must be a non-negative integer')
    if feature not in INTERVAL_FEATURES:
        raise ValueError(
            'Input value must in {"AS", "F", "M_AS", "M_IS", "W"}')
    if (not isinstance(bin_width, int)) or bin_width < 0 or bin_width > 1440:
        raise ValueError(
            'Bin width (minutes) must be a non-negative integer below 1440')

    # load data
    intervals = data.load_intervals(feature)
    mouse_data = intervals.loc[
        (intervals['strain'] == strain) & (intervals['mouse'] == mouse)]

    # build data frame
    days = sorted(np.unique(mouse_data['day']))
    bin_count = int(24 * 60 / bin_width)
    time_behaviour = np.repeat(0.0, bin_count * len(days))
    bin_length = bin_width * 60

    for j in days:
        df = mouse_data.loc[mouse_data['day'] == j]
        start_end = data.load_start_time_end_time(strain, mouse, j)
        start = np.asarray(df['start']) - start_end[0]
        end = np.asarray(df['stop']) - start_end[0]

        for i in range(len(start)):
            start_time = start[i]
            end_time = end[i]
            start_index = int(start_time / (bin_width * 60))
            end_index = int(end_time / (bin_width * 60))
            if start_index == end_index:
                time_behaviour[start_index + j *
                               bin_count] += end_time - start_time
            elif end_index - start_index == 1:
                time_behaviour[
                    start_index + j *
                    bin_count] += bin_length * end_index - start_time
                time_behaviour[end_index + j *
                               bin_count] += end_time % bin_length
            else:
                time_behaviour[
                    start_index + j *
                    bin_count] += bin_length * (start_index + 1) - start_time
                time_behaviour[end_index + j *
                               bin_count] += end_time % bin_length
                time_behaviour[start_index + j * bin_count +
                               1:end_index + j * bin_count] += bin_length

    if feature == 'F' or feature == 'W':
        all_feature = data.load_all_features()
        group = all_feature[
            ["strain", "mouse", "day", "hour", "Food", "Water"]].groupby(
            ["strain", "mouse", "day"]).sum()
        group = group.reset_index()
        mouse_data = group.loc[(group['strain'] == strain) &
                               (group['mouse'] == mouse)].copy()
        mouse_data.loc[:, 'day'] = np.arange(len(mouse_data))
        for i in mouse_data['day'].astype('int'):
            if feature == 'F':
                food_amount = float(mouse_data['Food'][mouse_data['day'] == i])
                time_behaviour[
                    (bin_count * i):(bin_count * (i + 1))] /= sum(
                    time_behaviour[(bin_count * i):(bin_count * (i + 1))])
                time_behaviour[(bin_count * i):(bin_count *
                                                (i + 1))] *= food_amount
            else:
                food_amount = float(mouse_data['Water'][
                                    mouse_data['day'] == i])
                time_behaviour[
                    (bin_count * i):(bin_count * (i + 1))] /= sum(
                    time_behaviour[(bin_count * i):(bin_count * (i + 1))])
                time_behaviour[(bin_count * i):(bin_count *
                                                (i + 1))] *= food_amount
    if feature == 'AS':
        time_behaviour /= (bin_width * 60)

    ts = pd.Series(time_behaviour, index=pd.date_range(
        '01/01/2014', periods=len(time_behaviour),
        freq=str(bin_width) + 'min'))
    return(ts)


def aggregate_movement(strain, mouse, bin_width):
    """
    Aggregate the movement data based on n-minute
    time intervals, return a time series.

    Parameters
    ----------
    strain: int
        nonnegative integer indicating the strain number
    mouse: int
        nonnegative integer indicating the mouse number
    bin_width: number of minutes of time interval for data aggregation

    Returns
    -------
    ts: pandas.tseries
        a pandas time series of length (#day)*24(hour)*60(minute)/n
    """
    # Input Check
    if (not isinstance(strain, int)) or (strain < 0):
        raise ValueError(
            'Strain must be a non-negative integer')
    if (not isinstance(mouse, int)) or (mouse < 0):
        raise ValueError(
            'Mouse value must be a non-negative integer')
    if (not isinstance(bin_width, int)) or bin_width < 0 or bin_width > 1440:
        raise ValueError(
            'Bin width (minutes) must be a non-negative integer below 1440')

    # determine number of days
    intervals = data.load_intervals('IS')
    mouse_data = intervals.loc[
        (intervals['strain'] == strain) & (intervals['mouse'] == mouse)]
    days = sorted(np.unique(mouse_data['day']))

    # build data frame
    bin_count = int(24 * 60 / bin_width)
    time_movements = np.repeat(0.0, bin_count * len(days))
    bin_length = bin_width * 60
    for j in days:
        M = data.load_movement(strain, mouse, day=int(j))
        distance_df = pd.DataFrame({"start": M["t"].values[0:-1],
                                    "end": M["t"].values[1:],
                                    "distance":
                                    np.linalg.norm(M[["x", "y"]].values[1:] -
                                                   M[["x", "y"]].values[0:-1],
                                                   axis=1)})
        start_end = data.load_start_time_end_time(strain, mouse, j)
        start = np.asarray(distance_df['start']) - start_end[0]
        end = np.asarray(distance_df['end']) - start_end[0]
        dist = distance_df['distance']
        for i in range(len(start)):
            start_time = start[i]
            end_time = end[i]
            start_index = int(start_time / (bin_width * 60))
            end_index = int(end_time / (bin_width * 60))
            if start_index == end_index:
                time_movements[start_index + j *
                               bin_count] += dist[i]
            else:
                time_movements[
                    end_index + j * bin_count] += end_time % \
                    bin_length / (end_time - start_time) * dist[i]
                time_movements[
                    start_index + j * bin_count] += dist[i] - \
                    end_time % bin_length / (end_time - start_time) * dist[i]
    ts = pd.Series(time_movements, index=pd.date_range(
        '01/01/2014', periods=len(time_movements),
        freq=str(bin_width) + 'min'))
    return(ts)


def aggregate_data(feature, bin_width, nmouse = 4, nstrain = 3):
    r"""
    Aggregate all the strains and mouses with any feature together
    in one dataframe. It combines the results you got from
    aggregate_movements and aggregate_interval. It will return
    a dataframe with three variables: mouse, strain, feature and hour.

    Parameters
    ----------
    feature :
        {"AS", "F", "IS", "M_AS", "M_IS", "W", "Distance"}
    bin_width : int
        Number of minutes, the time interval for data aggregation.

    Returns
    -------
    pandas.dataframe
    describe :
        Column 0: the mouse number (number depends on strain)(0-3)
        Column 1: the strain of the mouse (0-2)
        Column 2: hour(numeric values below 24 accourding to bin_width)
        Column 3: feature values

    Examples
    --------
    >>> test = aggregate_data("Distance",20)
    >>> print(np.mean(test["Distance"]))
    531.4500177747973
    """
    if feature not in ALL_FEATURES:
        raise ValueError(
            'Input value must in {"AS", "F", "M_AS", "M_IS", "W", "Distance"}')
    if (not isinstance(bin_width, int)) or bin_width < 0 or bin_width > 1440:
        raise ValueError(
            'Bin width (minutes) must be a non-negative integer below 1440')

    init = pd.DataFrame(columns=["mouse", "strain", "hour", feature])
    for i in range(nstrain):
        for j in range(nmouse):
            if feature == "Distance":
                tmp = aggregate_movement(strain=i, mouse=j,
                                         bin_width=bin_width)
            else:
                tmp = aggregate_interval(strain=i, mouse=j,
                                         feature=feature,
                                         bin_width=bin_width)
            tmp = pd.DataFrame(list(tmp.values), index=tmp.index)
            tmp.columns = [feature]
            tmp["strain"] = i
            tmp["mouse"] = j
            tmp["hour"] = tmp.index.hour + tmp.index.minute / 60
            init = init.append(tmp)
    return(init)


def seasonal_decomposition(strain, mouse, feature, bin_width, period_length):
    """
    Apply seasonal decomposition model on the time series
    of specified strain, mouse, feature and bin_width.

    Parameters
    ----------
    strain: int
        nonnegative integer indicating the strain number
    mouse: int
        nonnegative integer indicating the mouse number
    feature: {"AS", "F", "M_AS", "M_IS", "W", "Distance"}
        "AS": Active state probalibity
        "F": Food consumed (g)
        "M_AS": Movement outside homebase
        "M_IS": Movement inside homebase
        "W": Water consumed (g)
        "Distance": Distance traveled
    bin_width: int
        number of minutes, the time interval for data aggregation
    period_length: int
        number of hours, usually the significant period
        length indicated by Lomb-scargle model

    Returns
    -------
    res: statsmodel seasonal decomposition object
        seasonal decomposition result for the mouse.
        Check the seasonal decomposition plot by res.plot(),
        seasonl term and trend term by res.seasonal and
        res.trend separately.

    Examples
    --------
    >>> res = seasonal_decomposition(strain=0, mouse=0, feature="W",
                                     bin_width=30, period_length = 24)
    """

    if (not isinstance(strain, int)) or (strain < 0):
        raise ValueError(
            'Strain must be a non-negative integer')
    if (not isinstance(mouse, int)) or (mouse < 0):
        raise ValueError(
            'Mouse value must be a non-negative integer')
    if feature not in ALL_FEATURES:
        raise ValueError(
            'Input value must in {"AS", "F", "M_AS", "M_IS", "W", "Distance"}')
    if (not isinstance(bin_width, int)) or bin_width < 0 or bin_width > 1440:
        raise ValueError(
            'Bin width (minutes) must be a non-negative integer below 1440')
    if (not isinstance(period_length, int)) or period_length < 0:
        raise ValueError(
            'Peoriod length must be a non-negative integer')

    freq = int(period_length * 60 / bin_width)
    if feature == "Distance":
        ts = aggregate_movement(strain=strain, mouse=mouse,
                                bin_width=bin_width)
    else:
        ts = aggregate_interval(strain=strain, mouse=mouse,
                                feature=feature, bin_width=bin_width)
    res = sm.tsa.seasonal_decompose(ts.values, freq=freq, model="additive")
    return(res)


def strain_seasonal(strain, mouse, feature, bin_width, period_length):
    """
    Use seansonal decomposition model on the time series
    of specified strain, mouse, feature and bin_width.
    return the seasonal term and the plot of seasonal term
    by mouse of a set of mouses in a strain

    Parameters
    ----------
    strain: int
        nonnegative integer indicating the strain number
    mouse: list, set or tuple
        nonnegative integer indicating the mouse number
    feature: {"AS", "F", "M_AS", "M_IS", "W", "Distance"}
        "AS": Active state probalibity
        "F": Food consumed (g)
        "M_AS": Movement outside homebase
        "M_IS": Movement inside homebase
        "W": Water consumed (g)
        "Distance": Distance traveled
    bin_width: int
        number of minutes, the time interval for data aggregation
    period_length: int
        number of hours, usually the significant period
        length indicated by Lomb-scargle model

    Returns
    -------
    seasonal_all: numpy array containing the seasonal term for every
        mouse indicated by the input parameter

    Examples
    --------
    >>> res = strain_seasonal(strain=0, mouse={0, 1, 2, 3}, feature="W",
                              bin_width=30, period_length = 24)
    """

    if (not isinstance(strain, int)) or (strain < 0):
        raise ValueError(
            'Strain must be a non-negative integer')
    if (not all([isinstance(m, int)
                 for m in mouse])) or (any([m < 0 for m in mouse])):
        raise ValueError(
            'Mouse value must be a non-negative integer')
    if feature not in ALL_FEATURES:
        raise ValueError(
            'Input value must in {"AS", "F", "M_AS", "M_IS", "W", "Distance"}')
    if (not isinstance(bin_width, int)) or bin_width < 0 or bin_width > 1440:
        raise ValueError(
            'Bin width (minutes) must be a non-negative integer below 1440')
    if (not isinstance(period_length, int)) or period_length < 0:
        raise ValueError(
            'Peoriod length must be a non-negative integer')
    # seasonal decomposition
    seasonal_all = np.array([])
    freq = int(period_length * 60 / bin_width)
    for m in mouse:
        res = seasonal_decomposition(
            strain, m, feature, bin_width, period_length)
        seasonal_all = np.append(seasonal_all, res.seasonal[0:freq])
    seasonal_all = seasonal_all.reshape([len(mouse), -1])
    return(seasonal_all)


def plot_strain_seasonal(strains, mouse, feature, bin_width, period_length):
    """
    Use seansonal decomposition model on the time series
    of specified strain, mouse, feature and bin_width.
    return the seasonal term and the plot of seasonal term
    by mouse of a set of mouses in a strain

    Parameters
    ----------
    strain: list, set or tuple
        nonnegative integer indicating the strain number
    mouse: list, set or tuple
        nonnegative integer indicating the mouse number
    feature: {"AS", "F", "M_AS", "M_IS", "W", "Distance"}
        "AS": Active state probalibity
        "F": Food consumed (g)
        "M_AS": Movement outside homebase
        "M_IS": Movement inside homebase
        "W": Water consumed (g)
        "Distance": Distance traveled
    bin_width: int
        number of minutes, the time interval for data aggregation
    period_length: int
        number of hours, usually the significant period
        length indicated by Lomb-scargle model

    Returns
    -------
    seasonal_plot: plot of seasonal term by mouse

    Examples
    --------
    >>> res = plot_strain_seasonal(strain={0, 1, 2,}, mouse={0, 1, 2, 3},
                                   feature="W",
                                   bin_width=30, period_length = 24)
    """

    if (not all([isinstance(m, int)
                 for m in mouse])) or (any([m < 0 for m in mouse])):
        raise ValueError(
            'Strain must be a non-negative integer')
    if (not all([isinstance(m, int)
                 for m in mouse])) or (any([m < 0 for m in mouse])):
        raise ValueError(
            'Mouse value must be a non-negative integer')
    if feature not in ALL_FEATURES:
        raise ValueError(
            'Input value must in {"AS", "F", "M_AS", "M_IS", "W", "Distance"}')
    if (not isinstance(bin_width, int)) or bin_width < 0 or bin_width > 1440:
        raise ValueError(
            'Bin width (minutes) must be a non-negative integer below 1440')
    if (not isinstance(period_length, int)) or period_length < 0:
        raise ValueError(
            'Peoriod length must be a non-negative integer')
    time = np.arange(0, period_length, bin_width / 60)
    fig = plt.figure(figsize=(8, 8))
    flag = 0
    for strain in strains:
        if flag == 0:
            ax = fig.add_subplot(3, 1, strain + 1)
            flag += 1
        else:
            ax = fig.add_subplot(3, 1, strain + 1, sharey=ax)
        seasonal_all = strain_seasonal(strain, mouse, feature,
                                       bin_width, period_length)
        for i in np.arange(len(mouse)):
            ax.plot(time, seasonal_all[i, :])
        ax.legend(['mouse' + str(i) for i in np.arange(len(mouse))],
                  loc='upper right', prop={'size': 10})
        ax.set_title('strain ' + str(strain))
        plt.xlabel('Time')
        plt.ylabel('Seasonal Variation')
        plt.suptitle(feature, fontsize=20)
    fig.show()
    return(fig)


def mix_strain(data, feature, print_opt = True, nstrain = 3, range = (3, 12)):
    """
    Fit the linear mixed model onto our aggregate data. The fixed effects
    are the hour, strain, interactions between hour and strain; The random
    effect is mouse because we want to make sure that the different mouses
    will not give out any differences. We added two dummy variables:
    strain0 and strain1 to be our fixed effects.

    Parameters
    ----------
        data: data frame output from aggregate_data function
        feature: {"AS", "F", "IS", "M_AS", "M_IS", "W", "Distance"}

    Returns
    -------
    Two mixed model regression results which includes all the coefficients,
    t statistics and p values for corresponding coefficients; The first model
    includes interaction terms while the second model does not include the
    interaction terms

    Likelihood ratio test p values, if it is below our significance level,
    we can conclude that the different strains have significantly different
    time patterns

    Examples
    --------
    >>> result = mix_strain(data = aggregate_data("F",30), feature = "F",
    >>>          print_opt = False)
    >>> print(result)
    1.4047992545261542e-12

    """
    if not isinstance(data, pd.DataFrame):
        raise ValueError(
            'Data must be a pandas data frame')
    if feature not in ALL_FEATURES:
        raise ValueError(
            'Input value must in {"AS", "F", "M_AS", "M_IS", "W", "Distance"}')
    data["cycle"] = 0
    for i in range(nstrain):
        result = Find_Cycle(feature = "W", strain = i, plot = False,
                            search_range_find = range)
        cycle = result[0][0]
        data.loc[data["strain"] == i, "cycle"] = cycle
    b = pd.get_dummies(data["strain"])
    data["strain0"] = b.ix[:, 0]
    data["strain1"] = b.ix[:, 1]
    data["strain2"] = b.ix[:, 2]
    data = data.drop('strain', 1)
    names = data.columns.tolist()
    names[names.index(feature)] = 'feature'
    data.columns = names
    md1 = smf.mixedlm(
        "feature ~ hour + strain0 + strain1 + cycle + \
                      strain0*hour + strain1*hour",
        data, groups=data["mouse"])
    mdf1 = md1.fit()
    like1 = mdf1.llf
    if print_opt:
        print(mdf1.summary())
    md2 = smf.mixedlm("feature ~ hour + cycle + strain0 + strain1",
                      data, groups=data["mouse"])
    mdf2 = md2.fit()
    like2 = mdf2.llf
    if print_opt:
        print(mdf2.summary())
    fstat = 2*abs(like1 - like2)
    p_v = chi2.pdf(fstat, df=2)
    return(p_v)

# methods LombScargel, FDS, visualization take out, mouse == none


def Find_Cycle(feature, strain, mouse=None, bin_width=15,
               methods='LombScargleFast', search_range_fit=None,
               disturb_t=False, plot=True, nyquist_factor=3,
               n_cycle=10, search_range_find=(2, 26), sig=np.array([0.05])):
    """
    Either way of plotting or calculating power is not
    the same method used in the find_best cycle.

    Parameters
    ----------
    search_range_fit: numpy array, like np.arange(0,26,0.1), defalut is None

    Returns
    -------
    ts: pandas.tseries
        a pandas time series of length 12(day)*24(hour)*60(minute)/n
    """
    # get data
    if mouse is None:
        data_all = aggregate_data(feature=feature, bin_width=bin_width)
        n_mouse_in_strain = len(
            set(data_all.loc[data_all['strain'] == strain]['mouse']))
        data = [[] for i in range(n_mouse_in_strain)]
        t = [[] for i in range(n_mouse_in_strain)]
        for i in range(n_mouse_in_strain):
            data[i] = data_all.loc[(data_all['strain'] == strain) & (
                data_all['mouse'] == i)][feature]
            t[i] = np.array(np.arange(0, len(data[i]) *
                                      bin_width / 60, bin_width / 60))

        data = [val for sublist in data for val in sublist]
        N = len(data)
        t = [val for sublist in t for val in sublist]
    else:
        if feature == 'Distance':
            data = aggregate_movement(
                strain=strain, mouse=mouse, bin_width=bin_width)
            N = len(data)
            t = np.arange(0, N * bin_width / 60, bin_width / 60)
        else:
            data = aggregate_interval(
                strain=strain, mouse=mouse,
                feature=feature, bin_width=bin_width)
            N = len(data)
            t = np.arange(0, N * bin_width / 60, bin_width / 60)

    y = data

    # fit model
    if disturb_t is True:
        t = t + np.random.uniform(-bin_width / 600, bin_width / 600, N)

    model = LombScargleFast(fit_period=False).fit(t=t, y=y)
    # calculate periods' LS power
    if search_range_fit is None:
        periods, power = model.periodogram_auto(nyquist_factor=nyquist_factor)
    else:
        periods = search_range_fit
        power = model.periodogram(periods=search_range_fit)
    # print(periods[:15]); print(len(periods));
    # print(5*nyquist_factor/2*N)
    # find best cycle
    model.optimizer.period_range = search_range_find
    cycle, cycle_power = model.find_best_periods(
        return_scores=True, n_periods=n_cycle)
    cycle_pvalue = 1 - (1 - np.exp(cycle_power / (-2) * (N - 1))) ** (2 * N)
    # visualization
    if plot is True:
        fig, ax = plt.subplots()
        ax.plot(periods, power)
        ax.set(xlim=(0, 25),  # ylim=(0, 0.5),
               xlabel='period (hours)',
               ylabel='Lomb-Scargle Power')
        for i in sig:
            power_sig = -2 / (N - 1) * np.log(
                1 - (1 - np.asarray(i)) ** (1 / 2 / N))
            plt.axhline(y=power_sig, color='green', ls='dashed', lw=1)
            ax.text(x=24, y=power_sig, s='P-value:' +
                    str(float(i)), ha='right', va='bottom')
            idx = [i for i, x in enumerate(cycle_pvalue) if x < 0.001]
            for j in idx:
                ax.text(x=cycle[j], y=cycle_power[j],
                        s=r'$\bigstar\bigstar\bigstar$',
                        ha='right', va='top')
            idx = [i for i, x in enumerate(
                cycle_pvalue) if x > 0.001 and x < 0.01]
            for j in idx:
                ax.text(x=cycle[j], y=cycle_power[j],
                        s=r'$\bigstar\bigstar$', ha='right', va='top')
            idx = [i for i, x in enumerate(
                cycle_pvalue) if x > 0.01 and x < 0.05]
            for j in idx:
                ax.text(x=cycle[j], y=cycle_power[j],
                        s=r'$\bigstar$', ha='right', va='top')

    return cycle, cycle_power, cycle_pvalue
