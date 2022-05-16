import os
import sys
from unittest import case
#from hyperopt import hp
#from hyperopt import fmin
#from hyperopt import tpe
import numpy as np
import pandas as pd
from config_provider import ConfigProvider
import json
from hyper_param_provider import HyperParamProvider

import regression_evaluator as reg
#from ipywidgets import interact,interactive,fixed,interact_manual
from IPython.display import display
#import ipywidgets as widgets

import data_organizer as do


# 分析データ別の設定
confFilePath:str="./config/option.ini"
confSection:str="MANSION"
args: list[str] = sys.argv
if 2 <= len(args):
    sectionValue:str=args[1]

    if sectionValue=="TOCHI":
        confSection=sectionValue


conf:ConfigProvider=ConfigProvider(confFilePath,"utf-8")
indexColumn=conf.get(confSection,"indexColumn")
targetColumn=conf.get(confSection,"targetColumn")
unusedColumns=json.loads(conf.get(confSection,"unusedColumns"))
modelFilePath=conf.get(confSection,"modelFilePathGdrive")
if not os.path.exists(modelFilePath):
    modelFilePath=conf.get(confSection,"modelFilePathLocal")
resultFileName = conf.get(confSection,"resultFileName")
resultFolderPath=conf.get(confSection,"resultFolderPathGdrive")
resultFolderPathLocal=conf.get(confSection,"resultFolderPathLocal")
pickleFileName=conf.get(confSection,"pickleFileName")

resultFilePath=resultFolderPathLocal+resultFileName
pickleFilePath=resultFolderPathLocal+pickleFileName
if os.path.exists(resultFolderPath):
    resultFilePath=resultFolderPath + resultFileName
    pickleFilePath=resultFolderPath + pickleFileName

scoreFilePath=modelFilePath

categoryColumns=[]
min_features_to_select=json.loads(conf.get(confSection,"minFeaturesToSelect"))#考慮すべき特徴量の最小値

eva:reg.RegressionEvaluator = reg.RegressionEvaluator() 
eva.showEvaluationRadioButtons()


#データの読み込み
category_dtype={}
for i in categoryColumns:
    category_dtype[i]=object

model_data= pd.read_csv(modelFilePath,dtype=category_dtype,index_col=indexColumn,engine='python', sep='\t')
score_data= pd.read_csv(scoreFilePath,dtype=category_dtype,index_col=indexColumn,engine='python', sep='\t')

dataOrganizer:do.DataOrganizer = do.DataOrganizer(targetColumn,indexColumn,unusedColumns)
X_model,y_model,X_score,y_score=dataOrganizer.main(model_data,score_data)

from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from hyperopt import fmin, tpe, STATUS_OK, STATUS_FAIL, Trials
import column_optimizer as co
import estimate_ranking_maker as erm

#実行用
estParam={
    'xgb':{'param':HyperParamProvider.getXbgParam(),'est':XGBRegressor,"trials":Trials()}
#    ,'rf':{'param':HyperParamProvider.getRf_para(),'est':"RandomForestRegressor","trials":Trials()}
#    ,'mlp':{'param':HyperParamProvider.getMlp_para(),'est':MLPRegressor,"trials":Trials()}
#    ,'lgb':{'param':HyperParamProvider.getLgb_para(),'est':LGBMRegressor,"trials":Trials()}
#    ,'gb':{'param':HyperParamProvider.getGb_para(),'est':"GradientBoostingRegressor","trials":Trials()}#遅いので除外
#    ,'ctb':{'param':HyperParamProvider.getCtb_para(),'est':CatBoostClassifier,"trials":Trials()}#処理がものすごく遅い
}
columnOptimizer = co.ColumnOptimizer(X_model,y_model)
estimateRankingMaker = erm.EstimateRankingMaker()
#モデルの絞り込み(1回目)
max_evals=1
ests,rankResultDf = estimateRankingMaker.getRanking(X=X_model
                                                    ,y=y_model
                                                    ,estParam=estParam
                                                    ,max_evals=max_evals
                                                    ,evaluator=eva
                                                    ,columnOptimizer=columnOptimizer
                                                    ,min_features_to_select=min_features_to_select
                                                   )
display(rankResultDf)
estParam2={}
for i, estName in enumerate(rankResultDf.index.values.tolist()):
    if(i<6):#上位6モデルのみピックアップ
        estParam2[estName]=estParam[estName]
        
#モデルの絞り込み(2回目)
max_evals=5
ests,rankResultDf = estimateRankingMaker.getRanking(X=X_model
                                                    ,y=y_model
                                                    ,estParam=estParam2
                                                    ,max_evals=max_evals
                                                    ,evaluator=eva
                                                    ,columnOptimizer=columnOptimizer
                                                    ,min_features_to_select=min_features_to_select
                                                   )
display(rankResultDf)
estParam3={}
for i, estName in enumerate(rankResultDf.index.values.tolist()):
    if(i<4):#上位4モデルのみピックアップ
        estParam3[estName]=estParam[estName]


import pandas_profiling as pdp
import seaborn as sns # pip install seaborn
import pickle
pd.options.display.max_columns = 500
pd.options.display.max_rows=2

y_predname=y_score.name + "_pred"
est=estimateRankingMaker.getBestModel()

with open(pickleFilePath, 'wb') as f:
    pickle.dump(est, f, pickle.HIGHEST_PROTOCOL)

#y_pred=est.predict(X_score.drop("railwayCount", axis=1))
y_pred=est.predict(X_score)
y_pred = pd.Series(y_pred, index=y_score.index,name=y_predname)
df = model_data.join(y_pred)
display(df)

df_kasyo=df[df[y_score.name] > df[y_predname]]
#display("df_kasyo")
#display(df_kasyo)
#display(df_kasyo.describe())
#sns.pairplot(data=df_kasyo, kind='reg')

df_kadai=df[df[y_score.name] < df[y_predname]]
#display("df_kadai")
#display(df_kadai)
#display(df_kadai.describe())
#sns.pairplot(data=df_kadai, kind='reg')

np.savetxt('predict.csv',y_pred,delimiter=',', fmt=["%.0f"])
#fig

#predictProbaData=est.predict_proba(X_score)
#display(predictProbaData)
#np.savetxt('predict_proba.csv',predictProbaData,delimiter=',')
#np.savetxt('predict_proba_0.csv',predictProbaData[:,0],delimiter=',')
#np.savetxt('predict_proba_1.csv',predictProbaData[:,1],delimiter=',')
#np.savetxt('aijc1000.csv',predictProbaData[:,1],delimiter=',')

#display(accuracy_score(y_model, est.predict(X_model)))

#from google.colab import files
predict_rate=pd.Series(data=df[y_predname]/df[y_score.name],index=df.index,name="predict_rate")
df2 = df.join(predict_rate)
cols = df2.columns.tolist()
cols = cols[-1:] + cols[:-1]
df2 = df2[cols]
display(df2)
df2.to_csv(resultFilePath, encoding = 'utf-8-sig') 
