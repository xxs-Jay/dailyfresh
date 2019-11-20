from django.shortcuts import render
from django.views.generic import View
from django.shortcuts import render,redirect
from goods.models import GoodsType,GoodsSKU,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from order.models import OrderGoods
from django_redis import get_redis_connection

# Create your views here.
def index(request):
    '''显示首页'''
    # 获取商品的种类信息
    types = GoodsType.objects.all()

    # 获取首页商品轮播信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 获取首页活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取分类详情数据
    for type in types:
        #获取图片信息
        image_banner = IndexTypeGoodsBanner.objects.filter(type=type,display_type = 1).order_by('index')
        #获取文字信息
        title_banner = IndexTypeGoodsBanner.objects.filter(type=type,display_type = 0).order_by('index')

        #动态给type增加数据 分别保存首页分类商品的图片展示信息及文本信息
        type.image_banners = image_banner
        type.title_banners = title_banner
    #获取用户购物车的数据
    user = request.user
    cart_count = 0
    if user.is_authenticated():#判断当前是否登录
        #用户已登录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        cart_count = conn.hlen(cart_key)

    #组织上下文
    context = {
        'types':types,
        'goods_banners':goods_banners,
        'promotion_banners':promotion_banners,
        'cart_count':cart_count
    }
    return render(request,'index.html',context)

# /goods/商品id
class DetailView(View):
    '''详情页'''
    def get(self,request,goods_id):
        '''显示商品详情页'''
        try:
            sku = GoodsSKU.objects.get(id = goods_id)
        except GoodsSKU.DoesNotExist:
            #商品不存在
            return redirect(reversed('goods:index'))
        #获取商品的分类信息
        types = GoodsType.objects.all()
        #获取商品的品论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        #获取新品推荐
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        #获取同一SPU的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
        #获取用户购物车商品数量


        context = {

        }
        return render(request,'detail.html',context)








