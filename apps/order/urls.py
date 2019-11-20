from django.conf.urls import url
from order.views import OrderPlaceView,OrderCommitView,OrderPayView,CheckPayView

urlpatterns = [
    url(r'^place$',OrderPlaceView.as_view(),name='place'),#订单显示页面
    url(r'^commit$', OrderCommitView.as_view(), name='cmmit'),  # 订单显示页面
    url(r'^pay$', OrderPayView.as_view(), name='pay'),  # 订单显示页面
    url(r'^check$', CheckPayView.as_view(), name='check'), # 查询支付交易结果
]
