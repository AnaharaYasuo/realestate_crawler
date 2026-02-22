
from django.db import models
class Dummy(models.Model):
    name = models.TextField()
    class Meta:
        app_label = 'package'
