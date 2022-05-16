#from sklearn.neighbors import KNeighborsClassifier
#from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
#from sklearn.svm import SVC, LinearSVC
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import KFold

import pickle

#from hpsklearn import HyperoptEstimator, any_classifier
#from hpsklearn import HyperoptEstimator
from sklearn.preprocessing import OneHotEncoder

import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
import matplotlib.pyplot as plt
import japanize_matplotlib #日本語化matplotlib
from sklearn.model_selection import cross_val_predict
from hyperopt import hp
from IPython.display import display

class EstimateRankingMaker():
    def __displayFeatureImportance(self,est,X):       
        display("start __displayFeatureImportance")
        if (type(est)==RandomForestRegressor):
            #特徴量毎の重要性を可視化
            print('Feature Importances:')
            fi = est.feature_importances_
            fiMap={}

            for i, feat in enumerate(X.columns.values):
                if (fi[i]>0):
                    fiMap[feat]=fi[i]                            

            plotX=[]
            plotY=[]
            for k, v in sorted(fiMap.items(), reverse=True, key=lambda x:x[1]):
                if (len(plotX)<=20):
                    plotX.append(k)
                    plotY.append(v)
                display('\t{0:10s} : {1:>.6f}'.format(k, v))
            x_position = np.arange(len(plotX))

            fig = plt.figure(figsize=(20,20),dpi=200)
            ax = fig.add_subplot(1, 1, 1)
            #ax.bar(x_position, plotY, tick_label=plotX)
            ax.barh(x_position, plotY, tick_label=plotX)#横棒グラフ
            for label in ax.get_xticklabels():
                #label.set_fontproperties("MS Gothic")
                label.set_fontproperties("IPAexGothic")
            for label in ax.get_yticklabels():
                #label.set_fontproperties("MS Gothic")
                label.set_fontproperties("IPAexGothic")
            ax.set_xticklabels(ax.get_xticklabels(),fontsize=20)
            ax.set_yticklabels(ax.get_yticklabels(),fontsize=20)
            ax.set_xlabel('feature importance')
            ax.set_ylabel('features')

    def __displayEstimateResult(self,est,X,y):
        display("start __displayEstimateResult")
        predicted = cross_val_predict(est, X, y, cv=5)

        fig = plt.figure(figsize=(10,10),dpi=40)
        ax = fig.add_subplot(1, 1, 1)
        ax.scatter(y, predicted, edgecolors=(0, 0, 0))
        ax.plot([y.min(), y.max()], [y.min(), y.max()], 'k--', lw=4)
        ax.set_xlabel('Measured')
        ax.set_ylabel('Predicted')
        fig
        #plt.show()
        

    def getRanking(self,X,y,estParam,max_evals,evaluator,columnOptimizer,min_features_to_select):       
        scores=dict()
        ests=dict()
        #cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=1)#分類
        cv=KFold(n_splits=3, shuffle=True, random_state=1)#回帰
        for fn_name in estParam:
            display("==================================","start:" + fn_name,"==================================")
            pipeline=Pipeline([
                ('scl',StandardScaler())
                ,('est',HyperOptRegressor())
            ])

            cls=estParam[fn_name]["est"]
            display("min_features_to_select")
            trials=estParam[fn_name]["trials"]
            params=estParam[fn_name]["param"]["reg_params"]
            fit_params={"est__cls":cls
                        ,"est__eva":evaluator
                        ,"est__params":params
                        ,"est__columnOptimizer":columnOptimizer
                        ,"est__min_features_to_select":[hp.choice('min_features_to_select',min_features_to_select)]#配列にしないとcross_validateのチェックに引っかかる
                        ,"est__trials":trials
                        ,"est__max_evals":max_evals}
            try:
                #pipeline.fit(X,y,**fit_params)
                # Cross Validation で検証する
                display('start cross validate')
                #5回テストが実施されるがTrialsが共有される＆同じパラメータが投げられるので_trainは一度だけ。
                cross_validate_scores = cross_validate(estimator=pipeline
                                                       , X=X
                                                       , y=y
                                                       , fit_params=fit_params
                                                       , cv=cv
                                                       , scoring=evaluator.score_funcs
                                                       , return_train_score=True
                                                       , return_estimator=True
                                                       )
                display('cross validate Done')
                pipe=cross_validate_scores["estimator"][0]
                hyperOptRegressor:HyperOptRegressor=pipe["est"]
                est=hyperOptRegressor.getEst()
                ests[fn_name]={'pipe' : pipe, 'est' : est,' fit_params' : fit_params}
                
                display('check by train data')
                display(X)
                est.fit(X,y)
                #self.__displayFeatureImportance(est,X)
                #self.__displayEstimateResult(est,X,y)
                #accuracyitem
                scores[(fn_name,'test_neg_root_mean_squared_error')] = cross_validate_scores['test_neg_root_mean_squared_error'].mean()
                scores[(fn_name,'test_neg_mean_absolute_error')] = cross_validate_scores['test_neg_mean_absolute_error'].mean()
                scores[(fn_name,'test_neg_mean_squared_error')] = cross_validate_scores['test_neg_mean_squared_error'].mean()
                scores[(fn_name,'test_r2')] = cross_validate_scores['test_r2'].mean()
                with open(fn_name, 'wb') as f:
                    # Pickle the 'data' dictionary using the highest protocol available.
                    pickle.dump(est, f, pickle.HIGHEST_PROTOCOL)
            except Exception as e: 
                display('fit error')
                display(traceback.format_exc())
                #raise e
        
        sortColName= evaluator.getSelectedCrossvalidateResultName()
        display(pd.Series(scores))
        rankResultDf=pd.Series(scores).unstack()
        rankResultDf=rankResultDf.sort_values([sortColName], ascending=False)#unstack 行から列へピボット
        self.bestEstName=rankResultDf.index.values.tolist()[0]
        return ests,rankResultDf 

    def getBestModel(self):
        with open(self.bestEstName, 'rb') as file:
            est = pickle.load(file)
            return est    

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
