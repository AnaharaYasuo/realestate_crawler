#ハイパーパラメータ
from hyperopt import hp
from hyperopt import fmin
from hyperopt import tpe
import numpy as np

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

logistic_reg_params = {
    'tol':        hp.uniform('tol', 0.00001, 0.0001),
#    'C':        hp.uniform('C', 1, 1000),
    'max_iter':     hp.choice('max_iter',    np.arange(50, 151, 50)),
    'random_state':     1,
}
logistic_para = dict()
logistic_para['reg_params'] = logistic_reg_params
logistic_para['pca_params'] = pca_params

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

tree_reg_params = {
    'max_depth':        hp.choice('max_depth',        np.arange(3, 16, 2, dtype=int)),
    'min_samples_leaf': hp.choice('min_samples_leaf', np.arange(3, 16, 3, dtype=int)),
    'random_state':     1,
}
tree_para = dict()
tree_para['reg_params'] = tree_reg_params
tree_para['pca_params'] = pca_params

rf_reg_params = {
    'n_estimators':     hp.choice('n_estimators',    np.arange(100, 301, 50)),
    'max_depth':        hp.choice('max_depth',        np.arange(3, 26, 2, dtype=int)),
    'min_samples_leaf': hp.choice('min_samples_leaf', np.arange(3, 28, 3, dtype=int)),
    'random_state':     1,
}
rf_para = dict()
rf_para['reg_params'] = rf_reg_params
rf_para['pca_params'] = pca_params

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


# データ別の設定
indexColumn="pageUrl"
targetColumn="minPrice_p_heibei"
#unusedColumns=['minPrice','maxPrice','minInputDate','maxInputDate','hikiwatashi','kanriKaisya','propertyName','address','transfer1','transfer2','railway2','station2','railwayWalkMinute2','busStation2','busWalkMinute2','transfer3','railway3','station3','railwayWalkMinute3','busStation3','busWalkMinute3','transfer4','railway4','station4','railwayWalkMinute4','busStation4','busWalkMinute4','transfer5','railway5','station5','railwayWalkMinute5','busStation5','busWalkMinute5','kanriKeitaiKaisya'
#              ,'station1','menseki','yakan_total','yakan_total_p_area','chukan_total','chukan_total_p_area','jigyousyo_all_unk','jigyousyo_all','jyuugyou_all','jyuugyou_all_man','jyuugyou_all_woman','jig_all_unk_mitsudo','jig_all_mitsudo','jyuugyou_all_mitsu'
#              ,'nouzei_person_sum','syotoku_sum','syotoku_sum_p_area','syotoku_sum_p_person','chouki_jouto','chouki_jouto_p_person','tanki_jouto','tanki_jouto_p_person','kabu_ippan_jouto','kabu_ippan_jouto_p_person','kabu_jojo_jouto','kabu_jojo_jouto_p_person','kabu_jojo_haito','kabu_jojo_haito_p_person','sakimono','sakimono_p_person','kazei_taisyou','kazei_taisyou_p_person','kazei_hyojyun','kazei_hyojyun_p_person','syotoku_wari','syotoku_wari_p_person'
#              ,'JINKO_dtl','SETAI_dtl','busStation1','madori']
unusedColumns=['genkyo','minPrice','maxPrice','minInputDate','maxInputDate','propertyName','address','busStation1','busStation2','busStation3','busStation4','busStation5','busWalkMinute2','busWalkMinute3','busWalkMinute4','busWalkMinute5'
              ,'nouzei_person_sum','syotoku_sum','syotoku_sum_p_area','chouki_jouto','tanki_jouto','kabu_ippan_jouto','kabu_jojo_haito','sakimono','kazei_taisyou','kazei_hyojyun','syotoku_wari'
              ,'railway2','railway3','railway4','railway5','railwayWalkMinute2','railwayWalkMinute3','railwayWalkMinute4','railwayWalkMinute5','station2','station3','station4','station5','transfer1','transfer2','transfer3','transfer4','transfer5']#リーク＆クラッシュするので
categoryColumns=[]
min_features_to_select=[10,15,20]
import os
modelFilePath="/content/drive/My Drive/不動産分析/分析用データ/propertyAnalizeData.csv"
if not os.path.exists(modelFilePath):
    modelFilePath="D:/Users/anaharayasuo/Google ドライブ/不動産分析/分析用データ/propertyAnalizeData.csv"
#scoreFilePath="./data/final_hr_analysis_test.csv"
scoreFilePath=modelFilePath

import regression_evaluator as reg

eva = reg.RegressionEvaluator() 
from ipywidgets import interact,interactive,fixed,interact_manual
from IPython.display import display
import ipywidgets as widgets
eva.showEvaluationRadioButtons()

import pandas as pd
import data_organizer as do

#データの読み込み
category_dtype={}
for i in categoryColumns:
    category_dtype[i]=object

model_data= pd.read_csv(modelFilePath,dtype=category_dtype,index_col=indexColumn,engine='python', sep='\t')
score_data= pd.read_csv(scoreFilePath,dtype=category_dtype,index_col=indexColumn,engine='python', sep='\t')

dataOrganizer = do.DataOrganizer(categoryColumns,targetColumn,indexColumn,unusedColumns)
X_model,y_model,X_score,y_score=dataOrganizer.main(model_data,score_data)

from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from hyperopt import fmin, tpe, STATUS_OK, STATUS_FAIL, Trials
import column_optimizer as co
import estimate_ranking_maker as erm

#実行用
estParam={
    'xgb':{'param':xgb_para,'est':XGBRegressor,"trials":Trials()}
#    ,'rf':{'param':rf_para,'est':"RandomForestRegressor","trials":Trials()}
#    ,'mlp':{'param':mlp_para,'est':MLPRegressor,"trials":Trials()}
#    ,'lgb':{'param':lgb_para,'est':LGBMRegressor,"trials":Trials()}
#    ,'gb':{'param':gb_para,'est':"GradientBoostingRegressor","trials":Trials()}#遅いので除外
#    ,'ctb':{'param':ctb_para,'est':CatBoostClassifier,"trials":Trials()}#処理がものすごく遅い
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

fn_name="best_model.pickle"
with open(fn_name, 'wb') as f:
    pickle.dump(est, f, pickle.HIGHEST_PROTOCOL)
#!cp "best_model.pickle" "/content/drive/My Drive/不動産分析/分析用データ/best_model.pickle"

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
filename =  "property_analize_result.csv"
resultFolderPath="/content/drive/My Drive/不動産分析/分析用データ/"
localResultFolderPath="D:/Users/anaharayasuo/Google ドライブ/不動産分析/分析用データ/"
resultFilePath=localResultFolderPath+filename
if os.path.exists(resultFolderPath):
    resultFilePath=resultFolderPath + filename
df2.to_csv(resultFilePath, encoding = 'utf-8-sig') 
#!ls
#!cp "property_analize_result.csv" "/content/drive/My Drive/不動産分析/分析用データ/property_analize_result.csv"
#files.download(filename)