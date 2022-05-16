import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
#from sklearn.feature_selection import RFE
from sklearn.feature_selection import RFECV
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split # データセット分割用
import lightgbm as lgb #LightGBM
from IPython.display import display

# 表示列数のオプション変更
pd.options.display.max_columns = 500

class DataOrganizer():

    def __init__(self,targetColumn,indexColumn,unusedColumns):
        #self.categoryColumns=categoryColumns
        self.targetColumn = targetColumn
        self.indexColumn = indexColumn
        self.unusedColumns=unusedColumns

    def main(self,model_data:pd.DataFrame,score_data:pd.DataFrame):
        self._displayData(model_data,score_data)
        model_data,score_data = self._dropUnusedData(model_data,score_data)

        X_model,y_model,X_score,y_score=self._divideData(model_data,score_data)
        X_model,X_score=self._getOneHotEncodedData(X_model,X_score)
        X_model,X_score=self._getImputedData(X_model,X_score)
        X_model,X_score=self._deleteMeaninglessData(X_model,y_model,X_score,y_score)
        
        self._displayLine()
        display('invalance data check')
        self._displayLine()
        display(y_model.value_counts())
        
        # check the shape
        self._displayLine()
        display('X_model shape: (%i,%i)' %X_model.shape)
        display('X_score shape: (%i,%i)' %X_score.shape)
        self._displayLine()
        display('model data')
        display(X_model.join(y_model).head())        

        return X_model,y_model,X_score,y_score

    #有効でない列を削除
    def _deleteMeaninglessData(self,X_model:pd.DataFrame,y_model:pd.DataFrame,X_score:pd.DataFrame,y_score:pd.DataFrame):
        # トレーニングデータ,テストデータの分割
        X_train, X_test, y_train, y_test = train_test_split(X_model, y_model,test_size=0.20, random_state=2)
        
        # 学習に使用するデータを設定
        lgb_train = lgb.Dataset(X_train, y_train)
        lgb_eval = lgb.Dataset(X_test, y_test, reference=lgb_train) 
        
        # LightGBM parameters
        params = {
                'task': 'train',
                'boosting_type': 'gbdt',
                'objective': 'regression', # 目的 : 回帰  
                'metric': {'rmse'}, # 評価指標 : rsme(平均二乗誤差の平方根) 
        }
        
        # モデルの学習
        model = lgb.train(params,
                          train_set=lgb_train, # トレーニングデータの指定
                          valid_sets=lgb_eval, # 検証データの指定
                          )
        
        # 特徴量重要度の算出 (データフレームで取得)
        cols = list(X_test.columns)       # 特徴量名のリスト
        # display(cols)
        # 特徴量重要度の算出方法 'gain'(推奨) : トレーニングデータの損失の減少量を評価
        f_importance = np.array(model.feature_importance(importance_type='gain')) # 特徴量重要度の算出 //
        f_importance = f_importance / np.sum(f_importance) # 正規化(必要ない場合はコメントアウト)
        df_importance = pd.DataFrame({'feature':cols, 'importance':f_importance})
        df_importance = df_importance.sort_values('importance', ascending=False) # 降順ソート
        self._displayLine()
        display('特徴量の有効度')
        self._displayLine()
        display(df_importance)
        # display(df_importance[df_importance['importance'] < 0.000001])
        X_model = X_model.drop(list(set(X_model.columns.values) & set(df_importance[df_importance['importance'] < 0.000001]['feature'])),axis=1)
        X_score = X_score.drop(list(set(X_score.columns.values) & set(df_importance[df_importance['importance'] < 0.000001]['feature'])),axis=1)
        return X_model,X_score

    
    def _dropUnusedData(self,model_data:pd.DataFrame,score_data:pd.DataFrame):
        model_data = model_data.drop(list(set(model_data.columns.values) & set(self.unusedColumns)),axis=1)
        score_data = score_data.drop(list(set(score_data.columns.values) & set(self.unusedColumns)),axis=1)
        return model_data,score_data
        
    def _divideInputData(self,data:pd.DataFrame):
        X:pd.DataFrame = data
        y:pd.DataFrame = data[self.targetColumn]
        #if(len(self.indexColumn)>0 and self.indexColumn in X.columns):
        #    X = X.drop(self.indexColumn,axis=1)
        X = X.drop(self.targetColumn,axis=1)
        return X, y

    def _displayLine(self):
        display('--------------------------------------------------')

    def _getOneHotEncodedData(self,X_model:pd.DataFrame,X_score:pd.DataFrame):
        display('start _getOneHotEncodedData')
        self._displayLine()
        display('スコア側の項目の情報')
        self._displayLine()
        display(X_score.info())

        self._displayLine()
        display('X_score before one hot encode')
        self._displayLine()
        display(X_score)

        #One hot encode
        #Object型の列を全てエンコード
        #X_model = pd.get_dummies(X_model,dummy_na=True,columns=list(self.categoryColumns))
        X_model:pd.DataFrame = pd.get_dummies(X_model,dummy_na=True,columns=X_model.select_dtypes(include=object).columns.values)
        #X_score = pd.get_dummies(X_score,dummy_na=True,columns=list(self.categoryColumns))
        X_score:pd.DataFrame = pd.get_dummies(X_score,dummy_na=True,columns=X_score.select_dtypes(include=object).columns.values)

        #One hot encodeによる列の差異の対応
        cols_model = set(X_model.columns.values)
        cols_score = set(X_score.columns.values)

        modelCol = cols_model - cols_score
        display('モデルのみに存在する項目: %s' % modelCol)

        scoreCol = cols_score - cols_model
        display('スコアのみに存在する項目: %s' % scoreCol)

        #モデルデータの列調整
        df_cols_m = pd.DataFrame(None,columns=X_model.columns.values,dtype=np.float64)
        
        #モデル側のみに存在する項目をスコア側に追加
        X_score = pd.concat([X_score,df_cols_m])
        
        #追加した列に0埋め
        X_score.loc[:,list(cols_model-cols_score)] = X_score.loc[:,list(cols_model-cols_score)].fillna(0,axis=1)

        #スコア側のみに存在する項目をスコア側から削除
        X_score = X_score.drop(list(cols_score - cols_model),axis=1)
        
        #スコア側データの列順をモデル側にあわせる
        X_score = X_score.reindex(X_model.columns.values, axis=1)

        #数値データ列のデータ型をfloatで揃えるため
        X_model = pd.concat([X_model,df_cols_m])    

        self._displayLine()
        display('X_model after one hot encode')
        self._displayLine()
        display(X_model)
        display(X_model.info())
        display(X_model.dtypes)
        display(X_model.describe())

        self._displayLine()
        display('X_score after one hot encode')
        self._displayLine()
        display(X_score)
        display(X_score.info())
        display(X_score.dtypes)
        showDetailVal=False
        if showDetailVal:
            for val in X_score.columns:
                display(type(val))
                display(val)
        display(X_score.describe())

        return X_model,X_score

    #欠損値の対応
    def _getImputedData(self,X_model:pd.DataFrame,X_score:pd.DataFrame):
        display('start _getImputedData')
        imp = SimpleImputer()
        #imp.fit(X_model)
        display('start Impute')
        display(X_model.head())
        X_modelResult:pd.DataFrame=None
        X_scoreResult:pd.DataFrame=None
        tempColumns=[]
        #X_model = pd.DataFrame(imp.transform(X_model),index=X_model.index.values.tolist())
        for i,targetColumn in enumerate(X_model.columns.values):
            tempColumns.append(targetColumn)
            if not ((i+1) % 1000 !=0 and (i+1)!=len(X_model.columns.values)) :#1000列づつ処理
                X_modelTemp = X_model[tempColumns]
                X_scoreTemp = X_score[tempColumns]
                imp.fit(X_modelTemp)
                X_modelTemp = pd.DataFrame(imp.transform(X_modelTemp),columns=tempColumns,index=X_model.index.values.tolist())
                X_scoreTemp = pd.DataFrame(imp.transform(X_scoreTemp),columns=tempColumns,index=X_score.index.values.tolist())
                if X_modelResult is None:
                    X_modelResult=X_modelTemp
                    X_scoreResult=X_scoreTemp
                else:
                    X_modelResult=pd.concat((X_modelResult,X_modelTemp),axis=1)
                    X_scoreResult=pd.concat((X_scoreResult,X_scoreTemp),axis=1)
                    #X_modelResult[targetColumn] = X_modelTemp[targetColumn]
                    #X_scoreResult[targetColumn] = X_scoreTemp[targetColumn]
                    #X_modelResult=pd.merge(X_modelResult, X_modelTemp, on=X_model.index.name, how="inner")
                    #X_scoreResult=pd.merge(X_scoreResult, X_scoreTemp, on=X_score.index.name, how="inner")
                tempColumns=[]
        cols_model = set(X_model.columns.values)
        cols_result = set(X_modelResult.columns.values)

        lackCol = cols_model - cols_result
        display('減ってしまった項目: %s' % lackCol)

        print("X_model column count:"+str(len(X_model.columns.values)))
        print("X_modelResult column count:"+str(len(X_modelResult.columns.values)))
        X_model = X_modelResult
        X_score = X_scoreResult
        #X_model = pd.DataFrame(imp.transform(X_model),columns=X_model.columns.values,index=X_model.index.values.tolist())
        #X_score = pd.DataFrame(imp.transform(X_score),columns=X_model.columns.values,index=X_score.index.values.tolist())
        return X_model,X_score

    #データを確認
    def _displayData(self,model_data:pd.DataFrame,score_data:pd.DataFrame):
        self._displayLine()
        display('train data')
        self._displayLine()
        display(model_data.head())
        self._displayLine()
        display('score data')
        self._displayLine()
        display(score_data.head())

    #データを説明変数と目的変数に分割
    def _divideData(self,model_data:pd.DataFrame,score_data:pd.DataFrame):
        X_model,y_model=self._divideInputData(model_data)
        X_score,y_score=self._divideInputData(score_data)
        return X_model,y_model,X_score,y_score
