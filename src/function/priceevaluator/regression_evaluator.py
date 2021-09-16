from ipywidgets import interact,interactive,fixed,interact_manual
from IPython.display import display
import ipywidgets as widgets
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_validate

class RegressionEvaluator():
    def __init__(self):
        self.evaluation_index_params = {
            'rmse':     'RMSE',#もっとも一般的
            'mae':     'MAE',#外れ値の影響はさほど大きくない
            'mse':     'MSE',#外れ値の影響が大きい
            'r2':     'R2',#直線的な比例関係のみあらわせる。外れ値の影響を強く受ける場合がある。
        }
        #self.cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=1) #分類向け
        self.cv = KFold(n_splits=3, shuffle=True, random_state=1) #回帰向け
        self.score_funcs = [
            'neg_root_mean_squared_error'
            ,'neg_mean_absolute_error'
            ,'neg_mean_squared_error'
            ,'r2'
        ]

    def showEvaluationRadioButtons(self):
        self.answer = widgets.RadioButtons(options=list(self.evaluation_index_params.values()))
        display(self.answer)
                 
    def getSelectedEvaluationIndexValue(self):
        return self.answer.value
    
    def getSelectedEvaluationIndexKey(self):
        evaluation_index_keys = [k for k, v in self.evaluation_index_params.items() if v == self.answer.value]
        return evaluation_index_keys[0]

    def getSelectedCrossvalidateResultName(self):
        colName=""
        if self.getSelectedEvaluationIndexKey()=='rmse':
            colName= 'test_neg_root_mean_squared_error'
        elif self.getSelectedEvaluationIndexKey()=='mae':
            colName= 'test_neg_mean_absolute_error'
        elif self.getSelectedEvaluationIndexKey()=='mse':
            colName= 'test_neg_mean_squared_error'
        elif self.getSelectedEvaluationIndexKey()=='r2':
            colName= 'test_r2'
        return colName
    
    def getSelectedCrossvalidateResultMeanValue(self,cross_validate_scores):
        value=""
        if self.getSelectedEvaluationIndexKey()=='rmse':
            value= cross_validate_scores['test_neg_root_mean_squared_error'].mean()#cross_validateからはマイナス符号とともに値で出力されるので(高い程良く、低い程悪い、とするため)
        elif self.getSelectedEvaluationIndexKey()=='mae':
            value= cross_validate_scores['test_neg_mean_absolute_error'].mean()
        elif self.getSelectedEvaluationIndexKey()=='mse':
            value= cross_validate_scores['test_neg_mean_squared_error'].mean()
        elif self.getSelectedEvaluationIndexKey()=='r2':
            value= cross_validate_scores['test_r2'].mean()
        return value
    
    def getLossValue(self,est, X, y):        
            display("Evaluation cross_validate start")
            cross_validate_scores = cross_validate(estimator=est
                                                   , X=X
                                                   , y=y
                                                   , cv=self.cv
                                                   , scoring=self.score_funcs)
            display("Evaluation cross_validate done")

            display("Evaluate cross_validate_scores")
            display(cross_validate_scores)
            display("target evaluation index is " + self.getSelectedEvaluationIndexValue())
            
            value= self.getSelectedCrossvalidateResultMeanValue(cross_validate_scores)
            
            if self.getSelectedEvaluationIndexKey()=='rmse':
                loss= -value#cross_validateからはマイナス符号とともに値で出力されるので(高い程良く、低い程悪い、とするため)
            elif self.getSelectedEvaluationIndexKey()=='mae':
                loss= -value
            elif self.getSelectedEvaluationIndexKey()=='mse':
                loss= -value
            elif self.getSelectedEvaluationIndexKey()=='r2':
                loss= 1-value
            return loss
