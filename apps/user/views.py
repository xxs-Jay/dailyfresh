from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.conf import settings
from django.http import HttpResponse
from django.core.mail import send_mail
from django.contrib.auth import authenticate,login,logout
from django_redis import get_redis_connection
from user.models import User,Address
from goods.models import GoodsSKU

from celery_tasks.tasks import send_register_active_email
from utils.mixin import LoginRequiredMiXin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
import re
# Create your views here.
# /user/register
def register(request):
    '''注册页面跳转'''
    return render(request,'register.html')

def register_handle(request):
    ''' 注册业务 '''
    # 1、接收数据
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    # 2、数据校验
    if not all([username,password,email]):
        return render(request,'register.html',{'errmsg':"数据不完整"})
    # 3、校验邮箱
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
        return render(request, 'register.html', {'errmsg': "邮箱格式不正确"})
    if allow != 'on':
        return render(request, 'register.html', {'errmsg': "请同意注册协议"})
    # 4、查重用户
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        #用户不存在
        user=None
    if user:
        #用户已存在
        return render(request, 'register.html', {'errmsg': "用户已存在"})
    # 5、进行业务处理：进行用户注册
    user = User.objects.create_user(username,email,password)
    user.is_active = 0
    user.save()
    # 6、注册成功，跳转到首页
    return redirect(reverse('goods:index'))

# user/register
class RegisterView(View):
    def get(self,request):
        '''注册页面跳转'''
        return render(request, 'register.html')
    def post(self,request):
        ''' 注册业务 '''
        # 1、接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 2、数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': "数据不完整"})
        # 3、校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': "邮箱格式不正确"})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': "请同意注册协议"})
        # 4、查重用户
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户不存在
            user = None
        if user:
            # 用户已存在
            return render(request, 'register.html', {'errmsg': "用户已存在"})
        # 5、进行业务处理：进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0 #未激活状态
        user.save()
        #发送激活邮件，包含激活链接：http://127.0.0.1/user/active/1
        #激活链接需要包含用户的身份信息，并且需要对身份进行加密

        #加密用户的身份信息，生成token
        serializer = Serializer(settings.SECRET_KEY,3600)
        info = {'confirm':user.id} #身份信息
        token = serializer.dumps(info) #bytes
        token = token.decode()
        #发送邮件
        # 发邮件
        send_register_active_email.delay(email, username, token)
        # subject = "天天生鲜欢迎信息"
        # message = ""
        # html_message = "<h1>%s，欢迎您成为天天生鲜注册会员<h1>请点击下面链接激活您的账户<br/>" \
        #                "<a href='http://127.0.0.1:8000/user/active/%s'>http://127.0.0.1:8000/user/active/%s</a>"%(username,token,token)
        # sender = settings.EMAIL_FROM
        # receiver = [email] #注册邮箱
        # send_mail(subject,message,sender,receiver,html_message=html_message)

        # 6、注册成功，跳转到首页
        return redirect(reverse('goods:index'))

class ActiveView(View):
    def get(self,request,token):
        '''进行用户激活'''
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            #根据用户id 修改is_active   1
            user = User.objects.get(id = user_id)
            user.is_active = 1
            user.save()
            #跳转登陆页面----反向解析
            return redirect(reverse('user:login'))
        except SignatureExpired as e:   #实际业务---再次发送一个链接用于激活
            return HttpResponse('激活链接失效')

class LoginView(View):
    def get(self,request):
        '''显示登录页面'''
        #判断是记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request,'login.html',{'username':username,'checked':checked})

    def post(self, request):
        '''登录校验'''
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 业务处理:登录校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request, user)
                # # 跳转到首页
                #response = redirect(reverse('goods:index'))  # HttpResponseRedirect

                #获取登陆后要跳转的地址
                #默认跳转到首页
                next_url = request.GET.get('next',reverse('goods:index'))
                #跳转到next_url
                response = redirect(next_url) # HttpResponseRedirect
                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                else:
                    response.delete_cookie('username')
                # 返回response
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})

class LogoutView(View):
    def get(self,request):
        '''退出登录'''
        #清除用户的session信息
        logout(request)
        #跳转到首页面
        return redirect(reverse('goods:index'))

class UserCenterInfoView(LoginRequiredMiXin,View):
    '''用户中心-个人中心'''
    def get(self,request):
        #django会给request对象添加一个属性   request.user
        #如果用户未登录-->user是AnonymousUser类中的实例对象
        #如果用户登陆-->user是User类的一个实例对象
        # request.user.is_anthenticated()
        #获取用户数据
        user = request.user
        # 获取用户的默认收货地址
        try:
            address = Address.objects.get(user=user, is_default=True)
        except Exception as e:
            return render(request, 'user_center_info.html', {'page': 'user','address':address})
        #获取用户的浏览痕迹'----redis
        con = get_redis_connection('default')

        history_key = 'history_%d'%user.id

        #获取用户最新浏览的5个商品id
        sku_ids = con.lrange(history_key,0,4)

        #从数据库中查询用户浏览的商品详细信息----mysql
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        # goods_res = []
        # for a_id in sku_ids:
        #     for goods in goods_li:
        #         if a_id ==goods.id:
        #             goods_res.append(goods)
        #遍历获取用户浏览的商品数据
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id = id)
            goods_li.append(goods)
        #组织上下文
        context = {
            'page':'user',
            'address':address,
            'goods_li':goods_li
        }
        return render(request, 'user_center_info.html',context)

class UserCenterOrderView(LoginRequiredMiXin,View):
    '''用户中心-订单'''
    def get(self,request):
        return render(request, 'user_center_order.html',{'page':'order'})

class UserCenterAddressView(LoginRequiredMiXin,View):
    '''用户中心-地址'''
    def get(self,request):
        user = request.user
        #获取用户的默认收货地址
        try:
            address = Address.objects.get(user=user,is_default=True)
        except Exception as e:
            return render(request, 'user_center_site.html', {'page': 'address'})
        #address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html',{'page':'address','address':address})
    def post(self,request):
        #接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone =request.POST.get('phone')
        #校验数据
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errmsg':'数据不完整'})
        #校验手机号
        if not re.match(r'^1[3|4|5|7|8|9][0-9]{9}$',phone):
            return render(request,'user_center_site.html',{'errmsg':'手机格式不正确'})
        #业务处理
        #如果用户存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        user = request.user

        #address = Address.objects.get_default_address(user)
        try:
            address = Address.objects.get(user=user, is_default=True)
        except Exception as e:
            address = None
        if address:
            is_default = False
        else:
            is_default = True
        #添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)
        return redirect(reverse('user:address'))






