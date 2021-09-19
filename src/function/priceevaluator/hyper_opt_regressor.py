import numpy as np
from hyperopt import fmin, tpe, STATUS_OK, STATUS_FAIL, Trials

# 分類モデルの評価指標計算のための関数の読込
#from sklearn.metrics import accuracy_score
#from sklearn.metrics import precision_score
#from sklearn.metrics import recall_score
#from sklearn.metrics import f1_score

from sklearn.model_selection import cross_validate
#from sklearn.model_selection import cross_val_predict
from sklearn.model_selection import train_test_split
from sklearn.decomposition import PCA
#from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor

from sklearn.base import RegressorMixin
from sklearn.ensemble import BaseEnsemble
import traceback

from abc import ABCMeta
from IPython.display import display
class HyperOptRegressor(RegressorMixin, BaseEnsemble, metaclass=ABCMeta):

    def __init__(self):
        display("start HyperOptRegressor init")
        self.est_=None
                
    def _train(self,params):
        display("start HyperOptRegressor train")
        display("HyperOptRegressor train params")
        display(params)
        try:
            X = params["X"]
            columnOptimizer=params["columnOptimizer"]
            #X=columnOptimizer.getDataFeaturesSelected(X,params["min_features_to_select"])
            cls=params["cls"]
            cls_params=params["cls_params"]
            display("_train cls",cls)
            display("_train cls_params",cls_params)
            est = cls(**cls_params)
            evaluator = params["eva"]
            loss=evaluator.getLossValue(est, X, params["y"])
            display("train loss is " + str(loss))
            return {'loss': loss, 'status': STATUS_OK, 'est':est}
        except Exception as e: 
            display('train error')
            display(traceback.format_exc())
            #raise e
            return {'status': STATUS_FAIL,
                    'exception': str(e)}

    def fit(self, X, y, cls, eva, params, columnOptimizer, min_features_to_select, trials=Trials(), algo=tpe.suggest, max_evals=1):
        display("start HyperOptRegressor fit")
        if (cls=="RandomForestRegressor"):
            cls=RandomForestRegressor
        elif (cls=="GradientBoostingRegressor"):
            cls=GradientBoostingRegressor

        self.REFResult_={}
        loss=float('inf')
        space = dict()
        space["cls_params"]=params
        space["columnOptimizer"]=columnOptimizer
        space["min_features_to_select"]=min_features_to_select[0]
        space["eva"]=eva
        space["X"]=X
        space["y"]=y
        space["cls"]=cls
        display("space")
        display(space)
        try:
            display('start fmin')
            self.est_ = None
            result = fmin(fn=self._train, space=space, algo=algo, max_evals=max_evals, trials=trials, rstate=np.random.RandomState(0))
            for item in trials.trials:
                vals = item['misc']['vals']
                result = item['result']
                if ("loss" in result.keys() and loss > result["loss"]):
                    loss = result["loss"]
                    self.est_= result["est"]
                    self.est_.fit(X,y)
                    #display('check by train data in optimizer')
                    #display(accuracy_score(y, self.est_.predict(X)))

            display('finish fmin')
        except Exception as e: 
            display('fmin error')
            display(traceback.format_exc())
            raise e

        #チューニング済のパラメータでトレーニング
        try:
            self.est_.fit(X,y)
        except Exception as e: 
            display('fit error')
            display(traceback.format_exc())
            raise e

    def predict(self, X):
        display("start HyperOptRegressor predict")
        return self.est_.predict(X)

    def predict_proba(self, X):
        display("start HyperOptRegressor predict_proba")
        return self.est_.predict_proba(X)

    def transform(self, X):
        if hasattr(self.est_, "transform"):
            return self.est_.transform(X)
        return X
    
    def getEst(self):
        return self.est_
