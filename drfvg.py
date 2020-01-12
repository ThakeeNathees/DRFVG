
LOGIN_PATH_NAME  = 'api-login'  # 'admin:login'
LOGOUT_PATH_NAME = 'api-logout' # 'admin:logout'
LOGIN_URL        = 'api-login/'
LOGOUT_URL       = 'api-logout/'
HOME_PAGE_NAME   = 'home-page'
API_TITLE        = 'DRFVG'
DEFAULT_OBJECT_COUNT = 10

import os

from django.contrib.auth.models import auth
from django.contrib.auth import authenticate
from django.urls import path, include
from django.shortcuts import render, reverse
from django.http import JsonResponse
from django.http.response import FileResponse
from django.db import models
from django.db.models.fields.files import File
from django import forms

from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import UpdateAPIView, ListCreateAPIView
from rest_framework import serializers

## @login_required decorator
from django.shortcuts import render, reverse, redirect
from rest_framework.request import Request
from django.core.handlers.wsgi import WSGIRequest
def login_required(handler):
    ## if class based view Request object in args, else args[0] is request
    def wrapper(*args, **kwargs):
        if len(args) < 1 : raise Exception('handler at lease have request argument -- no args found')
        request = None
        for arg in args:
            if type(arg) == Request or type(arg) == WSGIRequest:
                request = arg ; break
        else:
            raise Exception('no django rest framework request found')
        if request.user.is_authenticated:
            return handler(*args, **kwargs)
        else :
            return redirect(reverse(LOGIN_PATH_NAME))
    return wrapper

def register_apps(app_registry):

    @login_required
    def home_page_response(request):
        app_urls = []
        for app_name in app_registry:
            app_urls.append(UrlRenderCtx(app_name, reverse('%s-home'%app_name)))
        return generate_ulr_page_response(request, app_urls, API_TITLE)

    urlpatterns = [
        path(LOGIN_URL,  login,  name=LOGIN_PATH_NAME),
        path(LOGOUT_URL, logout, name=LOGOUT_PATH_NAME),
    ]
    for app_name in app_registry:
        urlpatterns.append(path( '%s/'%app_name, include('%s.urls'%app_name) ))

    urlpatterns.append(path('', home_page_response, name=HOME_PAGE_NAME))
    return urlpatterns


## returns the url patterns for the models to be registered
def register_models(model_registry, app_name=None):
    urlpatterns = []
    for Model in model_registry:
        app_name = Model._meta.app_label

        model_name_s    = Model._meta.verbose_name
        model_name_p    = Model._meta.verbose_name_plural 

        ## default url patterns
        model_page      = '%s/'%model_name_p
        page_url_name   = getPageUrlName(Model)

        model_list      = '%s/list/'%model_name_p
        list_url_name   = getListUrlName(Model)

        model_detail    = '%s/<int:pk>/'%model_name_s
        detail_url_name = getDetailUrlName(Model)
        
        urlpatterns += [
            path(model_page ,  ObjectHomeResponse(Model),   name=page_url_name),
            path(model_list,   make_list_view_class(Model).as_view(),   name=list_url_name),
            path(model_detail, make_detail_view_class(Model).as_view(), name=detail_url_name),
        ]
    if app_name == None:
        raise Exception('app_name gethered from Model._meta.app_label, no model was provided. use app_name keyword argument')
    urlpatterns += [
        path('', AppHomeResponse(model_registry, app_name),  name='%s-home'%app_name),
    ]
    
    
    return urlpatterns



##############################################################################################################
##############################################################################################################

## generate names for urls -- used for reverse()
def getPageUrlName(Model):
    return '%s-%s'%( Model._meta.app_label, Model._meta.verbose_name_plural )

def getListUrlName(Model):
    return '%s-%s-list'%( Model._meta.app_label, Model._meta.verbose_name_plural )

def getDetailUrlName(Model):
    return '%s-%s'%( Model._meta.app_label, Model._meta.verbose_name)



## generate serializer for a model
REVRESE_M2M = models.fields.related_descriptors.ReverseManyToOneDescriptor
REVERSE_O2O = models.fields.related_descriptors.ReverseOneToOneDescriptor
def make_serializer_class(Model):
    class Serializer(serializers.ModelSerializer):
        class Meta:
            model  = Model
            fields = '__all__'
            # equal to __all__ -> fields = list( map( lambda field : field.name, Model._meta.fields ) ) +  list(map(lambda field : field.name, Model._meta.many_to_many))
    ##for attr_name in dir(Model):
    ##    attr = getattr(Model, attr_name)
    ##    if type(attr) == REVRESE_M2M:
    ##        ## to make change of relations replace read_only with queryset
    ##        ## RelatedModel = attr.rel.related_model ## queryset=RelatedModel.objects.all()
    ##        setattr(Serializer, attr_name, serializers.HyperlinkedRelatedField(many=True, view_name='accounts-home', read_only=True))
    ##        Serializer.Meta.fields.append(attr_name)
    return Serializer


## get object for a given model with pk
def get_object(Model, pk):
    try:
        return Model.objects.get(pk=pk)
    except Model.DoesNotExist:
        raise NotFound(detail="DoesNotExists pk:%s Model:%s"%(pk, Model.__name__ ))

## generate list view for a model
def make_list_view_class(Model):
    class ListView(ListCreateAPIView):
        
        def get_renderer_context(self):
            context = super().get_renderer_context()
            context['API_TITLE']  = API_TITLE
            context['logout_url'] = reverse(LOGOUT_PATH_NAME)
            context['login_url']  = reverse(LOGIN_PATH_NAME)
            return context

        queryset = Model.objects.all()
        serializer_class = make_serializer_class(Model)

        @login_required
        def get(self, request):
            return list_response_get(request, Model, make_serializer_class(Model))
        
        @login_required
        def post(self, request, format=None):
            return list_response_post(request, make_serializer_class(Model))
    ListView.__name__ = Model.__name__
    return ListView


def make_detail_view_class(Model):
    class DetailView(UpdateAPIView):
        queryset = Model.objects.all()
        serializer_class = make_serializer_class(Model)

        @login_required
        def get(self, request, pk):
            return detail_response_get(request, pk, Model, self.serializer_class)

        @login_required
        def put(self, request, pk, format=None):
            return detail_response_put(request, pk, Model, self.serializer_class)

        @login_required
        def delete(self, request, pk, format=None):
            return detail_response_delete(request, pk, Model)
    DetailView.__name__ = Model.__name__
    return DetailView

#################### view method implimentations #####################################


## url/appname/objects/?offset=10&count=12&orderby=name&reverse=true   -- count < 0 -> all objects
def filter_with_get_query(query : dict, Model : models.Model):
    offset  = query.get('offset', 0)
    count   = query.get('count', 10)
    orderby = query.get('orderby', None)
    reverse = query.get('reverse', 'false')
    objects = Model.objects.all()
    try:
        offset = max(int(offset), 0)    ## negative indexing not valid
        count  = int(count)
    except:
        offset = 0
        count  = DEFAULT_OBJECT_COUNT    
    try:
        ## clear unwanted query
        for attr in query:
            if query[attr] == 'false' : query[attr] = 'False'
            if query[attr] == 'true'  : query[attr] = 'True'
            if not hasattr(Model, attr): del query[attr]
        objects = objects.filter( **query )
    except:
        objects = Model.objects.none()
    if orderby :
        try:
            objects = objects.order_by('%s%s'%('-' if reverse == 'true' else '', orderby ))
        except:
            raise NotFound('InvalidOrderBy orderby:%s'%orderby)
    if count >= 0:
        objects = objects[ offset : count+1 ]
    return objects

def list_response_get(request, Model, Serializer):
    query_dict = dict()
    for q in request.GET:
        query_dict[q] = request.GET.get(q)
    objects = filter_with_get_query(query_dict, Model)
    serialized = Serializer(objects, many=True)
    return Response(serialized.data)


def list_response_post(request, Serializer):
    serializer = Serializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


## localhost:8000/app-name/model-name/pk/?download=file_name <-- for download any file field
def detail_response_get(request, pk, Model, Serializer):
    obj = get_object(Model, pk)
    ## download media
    download = request.GET.get('download')
    if download:
        if hasattr(obj, download):
            media = obj.__getattribute__(download)
            if not isinstance(media, File):
                raise NotFound(detail="AttributeNotMedia attr:%s Model:%s"%( download, Model.__name__ ))
            ## TODO: if manually delete the file from media and call the below line : FileNotFoundError raised
            response = FileResponse(media)
            response["Content-Disposition"] = "attachment; filename=" + os.path.split(media.name)[1]
            return response
        else:
            raise NotFound(detail="AttributeNotExists attr:%s Model:%s"%( download, Model.__name__ ))
        
    serialized = Serializer(obj)
    return Response(serialized.data)

def detail_response_put(request, pk, Model, Serializer):
    obj = get_object(Model, pk)
    serializer = Serializer(obj, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def detail_response_delete(request, pk, Model):
    obj = get_object(Model, pk)
    obj.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


##############################################################################################################
##############################################################################################################

def generate_ulr_page_response(request, urlctx, page_title):
    if 'HTTP_USER_AGENT' in request.META.keys():
        return render(request, 'urls-page.html', {
            'request': request,
            'title'  : page_title,
            'pages'  : urlctx,
            'API_TITLE': API_TITLE,
            'login_url' :  reverse(LOGIN_PATH_NAME),
            'logout_url' : reverse(LOGOUT_PATH_NAME),
        })
    ctx = dict()
    for page in urlctx: 
        ctx.update( { page.name : request.scheme + '://' + request.META['HTTP_HOST'] + page.url})
    return JsonResponse(ctx)

## context object to render url page
class UrlRenderCtx:
    def __init__(self, name, url):
        self.name = "%-10s"%name; self.url = url

class AppHomeResponse:
    ## model_registry is a list of django.db.models 
    def __init__(self, model_registry, app_name):
        self.model_registry = model_registry
        self.app_name = app_name

    @login_required
    def __call__(self, request):
        urlctx = []
        for Model in self.model_registry:
            urlctx.append( UrlRenderCtx(Model._meta.verbose_name_plural, reverse(getPageUrlName(Model))) )
        return generate_ulr_page_response(request, urlctx, self.app_name.capitalize())

class ObjectHomeResponse:
    def __init__(self, Model):
        self.title              = Model.__name__ 
        self.list_url_name      = getListUrlName(Model)
        self.detail_url_name    = getDetailUrlName(Model)
        self.Model              = Model
    
    @login_required
    def __call__(self, request):
        if 'HTTP_USER_AGENT' in request.META.keys():
            return render(request, 'objects.html', {
                'title'     : self.title,
                'request'   : request,
                'all_url'   : reverse(self.list_url_name),
                'urls' : [
                    reverse(self.detail_url_name, kwargs={'pk':obj.pk} ) for obj in self.Model.objects.all()
                ]
            })
        ctx = { 
            'List' :  reverse(self.list_url_name),
            'Detail' : [
                request.scheme +'://'+ request.META.HTTP_HOST + reverse(self.detail_url_name, kwargs={'pk':obj.pk} ) for obj in self.Model.objects.all()
            ]
        }
        return JsonResponse(ctx)

##############################################################################################################
##############################################################################################################


class LoginForm(forms.Form):
    username = forms.CharField(max_length=50)
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
    )


def login(request):
    ctx = { 'title': API_TITLE }
    ## redirects
    if request.user.is_authenticated:
        return redirect(HOME_PAGE_NAME)
    ## get
    elif request.method == 'GET':
        return render(request, 'login.html', ctx)
    ## post
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                auth.login(request, user)
                return redirect(HOME_PAGE_NAME)
            else:
                return render(request, 'login.html', {'username':username, 'error_message':"Invalid Username or Password" }.update(ctx))
        else:
            return render(request, 'login.html', {"error_message":"Invalid Login Form"}.update(ctx) )

def logout(request):
    auth.logout(request)
    return redirect(LOGIN_PATH_NAME)
