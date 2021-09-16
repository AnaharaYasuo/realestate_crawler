class ColumnOptimizer():
    def __init__(self,X,y):
        display("start ColumnOptimizer init")
        self.X=X
        self.y=y
        self.cashSelector={}
        
    def getDataFeaturesSelected(self,X,min_features_to_select):
        try:
            if((len(self.cashSelector)>0)
               and (min_features_to_select in self.cashSelector.keys())
               and (self.cashSelector[min_features_to_select] is not None)):
                selector=self.cashSelector[min_features_to_select]
            else:
                selector = RFECV(estimator=RandomForestClassifier(n_estimators=100,random_state=1),
                                 min_features_to_select=min_features_to_select, step=.05)
                selector.fit(self.X,self.y)
                self.cashSelector[min_features_to_select]=selector
            X = selector.transform(X)
            return X
        except Exception as e: 
            display('getDataFeaturesSelected error')
            display(str(e))
            raise e
