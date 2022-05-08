from hyperopt import hp
import numpy as np

class HyperParamProvider():

    pca_params = {
        'n_components': hp.choice('n_components',    np.arange(5, 11, 5, dtype=int)),
        'random_state':     1,
    }

    knn_reg_params = {
        'leaf_size':     hp.choice('leaf_size',    np.arange(25, 36, 2)),
        'n_neighbors':    hp.choice('n_neighbors', np.arange(3, 10, 2, dtype=int)),
    }
    knn_para = dict()
    knn_para['reg_params'] = knn_reg_params
    knn_para['pca_params'] = pca_params

    @classmethod
    def getKnnParam(self):
        return HyperParamProvider.knn_para

    logistic_reg_params = {
        'tol':        hp.uniform('tol', 0.00001, 0.0001),
    #    'C':        hp.uniform('C', 1, 1000),
        'max_iter':     hp.choice('max_iter',    np.arange(50, 151, 50)),
        'random_state':     1,
    }
    logistic_para = dict()
    logistic_para['reg_params'] = logistic_reg_params
    logistic_para['pca_params'] = pca_params

    @classmethod
    def getLogisticParam(self):
        return HyperParamProvider.logistic_para

    rsvc_reg_params = {
    #    'tol':        hp.uniform('tol', 0.001, 0.002),
    #    'C':        hp.uniform('C', 1, 1000),
        'max_iter':     hp.choice('max_iter',    np.arange(50, 151, 50)),
        'kernel':'rbf',
        'class_weight':'balanced',
        'probability':True,
        'random_state':     1,
    }
    rsvc_para = dict()
    rsvc_para['reg_params'] = rsvc_reg_params
    rsvc_para['pca_params'] = pca_params

    @classmethod
    def getRsvcParam(self):
        return HyperParamProvider.rsvc_para

    lsvc_reg_params = {
    #    'tol':        hp.uniform('tol', 0.001, 0.002),
    #    'C':        hp.uniform('C', 1, 1000),
        'max_iter':     hp.choice('max_iter',    np.arange(50, 151, 50)),
        'class_weight':'balanced',
        'random_state':     1,
    }
    lsvc_para = dict()
    lsvc_para['reg_params'] = lsvc_reg_params
    lsvc_para['pca_params'] = pca_params

    @classmethod
    def getLsvcParam(self):
        return HyperParamProvider.lsvc_para

    tree_reg_params = {
        'max_depth':        hp.choice('max_depth',        np.arange(3, 16, 2, dtype=int)),
        'min_samples_leaf': hp.choice('min_samples_leaf', np.arange(3, 16, 3, dtype=int)),
        'random_state':     1,
    }
    tree_para = dict()
    tree_para['reg_params'] = tree_reg_params
    tree_para['pca_params'] = pca_params

    @classmethod
    def getTreeParam(self):
        return HyperParamProvider.tree_para

    rf_reg_params = {
        'n_estimators':     hp.choice('n_estimators',    np.arange(100, 301, 50)),
        'max_depth':        hp.choice('max_depth',        np.arange(3, 26, 2, dtype=int)),
        'min_samples_leaf': hp.choice('min_samples_leaf', np.arange(3, 28, 3, dtype=int)),
        'random_state':     1,
    }
    rf_para = dict()
    rf_para['reg_params'] = rf_reg_params
    rf_para['pca_params'] = pca_params

    @classmethod
    def getRfParam(self):
        return HyperParamProvider.rf_para

    mlp_reg_params = {
        'hidden_layer_sizes':(100,100,100),
        'tol':        hp.uniform('tol', 0.001, 0.002),
        'learning_rate':hp.choice('learning_rate',['invscaling','adaptive']),
        'max_iter':     hp.choice('max_iter',    np.arange(200, 401, 50)),
        'early_stopping':True,
        'random_state':     1,
    }
    mlp_para = dict()
    mlp_para['reg_params'] = mlp_reg_params
    mlp_para['pca_params'] = pca_params

    @classmethod
    def getMlpParam(self):
        return HyperParamProvider.mlp_para

    # GB parameters
    gb_reg_params = {
        'learning_rate':    hp.uniform('learning_rate', 0.01, 0.3),
        'n_estimators':     hp.choice('n_estimators',    np.arange(100, 201, 50)),
        'max_depth':        hp.choice('max_depth',        np.arange(3, 16, 2, dtype=int)),
        'min_samples_leaf': hp.choice('min_samples_leaf', np.arange(3, 16, 3, dtype=int)),
        'max_features':     hp.choice('max_features', [1.0, 0.3, 0.1]),
        'subsample':        hp.uniform('subsample', 0.8, 1),
        'n_iter_no_change':     5,
        'random_state':     1,
    }

    gb_para = dict()
    gb_para['reg_params'] = gb_reg_params
    gb_para['pca_params'] = pca_params

    @classmethod
    def getGbParam(self):
        return HyperParamProvider.gb_para

    # XGB parameters
    xgb_reg_params = {
        'learning_rate':    hp.uniform('learning_rate', 0.01, 0.3),
        'n_estimators':     hp.choice('n_estimators',    np.arange(100, 201, 50)),
        'max_depth':        hp.choice('max_depth',        np.arange(3, 16, 2, dtype=int)),#決定木の深さの最大値
    #    'min_child_samples': hp.choice('min_child_samples', np.arange(20, 41, 10, dtype=int)),
        'min_child_weight': hp.choice('min_child_weight', np.arange(1, 40, 2, dtype=int)),#決定木の葉の重みの下限
        'colsample_bytree': hp.choice('colsample_bytree', np.arange(0.3, 0.8, 0.2)),
        'subsample':        hp.uniform('subsample', 0.9, 1),#ランダムに抽出される標本(データ)の割合
        'gamma': hp.loguniform('gamma', -8, 2),#葉の数に対するペナルティー
        'random_state':     1,
    }
    xgb_para = dict()
    xgb_para['reg_params'] = xgb_reg_params
    xgb_para['pca_params'] = pca_params

    @classmethod
    def getXbgParam(self):
        return HyperParamProvider.xgb_para

    # LightGBM parameters
    lgb_reg_params = {
        'learning_rate':    hp.uniform('learning_rate', 0.01, 0.3),
        'n_estimators':     hp.choice('n_estimators',    np.arange(100, 201, 50)),
        'num_leaves':        hp.choice('num_leaves',        np.arange(25, 51, 5, dtype=int)),
        'max_depth':        hp.choice('max_depth',        np.arange(3, 16, 2, dtype=int)),
    #    'min_child_samples': hp.choice('min_child_samples', np.arange(20, 41, 10, dtype=int)),
        'min_child_weight': hp.choice('min_child_weight', np.arange(1, 40, 2, dtype=int)),
        'colsample_bytree': hp.choice('colsample_bytree', np.arange(0.3, 0.8, 0.2)),
        'subsample':        hp.uniform('subsample', 0.8, 1),
        'objective':        'binary',
        'random_state':     1,
    }
    lgb_para = dict()
    lgb_para['reg_params'] = lgb_reg_params
    lgb_para['pca_params'] = pca_params

    @classmethod
    def getLbgParam(self):
        return HyperParamProvider.lgb_para

    # CatBoost parameters
    ctb_reg_params = {
        'learning_rate':    hp.choice('learning_rate',    np.arange(0.05, 0.31, 0.05)),
        'n_estimators':     hp.choice('n_estimators',    np.arange(100, 201, 50)),
        'max_depth':        hp.choice('max_depth',        np.arange(3, 16, 2, dtype=int)),
        'min_data_in_leaf': hp.choice('min_data_in_leaf', np.arange(1, 40, 2, dtype=int)),
        'colsample_bylevel': hp.choice('colsample_bylevel', np.arange(0.3, 0.8, 0.2)),
        'silent':      True,
        'random_state':     1,
    }
    ctb_para = dict()
    ctb_para['reg_params'] = ctb_reg_params
    ctb_para['pca_params'] = pca_params
        
    @classmethod
    def getCtbParam(self):
        return HyperParamProvider.ctb_para

