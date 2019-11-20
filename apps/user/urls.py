from django.conf.urls import url
from user.views import RegisterView,ActiveView,LoginView,LogoutView,UserCenterInfoView,UserCenterOrderView,UserCenterAddressView

urlpatterns = [
    # url(r'^register$',views.register,name='register'),#注册
    # url(r'^register_handle$',views.register_handle,name='register_handle'),#注册业务
    url(r'^register$',RegisterView.as_view(),name='register'),
    url(r'^active/(?P<token>.*)$',ActiveView.as_view(),name='active'),
    url(r'^login', LoginView.as_view(), name='login'),
    url(r'^logout', LogoutView.as_view(), name='logout'),

    url(r'^$', UserCenterInfoView.as_view(), name='user'),
    url(r'^order/(?P<page>\d+)$', UserCenterOrderView.as_view(), name='order'), # 用户中心-订单页
    url(r'^address', UserCenterAddressView.as_view(), name='address'),

]
