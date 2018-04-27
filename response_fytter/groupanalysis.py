from .response_fytter import ResponseFytter
import numpy as np
import pandas as pd
import warnings
import seaborn as sns

class GroupResponseFytter(object):

    def __init__(self,
                 timeseries,
                 behavior,
                 input_sample_rate,
                 confounds=None,
                 *args,
                 **kwargs):

        self.timeseries = timeseries.reset_index()
        self.onsets = behavior.reset_index()
        self.confounds = confounds

        if 'condition' not in self.onsets:
            self.onsets['condition'] = 'intercept'

        self.index_columns = []

        for c in ['subj_idx', 'run']:
            if c in self.timeseries.columns:
                self.index_columns.append(c)

        self.timeseries['t'] = self.timeseries.groupby(self.index_columns).apply(_make_time_column, 
                                                                                 input_sample_rate)

        self.response_fitters = []

        if self.index_columns is []:
            self.index_columns = None
            self.response_fitters = [ResponseFytter(self.timeseries,
                                                   input_sample_rate,
                                                   *args,
                                                   **kwargs)]
        else:
            self.timeseries.set_index(self.index_columns + ['t'], inplace=True)
            self.onsets.set_index(self.index_columns + ['condition'], inplace=True)

            for idx, ts in self.timeseries.groupby(level=self.index_columns):
                rf = ResponseFytter(ts,
                                    input_sample_rate,
                                    *args,
                                    **kwargs)
                self.response_fitters.append(rf)


    def add_event(self,
                 event=None,
                 basis_set='fir', 
                 interval=[0,10], 
                 n_regressors=0, 
                 covariates=None,
                 add_intercept=True,
                 **kwargs):

        if event is None:
            event = self.onsets.index.get_level_values('condition').unique()
        if event is str:
            event = [event]

        if type(covariates) is str:
            covariates = [covariates]

        for i, (col, ts) in self._groupby_ts():
            for e in event:
                
                if type(col) is not tuple:
                    col = (col,)

                if covariates is not None:
                    covariate_matrix = self.onsets.loc[col + (e,), covariates]

                    if add_intercept:
                        intercept_matrix = pd.DataFrame(np.ones((len(covariate_matrix), 1)),
                                                        columns=['intercept'],
                                                        index=covariate_matrix.index)
                        covariate_matrix = pd.concat((intercept_matrix, covariate_matrix), 1)
                else:
                    covariate_matrix = None

                self.response_fitters[i].add_event(e,
                                                   onset_times=self.onsets.loc[col + (e,), 'onset'],
                                                   basis_set=basis_set,
                                                   interval=interval,
                                                   n_regressors=n_regressors,
                                                   covariates=covariate_matrix)



    def fit(self):
        for response_fitter in self.response_fitters:
            response_fitter.regress()

    def get_timecourses(self):
        df = []
        for i, (col, ts) in self._groupby_ts():

            if type(col) is not tuple:
                col = (col,)

            tc = self.response_fitters[i].get_timecourses()

            for ic, value in zip(self.index_columns, col):
                tc[ic] = value
            

            df.append(tc)

        return pd.concat(df).reset_index().set_index(self.index_columns + tc.index.names)

    def _groupby_ts(self): 
        return enumerate(self.timeseries.groupby(level=self.index_columns))


    def get_subjectwise_timecourses(self, melt=False):
        tc = self.get_timecourses()
        tc = tc.reset_index().groupby(['subj_idx', 'event type','covariate', 'time', ]).mean()

        for c in self.index_columns:
            if c in tc.columns:
                tc.drop(columns=c, inplace=True)

        if melt:
            return tc.reset_index().melt(id_vars=tc.index.names,
                                         var_name='signal')
        else:
            return tc

    def plot_groupwise_timecourses(self,
                                   plots='signal',
                                   col='covariate',
                                   row=None,
                                   col_wrap=None,
                                   hue='event type',
                                   max_n_plots=40,
                                   *args,
                                   **kwargs):
        tc = self.get_subjectwise_timecourses(melt=True)

        
        if len(tc[plots].unique()) > max_n_plots:
            raise Exception('Splitting over %s would mean more than %d plots!')

        for idx, label in tc.groupby(plots):
            fac = sns.FacetGrid(tc.reset_index(),
                                col_wrap=col_wrap,
                                col=col,
                                row=row)

            fac.map_dataframe(sns.tsplot,
                              time='time',
                              unit='subj_idx',
                              condition=hue,
                              value='value',
                              color=sns.color_palette(),
                              *args,
                              **kwargs)

        return fac





def _make_time_column(d, sample_rate):
    return pd.DataFrame(np.arange(0, len(d) * sample_rate, sample_rate), index=d.index)

