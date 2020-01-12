# DRFVG
Automate your views creation and url routing with DRFVG (Django Rest Framework View Generator).

## Features
- auto generated serializers for django models (relations included🤟)
- auto generated django rest framework class based views
  - get, post methods for list view
  - get, put, patch, delete methods for detail view
- auto generated authentication system
- auto generated api home view, app home view, model home view

**All you have to do is to create your models. 🤝 That's all**

## Setup
- copy `drfvg.py` to your project directory (`BASE_DIR`).
- add `rest_framework` to your `INSTALLED_APPS` in `settings.py`
- add `static/html` to your template dirs `os.path.join(BASE_DIR, 'static/html')`

## Usage
register apps in `urls.py`
```python
from drfvg import register_apps
urlpatterns = [
    path('admin/', admin.site.urls),
] + register_apps( ['app1', 'app2'] )
```
register models in `BASE_DIR/app/urls.py`
```python
from django.urls import path
from .models import Model1, Model2
from drfvg import register_models
urlpatterns = [
    ## your paths
] + register_models( [Model1, Model2] )
```