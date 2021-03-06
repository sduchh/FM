"""Python wrappers for the libfm and fastFM"""
import subprocess
import os
import sys
import tempfile

import numpy as np
try:
    from fastFM import als, mcmc, sgd
except ImportError:
    print('Warning: fastFM package is not installed, can not use.')

from data_process import *


class Libfm:
    """ Class that wraps libfm library. For more information read
    [libFM manual](http://www.libfm.org/libfm-1.42.manual.pdf)
    github  https://github.com/srendle/libfm
    Parameters
    ----------
    task : string, MANDATORY
        regression: for regression
        classification: for binary classification
    num_iter: int, optional
        Number of iterations
        Defaults to 100
    init_stdev : double, optional
        Standard deviation for initialization of 2-way factors
        Defaults to 0.1
    k0 : bool, optional
        Use bias.
        Defaults to True
    k1 : bool, optional
        Use 1-way interactions.
        Defaults to True
    k2 : int, optional
        Dimensionality of 2-way interactions.
        Defaults to 8
    learning_method: string, optional
        sgd: parameter learning with SGD
        sgda: parameter learning with adpative SGD
        als: parameter learning with ALS
        mcmc: parameter learning with MCMC
        Defaults to 'mcmc'
    learn_rate: double, optional
        Learning rate for SGD
        Defaults to 0.1
    r0_regularization: int, optional
        bias regularization for SGD and ALS
        Defaults to 0
    r1_regularization: int, optional
        1-way regularization for SGD and ALS
        Defaults to 0
    r2_regularization: int, optional
        2-way regularization for SGD and ALS
        Defaults to 0
    rlog: bool, optional
        Enable/disable rlog output
        Defaults to True.
    verbose: bool, optional
        How much infos to print
        Defaults to False.
    seed: int, optional
        seed used to reproduce the results
        Defaults to None.
    silent: bool, optional
        Completely silences all libFM output
        Defaults to False.
    temp_path: string, optional
        Sets path for libFM temporary files. Useful when dealing with large data.
        Defaults to None (default NamedTemporaryFile behaviour)
    """

    """
    ### unsused libFM flags
    cache_size: cache size for data storage (only applicable if data is in binary format), default=infty
        datafile is text so we don't need this parameter
    relation: BS - filenames for the relations, default=''
        not dealing with BS extensions since they are only used for binary files
    """

    def __init__(self,
                 task='classification',
                 num_iter=100,
                 init_stdev=0.1,
                 k0=True,
                 k1=True,
                 k2=8,
                 learning_method='mcmc',
                 learn_rate=0.1,
                 r0_regularization=0,
                 r1_regularization=0,
                 r2_regularization=0,
                 rlog=True,
                 verbose=False,
                 seed=None,
                 silent=False,
                 temp_path=None,
                 model_path=None):
        self.__task = task[0]  # gets first letter of either regression or classification
        self.__num_iter = num_iter
        self.__init_stdev = init_stdev
        self.__dim = "%d,%d,%d" % (int(k0), int(k1), k2)
        self.__learning_method = learning_method
        self.__learn_rate = learn_rate
        self.__regularization = "%.5f,%.5f,%.5f" % (r0_regularization, r1_regularization, r2_regularization)
        self.__rlog = rlog
        self.__verbose = int(verbose)
        self.__seed = int(seed) if seed else None
        self.__silent = silent
        self.__temp_path = temp_path
        self.__model_path = model_path
        self.__libfm_path = os.environ.get('LIBFM_PATH')  # gets libfm path
        if self.__libfm_path is None:
            raise OSError("`LIBFM_PATH` is not set. Please install libFM and set the path variable "
                          "(https://github.com/jfloff/pywFM#installing).")
        # #ShameShame
        # Once upon a time, there was a bug in libFM that allowed any type of
        # learning_method to save the model. I @jfloff built this package at
        # that time, and did not find anything that showed me that MCMC couldn't
        # use save_model flag. Nowadays only SGD and ALS can use this parameter.
        # Hence, we need to reset the repo to this specific commit pre-fix, so
        # we can use MCMC with save_model flag.
        GITHASH = '91f8504a15120ef6815d6e10cc7dee42eebaab0f'
        if sys.version < '2.7':
            c_githash = subprocess.Popen(['git', '--git-dir', os.path.join(self.__libfm_path, "..", ".git"), 'rev-parse', 'HEAD'], stdout=subprocess.PIPE).communicate()[0].strip()
        else:
            c_githash = subprocess.check_output(['git', '--git-dir', os.path.join(self.__libfm_path, "..", ".git"), 'rev-parse', 'HEAD']).strip()
        if c_githash != GITHASH:
            raise OSError("libFM is not checked out to the correct commit."
                          "(https://github.com/jfloff/pywFM#installing).")

    @staticmethod
    def _save(data, path, fmt='%.8f'):
        np.savetxt(path, np.array(data), fmt=fmt)
        print('Already save the model parameters into {0}'.format(path))

    def run(self, train_set, test_set, validation_set=None, meta=None):
        """Run factorization machine model against train and test data
        Parameters
        ----------
        train_set: Training data, libsvm format 
        test_set: Testing data, libsvm format
        validation_set: optional, libsvm format Validation data (only for SGDA)
        meta: optional, numpy array of shape [n_features]
            Grouping input variables
        Return
        -------
        Returns `namedtuple` with the following properties:
        predictions: array [n_samples of x_test]
           Predicted target values per element in x_test.
        global_bias: float
            If k0 is True, returns the model's global bias w0
        weights: array [n_features]
            If k1 is True, returns the model's weights for each features Wj
        pairwise_interactions: numpy matrix [n_features x k2]
            Matrix with pairwise interactions Vj,f
        rlog: pandas dataframe [nrow = num_iter]
            `pandas` DataFrame with measurements about each iteration
        """
        from sklearn.datasets import dump_svmlight_file
        TMP_SUFFIX = '.pywfm' # file name end with this
        # train_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path)
        # test_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path)
        out_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path) # out has the predict values
        model_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path) # model parameters
        # converts train and test data to libSVM format
        # dump_svmlight_file(x_train, y_train, train_fd)
        # train_fd.seek(0)
        # dump_svmlight_file(x_test, y_test, test_fd)
        # test_fd.seek(0)

        # builds arguments array
        args = [os.path.join(self.__libfm_path, "libFM"),
                '-task', "%s" % self.__task,
                '-train', "%s" % train_set,  # modify from train_fd.name
                '-test', "%s" % test_set,
                '-dim', "'%s'" % self.__dim,
                '-init_stdev', "%g" % self.__init_stdev,
                '-iter', "%d" % self.__num_iter,
                '-method', "%s" % self.__learning_method,
                '-out', "%s" % out_fd.name,  # like '/var/folders/g5/m2jxwn5d0jd7c130nz1wcvg80000gn/T/tmp8C7Fh6fm'
                '-verbosity', "%d" % self.__verbose,
                '-save_model', "%s" % model_fd.name]

        # appends rlog if true
        rlog_fd = None
        if self.__rlog:
            rlog_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path)
            args.extend(['-rlog', "%s" % rlog_fd.name])
        # appends seed if given
        if self.__seed:
            args.extend(['-seed', "%d" % self.__seed])
        # appends arguments that only work for certain learning methods
        if self.__learning_method in ['sgd', 'sgda']:
            args.extend(['-learn_rate', "%.5f" % self.__learn_rate])

        if self.__learning_method in ['sgd', 'sgda', 'als']:
            args.extend(['-regular', "'%s'" % self.__regularization])
        # adds validation if sgda
        # if validation_set is none, libFM will throw error hence, I'm not doing any validation
        validation_fd = None
        if self.__learning_method == 'sgda' and validation_set is not None :
            # validation_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path)
            # dump_svmlight_file(validation_set, validation_fd.name)
            args.extend(['-validation', "%s" % validation_set])
        # if meta data is given
        meta_fd = None
        if meta is not None:
            meta_fd = tempfile.NamedTemporaryFile(suffix=TMP_SUFFIX, dir=self.__temp_path, text=True)
            # write group ids
            for group_id in meta:
                meta_fd.write("%s\n" % group_id)
            args.extend(['-meta', "%s" % meta_fd.name])
            meta_fd.seek(0)
        # if silent redirects all output
        stdout = None
        if self.__silent:
            stdout = open(os.devnull, 'wb')
        # call libfm with parsed arguments
        # had unkown bug with "-dim" option on array. At the time was forced to
        # concatenate string `args = ' '.join(args)` but looks like its working
        # needs further tests
        subprocess.call(args, shell=False, stdout=stdout)
        # reads output file
        preds = [float(p) for p in out_fd.read().split('\n') if p]
        self._save(preds, '%s/predictions.libfm' % self.__model_path)
        # "hidden" feature that allows users to save the model
        # We use this to get the feature weights
        # https://github.com/srendle/libfm/commit/19db0d1e36490290dadb530a56a5ae314b68da5d
        global_bias = None
        weights = []
        pairwise_interactions = []
        # if 0 its global bias; if 1, weights; if 2, pairwise interactions
        out_iter = 0
        for line in model_fd.read().splitlines():
            # checks which line is starting with #
            if line.startswith('#'):
                if "#global bias W0" in line:
                    out_iter = 0
                elif "#unary interactions Wj" in line:
                    out_iter = 1
                elif "#pairwise interactions Vj,f" in line:
                    out_iter = 2
            else:
                # check context get in previous step and adds accordingly
                if out_iter == 0:
                    global_bias = float(line)
                elif out_iter == 1:
                    weights.append(float(line))
                elif out_iter == 2:
                    try:
                        pairwise_interactions.append([float(x) for x in line.split(' ')])
                    except ValueError as e:
                        pairwise_interactions.append(0.0) #Case: no pairwise interactions used
        # pairwise_interactions = np.matrix(pairwise_interactions)
        self._save(weights, '%s/weights.libfm' % self.__model_path)  # call the statistic method
        self._save(pairwise_interactions, '%s/latent.libfm' % self.__model_path)
        # parses rlog into dataframe
        if self.__rlog:
            import pandas as pd
            rlog_fd.seek(0)
            rlog = pd.read_csv(rlog_fd.name, sep='\t')
            rlog_fd.close()
        else:
            rlog = None
        if self.__learning_method == 'sgda' and validation_set is not None:
            validation_fd.close()
        if meta is not None:
            meta_fd.close()

        # removes temporary output file after using
        model_fd.close()
        out_fd.close()

        # return as named collection for multiple output
        import collections
        model = collections.namedtuple('model', ['predictions',
                                                 'global_bias',
                                                 'weights',
                                                 'pairwise_interactions',
                                                 'rlog'])
        return model(preds, global_bias, weights, pairwise_interactions, rlog)


class Fastfm:
    """Wraps some related classes of the fastFM package
    References:
        -github  https://github.com/ibayer/fastFM
        -python package  https://pypi.python.org/pypi/fastFM/
        -paper  https://arxiv.org/abs/1505.00641

    fastFM input data must be sparse matrix format
    TODO: need to compare with the libFM and provide the interface"""
    def __init__(self,
                 learning_method='mcmc',
                 num_iter=100,
                 init_stdev=0.1,
                 k2=8,
                 learn_rate=0,
                 r0_regularization=0.1,
                 r1_regularization=0.1,
                 r2_regularization=0.1,
                 seed=123,
                 model_path=None):
        if learning_method.upper() == 'MCMC':
            self.fm = mcmc.FMClassification(n_iter=num_iter,
                                            init_stdev=init_stdev,
                                            rank=k2,
                                            random_state=seed)
        elif learning_method.upper() == 'ALS':
            self.fm = als.FMClassification(n_iter=num_iter,
                                           init_stdev=init_stdev,
                                           rank=k2,
                                           random_state=seed,
                                           l2_reg=r0_regularization,
                                           l2_reg_w=r1_regularization,
                                           l2_reg_V=r2_regularization)
        elif learning_method.upper() == 'SGD':
            self.fm = sgd.FMClassification(n_iter=num_iter,
                                           init_stdev=init_stdev,
                                           rank=k2,
                                           random_state=seed,
                                           l2_reg=r0_regularization,
                                           l2_reg_w=r1_regularization,
                                           l2_reg_V=r2_regularization,
                                           step_size=learn_rate)
        else:
            raise TypeError('method should be one of {sgd, als, mcmc}')
        self.__method = learning_method.upper()  # __* means private attribute
        self.__model_path = model_path

    @staticmethod
    def _save(data, path, fmt='%.8f'):
        np.savetxt(path, np.array(data), fmt=fmt)

    @keyword_only
    def run(self, train_X, test_X, train_y, test_y):
        from sklearn.metrics import accuracy_score, roc_auc_score
        if self.__method in ['SGD', 'ALS']:
            self.fm.fit(train_X, train_y)
            y_pred = self.fm.predict(test_X)
            y_pred_proba = self.fm.predict_proba(test_X)
        elif self.__method == 'MCMC':
            y_pred = self.fm.fit_predict(train_X, train_y, test_X)
            y_pred_proba = self.fm.fit_predict_proba(train_X, train_y, test_X)
        # print('the model parameters: \n {}'.format(self.fm.get_params()))  # get the hyperparams of the model))
        print('acc: {0}'.format(accuracy_score(test_y, y_pred)))
        print('auc: {0}'.format(roc_auc_score(test_y, y_pred_proba)))

        if not os.path.exists(self.__model_path):
            os.mkdir(self.__model_path)
        # the model params are in attributes self.fm.w0_, w_, V_
        self._save(self.fm.V_, '%s/latent.fastfm' % self.__model_path)
        self._save(self.fm.w_, '%s/weights.fastfm' % self.__model_path)
        self._save(y_pred_proba, '%s/predictions.fastfm' % self.__model_path)

        import collections
        model = collections.namedtuple('model', ['predictions',
                                                 'global_bias',
                                                 'weights',
                                                 'pairwise_interactions',
                                                 'auc'
                                                 ])
        return model(y_pred, self.fm.w0_, self.fm.w_, self.fm.V_, roc_auc_score(test_y, y_pred_proba))



