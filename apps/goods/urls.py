from django.conf.urls import url
from goods import views
urlpatterns = [
    url('^$',views.index,name='index'),#首页



]
