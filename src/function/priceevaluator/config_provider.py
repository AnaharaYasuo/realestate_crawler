from configparser import SafeConfigParser

class ConfigProvider():
    def __init__(self,filePath:str, encoding:str=None):
        self.config:SafeConfigParser = SafeConfigParser()
        self.config.read(filePath,encoding)

    def get(self,section, key):
        return self.config.get(section, key)