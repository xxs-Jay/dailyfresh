from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse

from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMiXin

# Create your views here.
#添加商品到购物车
#1) 请求方式   ajax  post
#  如果涉及到数据的修改(新增、更新、删除)-----post
#  如果只是获取数据采用get
#2） 传递参数  商品id 商品数量（count）
# /cart/add
class CartAddView(View):
    """购物车记录添加"""
    def post(self,request):
        user = request.user
        if not user.is_authenticated():
            #用户未登录
            return JsonResponse({'res':0,'errmsg':'请先登录'})
        #接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        #数据校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})
        #校验商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数量异常'})
        #校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        #业务处理,添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_id%d'%user.id
        #先尝试获取sku_id的值   ---->  hget cart_key 属性
        #如果sku_id在hash中不存在，hget返回None
        cart_count = conn.hget(cart_key,sku_id)
        if cart_count:
            #累加购物车中的商品数量
            count += int(cart_count)
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})
        #设置hash中sku_id的值
        #hget---> 如果sku_id已存在  更新数据   如果sku_id 不存在  添加数据
        conn.hset(cart_key,sku_id,count)
        #计算用户购物车商品的条目数
        total_count = conn.hlen(cart_key)
        #返回
        return JsonResponse({'res': 5, 'total_count': total_count,'message':'添加成功'})


#购物车显示
class CartInfoView(LoginRequiredMiXin,View):
    def get(self,request):
        #获取用户
        user = request.user
        conn = get_redis_connection('default')
        cart_key = 'cart_id%d'%user.id
        cart_dict = conn.hgetall(cart_key)
        skus = []
        total_count = 0
        total_price = 0
        #遍历获取商品的信息
        for sku_id,count in cart_dict.items():
            sku = GoodsSKU.objects.get(id = sku_id)
            #计算商品的小计
            amount = sku.price * int(count)
            sku.amount = amount #动态给sku对象添加一个amount属性保存价格的小计
            sku.count = count
            skus.append(sku)
            #累计计算商品的总数及总价
            total_count += int(count)
            total_price += amount
        context = {
            'total_count':total_count,
            'total_price':total_price,
            'skus':skus,
            'skus_count':len(skus)
        }
        return render(request,'cart.html',context)

#更新购物车记录----ajax
#/cart/update
class CartUpdateView(View):
    def post(self,request):
        '''购物车记录更新'''
        user = request.user
        if not user.is_authenticated():
            #用户未登录
            return JsonResponse({'res':0,'errmsg':'请先登录'})
            # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        #校验商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数量异常'})
        #校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        #业务处理,更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_id%d'%user.id
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})
        #更新
        conn.hset(cart_key,sku_id,count)
        #计算总件数  {'1':5, '2':3}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        #返回
        return JsonResponse({'res':5,'total_count':total_count,'message':'更新成功'})

#删除购物车记录
class CartDeleteView(View):
    '''删除购物车记录'''
    def post(self,request):
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 1, 'errmsg': '请先登录'})
        #获取商品的id
        sku_id = request.POST.get('sku_id')
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
        #业务处理,更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_id%d'%user.id
        conn.hdel(cart_key,sku_id)
        # 计算总件数  {'1':5, '2':3}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        return JsonResponse({'res':3,'total_count':total_count,'message':'删除成功'})







