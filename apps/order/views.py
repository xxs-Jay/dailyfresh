from django.shortcuts import render,redirect
from django.views.generic import View
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import JsonResponse
from django.conf import settings

from order.models import OrderInfo,OrderGoods
from goods.models import GoodsSKU
from user.models import Address
from datetime import datetime
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMiXin


from alipay import AliPay
import os
# Create your views here.
# /order/place
class OrderPlaceView(LoginRequiredMiXin,View):
    '''提交订单的显示页面'''
    def post(self,request):
        user = request.user
        #获取所选商品的id
        sku_ids = request.POST.getlist('sku_ids')
        #校验参数
        if not sku_ids:
            return redirect(reverse('cart:show'))
        conn = get_redis_connection('default')
        cart_key = 'cart_id%d'%user.id
        skus = []
        total_count = 0
        total_price = 0
        #遍历商品数据
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id = sku_id)
            count = conn.hget(cart_key,sku_id)
            #小计
            amount = sku.price * int(count)
            sku.amount = amount
            sku.count = count
            skus.append(sku)
            total_count += int(count) #总数量
            total_price += amount #总价格
        #运费------实际开发中为单独物流子系统
        transit_price = 10
        #实付款
        total_pay = total_price + transit_price
        #用户地址
        addrs = Address.objects.filter(user = user)
        sku_ids = ','.join(sku_ids) #[1,25]  --->  1,25
        context = {
            'skus':skus,
            'total_count':total_count,
             'total_price':total_price,
            'transit_price':transit_price,
            'total_pay':total_pay,
            'addrs':addrs,
            'sku_ids':sku_ids
        }
        return render(request,'place_order.html',context)


#接收参数 addr_id  支付方式(微信、支付宝)   购买的商品（sku_ids）  ----str
#/order/commit
#订单生成--提交
class OrderCommitView(View):
    '''订单创建'''
    @transaction.atomic
    def post(self,request):
        user = request.user
        if not user.is_authenticated():
            #用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        #获取数据
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        #校验参数
        if not all([addr_id,pay_method,sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        #校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
        #if pay_method not in OrderInfo.PAY_METHOD_CHOICES().keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})

        #校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址异常'})
        # todo :  创建订单核心业务
        #组织参数   订单id   日期+用户id
        order_id  = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

        #运费
        transit_price = 10

        #总数量和总价格
        total_count = 0
        total_price = 0

        #设置事务的保存点
        save_id = transaction.savepoint()
        try:
            order = OrderInfo.objects.create(order_id=order_id,
                                             user = user,
                                             addr = addr,
                                             pay_method = pay_method,
                                             total_count = total_count,
                                             total_price = total_price,
                                             transit_price = transit_price)
            #todo:用户订单中的商品   -----OrderGoods添加数据
            conn = get_redis_connection('default')
            cart_key = 'cart_id%d' % user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                #获取订单中所有商品
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                print('user:%d stock:%d'%(user.id, sku.stock))
                import time
                time.sleep(10)

                #从redis中获取用户所购买的商品数量
                count = conn.hget(cart_key,sku_id)
                #todo: 判断商品库存
                if int(count)>sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 5, 'errmsg': '商品库存不足'})

                # todo: 向OrderGoods中添加数据
                OrderGoods.objects.create(order=order,
                                          sku = sku,
                                          count = count,
                                          price = sku.price
                                          )
                #todo 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo 累计计算商品的总数量和总价格
                acount = sku.price*int(count)
                total_count +=int(count)
                total_price += acount
            #todo 更新订单表中的总数量和总价格---覆盖
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 6, 'errmsg': '下单失败'})

        #todo 提交事务
        transaction.savepoint_commit(save_id)
        # todo 清除购物车对应记录
        conn.hdel(cart_key,*sku_ids)

        return JsonResponse({'res':7,'message':'创建成功'})


# ajax    post
#/order/pay
class OrderPayView(View):
    def post(self,request):
        #判断用户登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        #接收参数-----订单Id
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2 , 'errmsg': '订单异常'})
        #todo  支付业务处理
        #初始化-----AliPay
        alipay = AliPay(
            appid="2016101700706711",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        # 运费
        transit_price = 10
        total_pay = order.total_price + transit_price
        #调用支付宝接口
        try:
            order_string = alipay.api_alipay_trade_page_pay(
                out_trade_no=str(order_id),  # 订单id
                total_amount=str(total_pay),  # 支付总金额
                subject='天天生鲜%s'%order_id,
                return_url=None,
                notify_url=None  # 可选, 不填则使用默认notify url
            )
        except Exception as e:
            print(e)    #alipaydev     alipay-真实支付
        pay_utl = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3,'pay_url':pay_utl})


# ajax post
# 前端传递的参数:订单id(order_id)
# /order/check
class CheckPayView(View):
    '''查看订单支付的结果'''
    def post(self, request):
        '''查询支付结果'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016090800464054",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付宝的交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(order_id)

            # response = {
            #         "trade_no": "2017032121001004070200176844", # 支付宝交易号
            #         "code": "10000", # 接口调用是否成功
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS", # 支付结果
            #         "total_amount": "20.00"
            # }

            code = response.get('code')

            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4 # 待评价
                order.save()
                # 返回结果
                return JsonResponse({'res':3, 'message':'支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res':4, 'errmsg':'支付失败'})







